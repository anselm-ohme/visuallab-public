# VisualLab

> Turn any academic paper, GitHub repository, Wikipedia article, or museum artwork into a live, AI-generated, interactive HTML dashboard — in about 5 minutes.

**Live demo →** [visuallab.onrender.com](https://visuallab.onrender.com)

VisualLab is a small Flask app that fetches structured content from
arXiv / Semantic Scholar / GitHub / Wikipedia / the Met Museum, sends it to
two NVIDIA-hosted LLMs **racing in parallel**, and **streams a self-contained
HTML dashboard back into your browser in real time** — complete with KPIs,
charts, image galleries, animated process diagrams, and KaTeX equations.

Built as a side project alongside a PhD at ESCP, primarily for academics
who want to skim research and codebases faster — or to present a paper
(including their own) in a quick visual format.

---

## Four modes

| Mode | Source | Best for |
|---|---|---|
| **VisualScholar** | arXiv + Semantic Scholar (search or paper id) | Skimming new papers; presenting your own work |
| **VisualRepo** | GitHub REST API (search or `owner/repo`) | Understanding an unfamiliar codebase fast |
| **VisualPedia** | Wikipedia search | Encyclopedia-style dashboards on any topic |
| **VisualArt** | Met Museum Open Access API | Museum-wall-card-style artwork explainers |

The page rendered in the iframe is *whatever the model produces* — Tailwind
themed, Chart.js-powered, GSAP-animated, fully self-contained. The Flask
backend never touches the HTML beyond streaming it through.

---

## How it works

```
Browser ──search──► Flask ──► arXiv / Semantic Scholar / GitHub / Wikipedia / Met
                      │
                      ▼
              structured JSON (+ PDF text for papers, README excerpt for repos)
                      │
                      ▼
            two NVIDIA NIM models in parallel ──streamed HTML──► live iframe
                      │
                      ▼
                   first to finish wins; the other stays available as a tab
```

- **Backend:** Python 3.12 + Flask, streaming NDJSON responses.
- **LLM hosting:** [NVIDIA NIM free endpoints](https://build.nvidia.com) — currently defaults to GLM 4.7 + Mistral Medium 3.5; also supports MiniMax M2.7, DeepSeek v4 Flash/Pro, GLM 5.1.
- **Frontend:** Vanilla JS SPA with hash routing, dark glassmorphism theme.
- **Generated dashboards:** Tailwind + Chart.js + GSAP/anime.js + Leaflet + KaTeX, loaded from public CDNs and rendered inside a sandboxed iframe.
- **Shareable URLs:** `POST /api/share` saves the generated HTML to disk; `/d/<slug>` serves it back later. Persisted to a 1 GB Render disk in production.

---

## Quick start

### Prerequisites

- Python 3.12+ (`py -3 --version` on Windows)
- A free [NVIDIA NIM API key](https://build.nvidia.com)
- Optional: a [Semantic Scholar API key](https://www.semanticscholar.org/product/api), a [GitHub personal access token](https://github.com/settings/tokens) (lifts the `60 → 5000 req/h` rate limit)

### Run locally

**Windows:** double-click `start.bat`. The launcher creates the venv,
installs dependencies, copies `.env.example` → `.env`, and starts the server.

**Manual setup (any platform):**

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # then fill in NVIDIA_API_KEY at minimum
python app.py
```

Then open http://127.0.0.1:5000.

---

## Configuration

All configuration is via environment variables (see `.env.example` for the full annotated list).

| Variable | Required? | Purpose |
|---|---|---|
| `NVIDIA_API_KEY` | **Yes** | NVIDIA NIM API key |
| `NVIDIA_MODEL` | No | Default model (defaults to `z-ai/glm4.7`) |
| `NVIDIA_TIMEOUT` | No | Per-request timeout in seconds (default 300) |
| `WIKI_USER_AGENT` | **Yes** | Wikipedia's API ToS asks every script to identify itself with a contact email. Format: `MyApp (you@example.com)` |
| `SEMANTIC_SCHOLAR_API_KEY` | No | Lifts S2 from the anonymous shared pool to ~1 req/sec |
| `GITHUB_TOKEN` | No | Lifts GitHub from 60 → 5000 req/h |
| `MET_USER_AGENT` | No | Override the browser-style UA used for Met Museum requests if the default ever gets blocked |
| `RATE_LIMIT_PER_HOUR` | No | Per-IP dashboard generation cap (default 10). Set to `0` to disable |
| `SHARE_DIR`, `SHARE_RETENTION_DAYS` | No | Where shareable dashboard HTML gets written / how long it lives |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | No | Enables the "email this dashboard" feature when all are set |

---

## Deploying to Render

The repo ships with `render.yaml` — a Render Blueprint that builds and runs
the app with sensible defaults (single Gunicorn worker, 8 threads, 600s
request timeout for long LLM streams), plus a 1 GB persistent disk for
shareable dashboards.

1. Push the repo to GitHub.
2. On [Render](https://render.com), create a **New Blueprint**, point at the repo.
3. Fill in the secret env vars when prompted (`NVIDIA_API_KEY`, optionally `SEMANTIC_SCHOLAR_API_KEY` / `GITHUB_TOKEN`, and `WIKI_USER_AGENT` with your real email).
4. Deploy.

Free tier sleeps after 15 min idle (~30s cold start). Starter ($7/mo) keeps
it warm and is required to attach the persistent disk for shareable URLs.

---

## Project layout

```
VisualLab/
├── app.py                         # Flask backend, streaming + race mode + rate limiting
├── requirements.txt
├── render.yaml                    # Render Blueprint (Starter plan + 1 GB disk)
├── Procfile                       # Generic PaaS fallback
├── .env.example
├── start.bat / start.ps1          # Windows launchers
├── scripts/
│   ├── build_examples.py          # Builds the static example dashboards
│   └── fix_met_image_urls.py      # Refreshes Met image URLs from the live API
├── templates/
│   └── index.html                 # SPA shell, hash-routed
└── static/
    ├── style.css                  # Glassmorphism dark theme + responsive layer
    ├── app.js                     # Search + streaming controller (incl. race mode)
    └── examples/
        ├── pedia/                 # 10 hand-built encyclopedia dashboards
        ├── scholar/               # 10 hand-built paper explainers
        ├── repo/                  # 10 GitHub repo explainers
        └── art/                   # 10 Met Museum artwork explainers
```

---

## Why I built this

Most academic content is wall-of-text, but our brains process structure
much more efficiently — charts, timelines, side-by-sides, animations.
VisualLab takes a paper or repo I'm trying to understand and instantly
shows me a *visualised* version, so I can decide in 30 seconds whether
it's worth a deep read — and if it is, the visual version becomes a great
tool for presenting it later.

It's also a useful sandbox for prompting frontier LLMs to produce
*complete, working, opinionated UI* in one shot — not snippets, not "here's
how you might…", but a finished page that runs.

---

## Status

This is an active side project, not a commercial product. Issues and PRs
are welcome but responses may be slow. If you find a bug or want a new
mode, please open an issue.

---

## License

[MIT](LICENSE) — built by [Anselm Ohme](mailto:aohme@escp.eu). Questions and
feedback welcome.
