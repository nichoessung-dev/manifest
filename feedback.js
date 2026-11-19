/* Feedback pop-up (owner, 19 Nov 2026: "only give feedback to people who has spendt alot of time on the spreadsheet
   (top 5-10%)"). Counts this browser's active time on the site (tab visible and the visitor did something in the last
   minute), in localStorage "pc.fb". Only heavy users are asked: at least 30 active minutes in all, or 15 minutes over 3 or
   more different days. Asked once; "Not now" waits 30 days, a sent answer is never asked again. Sends to /api/feedback. */
(function () {
  "use strict";
  var K = "pc.fb", TICK = 15, NEED_MIN = 30, NEED_MIN_DAYS = 15, NEED_DAYS = 3, WAIT_SESSION = 45;
  if (/^\/(partner|admin|stats)/.test(location.pathname)) return;
  var st; try { st = JSON.parse(localStorage.getItem(K) || "{}") || {}; } catch (e) { return; }
  st.sec = +st.sec || 0; st.days = Array.isArray(st.days) ? st.days : [];
  var last = Date.now(), here = 0, shown = false;
  function save() { try { localStorage.setItem(K, JSON.stringify(st)); } catch (e) {} }
  function today() { return new Date().toISOString().slice(0, 10); }
  ["pointerdown", "keydown", "scroll", "touchstart", "mousemove", "wheel"].forEach(function (e) {
    addEventListener(e, function () { last = Date.now(); }, { passive: true, capture: true });
  });
  function heavy() { var m = st.sec / 60; return m >= NEED_MIN || (m >= NEED_MIN_DAYS && st.days.length >= NEED_DAYS); }
  function may() { return !st.done && !(st.until && Date.now() < st.until); }
  setInterval(function () {
    if (document.visibilityState !== "visible" || Date.now() - last > 60000) return;
    st.sec += TICK; here += TICK;
    var d = today(); if (st.days[st.days.length - 1] !== d) { st.days.push(d); st.days = st.days.slice(-60); }
    save();
    if (!shown && here >= WAIT_SESSION && heavy() && may() && !document.querySelector("dialog[open],.pcs-ov:not([hidden])")) { shown = true; show(); }
  }, TICK * 1000);

  function show() {
    var css = ".pcfb{position:fixed;right:16px;bottom:16px;z-index:9000;width:min(360px,calc(100vw - 32px));background:var(--surface,#fff);color:var(--ink,#111);" +
      "border:1px solid var(--line-2,rgba(0,0,0,.12));border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,.18);padding:18px;font-size:14px;line-height:1.45;font-family:inherit;" +
      "transform:translateY(12px);opacity:0;transition:transform .25s ease,opacity .25s ease}.pcfb.on{transform:none;opacity:1}" +
      ".pcfb h3{margin:0 28px 4px 0;font-size:16px;font-weight:600}.pcfb p{margin:0 0 12px;color:var(--muted,#666)}" +
      ".pcfb .x{position:absolute;top:10px;right:10px;width:30px;height:30px;border:0;border-radius:50%;background:transparent;color:inherit;cursor:pointer;font-size:18px;line-height:1}" +
      ".pcfb .x:hover{background:var(--surface-2,rgba(0,0,0,.06))}.pcfb .rt{display:flex;gap:6px;margin:0 0 12px}" +
      ".pcfb .rt button{flex:1;height:40px;border-radius:12px;border:1px solid var(--line-2,rgba(0,0,0,.12));background:var(--surface-2,transparent);color:inherit;font-weight:600;font-size:15px;font-family:inherit;cursor:pointer}" +
      ".pcfb .rt button.on{background:var(--ink,#111);color:var(--bg,#fff);border-color:transparent}" +
      ".pcfb textarea,.pcfb input{width:100%;box-sizing:border-box;border:1px solid var(--line-2,rgba(0,0,0,.12));border-radius:12px;background:var(--bg,transparent);color:inherit;font-family:inherit;font-size:14px;padding:10px 12px;margin:0 0 8px}" +
      ".pcfb textarea{min-height:84px;resize:vertical}.pcfb .row{display:flex;gap:8px;justify-content:flex-end;margin-top:4px}" +
      ".pcfb .b{height:38px;padding:0 16px;border-radius:999px;border:0;font-weight:600;font-size:14px;font-family:inherit;cursor:pointer}.pcfb .b1{background:var(--ink,#111);color:var(--bg,#fff)}" +
      ".pcfb .b2{background:transparent;color:var(--muted,#666)}.pcfb .lbl{display:flex;justify-content:space-between;font-size:12px;color:var(--muted,#666);margin:-6px 0 12px}";
    var s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    var b = document.createElement("div"); b.className = "pcfb"; b.setAttribute("role", "dialog"); b.setAttribute("aria-label", "Feedback");
    b.innerHTML = '<button class="x" type="button" aria-label="Close">×</button>' +
      "<h3>You're one of our most active members</h3><p>Got 30 seconds? Tell us what would make Puro Classico better for you.</p>" +
      '<div class="rt" role="group" aria-label="How useful is the spreadsheet for you?">' + [1, 2, 3, 4, 5].map(function (n) { return '<button type="button" data-r="' + n + '">' + n + "</button>"; }).join("") + "</div>" +
      '<div class="lbl"><span>Not useful</span><span>Love it</span></div>' +
      '<textarea maxlength="1000" placeholder="What should we add, fix or change?"></textarea>' +
      '<input type="email" maxlength="200" placeholder="Email (optional, if you want a reply)" autocomplete="email">' +
      '<div class="row"><button class="b b2" type="button" data-no>Not now</button><button class="b b1" type="button" data-send>Send</button></div>';
    document.body.appendChild(b);
    requestAnimationFrame(function () { b.classList.add("on"); });
    var r = 0;
    b.querySelectorAll("[data-r]").forEach(function (x) {
      x.addEventListener("click", function () { r = +x.dataset.r; b.querySelectorAll("[data-r]").forEach(function (y) { y.classList.toggle("on", y === x); }); });
    });
    function close(snooze) {
      if (snooze) { st.until = Date.now() + 30 * 864e5; save(); }
      b.classList.remove("on"); setTimeout(function () { b.remove(); }, 300);
    }
    b.querySelector(".x").onclick = function () { close(true); };
    b.querySelector("[data-no]").onclick = function () { close(true); };
    b.querySelector("[data-send]").onclick = function () {
      var text = b.querySelector("textarea").value.trim(), email = b.querySelector("input").value.trim();
      if (!r && !text) { b.querySelector("textarea").focus(); return; }
      var body = JSON.stringify({ r: r, text: text, email: email, page: location.pathname, min: Math.round(st.sec / 60), days: st.days.length, lang: document.documentElement.lang || "" });
      try { fetch("/api/feedback", { method: "POST", headers: { "content-type": "application/json" }, body: body, keepalive: true }); } catch (e) {}
      st.done = 1; save();
      b.innerHTML = "<h3>Thank you!</h3><p style=\"margin:0\">We read every message.</p>";
      setTimeout(function () { close(false); }, 2200);
    };
    addEventListener("keydown", function (e) { if (e.key === "Escape" && document.body.contains(b)) close(true); });
  }
})();
