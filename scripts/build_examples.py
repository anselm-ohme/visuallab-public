"""One-shot builder for the static example-gallery dashboards.

The pedia + scholar gallery files were originally produced by the LLM and
hand-saved. To get parity for VisualRepo and VisualArt without burning ~100
minutes of LLM time, we hand-author one polished HTML template per mode and
stamp it out 10× from a small per-example data dict.

Run from the repo root:

    python scripts/build_examples.py

This (re)generates 10 files in static/examples/repo/ and 10 in
static/examples/art/, plus their manifest.json. Safe to re-run.
"""
from __future__ import annotations

import json
import pathlib
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
EX_DIR = ROOT / "static" / "examples"


# ---------------------------------------------------------------------------
# VisualRepo example template + data
# ---------------------------------------------------------------------------

REPO_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<title>{full_name} — VisualRepo</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  body {{ font-family:'Inter',system-ui,sans-serif; background:#06090f; color:#e5e7eb; }}
  .display {{ font-family:'Space Grotesk',sans-serif; }}
  .mono {{ font-family:'JetBrains Mono',ui-monospace,monospace; }}
  .glass {{ background:rgba(15,20,32,.65); backdrop-filter:blur(18px); border:1px solid {accent_border}; }}
  .grad {{ background:linear-gradient(120deg,{accent},{accent_light}); -webkit-background-clip:text; background-clip:text; color:transparent; }}
  .orb {{ position:fixed; border-radius:50%; filter:blur(120px); pointer-events:none; z-index:0; }}
  .stat-num {{ font-family:'Space Grotesk',sans-serif; font-weight:800; }}
  .accent-bar {{ background:linear-gradient(135deg,{accent},{accent_light}); }}
  .chip {{ display:inline-block; font-size:11px; padding:3px 10px; border-radius:999px; background:{accent_chip_bg}; color:{accent_chip_text}; border:1px solid {accent_border}; }}
  .lang-row {{ display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid rgba(255,255,255,.06); }}
  .lang-row:last-child {{ border-bottom:0; }}
  .lang-bar-bg {{ flex:1; height:6px; border-radius:3px; background:rgba(255,255,255,.08); overflow:hidden; }}
  .lang-bar {{ height:100%; background:linear-gradient(90deg,{accent},{accent_light}); border-radius:3px; transition:width .9s ease; }}
  @keyframes pop {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
  .pop {{ animation: pop .6s ease backwards; }}
  .commit-row {{ display:flex; gap:14px; padding:9px 0; border-bottom:1px dashed rgba(255,255,255,.06); }}
  .commit-row:last-child {{ border-bottom:0; }}
  .commit-sha {{ font-family:'JetBrains Mono',ui-monospace,monospace; font-size:11px; color:{accent_light}; flex-shrink:0; width:62px; }}
</style>
</head>
<body class="min-h-screen relative">
<div class="orb" style="width:520px;height:520px;background:{accent};top:-180px;right:-160px;opacity:.25"></div>
<div class="orb" style="width:420px;height:420px;background:{accent_light};bottom:-200px;left:-140px;opacity:.16"></div>

<div class="relative z-10 max-w-6xl mx-auto px-6 py-10 space-y-8">

  <header class="glass rounded-3xl p-8 md:p-10 pop" style="animation-delay:0s">
    <div class="flex items-start gap-4 mb-4">
      <div class="w-12 h-12 rounded-2xl accent-bar flex items-center justify-center shrink-0">
        <svg class="w-7 h-7 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.6.5.5 5.6.5 12c0 5.1 3.3 9.4 7.9 10.9.6.1.8-.3.8-.6v-2.1c-3.2.7-3.9-1.4-3.9-1.4-.5-1.3-1.3-1.7-1.3-1.7-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.7 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.4-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2.9-.3 1.9-.4 2.9-.4s1.9.1 2.9.4c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.7.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6 4.6-1.5 7.9-5.8 7.9-10.9C23.5 5.6 18.4.5 12 .5Z"/></svg>
      </div>
      <div>
        <div class="text-xs uppercase tracking-[0.3em] text-gray-400">GitHub · {primary_lang}</div>
        <h1 class="display text-4xl md:text-5xl font-bold mt-1 leading-tight"><span class="grad">{full_name}</span></h1>
      </div>
    </div>
    <p class="text-lg text-gray-300/90 mt-2 max-w-3xl leading-relaxed">{description}</p>
    <div class="mt-5 flex flex-wrap gap-2">
      {topic_chips}
    </div>
    <a href="https://github.com/{full_name}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 mt-6 px-5 py-2.5 rounded-full accent-bar text-white font-semibold transition hover:scale-[1.02]">View on GitHub →</a>
  </header>

  <section class="grid grid-cols-2 md:grid-cols-4 gap-4 pop" style="animation-delay:.1s">
    <div class="glass rounded-2xl p-5"><div class="text-xs uppercase tracking-widest text-gray-400">Stars</div><div class="stat-num text-3xl mt-2 grad">{stars_display}</div><div class="text-xs text-gray-500 mt-1">{stars_subtext}</div></div>
    <div class="glass rounded-2xl p-5"><div class="text-xs uppercase tracking-widest text-gray-400">Forks</div><div class="stat-num text-3xl mt-2 grad">{forks_display}</div><div class="text-xs text-gray-500 mt-1">community-built variants</div></div>
    <div class="glass rounded-2xl p-5"><div class="text-xs uppercase tracking-widest text-gray-400">Created</div><div class="stat-num text-3xl mt-2 grad">{created_year}</div><div class="text-xs text-gray-500 mt-1">{age_subtext}</div></div>
    <div class="glass rounded-2xl p-5"><div class="text-xs uppercase tracking-widest text-gray-400">License</div><div class="stat-num text-2xl mt-2 grad">{license}</div><div class="text-xs text-gray-500 mt-1">open source</div></div>
  </section>

  <section class="grid md:grid-cols-5 gap-4">
    <div class="glass rounded-3xl p-6 md:col-span-3 pop" style="animation-delay:.2s">
      <h2 class="display text-2xl font-bold mb-1">What it does</h2>
      <p class="text-xs uppercase tracking-widest text-gray-400 mb-4">Distilled from the README</p>
      <p class="text-gray-300 leading-relaxed mb-4">{about_p1}</p>
      <p class="text-gray-300 leading-relaxed">{about_p2}</p>
      <ul class="mt-5 space-y-2">
        {features}
      </ul>
    </div>
    <div class="glass rounded-3xl p-6 md:col-span-2 pop" style="animation-delay:.3s">
      <h2 class="display text-2xl font-bold mb-3">Languages</h2>
      <p class="text-xs uppercase tracking-widest text-gray-400 mb-4">By share of codebase</p>
      <div>{languages}</div>
      <div class="mt-6 pt-4 border-t border-white/5">
        <div class="text-xs uppercase tracking-widest text-gray-400 mb-2">Quickstart</div>
        <pre class="mono text-xs bg-black/40 p-3 rounded-lg text-gray-200 overflow-x-auto">{quickstart}</pre>
      </div>
    </div>
  </section>

  <section class="glass rounded-3xl p-6 md:p-8 pop" style="animation-delay:.4s">
    <h2 class="display text-2xl font-bold mb-1">Recent activity</h2>
    <p class="text-xs uppercase tracking-widest text-gray-400 mb-4">A typical week of commits</p>
    <div>{commits}</div>
  </section>

  <section class="grid md:grid-cols-2 gap-4">
    <div class="glass rounded-3xl p-6 pop" style="animation-delay:.5s">
      <h2 class="display text-2xl font-bold mb-3">Top contributors</h2>
      <ol class="space-y-3 text-sm">
        {contributors}
      </ol>
    </div>
    <div class="glass rounded-3xl p-6 pop" style="animation-delay:.55s">
      <h2 class="display text-2xl font-bold mb-3">Why people use it</h2>
      <p class="text-gray-300 leading-relaxed text-sm">{why}</p>
      <div class="mt-5 grid grid-cols-2 gap-3 text-xs">
        <div class="rounded-xl bg-black/30 p-3"><div class="text-gray-400 uppercase tracking-widest">Best for</div><div class="text-gray-200 mt-1 font-medium">{best_for}</div></div>
        <div class="rounded-xl bg-black/30 p-3"><div class="text-gray-400 uppercase tracking-widest">Watch out</div><div class="text-gray-200 mt-1 font-medium">{watch_out}</div></div>
      </div>
    </div>
  </section>

  <footer class="text-center text-xs text-gray-500 mt-6 pb-4">
    Hand-built example dashboard · the live tool produces dashboards like this from the GitHub API in real time.
  </footer>
</div>

<script>
  // Animate the language bars to their target widths after a tick.
  requestAnimationFrame(() => {{
    document.querySelectorAll('.lang-bar').forEach((b) => {{
      const w = b.getAttribute('data-w');
      if (w) b.style.width = w;
    }});
  }});
</script>
</body>
</html>
"""


REPO_DATA = [
    {
        "slug": "facebook-react",
        "full_name": "facebook/react",
        "primary_lang": "JavaScript",
        "accent": "#61dafb", "accent_light": "#7dd3fc",
        "description": "A declarative, component-based JavaScript library for building user interfaces. The de-facto frontend framework powering a huge share of the modern web.",
        "topics": ["javascript", "react", "frontend", "ui", "library"],
        "stars": 234000, "forks": 48000, "created_year": 2013, "license": "MIT",
        "about_p1": "React lets you build UIs as a tree of small, reusable components. State changes flow downward through props; user actions flow upward through callbacks. Re-renders are reconciled against a virtual DOM, so the browser only paints what actually changed.",
        "about_p2": "Originally built at Facebook in 2011 to handle their increasingly stateful UI, React was open-sourced in 2013 and has since become the foundation of frameworks like Next.js, Remix and React Native.",
        "features": ["Declarative component model", "Hooks-based state and effects", "JSX for HTML-in-JS templates", "Concurrent rendering and Suspense", "Used by Meta, Netflix, Airbnb, Uber"],
        "languages": [("JavaScript", 64.0), ("TypeScript", 31.0), ("HTML", 3.5), ("CSS", 1.5)],
        "quickstart": "npx create-react-app my-app\ncd my-app\nnpm start",
        "commits": [
            ("a4f9c2b", "Fix Suspense boundary regression in concurrent renderer", "gaearon", "2 hours ago"),
            ("8e1bd03", "Improve error messages for invalid hook calls", "rickhanlonii", "yesterday"),
            ("f072e51", "Bump dependencies to latest stable", "sebmarkbage", "2 days ago"),
            ("d3c45a9", "Update docs: server components stable in 19.1", "acdlite", "3 days ago"),
        ],
        "contributors": [("gaearon", 2840), ("sebmarkbage", 2401), ("acdlite", 1903), ("sophiebits", 1612), ("rickhanlonii", 1204)],
        "why": "Mature, battle-tested, with by far the largest ecosystem of libraries, examples, and hireable engineers. If something can be built on the web, someone has already done it in React.",
        "best_for": "Stateful product UIs", "watch_out": "Bundle size if naive",
    },
    {
        "slug": "huggingface-transformers",
        "full_name": "huggingface/transformers",
        "primary_lang": "Python",
        "accent": "#fbbf24", "accent_light": "#fde68a",
        "description": "State-of-the-art Machine Learning for PyTorch, TensorFlow, and JAX. Provides thousands of pre-trained models to perform tasks across modalities — text, vision, audio.",
        "topics": ["nlp", "pytorch", "transformers", "llm", "machine-learning"],
        "stars": 137000, "forks": 27500, "created_year": 2018, "license": "Apache-2.0",
        "about_p1": "transformers is the canonical Python library for downloading, fine-tuning and running pre-trained transformer models. It abstracts away architecture differences so you can call BERT, GPT, T5, LLaMA, Mistral and Whisper through one consistent API.",
        "about_p2": "Maintained by Hugging Face, the library has become the on-ramp to modern NLP — and increasingly to vision and speech as well. Most published models on the Hugging Face Hub work with one line of `AutoModel.from_pretrained(...)`.",
        "features": ["1,000+ pre-trained checkpoints", "Pipeline API for one-line inference", "Trainer + Accelerate for distributed fine-tuning", "Tokenizers in pure Rust", "Backends for PyTorch, JAX, TF"],
        "languages": [("Python", 91.0), ("Cuda", 4.0), ("Rust", 2.5), ("Shell", 1.5), ("Other", 1.0)],
        "quickstart": "pip install transformers\nfrom transformers import pipeline\nclf = pipeline('sentiment-analysis')\nclf('VisualLab is great!')",
        "commits": [
            ("3a1f0c2", "Add LLaMA 4 architecture support", "ArthurZucker", "3 hours ago"),
            ("9be41d8", "Fix tokenizer slow path for emoji-heavy inputs", "ydshieh", "yesterday"),
            ("b201ef5", "Update Trainer FSDP integration", "muellerzr", "2 days ago"),
            ("e4d3a7c", "Docs: clarify chat template behaviour", "stevhliu", "3 days ago"),
        ],
        "contributors": [("ArthurZucker", 1812), ("LysandreJik", 1604), ("ydshieh", 1487), ("muellerzr", 902), ("stevhliu", 770)],
        "why": "It's the universal port for trying any new open model the day it drops. Researchers ship demos here; engineers fine-tune here; everyone reads the README to learn the field.",
        "best_for": "Pre-trained model use", "watch_out": "Heavy install size",
    },
    {
        "slug": "ggerganov-llama-cpp",
        "full_name": "ggerganov/llama.cpp",
        "primary_lang": "C++",
        "accent": "#a78bfa", "accent_light": "#c4b5fd",
        "description": "LLM inference in pure C/C++. Runs LLaMA-family and many other open models on CPU (and Apple Silicon, AMD, NVIDIA, Vulkan) with surprisingly little RAM via clever quantisation.",
        "topics": ["llm", "inference", "cpp", "quantization", "ggml"],
        "stars": 71000, "forks": 10300, "created_year": 2023, "license": "MIT",
        "about_p1": "llama.cpp showed that you don't need a GPU to run a useful LLM. By rewriting LLaMA inference in tight C/C++ with custom 4-bit quantisation, Georgi Gerganov made 7B-parameter models usable on a 2020 MacBook Air.",
        "about_p2": "It has since become the go-to local-inference engine — backing Ollama, LM Studio, and most desktop chat apps. The GGUF file format it introduced is now the standard for distributing quantised open-weight models.",
        "features": ["1.5-bit through 8-bit quantisation", "Apple Metal / CUDA / Vulkan / OpenCL backends", "GGUF model format (now an ecosystem standard)", "OpenAI-compatible HTTP server", "Bindings for Python, Rust, Go, Node, Kotlin"],
        "languages": [("C++", 67.0), ("C", 17.0), ("Python", 8.0), ("Cuda", 4.0), ("Metal", 2.5), ("Other", 1.5)],
        "quickstart": "git clone https://github.com/ggerganov/llama.cpp\ncd llama.cpp && make\n./llama-cli -m model.gguf -p \"Hello\"",
        "commits": [
            ("c7d2b9a", "Add GLM-5 architecture support", "ggerganov", "1 hour ago"),
            ("8a3e1f0", "Quantize: faster IQ4_XS path on Zen5", "JohannesGaessler", "yesterday"),
            ("d104c2b", "Metal: Q5_K matmul perf +18% on M3", "0cc4m", "2 days ago"),
            ("af52093", "Server: stream tool-call deltas", "ngxson", "3 days ago"),
        ],
        "contributors": [("ggerganov", 1503), ("slaren", 802), ("JohannesGaessler", 612), ("ngxson", 487), ("0cc4m", 401)],
        "why": "If you want to run a 70B-parameter model on a laptop, this is how. The author's deep understanding of low-level perf has made `llama.cpp` faster per watt than every commercial inference stack on consumer hardware.",
        "best_for": "Local LLM inference", "watch_out": "Steep learning curve",
    },
    {
        "slug": "vercel-next-js",
        "full_name": "vercel/next.js",
        "primary_lang": "TypeScript",
        "accent": "#ffffff", "accent_light": "#94a3b8",
        "description": "The React framework for production. Adds routing, server-side rendering, image optimisation, and an end-to-end build pipeline on top of React, with first-class deployment to Vercel and other hosts.",
        "topics": ["react", "framework", "ssr", "vercel", "typescript"],
        "stars": 128000, "forks": 27300, "created_year": 2016, "license": "MIT",
        "about_p1": "Next.js takes React's render-anything component model and adds the things you actually need to ship a real product: a file-system router, server components, edge functions, image optimisation, and an opinionated build pipeline.",
        "about_p2": "Maintained by Vercel, it's now the default React framework for new product builds. It pioneered the React Server Components model and powers a huge slice of the modern startup web.",
        "features": ["File-system routing with the App Router", "React Server Components by default", "Built-in image / font / script optimisation", "API routes that deploy as edge functions", "ISR — incremental static regeneration"],
        "languages": [("TypeScript", 73.0), ("JavaScript", 14.0), ("Rust", 9.0), ("CSS", 2.0), ("Other", 2.0)],
        "quickstart": "npx create-next-app@latest my-app\ncd my-app\nnpm run dev",
        "commits": [
            ("2c0e814", "App router: fix prefetch behaviour for nested layouts", "ijjk", "4 hours ago"),
            ("6f3d271", "Turbopack: remove a 12% perf regression in dev", "timneutkens", "yesterday"),
            ("a195b30", "Image: support new AVIF profile flags", "shuding", "2 days ago"),
            ("9f81c20", "Docs: clarify partial-prerendering opt-in", "leerob", "3 days ago"),
        ],
        "contributors": [("timneutkens", 4203), ("ijjk", 2891), ("shuding", 1604), ("leerob", 1102), ("huozhi", 902)],
        "why": "Next.js gives you sane defaults for the 90% of decisions a React project would otherwise force you to make manually. Most teams that pick it ship faster than they would have on bare React.",
        "best_for": "Production React apps", "watch_out": "Vercel-shaped opinions",
    },
    {
        "slug": "ollama-ollama",
        "full_name": "ollama/ollama",
        "primary_lang": "Go",
        "accent": "#22d3ee", "accent_light": "#67e8f9",
        "description": "Get up and running with Llama 3, Mistral, Gemma, Phi and dozens of other open LLMs locally. One install, one command, models managed for you.",
        "topics": ["llm", "local", "macos", "linux", "windows", "go"],
        "stars": 92000, "forks": 7400, "created_year": 2023, "license": "MIT",
        "about_p1": "Ollama wraps `llama.cpp` with a friendly CLI and an OpenAI-compatible HTTP server, plus automatic model downloads from a curated library. The result is the simplest possible way to run a serious LLM on your own machine.",
        "about_p2": "It feels like Docker for LLMs: `ollama pull llama3` then `ollama run llama3` and you're talking to a model. The same server can be hit by any OpenAI-SDK app by changing the base URL.",
        "features": ["Curated model library (Llama, Mistral, Phi, Gemma, …)", "OpenAI-compatible REST API", "GPU acceleration (Metal, CUDA, ROCm)", "One-line install on macOS, Linux and Windows", "Model file format (`Modelfile`) for custom configs"],
        "languages": [("Go", 78.0), ("C++", 9.0), ("Python", 5.0), ("Shell", 4.0), ("Other", 4.0)],
        "quickstart": "curl https://ollama.com/install.sh | sh\nollama run llama3",
        "commits": [
            ("e208f1c", "Add support for Llama 4 8B and 70B", "mxyng", "5 hours ago"),
            ("18dc3a0", "Improve cold-start latency on Windows", "jmorganca", "yesterday"),
            ("c7b1f82", "Server: cancel in-flight generations on disconnect", "BruceMacD", "2 days ago"),
            ("4129ad6", "Docs: how to expose Ollama on the LAN", "pdevine", "3 days ago"),
        ],
        "contributors": [("jmorganca", 1840), ("mxyng", 803), ("pdevine", 612), ("BruceMacD", 491), ("dhiltgen", 387)],
        "why": "It removes all the friction of self-hosting an LLM. People who would never have set up Python + CUDA + a quantised model manually run open models daily because of Ollama.",
        "best_for": "Local LLM experiments", "watch_out": "Memory budget for big models",
    },
    {
        "slug": "openai-whisper",
        "full_name": "openai/whisper",
        "primary_lang": "Python",
        "accent": "#34d399", "accent_light": "#6ee7b7",
        "description": "Robust speech recognition via large-scale weak supervision. A general-purpose, multilingual ASR model that just works on noisy real-world audio.",
        "topics": ["speech-recognition", "asr", "whisper", "multilingual", "openai"],
        "stars": 75000, "forks": 8800, "created_year": 2022, "license": "MIT",
        "about_p1": "Whisper was the first open speech-recognition model that genuinely matched commercial APIs across 100 languages. It transcribes, translates to English, and identifies language — all from a single model trained on 680,000 hours of weakly supervised audio.",
        "about_p2": "The release came with the model weights at five sizes (tiny → large), the inference code, and a straightforward Python API. It immediately became the default ASR for podcasters, video editors, accessibility tooling and meeting bots.",
        "features": ["100+ languages, including code-switching", "Speech-to-text and speech-to-English-translation", "Word-level timestamps", "Five model sizes from 39M to 1.55B parameters", "Easy fine-tuning on your own audio"],
        "languages": [("Python", 96.0), ("Jupyter Notebook", 3.0), ("Other", 1.0)],
        "quickstart": "pip install -U openai-whisper\nwhisper audio.mp3 --model medium",
        "commits": [
            ("b91c2a0", "Add support for word-level diarisation", "jongwook", "1 week ago"),
            ("31d4f09", "Improve speaker change detection", "fcakyon", "2 weeks ago"),
            ("af7b3e2", "Speed up encoder on M-series Macs", "hannes", "3 weeks ago"),
            ("d7f1c08", "Docs: clarify VAD-trimming workflow", "alphacep", "1 month ago"),
        ],
        "contributors": [("jongwook", 91), ("fcakyon", 24), ("hannes", 18), ("alphacep", 12), ("anonymous", 9)],
        "why": "It opened up high-quality speech-to-text to anyone with a laptop. A massive number of derivative tools (whisper.cpp, faster-whisper, MacWhisper) exist because the original model is so good and so freely licensed.",
        "best_for": "Audio transcription", "watch_out": "Slow on long files",
    },
    {
        "slug": "tailwindlabs-tailwindcss",
        "full_name": "tailwindlabs/tailwindcss",
        "primary_lang": "TypeScript",
        "accent": "#06b6d4", "accent_light": "#67e8f9",
        "description": "A utility-first CSS framework for rapidly building modern websites without ever leaving your HTML. Compose styles from atomic classes; the build step strips the unused 99%.",
        "topics": ["css", "framework", "design-system", "utility", "tailwind"],
        "stars": 84000, "forks": 4400, "created_year": 2017, "license": "MIT",
        "about_p1": "Tailwind replaces handwritten CSS with a tightly-scoped vocabulary of utility classes — `flex`, `gap-4`, `text-zinc-200`, `hover:bg-blue-500/30`. You compose styles in markup; a JIT compiler emits exactly the bytes you used.",
        "about_p2": "The result is a workflow that's faster than writing CSS by hand and more consistent than ad-hoc class systems. It's now the dominant styling approach for new React, Next, and Astro projects.",
        "features": ["JIT compiler — instant build, no unused CSS", "Design tokens via `tailwind.config.js`", "Built-in dark mode and responsive variants", "First-party plugins for forms, typography, container queries", "Headless UI + Catalyst components from the same team"],
        "languages": [("TypeScript", 64.0), ("JavaScript", 23.0), ("CSS", 9.0), ("HTML", 3.0), ("Other", 1.0)],
        "quickstart": "npm install -D tailwindcss\nnpx tailwindcss init\nnpx tailwindcss -o style.css --watch",
        "commits": [
            ("b53e1f8", "v4: container query units in arbitrary props", "philipp-spiess", "6 hours ago"),
            ("a91b4d2", "Improve OKLCH color preview in autocomplete", "RobinMalfait", "yesterday"),
            ("c204a8f", "Faster initial JIT scan on monorepos", "thecrypticace", "2 days ago"),
            ("8f10d29", "Docs: migrating from v3 to v4", "adamwathan", "3 days ago"),
        ],
        "contributors": [("adamwathan", 2104), ("RobinMalfait", 1391), ("philipp-spiess", 802), ("thecrypticace", 614), ("ChrisBrownie55", 287)],
        "why": "It's the fastest way to ship a UI that looks designed, especially without a designer. Most '2024-looking' websites — including this one — are built with it.",
        "best_for": "Custom UI design", "watch_out": "Markup-heavy classnames",
    },
    {
        "slug": "denoland-deno",
        "full_name": "denoland/deno",
        "primary_lang": "Rust",
        "accent": "#fb923c", "accent_light": "#fdba74",
        "description": "A modern, all-in-one runtime for JavaScript and TypeScript. Built in Rust, powered by V8, with secure-by-default permissions and a built-in toolchain.",
        "topics": ["javascript", "typescript", "runtime", "rust", "v8"],
        "stars": 96000, "forks": 5300, "created_year": 2018, "license": "MIT",
        "about_p1": "Deno is what Node.js's creator, Ryan Dahl, would build if he started over today. TypeScript runs natively. Imports are URLs. The runtime asks for permission before touching the filesystem or network.",
        "about_p2": "It bundles formatter, linter, test runner, doc generator and dependency cache so you don't curate a package.json + 47 dev dependencies just to start a project. Recent versions added full Node.js compatibility, so you can use Deno for new code without giving up the npm ecosystem.",
        "features": ["TypeScript-first; no transpile step needed", "Permission-based security model", "Single binary — no global package mess", "Built-in fmt, lint, test, doc, bench", "Node.js + npm compatibility (since 1.30)"],
        "languages": [("Rust", 73.0), ("TypeScript", 17.0), ("JavaScript", 6.0), ("Python", 2.0), ("Other", 2.0)],
        "quickstart": "curl -fsSL https://deno.land/install.sh | sh\ndeno run --allow-net main.ts",
        "commits": [
            ("af19c0d", "Improve `deno bundle` performance for large graphs", "bartlomieju", "5 hours ago"),
            ("c01f9b3", "Fix Node compat: stream.pipeline edge case", "lucacasonato", "yesterday"),
            ("9e2018a", "Update V8 to 12.7", "kt3k", "2 days ago"),
            ("1a4b720", "Docs: comparing Deno KV with Redis", "nayeemrmn", "3 days ago"),
        ],
        "contributors": [("ry", 1502), ("bartlomieju", 1391), ("kt3k", 902), ("lucacasonato", 803), ("nayeemrmn", 491)],
        "why": "Deno fixes the most-cited frustrations with Node.js without breaking the JavaScript ecosystem. It's a quietly excellent choice for new tooling, scripts, and serverless functions.",
        "best_for": "TypeScript scripting", "watch_out": "Smaller ecosystem than Node",
    },
    {
        "slug": "pytorch-pytorch",
        "full_name": "pytorch/pytorch",
        "primary_lang": "Python",
        "accent": "#f97316", "accent_light": "#fdba74",
        "description": "Tensors and dynamic neural networks in Python with strong GPU acceleration. The default deep-learning framework for research, and increasingly for production too.",
        "topics": ["deep-learning", "pytorch", "neural-network", "gpu", "machine-learning"],
        "stars": 86000, "forks": 23400, "created_year": 2016, "license": "BSD-3-Clause",
        "about_p1": "PyTorch gives you a numpy-style array library where every operation is differentiable. You write a neural network as a regular Python class; backpropagation, GPU placement and distributed training come for free.",
        "about_p2": "Originally built at Facebook AI Research, it's now the framework behind almost every major published ML paper, every modern open LLM, and a growing share of production inference too — especially since the `torch.compile` JIT in PyTorch 2 closed most of the perf gap with C++ frameworks.",
        "features": ["Autograd over arbitrary Python", "Native distributed training (FSDP, DDP)", "torch.compile for graph-mode speedups", "Strong CUDA, MPS and ROCm backends", "Massive ecosystem (TorchVision, TorchText, Lightning, …)"],
        "languages": [("Python", 53.0), ("C++", 38.0), ("Cuda", 6.0), ("CMake", 2.0), ("Other", 1.0)],
        "quickstart": "pip install torch\nimport torch\nx = torch.randn(3, 3, requires_grad=True)\n(x * 2).sum().backward()",
        "commits": [
            ("d4e018b", "Inductor: support flex-attention for arbitrary masks", "drisspg", "3 hours ago"),
            ("a0f9c12", "Distributed: FSDP fix for tied embeddings", "awgu", "yesterday"),
            ("c8b1740", "MPS: faster bilinear interp on Apple Silicon", "kulinseth", "2 days ago"),
            ("6f0a3e8", "torch.compile: better diagnostics on graph break", "ezyang", "3 days ago"),
        ],
        "contributors": [("ezyang", 4012), ("malfet", 2903), ("ngimel", 2104), ("kulinseth", 1502), ("awgu", 1207)],
        "why": "If you read an ML paper from the last five years, the reference implementation is overwhelmingly likely to be in PyTorch. It's the lingua franca of modern deep learning research.",
        "best_for": "Deep-learning research", "watch_out": "Heavy install on CUDA",
    },
    {
        "slug": "langchain-ai-langchain",
        "full_name": "langchain-ai/langchain",
        "primary_lang": "Python",
        "accent": "#10b981", "accent_light": "#34d399",
        "description": "Building applications with LLMs through composability. A framework for chaining models, prompts, retrievers, tools and agents into useful applications.",
        "topics": ["llm", "agents", "rag", "ai", "framework"],
        "stars": 89000, "forks": 14300, "created_year": 2022, "license": "MIT",
        "about_p1": "LangChain is the most popular framework for stitching LLM calls into applications. It abstracts the LLM, the vector store, the retriever, the tool, the memory, and the agent loop — so you can swap any layer without rewriting the rest.",
        "about_p2": "The LangChain ecosystem now includes LangSmith for tracing, LangServe for deployment, and LangGraph for building stateful, multi-step agents. Used by tens of thousands of teams to ship LLM features quickly.",
        "features": ["Chains and pipelines for prompt → model → parse flows", "RAG primitives — splitter, embedding, vector store, retriever", "200+ integrations (OpenAI, Anthropic, Mistral, NVIDIA NIM, …)", "Agent patterns: ReAct, plan-and-execute, OpenAI tools", "LangGraph for stateful, multi-actor agent graphs"],
        "languages": [("Python", 96.5), ("Jupyter Notebook", 2.5), ("Shell", 0.5), ("Other", 0.5)],
        "quickstart": "pip install langchain langchain-openai\nfrom langchain_openai import ChatOpenAI\nllm = ChatOpenAI()\nllm.invoke('Hi')",
        "commits": [
            ("9e6b3ad", "Add NVIDIA NIM-hosted model support", "efriis", "4 hours ago"),
            ("2c1f807", "RAG: faster Chroma multi-collection query", "ccurme", "yesterday"),
            ("a705d1c", "LangGraph integration for sub-graph composition", "hwchase17", "2 days ago"),
            ("d40b912", "Docs: tool-call streaming patterns", "rlancemartin", "3 days ago"),
        ],
        "contributors": [("hwchase17", 1402), ("efriis", 891), ("ccurme", 612), ("rlancemartin", 487), ("baskaryan", 401)],
        "why": "If you're prototyping an LLM application and don't have a strong opinion yet on the stack, LangChain gets you to a working demo fastest. The integration coverage is unmatched.",
        "best_for": "LLM app prototyping", "watch_out": "Abstraction layers",
    },
]


def hex_to_rgba(hex_str: str, a: float) -> str:
    h = hex_str.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def fmt_stars(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.0f}k" if n >= 10000 else f"{n/1000:.1f}k"
    return str(n)


def build_repo_html(d: dict) -> str:
    accent = d["accent"]
    accent_light = d["accent_light"]
    accent_border = hex_to_rgba(accent, 0.22)
    accent_chip_bg = hex_to_rgba(accent, 0.12)
    accent_chip_text = accent_light
    topic_chips = "\n      ".join(f'<span class="chip">{t}</span>' for t in d["topics"])
    features_html = "\n        ".join(
        f'<li class="flex gap-3"><span class="text-xs font-bold mt-1" style="color:{accent_light}">▸</span><span class="text-sm text-gray-300">{f}</span></li>'
        for f in d["features"]
    )
    total = sum(p for _, p in d["languages"])
    lang_html = "\n        ".join(
        f'<div class="lang-row"><span class="text-sm w-32 truncate text-gray-200">{lang}</span><div class="lang-bar-bg"><div class="lang-bar" data-w="{(p/total*100):.0f}%" style="width:0"></div></div><span class="mono text-xs text-gray-400 w-12 text-right">{(p/total*100):.0f}%</span></div>'
        for lang, p in d["languages"]
    )
    commits_html = "\n      ".join(
        f'<div class="commit-row"><div class="commit-sha">{sha}</div><div class="flex-1 min-w-0"><div class="text-sm text-gray-200 truncate">{msg}</div><div class="text-xs text-gray-500 mt-0.5">@{author} · {when}</div></div></div>'
        for sha, msg, author, when in d["commits"]
    )
    contribs_html = "\n        ".join(
        f'<li class="flex items-center gap-3"><span class="display font-bold text-lg" style="color:{accent_light}">{i+1}</span><span class="flex-1 text-gray-200">{name}</span><span class="mono text-xs text-gray-400">{count:,} commits</span></li>'
        for i, (name, count) in enumerate(d["contributors"])
    )
    age = 2026 - d["created_year"]
    return REPO_TEMPLATE.format(
        full_name=d["full_name"],
        primary_lang=d["primary_lang"],
        accent=accent, accent_light=accent_light,
        accent_border=accent_border,
        accent_chip_bg=accent_chip_bg, accent_chip_text=accent_chip_text,
        description=d["description"],
        topic_chips=topic_chips,
        stars_display=fmt_stars(d["stars"]),
        stars_subtext="GitHub stars",
        forks_display=fmt_stars(d["forks"]),
        created_year=d["created_year"],
        age_subtext=f"{age} years old",
        license=d["license"],
        about_p1=d["about_p1"],
        about_p2=d["about_p2"],
        features=features_html,
        languages=lang_html,
        quickstart=d["quickstart"],
        commits=commits_html,
        contributors=contribs_html,
        why=d["why"],
        best_for=d["best_for"],
        watch_out=d["watch_out"],
    )


# ---------------------------------------------------------------------------
# VisualArt example template + data
# ---------------------------------------------------------------------------

ART_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<title>{title} — VisualArt</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  body {{ font-family:'Inter',system-ui,sans-serif; background:#0a0908; color:#e8e6e1; }}
  .serif {{ font-family:'Cormorant Garamond',Georgia,serif; }}
  .glass {{ background:rgba(20,17,15,.7); backdrop-filter:blur(14px); border:1px solid rgba(212,163,115,.18); }}
  .grad {{ background:linear-gradient(120deg,{accent},{accent_light}); -webkit-background-clip:text; background-clip:text; color:transparent; }}
  @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
  @keyframes heroIn {{ from {{ opacity:0; transform:scale(1.04); }} to {{ opacity:1; transform:scale(1); }} }}
  .pop {{ animation: fadeIn .8s ease backwards; }}
  .hero-img {{ animation: heroIn 1.4s ease both; }}
  .hairline {{ height:1px; background:linear-gradient(90deg,transparent,{accent},transparent); }}
  .accent-bar {{ background:linear-gradient(135deg,{accent},{accent_light}); }}
</style>
</head>
<body class="min-h-screen">

<div class="max-w-5xl mx-auto px-6 md:px-10 py-10 space-y-12">

  <!-- HERO -->
  <header class="text-center pop" style="animation-delay:0s">
    <div class="text-xs uppercase tracking-[0.4em] text-stone-400 mb-4">The Metropolitan Museum of Art · {department}</div>
    <div class="rounded-2xl overflow-hidden mb-8 bg-stone-900/60" style="border:1px solid rgba(212,163,115,.15)">
      <img src="{image}" alt="{title}" class="hero-img w-full max-h-[78vh] object-contain bg-stone-950" loading="lazy" referrerpolicy="no-referrer" />
    </div>
    <h1 class="serif text-4xl md:text-6xl font-medium leading-tight"><span class="grad">{title}</span></h1>
    <div class="serif text-xl md:text-2xl text-stone-300 mt-3 italic">{artist}</div>
    <div class="text-sm uppercase tracking-[0.3em] text-stone-400 mt-2">{date}</div>
    <a href="{url}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 mt-6 px-5 py-2.5 rounded-full accent-bar text-stone-900 font-semibold text-sm transition hover:scale-[1.02]">View on metmuseum.org →</a>
  </header>

  <div class="hairline"></div>

  <!-- ABOUT -->
  <section class="grid md:grid-cols-3 gap-10 pop" style="animation-delay:.15s">
    <div class="md:col-span-2 space-y-5 serif text-lg leading-relaxed text-stone-200" style="font-weight:400">
      <h2 class="text-3xl font-semibold mb-2 text-stone-100">About this work</h2>
      <p>{about_p1}</p>
      <p>{about_p2}</p>
      <p>{about_p3}</p>
    </div>
    <aside class="space-y-4">
      <div class="glass rounded-xl p-5">
        <div class="text-xs uppercase tracking-[0.2em] text-stone-400">Medium</div>
        <div class="serif text-lg text-stone-200 mt-1">{medium}</div>
      </div>
      <div class="glass rounded-xl p-5">
        <div class="text-xs uppercase tracking-[0.2em] text-stone-400">Dimensions</div>
        <div class="serif text-lg text-stone-200 mt-1">{dimensions}</div>
      </div>
      <div class="glass rounded-xl p-5">
        <div class="text-xs uppercase tracking-[0.2em] text-stone-400">Classification</div>
        <div class="serif text-lg text-stone-200 mt-1">{classification}</div>
      </div>
      <div class="glass rounded-xl p-5">
        <div class="text-xs uppercase tracking-[0.2em] text-stone-400">Credit line</div>
        <div class="text-sm text-stone-300 mt-1 leading-relaxed">{credit_line}</div>
      </div>
    </aside>
  </section>

  <div class="hairline"></div>

  <!-- ARTIST -->
  <section class="pop" style="animation-delay:.25s">
    <h2 class="serif text-3xl font-semibold mb-3 text-stone-100">About the artist</h2>
    <p class="serif text-lg leading-relaxed text-stone-200 max-w-3xl">{artist_blurb}</p>
  </section>

  <div class="hairline"></div>

  <!-- METADATA -->
  <footer class="pt-2 pop" style="animation-delay:.35s">
    <div class="flex flex-wrap gap-2 mb-4">
      {tags}
    </div>
    <div class="text-xs text-stone-500 text-center mt-8 leading-relaxed">
      Hand-built example dashboard · the live tool produces dashboards like this from the Met API in real time.<br/>
      Image and metadata via the Metropolitan Museum of Art Open Access program.
    </div>
  </footer>
</div>
</body>
</html>
"""


# Met objectIDs are stable identifiers. The image URLs are public (Open Access).
# We pick well-known works with high-resolution open-content images.
ART_DATA = [
    {
        "slug": "van-gogh-wheat-field",
        "object_id": "436535",
        "title": "Wheat Field with Cypresses",
        "artist": "Vincent van Gogh",
        "date": "1889",
        "year": 1889,
        "medium": "Oil on canvas",
        "dimensions": "73 × 93.4 cm (28 7/8 × 36 3/4 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Purchase, The Annenberg Foundation Gift, 1993",
        "accent": "#d4a373", "accent_light": "#f4d4a8",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP-42549-001.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/436535",
        "blurb": "Van Gogh's swirling Provence landscape — one of three closely-related canvases.",
        "about_p1": "Painted in late June or early July 1889, during Van Gogh's voluntary stay at the asylum of Saint-Paul-de-Mausole at Saint-Rémy-de-Provence, this canvas is one of his most beloved landscapes.",
        "about_p2": "The dynamic, swirling brushwork that animates the cypresses, the rolling wheat and the rapidly moving clouds was Van Gogh's solution to a deeply held problem: how to render natural movement and emotion in static pigment.",
        "about_p3": "There are three closely related Wheat Field with Cypresses paintings, of which this is the most finished. Van Gogh wrote to his brother Theo that the cypresses were 'always occupying my thoughts — it astonishes me that no one has yet done them as I see them'.",
        "artist_blurb": "Vincent van Gogh (1853-1890) painted just over 800 oil paintings in a career that lasted only ten years. He sold one in his lifetime. Today his works hold the highest auction records in art history. The Met's collection includes 17 of his paintings.",
        "tags": ["Post-Impressionism", "Saint-Rémy", "Landscape", "Cypresses", "1889", "Open Access"],
    },
    {
        "slug": "vermeer-young-woman-water-pitcher",
        "object_id": "437881",
        "title": "Young Woman with a Water Pitcher",
        "artist": "Johannes Vermeer",
        "date": "ca. 1662",
        "year": 1662,
        "medium": "Oil on canvas",
        "dimensions": "45.7 × 40.6 cm (18 × 16 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Marquand Collection, Gift of Henry G. Marquand, 1889",
        "accent": "#94a3b8", "accent_light": "#cbd5e1",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP353257.jpg".replace("DT1567", "DT1466"),
        "url": "https://www.metmuseum.org/art/collection/search/437881",
        "blurb": "An early-1660s Vermeer — the first work by him to enter an American museum.",
        "about_p1": "Painted around 1662, this small canvas was the first painting by Vermeer to enter a public collection in the United States. It arrived at the Met in 1889, when fewer than a dozen Vermeers had ever crossed the Atlantic.",
        "about_p2": "A young woman, caught in a quiet morning ritual, holds a brass basin with one hand and reaches for a window with the other. The cool light entering from the left and the precise geometry of the room are unmistakably Vermeer's.",
        "about_p3": "Vermeer painted only about 35 known works in his lifetime — exquisite, slow, and almost entirely set in the same tiled rooms of his Delft house. Each is a study of light, glass, fabric and the interior worlds of women.",
        "artist_blurb": "Johannes Vermeer (1632-1675) was a Dutch Baroque painter who spent his entire life in Delft. Largely forgotten for two centuries after his death, he was rediscovered in the 19th century and is now considered one of the supreme masters of Western painting.",
        "tags": ["Dutch Golden Age", "Baroque", "Vermeer", "Delft", "ca. 1662", "Open Access"],
    },
    {
        "slug": "sargent-madame-x",
        "object_id": "12127",
        "title": "Madame X (Madame Pierre Gautreau)",
        "artist": "John Singer Sargent",
        "date": "1883-84",
        "year": 1884,
        "medium": "Oil on canvas",
        "dimensions": "208.6 × 109.9 cm (82 1/8 × 43 1/4 in.)",
        "classification": "Paintings",
        "department": "American Wing",
        "credit_line": "Arthur Hoppock Hearn Fund, 1916",
        "accent": "#dc2626", "accent_light": "#fca5a5",
        "image": "https://images.metmuseum.org/CRDImages/ad/original/DP-29006-001.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/12127",
        "blurb": "The portrait that scandalized the 1884 Paris Salon and made Sargent's career.",
        "about_p1": "Sargent painted the famous American expatriate beauty Virginie Amélie Avegno Gautreau in 1883-84 not on commission, but because he believed her unusual chalk-white skin and aquiline profile would launch his career.",
        "about_p2": "When the painting was unveiled at the 1884 Paris Salon, the original version showed one of the dress's jeweled straps slipping off her shoulder. Critics were appalled; the Gautreau family demanded its withdrawal. Sargent later repainted the strap into place — but his reputation in Paris was ruined and he moved to London.",
        "about_p3": "Decades later, Sargent told a friend that this was 'the best thing I have done.' The Met purchased it in 1916, by which time Madame X had become a touchstone of late-19th-century portraiture.",
        "artist_blurb": "John Singer Sargent (1856-1925) was the leading portraitist of the Edwardian era. Born in Florence to American parents, he trained in Paris and worked between Paris, London, and Boston. He left more than 900 oil paintings and 2,000 watercolors.",
        "tags": ["Portraiture", "Belle Époque", "American Wing", "Sargent", "1884", "Open Access"],
    },
    {
        "slug": "hokusai-great-wave",
        "object_id": "45434",
        "title": "Under the Wave off Kanagawa (The Great Wave)",
        "artist": "Katsushika Hokusai",
        "date": "ca. 1830-32",
        "year": 1831,
        "medium": "Polychrome woodblock print; ink and color on paper",
        "dimensions": "25.7 × 37.9 cm (10 1/8 × 14 15/16 in.)",
        "classification": "Prints",
        "department": "Asian Art",
        "credit_line": "H. O. Havemeyer Collection, Bequest of Mrs. H. O. Havemeyer, 1929",
        "accent": "#0ea5e9", "accent_light": "#7dd3fc",
        "image": "https://images.metmuseum.org/CRDImages/as/original/DP130155.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/45434",
        "blurb": "The most reproduced image in art history — Hokusai's towering wave.",
        "about_p1": "The first print in Hokusai's series Thirty-six Views of Mount Fuji, this woodblock print is the most widely reproduced image in the history of art. Mount Fuji appears small and snow-capped on the horizon, its silhouette echoed by the cresting wave that dominates the foreground.",
        "about_p2": "The print uses a then-newly imported Prussian blue pigment, which gave Hokusai a deep, lightfast colour unavailable to earlier ukiyo-e artists. The Met's impression is one of the finest surviving early printings.",
        "about_p3": "Several thousand impressions were originally pulled from the woodblocks; only a few hundred remain. The image's reach is so total that it has become a visual shorthand for Japan itself, despite originally being a piece of mass-produced commercial art.",
        "artist_blurb": "Katsushika Hokusai (1760-1849) was a Japanese ukiyo-e painter and printmaker of the Edo period. Active for over seventy years, he produced an estimated 30,000 works. He famously claimed that 'from around the age of 73 I began to grasp the structures of birds and beasts'.",
        "tags": ["Ukiyo-e", "Edo Period", "Woodblock", "Hokusai", "ca. 1831", "Open Access"],
    },
    {
        # Originally Monet's Bridge over a Pond of Water Lilies — but the Met
        # doesn't release Monet images under Open Access (none of his works in
        # the collection have a primaryImage URL). Swapped for Rembrandt's
        # Aristotle, one of the Met's signature acquisitions.
        "slug": "rembrandt-aristotle-with-homer",
        "object_id": "437394",
        "title": "Aristotle with a Bust of Homer",
        "artist": "Rembrandt (Rembrandt van Rijn)",
        "date": "1653",
        "year": 1653,
        "medium": "Oil on canvas",
        "dimensions": "143.5 × 136.5 cm (56 1/2 × 53 3/4 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Purchase, special contributions and funds given or bequeathed by friends of the Museum, 1961",
        "accent": "#fbbf24", "accent_light": "#fde68a",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP-30758-001.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/437394",
        "blurb": "Rembrandt's meditation on knowledge and worldly success — the most expensive painting in the world when the Met bought it in 1961.",
        "about_p1": "Painted in 1653 for the Sicilian collector Don Antonio Ruffo, Aristotle with a Bust of Homer is among Rembrandt's most enigmatic works. The philosopher, draped in a luxurious gold chain, rests one hand thoughtfully on a marble bust of Homer — wealth and power touching the head of an itinerant blind poet.",
        "about_p2": "Scholars have read the painting as Rembrandt's commentary on the relative worth of material success and creative genius. Aristotle's expression is famously ambiguous: melancholy, admiring, possibly even envious.",
        "about_p3": "When the Met acquired the painting at auction in 1961 for $2.3 million, it was the highest price ever paid for any work of art — a record that made front-page news around the world and helped establish the New York art market's modern importance.",
        "artist_blurb": "Rembrandt van Rijn (1606-1669) was the towering figure of the Dutch Golden Age and is generally considered one of the greatest painters in European history. He produced about 300 paintings, 300 etchings and 2,000 drawings across a career marked by dazzling early success and late-life bankruptcy.",
        "tags": ["Dutch Golden Age", "Baroque", "Rembrandt", "Portraiture", "1653", "Open Access"],
    },
    {
        "slug": "bruegel-harvesters",
        "object_id": "435809",
        "title": "The Harvesters",
        "artist": "Pieter Bruegel the Elder",
        "date": "1565",
        "year": 1565,
        "medium": "Oil on wood",
        "dimensions": "119 × 162 cm (46 7/8 × 63 3/4 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Rogers Fund, 1919",
        "accent": "#ca8a04", "accent_light": "#fbbf24",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP119115.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/435809",
        "blurb": "August panel from Bruegel's revolutionary cycle of the seasons.",
        "about_p1": "Painted in 1565, The Harvesters is one of six (originally probably twelve) panels Bruegel made depicting different seasons of the year. Five survive; this one represents August, the ripening of summer.",
        "about_p2": "Bruegel was the first European painter to make peasants the central subject of monumental art rather than incidental figures. The harvest is shown with humanity, humor, and a complete absence of moralising.",
        "about_p3": "The Met acquired the painting in 1919 for what was then the colossal sum of $50,000. It is widely considered one of the greatest paintings of the Northern Renaissance and one of the Met's signature European works.",
        "artist_blurb": "Pieter Bruegel the Elder (c.1525-1569) was the most important Flemish painter of the 16th century and the founder of a multi-generational artistic dynasty. He painted only about 45 surviving panel paintings; the Met owns three.",
        "tags": ["Northern Renaissance", "Flemish", "Bruegel", "Harvest", "1565", "Open Access"],
    },
    {
        "slug": "klimt-mada-primavesi",
        "object_id": "435799",
        "title": "Mäda Primavesi",
        "artist": "Gustav Klimt",
        "date": "1912-13",
        "year": 1913,
        "medium": "Oil on canvas",
        "dimensions": "150.0 × 110.5 cm (59 1/16 × 43 1/2 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Gift of André and Clara Mertens, in memory of her mother, Jenny Pulitzer Steiner, 1964",
        "accent": "#a855f7", "accent_light": "#d8b4fe",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/158042.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/435799",
        "blurb": "Klimt's vivid 1912-13 portrait of nine-year-old Mäda Primavesi.",
        "about_p1": "Mäda was the youngest child of Otto and Eugenia Primavesi, important Klimt patrons in the Vienna Secession's later years. She sat for Klimt over many sessions in 1912 and 1913, when she was nine years old.",
        "about_p2": "Klimt rejected the conventions of formal child portraiture, instead presenting Mäda standing planted and self-possessed against an explosively patterned background of his own invention — flowers, ribbons, and stylized motifs.",
        "about_p3": "Mäda survived two world wars and lived until 2000. She told a Met interviewer in 1987 that she had been bored sitting for the painting and had to be bribed with sweets, but that 'Klimt was very kind, and I think he understood me.'",
        "artist_blurb": "Gustav Klimt (1862-1918) led the Vienna Secession movement and is the central figure of Austrian Symbolism. His mature work — flat, gold-leaf, ornamental — defined fin-de-siècle Vienna and remains among the most recognised in art history.",
        "tags": ["Vienna Secession", "Portrait", "Klimt", "Symbolism", "1913", "Open Access"],
    },
    {
        "slug": "caravaggio-denial-saint-peter",
        "object_id": "436105",
        "title": "The Denial of Saint Peter",
        "artist": "Caravaggio (Michelangelo Merisi)",
        "date": "ca. 1610",
        "year": 1610,
        "medium": "Oil on canvas",
        "dimensions": "94 × 125.4 cm (37 × 49 3/8 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "Gift of Herman and Lila Shickman, and Purchase, Lila Acheson Wallace Gift, 1997",
        "accent": "#f59e0b", "accent_light": "#fcd34d",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP-13139-001.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/436105",
        "blurb": "One of Caravaggio's last paintings — three figures, two pointing fingers.",
        "about_p1": "Painted in the final months of Caravaggio's life, around 1610, this is one of the most concentrated narrative paintings in Western art. A maidservant accuses Peter; a soldier presses the question; Peter denies, his hands raised in protest. Three figures, two pointing fingers.",
        "about_p2": "The dramatic light comes from a single off-canvas source — Caravaggio's signature tenebrism stripped down to its most economical form. Background, setting and props have all been eliminated.",
        "about_p3": "Caravaggio died only weeks or months after completing this work, on a beach near Porto Ercole, aged 38. The painting changed hands repeatedly over the centuries before entering the Met in 1997.",
        "artist_blurb": "Michelangelo Merisi da Caravaggio (1571-1610) revolutionised European painting with his use of dramatic lighting and unidealised, common figures as religious subjects. His influence on Baroque painting from Rome to the Netherlands was immediate and immense.",
        "tags": ["Baroque", "Caravaggio", "Tenebrism", "Religious", "ca. 1610", "Open Access"],
    },
    {
        "slug": "leutze-washington-crossing-delaware",
        "object_id": "11417",
        "title": "Washington Crossing the Delaware",
        "artist": "Emanuel Leutze",
        "date": "1851",
        "year": 1851,
        "medium": "Oil on canvas",
        "dimensions": "378.5 × 647.7 cm (149 × 255 in.)",
        "classification": "Paintings",
        "department": "American Wing",
        "credit_line": "Gift of John Stewart Kennedy, 1897",
        "accent": "#3b82f6", "accent_light": "#93c5fd",
        "image": "https://images.metmuseum.org/CRDImages/ad/original/DP215410.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/11417",
        "blurb": "The 12-foot-tall icon of American national mythology, painted in Düsseldorf.",
        "about_p1": "Emanuel Leutze painted his vast canvas — over twelve feet tall and twenty-one feet wide — in Düsseldorf in 1850-51, hoping to inspire European reformers with American revolutionary spirit. Models for the soldiers included American art students living in Düsseldorf.",
        "about_p2": "Leutze took several historical liberties: the boats are too small, the flag (Stars and Stripes) was not adopted until six months after the actual crossing, and the morning sky is wrong for the hour. He was making a national myth, not a documentary.",
        "about_p3": "An earlier 1850 version was destroyed in a museum fire in 1942; a 1979 copy hangs in the West Wing of the White House. The Met's painting is the original surviving full-size version, gifted in 1897.",
        "artist_blurb": "Emanuel Leutze (1816-1868) was a German-born American history painter best known for monumental scenes of American history. He divided his career between Düsseldorf and the United States, helping found the Düsseldorf school's American branch.",
        "tags": ["American Wing", "History Painting", "Leutze", "Revolutionary War", "1851", "Open Access"],
    },
    {
        "slug": "degas-dance-class",
        "object_id": "438817",
        "title": "The Dance Class",
        "artist": "Edgar Degas",
        "date": "1874",
        "year": 1874,
        "medium": "Oil on canvas",
        "dimensions": "83.5 × 77.2 cm (32 7/8 × 30 3/8 in.)",
        "classification": "Paintings",
        "department": "European Paintings",
        "credit_line": "H. O. Havemeyer Collection, Bequest of Mrs. H. O. Havemeyer, 1929",
        "accent": "#ec4899", "accent_light": "#f9a8d4",
        "image": "https://images.metmuseum.org/CRDImages/ep/original/DP-20101-001.jpg",
        "url": "https://www.metmuseum.org/art/collection/search/438817",
        "blurb": "Degas at the Paris Opéra — a rehearsal frozen between motion and rest.",
        "about_p1": "Begun in 1873 and finished in 1874, this is the largest and most important of Degas's many studies of the Paris Opéra ballet. The setting is the rehearsal room of the old Le Peletier opera house, which had burned down only days before the painting was first shown.",
        "about_p2": "The composition is unusual: a diagonal floor sweeps the eye from the dancers in the foreground all the way back to the master, Jules Perrot, whose figure was added late in the painting's development. Two dozen dancers are stretching, scratching, adjusting hair-ribbons — anything but performing.",
        "about_p3": "Degas painted ballet not for its glamour but as a study of women working — the unromantic, posture-correcting reality of a brutal profession. He produced over 1,500 paintings, sketches and sculptures of dancers across his career.",
        "artist_blurb": "Edgar Degas (1834-1917) was a French Impressionist who insisted, throughout his life, that he was a Realist. He exhibited with the Impressionists but was suspicious of plein-air painting and worked obsessively in the studio from sketches and memory.",
        "tags": ["Impressionism", "Degas", "Paris Opéra", "Ballet", "1874", "Open Access"],
    },
]


def build_art_html(d: dict) -> str:
    tags_html = "\n      ".join(
        f'<span class="text-[10px] uppercase tracking-[0.2em] text-stone-400 px-3 py-1.5 rounded-full" style="border:1px solid {hex_to_rgba(d["accent"], 0.3)}; background:{hex_to_rgba(d["accent"], 0.06)}">{t}</span>'
        for t in d["tags"]
    )
    return ART_TEMPLATE.format(
        title=d["title"],
        artist=d["artist"],
        date=d["date"],
        medium=d["medium"],
        dimensions=d["dimensions"],
        classification=d["classification"],
        department=d["department"],
        credit_line=d["credit_line"],
        accent=d["accent"], accent_light=d["accent_light"],
        image=d["image"],
        url=d["url"],
        about_p1=d["about_p1"],
        about_p2=d["about_p2"],
        about_p3=d["about_p3"],
        artist_blurb=d["artist_blurb"],
        tags=tags_html,
    )


def main():
    repo_dir = EX_DIR / "repo"
    art_dir = EX_DIR / "art"
    repo_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)

    # ----- Repo -----
    for d in REPO_DATA:
        (repo_dir / f"{d['slug']}.html").write_text(build_repo_html(d), encoding="utf-8")
    repo_manifest = {
        "items": [
            {
                "slug": d["slug"],
                "title": d["full_name"],
                "blurb": textwrap.shorten(d["description"], width=110, placeholder="…"),
                "accent": d["accent"],
                "year": d["created_year"],
                "authors": d["primary_lang"],
            }
            for d in REPO_DATA
        ]
    }
    (repo_dir / "manifest.json").write_text(
        json.dumps(repo_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(REPO_DATA)} repo examples + manifest")

    # ----- Art -----
    for d in ART_DATA:
        (art_dir / f"{d['slug']}.html").write_text(build_art_html(d), encoding="utf-8")
    art_manifest = {
        "items": [
            {
                "slug": d["slug"],
                "title": d["title"],
                "blurb": d["blurb"],
                "accent": d["accent"],
                "year": d["year"],
                "authors": d["artist"],
            }
            for d in ART_DATA
        ]
    }
    (art_dir / "manifest.json").write_text(
        json.dumps(art_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(ART_DATA)} art examples + manifest")


if __name__ == "__main__":
    main()
