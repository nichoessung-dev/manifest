/* Puro Classico shopping assistant widget (Nov 2026). Included on every page as <script src="/chat.js?v=1" defer>.
   A round "Ask" button bottom right opens a chat panel (a full-screen sheet on phones, 380 px on desktop) that talks to
   POST /api/chat (functions/api/chat.js, newline-delimited JSON). No libraries. The conversation lives in sessionStorage
   only ("pc.chat.v1") and is gone when the tab closes. Hidden on /feed and /admin, and when /api/chat answers 503
   (no API key set). Colours come from the page's own tokens (ds.css on server pages, the app's in index.html), so light,
   dark and system follow html[data-theme] and prefers-color-scheme. */
(function () {
  "use strict";
  var D = document, W = window;
  if (W.__pcChat) return; W.__pcChat = 1;
  if (/^\/(feed|admin)(\.html)?\/?$/.test(location.pathname)) return;

  var KEY = "pc.chat.v1", OKKEY = "pc.chat.ok", MAXLEN = 1000, MAXKEEP = 30;
  var ss = { get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
             set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} } };
  var state = { msgs: [], open: false };
  try { var saved = JSON.parse(ss.get(KEY) || "null"); if (saved && Array.isArray(saved.msgs)) state = { msgs: saved.msgs.slice(-MAXKEEP), open: !!saved.open }; } catch (e) {}
  var save = function () { ss.set(KEY, JSON.stringify({ msgs: state.msgs.slice(-MAXKEEP), open: state.open })); };

  var SUGGEST = ["Ralph Lauren knit under $40", "How do I order with MyCNBox?", "What are QC photos?", "Do Chinese sizes run small?"];
  var ICON_CHAT = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 5h16v11H9l-5 4Z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/></svg>';
  var ICON_X = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M18 6 6 18M6 6l12 12"/></svg>';
  var ICON_SEND = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  var ICON_NEW = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>';

  var CSS =
    ".pcc{--pc-bg:var(--surface,var(--bg,#fff));--pc-ink:var(--ink,#0a0a0a);--pc-mut:var(--muted,#6b6b6b);--pc-line:var(--line,#e5e5e5);--pc-s2:var(--surface-2,var(--well,#f5f5f5));--pc-fill:var(--fill,#171717);--pc-fink:var(--fill-ink,#fafafa);" +
    "font-family:var(--f-body,var(--font,\"Instrument Sans\",Inter,-apple-system,BlinkMacSystemFont,\"Segoe UI\",system-ui,sans-serif));font-size:15px;line-height:1.5;color:var(--pc-ink);-webkit-font-smoothing:antialiased}" +
    ".pcc *,.pcc *::before,.pcc *::after{box-sizing:border-box}" +
    ".pcc-fab{position:fixed;right:max(16px,env(safe-area-inset-right,0px));bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:70;display:inline-flex;align-items:center;gap:8px;height:48px;padding:0 18px 0 15px;border:1px solid var(--pc-line);border-radius:999px;background:var(--pc-fill);color:var(--pc-fink);font-family:inherit;font-size:15px;font-weight:600;line-height:1;cursor:pointer;box-shadow:0 10px 15px -3px rgba(0,0,0,.15),0 4px 6px -4px rgba(0,0,0,.15);transition:transform .15s,bottom .25s cubic-bezier(.22,1,.36,1);-webkit-tap-highlight-color:transparent;touch-action:manipulation}" +
    ".pcc-fab:active{transform:scale(.96)}.pcc-fab:focus-visible{outline:2px solid var(--pc-ink);outline-offset:3px}" +
    "@media (max-width:900px){body.has-buybar .pcc-fab,body:has(.buybar.on) .pcc-fab{bottom:calc(84px + env(safe-area-inset-bottom,0px))}}" +
    "@media (max-width:859px){body:has(.drawer.open .d-buybar.on) .pcc-fab{bottom:calc(84px + env(safe-area-inset-bottom,0px))}}" +
    ".pcc-open .pcc-fab{visibility:hidden}" +
    ".pcc-panel{position:fixed;right:16px;bottom:16px;z-index:1001;display:flex;flex-direction:column;width:380px;height:min(640px,calc(100vh - 32px));height:min(640px,calc(100dvh - 32px));background:var(--pc-bg);color:var(--pc-ink);border:1px solid var(--pc-line);border-radius:16px;box-shadow:0 20px 40px -8px rgba(0,0,0,.25);overflow:hidden}" +
    ".pcc-panel[hidden]{display:none}" +
    "@media (max-width:640px){.pcc-panel{inset:0;width:auto;height:100%;border:0;border-radius:0;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) 0 env(safe-area-inset-left,0px)}}" +
    "@media (prefers-reduced-motion:no-preference){.pcc-panel{animation:pcc-in .22s cubic-bezier(.22,1,.36,1)}@keyframes pcc-in{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}}" +
    ".pcc-hd{display:flex;align-items:center;gap:8px;padding:12px 12px 12px 18px;border-bottom:1px solid var(--pc-line)}" +
    ".pcc-ttl{flex:1;min-width:0}.pcc-ttl b{display:block;font-size:16px;font-weight:600;letter-spacing:-.01em}.pcc-ttl span{display:block;font-size:12.5px;color:var(--pc-mut)}" +
    ".pcc-ib{display:inline-grid;place-items:center;width:40px;height:40px;border:0;border-radius:999px;background:transparent;color:var(--pc-ink);cursor:pointer}.pcc-ib:hover{background:var(--pc-s2)}.pcc-ib:focus-visible{outline:2px solid var(--pc-ink);outline-offset:1px}" +
    ".pcc-log{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:16px;display:flex;flex-direction:column;gap:12px}" +
    ".pcc-m{flex-shrink:0;max-width:88%;padding:10px 14px;border-radius:18px;overflow-wrap:anywhere;white-space:normal}" +
    ".pcc-m.u{align-self:flex-end;background:var(--pc-fill);color:var(--pc-fink);border-bottom-right-radius:6px}" +
    ".pcc-m.a{align-self:flex-start;background:var(--pc-s2);border-bottom-left-radius:6px}" +
    ".pcc-m.err{background:transparent;border:1px solid var(--pc-line);color:var(--pc-mut)}" +
    ".pcc-m a{color:inherit;text-decoration:underline;text-underline-offset:3px;font-weight:500}" +
    ".pcc-m p{margin:0}.pcc-m p+p{margin-top:8px}" +
    ".pcc-dots{display:inline-flex;gap:4px;padding:4px 0}.pcc-dots i{width:6px;height:6px;border-radius:50%;background:var(--pc-mut);opacity:.4;animation:pcc-b 1s infinite}.pcc-dots i:nth-child(2){animation-delay:.15s}.pcc-dots i:nth-child(3){animation-delay:.3s}@keyframes pcc-b{50%{opacity:1}}" +
    ".pcc-cards{flex-shrink:0;display:flex;gap:8px;overflow-x:auto;align-self:stretch;padding:2px 0 4px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}" +
    ".pcc-card{flex:0 0 132px;scroll-snap-align:start;display:flex;flex-direction:column;border:1px solid var(--pc-line);border-radius:12px;overflow:hidden;background:var(--pc-bg);color:var(--pc-ink);text-decoration:none}" +
    ".pcc-card:hover{border-color:var(--pc-mut)}.pcc-card:focus-visible{outline:2px solid var(--pc-ink);outline-offset:1px}" +
    ".pcc-card img{display:block;width:100%;aspect-ratio:1;object-fit:cover;background:var(--pc-s2)}" +
    ".pcc-card span{display:block;padding:8px 10px 10px;font-size:12.5px;line-height:1.35}" +
    ".pcc-card em{font-style:normal;color:var(--pc-mut);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    ".pcc-card strong{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-weight:500;margin:1px 0 4px}" +
    ".pcc-card small{font-size:12px;font-weight:600;font-variant-numeric:tabular-nums}.pcc-card small i{font-style:normal;font-weight:400;color:var(--pc-mut);margin-left:6px}" +
    ".pcc-sug{flex-shrink:0;display:flex;flex-wrap:wrap;gap:8px}.pcc-sug button{border:1px solid var(--pc-line);background:var(--pc-bg);color:var(--pc-ink);border-radius:999px;padding:8px 14px;font:inherit;font-size:13.5px;cursor:pointer;text-align:left}.pcc-sug button:hover{background:var(--pc-s2)}" +
    ".pcc-ft{border-top:1px solid var(--pc-line);padding:10px 12px calc(10px + env(safe-area-inset-bottom,0px))}" +
    ".pcc-form{display:flex;align-items:flex-end;gap:8px;border:1px solid var(--pc-line);border-radius:24px;padding:5px 5px 5px 16px;background:var(--pc-bg)}" +
    ".pcc-form:focus-within{border-color:var(--pc-mut)}" +
    ".pcc-in{flex:1;min-width:0;border:0!important;outline:0!important;box-shadow:none!important;background:transparent!important;color:var(--pc-ink);font:inherit;font-size:16px;line-height:1.4;padding:7px 0!important;resize:none;max-height:120px;border-radius:0}" +
    ".pcc-send{flex:0 0 auto;display:inline-grid;place-items:center;width:36px;height:36px;border:0;border-radius:999px;background:var(--pc-fill);color:var(--pc-fink);cursor:pointer}.pcc-send:disabled{opacity:.35;cursor:default}.pcc-send:focus-visible{outline:2px solid var(--pc-ink);outline-offset:2px}" +
    ".pcc-note{margin:8px 4px 0;font-size:11.5px;line-height:1.4;color:var(--pc-mut)}.pcc-note a{color:inherit}" +
    ".pcc-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}" +
    "html.pcc-lock,html.pcc-lock body{overflow:hidden}";

  // ---------------------------------------------------------------- markdown-lite (escape first, then a few safe patterns)
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function safeUrl(u) {
    u = String(u || "").replace(/&amp;/g, "&");
    if (/^\/(?!\/)/.test(u)) return u;
    if (/^https?:\/\//i.test(u)) return u;
    return "";
  }
  function link(text, url) {
    var u = safeUrl(url); if (!u) return text;
    var own = u.charAt(0) === "/" || /^https?:\/\/(www\.)?puroclassico\.com(\/|$)/i.test(u);
    if (own) u = u.replace(/^https?:\/\/(www\.)?puroclassico\.com/i, "") || "/";
    return '<a href="' + esc(u) + '"' + (own ? "" : ' target="_blank" rel="noopener nofollow"') + ">" + text + "</a>";
  }
  function md(src) {
    var h = esc(src);
    var slots = [];
    h = h.replace(/\[([^\]\n]{1,200})\]\(([^)\s]{1,500})\)/g, function (_, t, u) { slots.push(link(t, u)); return "\u0000" + (slots.length - 1) + "\u0000"; });
    h = h.replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,!?:;'"])/g, function (_, pre, u) { slots.push(link(u.replace(/^https?:\/\/(www\.)?/i, ""), u)); return pre + "\u0000" + (slots.length - 1) + "\u0000"; });
    h = h.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/\u0000(\d+)\u0000/g, function (_, i) { return slots[+i]; });
    return h.split(/\n{2,}/).map(function (p) {
      return "<p>" + p.split("\n").map(function (l) { return l.replace(/^\s*[-*]\s+/, "• ").replace(/^#{1,4}\s+/, ""); }).join("<br>") + "</p>";
    }).join("");
  }

  // ---------------------------------------------------------------- DOM
  var root, fab, panel, log, input, send, busy = false, lastFocus = null;
  function el(tag, cls, html) { var e = D.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }

  function build() {
    var st = el("style"); st.textContent = CSS; D.head.appendChild(st);
    root = el("div", "pcc");
    fab = el("button", "pcc-fab", ICON_CHAT + "<span>Ask</span>");
    fab.type = "button"; fab.setAttribute("aria-label", "Ask the shopping assistant"); fab.setAttribute("aria-haspopup", "dialog"); fab.setAttribute("aria-expanded", "false"); fab.setAttribute("aria-controls", "pcc-panel");
    panel = el("div", "pcc-panel"); panel.id = "pcc-panel"; panel.hidden = true;
    panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true"); panel.setAttribute("aria-labelledby", "pcc-title");
    panel.innerHTML =
      '<div class="pcc-hd"><div class="pcc-ttl"><b id="pcc-title">Ask Puro Classico</b><span>AI shopping assistant</span></div>' +
      '<button type="button" class="pcc-ib" data-new aria-label="Start a new chat" title="New chat">' + ICON_NEW + '</button>' +
      '<button type="button" class="pcc-ib" data-close aria-label="Close chat">' + ICON_X + '</button></div>' +
      '<div class="pcc-log" role="log" aria-live="polite" aria-relevant="additions" tabindex="-1"></div>' +
      '<div class="pcc-ft"><form class="pcc-form"><label class="pcc-sr" for="pcc-in">Your message</label>' +
      '<textarea class="pcc-in" id="pcc-in" rows="1" maxlength="' + MAXLEN + '" placeholder="Ask about a find, sizing, shipping..." enterkeyhint="send" autocomplete="off"></textarea>' +
      '<button type="submit" class="pcc-send" aria-label="Send" disabled>' + ICON_SEND + '</button></form>' +
      '<p class="pcc-note">AI answers can be wrong; check the product page before you buy. Messages go to Anthropic to write the answer and are not stored by us. <a href="/privacy">Privacy</a></p></div>';
    root.appendChild(fab); root.appendChild(panel); D.body.appendChild(root);
    log = panel.querySelector(".pcc-log"); input = panel.querySelector(".pcc-in"); send = panel.querySelector(".pcc-send");

    fab.addEventListener("click", function () { setOpen(true); });
    panel.querySelector("[data-close]").addEventListener("click", function () { setOpen(false); });
    panel.querySelector("[data-new]").addEventListener("click", function () { if (busy) return; state.msgs = []; save(); render(); input.focus(); });
    panel.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
    input.addEventListener("input", function () { grow(); send.disabled = busy || !input.value.trim(); });
    input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); } });
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.stopPropagation(); setOpen(false); return; }
      if (e.key !== "Tab") return;
      var f = [].filter.call(panel.querySelectorAll("button,textarea,a[href]"), function (x) { return !x.disabled && x.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && D.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && D.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    W.matchMedia && W.matchMedia("(max-width:640px)").addEventListener && W.matchMedia("(max-width:640px)").addEventListener("change", lock);
    render();
    if (state.open) setOpen(true, true);
  }
  function grow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 120) + "px"; }
  function lock() { D.documentElement.classList.toggle("pcc-lock", state.open && W.matchMedia && W.matchMedia("(max-width:640px)").matches); }
  function setOpen(on, quiet) {
    state.open = on; save();
    panel.hidden = !on; fab.setAttribute("aria-expanded", on ? "true" : "false");
    root.classList.toggle("pcc-open", on); lock();
    if (on) { lastFocus = quiet ? null : D.activeElement; scroll(); if (!quiet || !W.matchMedia("(max-width:640px)").matches) setTimeout(function () { input.focus(); }, 30); }
    else if (!quiet) (lastFocus && lastFocus.focus ? lastFocus : fab).focus();
  }
  function scroll() { log.scrollTop = log.scrollHeight; }

  function bubble(m) {
    var b = el("div", "pcc-m " + (m.role === "user" ? "u" : "a") + (m.err ? " err" : ""));
    if (m.role === "user") b.textContent = m.content; else b.innerHTML = m.content ? md(m.content) : '<span class="pcc-dots" aria-label="Writing"><i></i><i></i><i></i></span>';
    return b;
  }
  function cards(list) {
    var row = el("div", "pcc-cards"); row.setAttribute("role", "list"); row.setAttribute("aria-label", "Finds");
    list.forEach(function (f) {
      var a = el("a", "pcc-card"); a.href = safeUrl(f.url) || "/"; a.setAttribute("role", "listitem");
      var price = f.price ? "$" + f.price : "Ask seller";
      a.innerHTML = (f.img ? '<img src="' + esc(f.img) + '" alt="" loading="lazy" decoding="async" width="132" height="132">' : "") +
        "<span><em>" + esc(f.brand || "") + "</em><strong>" + esc(f.title) + "</strong><small>" + esc(price) + (f.qc ? "<i>" + esc(f.qc) + " QC</i>" : "") + "</small></span>";
      var img = a.querySelector("img"); if (img) img.addEventListener("error", function () { img.remove(); });
      a.setAttribute("aria-label", f.title + ", " + price + (f.qc ? ", " + f.qc + " QC photos" : ""));
      row.appendChild(a);
    });
    return row;
  }
  function render() {
    log.innerHTML = "";
    if (!state.msgs.length) {
      log.appendChild(bubble({ role: "assistant", content: "Hi! I can find reps in the catalogue and explain ordering through an agent, QC photos, sizing and shipping. What are you looking for?" }));
      var sug = el("div", "pcc-sug");
      SUGGEST.forEach(function (s) { var b = el("button"); b.type = "button"; b.textContent = s; b.addEventListener("click", function () { ask(s); }); sug.appendChild(b); });
      log.appendChild(sug);
    }
    state.msgs.forEach(function (m) { log.appendChild(bubble(m)); if (m.finds && m.finds.length) log.appendChild(cards(m.finds)); });
    scroll();
  }

  // ---------------------------------------------------------------- talking to /api/chat
  function hide() { ss.set(OKKEY, "0"); if (root) { D.documentElement.classList.remove("pcc-lock"); root.remove(); } }
  function ask(text) {
    text = String(text || "").trim().slice(0, MAXLEN);
    if (!text || busy) return;
    busy = true; send.disabled = true; input.value = ""; grow();
    var history = state.msgs.filter(function (m) { return !m.err && m.content; }).map(function (m) { return { role: m.role, content: m.content.slice(0, MAXLEN) }; });
    history.push({ role: "user", content: text });
    state.msgs.push({ role: "user", content: text });
    var me = { role: "assistant", content: "" };
    state.msgs.push(me); render(); save();
    log.setAttribute("aria-busy", "true");
    var node = log.lastChild;
    var paint = function () { var n = bubble(me); log.replaceChild(n, node); node = n; scroll(); };
    var fail = function (msg) { me.content = msg || "Sorry, something went wrong. Please try again."; me.err = true; paint(); };
    var finish = function () { busy = false; send.disabled = !input.value.trim(); log.setAttribute("aria-busy", "false"); if (!me.content) fail(); save(); };
    fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ messages: history.slice(-10) }), credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 503) { hide(); return; }
        if (!r.ok || !r.body || !r.body.getReader) return r.json().then(function (j) { fail(j && j.error); }, function () { fail(); });
        var reader = r.body.getReader(), dec = new TextDecoder(), buf = "";
        var line = function (s) {
          if (!s.trim()) return;
          var o; try { o = JSON.parse(s); } catch (e) { return; }
          if (o.t === "text") { me.content += o.v; paint(); }
          else if (o.t === "finds" && Array.isArray(o.v)) { me.finds = o.v.slice(0, 6); log.appendChild(cards(me.finds)); scroll(); }
          else if (o.t === "error") { fail(o.v); }
        };
        var pump = function () {
          return reader.read().then(function (x) {
            if (x.done) { line(buf); return; }
            buf += dec.decode(x.value, { stream: true });
            var i; while ((i = buf.indexOf("\n")) >= 0) { line(buf.slice(0, i)); buf = buf.slice(i + 1); }
            return pump();
          });
        };
        return pump();
      })
      .catch(function () { fail("The connection dropped. Please try again."); })
      .then(finish, finish);
  }

  // ---------------------------------------------------------------- start: only when the assistant is set up
  function start() {
    var ok = ss.get(OKKEY);
    if (ok === "0") return;
    if (ok === "1") return build();
    fetch("/api/chat", { method: "GET", credentials: "same-origin" }).then(function (r) {
      if (r.ok) { ss.set(OKKEY, "1"); build(); } else if (r.status === 503) ss.set(OKKEY, "0");
    }).catch(function () {});
  }
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start); else start();
})();
