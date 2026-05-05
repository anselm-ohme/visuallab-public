(() => {
  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------------
  // Generic helpers
  // ---------------------------------------------------------------------
  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function stripFences(text) {
    return text
      .replace(/^```(?:html)?\s*/i, "")
      .replace(/\s*```\s*$/i, "")
      .trim();
  }

  function safeFilename(name) {
    const slug = (name || "dashboard")
      .toLowerCase()
      .replace(/[^a-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return (slug || "dashboard") + ".html";
  }

  function isValidEmail(s) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((s || "").trim());
  }

  function downloadBlob(text, filename) {
    const blob = new Blob([text], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  // ---------------------------------------------------------------------
  // Email status (set up by SMTP_* env vars)
  // ---------------------------------------------------------------------
  let emailStatus = { enabled: false, sender: null };
  async function loadEmailStatus() {
    try {
      const res = await fetch("/api/email/status");
      emailStatus = await res.json();
    } catch {
      emailStatus = { enabled: false, sender: null };
    }
  }

  // ---------------------------------------------------------------------
  // Model dropdown (shared list, populated into both selects)
  // ---------------------------------------------------------------------
  const MODEL_SELECTS = [
    "pedia-model-select", "scholar-model-select",
    "repo-model-select", "art-model-select",
  ];
  const RACE_SELECTS = [
    "pedia-model-select-b", "scholar-model-select-b",
    "repo-model-select-b", "art-model-select-b",
  ];
  let modelData = { models: [], default: "" };

  // Helper: friendly label for a given model id.
  function modelLabel(id) {
    const m = (modelData.models || []).find((x) => x.id === id);
    return m ? m.label : id;
  }
  // Helper: short label for chips/tabs — strips the descriptive suffix.
  // "GLM 4.7 — fast, UI-tuned (default)" -> "GLM 4.7"
  function shortModelLabel(id) {
    const full = modelLabel(id);
    return full.split(/\s[—–-]\s/)[0].trim() || full;
  }

  async function loadModels() {
    try {
      const res = await fetch("/api/models");
      modelData = await res.json();
    } catch {
      modelData = { models: [], default: "" };
    }
    // v4 / b.v2: bumped to flush stale DeepSeek/older selections so the
    // current curated defaults (GLM 4.7 + Mistral Medium 3.5) actually
    // appear pre-selected for everyone, including returning visitors.
    const STORAGE_KEY = "vi.model.v4";
    const RACE_B_KEY = "vi.model.b.v2";
    try {
      ["vi.model", "vi.model.v2", "vi.model.v3", "vi.model.b.v1"]
        .forEach((k) => localStorage.removeItem(k));
    } catch {}
    const saved = localStorage.getItem(STORAGE_KEY);
    const savedB = localStorage.getItem(RACE_B_KEY);

    // Default A: whatever the server reports (currently GLM 4.7).
    // Default B: explicitly Mistral Medium 3.5 — the user-confirmed second
    // best for speed + reliability. Falls back to "first non-default" if
    // Mistral isn't in the list for some reason.
    const all = modelData.models || [];
    const PREFERRED_B = "mistralai/mistral-medium-3.5-128b";
    const defaultB =
      (all.find((m) => m.id === PREFERRED_B) ||
       all.find((m) => m.id !== modelData.default) ||
       all[1] || {}).id || modelData.default;

    MODEL_SELECTS.forEach((id) => {
      const sel = $(id);
      if (!sel) return;
      sel.innerHTML = "";
      all.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = m.label;
        if (m.id === modelData.default) opt.selected = true;
        sel.appendChild(opt);
      });
      if (saved && [...sel.options].some((o) => o.value === saved)) {
        sel.value = saved;
      }
      sel.addEventListener("change", () => {
        localStorage.setItem(STORAGE_KEY, sel.value);
        MODEL_SELECTS.forEach((other) => {
          if (other !== id && $(other)) $(other).value = sel.value;
        });
      });
    });

    // Populate the second dropdowns used in race mode with the same list.
    RACE_SELECTS.forEach((id) => {
      const sel = $(id);
      if (!sel) return;
      sel.innerHTML = "";
      all.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = m.label;
        if (m.id === defaultB) opt.selected = true;
        sel.appendChild(opt);
      });
      if (savedB && [...sel.options].some((o) => o.value === savedB)) {
        sel.value = savedB;
      }
      sel.addEventListener("change", () => {
        localStorage.setItem(RACE_B_KEY, sel.value);
        RACE_SELECTS.forEach((other) => {
          if (other !== id && $(other)) $(other).value = sel.value;
        });
      });
    });
  }

  // Race-toggle wiring shared by all modes. Default = ON (per user request).
  const RACE_TOGGLE_KEY = "vi.race.v2";   // bumped to v2 so old "off" prefs don't override the new ON default
  function bindRaceToggle(prefix) {
    const cb = $(`${prefix}-race-toggle`);
    const secondSel = $(`${prefix}-model-select-b`);
    if (!cb || !secondSel) return;
    const stored = localStorage.getItem(RACE_TOGGLE_KEY);
    // First visit: default ON. Returning visitors: respect their last choice.
    const initial = stored === null ? true : stored === "1";
    cb.checked = initial;
    secondSel.classList.toggle("hidden", !initial);
    cb.addEventListener("change", () => {
      localStorage.setItem(RACE_TOGGLE_KEY, cb.checked ? "1" : "0");
      // Mirror to the other modes' toggles so race-mode is global, not per-mode.
      ["pedia", "scholar", "repo", "art"].forEach((p) => {
        const other = $(`${p}-race-toggle`);
        const otherSel = $(`${p}-model-select-b`);
        if (other && other !== cb) other.checked = cb.checked;
        if (otherSel) otherSel.classList.toggle("hidden", !cb.checked);
      });
    });
  }
  function isRaceModeOn() {
    return ["pedia", "scholar", "repo", "art"].some(
      (p) => $(`${p}-race-toggle`)?.checked
    );
  }
  function raceModelsFor(prefix) {
    const a = $(`${prefix}-model-select`)?.value;
    const b = $(`${prefix}-model-select-b`)?.value;
    if (!a || !b) return null;
    if (a === b) return null;   // identical picks — fall back to single-mode
    return [a, b];
  }

  // ---------------------------------------------------------------------
  // Routing
  // ---------------------------------------------------------------------
  const VIEWS = {
    landing: { el: "view-landing", pill: null },
    pedia: { el: "view-pedia", pill: "VisualPedia" },
    scholar: { el: "view-scholar", pill: "VisualScholar" },
    repo: { el: "view-repo", pill: "VisualRepo" },
    art: { el: "view-art", pill: "VisualArt" },
  };

  function currentRoute() {
    const h = (location.hash || "#/").replace(/^#\/?/, "");
    if (VIEWS[h]) return h;
    return "landing";
  }

  const BRAND_TAGS = {
    scholar: "arXiv & Semantic Scholar → animated paper explainers",
    repo: "GitHub → animated repository explainers",
    pedia: "Wikipedia → encyclopedia-style dashboards",
    art: "Met Museum → museum wall cards",
  };

  function applyRoute() {
    const route = currentRoute();
    Object.entries(VIEWS).forEach(([name, def]) => {
      const el = $(def.el);
      if (el) el.classList.toggle("hidden", name !== route);
    });
    const pill = $("mode-pill");
    const back = $("back-home");
    if (route === "landing") {
      pill.classList.add("hidden");
      back.classList.add("hidden");
      $("brand-tag").textContent = "Animated explainers for academic papers, repos & more";
    } else {
      pill.textContent = VIEWS[route].pill;
      pill.dataset.mode = route;
      pill.classList.remove("hidden");
      back.classList.remove("hidden");
      $("brand-tag").textContent = BRAND_TAGS[route] || "";
      const input = $(`${route}-search-input`);
      if (input) setTimeout(() => input.focus(), 30);
    }
    document.title =
      route === "landing"
        ? "VisualLab"
        : `${VIEWS[route].pill} · VisualLab`;
  }

  window.addEventListener("hashchange", applyRoute);
  document.querySelectorAll(".mode-card").forEach((card) => {
    card.addEventListener("click", () => {
      location.hash = `#/${card.dataset.mode}`;
    });
  });
  $("home-brand").addEventListener("click", () => (location.hash = "#/"));
  $("back-home").addEventListener("click", () => (location.hash = "#/"));

  // ---------------------------------------------------------------------
  // Landing demo: cycle through real example dashboards in an iframe.
  // Pulls from the existing pedia + scholar example manifests so we don't
  // have to maintain a separate list. Pauses on hover and on tab-blur.
  // ---------------------------------------------------------------------
  const LANDING_DEMO_INTERVAL_MS = 8000;
  async function initLandingDemo() {
    const frameEl = $("landing-demo-frame");
    const pillEl = $("landing-demo-pill");
    const openEl = $("landing-demo-open");
    const thumbsEl = $("landing-demo-thumbs");
    if (!frameEl || !thumbsEl) return;

    // Pull all four manifests in parallel and round-robin merge them so the
    // demo alternates source modes (scholar → repo → pedia → art → scholar …).
    // This keeps the preview representative of the whole tool, not just the
    // two modes we feature on top.
    const SOURCES = ["scholar", "repo", "pedia", "art"];
    const MODE_LABELS = {
      scholar: "VisualScholar",
      repo: "VisualRepo",
      pedia: "VisualPedia",
      art: "VisualArt",
    };
    const fetched = await Promise.all(
      SOURCES.map(async (mode) => {
        try {
          const res = await fetch(`/static/examples/${mode}/manifest.json`, { cache: "no-store" });
          const data = await res.json();
          return (data.items || []).map((it) => ({ ...it, mode }));
        } catch { return []; }
      })
    );
    // Round-robin merge across the four modes.
    const items = [];
    let idx = 0;
    while (true) {
      const before = items.length;
      fetched.forEach((arr) => { if (idx < arr.length) items.push(arr[idx]); });
      idx += 1;
      if (items.length === before) break;
    }
    if (!items.length) {
      pillEl.textContent = "No examples available";
      return;
    }

    // Build thumbnail bar
    thumbsEl.innerHTML = "";
    items.forEach((it, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "landing-demo-thumb";
      b.textContent = it.title;
      b.title = `${it.title} — ${MODE_LABELS[it.mode] || it.mode}`;
      b.dataset.idx = String(i);
      b.addEventListener("click", () => activate(i, true));
      thumbsEl.appendChild(b);
    });

    let active = -1;
    let timer = null;
    let paused = false;

    function activate(i, userInitiated) {
      if (active === i) return;
      const it = items[i];
      if (!it) return;
      const url = `/static/examples/${it.mode}/${it.slug}.html`;
      // Tiny fade for visual polish
      frameEl.classList.add("fading");
      setTimeout(() => {
        frameEl.src = url;
        frameEl.classList.remove("fading");
      }, 250);
      pillEl.textContent = `${MODE_LABELS[it.mode] || it.mode} · ${it.title}`;
      openEl.onclick = () => { window.location.href = url; };
      [...thumbsEl.children].forEach((c, ix) => c.classList.toggle("active", ix === i));
      active = i;
      if (userInitiated) {
        // Reset the autoplay clock so the user has time to enjoy their pick.
        if (timer) { clearInterval(timer); timer = null; }
        startTimer();
      }
    }
    function next() {
      if (paused) return;
      activate((active + 1) % items.length, false);
    }
    function startTimer() {
      if (timer) return;
      timer = setInterval(next, LANDING_DEMO_INTERVAL_MS);
    }
    function stopTimer() {
      if (timer) { clearInterval(timer); timer = null; }
    }
    // Pause when hovering the iframe area — easier to read what's inside.
    const wrap = frameEl.closest(".landing-demo-frame-wrap");
    if (wrap) {
      wrap.addEventListener("mouseenter", () => { paused = true; });
      wrap.addEventListener("mouseleave", () => { paused = false; });
    }
    // Don't burn CPU when the tab isn't visible.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopTimer(); else startTimer();
    });
    // Don't run if the user isn't on the landing page (saves bandwidth).
    function syncWithRoute() {
      if (currentRoute() === "landing") startTimer(); else stopTimer();
    }
    window.addEventListener("hashchange", syncWithRoute);
    activate(0, false);
    syncWithRoute();
  }

  // ---- "More modes" reveal toggle (landing) ---------------------------
  const moreBtn = $("more-modes-btn");
  const moreGrid = $("more-modes-grid");
  if (moreBtn && moreGrid) {
    const MORE_KEY = "vi.morestate.v1";
    const setOpen = (open) => {
      moreGrid.classList.toggle("hidden", !open);
      moreGrid.setAttribute("aria-hidden", open ? "false" : "true");
      moreBtn.setAttribute("aria-expanded", open ? "true" : "false");
      const txt = moreBtn.querySelector(".more-modes-text");
      if (txt) txt.textContent = open ? "Fewer modes" : "More modes";
    };
    setOpen(localStorage.getItem(MORE_KEY) === "1");
    moreBtn.addEventListener("click", () => {
      const nowOpen = moreGrid.classList.contains("hidden");
      setOpen(nowOpen);
      localStorage.setItem(MORE_KEY, nowOpen ? "1" : "0");
      if (nowOpen) {
        // Scroll the reveal into view smoothly so the user sees what appeared.
        setTimeout(() => moreGrid.scrollIntoView({ behavior: "smooth", block: "nearest" }), 30);
      }
    });
  }

  // ---------------------------------------------------------------------
  // Examples gallery (static, hand-built dashboards)
  // ---------------------------------------------------------------------
  async function loadExamples(mode, gridId, controllerRef) {
    const grid = $(gridId);
    if (!grid) return;
    try {
      const res = await fetch(`/static/examples/${mode}/manifest.json`, { cache: "no-store" });
      const data = await res.json();
      const items = data.items || [];
      grid.innerHTML = "";
      items.forEach((item) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "example-card";
        card.style.setProperty("--card-accent", item.accent || "#7c5cff");
        card.innerHTML = `
          <span class="accent-bar"></span>
          <div class="example-title"></div>
          <div class="example-blurb"></div>
          <div class="example-meta">
            <span></span>
            <span class="example-dot"></span>
          </div>
        `;
        card.querySelector(".example-title").textContent = item.title;
        card.querySelector(".example-blurb").textContent = item.blurb || "";
        const metaText = item.authors
          ? `${item.authors} · ${item.year || ""}`
          : (item.year ? String(item.year) : "Open dashboard");
        card.querySelector(".example-meta span").textContent = metaText;
        card.addEventListener("click", () => {
          grid.querySelectorAll(".example-card").forEach((c) => c.classList.remove("active"));
          card.classList.add("active");
          controllerRef.current?.openExample(
            `/static/examples/${mode}/${item.slug}.html`,
            item.title,
          );
        });
        grid.appendChild(card);
      });
    } catch (err) {
      grid.innerHTML = `<div class="results-status">Examples failed to load: ${err.message}</div>`;
    }
  }

  // ---------------------------------------------------------------------
  // Generic dashboard streamer (shared by both modes)
  // ---------------------------------------------------------------------
  function makeDashboardController(prefix) {
    const els = {
      panel: $(`${prefix}-dashboard-panel`),
      empty: $(`${prefix}-dashboard-empty`),
      loading: $(`${prefix}-dashboard-loading`),
      error: $(`${prefix}-dashboard-error`),
      frame: $(`${prefix}-dashboard-frame`),
      title: $(`${prefix}-loading-title`),
      sub: $(`${prefix}-loading-sub`),
      bar: $(`${prefix}-stream-bar`),
      stats: $(`${prefix}-stream-stats`),
      toolbar: $(`${prefix}-dashboard-toolbar`),
      grid: $(`${prefix}-examples-grid`),
      notifyForm: $(`${prefix}-notify-form`),
      notifyEmail: $(`${prefix}-notify-email`),
      notifyStatus: $(`${prefix}-notify-status`),
      streamOverlay: $(`${prefix}-streaming-overlay`),
      raceTabs: $(`${prefix}-race-tabs`),
    };
    const toolbarBtn = (act) => els.toolbar?.querySelector(`[data-act="${act}"]`);

    let abort = null;
    let lastHtml = null;
    let lastTitle = "dashboard";
    let lastSourceUrl = null;
    let notifyEmail = null;
    let popover = null;
    // Race-mode state (cleared between runs)
    let raceState = null;

    // ---- Email popover (lazy-built) -----------------------------------
    function ensurePopover() {
      if (popover) return popover;
      popover = document.createElement("div");
      popover.className = "email-popover hidden";
      popover.innerHTML = `
        <h4>Email this dashboard</h4>
        <p>We'll attach a self-contained <code>.html</code> file you can open in any browser.</p>
        <form>
          <div class="row">
            <input type="email" name="to" placeholder="you@example.com" required autocomplete="email" />
            <button type="submit">Send</button>
          </div>
          <div class="status"></div>
        </form>`;
      const form = popover.querySelector("form");
      const input = popover.querySelector("input");
      const status = popover.querySelector(".status");
      const sendBtn = popover.querySelector("button[type=submit]");
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        status.className = "status";
        status.textContent = "";
        const to = input.value.trim();
        if (!isValidEmail(to)) {
          status.className = "status err";
          status.textContent = "That doesn't look like a valid email.";
          return;
        }
        const html = await ensureLatestHtml();
        if (!html) {
          status.className = "status err";
          status.textContent = "No dashboard HTML available yet.";
          return;
        }
        sendBtn.disabled = true;
        status.className = "status";
        status.textContent = "Sending…";
        try {
          const res = await fetch("/api/email/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ to, title: lastTitle, html }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
          status.className = "status ok";
          status.textContent = `Queued for ${to}. Check your inbox in a minute.`;
          setTimeout(() => { popover.classList.add("hidden"); }, 1800);
        } catch (err) {
          status.className = "status err";
          status.textContent = err.message;
        } finally {
          sendBtn.disabled = false;
        }
      });
      els.panel.appendChild(popover);
      // Click-outside to dismiss
      document.addEventListener("click", (e) => {
        if (popover.classList.contains("hidden")) return;
        const emailBtn = toolbarBtn("email");
        if (popover.contains(e.target) || emailBtn?.contains(e.target)) return;
        popover.classList.add("hidden");
      });
      return popover;
    }

    async function ensureLatestHtml() {
      if (lastHtml) return lastHtml;
      if (lastSourceUrl) {
        try {
          const res = await fetch(lastSourceUrl);
          if (res.ok) {
            lastHtml = await res.text();
            return lastHtml;
          }
        } catch (_) {}
      }
      return null;
    }

    // ---- View state ---------------------------------------------------
    function refreshToolbar({ hasHtml = false, hasSource = false } = {}) {
      if (!els.toolbar) return;
      const dl = toolbarBtn("download");
      const em = toolbarBtn("email");
      const sh = toolbarBtn("share");
      const downloadable = hasHtml || hasSource;
      if (dl) dl.classList.toggle("hidden", !downloadable);
      if (em) em.classList.toggle("hidden", !(downloadable && emailStatus.enabled));
      // Share works whether html is in memory or only as a source URL — we'll
      // fetch it on demand. Hide it in the empty state, show it otherwise.
      if (sh) sh.classList.toggle("hidden", !downloadable);
    }

    function showState({ empty = false, loading = false, error = null, html = null } = {}) {
      els.empty.classList.toggle("hidden", !empty);
      els.loading.classList.toggle("hidden", !loading);
      els.error.classList.toggle("hidden", !error);
      els.frame.classList.toggle("hidden", !html);
      if (els.toolbar) els.toolbar.classList.toggle("hidden", empty);
      if (popover && empty) popover.classList.add("hidden");
      if (error) els.error.textContent = error;
      if (html !== null) {
        lastHtml = html;
        lastSourceUrl = null;
        els.frame.removeAttribute("src");
        els.frame.srcdoc = html;
      }
      refreshToolbar({ hasHtml: !!lastHtml, hasSource: !!lastSourceUrl });
    }

    function backToExamples() {
      if (abort) { try { abort.abort(); } catch (_) {} abort = null; }
      tearDownRace();
      els.frame.removeAttribute("src");
      els.frame.removeAttribute("srcdoc");
      els.frame.classList.add("hidden");
      if (els.streamOverlay) els.streamOverlay.classList.add("hidden");
      if (popover) popover.classList.add("hidden");
      if (els.grid) els.grid.querySelectorAll(".example-card.active")
        .forEach((c) => c.classList.remove("active"));
      lastHtml = null;
      lastSourceUrl = null;
      lastTitle = "dashboard";
      notifyEmail = null;
      resetNotifyForm();
      showState({ empty: true });
    }

    // ---- Toolbar wiring -----------------------------------------------
    if (els.toolbar) {
      els.toolbar.addEventListener("click", async (e) => {
        const btn = e.target.closest(".toolbar-btn");
        if (!btn) return;
        const act = btn.dataset.act;
        if (act === "back") return backToExamples();
        if (act === "download") {
          const html = await ensureLatestHtml();
          if (!html) return;
          downloadBlob(html, safeFilename(lastTitle));
          btn.classList.add("success");
          setTimeout(() => btn.classList.remove("success"), 1200);
        }
        if (act === "email") {
          const pop = ensurePopover();
          pop.classList.toggle("hidden");
          if (!pop.classList.contains("hidden")) {
            setTimeout(() => pop.querySelector("input")?.focus(), 30);
          }
        }
        if (act === "share") {
          await handleShareClick(btn);
        }
      });
    }

    // ---- Share button: persist HTML server-side, copy URL to clipboard
    async function handleShareClick(btn) {
      const html = await ensureLatestHtml();
      if (!html) {
        flashShareStatus(btn, "No dashboard yet", "err");
        return;
      }
      const originalText = btn.querySelector("span")?.textContent || "Share";
      btn.disabled = true;
      flashShareStatus(btn, "Saving…");
      try {
        const res = await fetch("/api/share", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            html,
            title: lastTitle,
            mode: prefix,
            query: lastTitle,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Save failed (${res.status})`);
        const fullUrl = data.share_url || (location.origin + (data.url || ""));
        // Try the modern clipboard API; fall back to a temp textarea.
        try {
          await navigator.clipboard.writeText(fullUrl);
        } catch (_) {
          const ta = document.createElement("textarea");
          ta.value = fullUrl;
          ta.setAttribute("readonly", "");
          ta.style.position = "absolute"; ta.style.left = "-9999px";
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); } catch (_) {}
          document.body.removeChild(ta);
        }
        flashShareStatus(btn, "Link copied ✓", "ok");
      } catch (err) {
        flashShareStatus(btn, err.message || "Failed", "err");
      } finally {
        btn.disabled = false;
        setTimeout(() => {
          const span = btn.querySelector("span");
          if (span) span.textContent = originalText;
          btn.classList.remove("success");
        }, 2200);
      }
    }
    function flashShareStatus(btn, text, kind) {
      const span = btn.querySelector("span");
      if (span) span.textContent = text;
      btn.classList.toggle("success", kind === "ok");
    }

    // ---- Notify-when-done form (in loading state) ----------------------
    function resetNotifyForm() {
      if (!els.notifyForm) return;
      const btn = els.notifyForm.querySelector(".notify-btn");
      const input = els.notifyEmail;
      if (input) { input.disabled = false; input.value = ""; }
      if (btn) { btn.disabled = false; btn.textContent = "Notify me"; btn.classList.remove("subscribed"); }
      if (els.notifyStatus) { els.notifyStatus.className = "notify-status"; els.notifyStatus.textContent = ""; }
    }
    if (els.notifyForm) {
      els.notifyForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const email = (els.notifyEmail.value || "").trim();
        if (!isValidEmail(email)) {
          els.notifyStatus.className = "notify-status err";
          els.notifyStatus.textContent = "Please enter a valid email address.";
          return;
        }
        notifyEmail = email;
        const btn = els.notifyForm.querySelector(".notify-btn");
        btn.disabled = true;
        btn.textContent = "✓ You're on the list";
        btn.classList.add("subscribed");
        els.notifyEmail.disabled = true;
        els.notifyStatus.className = "notify-status ok";
        els.notifyStatus.textContent = `We'll email ${email} as soon as the dashboard is ready.`;
      });
    }

    async function maybeSendNotifyEmail(html) {
      if (!notifyEmail || !html) return;
      try {
        await fetch("/api/email/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to: notifyEmail, title: lastTitle, html }),
        });
      } catch (_) {
        // silent — the dashboard is on screen anyway
      }
    }

    // Inject defensive CSS into a finished iframe so weirdly-laid-out LLM
    // dashboards always start scrolled to the top. Some models occasionally
    // produce <body> tags with `min-h-screen flex items-end` (or similar)
    // which pushes the actual content to the bottom of the viewport. We
    // override that without affecting genuinely centered designs.
    function injectIframeSafetyStyles(iframe) {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;
        // Make sure the iframe itself uses the device viewport — otherwise
        // mobile Chrome falls back to a 980px desktop layout inside the frame
        // and EVERY dashboard overflows horizontally.
        if (!doc.querySelector('meta[name="viewport"]')) {
          const vp = doc.createElement("meta");
          vp.name = "viewport";
          vp.content = "width=device-width, initial-scale=1, viewport-fit=cover";
          (doc.head || doc.documentElement).appendChild(vp);
        }
        if (doc.getElementById("__visuallab_safety_css")) return;   // idempotent
        const style = doc.createElement("style");
        style.id = "__visuallab_safety_css";
        style.textContent = [
          "html, body { scroll-padding-top: 0 !important;",
          "  max-width: 100vw !important;",
          "  overflow-x: hidden !important; }",
          // Defensive top-alignment ONLY for the body element itself, so
          // genuinely centered grid/flex layouts inside the page (e.g. a
          // hero card with `mx-auto`) keep working as the LLM intended.
          "body { align-items: flex-start !important;",
          "  justify-items: flex-start !important;",
          "  justify-content: flex-start !important; }",
          // Common mobile overflow culprits: oversized media + tables +
          // pre-formatted code blocks. Force them to shrink to fit.
          "img, video, canvas, iframe, svg {",
          "  max-width: 100% !important;",
          "  height: auto !important; }",
          "table, pre, code {",
          "  max-width: 100% !important;",
          "  overflow-x: auto !important; }",
          // Long unbroken strings (URLs, tokens) — break instead of overflowing.
          "p, h1, h2, h3, h4, h5, h6, li, td, th, a, span {",
          "  overflow-wrap: anywhere !important;",
          "  word-break: break-word !important; }",
          // Mobile-specific: clamp giant hero typography and force common
          // multi-column grids to stack so cards don't extend off-screen.
          "@media (max-width: 600px) {",
          "  h1 { font-size: clamp(28px, 9vw, 56px) !important; line-height: 1.05 !important; }",
          "  h2 { font-size: clamp(22px, 6.5vw, 40px) !important; line-height: 1.1 !important; }",
          "  [class*=\"grid-cols-2\"], [class*=\"grid-cols-3\"], [class*=\"grid-cols-4\"], [class*=\"grid-cols-5\"], [class*=\"grid-cols-6\"] {",
          "    grid-template-columns: 1fr !important; }",
          "  [class*=\"min-w-\"] { min-width: 0 !important; }",
          "}",
        ].join("\n");
        (doc.head || doc.documentElement).appendChild(style);
      } catch (_) { /* cross-origin or doc not ready — give up silently */ }
    }

    // ---- Streaming run ------------------------------------------------
    // Two phases:
    //   1) Loading phase: spinner + status text, before first HTML chunk arrives.
    //   2) Progressive phase: switch to iframe, document.write() chunks live so
    //      the user watches the page build itself instead of staring at a loader.
    async function run({ url, body, headline, modelLabel, initialSub, title }) {
      if (abort) abort.abort();
      tearDownRace();
      abort = new AbortController();
      lastHtml = null;
      lastSourceUrl = null;
      lastTitle = title || headline || "dashboard";
      notifyEmail = null;
      resetNotifyForm();
      if (els.notifyForm) els.notifyForm.classList.toggle("hidden", !emailStatus.enabled);

      showState({ loading: true });
      els.title.textContent = headline;
      els.sub.textContent =
        initialSub ||
        `Warming up ${modelLabel}. First request can take up to a minute on the trial tier.`;
      els.bar.style.width = "8%";
      els.stats.textContent = "0 chars streamed";
      hideStreamOverlay();

      let buffer = "";
      let totalChars = 0;
      let docOpen = false;       // true once we've started writing into the iframe
      let writtenIdx = 0;        // how much of `buffer` we've already document.write'd

      // Find the start of the actual HTML doc — skips any code-fence preamble.
      function findHtmlStart(s) {
        const m = /<!doctype|<html\b/i.exec(s);
        return m ? m.index : -1;
      }

      function startProgressiveWrite() {
        const startIdx = findHtmlStart(buffer);
        if (startIdx === -1) return false;
        writtenIdx = startIdx;
        // Switch from loading screen to iframe.
        els.loading.classList.add("hidden");
        els.error.classList.add("hidden");
        els.empty.classList.add("hidden");
        els.frame.classList.remove("hidden");
        els.frame.removeAttribute("src");
        els.frame.removeAttribute("srcdoc");
        // Open a fresh document; subsequent writes parse incrementally.
        try {
          const doc = els.frame.contentDocument;
          doc.open();
          doc.write(buffer.slice(writtenIdx));
          writtenIdx = buffer.length;
          docOpen = true;
          showStreamOverlay(modelLabel);
          if (els.toolbar) els.toolbar.classList.remove("hidden");
          // Apply mobile-overflow + viewport safety as soon as <head> is
          // parseable so the page lays out correctly during streaming, not
          // only after `done`.
          injectIframeSafetyStyles(els.frame);
          return true;
        } catch (e) {
          // Fallback: rare iframe access failure — give up progressive mode.
          docOpen = false;
          return false;
        }
      }

      function progressiveWrite() {
        if (!docOpen) return;
        const piece = buffer.slice(writtenIdx);
        if (!piece) return;
        try {
          els.frame.contentDocument.write(piece);
          writtenIdx = buffer.length;
          injectIframeSafetyStyles(els.frame);   // idempotent
        } catch (e) { /* iframe may be detached */ }
      }

      function progressiveClose(finalHtml) {
        if (docOpen) {
          try { els.frame.contentDocument.close(); } catch (e) {}
          docOpen = false;
        }
        // Replace srcdoc with the canonical, fence-stripped HTML so download/email
        // get a clean document and the iframe matches what the model actually sent.
        if (finalHtml) {
          els.frame.srcdoc = finalHtml;
          lastHtml = finalHtml;
          // srcdoc creates a fresh document — re-inject safety styles once it loads.
          els.frame.addEventListener("load", function once() {
            els.frame.removeEventListener("load", once);
            injectIframeSafetyStyles(els.frame);
          });
        }
        hideStreamOverlay(true);
        refreshToolbar({ hasHtml: !!lastHtml, hasSource: false });
      }

      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: abort.signal,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || `Request failed (${res.status})`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let leftover = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          leftover += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = leftover.indexOf("\n")) !== -1) {
            const line = leftover.slice(0, idx).trim();
            leftover = leftover.slice(idx + 1);
            if (!line) continue;
            let evt;
            try { evt = JSON.parse(line); } catch { continue; }
            handleEvent(evt);
          }
        }

        function handleEvent(evt) {
          if (evt.type === "meta") {
            els.sub.textContent = `Composing dashboard with ${modelLabel}…`;
            if (evt.title) lastTitle = evt.title;
          } else if (evt.type === "chunk") {
            buffer += evt.content;
            totalChars += evt.content.length;
            // Update progress bar (still useful in the brief pre-HTML window).
            const pct = Math.min(95, 8 + Math.round((totalChars / 9000) * 87));
            els.bar.style.width = pct + "%";
            els.stats.textContent = `${totalChars.toLocaleString()} chars streamed`;
            // Live overlay counter (once iframe is showing).
            if (els.streamOverlay) {
              const cnt = els.streamOverlay.querySelector(".streaming-count");
              if (cnt) cnt.textContent = `${totalChars.toLocaleString()} chars`;
            }
            if (!docOpen) {
              startProgressiveWrite();
            } else {
              progressiveWrite();
            }
          } else if (evt.type === "done") {
            els.bar.style.width = "100%";
            const html = (evt.html || stripFences(buffer)).trim();
            if (!html) {
              hideStreamOverlay();
              showState({ error: "The model returned an empty dashboard." });
            } else if (docOpen) {
              // Progressive path: close + canonicalise.
              progressiveClose(html);
              maybeSendNotifyEmail(html);
            } else {
              // Fast model that returned everything before we ever opened the doc.
              hideStreamOverlay();
              showState({ html });
              maybeSendNotifyEmail(html);
            }
          } else if (evt.type === "error") {
            if (docOpen) progressiveClose(null);
            hideStreamOverlay();
            showState({ error: evt.message || "Unknown model error." });
          }
        }
      } catch (err) {
        if (err.name === "AbortError") return;
        if (docOpen) progressiveClose(null);
        hideStreamOverlay();
        showState({ error: err.message });
      }
    }

    // ---- Race-mode streaming run --------------------------------------
    // Spawns one hidden iframe per model and progressively writes chunks
    // routed by `evt.model`. First model to complete becomes the active tab.
    async function runRace({ url, body, headline, modelLabels, title }) {
      if (abort) abort.abort();
      // CRITICAL: remove iframes from any previous run BEFORE building the
      // new raceState. Without this, ensureRaceIframe() appends the new
      // run's iframes alongside the previous run's leftovers, producing the
      // "two stacked dashboards" bug when the user kicks off a second
      // request before tearing down (or right after) the first one.
      tearDownRace();
      // Also clear the single-mode iframe in case the last run was solo.
      els.frame.removeAttribute("src");
      els.frame.removeAttribute("srcdoc");
      els.frame.classList.add("hidden");
      abort = new AbortController();
      lastHtml = null;
      lastSourceUrl = null;
      lastTitle = title || headline || "dashboard";
      notifyEmail = null;
      resetNotifyForm();
      if (els.notifyForm) els.notifyForm.classList.toggle("hidden", !emailStatus.enabled);

      const models = body.models;
      // Build per-model state.
      raceState = {
        active: null,           // currently visible model id
        winner: null,           // first model to emit `done`
        models: {},             // model id -> { iframe, label, buffer, docOpen, writtenIdx, status, html }
      };
      models.forEach((m) => {
        raceState.models[m] = {
          label: modelLabels[m] || m,           // long label (used in alt/title)
          shortLabel: shortModelLabel(m),       // tab text — keep it tight
          iframe: null,
          buffer: "",
          docOpen: false,
          writtenIdx: 0,
          status: "queued",     // queued | streaming | done | error
          totalChars: 0,
          html: null,
          error: null,
        };
      });

      // Loading screen first; switches to iframes as soon as any chunk has HTML.
      showState({ loading: true });
      els.title.textContent = headline;
      els.sub.textContent = `Racing ${models.length} models — first to finish wins.`;
      els.bar.style.width = "8%";
      els.stats.textContent = "0 chars streamed";
      hideStreamOverlay();
      renderRaceTabs();   // builds initial tab bar

      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: abort.signal,
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || `Request failed (${res.status})`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let leftover = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          leftover += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = leftover.indexOf("\n")) !== -1) {
            const line = leftover.slice(0, idx).trim();
            leftover = leftover.slice(idx + 1);
            if (!line) continue;
            let evt;
            try { evt = JSON.parse(line); } catch { continue; }
            handleRaceEvent(evt);
          }
        }
      } catch (err) {
        if (err.name === "AbortError") return;
        // If we never managed to render anything, fall back to error state.
        const anyDone = Object.values(raceState.models).some((m) => m.status === "done");
        if (!anyDone) {
          els.raceTabs.classList.add("hidden");
          showState({ error: err.message });
        }
      }
    }

    function handleRaceEvent(evt) {
      if (!raceState) return;
      if (evt.type === "race") return;   // already used to seed UI
      const modelId = evt.model;
      const m = modelId && raceState.models[modelId];
      if (!m) return;

      if (evt.type === "meta") {
        m.status = m.status === "queued" ? "streaming" : m.status;
        renderRaceTabs();
      } else if (evt.type === "chunk") {
        m.buffer += evt.content;
        m.totalChars += evt.content.length;
        if (m.status === "queued") m.status = "streaming";

        if (!m.docOpen) {
          startRaceProgressive(modelId);
        } else {
          writeRaceProgressive(modelId);
        }
        renderRaceTabs();
      } else if (evt.type === "done") {
        const html = (evt.html || stripFences(m.buffer)).trim();
        m.html = html || null;
        m.status = html ? "done" : "error";
        if (!html) m.error = "Empty response";
        if (m.docOpen) {
          try { m.iframe.contentDocument.close(); } catch (e) {}
          m.docOpen = false;
        }
        // NOTE: deliberately NOT reassigning iframe.srcdoc here.
        // For hidden iframes (the non-active racer) Chrome can show a blank
        // document after a srcdoc reassignment-after-document.write. The
        // already-document.write'd content is already fence-stripped client-
        // side via findHtmlStart, so it's safe to keep as-is.
        injectIframeSafetyStyles(m.iframe);
        // Reset scroll on the finished iframe — fixes the "hero appears at the
        // bottom" bug where Chrome doesn't lay out hidden iframes properly
        // until they're activated.
        try {
          const win = m.iframe.contentWindow;
          if (win && typeof win.scrollTo === "function") win.scrollTo(0, 0);
        } catch (_) {}
        // First successful finisher becomes the spotlight + winner.
        if (!raceState.winner && html) {
          raceState.winner = modelId;
          activateRaceTab(modelId);
          lastHtml = html;
          maybeSendNotifyEmail(html);
          refreshToolbar({ hasHtml: true, hasSource: false });
        }
        // If THIS finished model is the active one, update lastHtml so download/email
        // for the active tab gets the canonical version.
        if (raceState.active === modelId) {
          lastHtml = html;
          refreshToolbar({ hasHtml: !!lastHtml, hasSource: false });
        }
        renderRaceTabs();
      } else if (evt.type === "error") {
        m.status = "error";
        m.error = evt.message || "Model error";
        if (m.docOpen) {
          try { m.iframe.contentDocument.close(); } catch (e) {}
          m.docOpen = false;
        }
        renderRaceTabs();
        // If every model errored, surface the first error.
        const anyAlive = Object.values(raceState.models).some(
          (x) => x.status === "streaming" || x.status === "done"
        );
        if (!anyAlive && !raceState.winner) {
          els.raceTabs.classList.add("hidden");
          showState({ error: m.error });
        }
      }
    }

    function ensureRaceIframe(modelId) {
      const m = raceState.models[modelId];
      if (m.iframe) return m.iframe;
      const iframe = document.createElement("iframe");
      iframe.className = "dashboard-frame";
      iframe.setAttribute("sandbox", "allow-scripts allow-popups allow-same-origin");
      iframe.title = `Generated dashboard (${m.label})`;
      iframe.style.display = "none";   // invisible until activated
      els.panel.appendChild(iframe);
      m.iframe = iframe;
      return iframe;
    }

    function startRaceProgressive(modelId) {
      const m = raceState.models[modelId];
      const idx = (function findHtmlStart(s) {
        const mm = /<!doctype|<html\b/i.exec(s);
        return mm ? mm.index : -1;
      })(m.buffer);
      if (idx === -1) return;
      m.writtenIdx = idx;
      const iframe = ensureRaceIframe(modelId);
      try {
        const doc = iframe.contentDocument;
        doc.open();
        doc.write(m.buffer.slice(m.writtenIdx));
        m.writtenIdx = m.buffer.length;
        m.docOpen = true;
        injectIframeSafetyStyles(iframe);
      } catch (e) { m.docOpen = false; return; }

      // First model to start writing gets the spotlight (until winner overrides).
      if (!raceState.active) {
        // Hide loading + main frame, show race tab bar.
        els.loading.classList.add("hidden");
        els.error.classList.add("hidden");
        els.empty.classList.add("hidden");
        els.frame.classList.add("hidden");
        els.raceTabs.classList.remove("hidden");
        if (els.toolbar) els.toolbar.classList.remove("hidden");
        activateRaceTab(modelId);
      }
    }

    function writeRaceProgressive(modelId) {
      const m = raceState.models[modelId];
      if (!m.docOpen) return;
      const piece = m.buffer.slice(m.writtenIdx);
      if (!piece) return;
      try {
        m.iframe.contentDocument.write(piece);
        m.writtenIdx = m.buffer.length;
        injectIframeSafetyStyles(m.iframe);   // idempotent
      } catch (e) {}
    }

    function activateRaceTab(modelId) {
      if (!raceState) return;
      raceState.active = modelId;
      Object.entries(raceState.models).forEach(([id, m]) => {
        if (m.iframe) m.iframe.style.display = (id === modelId) ? "block" : "none";
      });
      const active = raceState.models[modelId];
      // Defensive: hidden iframes that got document.write'd can end up scrolled
      // to a weird position once shown (Chrome doesn't fully lay out invisible
      // iframes). Force a scroll-to-top on activation so the user always sees
      // the dashboard's hero, not a half-scrolled middle.
      if (active.iframe) {
        try {
          requestAnimationFrame(() => {
            const win = active.iframe.contentWindow;
            if (win && typeof win.scrollTo === "function") win.scrollTo(0, 0);
          });
        } catch (_) {}
      }
      // Update lastHtml to whatever this tab currently has finished (or null if streaming).
      lastHtml = active.html || null;
      refreshToolbar({ hasHtml: !!lastHtml, hasSource: false });
      renderRaceTabs();
    }

    function renderRaceTabs() {
      if (!raceState || !els.raceTabs) return;
      const order = Object.keys(raceState.models);
      // Build/update tab buttons.
      els.raceTabs.innerHTML = "";
      order.forEach((id) => {
        const m = raceState.models[id];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "race-tab " + m.status;
        if (raceState.active === id) btn.classList.add("active");
        if (raceState.winner === id) btn.classList.add("winner");
        const statusText =
          m.status === "queued" ? "queued" :
          m.status === "streaming" ? `${m.totalChars.toLocaleString()} chars` :
          m.status === "done" ? "done" :
          m.status === "error" ? "failed" : "";
        btn.innerHTML = `
          <span class="race-tab-spinner" aria-hidden="true"></span>
          <span class="race-tab-name"></span>
          <span class="race-tab-status"></span>
        `;
        btn.title = m.label;
        btn.querySelector(".race-tab-name").textContent = m.shortLabel || m.label;
        btn.querySelector(".race-tab-status").textContent = statusText;
        btn.addEventListener("click", () => {
          if (m.status === "queued") return;     // nothing to show yet
          if (m.iframe) activateRaceTab(id);
        });
        els.raceTabs.appendChild(btn);
      });
      updateRaceOverlay();
    }

    // Mirrors the active racer's progress into the streaming-overlay pill so
    // the chars-streamed counter stays visible on MOBILE — where the per-tab
    // chars in .race-tab-status are hidden to save horizontal space.
    //
    // On desktop we deliberately keep the overlay hidden during race mode:
    // both race-tabs and streaming-overlay live at top-left, so showing both
    // means the wider overlay's trailing "chars" text peeks out from behind
    // the tab bar and crashes into the toolbar.
    function updateRaceOverlay() {
      if (!raceState || !els.streamOverlay) return;
      const isMobile = typeof window.matchMedia === "function" &&
        window.matchMedia("(max-width: 720px)").matches;
      if (!isMobile) { hideStreamOverlay(); return; }
      const activeId = raceState.active;
      if (!activeId) { hideStreamOverlay(); return; }
      const m = raceState.models[activeId];
      if (!m) { hideStreamOverlay(); return; }
      if (m.status === "streaming" || m.status === "queued") {
        const modelEl = els.streamOverlay.querySelector(".streaming-model");
        const countEl = els.streamOverlay.querySelector(".streaming-count");
        if (modelEl) modelEl.textContent = m.shortLabel || m.label;
        if (countEl) countEl.textContent = `${m.totalChars.toLocaleString()} chars`;
        els.streamOverlay.classList.remove("hidden", "fade-out");
      } else {
        hideStreamOverlay(true);
      }
    }

    function tearDownRace() {
      if (raceState) {
        Object.values(raceState.models).forEach((m) => {
          if (m.iframe) {
            try { m.iframe.remove(); } catch (e) {}
          }
        });
        raceState = null;
      }
      // Defensive sweep: remove any race iframes that may still be in the DOM
      // (e.g. from an aborted run whose state we already discarded). The
      // canonical single-mode iframe has the id ${prefix}-dashboard-frame and
      // must be preserved; race iframes are created without an id.
      if (els.panel) {
        els.panel.querySelectorAll("iframe.dashboard-frame").forEach((node) => {
          if (node !== els.frame) {
            try { node.remove(); } catch (_) {}
          }
        });
      }
      if (els.raceTabs) {
        els.raceTabs.innerHTML = "";
        els.raceTabs.classList.add("hidden");
      }
      hideStreamOverlay();
    }

    // ---- Streaming overlay helpers ------------------------------------
    function showStreamOverlay(modelLabel) {
      if (!els.streamOverlay) return;
      const m = els.streamOverlay.querySelector(".streaming-model");
      if (m) m.textContent = modelLabel || "model";
      const c = els.streamOverlay.querySelector(".streaming-count");
      if (c) c.textContent = "0 chars";
      els.streamOverlay.classList.remove("hidden", "fade-out");
    }
    function hideStreamOverlay(animate) {
      if (!els.streamOverlay) return;
      if (animate) {
        els.streamOverlay.classList.add("fade-out");
        setTimeout(() => {
          els.streamOverlay.classList.add("hidden");
          els.streamOverlay.classList.remove("fade-out");
        }, 380);
      } else {
        els.streamOverlay.classList.add("hidden");
        els.streamOverlay.classList.remove("fade-out");
      }
    }

    function openExample(url, title) {
      if (abort) { try { abort.abort(); } catch (_) {} abort = null; }
      tearDownRace();
      lastHtml = null;
      lastSourceUrl = url;
      lastTitle = title || "dashboard";
      notifyEmail = null;
      els.empty.classList.add("hidden");
      els.loading.classList.add("hidden");
      els.error.classList.add("hidden");
      els.frame.classList.remove("hidden");
      els.frame.removeAttribute("srcdoc");
      els.frame.src = url;
      if (els.toolbar) els.toolbar.classList.remove("hidden");
      refreshToolbar({ hasHtml: false, hasSource: true });
      // Prefetch in the background so download/email feel instant.
      fetch(url).then((r) => r.ok ? r.text() : null)
        .then((t) => { if (t) lastHtml = t; refreshToolbar({ hasHtml: !!lastHtml, hasSource: true }); })
        .catch(() => {});
    }

    showState({ empty: true });
    return { run, runRace, showState, openExample, backToExamples };
  }

  // ---------------------------------------------------------------------
  // VisualPedia (Wikipedia)
  // ---------------------------------------------------------------------
  const PEDIA_LUCKY = [
    "Octopus", "Marie Curie", "Saturn V", "Vincent van Gogh", "Black hole",
    "Tokyo", "The Beatles", "Mariana Trench", "Quantum entanglement", "Mount Everest",
    "Roman Empire", "Ada Lovelace", "Bioluminescence", "Voyager 1", "Studio Ghibli",
  ];

  function initPedia() {
    const input = $("pedia-search-input");
    const lucky = $("pedia-lucky-btn");
    const select = $("pedia-model-select");
    const resultsEl = $("pedia-results");
    const dash = makeDashboardController("pedia");
    const ref = { current: dash };
    loadExamples("pedia", "pedia-examples-grid", ref);
    let activeBtn = null;
    let abort = null;

    function setStatus(msg) {
      resultsEl.innerHTML = `<div class="results-status">${msg}</div>`;
    }

    function render(items) {
      if (!items.length) { setStatus("No matching articles. Try a different query."); return; }
      resultsEl.innerHTML = "";
      items.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "result-item";
        btn.type = "button";
        btn.innerHTML = `
          <div class="result-title"></div>
          <div class="result-snippet"></div>
          ${item.wordcount ? `<div class="result-meta">${item.wordcount.toLocaleString()} words</div>` : ""}
        `;
        btn.querySelector(".result-title").textContent = item.title;
        btn.querySelector(".result-snippet").textContent = item.snippet || "";
        btn.addEventListener("click", () => select_(item.title, btn));
        resultsEl.appendChild(btn);
      });
    }

    async function runSearch(q) {
      if (abort) abort.abort();
      if (!q) { resultsEl.innerHTML = ""; return; }
      abort = new AbortController();
      setStatus("Searching Wikipedia…");
      try {
        const res = await fetch(`/api/pedia/search?q=${encodeURIComponent(q)}`, { signal: abort.signal });
        const data = await res.json();
        if (data.error) { setStatus(`Error: ${data.error}`); return; }
        render(data.results || []);
      } catch (err) { if (err.name !== "AbortError") setStatus(`Error: ${err.message}`); }
    }

    function select_(title, btn) {
      if (activeBtn) activeBtn.classList.remove("active");
      activeBtn = btn; btn.classList.add("active");
      const raceModels = isRaceModeOn() ? raceModelsFor("pedia") : null;
      if (raceModels) {
        const labels = {};
        raceModels.forEach((m) => { labels[m] = modelLabel(m); });
        dash.runRace({
          url: "/api/pedia/dashboard",
          body: { title, models: raceModels },
          headline: `Racing ${raceModels.length} models on “${title}”`,
          modelLabels: labels,
          title,
        });
      } else {
        const label = select.options[select.selectedIndex]?.textContent || "model";
        dash.run({
          url: "/api/pedia/dashboard",
          body: { title, model: select.value || undefined },
          headline: `Building dashboard for “${title}”`,
          modelLabel: label,
          initialSub: `Fetching “${title}” from Wikipedia and warming up ${label}…`,
          title,
        });
      }
    }

    const debounced = debounce((q) => runSearch(q), 280);
    input.addEventListener("input", (e) => debounced(e.target.value.trim()));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = resultsEl.querySelector(".result-item");
        if (first) first.click();
      }
    });
    lucky.addEventListener("click", () => {
      const t = PEDIA_LUCKY[Math.floor(Math.random() * PEDIA_LUCKY.length)];
      input.value = t;
      runSearch(t);
    });
  }

  // ---------------------------------------------------------------------
  // VisualScholar (arXiv)
  // ---------------------------------------------------------------------
  const SCHOLAR_LUCKY = [
    "transformer attention is all you need",
    "diffusion models image synthesis",
    "graph neural networks",
    "AlphaFold protein structure prediction",
    "CRISPR gene editing review",
    "mixture of experts language models",
    "retrieval augmented generation",
    "reinforcement learning from human feedback",
    "quantum error correction surface code",
    "neural radiance fields",
  ];

  function initScholar() {
    const input = $("scholar-search-input");
    const lucky = $("scholar-lucky-btn");
    const select = $("scholar-model-select");
    const resultsEl = $("scholar-results");
    const tabs = document.querySelectorAll(".source-tab");
    const hintEl = $("scholar-source-hint");
    const dash = makeDashboardController("scholar");
    const ref = { current: dash };
    loadExamples("scholar", "scholar-examples-grid", ref);
    let activeBtn = null;
    let abort = null;
    let source = localStorage.getItem("vi.scholar.source") || "arxiv";
    let sourceMeta = {};

    fetch("/api/scholar/sources").then((r) => r.json()).then((data) => {
      (data.sources || []).forEach((s) => { sourceMeta[s.id] = s; });
      applySource(source, { silent: true });
    }).catch(() => {});

    function applySource(next, { silent = false } = {}) {
      source = next;
      localStorage.setItem("vi.scholar.source", source);
      tabs.forEach((t) => {
        const active = t.dataset.source === source;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
      });
      input.placeholder =
        source === "arxiv"
          ? "arXiv search — keywords, author, or paper id (e.g. 2310.06825)"
          : "Semantic Scholar — keywords, author, DOI, or paperId";
      const meta = sourceMeta[source] || {};
      const parts = [meta.description || ""];
      if (source === "semantic_scholar" && meta.has_api_key === false) {
        parts.push('<span class="warn">No SEMANTIC_SCHOLAR_API_KEY set — sharing the anonymous quota, expect frequent 429s under load.</span>');
      }
      hintEl.innerHTML = parts.filter(Boolean).join(" ");
      if (!silent && input.value.trim()) runSearch(input.value.trim());
      else if (!silent) resultsEl.innerHTML = "";
    }

    tabs.forEach((t) => t.addEventListener("click", () => applySource(t.dataset.source)));

    function setStatus(msg) {
      resultsEl.innerHTML = `<div class="results-status">${msg}</div>`;
    }

    function fmtAuthors(authors) {
      if (!authors || !authors.length) return "";
      if (authors.length <= 3) return authors.join(", ");
      return `${authors.slice(0, 3).join(", ")} +${authors.length - 3}`;
    }

    function fmtDate(iso) {
      if (!iso) return "";
      try { return new Date(iso).toISOString().slice(0, 10); } catch { return String(iso).slice(0, 10); }
    }

    function shortId(item) {
      if (source === "arxiv") return item.short_id || "";
      if (item.arxiv_id) return `arXiv:${item.arxiv_id}`;
      if (item.doi) return `doi:${item.doi}`;
      return item.id ? item.id.slice(0, 12) + "…" : "";
    }

    function render(items) {
      if (!items.length) {
        const hint = source === "arxiv"
          ? "No matching papers. Try different keywords or an arXiv id."
          : "No matching papers. Try different keywords, a DOI, or a Semantic Scholar paperId.";
        setStatus(hint);
        return;
      }
      resultsEl.innerHTML = "";
      items.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "result-item scholar";
        btn.type = "button";

        const catsRaw = (item.categories && item.categories.length
          ? item.categories
          : (item.fields_of_study || [])).slice(0, 3);
        const catChips = catsRaw.map((c) => `<span class="cat">${c}</span>`).join("");

        const extras = [];
        if (Number.isFinite(item.citation_count)) {
          extras.push(`<span class="cat cite">${item.citation_count.toLocaleString()} citations</span>`);
        }
        if (item.venue) {
          extras.push(`<span class="cat">${escapeHtml(item.venue)}</span>`);
        }
        const tldrChip = item.tldr
          ? `<span class="cat tldr" title="${escapeHtml(item.tldr)}">TL;DR: ${escapeHtml(item.tldr).slice(0, 90)}…</span>`
          : "";

        const dateStr = fmtDate(item.published) || (item.year ? String(item.year) : "");
        const idStr = shortId(item);

        btn.innerHTML = `
          <div class="result-title"></div>
          <div class="result-authors"></div>
          <div class="result-snippet"></div>
          <div class="result-cats">${catChips}${extras.join("")}</div>
          ${tldrChip ? `<div class="result-cats">${tldrChip}</div>` : ""}
          <div class="result-meta">${escapeHtml(idStr)}${idStr && dateStr ? " · " : ""}${escapeHtml(dateStr)}</div>
        `;
        btn.querySelector(".result-title").textContent = item.title;
        btn.querySelector(".result-authors").textContent = fmtAuthors(item.authors);
        const snippet = (item.summary || "").replace(/\s+/g, " ").slice(0, 220);
        btn.querySelector(".result-snippet").textContent = snippet ? snippet + "…" : "";
        btn.addEventListener("click", () => select_(item, btn));
        resultsEl.appendChild(btn);
      });
    }

    async function runSearch(q) {
      if (abort) abort.abort();
      if (!q) { resultsEl.innerHTML = ""; return; }
      abort = new AbortController();
      setStatus(source === "arxiv" ? "Searching arXiv…" : "Searching Semantic Scholar…");
      try {
        const res = await fetch(
          `/api/scholar/search?q=${encodeURIComponent(q)}&source=${source}`,
          { signal: abort.signal }
        );
        const data = await res.json();
        if (data.error) { setStatus(`Error: ${data.error}`); return; }
        render(data.results || []);
      } catch (err) { if (err.name !== "AbortError") setStatus(`Error: ${err.message}`); }
    }

    function select_(item, btn) {
      if (activeBtn) activeBtn.classList.remove("active");
      activeBtn = btn; btn.classList.add("active");
      const paperId = source === "arxiv" ? item.short_id : item.id;
      const sourceLabel = source === "arxiv" ? "arXiv" : "Semantic Scholar";
      const headline = `Explaining “${item.title.slice(0, 80)}${item.title.length > 80 ? "…" : ""}”`;
      const raceModels = isRaceModeOn() ? raceModelsFor("scholar") : null;
      if (raceModels) {
        const labels = {};
        raceModels.forEach((m) => { labels[m] = modelLabel(m); });
        dash.runRace({
          url: "/api/scholar/dashboard",
          body: { paper_id: paperId, source, models: raceModels },
          headline: `Racing ${raceModels.length} models on this paper`,
          modelLabels: labels,
          title: item.title,
        });
      } else {
        const label = select.options[select.selectedIndex]?.textContent || "model";
        dash.run({
          url: "/api/scholar/dashboard",
          body: { paper_id: paperId, source, model: select.value || undefined },
          headline,
          modelLabel: label,
          initialSub:
            `Fetching paper from ${sourceLabel}${item.pdf_url ? " and extracting PDF text" : ""} — this can take 30–60s before the model starts streaming.`,
          title: item.title,
        });
      }
    }

    function escapeHtml(s) {
      return String(s ?? "").replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
      ));
    }

    const debounced = debounce((q) => runSearch(q), 320);
    input.addEventListener("input", (e) => debounced(e.target.value.trim()));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = resultsEl.querySelector(".result-item");
        if (first) first.click();
      }
    });
    lucky.addEventListener("click", () => {
      const t = SCHOLAR_LUCKY[Math.floor(Math.random() * SCHOLAR_LUCKY.length)];
      input.value = t;
      runSearch(t);
    });
  }

  // ---------------------------------------------------------------------
  // VisualRepo (GitHub)
  // ---------------------------------------------------------------------
  const REPO_LUCKY = [
    "facebook/react", "huggingface/transformers", "ggerganov/llama.cpp",
    "vercel/next.js", "openai/whisper", "ollama/ollama", "tailwindlabs/tailwindcss",
    "denoland/deno", "rust-lang/rust", "pytorch/pytorch", "neovim/neovim",
    "supabase/supabase", "Significant-Gravitas/AutoGPT", "anthropics/anthropic-sdk-python",
  ];

  function escapeHtmlGlobal(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function initRepo() {
    const input = $("repo-search-input");
    const lucky = $("repo-lucky-btn");
    const select = $("repo-model-select");
    const resultsEl = $("repo-results");
    const hintEl = $("repo-source-hint");
    const dash = makeDashboardController("repo");
    const ref = { current: dash };
    loadExamples("repo", "repo-examples-grid", ref);
    let activeBtn = null;
    let abort = null;

    function setStatus(msg) {
      resultsEl.innerHTML = `<div class="results-status">${msg}</div>`;
    }

    function fmtNum(n) {
      if (n == null || !Number.isFinite(n)) return "";
      if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k";
      return String(n);
    }

    function fmtDate(iso) {
      if (!iso) return "";
      try { return new Date(iso).toISOString().slice(0, 10); } catch { return String(iso).slice(0, 10); }
    }

    function render(items, meta) {
      if (!items.length) { setStatus("No matching repositories. Try a different query, or paste an exact owner/repo."); return; }
      if (meta && meta.has_token === false) {
        hintEl.innerHTML = '<span class="warn">No GITHUB_TOKEN set — sharing the unauthenticated 60 req/h quota; expect occasional 403s.</span>';
      } else {
        hintEl.textContent = "";
      }
      resultsEl.innerHTML = "";
      items.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "result-item repo";
        btn.type = "button";
        const langChip = item.language ? `<span class="cat">${escapeHtmlGlobal(item.language)}</span>` : "";
        const stars = Number.isFinite(item.stars) ? `<span class="result-repo-stars">★ ${fmtNum(item.stars)}</span>` : "";
        btn.innerHTML = `
          <div class="result-title"></div>
          <div class="result-snippet"></div>
          <div class="result-cats">${langChip}</div>
          <div class="result-meta"></div>
        `;
        const titleEl = btn.querySelector(".result-title");
        titleEl.textContent = item.full_name || item.id || "";
        // Append the stars chip inline next to the title
        if (stars) {
          const span = document.createElement("span");
          span.innerHTML = stars;
          titleEl.appendChild(span.firstChild);
        }
        btn.querySelector(".result-snippet").textContent = item.description || "";
        const meta = [
          item.updated ? `updated ${fmtDate(item.updated)}` : "",
          Number.isFinite(item.forks) ? `${fmtNum(item.forks)} forks` : "",
        ].filter(Boolean).join(" · ");
        btn.querySelector(".result-meta").textContent = meta;
        btn.addEventListener("click", () => select_(item, btn));
        resultsEl.appendChild(btn);
      });
    }

    async function runSearch(q) {
      if (abort) abort.abort();
      if (!q) { resultsEl.innerHTML = ""; hintEl.textContent = ""; return; }
      abort = new AbortController();
      setStatus("Searching GitHub…");
      try {
        const res = await fetch(`/api/repo/search?q=${encodeURIComponent(q)}`, { signal: abort.signal });
        const data = await res.json();
        if (data.error) { setStatus(`Error: ${data.error}`); return; }
        render(data.results || [], data);
      } catch (err) { if (err.name !== "AbortError") setStatus(`Error: ${err.message}`); }
    }

    function select_(item, btn) {
      if (activeBtn) activeBtn.classList.remove("active");
      activeBtn = btn; btn.classList.add("active");
      const repoSlug = item.full_name || item.id;
      const headline = `Building 60-second explainer for ${repoSlug}`;
      const raceModels = isRaceModeOn() ? raceModelsFor("repo") : null;
      if (raceModels) {
        const labels = {};
        raceModels.forEach((m) => { labels[m] = modelLabel(m); });
        dash.runRace({
          url: "/api/repo/dashboard",
          body: { repo: repoSlug, models: raceModels },
          headline: `Racing ${raceModels.length} models on ${repoSlug}`,
          modelLabels: labels,
          title: repoSlug,
        });
      } else {
        const label = select.options[select.selectedIndex]?.textContent || "model";
        dash.run({
          url: "/api/repo/dashboard",
          body: { repo: repoSlug, model: select.value || undefined },
          headline,
          modelLabel: label,
          initialSub: `Fetching ${repoSlug} from GitHub (metadata, README, contributors, recent commits)…`,
          title: repoSlug,
        });
      }
    }

    const debounced = debounce((q) => runSearch(q), 320);
    input.addEventListener("input", (e) => debounced(e.target.value.trim()));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = resultsEl.querySelector(".result-item");
        if (first) first.click();
        else if (input.value.trim().includes("/")) {
          // Treat the typed text as a slug and jump straight in.
          select_({ full_name: input.value.trim() }, input);
        }
      }
    });
    lucky.addEventListener("click", () => {
      const t = REPO_LUCKY[Math.floor(Math.random() * REPO_LUCKY.length)];
      input.value = t;
      runSearch(t);
    });

    // Inline-link buttons in the empty state ("try facebook/react")
    document.querySelectorAll("#repo-dashboard-empty .inline-link[data-repo]").forEach((b) => {
      b.addEventListener("click", () => {
        input.value = b.dataset.repo;
        runSearch(b.dataset.repo);
      });
    });
  }

  // ---------------------------------------------------------------------
  // VisualArt (Met Museum + Rijksmuseum)
  // ---------------------------------------------------------------------
  const ART_LUCKY = [
    "Vermeer", "Rembrandt night watch", "Van Gogh sunflowers", "Hokusai wave",
    "Monet water lilies", "Caravaggio", "Klimt kiss", "Botticelli venus",
    "Hopper diner", "Goya", "Vermeer milkmaid", "ukiyo-e",
  ];

  function initArt() {
    const input = $("art-search-input");
    const lucky = $("art-lucky-btn");
    const select = $("art-model-select");
    const resultsEl = $("art-results");
    const dash = makeDashboardController("art");
    const ref = { current: dash };
    loadExamples("art", "art-examples-grid", ref);
    let activeBtn = null;
    let abort = null;

    function setStatus(msg) {
      resultsEl.innerHTML = `<div class="results-status">${msg}</div>`;
    }

    function render(items) {
      if (!items.length) {
        setStatus("No matching artworks. Try a different artist, subject, or period.");
        return;
      }
      resultsEl.innerHTML = "";
      items.forEach((item) => {
        const btn = document.createElement("button");
        btn.className = "result-item art";
        btn.type = "button";
        const thumb = item.image_thumb
          ? `<img class="result-art-thumb" src="${escapeHtmlGlobal(item.image_thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`
          : `<div class="result-art-thumb"></div>`;
        const dateStr = item.date || (item.year != null ? String(item.year) : "");
        btn.innerHTML = `
          ${thumb}
          <div class="result-art-body">
            <div class="result-title"></div>
            <div class="result-authors"></div>
            <div class="result-art-meta"></div>
          </div>
        `;
        btn.querySelector(".result-title").textContent = item.title || "Untitled";
        btn.querySelector(".result-authors").textContent = item.artist || "";
        btn.querySelector(".result-art-meta").textContent = [dateStr, item.medium].filter(Boolean).join(" · ");
        btn.addEventListener("click", () => select_(item, btn));
        resultsEl.appendChild(btn);
      });
    }

    async function runSearch(q) {
      if (abort) abort.abort();
      if (!q) { resultsEl.innerHTML = ""; return; }
      abort = new AbortController();
      setStatus("Searching the Met Museum…");
      try {
        const res = await fetch(`/api/art/search?q=${encodeURIComponent(q)}`, { signal: abort.signal });
        const data = await res.json();
        if (data.error) { setStatus(`Error: ${data.error}`); return; }
        render(data.results || []);
      } catch (err) { if (err.name !== "AbortError") setStatus(`Error: ${err.message}`); }
    }

    function select_(item, btn) {
      if (activeBtn) activeBtn.classList.remove("active");
      activeBtn = btn; btn.classList.add("active");
      const headline = `Composing wall card for "${(item.title || "Untitled").slice(0, 80)}"`;
      const raceModels = isRaceModeOn() ? raceModelsFor("art") : null;
      if (raceModels) {
        const labels = {};
        raceModels.forEach((m) => { labels[m] = modelLabel(m); });
        dash.runRace({
          url: "/api/art/dashboard",
          body: { object_id: item.id, models: raceModels },
          headline: `Racing ${raceModels.length} models on this artwork`,
          modelLabels: labels,
          title: item.title,
        });
      } else {
        const label = select.options[select.selectedIndex]?.textContent || "model";
        dash.run({
          url: "/api/art/dashboard",
          body: { object_id: item.id, model: select.value || undefined },
          headline,
          modelLabel: label,
          initialSub: `Fetching artwork from the Met and warming up ${label}…`,
          title: item.title,
        });
      }
    }

    const debounced = debounce((q) => runSearch(q), 320);
    input.addEventListener("input", (e) => debounced(e.target.value.trim()));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const first = resultsEl.querySelector(".result-item");
        if (first) first.click();
      }
    });
    lucky.addEventListener("click", () => {
      const t = ART_LUCKY[Math.floor(Math.random() * ART_LUCKY.length)];
      input.value = t;
      runSearch(t);
    });
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------
  loadModels().then(() => {
    bindRaceToggle("pedia");
    bindRaceToggle("scholar");
    bindRaceToggle("repo");
    bindRaceToggle("art");
  });
  loadEmailStatus().then(() => {
    document.querySelectorAll(".notify-form").forEach((f) => {
      f.classList.toggle("hidden", !emailStatus.enabled);
    });
  });
  initPedia();
  initScholar();
  initRepo();
  initArt();
  initLandingDemo();
  applyRoute();
})();
