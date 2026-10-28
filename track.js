/* Counts "Buy" clicks per agent (and the visitor's country, which the server adds). No cookies set, nothing personal sent:
   only which agent, which item, which page, and where this visit came from. The link itself is never changed, so
   affiliate codes work as before.
   Source (22 Oct 2026): worked out once per visit, on the landing page, and kept in this tab's sessionStorage: a tag on
   the link (utm_source, src, or a channel ?ref such as tt/yt/ig/pin), else the site the visitor came from (google, bing,
   chatgpt, reddit, tiktok ...), else the in-app browser (TikTok, Instagram), else "direct". Member referral codes are not
   stored here; they travel in the pc_ref cookie as before. */
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
  function source() {
    try {
      var kept = sessionStorage.getItem("pc.src"); if (kept) return kept;
      var q = new URLSearchParams(location.search), v = q.get("utm_source") || q.get("src"), ref = clean(q.get("ref"));
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
      v = clean(v) || "direct"; sessionStorage.setItem("pc.src", v); return v;
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
    var body = JSON.stringify({ a: agent, i: itemOf(href), pl: pl, pg: pageNow(), r: SRC });
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
})();
