"""VisualLab — AI dashboards for academic papers (VisualScholar), GitHub repos
(VisualRepo), Wikipedia articles (VisualPedia), and museum artworks (VisualArt).

Originally built as a side-project by Anselm Ohme (PhD student at ESCP) to make
research / repos / topics easier to skim.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import re
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from typing import Any, Iterable

import arxiv
import requests
import wikipediaapi
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from openai import OpenAI
from pypdf import PdfReader

load_dotenv(override=True)

# ----- Rate limiting (per-IP, sliding window) ------------------------------
# Protects the NVIDIA quota from a single visitor scripting the endpoint.
# Single gunicorn worker (see render.yaml) means in-memory state is sufficient.
from collections import defaultdict

RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
_RATE_BUCKETS: "dict[str, list[float]]" = defaultdict(list)
_RATE_LOCK = threading.Lock()


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit(scope: str) -> "tuple[bool, int]":
    """Returns (allowed, retry_after_seconds). Records a hit if allowed."""
    if RATE_LIMIT_PER_HOUR <= 0:
        return True, 0
    key = f"{scope}:{_client_ip()}"
    now = time.time()
    cutoff = now - 3600.0
    with _RATE_LOCK:
        bucket = [t for t in _RATE_BUCKETS[key] if t > cutoff]
        _RATE_BUCKETS[key] = bucket
        if len(bucket) >= RATE_LIMIT_PER_HOUR:
            retry = int(3600.0 - (now - min(bucket))) + 1
            return False, retry
        bucket.append(now)
        return True, 0


NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "z-ai/glm-5.1")
NVIDIA_TIMEOUT = float(os.getenv("NVIDIA_TIMEOUT", "300"))
WIKI_USER_AGENT = os.getenv("WIKI_USER_AGENT", "VisualLab (contact@example.com)")
WIKI_LANGUAGE = os.getenv("WIKI_LANGUAGE", "en")

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
SEMANTIC_SCHOLAR_BASE_URL = os.getenv(
    "SEMANTIC_SCHOLAR_BASE_URL", "https://api.semanticscholar.org/graph/v1"
)
SEMANTIC_SCHOLAR_TIMEOUT = float(os.getenv("SEMANTIC_SCHOLAR_TIMEOUT", "20"))
SEMANTIC_SCHOLAR_MIN_INTERVAL = float(
    os.getenv("SEMANTIC_SCHOLAR_RATE_LIMIT", "1.1")
)

# --- GitHub (VisualRepo) --------------------------------------------------
# Optional token: lifts unauthed REST quota from 60/h to 5000/h. Recommended.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_BASE_URL = os.getenv("GITHUB_BASE_URL", "https://api.github.com")
GITHUB_TIMEOUT = float(os.getenv("GITHUB_TIMEOUT", "15"))
MAX_README_CHARS = 14000

# --- Art (Met Museum) -----------------------------------------------------
MET_BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
MET_TIMEOUT = float(os.getenv("MET_TIMEOUT", "12"))
MET_SEARCH_LIMIT = 25  # we filter Met IDs down to ~10 with images locally

# The Met's edge (Cloudflare) regularly returns 403 to non-browser-shaped
# requests — especially from cloud IPs like Render — when the User-Agent
# looks like a polite bot string ("MyApp (contact@x)"). Sending a full
# browser-style header set has been the reliable workaround. Override via
# MET_USER_AGENT if you ever need to.
MET_USER_AGENT = os.getenv(
    "MET_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
)
MET_HEADERS = {
    "User-Agent": MET_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.metmuseum.org/",
    "Origin": "https://www.metmuseum.org",
}

# --- Shareable dashboards -------------------------------------------------
# Saved to disk so a generated dashboard can be opened later via /d/<slug>.
# On Render's free tier the filesystem is ephemeral — shares survive until the
# next deploy / wake from sleep. That's plenty for "send link to colleague this
# week" but worth being honest about in the share UI.
SHARE_DIR = pathlib.Path(os.getenv("SHARE_DIR", "data/shared"))
SHARE_DIR.mkdir(parents=True, exist_ok=True)
SHARE_MAX_HTML_BYTES = 6 * 1024 * 1024  # 6 MB ceiling per share
SHARE_RETENTION_DAYS = int(os.getenv("SHARE_RETENTION_DAYS", "30"))
SHARE_SLUG_RE = re.compile(r"^[A-Za-z0-9]{6,16}$")

# --- Email (SMTP) ---------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER).strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "VisualLab").strip()
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}
SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT", "20"))
EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASSWORD and SMTP_FROM_EMAIL)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# --- Wikipedia caps -------------------------------------------------------
MAX_TEXT_CHARS = 18000
MAX_SECTION_CHARS = 1200
MAX_SECTIONS = 40
MAX_LINKS = 60
MAX_CATEGORIES = 30
MAX_IMAGES = 12

# --- arXiv caps -----------------------------------------------------------
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_CHARS = 28000
PDF_DOWNLOAD_TIMEOUT = 25

AVAILABLE_MODELS = [
    {"id": "z-ai/glm4.7", "label": "GLM 4.7 — fast, UI-tuned (default)"},
    {"id": "mistralai/mistral-medium-3.5-128b", "label": "Mistral Medium 3.5 — fast text & code"},
    {"id": "deepseek-ai/deepseek-v4-flash", "label": "DeepSeek v4 Flash — speed-optimized"},
    {"id": "z-ai/glm-5.1", "label": "GLM 5.1 — deeper reasoning, slower"},
    {"id": "minimaxai/minimax-m2.7", "label": "MiniMax M2.7 — 230B, best quality, slowest"},
    {"id": "deepseek-ai/deepseek-v4-pro", "label": "DeepSeek v4 Pro — slow / may queue"},
]


def _chat_template_kwargs_for(model: str) -> dict | None:
    m = model.lower()
    if m.startswith("z-ai/") or "glm" in m:
        return {"enable_thinking": False, "clear_thinking": False}
    if "deepseek" in m:
        return {"thinking": False}
    return None


app = Flask(__name__)

_wiki = wikipediaapi.Wikipedia(
    user_agent=WIKI_USER_AGENT,
    language=WIKI_LANGUAGE,
    extract_format=wikipediaapi.ExtractFormat.WIKI,
)
_arxiv = arxiv.Client(page_size=10, delay_seconds=2.0, num_retries=3)
_openai = OpenAI(
    base_url=NVIDIA_BASE_URL,
    api_key=NVIDIA_API_KEY,
    timeout=NVIDIA_TIMEOUT,
    max_retries=0,
)


# ---------------------------------------------------------------------------
# Wikipedia helpers
# ---------------------------------------------------------------------------

def _flatten_sections(sections, level: int = 1, out: list[dict] | None = None) -> list[dict]:
    if out is None:
        out = []
    for s in sections:
        if len(out) >= MAX_SECTIONS:
            return out
        out.append({
            "level": level,
            "title": s.title,
            "text": (s.text or "")[:MAX_SECTION_CHARS],
        })
        _flatten_sections(s.sections, level + 1, out)
    return out


def _extract_wiki_data(title: str) -> dict[str, Any]:
    page = _wiki.page(title)
    if not page.exists():
        return {"error": f"No Wikipedia article found for '{title}'."}

    summary = (page.summary or "")[:4000]
    sections = _flatten_sections(page.sections)
    full_text = (page.text or "")[:MAX_TEXT_CHARS]

    try:
        categories = list(page.categories.keys())[:MAX_CATEGORIES]
    except Exception:
        categories = []
    try:
        links = list(page.links.keys())[:MAX_LINKS]
    except Exception:
        links = []

    image_urls: list[str] = []
    try:
        for _t, img in list(page.images.items())[:MAX_IMAGES]:
            try:
                url = img.url
                if url and not url.lower().endswith((".svg", ".ogg", ".webm")):
                    image_urls.append(url)
            except Exception:
                continue
    except Exception:
        pass

    coords = []
    try:
        for c in page.coordinates or []:
            coords.append({"lat": c.lat, "lon": c.lon, "primary": c.primary})
    except Exception:
        pass

    return {
        "title": page.title,
        "url": page.fullurl,
        "summary": summary,
        "sections": sections,
        "full_text": full_text,
        "categories": categories,
        "links": links,
        "images": image_urls,
        "coordinates": coords,
    }


# ---------------------------------------------------------------------------
# arXiv helpers
# ---------------------------------------------------------------------------

_ARXIV_ID_RE = re.compile(r"(?:arxiv:|abs/|/pdf/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+/\d{7}(?:v\d+)?)", re.I)


def _looks_like_arxiv_id(query: str) -> str | None:
    m = _ARXIV_ID_RE.search(query.strip())
    if m:
        return m.group(1)
    return None


def _result_to_dict(r: arxiv.Result) -> dict[str, Any]:
    return {
        "id": r.entry_id,
        "short_id": r.get_short_id(),
        "title": r.title.strip(),
        "authors": [a.name for a in r.authors],
        "summary": (r.summary or "").strip(),
        "published": r.published.isoformat() if r.published else None,
        "updated": r.updated.isoformat() if r.updated else None,
        "primary_category": r.primary_category,
        "categories": list(r.categories),
        "comment": r.comment,
        "journal_ref": r.journal_ref,
        "doi": r.doi,
        "pdf_url": r.pdf_url,
        "abs_url": r.entry_id,
    }


def _arxiv_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    arxiv_id = _looks_like_arxiv_id(query)
    if arxiv_id:
        search = arxiv.Search(id_list=[arxiv_id])
    else:
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance,
        )
    return [_result_to_dict(r) for r in _arxiv.results(search)]


def _fetch_paper(arxiv_id: str) -> dict[str, Any] | None:
    search = arxiv.Search(id_list=[arxiv_id])
    for r in _arxiv.results(search):
        return _result_to_dict(r)
    return None


def _download_pdf_text(pdf_url: str) -> tuple[str, int]:
    """Download arXiv PDF and extract text. Returns (text, num_pages). Soft-fails."""
    try:
        with requests.get(pdf_url, stream=True, timeout=PDF_DOWNLOAD_TIMEOUT,
                          headers={"User-Agent": WIKI_USER_AGENT}) as resp:
            resp.raise_for_status()
            buf = io.BytesIO()
            total = 0
            for chunk in resp.iter_content(64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    break
                buf.write(chunk)
            buf.seek(0)
        reader = PdfReader(buf)
        pages: list[str] = []
        chars = 0
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            pages.append(t)
            chars += len(t)
            if chars >= MAX_PDF_CHARS:
                break
        text = "\n\n".join(pages)
        # Light cleanup: collapse runs of whitespace.
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:MAX_PDF_CHARS], len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("PDF fetch failed for %s: %s", pdf_url, exc)
        return "", 0


# ---------------------------------------------------------------------------
# Semantic Scholar helpers
# ---------------------------------------------------------------------------

S2_SEARCH_FIELDS = (
    "paperId,title,abstract,year,authors.name,citationCount,influentialCitationCount,"
    "venue,publicationDate,fieldsOfStudy,externalIds,openAccessPdf,tldr"
)
S2_DETAIL_FIELDS = (
    "paperId,title,abstract,year,authors.name,authors.affiliations,citationCount,"
    "influentialCitationCount,referenceCount,venue,publicationVenue,publicationDate,"
    "fieldsOfStudy,s2FieldsOfStudy,externalIds,openAccessPdf,tldr,journal,"
    "references.title,references.year,references.authors"
)
MAX_S2_REFERENCES = 25


def _s2_headers() -> dict[str, str]:
    h = {"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"}
    if SEMANTIC_SCHOLAR_API_KEY:
        h["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return h


_S2_RATE_LOCK = threading.Lock()
_S2_LAST_CALL = 0.0


def _s2_throttle() -> None:
    """Block until at least SEMANTIC_SCHOLAR_MIN_INTERVAL has passed since last call."""
    global _S2_LAST_CALL
    with _S2_RATE_LOCK:
        now = time.monotonic()
        wait = SEMANTIC_SCHOLAR_MIN_INTERVAL - (now - _S2_LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        _S2_LAST_CALL = time.monotonic()


def _s2_request(path: str, params: dict | None = None) -> dict:
    _s2_throttle()
    url = f"{SEMANTIC_SCHOLAR_BASE_URL}{path}"
    resp = requests.get(
        url, params=params, headers=_s2_headers(), timeout=SEMANTIC_SCHOLAR_TIMEOUT
    )
    if resp.status_code == 429:
        raise RuntimeError(
            "Semantic Scholar rate limited (429). Without an API key the shared "
            "anonymous quota is small — set SEMANTIC_SCHOLAR_API_KEY in .env."
        )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Semantic Scholar {resp.status_code}: {resp.text[:200]}"
        )
    return resp.json()


def _s2_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    data = _s2_request(
        "/paper/search",
        {"query": query, "limit": min(limit, 25), "fields": S2_SEARCH_FIELDS},
    )
    out: list[dict[str, Any]] = []
    for p in data.get("data", []) or []:
        if not p:
            continue
        out.append(_s2_to_dict(p))
    return out


def _s2_fetch(paper_id: str) -> dict[str, Any] | None:
    # Accepts S2 paperId, DOI:..., ARXIV:..., URL:..., etc per S2 docs.
    data = _s2_request(f"/paper/{paper_id}", {"fields": S2_DETAIL_FIELDS})
    if not data:
        return None
    return _s2_to_dict(data, include_refs=True)


def _s2_to_dict(p: dict, include_refs: bool = False) -> dict[str, Any]:
    authors = [a.get("name") for a in (p.get("authors") or []) if a and a.get("name")]
    open_pdf = p.get("openAccessPdf") or {}
    pdf_url = open_pdf.get("url") if isinstance(open_pdf, dict) else None
    external = p.get("externalIds") or {}
    arxiv_id = external.get("ArXiv") or external.get("arXiv")
    doi = external.get("DOI") or p.get("doi")
    tldr = p.get("tldr") or {}
    out: dict[str, Any] = {
        "id": p.get("paperId"),
        "short_id": p.get("paperId"),
        "title": (p.get("title") or "").strip(),
        "authors": authors,
        "summary": (p.get("abstract") or "").strip(),
        "tldr": (tldr.get("text") if isinstance(tldr, dict) else None) or "",
        "year": p.get("year"),
        "published": p.get("publicationDate") or (str(p.get("year")) if p.get("year") else None),
        "venue": p.get("venue") or (p.get("publicationVenue") or {}).get("name"),
        "journal": (p.get("journal") or {}).get("name") if isinstance(p.get("journal"), dict) else None,
        "fields_of_study": p.get("fieldsOfStudy") or [
            f.get("category") for f in (p.get("s2FieldsOfStudy") or []) if isinstance(f, dict)
        ],
        "categories": p.get("fieldsOfStudy") or [],
        "citation_count": p.get("citationCount"),
        "influential_citation_count": p.get("influentialCitationCount"),
        "reference_count": p.get("referenceCount"),
        "doi": doi,
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "abs_url": (
            f"https://www.semanticscholar.org/paper/{p.get('paperId')}"
            if p.get("paperId") else None
        ),
        "primary_category": (p.get("fieldsOfStudy") or [None])[0],
    }
    if include_refs:
        refs = p.get("references") or []
        out["references"] = [
            {
                "title": (r.get("title") or "").strip(),
                "year": r.get("year"),
                "authors": [a.get("name") for a in (r.get("authors") or []) if a and a.get("name")][:5],
            }
            for r in refs[:MAX_S2_REFERENCES]
            if r and r.get("title")
        ]
    return out


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PEDIA_SYSTEM_PROMPT = """You are VisualPedia, an expert data-visualization designer.

You will receive structured data extracted from a Wikipedia article. Produce a
SINGLE self-contained HTML document that renders a beautiful, informative,
*alive* DASHBOARD about the article's subject. The reader should feel motion
the moment the page loads.

HARD REQUIREMENTS
- Output ONLY raw HTML. No markdown fences, no commentary.
- Complete valid HTML5 page (`<!DOCTYPE html>` ... `</html>`) that runs standalone in an iframe.
- Allowed CDNs only: cdn.tailwindcss.com, cdn.jsdelivr.net (Chart.js, ApexCharts,
  Leaflet, KaTeX, anime.js, GSAP), unpkg.com, fonts.googleapis.com.
- Use Tailwind for styling. Modern dark theme, glassmorphism, vivid accent that fits the topic.
- Use Chart.js for charts.
- Include AT LEAST:
    * Hero header with title, a tagline you write, and a button linking back to Wikipedia.
    * 3-6 KPI / stat cards with concrete numbers from the data (years, counts, etc.).
    * At least TWO genuine charts reflecting the data.
    * 2-4 short paragraphs of "Key facts" written by you.
    * A "Sections at a glance" panel listing the main sections.
    * A small image gallery if `images` are provided (use URLs verbatim).
    * A Leaflet map if `coordinates` are provided.
- NEVER fabricate facts that contradict the source. If unsure, omit.

MOTION & MICRO-INTERACTIONS (mandatory — the page must feel alive)
Use GSAP (gsap.min.js + ScrollTrigger) OR anime.js for orchestration. Required:
1. STAGGERED entrance animations for the hero and the first row of cards
   (translateY + opacity, ease-out, ~80ms stagger).
2. ANIMATED COUNTERS on every numeric KPI card (count up from 0 to the real
   value over ~1.2s).
3. SCROLL-TRIGGERED reveals on every major section as it enters the viewport
   (use GSAP ScrollTrigger or IntersectionObserver).
4. HOVER MICRO-INTERACTIONS on cards (subtle scale, glow, or accent slide-in).
5. CHART animations (Chart.js animations enabled, not disabled).
6. A subtle gradient or radial-glow that drifts in the background of the hero
   (CSS keyframes or canvas, slow loop).

Make the motion *tasteful* — quick, smooth, in service of the content. Avoid
gimmicks (no spinning logos, no bouncing text). Reduce motion if the user has
`prefers-reduced-motion: reduce` set (wrap animation calls in a media query).

Begin with `<!DOCTYPE html>` and end with `</html>`. Nothing else.
"""


SCHOLAR_SYSTEM_PROMPT = """You are VisualScholar, an expert at turning academic
papers into INTERACTIVE, ANIMATED visual explainers.

You will receive structured metadata for an arXiv paper plus an excerpt of its
full text. Produce a SINGLE self-contained HTML document that renders a
beautiful, animated, interactive DASHBOARD about the paper.

HARD REQUIREMENTS
- Output ONLY raw HTML. No markdown fences, no commentary.
- Complete valid HTML5 page (`<!DOCTYPE html>` ... `</html>`) that runs standalone in an iframe.
- Allowed CDNs only: cdn.tailwindcss.com, cdn.jsdelivr.net
  (Chart.js, ApexCharts, KaTeX, anime.js, GSAP + ScrollTrigger, three.js),
  unpkg.com, fonts.googleapis.com.
- Use Tailwind for styling. Modern dark theme with subtle glassmorphism. Pick an
  accent color that fits the field (e.g. cyan/blue for ML, magenta for physics,
  green for biology).
- Render math properly: load KaTeX from cdn.jsdelivr.net/npm/katex@0.16.11/dist/
  and call renderMathInElement on relevant containers. Wrap inline math in $...$
  and display math in $$...$$.

DASHBOARD MUST CONTAIN
1. HERO with paper title, authors, primary arXiv category badge, publication
   date, and a single button linking to the abstract page (do NOT add a "PDF"
   button — direct PDF links from arXiv / Semantic Scholar are unreliable in
   the iframe sandbox).
2. A "TL;DR" panel with a 3-4 sentence plain-language summary YOU write,
   distilled from the abstract and excerpt.
3. KEY CONTRIBUTIONS list (3-6 bullets), each with a small icon (inline SVG).
4. A "METHODOLOGY" or "HOW IT WORKS" section that uses ANIMATED VISUALS to
   explain any process described in the paper. Use one or more of:
     - Inline SVG with `<animate>` / `<animateTransform>` tags
     - CSS keyframe animations for flow diagrams
     - anime.js or GSAP for staged reveals and timeline-based orchestration
     - GSAP ScrollTrigger to advance an explanation as the user scrolls
     - A small interactive simulation if appropriate (e.g. a slider that drives
       a chart). DO NOT just produce a static block of text — there MUST be
       continuous, looping motion in this section.
5. A RESULTS / FINDINGS section with at least one Chart.js chart that genuinely
   reflects numbers, comparisons, or qualitative claims from the paper. If no
   numbers are explicit, use a comparative qualitative chart (e.g. radar of
   strengths) and label it "Qualitative comparison — not from raw data".
6. A "KEY EQUATIONS" section if any math is present in the excerpt: render 1-3
   relevant equations with KaTeX and a one-line plain-English explanation under
   each.
7. A METADATA strip at the bottom: arXiv id, primary category, all categories,
   submission date, last updated, DOI / journal-ref if available, page count.

INTERACTIVITY
- At least one section must be interactive: tabs, accordion, slider, hover
  reveal, or a toggle that switches a diagram between two states.
- All animations should auto-play but also be triggerable / replayable via a
  button.
- Add staggered entrance animations on the hero and the first row of cards
  (translateY + opacity, ease-out, ~80ms stagger) and scroll-triggered reveals
  on every subsequent section.
- Respect `prefers-reduced-motion: reduce` — wrap timeline calls so reduced-
  motion users get instant transitions instead of long animations.

CONSTRAINTS
- Do NOT invent statistics. If a number isn't in the provided data, write a
  qualitative claim instead.
- Quote at most one short sentence from the paper verbatim; everything else
  should be paraphrased in clearer language.
- Keep total output under ~10000 tokens.

Begin with `<!DOCTYPE html>` and end with `</html>`. Nothing else.
"""


def _build_pedia_user_prompt(data: dict[str, Any]) -> str:
    payload = {
        "title": data["title"],
        "url": data["url"],
        "summary": data["summary"],
        "sections": [
            {"level": s["level"], "title": s["title"], "preview": s["text"][:400]}
            for s in data["sections"]
        ],
        "categories": data["categories"],
        "related_links": data["links"],
        "images": data["images"],
        "coordinates": data["coordinates"],
        "excerpt": data["full_text"][:6000],
    }
    return (
        "Build a dashboard for the following Wikipedia article. Use the data "
        "verbatim where possible; do not invent statistics.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def _build_scholar_user_prompt(meta: dict[str, Any], pdf_text: str, num_pages: int,
                                source: str) -> str:
    payload = {
        "source": source,
        "title": meta.get("title"),
        "authors": meta.get("authors"),
        "abs_url": meta.get("abs_url"),
        "pdf_url": meta.get("pdf_url"),
        "primary_category": meta.get("primary_category"),
        "categories": meta.get("categories") or meta.get("fields_of_study"),
        "published": meta.get("published"),
        "updated": meta.get("updated"),
        "doi": meta.get("doi"),
        "journal_ref": meta.get("journal_ref") or meta.get("journal"),
        "venue": meta.get("venue"),
        "year": meta.get("year"),
        "comment": meta.get("comment"),
        "abstract": meta.get("summary"),
        "tldr_from_source": meta.get("tldr"),
        "citation_count": meta.get("citation_count"),
        "influential_citation_count": meta.get("influential_citation_count"),
        "reference_count": meta.get("reference_count"),
        "key_references": meta.get("references"),
        "arxiv_id": meta.get("arxiv_id") or (meta.get("short_id") if source == "arxiv" else None),
        "s2_paper_id": meta.get("id") if source == "semantic_scholar" else None,
        "num_pages": num_pages,
        "full_text_excerpt": pdf_text,
    }
    # Drop None / empty entries to keep the prompt tight.
    payload = {k: v for k, v in payload.items() if v not in (None, "", [], {})}
    src_label = "arXiv" if source == "arxiv" else "Semantic Scholar"
    return (
        f"Build an interactive, animated dashboard for the following academic "
        f"paper (source: {src_label}). Pay particular attention to visualizing "
        f"any process / pipeline / algorithm described in the methodology with "
        f"motion. If `key_references` are provided, include a small references "
        f"panel with the most relevant ones.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


_HTML_FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _HTML_FENCE_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# GitHub helpers (VisualRepo)
# ---------------------------------------------------------------------------

# Accepts: "owner/repo", full GitHub URLs (https/ssh), or trailing slashes.
_GH_REPO_RE = re.compile(
    r"(?:https?://github\.com/|git@github\.com:)?"
    r"([A-Za-z0-9][A-Za-z0-9\-]{0,38})/([A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?/?(?:[#?].*)?$"
)


def _looks_like_repo_slug(query: str) -> "tuple[str, str] | None":
    q = (query or "").strip()
    if not q or " " in q:
        return None
    m = _GH_REPO_RE.match(q)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    # Reject obvious false positives like "foo/bar/baz" and bare repo names.
    if "/" not in q:
        return None
    return owner, repo


def _gh_headers() -> dict[str, str]:
    h = {
        "User-Agent": WIKI_USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _gh_request(path: str, params: dict | None = None) -> Any:
    url = f"{GITHUB_BASE_URL}{path}"
    headers = _gh_headers()
    resp = requests.get(url, params=params, headers=headers, timeout=GITHUB_TIMEOUT)
    # GitHub returns rate-limit hints in headers — surface them so we can
    # tell "no token loaded" vs "token loaded but secondary rate hit".
    has_auth = "Authorization" in headers
    remaining = resp.headers.get("X-RateLimit-Remaining")
    limit = resp.headers.get("X-RateLimit-Limit")
    if resp.status_code == 401:
        raise RuntimeError(
            "GitHub rejected the GITHUB_TOKEN (401 Unauthorized). The token may "
            "be expired, malformed, or revoked. Generate a new one at "
            "https://github.com/settings/tokens and update GITHUB_TOKEN."
        )
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        if has_auth:
            raise RuntimeError(
                f"GitHub rate-limited the server even though a token was sent "
                f"(limit={limit}, remaining={remaining}). Likely the search "
                f"API's secondary rate limit (~30 req/min) — wait a minute and "
                f"retry, or check that the token isn't shared/exhausted."
            )
        raise RuntimeError(
            f"GitHub rate-limited the server and NO GITHUB_TOKEN was sent "
            f"(limit={limit}, remaining={remaining}). Add GITHUB_TOKEN as an "
            f"environment variable in Render → click 'Manual Deploy' → "
            f"'Clear build cache & deploy' to make sure the new env var is "
            f"loaded. Verify it shows up at /api/repo/status."
        )
    if resp.status_code == 404:
        raise RuntimeError("Repository not found on GitHub.")
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub {resp.status_code}: {resp.text[:200]}")
    if resp.status_code == 204:
        return None
    return resp.json()


def _gh_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    slug = _looks_like_repo_slug(query)
    if slug:
        owner, repo = slug
        try:
            r = _gh_request(f"/repos/{owner}/{repo}")
        except Exception:
            r = None
        if r:
            return [_gh_repo_to_search_dict(r)]
    data = _gh_request(
        "/search/repositories",
        {"q": query, "per_page": min(limit, 25), "sort": "stars", "order": "desc"},
    )
    items = data.get("items", []) if isinstance(data, dict) else []
    return [_gh_repo_to_search_dict(r) for r in items]


def _gh_repo_to_search_dict(r: dict) -> dict[str, Any]:
    owner = (r.get("owner") or {}).get("login")
    return {
        "id": r.get("full_name") or (f"{owner}/{r.get('name')}" if owner else r.get("name")),
        "full_name": r.get("full_name"),
        "name": r.get("name"),
        "owner": owner,
        "description": r.get("description") or "",
        "stars": r.get("stargazers_count"),
        "forks": r.get("forks_count"),
        "language": r.get("language"),
        "updated": r.get("pushed_at") or r.get("updated_at"),
        "url": r.get("html_url"),
        "topics": r.get("topics") or [],
    }


def _gh_fetch(owner: str, repo: str) -> dict[str, Any]:
    """Aggregate everything the model needs to build a repo dashboard."""
    base = _gh_request(f"/repos/{owner}/{repo}")
    languages: dict[str, int] = {}
    contributors: list[dict] = []
    commits: list[dict] = []
    readme_text = ""
    readme_truncated = False
    try:
        languages = _gh_request(f"/repos/{owner}/{repo}/languages") or {}
    except Exception as e:
        app.logger.info("languages fetch failed: %s", e)
    try:
        raw_contribs = _gh_request(
            f"/repos/{owner}/{repo}/contributors",
            {"per_page": 10, "anon": "false"},
        ) or []
        for c in raw_contribs[:10]:
            contributors.append({
                "login": c.get("login"),
                "contributions": c.get("contributions"),
                "url": c.get("html_url"),
                "avatar": c.get("avatar_url"),
            })
    except Exception as e:
        app.logger.info("contributors fetch failed: %s", e)
    try:
        raw_commits = _gh_request(
            f"/repos/{owner}/{repo}/commits", {"per_page": 10}
        ) or []
        for c in raw_commits[:10]:
            commit = c.get("commit") or {}
            author = commit.get("author") or {}
            commits.append({
                "sha": (c.get("sha") or "")[:7],
                "message": (commit.get("message") or "").splitlines()[0][:160],
                "author": author.get("name"),
                "date": author.get("date"),
            })
    except Exception as e:
        app.logger.info("commits fetch failed: %s", e)
    try:
        # Readme returns base64-encoded content + raw download URL.
        rd = _gh_request(f"/repos/{owner}/{repo}/readme") or {}
        download_url = rd.get("download_url")
        if download_url:
            txt_resp = requests.get(
                download_url, headers={"User-Agent": WIKI_USER_AGENT},
                timeout=GITHUB_TIMEOUT,
            )
            if txt_resp.ok:
                raw = txt_resp.text
                if len(raw) > MAX_README_CHARS:
                    readme_text = raw[:MAX_README_CHARS]
                    readme_truncated = True
                else:
                    readme_text = raw
    except Exception as e:
        app.logger.info("readme fetch failed: %s", e)

    return {
        "full_name": base.get("full_name"),
        "name": base.get("name"),
        "owner": (base.get("owner") or {}).get("login"),
        "description": base.get("description") or "",
        "homepage": base.get("homepage") or "",
        "url": base.get("html_url"),
        "stars": base.get("stargazers_count"),
        "watchers": base.get("subscribers_count"),
        "forks": base.get("forks_count"),
        "open_issues": base.get("open_issues_count"),
        "language": base.get("language"),
        "languages": languages,            # {"Python": 12345, "JavaScript": 6789}
        "license": (base.get("license") or {}).get("spdx_id"),
        "topics": base.get("topics") or [],
        "default_branch": base.get("default_branch"),
        "created": base.get("created_at"),
        "updated": base.get("updated_at"),
        "pushed": base.get("pushed_at"),
        "size_kb": base.get("size"),
        "is_fork": base.get("fork"),
        "is_archived": base.get("archived"),
        "contributors": contributors,
        "recent_commits": commits,
        "readme_excerpt": readme_text,
        "readme_truncated": readme_truncated,
    }


# ---------------------------------------------------------------------------
# Art helpers (VisualArt — Met Museum)
# ---------------------------------------------------------------------------

def _met_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    # Met /search returns objectIDs. We then fetch up to ~limit objects in
    # parallel-ish fashion via short sequential calls (Met has no documented
    # bulk endpoint).
    #
    # We require BOTH primaryImage (full-size, used as the dashboard hero)
    # AND primaryImageSmall (used as the search-result thumbnail). The Met's
    # `hasImages=true` query flag is necessary but not sufficient — many works
    # marked as "having images" still come back with empty primaryImage URLs
    # because the Met excludes whole rights-restricted artists (e.g. Monet)
    # from their Open Access program. Filtering here means the user never
    # sees a result that would generate a dashboard with a broken hero.
    resp = requests.get(
        f"{MET_BASE_URL}/search",
        params={"q": query, "hasImages": "true"},
        headers=MET_HEADERS,
        timeout=MET_TIMEOUT,
    )
    if resp.status_code >= 400:
        # Surface a useful hint when the Met's edge blocks us — historically
        # this is a UA / IP block, not a real "no permission" condition.
        hint = ""
        if resp.status_code == 403:
            hint = (
                " — the Met's API blocked this request (usually User-Agent "
                "or cloud-IP based). Try again, or set MET_USER_AGENT to a "
                "different browser string."
            )
        raise RuntimeError(
            f"Met search {resp.status_code}: {resp.text[:160]}{hint}"
        )
    data = resp.json() or {}
    # Scan more IDs than we need so that even if many are filtered out we
    # still surface a full page of results — but keep the ceiling modest
    # (we issue one /objects/<id> GET per scanned ID and the Met's edge
    # rate-limits aggressively from cloud IPs).
    ids = (data.get("objectIDs") or [])[: MET_SEARCH_LIMIT * 2]
    out: list[dict[str, Any]] = []
    for oid in ids:
        try:
            obj = _met_fetch_raw(int(oid))
        except Exception:
            continue
        if not obj:
            continue
        if not obj.get("primaryImage") or not obj.get("primaryImageSmall"):
            continue
        out.append(_met_obj_to_dict(obj))
        if len(out) >= limit:
            break
    return out


def _met_fetch_raw(object_id: int) -> dict | None:
    resp = requests.get(
        f"{MET_BASE_URL}/objects/{object_id}",
        headers=MET_HEADERS,
        timeout=MET_TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise RuntimeError(f"Met object {resp.status_code}: {resp.text[:160]}")
    return resp.json()


def _met_obj_to_dict(o: dict) -> dict[str, Any]:
    return {
        "id": str(o.get("objectID")),
        "source": "met",
        "title": o.get("title") or "Untitled",
        "artist": o.get("artistDisplayName") or "Unknown artist",
        "artist_bio": o.get("artistDisplayBio") or "",
        "artist_nationality": o.get("artistNationality") or "",
        "date": o.get("objectDate") or "",
        "year": o.get("objectBeginDate"),
        "medium": o.get("medium") or "",
        "dimensions": o.get("dimensions") or "",
        "department": o.get("department") or "",
        "classification": o.get("classification") or "",
        "culture": o.get("culture") or "",
        "period": o.get("period") or "",
        "credit_line": o.get("creditLine") or "",
        "image": o.get("primaryImage") or o.get("primaryImageSmall") or "",
        "image_thumb": o.get("primaryImageSmall") or o.get("primaryImage") or "",
        "additional_images": (o.get("additionalImages") or [])[:6],
        "url": o.get("objectURL") or "",
        "tags": [t.get("term") for t in (o.get("tags") or []) if t and t.get("term")][:8],
        "is_public_domain": bool(o.get("isPublicDomain")),
    }


# ---------------------------------------------------------------------------
# Prompts for VisualRepo and VisualArt
# ---------------------------------------------------------------------------

REPO_SYSTEM_PROMPT = """You are VisualRepo, a designer who turns GitHub
repositories into beautiful, animated explainer dashboards.

You will receive structured metadata about a GitHub repo (description, stars,
languages, top contributors, recent commits, README excerpt). Produce a SINGLE
self-contained HTML document that explains, in 60 seconds of reading, what the
repository is, who built it, how active it is, and how it works.

HARD REQUIREMENTS
- Output ONLY raw HTML. No markdown fences, no commentary.
- Complete valid HTML5 page (`<!DOCTYPE html>` ... `</html>`) that runs standalone in an iframe.
- Allowed CDNs only: cdn.tailwindcss.com, cdn.jsdelivr.net (Chart.js, ApexCharts,
  anime.js, GSAP), unpkg.com, fonts.googleapis.com.
- Use Tailwind. Modern dark theme. Pick an accent color that fits the repo's
  primary language (e.g. yellow for Python, cyan for TypeScript, orange for
  Rust, red for Java). Subtle glassmorphism is welcome.

DASHBOARD MUST CONTAIN
1. HERO with the full repo name (`owner/repo`), the description, the primary
   language, and a button linking to the repo on GitHub. Show the avatar of the
   top contributor as a small chip if provided.
2. KPI strip with 4-6 stat cards: stars, forks, watchers, open issues, license,
   age (years since `created`). Use animated counters that count up to the
   actual numbers.
3. A LANGUAGE BREAKDOWN doughnut or stacked-bar chart (Chart.js) using the
   `languages` byte counts. Label segments with percentages.
4. A "TOP CONTRIBUTORS" panel (top 5-8) with avatars (use the provided URLs)
   and contribution counts as small bar charts.
5. A "RECENT ACTIVITY" timeline using the recent commits — show date, author,
   first line of message. Animate them in with a stagger.
6. A "WHAT IT DOES" section synthesised from the README excerpt — 3-5 short
   plain-English paragraphs. If the README contains a "Features" or "Why"
   list, extract 3-6 bullets with inline-SVG icons.
7. A "GETTING STARTED" snippet block with the install/quickstart command(s)
   pulled from the README (if present). Use a `<pre><code>` block with a
   copy-to-clipboard button (vanilla JS).
8. A METADATA strip at the bottom: license, default branch, size, created /
   last-pushed dates, topics as chips.

MOTION (mandatory)
- Use anime.js or GSAP for staggered hero + KPI entrance.
- Animated counters on every numeric KPI (count up over ~1.2s).
- Scroll-triggered reveals on subsequent sections (IntersectionObserver is fine).
- Subtle hover micro-interactions on cards.
- Chart.js animations enabled.
- Respect `prefers-reduced-motion: reduce`.

CONSTRAINTS
- Do not invent statistics. If a number isn't in the data, omit the card.
- Quote at most one short sentence verbatim from the README; paraphrase
  everything else into clearer prose.

Begin with `<!DOCTYPE html>` and end with `</html>`. Nothing else.
"""


ART_SYSTEM_PROMPT = """You are VisualArt, a designer who turns a single
artwork into a beautiful, animated, museum-quality explainer dashboard.

You will receive structured metadata for one artwork from the Metropolitan
Museum of Art (the Met), including a high-resolution image URL. Produce a
SINGLE self-contained HTML document that lets the viewer truly *see* the work
and understand its context.

HARD REQUIREMENTS
- Output ONLY raw HTML. No markdown fences, no commentary.
- Complete valid HTML5 page (`<!DOCTYPE html>` ... `</html>`) that runs standalone in an iframe.
- Allowed CDNs only: cdn.tailwindcss.com, cdn.jsdelivr.net (anime.js, GSAP +
  ScrollTrigger), unpkg.com, fonts.googleapis.com.
- Use Tailwind. Choose a refined, museum-style palette — deep neutrals, a
  single accent that complements the artwork (e.g. warm gold for Old Masters,
  cool teal for Impressionism). Use a serif typeface (e.g. Cormorant Garamond
  or Playfair Display) for the artwork title and artist.

DASHBOARD MUST CONTAIN
1. HERO that gives the artwork the spotlight: the image displayed large
   (object-fit: contain, max-height ~80vh), the title in serif, the artist
   below in a smaller weight, the date / period, and a button linking to the
   museum's page for the work. The image should fade/zoom in on load.
2. A "ABOUT THIS WORK" panel with 3-5 short, well-written paragraphs YOU
   compose from the metadata: medium, dimensions, technique, what the viewer
   is looking at. Be concrete. Do NOT invent biographical claims that aren't
   supported by the data.
3. A "DETAILS" KPI strip: medium, dimensions, classification, culture,
   period, credit line — each as a small card with a tiny inline-SVG icon.
4. An "ABOUT THE ARTIST" panel built from artist + bio fields if provided.
   Keep it short (2-3 sentences) and stick to the supplied facts.
5. If `additional_images` are provided, include a small gallery beneath the
   hero (clickable thumbs that swap into the hero — vanilla JS).
6. A METADATA strip at the bottom: museum, department, object id, public-
   domain status, tags as chips.

MOTION (mandatory)
- Hero image fade + slow zoom (~1.6s) on load.
- Staggered entrance for title / artist / date (~80ms stagger).
- Scroll-triggered reveals for subsequent sections.
- Subtle parallax on the hero image as the viewer scrolls.
- Respect `prefers-reduced-motion: reduce`.

STYLE NOTES
- Treat this like a museum wall card, not a tech dashboard. Generous
  whitespace, restrained color, elegant typography.
- Do not add KPI counters or gauges — they don't belong here.
- Always credit the museum in the footer.

Begin with `<!DOCTYPE html>` and end with `</html>`. Nothing else.
"""


def _build_repo_user_prompt(data: dict[str, Any]) -> str:
    payload = {k: v for k, v in data.items() if v not in (None, "", [], {})}
    return (
        "Build an animated dashboard explaining the following GitHub repository. "
        "Stick strictly to the data provided — do not invent stars, contributors, "
        "or features that aren't supported by the metadata or README excerpt.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def _build_art_user_prompt(data: dict[str, Any]) -> str:
    payload = {k: v for k, v in data.items() if v not in (None, "", [], {})}
    return (
        "Build an elegant, museum-quality dashboard for the following artwork "
        "from the Metropolitan Museum of Art. The provided image URL is the "
        "highest-resolution available — display it large in the hero. Keep "
        "prose grounded in the metadata; do NOT invent biographical or art-"
        "historical claims.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


# ---------------------------------------------------------------------------
# Shared streaming generator
# ---------------------------------------------------------------------------

def _stream_dashboard(*, model: str, system_prompt: str, user_prompt: str,
                      meta_event: dict[str, Any]) -> Iterable[str]:
    yield json.dumps({"type": "meta", **meta_event, "model": model}) + "\n"
    buffer: list[str] = []
    try:
        extra_body: dict = {}
        tk = _chat_template_kwargs_for(model)
        if tk:
            extra_body["chat_template_kwargs"] = tk
        stream = _openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            top_p=0.95,
            max_tokens=12000,
            stream=True,
            extra_body=extra_body or None,
        )
        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                buffer.append(piece)
                yield json.dumps({"type": "chunk", "content": piece}) + "\n"
        full = _strip_fences("".join(buffer))
        if not full:
            yield json.dumps({
                "type": "error",
                "message": (
                    "The model returned an empty response. The model may be "
                    "rate-limited or unavailable on this tier — try a different "
                    "model from the dropdown."
                ),
            }) + "\n"
        else:
            yield json.dumps({"type": "done", "html": full}) + "\n"
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Model call failed")
        yield json.dumps({
            "type": "error",
            "message": f"{type(exc).__name__}: {exc}",
        }) + "\n"


def _streaming_response(gen: Iterable[str]) -> Response:
    response = Response(stream_with_context(gen), mimetype="application/x-ndjson")
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---- Race mode -----------------------------------------------------------
# Fans out a single dashboard request to N models in parallel and multiplexes
# their NDJSON event streams back into a single response. Each event gets a
# `model` field tagged on so the frontend can route it to the right tab.
import queue as _queue  # noqa: E402  (kept local-ish to limit blast radius)

# Hard cap to keep one user from accidentally racing every model in the list.
RACE_MAX_MODELS = 3


def _race_dashboards(*, models: list[str], system_prompt: str, user_prompt: str,
                     meta_event: dict[str, Any]) -> Iterable[str]:
    q: "_queue.Queue[Any]" = _queue.Queue()
    sentinel = object()

    # Send a single "race" event up front so the frontend can build tabs
    # before any model has emitted anything.
    yield json.dumps({
        "type": "race",
        "models": models,
        **{k: v for k, v in meta_event.items() if k in ("title", "url", "source", "paper_id")},
    }) + "\n"

    def worker(model: str) -> None:
        try:
            for line in _stream_dashboard(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                meta_event=meta_event,
            ):
                # Tag every event with the producing model.
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                evt["model"] = model
                q.put(json.dumps(evt) + "\n")
        except Exception as exc:  # noqa: BLE001
            q.put(json.dumps({
                "type": "error",
                "model": model,
                "message": f"{type(exc).__name__}: {exc}",
            }) + "\n")
        finally:
            q.put((sentinel, model))

    threads = [
        threading.Thread(target=worker, args=(m,), daemon=True, name=f"race-{m}")
        for m in models
    ]
    for t in threads:
        t.start()

    pending = set(models)
    while pending:
        item = q.get()
        if isinstance(item, tuple) and item[0] is sentinel:
            pending.discard(item[1])
            continue
        yield item


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/models")
def api_models():
    return jsonify({"models": AVAILABLE_MODELS, "default": NVIDIA_MODEL})


# ---- Email delivery ------------------------------------------------------

def _build_dashboard_email(to: str, subject: str, title: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject or f"Your VisualLab dashboard: {title}"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>" if SMTP_FROM_NAME else SMTP_FROM_EMAIL
    msg["To"] = to
    safe_title = (title or "dashboard").strip() or "dashboard"
    text_body = (
        f"Your VisualLab dashboard \"{safe_title}\" is ready.\n\n"
        "It is attached to this email as a single self-contained HTML file. "
        "Open it in any modern browser to view the interactive dashboard with "
        "charts, animations and KaTeX equations.\n\n"
        "— VisualLab"
    )
    msg.set_content(text_body)
    html_body = f"""<!doctype html><html><body style=\"font-family:system-ui,Segoe UI,Arial,sans-serif;color:#1f2937;line-height:1.55\">
  <p>Your VisualLab dashboard <strong>{title or 'dashboard'}</strong> is ready.</p>
  <p>It is attached as a single self-contained HTML file — open it in any modern
  browser to see the full interactive dashboard with charts, animations and
  equations.</p>
  <p style=\"color:#6b7280;font-size:12px\">— VisualLab</p>
</body></html>"""
    msg.add_alternative(html_body, subtype="html")
    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "-", safe_title.lower()).strip("-") or "dashboard"
    if not safe_filename.endswith(".html"):
        safe_filename = f"{safe_filename}.html"
    msg.add_attachment(
        html.encode("utf-8"),
        maintype="text",
        subtype="html",
        filename=safe_filename,
    )
    return msg


def _smtp_send(msg: EmailMessage) -> None:
    if SMTP_USE_SSL:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=ctx) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)


def _send_dashboard_email_async(to: str, subject: str, title: str, html: str) -> None:
    def _run() -> None:
        try:
            msg = _build_dashboard_email(to, subject, title, html)
            _smtp_send(msg)
            app.logger.info("Email sent to %s (title=%r, %d bytes)", to, title, len(html))
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Failed to send email to %s: %s", to, exc)

    threading.Thread(target=_run, daemon=True).start()


@app.route("/api/email/status")
def api_email_status():
    return jsonify({
        "enabled": EMAIL_ENABLED,
        "sender": SMTP_FROM_EMAIL if EMAIL_ENABLED else None,
        "host": SMTP_HOST if EMAIL_ENABLED else None,
    })


@app.route("/api/email/send", methods=["POST"])
def api_email_send():
    if not EMAIL_ENABLED:
        return jsonify({
            "error": (
                "Email is not configured on the server. Set SMTP_USER, "
                "SMTP_PASSWORD and SMTP_FROM_EMAIL in .env to enable it."
            )
        }), 503

    body = request.get_json(silent=True) or {}
    to = (body.get("to") or "").strip()
    subject = (body.get("subject") or "").strip()
    title = (body.get("title") or "").strip()
    html = body.get("html") or ""

    if not to or not EMAIL_RE.match(to):
        return jsonify({"error": "A valid recipient email address is required."}), 400
    if not isinstance(html, str) or len(html) < 200:
        return jsonify({"error": "Missing or too-small dashboard HTML."}), 400
    if len(html.encode("utf-8")) > 10 * 1024 * 1024:
        return jsonify({"error": "Dashboard HTML exceeds the 10 MB email cap."}), 413

    _send_dashboard_email_async(to=to, subject=subject, title=title, html=html)
    return jsonify({"ok": True, "queued_for": to})


# ---- VisualPedia ---------------------------------------------------------

@app.route("/api/pedia/search")
def api_pedia_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": []})
    try:
        results = _wiki.search(query, limit=8)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500

    payload = []
    for title, page in results.pages.items():
        meta = page.search_meta
        snippet = re.sub(r"<[^>]+>", "", meta.snippet or "") if meta else ""
        payload.append({
            "title": title,
            "snippet": snippet,
            "wordcount": getattr(meta, "wordcount", None) if meta else None,
        })
    return jsonify({"results": payload, "totalhits": results.totalhits})


def _resolve_models(body: dict) -> "tuple[list[str] | None, str]":
    """Returns (race_models, single_model). If race_models is non-None, run race mode."""
    raw = body.get("models")
    if isinstance(raw, list) and raw:
        models = []
        seen = set()
        for m in raw:
            s = str(m or "").strip()
            if s and s not in seen:
                seen.add(s)
                models.append(s)
        models = models[:RACE_MAX_MODELS]
        if len(models) >= 2:
            return models, models[0]
    single = (body.get("model") or NVIDIA_MODEL).strip()
    return None, single


@app.route("/api/pedia/dashboard", methods=["POST"])
def api_pedia_dashboard():
    allowed, retry = _check_rate_limit("dashboard")
    if not allowed:
        return jsonify({
            "error": (
                f"You've generated {RATE_LIMIT_PER_HOUR} dashboards in the last hour, "
                "which is the per-visitor limit on this free demo. "
                f"Please try again in about {max(1, retry // 60)} minutes."
            ),
            "retry_after": retry,
        }), 429

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Missing 'title'."}), 400

    data = _extract_wiki_data(title)
    if "error" in data:
        return jsonify(data), 404

    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured."}), 500

    user_prompt = _build_pedia_user_prompt(data)
    meta = {"title": data["title"], "url": data["url"]}

    race_models, single = _resolve_models(body)
    if race_models:
        app.logger.info("Pedia race: title=%r models=%r", title, race_models)
        return _streaming_response(_race_dashboards(
            models=race_models,
            system_prompt=PEDIA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            meta_event=meta,
        ))

    app.logger.info("Pedia dashboard: title=%r model=%r", title, single)
    return _streaming_response(_stream_dashboard(
        model=single,
        system_prompt=PEDIA_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        meta_event=meta,
    ))


# Backwards-compatible aliases (older frontend builds).
app.add_url_rule("/api/search", view_func=api_pedia_search)
app.add_url_rule("/api/dashboard", view_func=api_pedia_dashboard, methods=["POST"])


# ---- VisualScholar -------------------------------------------------------

SCHOLAR_SOURCES = {"arxiv", "semantic_scholar"}


@app.route("/api/scholar/sources")
def api_scholar_sources():
    return jsonify({
        "sources": [
            {"id": "arxiv", "label": "arXiv", "available": True,
             "description": "Open preprint server. PDFs are always downloadable."},
            {"id": "semantic_scholar", "label": "Semantic Scholar",
             "available": True,
             "has_api_key": bool(SEMANTIC_SCHOLAR_API_KEY),
             "description": (
                 "214M papers across all fields. Returns citation counts, "
                 "TLDR summaries, and references. Open-access PDFs when available."
             )},
        ]
    })


@app.route("/api/scholar/search")
def api_scholar_search():
    query = (request.args.get("q") or "").strip()
    source = (request.args.get("source") or "arxiv").strip().lower()
    if source not in SCHOLAR_SOURCES:
        return jsonify({"error": f"Unknown source {source!r}."}), 400
    if not query:
        return jsonify({"results": []})
    try:
        if source == "arxiv":
            results = _arxiv_search(query, limit=10)
        else:
            results = _s2_search(query, limit=10)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"results": results, "source": source})


@app.route("/api/scholar/dashboard", methods=["POST"])
def api_scholar_dashboard():
    allowed, retry = _check_rate_limit("dashboard")
    if not allowed:
        return jsonify({
            "error": (
                f"You've generated {RATE_LIMIT_PER_HOUR} dashboards in the last hour, "
                "which is the per-visitor limit on this free demo. "
                f"Please try again in about {max(1, retry // 60)} minutes."
            ),
            "retry_after": retry,
        }), 429

    body = request.get_json(silent=True) or {}
    source = (body.get("source") or "arxiv").strip().lower()
    paper_id = (body.get("paper_id") or body.get("arxiv_id") or "").strip()

    if source not in SCHOLAR_SOURCES:
        return jsonify({"error": f"Unknown source {source!r}."}), 400
    if not paper_id:
        return jsonify({"error": "Missing 'paper_id'."}), 400
    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured."}), 500

    try:
        if source == "arxiv":
            meta = _fetch_paper(paper_id)
        else:
            meta = _s2_fetch(paper_id)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to fetch paper: {exc}"}), 500
    if not meta:
        return jsonify({"error": f"No paper found with id {paper_id!r}."}), 404

    pdf_url = meta.get("pdf_url")
    pdf_text, num_pages = _download_pdf_text(pdf_url) if pdf_url else ("", 0)

    user_prompt = _build_scholar_user_prompt(meta, pdf_text, num_pages, source)

    meta_event = {
        "title": meta.get("title"),
        "url": meta.get("abs_url"),
        "source": source,
        "paper_id": paper_id,
        "pdf_chars": len(pdf_text),
        "num_pages": num_pages,
        "has_pdf": bool(pdf_url),
    }

    race_models, single = _resolve_models(body)
    if race_models:
        app.logger.info(
            "Scholar race: source=%s id=%s models=%r pdf_chars=%d",
            source, paper_id, race_models, len(pdf_text),
        )
        return _streaming_response(_race_dashboards(
            models=race_models,
            system_prompt=SCHOLAR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            meta_event=meta_event,
        ))

    app.logger.info(
        "Scholar dashboard: source=%s id=%s model=%r pdf_chars=%d pages=%d",
        source, paper_id, single, len(pdf_text), num_pages,
    )
    return _streaming_response(_stream_dashboard(
        model=single,
        system_prompt=SCHOLAR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        meta_event=meta_event,
    ))


# ---- VisualRepo (GitHub) -------------------------------------------------

@app.route("/api/repo/status")
def api_repo_status():
    """Diagnostic: confirm whether the server sees a GITHUB_TOKEN, and (if so)
    a non-secret fingerprint so the user can verify they're looking at the
    right deployment without leaking the token itself.
    Also makes a single live call to /rate_limit so the user can see what
    quota the token actually resolves to on GitHub's end."""
    has_token = bool(GITHUB_TOKEN)
    fingerprint = None
    if has_token:
        # Non-secret: the prefix tells us what TYPE of token it is, and the
        # length is enough to detect "I pasted the wrong string".
        prefix = GITHUB_TOKEN[:4]
        fingerprint = f"{prefix}…(len={len(GITHUB_TOKEN)})"
    live = {}
    try:
        resp = requests.get(
            f"{GITHUB_BASE_URL}/rate_limit", headers=_gh_headers(),
            timeout=GITHUB_TIMEOUT,
        )
        if resp.ok:
            data = resp.json() or {}
            core = (data.get("resources") or {}).get("core") or {}
            search = (data.get("resources") or {}).get("search") or {}
            live = {
                "core_limit": core.get("limit"),
                "core_remaining": core.get("remaining"),
                "search_limit": search.get("limit"),
                "search_remaining": search.get("remaining"),
                "authenticated": core.get("limit", 0) > 60,
            }
        else:
            live = {"error": f"GitHub returned {resp.status_code}: {resp.text[:120]}"}
    except Exception as exc:
        live = {"error": f"{type(exc).__name__}: {exc}"}
    return jsonify({
        "has_token": has_token,
        "token_fingerprint": fingerprint,
        "github_base_url": GITHUB_BASE_URL,
        "rate_limit_per_hour": RATE_LIMIT_PER_HOUR,
        "github_live": live,
    })


@app.route("/api/repo/search")
def api_repo_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": []})
    try:
        results = _gh_search(query, limit=10)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"results": results, "has_token": bool(GITHUB_TOKEN)})


@app.route("/api/repo/dashboard", methods=["POST"])
def api_repo_dashboard():
    allowed, retry = _check_rate_limit("dashboard")
    if not allowed:
        return jsonify({
            "error": (
                f"You've generated {RATE_LIMIT_PER_HOUR} dashboards in the last hour, "
                "which is the per-visitor limit on this free demo. "
                f"Please try again in about {max(1, retry // 60)} minutes."
            ),
            "retry_after": retry,
        }), 429

    body = request.get_json(silent=True) or {}
    repo_id = (body.get("repo") or body.get("full_name") or "").strip()
    if not repo_id or "/" not in repo_id:
        return jsonify({"error": "Missing or malformed 'repo' (expected 'owner/name')."}), 400
    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured."}), 500

    owner, _, name = repo_id.partition("/")
    name = name.split("/", 1)[0]  # defensive: ignore anything past the second slash
    try:
        data = _gh_fetch(owner, name)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to fetch repository: {exc}"}), 500
    if not data:
        return jsonify({"error": f"Repository {repo_id!r} not found."}), 404

    user_prompt = _build_repo_user_prompt(data)
    meta = {"title": data["full_name"], "url": data["url"], "source": "github"}

    race_models, single = _resolve_models(body)
    if race_models:
        app.logger.info("Repo race: %s models=%r", repo_id, race_models)
        return _streaming_response(_race_dashboards(
            models=race_models,
            system_prompt=REPO_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            meta_event=meta,
        ))
    app.logger.info("Repo dashboard: %s model=%r readme=%dch", repo_id, single, len(data.get("readme_excerpt") or ""))
    return _streaming_response(_stream_dashboard(
        model=single,
        system_prompt=REPO_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        meta_event=meta,
    ))


# ---- VisualArt (Met Museum) ----------------------------------------------

@app.route("/api/art/search")
def api_art_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": []})
    try:
        results = _met_search(query, limit=10)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"results": results, "source": "met"})


@app.route("/api/art/dashboard", methods=["POST"])
def api_art_dashboard():
    allowed, retry = _check_rate_limit("dashboard")
    if not allowed:
        return jsonify({
            "error": (
                f"You've generated {RATE_LIMIT_PER_HOUR} dashboards in the last hour, "
                "which is the per-visitor limit on this free demo. "
                f"Please try again in about {max(1, retry // 60)} minutes."
            ),
            "retry_after": retry,
        }), 429

    body = request.get_json(silent=True) or {}
    obj_id = str(body.get("object_id") or body.get("id") or "").strip()

    if not obj_id:
        return jsonify({"error": "Missing 'object_id'."}), 400
    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY is not configured."}), 500

    try:
        raw = _met_fetch_raw(int(obj_id))
        data = _met_obj_to_dict(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to fetch artwork: {exc}"}), 500
    if not data:
        return jsonify({"error": f"No artwork found with id {obj_id!r}."}), 404

    user_prompt = _build_art_user_prompt(data)
    meta = {
        "title": data.get("title"),
        "url": data.get("url"),
        "source": "met",
        "object_id": obj_id,
    }

    race_models, single = _resolve_models(body)
    if race_models:
        app.logger.info("Art race: id=%s models=%r", obj_id, race_models)
        return _streaming_response(_race_dashboards(
            models=race_models,
            system_prompt=ART_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            meta_event=meta,
        ))
    app.logger.info("Art dashboard: id=%s model=%r", obj_id, single)
    return _streaming_response(_stream_dashboard(
        model=single,
        system_prompt=ART_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        meta_event=meta,
    ))


# ---- Shareable dashboard links -------------------------------------------
# Save a generated dashboard's HTML to disk under a short slug, then serve it
# at /d/<slug>. Used for "Copy share link" so colleagues can open the result
# without re-running the model.

def _make_share_slug(html: str, mode: str, query: str) -> str:
    """Deterministic 10-char slug from the HTML + mode + query.
    Same content → same slug, so re-sharing doesn't bloat storage."""
    h = hashlib.sha256()
    h.update(html.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(mode.encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update(query.encode("utf-8", errors="replace"))
    # Keep it URL-safe and short. 10 hex chars = 40 bits ≈ negligible
    # collision risk for the volume this app will ever see.
    return h.hexdigest()[:10]


def _purge_old_shares() -> None:
    """Best-effort cleanup of shares older than SHARE_RETENTION_DAYS. Runs
    inline on each save call so we don't need a scheduler. Cheap because it
    only touches mtimes, not file content."""
    if SHARE_RETENTION_DAYS <= 0:
        return
    cutoff = time.time() - SHARE_RETENTION_DAYS * 86400
    try:
        for f in SHARE_DIR.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass


@app.route("/api/share", methods=["POST"])
def api_share_create():
    body = request.get_json(silent=True) or {}
    html = body.get("html") or ""
    title = (body.get("title") or "").strip()[:200]
    mode = (body.get("mode") or "").strip().lower()[:20]
    query = (body.get("query") or "").strip()[:300]
    if not isinstance(html, str) or len(html) < 200:
        return jsonify({"error": "Missing or too-small HTML."}), 400
    encoded = html.encode("utf-8", errors="replace")
    if len(encoded) > SHARE_MAX_HTML_BYTES:
        return jsonify({
            "error": f"Dashboard HTML exceeds the {SHARE_MAX_HTML_BYTES // (1024*1024)} MB share cap.",
        }), 413
    slug = _make_share_slug(html, mode, query)
    html_path = SHARE_DIR / f"{slug}.html"
    meta_path = SHARE_DIR / f"{slug}.json"
    try:
        # Touch + bump mtime even if the file already exists, so popular
        # shares stay alive longer than the retention window.
        html_path.write_bytes(encoded)
        meta_path.write_text(json.dumps({
            "slug": slug,
            "title": title,
            "mode": mode,
            "query": query,
            "created_at": int(time.time()),
            "size": len(encoded),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        app.logger.exception("Failed to save share %s", slug)
        return jsonify({"error": f"Failed to save share: {exc}"}), 500
    _purge_old_shares()
    app.logger.info("Share saved: %s mode=%s title=%r bytes=%d", slug, mode, title, len(encoded))
    return jsonify({
        "slug": slug,
        "url": f"/d/{slug}",
        "share_url": request.host_url.rstrip("/") + f"/d/{slug}",
    })


@app.route("/d/<slug>")
def serve_share(slug: str):
    if not SHARE_SLUG_RE.match(slug):
        return Response("Invalid share id.", status=404, mimetype="text/plain")
    html_path = SHARE_DIR / f"{slug}.html"
    if not html_path.is_file():
        # Friendly HTML error page rather than a bare 404.
        return Response(
            _SHARE_EXPIRED_HTML.format(slug=slug, base="/"),
            status=404, mimetype="text/html",
        )
    try:
        body = html_path.read_bytes()
    except Exception as exc:
        return Response(f"Could not read share: {exc}", status=500, mimetype="text/plain")
    # Bump mtime so each view counts as recent activity → keeps it alive.
    try:
        os.utime(html_path, None)
    except Exception:
        pass
    resp = Response(body, mimetype="text/html; charset=utf-8")
    # Allow the dashboard's CDN scripts and cross-origin images.
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


_SHARE_EXPIRED_HTML = """<!doctype html><html lang=en><meta charset=utf-8>
<title>Share link expired · VisualLab</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>html,body{{margin:0;padding:0;background:#0b0f1c;color:#e7eaf2;font-family:Inter,system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.box{{max-width:520px;padding:36px 32px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px}}
h1{{font-size:22px;margin:0 0 12px}}p{{color:#aab1c5;line-height:1.55;margin:0 0 14px;font-size:14px}}
a{{display:inline-block;margin-top:6px;padding:10px 18px;background:linear-gradient(135deg,#7c5cff,#2dd4bf);color:white;border-radius:10px;text-decoration:none;font-weight:600;font-size:13px}}
code{{font-family:ui-monospace,Consolas,monospace;color:#94a3b8;font-size:12px}}</style>
<div class=box>
  <h1>This share link is no longer available</h1>
  <p>Shared dashboards are kept on a small free-tier server, so they expire
  after a while or when the server restarts.</p>
  <p>The original creator can re-generate the dashboard and share a new link.</p>
  <p><code>/d/{slug}</code></p>
  <a href="{base}">← Back to VisualLab</a>
</div>
"""


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
