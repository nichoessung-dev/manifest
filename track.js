/* Counts "Buy" clicks per agent (and the visitor's country, which the server adds). No cookies set, nothing personal sent:
   only which agent, which item, which page, and where this visit came from. The link itself is never changed, so
   affiliate codes work as before.
   Source (22 Oct 2026): worked out once per visit, on the landing page, and kept in this tab's sessionStorage: a tag on
   the link (utm_source, src, or a channel ?ref such as tt/yt/ig/pin), else the site the visitor came from (google, bing,
   chatgpt, reddit, tiktok ...), else the in-app browser (TikTok, Instagram), else "direct". Member referral codes are not
   stored here; they travel in the pc_ref cookie as before.
   Campaign (29 Oct 2026): the link's utm_campaign (max 40 chars) is kept next to the source in sessionStorage (pc.cmp) and
   sent as its own field, so it survives on ?ref= channel links and when "source.campaign" is longer than 23 chars. */
(function () {
  var AG = { "mycnbox.com": "mycnbox", "kakobuy.com": "kakobuy", "ikako.vip": "kakobuy", "oopbuy.com": "oopbuy", "lovegobuy.com": "lovegobuy", "sugargoo.com": "sugargoo" };
  var CHANNEL = { tt: "tiktok", tiktok: "tiktok", yt: "youtube", youtube: "youtube", ig: "instagram", instagram: "instagram", pin: "pinterest",
    pinterest: "pinterest", threads: "threads", dc: "discord", discord: "discord", tg: "telegram", telegram: "telegram", email: "email", x: "x" };
  var HOSTS = [[/(^|\.)gemini\.google\.com$/, "gemini"], [/(^|\.)copilot\.microsoft\.com$/, "copilot"], [/(^|\.)claude\.ai$/, "claude"],
    [/(^|\.)google\./, "google"], [/(^|\.)bing\.com$/, "bing"], [/(^|\.)duckduckgo\.com$/, "duckduckgo"], [/(^|\.)yahoo\./, "yahoo"],
    [/(^|\.)yandex\./, "yandex"], [/(^|\.)ecosia\.org$/, "ecosia"], [/(^|\.)(chatgpt\.com|openai\.com)$/, "chatgpt"], [/(^|\.)perplexity\.ai$/, "perplexity"],
    [/(^|\.)reddit\.com$/, "reddit"], [/(^|\.)tiktok\.com$/, "tiktok"], [/(^|\.)instagram\.com$/, "instagram"], [/(^|\.)(youtube\.com|youtu\.be)$/, "youtube"],
    [/(^|\.)(facebook\.com|fb\.com)$/, "facebook"], [/(^|\.)(x\.com|twitter\.com|t\.co)$/, "x"], [/(^|\.)(discord\.com|discordapp\.com|discord\.gg)$/, "discord"],
    [/(^|\.)(t\.me|telegram\.org)$/, "telegram"], [/(^|\.)pinterest\./, "pinterest"]];
  function clean(v) { return String(v || "").toLowerCase().replace(/[^a-z0-9_.-]/g, "").slice(0, 23); }
  function cmpClean(v) { return String(v || "").toLowerCase().replace(/[^a-z0-9_.-]/g, "").replace(/^[._-]+/, "").slice(0, 40); }
  var CMP = "";                                                   // this visit's campaign tag, set by source()
  function source() {
    try {
      var kept = sessionStorage.getItem("pc.src"); if (kept) { CMP = sessionStorage.getItem("pc.cmp") || ""; return kept; }
      var q = new URLSearchParams(location.search), v = q.get("utm_source") || q.get("src"), ref = clean(q.get("ref"));
      CMP = cmpClean(q.get("utm_campaign"));                      // whatever the source: also on ?ref= links, also past 23 chars
      if (v) { v = clean(v); var c = clean(q.get("utm_campaign")); if (c && (v + "." + c).length <= 23) v += "." + c; }
      else if (ref && CHANNEL[ref]) v = CHANNEL[ref];
      else if (ref) v = "member";                                 // a member's /r/ or ?ref= code: the code itself is in pc_ref
      if (!v && document.referrer) {
        var h = new URL(document.referrer).hostname.replace(/^www\./, "");
        if (h && h !== location.hostname.replace(/^www\./, "") && !/(^|\.)puroclassico\.com$/.test(h)) {
          v = "web"; for (var i = 0; i < HOSTS.length; i++) if (HOSTS[i][0].test(h)) { v = HOSTS[i][1]; break; }
        }
      }
      if (!v) { var ua = navigator.userAgent || ""; v = /musical_ly|BytedanceWebview|TikTok/i.test(ua) ? "tiktok" : /Instagram/i.test(ua) ? "instagram" : /FBAN|FBAV/i.test(ua) ? "facebook" : "direct"; }
      v = clean(v) || "direct"; sessionStorage.setItem("pc.src", v); if (CMP) sessionStorage.setItem("pc.cmp", CMP); return v;
    } catch (e) { return ""; }
  }
  var SRC = source();                                             // on the landing page, before any internal navigation
  // The catalogue app (homepage and hubs) puts /product/<id> in the address bar when it opens a find, so a click there
  // would look like one on the server-rendered product page. The app's clicks are sent as "/app" + the page it was
  // loaded on (/app/, /app/kakobuy-spreadsheet ...); real product pages keep their own path.
  var PAGE = location.pathname.slice(0, 110);
  function pageNow() { return document.getElementById("grid") ? "/app" + PAGE : location.pathname.slice(0, 120); }
  function agentOf(host) {
    host = (host || "").toLowerCase().replace(/^www\./, "");
    for (var d in AG) if (host === d || host.slice(-d.length - 1) === "." + d) return AG[d];
    return "";
  }
  function itemOf(href) {
    var u = href; try { u = decodeURIComponent(href); } catch (e) {}
    var m = u.match(/[?&]itemI[dD]=(\d{5,20})/) || u.match(/[?&]id=(\d{5,20})/) || u.match(/\/product\/[a-z0-9]+\/(\d{5,20})/i);
    if (m) return m[1];
    if (/[?&](memberId|inviteCode|invite_code|affcode)=|\/register\b|\/login\b|ikako\.vip\/r\//i.test(u)) return "";   // a sign-up link: its code is not an item
    m = u.match(/(\d{8,20})/);
    return m ? m[1] : "";
  }
  var last = { href: "", t: 0 };
  function send(a) {
    var agent = agentOf(a.hostname); if (!agent) return;
    var href = a.href || "", now = Date.now();
    if (href === last.href && now - last.t < 2000) return;        // a double tap opens one tab: count it once
    last = { href: href, t: now };
    var u = href; try { u = decodeURIComponent(href); } catch (e) {}
    var pl = /1688\.com|mallType=1688|platform=1688/i.test(u) ? "1688" : /taobao|tmall|mallType=taobao|platform=taobao/i.test(u) ? "taobao" : /weidian/i.test(u) ? "weidian" : "";
    var body = JSON.stringify({ a: agent, i: itemOf(href), pl: pl, pg: pageNow(), r: SRC, c: CMP });
    try {
      if (navigator.sendBeacon && navigator.sendBeacon("/api/click", new Blob([body], { type: "application/json" }))) return;
    } catch (e) {}
    try { fetch("/api/click", { method: "POST", body: body, headers: { "content-type": "application/json" }, keepalive: true }); } catch (e) {}
  }
  function onClick(ev) {
    if (ev.type === "auxclick" && ev.button !== 1) return;           // middle click opens a tab too
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
    if (a) send(a);
  }
  document.addEventListener("click", onClick, true);
  document.addEventListener("auxclick", onClick, true);
  // iOS Safari only shows :active press styles when the page listens for touches; this empty listener turns them on
  document.addEventListener("touchstart", function () {}, { passive: true });

  /* Site search counting (29 Oct 2026), so we learn what people look for and do not find. The catalogue app calls
     pcSearch.q(text, results, kind) after each search render, pcSearch.commit() on Enter or leaving the box, and
     pcSearch.open() when a find opens. A query counts once it has rested 1.5 s (or on Enter / leaving the box) and is
     sent to /api/search when the next query starts, when a find opens (opened = yes), or when the page is hidden.
     Sent: the query (lowercased, trimmed, 80 chars), the result count, opened yes/no, home/hub/product. No id, no
     cookie, nothing stored. Queries with 1 character, or that look like an email, a phone or long number or a link, are never sent. */
  var SQ = { cur: null, last: "", t: 0 };
  function sClean(raw) {
    var q = Array.from(String(raw == null ? "" : raw).toLowerCase().replace(/[\u0000-\u001f<>"`\\]/g, " ").replace(/\s+/g, " ").trim()).slice(0, 80).join("").trim();
    if (Array.from(q).length < 2 || /@|https?:|www\.|\.(com|net|org|cn|io|me|no)\b|\d{6,}/i.test(q)) return "";
    var runs = q.match(/[+(]?\d[\d\s().+-]*\d/g) || [];
    for (var i = 0; i < runs.length; i++) if (runs[i].replace(/\D/g, "").length >= 8) return "";
    return q;
  }
  function sSend() {
    var c = SQ.cur; SQ.cur = null; clearTimeout(SQ.t);
    if (!c || !c.done || (c.q === SQ.last && !c.o)) return;
    SQ.last = c.q; taste("q", c.q);
    var body = JSON.stringify({ q: c.q, n: c.n, o: c.o ? 1 : 0, k: c.k });
    try { if (navigator.sendBeacon && navigator.sendBeacon("/api/search", new Blob([body], { type: "application/json" }))) return; } catch (e) {}
    try { fetch("/api/search", { method: "POST", body: body, headers: { "content-type": "application/json" }, keepalive: true }); } catch (e) {}
  }
  window.pcSearch = {
    q: function (raw, n, kind) {
      var q = sClean(raw), c = SQ.cur;
      if (c && c.q === q) { c.n = +n || 0; return; }               // same query re-rendered (a filter, the currency): keep it
      if (c && c.done) sSend(); else { SQ.cur = null; clearTimeout(SQ.t); }   // a half-typed query is dropped
      if (!q) return;
      SQ.cur = c = { q: q, n: +n || 0, k: kind || "", done: false, o: false };
      SQ.t = setTimeout(function () { c.done = true; }, 1500);
    },
    commit: function () { if (SQ.cur) SQ.cur.done = true; },
    open: function () { var c = SQ.cur; if (!c) return; c.done = true; c.o = true; sSend(); }
  };
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") sSend(); });
  window.addEventListener("pagehide", sSend);

  /* Taste log (4 Nov 2026, widened 5 and 6 Nov 2026): the one taste memory that the Swipe Finds feed (/feed) and the
     spreadsheet's "For you" sort both learn from. Kept only in this browser (localStorage "pc.taste"), never sent anywhere.
     q = searches [[query, time]] (last 40); v = finds opened [[id, time, seconds looked at]] (last 150; the time counts only
     while the tab is visible, capped at 10 minutes); b = buy clicks [[id, time]] (last 60); c = QC photos looked at
     [[id, time]] (last 100); f = category and brand clicks, and filter and sort picks on the spreadsheet [["cat:Shoes",
     "brand:stone-island", "col:black", "pr:0-150" (CNY), "plat:taobao", "sort:low", time]] (last 80);
     h = finds the mouse rested on for over a second [[id, time]] (last 80); i = finds that were on screen for a second or
     more and not opened [[id, time, 1 if the list was filtered or searched]] (last 300; a weak "not for me"); n = no's [["uf:<id>" a find unsaved, "ni:Brand|type"
     "Not interested" and "nb:Brand" "Show less" in the feed, time, 1 when the feed wrote it]] (last 100);
     s = the feed's swipes [[id, time, 1 yes or 0 no, seconds on the card, 1 if its QC photos were looked at]] (last 300,
     written by feed.html). v: 2 marks this layout; readers skip what they do not know. */
  var CAP = { v: 150, q: 40, b: 60, c: 100, f: 80, h: 80, i: 300, n: 100, s: 300 };
  function tasteRW(fn) {
    try { var t = JSON.parse(localStorage.getItem("pc.taste") || "{}") || {}; if (fn(t) !== false) { t.ver = 2; localStorage.setItem("pc.taste", JSON.stringify(t)); } } catch (e) {}
  }
  function taste(kind, val) {
    if (!val || !CAP[kind] || kind === "s") return;
    tasteRW(function (t) {
      var a = Array.isArray(t[kind]) ? t[kind] : [], last = a[a.length - 1];
      if (last && last[0] === val && Date.now() - last[1] < (kind === "v" ? 2000 : 60000)) return false;   // the same thing twice in a row
      a.push(kind === "v" ? [val, Date.now(), 0] : [val, Date.now()]); t[kind] = a.slice(-CAP[kind]);
    });
  }
  window.pcTaste = { add: taste };                               // for the spreadsheet's filter and sort picks
  /* how long a find is looked at: from opening it until the address leaves it, the tab hides or the page closes */
  var open = null;                                               // { id, t0 (visible since), ms (visible time before) }
  function closeView() {
    if (!open) return;
    var ms = open.ms + (open.t0 ? Date.now() - open.t0 : 0), id = open.id; open = null;
    var sec = Math.min(600, Math.round(ms / 1000));
    if (sec < 1) return;
    tasteRW(function (t) {
      var a = Array.isArray(t.v) ? t.v : [];
      for (var i = a.length - 1; i >= 0 && i >= a.length - 5; i--) if (a[i][0] === id) { a[i][2] = Math.max(a[i][2] || 0, sec); return; }
      return false;
    });
  }
  function seen(path) {
    var m = /^\/product\/([^\/?#]+)/.exec(path || ""), id = "";
    if (m) { id = m[1]; try { id = decodeURIComponent(id); } catch (e) {} if (!/^[A-Za-z0-9_-]{4,40}$/.test(id)) id = ""; }
    if (open && open.id === id) return;
    closeView();
    if (id) { taste("v", id); open = { id: id, t0: document.hidden ? 0 : Date.now(), ms: 0 }; }
  }
  function curId() { return open ? open.id : ""; }
  seen(location.pathname);                                       // a product page, or the app opened on one
  ["pushState", "replaceState"].forEach(function (k) {           // the app opens a find by putting /product/<id> in the address bar
    var orig = history[k]; if (typeof orig !== "function") return;
    history[k] = function (st, title, url) {
      var r = orig.apply(this, arguments);
      try { if (url != null) seen(new URL(String(url), location.href).pathname); } catch (e) {}
      return r;
    };
  });
  window.addEventListener("popstate", function () { seen(location.pathname); });
  document.addEventListener("visibilitychange", function () {
    if (!open) return;
    if (document.hidden) { if (open.t0) { open.ms += Date.now() - open.t0; open.t0 = 0; } }
    else open.t0 = Date.now();
  });
  window.addEventListener("pagehide", closeView);
  /* buy clicks, QC photos, category and brand clicks */
  document.addEventListener("click", function (ev) {
    var el = ev.target && ev.target.closest ? ev.target : null; if (!el) return;
    var a = el.closest("a[href]");
    if (a && agentOf(a.hostname)) { taste("b", curId() || itemOf(a.href || "")); return; }
    var qc = el.closest('.qc-pill,.qcb,#qc-btns,#qc-chip,.qc-thumbs,#qc-thumbs,.qcs,[data-act="qc"],a[href$="#qc"],a[href*="#qc"]');
    if (qc) {
      var m = /\/product\/([^\/?#]+)/.exec((qc.getAttribute && qc.getAttribute("href")) || "");
      taste("c", m ? m[1] : curId()); return;
    }
    var fv = el.closest("[data-fav]");                           // a heart: unsaving is a no (saving is already in the saved list)
    if (fv) { if (fv.getAttribute("aria-pressed") === "true") taste("n", "uf:" + fv.getAttribute("data-fav")); return; }
    var c = el.closest("[data-cat]"), cat = c && c.getAttribute("data-cat");
    if (cat) { taste("f", "cat:" + cat); return; }
    if (a) { var bm = /^\/brand\/([a-z0-9-]+)/.exec(a.getAttribute("href") || ""); if (bm) taste("f", "brand:" + bm[1]); }
  }, true);
  /* finds on screen (the spreadsheet's cards and the server pages' cards, which all carry a heart with data-fav): one that
     stays at least 60% visible for a second and is not opened was looked at and passed over. Kept in memory and written
     every few seconds, at most once per find per page, and never while a find is open on top. */
  function cardId(el) { var f = el && el.querySelector && el.querySelector("[data-fav]"); return f ? f.getAttribute("data-fav") || "" : ""; }
  var IMP = [], impDone = {}, impT = {}, io = null, watched = typeof WeakSet === "function" ? new WeakSet() : null;
  function impFlush() {
    if (!IMP.length) return;
    var add = IMP; IMP = [];
    tasteRW(function (t) { var a = Array.isArray(t.i) ? t.i : []; t.i = a.concat(add).slice(-CAP.i); });
  }
  /* the third field is 1 when the list was already narrowed to the visitor's pick (a filter, a search, a brand or category
     page): every find there shares what they picked, so passing one says little about its brand or colour */
  function impCtx() { var c = window.pcTasteCtx; return c != null ? (c ? 1 : 0) : location.pathname === "/" ? 0 : 1; }
  function impSeen(id) { if (!id || impDone[id] || curId()) return; impDone[id] = 1; IMP.push([id, Date.now(), impCtx()]); }   // not while a find is open over the grid
  if (window.IntersectionObserver && watched) {
    io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        var id = cardId(e.target); if (!id) return;
        if (e.isIntersecting && e.intersectionRatio >= 0.6 && !document.hidden) { if (!impT[id]) impT[id] = setTimeout(function () { impT[id] = 0; impSeen(id); }, 1000); }
        else if (impT[id]) { clearTimeout(impT[id]); impT[id] = 0; }
      });
    }, { threshold: [0, 0.6] });
    setInterval(function () {
      if (document.hidden) return;
      var cs = document.querySelectorAll(".card");
      for (var i = 0; i < cs.length; i++) if (!watched.has(cs[i]) && cardId(cs[i])) { watched.add(cs[i]); io.observe(cs[i]); }
      impFlush();
    }, 2500);
  }
  window.addEventListener("pagehide", impFlush);
  document.addEventListener("visibilitychange", function () { if (document.hidden) impFlush(); });
  /* the mouse resting on a find for over a second (desktop only; a touch is a tap, not a hover) */
  var hov = { el: null, t: 0 };
  document.addEventListener("pointerover", function (e) {
    if (e.pointerType !== "mouse") return;
    var c = e.target && e.target.closest ? e.target.closest(".card") : null;
    if (c === hov.el) return;
    clearTimeout(hov.t); hov.el = c;
    if (c) hov.t = setTimeout(function () { if (hov.el === c) taste("h", cardId(c)); }, 1200);
  }, { passive: true });
})();
