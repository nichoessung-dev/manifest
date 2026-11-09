/* Puro Classico shopping assistant widget (Nov 2026, v3). Included on every page as <script src="/chat.js?v=3" defer>.
   A round "Ask" button bottom right opens a chat panel (a full-screen sheet on phones, 380 px on desktop) that talks to
   POST /api/chat (functions/api/chat.js, newline-delimited JSON). No libraries. The conversation lives in sessionStorage
   only ("pc.chat.v1") and is gone when the tab closes. Hidden on /feed and /admin, and when /api/chat answers 503
   (no API key set). Colours come from the page's own tokens (ds.css on server pages, the app's in index.html), so light,
   dark and system follow html[data-theme] and prefers-color-scheme.
   v2: the panel eases in and out (transform + opacity, interruptible, plain fade with reduced motion); answers stream in
   paragraph by paragraph, painted once per frame, and the log follows only while the reader is at the bottom; cards for
   the finds appear as soon as the search returns, with the price in the visitor's currency (manifest.state.cur) and a
   Buy button for their agent (manifest.state.agent); Stop while it writes, Try again after an error; the sheet follows
   the on-screen keyboard (visualViewport). The request carries the visitor's currency, agent and the find on screen.
   v3: messenger look (logo and status line in the header, a "Today" divider, the greeting as stacked bubbles, suggestions
   as right-aligned outline pills, a grey pill input with a round send button). On the app (index.html: openDetail and
   BY_ID) a find in the chat opens the app's own product view; the chat steps aside and comes back when that view closes.
   Everywhere else, and with cmd/ctrl/shift/middle click, the links stay ordinary links. */
(function () {
  "use strict";
  var D = document, W = window;
  if (W.__pcChat) return; W.__pcChat = 1;
  if (/^\/(feed|admin)(\.html)?\/?$/.test(location.pathname)) return;

  var KEY = "pc.chat.v1", OKKEY = "pc.chat.ok", MAXLEN = 1000, MAXKEEP = 30;
  var ss = { get: function (k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
             set: function (k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} } };
  // sid: a random id for one conversation (a new one with "New chat"), so saved chats can be read as whole conversations.
  // Not linked to the visitor: no account, no IP.
  var newSid = function () { var a = ""; try { var u = new Uint8Array(9); crypto.getRandomValues(u); for (var i = 0; i < u.length; i++) a += (u[i] % 36).toString(36); } catch (e) { a = Math.random().toString(36).slice(2, 11); } return a; };
  var state = { msgs: [], open: false, sid: newSid() };
  try { var saved = JSON.parse(ss.get(KEY) || "null"); if (saved && Array.isArray(saved.msgs)) state = { msgs: saved.msgs.slice(-MAXKEEP), open: !!saved.open, sid: /^[a-z0-9]{6,16}$/.test(saved.sid || "") ? saved.sid : newSid() }; } catch (e) {}
  // An answer that was still being written when the page changed stays as far as it got.
  state.msgs.forEach(function (m) { if (m.pending) { delete m.pending; m.retry = true; if (m.content) m.note = "Stopped"; else { m.content = "Stopped."; m.err = true; } } });
  var save = function () { ss.set(KEY, JSON.stringify({ msgs: state.msgs.slice(-MAXKEEP), open: state.open, sid: state.sid })); };

  // The visitor's settings from the app (same key the app and the server pages read), and the find on screen.
  function prefs() {
    var s = {}; try { s = JSON.parse(localStorage.getItem("manifest.state") || "{}") || {}; } catch (e) {}
    var m = /^\/product\/([^/?#]+)/.exec(location.pathname), pid = "";
    if (m) try { pid = decodeURIComponent(m[1]); } catch (e) {}
    return { cur: String(s.cur || "USD"), agent: String(s.agent || "mycnbox").replace(/[^a-z0-9]/gi, "").toLowerCase(), pid: pid };
  }
  // Prices in the visitor's currency: the same rates as the app's CUR table and CUR_JS in functions/_lib/site.js.
  var CUR = { USD: ["$", .14], EUR: ["€", .13], NOK: ["kr ", 1.45], SEK: ["kr ", 1.47], DKK: ["kr ", .97], GBP: ["£", .11], CHF: ["CHF ", .125],
    PLN: ["zł ", .55], CAD: ["C$", .19], AUD: ["A$", .21], JPY: ["JP¥", 21], CNY: ["¥", 1] };
  function money(f) {
    var c = CUR[prefs().cur] || CUR.USD;
    if (f.cny > 0) return c[0] + Math.max(1, Math.round(f.cny * c[1])).toLocaleString("en-US");
    return f.price ? "$" + f.price : "Ask seller";
  }

  var SUGGEST = ["Ralph Lauren knit under $40", "How do I order with an agent?", "What are QC photos?", "Do Chinese sizes run small?"];
  var SUGGEST_PRODUCT = ["Is this a good find?", "What size should I get?", "Similar finds for less", "How do I order this?"];
  var SVG = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">';
  var ICON_CHAT = SVG + '<path d="M4 5h16v11H9l-5 4Z"/><path d="M8.5 10.5h.01M12 10.5h.01M15.5 10.5h.01"/></svg>';
  var ICON_X = SVG + '<path d="M18 6 6 18M6 6l12 12"/></svg>';
  var ICON_SEND = SVG.replace('stroke-width="1.75"', 'stroke-width="2"').replace(/20/g, "18") + '<path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  var ICON_STOP = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><rect x="5" y="5" width="14" height="14" rx="2.5"/></svg>';
  var ICON_NEW = SVG.replace(/20/g, "18") + '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>';
  var ICON_DOWN = SVG.replace(/20/g, "18") + '<path d="M12 5v14M5 12l7 7 7-7"/></svg>';
  var ICON_CAM = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 8h3l2-3h6l2 3h3v11H4Z"/><circle cx="12" cy="13" r="3.5"/></svg>';

  var LOGO = /(^|\.)puroclassico\.com$/.test(location.hostname) ? "/cdn-cgi/image/width=120,format=auto/logo-mark.png" : "/logo-mark.png";
  var EASE = "cubic-bezier(.22,1,.36,1)";
  var CSS =
    ".pcc{--pc-bg:var(--surface,var(--bg,#fff));--pc-ink:var(--ink,#0a0a0a);--pc-mut:var(--muted,#6b6b6b);--pc-line:var(--line,#e5e5e5);--pc-s2:var(--surface-2,var(--well,#f5f5f5));--pc-fill:var(--fill,#171717);--pc-fink:var(--fill-ink,#fafafa);" +
    "font-family:var(--f-body,var(--font,\"Instrument Sans\",Inter,-apple-system,BlinkMacSystemFont,\"Segoe UI\",system-ui,sans-serif));font-size:15px;line-height:1.5;color:var(--pc-ink);-webkit-font-smoothing:antialiased}" +
    ".pcc *,.pcc *::before,.pcc *::after{box-sizing:border-box}" +
    ".pcc button{-webkit-tap-highlight-color:transparent;touch-action:manipulation}" +
    // the round button
    ".pcc-fab{position:fixed;right:max(16px,env(safe-area-inset-right,0px));bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:70;display:inline-flex;align-items:center;gap:8px;height:48px;padding:0 18px 0 15px;border:1px solid var(--pc-line);border-radius:999px;background:var(--pc-fill);color:var(--pc-fink);font-family:inherit;font-size:15px;font-weight:600;line-height:1;cursor:pointer;box-shadow:0 10px 15px -3px rgba(0,0,0,.15),0 4px 6px -4px rgba(0,0,0,.15);transition:transform .2s " + EASE + ",opacity .15s ease-out,bottom .25s " + EASE + "}" +
    ".pcc-fab:active{transform:scale(.96)}.pcc-fab:focus-visible{outline:2px solid var(--pc-ink);outline-offset:3px}" +
    "@media (max-width:900px){body.has-buybar .pcc-fab,body:has(.buybar.on) .pcc-fab{bottom:calc(84px + env(safe-area-inset-bottom,0px))}}" +
    "@media (max-width:859px){body:has(.drawer.open .d-buybar.on) .pcc-fab{bottom:calc(84px + env(safe-area-inset-bottom,0px))}}" +
    ".pcc-open .pcc-fab{opacity:0;transform:scale(.9);pointer-events:none}" +
    // the panel: always in the page, eased in and out with transform + opacity (CSS transitions, so a quick re-click reverses mid-way)
    ".pcc-panel{position:fixed;right:16px;bottom:16px;z-index:1001;display:flex;flex-direction:column;width:380px;height:min(660px,calc(100vh - 32px));height:min(660px,calc(100dvh - 32px));background:var(--pc-bg);color:var(--pc-ink);border:1px solid var(--pc-line);border-radius:24px;box-shadow:0 20px 40px -8px rgba(0,0,0,.25);overflow:hidden;" +
    "transform-origin:calc(100% - 40px) calc(100% - 24px);opacity:0;visibility:hidden;pointer-events:none;transform:translateY(14px) scale(.97);transition:opacity .16s ease-out,transform .2s " + EASE + ",visibility 0s linear .2s}" +
    ".pcc-open .pcc-panel{opacity:1;visibility:visible;pointer-events:auto;transform:none;transition:opacity .2s ease-out,transform .32s " + EASE + ",visibility 0s}" +
    "@media (max-width:640px){.pcc-panel{top:0;left:0;right:0;bottom:auto;width:auto;height:100%;border:0;border-radius:0;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) 0 env(safe-area-inset-left,0px);transform:translateY(28px)}}" +
    "@media (prefers-reduced-motion:reduce){.pcc-panel,.pcc-open .pcc-panel{transform:none!important;transition-property:opacity,visibility}.pcc-fab{transition:opacity .15s}}" +
    ".pcc-still .pcc-panel,.pcc-still .pcc-fab{transition:none!important}" +
    // header: new chat left, logo and status line in the middle, close right
    ".pcc-hd{display:grid;grid-template-columns:40px minmax(0,1fr) 40px;align-items:center;gap:8px;padding:12px 12px 12px;border-bottom:1px solid var(--pc-line)}" +
    ".pcc-ttl{min-width:0;display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}" +
    ".pcc-logo{display:block;width:46px;height:44px;background-color:var(--pc-ink);-webkit-mask:url(" + LOGO + ") center/contain no-repeat;mask:url(" + LOGO + ") center/contain no-repeat}" +
    ".pcc-ttl span{display:block;font-size:12.5px;line-height:1.2;color:var(--pc-mut)}" +
    ".pcc-ib{display:inline-grid;place-items:center;width:40px;height:40px;border:0;border-radius:999px;background:transparent;color:var(--pc-ink);cursor:pointer;transition:background-color .15s}@media (hover:hover){.pcc-ib:hover{background:var(--pc-s2)}}.pcc-ib:focus-visible{outline:2px solid var(--pc-ink);outline-offset:1px}" +
    ".pcc-body{position:relative;flex:1;min-height:0;display:flex}" +
    ".pcc-log{flex:1;overflow-y:auto;overscroll-behavior:contain;padding:16px;display:flex;flex-direction:column;gap:12px;-webkit-overflow-scrolling:touch}" +
    ".pcc-log>:first-child{margin-top:auto}" +           // a short chat sits at the bottom, by the input, like a messenger
    ".pcc-day{flex-shrink:0;align-self:center;padding:2px 0;font-size:12.5px;color:var(--pc-mut)}" +
    ".pcc-hi{gap:4px}.pcc-hi .pcc-m{max-width:85%}" +
    ".pcc-turn{flex-shrink:0;display:flex;flex-direction:column;gap:8px}" +
    ".pcc-m{flex-shrink:0;max-width:88%;padding:10px 14px;border-radius:20px;overflow-wrap:anywhere;white-space:normal}" +
    ".pcc-m.u{align-self:flex-end;background:var(--pc-fill);color:var(--pc-fink);white-space:pre-wrap}" +
    ".pcc-m.a{align-self:flex-start;background:var(--pc-s2)}" +
    ".pcc-m strong{font-weight:600}" +
    ".pcc-m.err{background:transparent;border:1px solid var(--pc-line);color:var(--pc-mut)}" +
    ".pcc-m a{color:inherit;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;font-weight:500}" +
    ".pcc-m p{margin:0}.pcc-m p+p{margin-top:8px}.pcc-m p:empty{display:none}" +
    ".pcc-li{position:relative;display:block;padding-left:16px}.pcc-li.n{padding-left:22px}.pcc-li+.pcc-li{margin-top:4px}.pcc-li>i{position:absolute;left:0;top:0;font-style:normal;color:var(--pc-mut);font-variant-numeric:tabular-nums}" +
    ".pcc-m .pcc-stop{display:block;margin-top:6px;font-size:12.5px;color:var(--pc-mut)}" +
    ".pcc-retry{margin-top:8px;display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;border:1px solid var(--pc-line);border-radius:999px;background:var(--pc-bg);color:var(--pc-ink);font:inherit;font-size:13.5px;font-weight:500;cursor:pointer}@media (hover:hover){.pcc-retry:hover{background:var(--pc-s2)}}" +
    ".pcc-dots{display:inline-flex;align-items:center;gap:4px;padding:5px 0;min-height:24px}.pcc-dots i{width:6px;height:6px;border-radius:50%;background:var(--pc-mut);opacity:.35;animation:pcc-b 1.1s ease-in-out infinite}.pcc-dots i:nth-child(2){animation-delay:.15s}.pcc-dots i:nth-child(3){animation-delay:.3s}" +
    ".pcc-dots span{margin-left:6px;font-size:13px;color:var(--pc-mut)}@keyframes pcc-b{40%{opacity:1;transform:translateY(-2px)}}" +
    "@keyframes pcc-up{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}@keyframes pcc-fade{from{opacity:0}to{opacity:1}}" +
    "@media (prefers-reduced-motion:no-preference){.pcc-new{animation:pcc-up .24s " + EASE + " both}.pcc-card.pcc-new{animation-duration:.3s}}" +
    "@media (prefers-reduced-motion:reduce){.pcc-dots i{animation:none;opacity:.6}}" +
    // cards
    ".pcc-cards{flex-shrink:0;display:flex;gap:8px;overflow-x:auto;margin:0 -16px;padding:2px 16px 6px;scroll-padding:0 16px;scroll-snap-type:x proximity;scrollbar-width:none;-webkit-overflow-scrolling:touch}.pcc-cards::-webkit-scrollbar{display:none}" +
    ".pcc-cwrap{position:relative;flex-shrink:0}" +
    ".pcc-arr{position:absolute;top:calc(50% - 16px);z-index:2;display:grid;place-items:center;width:32px;height:32px;padding:0;border:1px solid var(--pc-line);border-radius:50%;background:var(--pc-bg);color:var(--pc-ink);box-shadow:0 2px 10px rgba(0,0,0,.22);cursor:pointer;opacity:0;pointer-events:none;transition:opacity .15s,transform .1s}" +
    ".pcc-arr svg{width:16px;height:16px}.pcc-arr.l{left:-6px}.pcc-arr.r{right:-6px}.pcc-arr:active{transform:scale(.94)}" +
    "@media (hover:hover){.pcc-cwrap:hover .pcc-arr.on{opacity:1;pointer-events:auto}}" +
    ".pcc-card{position:relative;flex:0 0 144px;scroll-snap-align:start;display:flex;flex-direction:column;border:1px solid var(--pc-line);border-radius:12px;overflow:hidden;background:var(--pc-bg);color:var(--pc-ink);transition:border-color .15s}" +
    "@media (hover:hover){.pcc-card:hover{border-color:var(--pc-mut)}}" +
    ".pcc-ph{display:block;width:100%;aspect-ratio:1;background:var(--pc-s2);overflow:hidden}.pcc-ph img{display:block;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .25s ease-out}.pcc-ph img.in{opacity:1}" +
    ".pcc-ci{display:flex;flex-direction:column;flex:1;padding:8px 10px 10px;font-size:12.5px;line-height:1.35}" +
    ".pcc-ci em{font-style:normal;color:var(--pc-mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    ".pcc-cl{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-weight:500;margin:1px 0 6px;color:inherit;text-decoration:none}" +
    ".pcc-cl::after{content:\"\";position:absolute;inset:0;border-radius:12px}.pcc-cl:focus-visible{outline:none}.pcc-cl:focus-visible::after{outline:2px solid var(--pc-ink);outline-offset:-2px}" +
    ".pcc-cr{margin-top:auto;display:flex;align-items:center;gap:6px}" +
    ".pcc-cr b{font-size:13px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}" +
    ".pcc-qc{display:inline-flex;align-items:center;gap:3px;color:var(--pc-mut);font-size:11.5px;font-variant-numeric:tabular-nums;white-space:nowrap}" +
    ".pcc-buy{position:relative;z-index:1;margin-left:auto;display:inline-grid;place-items:center;height:26px;padding:0 10px;border-radius:999px;background:var(--pc-fill);color:var(--pc-fink);font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap}" +
    ".pcc-buy:focus-visible{outline:2px solid var(--pc-ink);outline-offset:2px}" +
    // suggestion chips
    ".pcc-sug{flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:8px;margin-top:6px}" +
    ".pcc-sug button{max-width:88%;min-height:40px;border:1px solid var(--pc-ink);background:transparent;color:var(--pc-ink);border-radius:999px;padding:8px 16px;font:inherit;font-size:14px;font-weight:500;line-height:1.35;cursor:pointer;text-align:left;transition:background-color .15s,transform .15s " + EASE + "}" +
    "@media (hover:hover){.pcc-sug button:hover{background:var(--pc-s2)}}.pcc-sug button:active{transform:scale(.96)}.pcc-sug button:focus-visible{outline:2px solid var(--pc-ink);outline-offset:2px}" +
    ".pcc-jump{position:absolute;left:50%;bottom:10px;z-index:2;display:inline-grid;place-items:center;width:36px;height:36px;margin-left:-18px;border:1px solid var(--pc-line);border-radius:999px;background:var(--pc-bg);color:var(--pc-ink);box-shadow:0 4px 12px -2px rgba(0,0,0,.18);cursor:pointer;opacity:0;transform:translateY(6px);pointer-events:none;transition:opacity .15s ease-out,transform .2s " + EASE + "}" +
    ".pcc-jump.on{opacity:1;transform:none;pointer-events:auto}" +
    // composer
    ".pcc-ft{padding:8px 12px calc(14px + env(safe-area-inset-bottom,0px))}" +
    ".pcc-form{display:flex;align-items:flex-end;gap:8px}" +
    ".pcc-note{margin:6px 2px 0;font-size:10.5px;line-height:1.3;color:var(--pc-mut);text-align:center}.pcc-note a{color:inherit;text-underline-offset:2px}" +
    ".pcc-field{flex:1;min-width:0;display:flex;border:1px solid transparent;border-radius:24px;padding:4px 18px;background:var(--pc-s2);transition:border-color .15s}" +
    ".pcc-field:focus-within{border-color:var(--pc-line)}" +
    ".pcc-in{flex:1;min-width:0;border:0!important;outline:0!important;box-shadow:none!important;background:transparent!important;color:var(--pc-ink);font:inherit;font-size:16px;line-height:1.4;padding:8px 0!important;margin:0;resize:none;height:38px;max-height:120px;overflow-y:hidden;border-radius:0}" +
    ".pcc-in::placeholder{color:var(--pc-mut);opacity:1}" +
    ".pcc-send{flex:0 0 auto;display:inline-grid;place-items:center;width:48px;height:48px;border:0;border-radius:999px;background:var(--pc-fill);color:var(--pc-fink);cursor:pointer;transition:opacity .15s,transform .15s " + EASE + "}.pcc-send:active{transform:scale(.96)}.pcc-send:disabled{opacity:.3;cursor:default;transform:none}.pcc-send:focus-visible{outline:2px solid var(--pc-ink);outline-offset:2px}" +
    ".pcc-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}" +
    "html.pcc-lock,html.pcc-lock body{overflow:hidden}";

  // ---------------------------------------------------------------- markdown-lite (escape first, then a few safe patterns)
  function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function safeUrl(u) {
    u = String(u || "").replace(/&amp;/g, "&");
    if (/^\/(?![\/\\])/.test(u)) return u;               // a site path; "//x" and "/\x" would leave the site
    if (/^https?:\/\//i.test(u)) return u;
    return "";
  }
  function link(text, url) {
    var u = safeUrl(url); if (!u) return text;
    var own = u.charAt(0) === "/" || /^https?:\/\/(www\.)?puroclassico\.com(\/|$)/i.test(u);
    if (own) u = u.replace(/^https?:\/\/(www\.)?puroclassico\.com/i, "") || "/";
    return '<a href="' + esc(u) + '"' + (own ? "" : ' target="_blank" rel="noopener nofollow"') + ">" + text + "</a>";
  }
  // One paragraph -> the inside of its <p>. While the answer is still streaming, a link or bold that is not closed yet is
  // shown as its plain words, so raw "[title](https://..." never flashes on screen.
  function mdPara(src, live) {
    if (live) {
      var m = /\[([^\]\n]*)(\]\(?[^)\s]*)?$/.exec(src);
      if (m) src = src.slice(0, m.index) + m[1];
      if ((src.match(/\*\*/g) || []).length % 2) src = src.replace(/\*\*(?![\s\S]*\*\*)/, "");
    }
    var h = esc(src), slots = [];
    h = h.replace(/\[([^\]\n]{1,200})\]\(([^)\s]{1,500})\)/g, function (_, t, u) { slots.push(link(t, u)); return "\u0000" + (slots.length - 1) + "\u0000"; });
    h = h.replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,!?:;'"])/g, function (_, pre, u) { slots.push(link(u.replace(/^https?:\/\/(www\.)?/i, ""), u)); return pre + "\u0000" + (slots.length - 1) + "\u0000"; });
    h = h.replace(/(^|[\s(])((?:www\.)?puroclassico\.com\/[^\s<)]*[^\s<).,!?:;'"])/gi, function (_, pre, u) { slots.push(link(u.replace(/^www\./i, ""), "https://" + u)); return pre + "\u0000" + (slots.length - 1) + "\u0000"; });
    h = h.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/\u0000(\d+)\u0000/g, function (_, i) { return slots[+i]; });
    // "- item", "* item", "1. item": a block line with a hanging indent, so wrapped bullets line up
    var out = "", prevLi = false;
    h.split("\n").forEach(function (l) {
      l = l.replace(/^#{1,4}\s+/, "");
      var b = /^\s*(?:[-*\u2022]|(\d{1,2})[.)])\s+/.exec(l);
      if (b) { out += '<span class="pcc-li' + (b[1] ? " n" : "") + '"><i' + (b[1] ? ">" + b[1] + "." : ' aria-hidden="true">\u2022') + "</i>" + l.slice(b[0].length) + "</span>"; prevLi = true; }
      else { if (out && !prevLi) out += "<br>"; out += l; prevLi = false; }
    });
    return out;
  }
  var paras = function (s) { return String(s || "").replace(/^\s+/, "").split(/\n{2,}/); };

  // ---------------------------------------------------------------- DOM
  var root, fab, panel, log, input, send, jump, busy = false, ctl = null, lastFocus = null, pinned = true;
  var phone = W.matchMedia ? W.matchMedia("(max-width:640px)") : { matches: false };
  var fine = W.matchMedia ? W.matchMedia("(hover:hover) and (pointer:fine)") : { matches: true };
  function el(tag, cls, html) { var e = D.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function listen(mq, fn) { if (mq.addEventListener) mq.addEventListener("change", fn); else if (mq.addListener) mq.addListener(fn); }

  function build() {
    var st = el("style"); st.textContent = CSS; D.head.appendChild(st);
    root = el("div", "pcc pcc-still");
    fab = el("button", "pcc-fab", ICON_CHAT + "<span>Ask</span>");
    fab.type = "button"; fab.setAttribute("aria-label", "Ask the shopping assistant"); fab.setAttribute("aria-haspopup", "dialog"); fab.setAttribute("aria-expanded", "false"); fab.setAttribute("aria-controls", "pcc-panel");
    panel = el("div", "pcc-panel"); panel.id = "pcc-panel"; panel.inert = true; panel.setAttribute("aria-hidden", "true");
    panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true"); panel.setAttribute("aria-labelledby", "pcc-title");
    panel.innerHTML =
      '<div class="pcc-hd"><button type="button" class="pcc-ib" data-new aria-label="Start a new chat" title="New chat">' + ICON_NEW + '</button>' +
      '<div class="pcc-ttl"><b id="pcc-title" class="pcc-sr">Ask Puro Classico</b><i class="pcc-logo" aria-hidden="true"></i><span>Replies right away</span></div>' +
      '<button type="button" class="pcc-ib" data-close aria-label="Close chat">' + ICON_X + '</button></div>' +
      '<div class="pcc-body"><div class="pcc-log" role="log" aria-live="polite" aria-relevant="additions" tabindex="-1"></div>' +
      '<button type="button" class="pcc-jump" aria-label="Scroll to the latest message" tabindex="-1">' + ICON_DOWN + '</button></div>' +
      '<div class="pcc-ft"><form class="pcc-form"><label class="pcc-sr" for="pcc-in">Your message</label>' +
      '<span class="pcc-field"><textarea class="pcc-in" id="pcc-in" rows="1" maxlength="' + MAXLEN + '" placeholder="Ask a question..." enterkeyhint="send" autocomplete="off"></textarea></span>' +
      '<button type="submit" class="pcc-send" aria-label="Send" disabled>' + ICON_SEND + '</button></form>' +
      '<p class="pcc-note">Chats are saved to improve answers. Don\'t share personal details. <a href="/privacy#chat">Privacy</a></p></div>';
    root.appendChild(fab); root.appendChild(panel); D.body.appendChild(root);
    log = panel.querySelector(".pcc-log"); input = panel.querySelector(".pcc-in"); send = panel.querySelector(".pcc-send"); jump = panel.querySelector(".pcc-jump");

    fab.addEventListener("click", function () { setOpen(true); });
    panel.querySelector("[data-close]").addEventListener("click", function () { setOpen(false); });
    panel.querySelector("[data-new]").addEventListener("click", function () {
      if (busy) { stop(true); busy = false; ctl = null; log.setAttribute("aria-busy", "false"); sendState(); }
      state.msgs = []; state.sid = newSid(); save(); render(); if (fine.matches) input.focus();
    });
    panel.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); if (busy) stop(); else ask(input.value); });
    input.addEventListener("input", function () { grow(); sendState(); });
    panel.querySelector(".pcc-field").addEventListener("mousedown", function (e) { if (e.target !== input) { e.preventDefault(); input.focus(); } });
    log.addEventListener("click", openFind);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); if (!busy) ask(input.value); } });
    log.addEventListener("scroll", function () { pinned = log.scrollHeight - log.scrollTop - log.clientHeight < 40; if (pinned) jump.classList.remove("on"); }, { passive: true });
    jump.addEventListener("click", function () { pinned = true; jump.classList.remove("on"); toBottom(true); });
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.stopPropagation(); setOpen(false); return; }
      if (e.key !== "Tab") return;
      var f = [].filter.call(panel.querySelectorAll("button:not([tabindex='-1']),textarea,a[href]"), function (x) { return !x.disabled && x.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && D.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && D.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    listen(phone, function () { lock(); fit(); });
    if (W.visualViewport) { W.visualViewport.addEventListener("resize", fit); W.visualViewport.addEventListener("scroll", fit); }
    W.addEventListener("pagehide", function () { save(); });
    render();
    if (state.open) setOpen(true, true);
    // transitions on from the next frame, so a panel restored open does not animate in on every page
    setTimeout(function () { root.classList.remove("pcc-still"); }, 80);
  }
  function frame(fn) { (W.requestAnimationFrame || function (f) { return setTimeout(f, 16); })(fn); }
  function grow() { input.style.height = "auto"; var h = Math.min(input.scrollHeight, 120); input.style.height = h + "px"; input.style.overflowY = input.scrollHeight > 120 ? "auto" : "hidden"; }
  function sendState() {
    if (busy) { send.disabled = false; send.innerHTML = ICON_STOP; send.setAttribute("aria-label", "Stop"); }
    else { send.innerHTML = ICON_SEND; send.setAttribute("aria-label", "Send"); send.disabled = !input.value.trim(); }
  }
  function lock() { D.documentElement.classList.toggle("pcc-lock", state.open && phone.matches); }
  // Phones: keep the sheet inside the visible area when the on-screen keyboard is up.
  function fit() {
    var v = W.visualViewport;
    if (!v || !phone.matches || !state.open) { panel.style.height = ""; panel.style.top = ""; return; }
    panel.style.height = Math.round(v.height) + "px"; panel.style.top = Math.round(v.offsetTop) + "px";
    if (pinned) toBottom();
  }
  // "Ask about this item" box on product pages (8 Nov 2026, beta): opens the panel and asks the question in one go.
  W.pcChatAsk = function (text) { if (!panel) return false; if (!state.open) setOpen(true, true); ask(text); return true; };
  function setOpen(on, quiet) {
    state.open = on; save();
    root.classList.toggle("pcc-open", on);
    panel.inert = !on; panel.setAttribute("aria-hidden", on ? "false" : "true");
    fab.setAttribute("aria-expanded", on ? "true" : "false"); fab.tabIndex = on ? -1 : 0;
    lock(); fit();
    if (on) {
      lastFocus = quiet ? null : D.activeElement;
      pinned = true; toBottom();
      // no automatic focus on touch screens: the keyboard would cover the chips and the answer
      if (fine.matches && !quiet) setTimeout(function () { input.focus({ preventScroll: true }); }, 40);
    } else if (!quiet) (lastFocus && lastFocus.focus && lastFocus !== D.body ? lastFocus : fab).focus({ preventScroll: true });
  }
  function toBottom(smooth) {
    if (smooth && log.scrollTo && !(W.matchMedia && W.matchMedia("(prefers-reduced-motion:reduce)").matches)) log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
    else log.scrollTop = log.scrollHeight;
  }
  // After new content: follow it only while the reader is at the bottom; otherwise offer the jump button.
  function follow() { if (pinned) toBottom(); else jump.classList.add("on"); }

  // ---------------------------------------------------------------- views
  // A turn = the bubble plus, for answers, a row of cards. Answers are painted per paragraph: finished paragraphs once,
  // only the last one again on each frame.
  function userTurn(m) { var t = el("div", "pcc-turn"), b = el("div", "pcc-m u"); b.textContent = m.content; t.appendChild(b); return t; }
  function answerView(m) {
    var v = { m: m, turn: el("div", "pcc-turn"), bubble: el("div", "pcc-m a"), ps: [], cards: null, status: "" };
    v.turn.appendChild(v.bubble);
    paint(v, false);
    if (m.finds && m.finds.length) setCards(v, m.finds, false);
    return v;
  }
  function paint(v, live) {
    var m = v.m, b = v.bubble;
    b.classList.toggle("err", !!m.err);
    if (!m.content) {
      if (!b.querySelector(".pcc-dots")) { b.innerHTML = '<span class="pcc-dots" role="status"><i></i><i></i><i></i><span class="pcc-sr">Writing</span></span>'; v.ps = []; }
      var lab = b.querySelector(".pcc-dots > span");
      var want = v.status === "search" ? "Searching finds" : "";
      if (lab.textContent !== (want || "Writing")) { lab.textContent = want || "Writing"; lab.className = want ? "" : "pcc-sr"; }
      return;
    }
    if (b.querySelector(".pcc-dots")) { b.innerHTML = ""; v.ps = []; }
    var list = paras(m.content);
    for (var i = 0; i < list.length; i++) {
      var p = v.ps[i];
      if (!p) { p = D.createElement("p"); b.appendChild(p); v.ps[i] = p; p._src = null; }
      var isLast = i === list.length - 1, key = list[i] + (live && isLast ? "\u0001" : "");
      if (p._src !== key) { p.innerHTML = mdPara(list[i], live && isLast); p._src = key; }
    }
    while (v.ps.length > list.length) b.removeChild(v.ps.pop());
    var extra = b.querySelector(".pcc-stop, .pcc-retry");
    if (extra) extra.remove();
    if (m.note) b.appendChild(el("span", "pcc-stop", esc(m.note)));
    if (m.retry && !busy) {
      var r = el("button", "pcc-retry", "Try again"); r.type = "button";
      r.addEventListener("click", function () { retry(m); });
      b.appendChild(r);
    }
  }
  var imgIn = function () { this.classList.add("in"); };
  function card(f, i) {
    var c = el("div", "pcc-card pcc-new"); c.setAttribute("role", "listitem"); c._id = f.id;
    c.addEventListener("animationend", function () { c.classList.remove("pcc-new"); c.style.animationDelay = ""; });
    c.style.animationDelay = Math.min(i, 6) * 45 + "ms";
    var href = safeUrl(f.url) || "/", price = money(f), buy = safeUrl(f.buy);
    c.innerHTML = '<span class="pcc-ph">' + (f.img ? '<img src="' + esc(f.img) + '" alt="" loading="lazy" decoding="async" width="144" height="144">' : "") + "</span>" +
      '<span class="pcc-ci"><em>' + esc(f.brand || " ") + '</em><a class="pcc-cl" href="' + esc(href) + '">' + esc(f.title) + "</a>" +
      '<span class="pcc-cr"><b>' + esc(price) + "</b>" + (f.qc ? '<span class="pcc-qc" title="QC photos">' + ICON_CAM + esc(f.qc) + "</span>" : "") +
      (buy && /^https:\/\//.test(buy) ? '<a class="pcc-buy" href="' + esc(buy) + '" target="_blank" rel="sponsored nofollow noopener">Buy</a>' : "") + "</span></span>";
    c.querySelector(".pcc-cl").setAttribute("aria-label", f.title + ", " + price + (f.qc ? ", " + f.qc + " QC photos" : ""));
    var b = c.querySelector(".pcc-buy"); if (b) b.setAttribute("aria-label", "Buy " + f.title + " via " + (f.agent || "your agent"));
    var img = c.querySelector("img");
    if (img) { img.addEventListener("load", imgIn); img.addEventListener("error", function () { img.remove(); }); if (img.complete && img.naturalWidth) img.classList.add("in"); }
    return c;
  }
  // The card row scrolls sideways (owner, 8 Nov 2026: "make it possible to scroll here"): a mouse wheel or trackpad moves it
  // while it can still move (then the chat scrolls as usual), and on mouse devices round arrows show at the row's ends.
  function scroller(wrap, row) {
    var ARR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>';
    var l = el("button", "pcc-arr l", ARR), r = el("button", "pcc-arr r", ARR);
    r.querySelector("svg").style.transform = "scaleX(-1)";
    l.type = r.type = "button"; l.setAttribute("aria-label", "Previous finds"); r.setAttribute("aria-label", "Next finds");
    l.tabIndex = r.tabIndex = -1; wrap.appendChild(l); wrap.appendChild(r);
    var upd = function () { var max = row.scrollWidth - row.clientWidth - 2; l.classList.toggle("on", row.scrollLeft > 2); r.classList.toggle("on", max > 0 && row.scrollLeft < max); };
    var go = function (d) { var rm = W.matchMedia && W.matchMedia("(prefers-reduced-motion: reduce)").matches; row.scrollBy({ left: d * Math.max(150, row.clientWidth * 0.8), behavior: rm ? "auto" : "smooth" }); };
    l.addEventListener("click", function () { go(-1); }); r.addEventListener("click", function () { go(1); });
    row.addEventListener("scroll", upd, { passive: true });
    row.addEventListener("wheel", function (e) {
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX) || row.scrollWidth <= row.clientWidth) return;
      var before = row.scrollLeft; row.scrollLeft += e.deltaY;
      if (row.scrollLeft !== before) e.preventDefault();
    }, { passive: false });
    wrap._upd = upd; setTimeout(upd, 0); setTimeout(upd, 400);
  }
  // Cards keyed by find id: an update moves the cards it keeps (no image reload), adds new ones and drops the rest.
  function setCards(v, list, animate) {
    list = (list || []).filter(function (f) { return f && f.id && f.title; });
    if (!list.length) { if (v.cards) { (v.cwrap || v.cards).remove(); v.cards = null; v.cwrap = null; } return; }
    if (!v.cards) {
      v.cards = el("div", "pcc-cards"); v.cards.setAttribute("role", "list"); v.cards.setAttribute("aria-label", "Finds");
      v.cwrap = el("div", "pcc-cwrap"); v.cwrap.appendChild(v.cards); v.turn.appendChild(v.cwrap); scroller(v.cwrap, v.cards);
    }
    if (v.cwrap && v.cwrap._upd) setTimeout(v.cwrap._upd, 60);
    var have = {}; [].forEach.call(v.cards.children, function (c) { have[c._id] = c; });
    var keep = {}, moved = false;
    list.forEach(function (f, i) {
      var c = have[f.id];
      if (c) c.classList.remove("pcc-new");                 // a moved node would replay its entrance animation
      else { c = card(f, i); if (!animate) c.classList.remove("pcc-new"); }
      keep[f.id] = 1;
      if (v.cards.children[i] !== c) { if (c.parentNode) moved = true; v.cards.insertBefore(c, v.cards.children[i] || null); }
    });
    [].slice.call(v.cards.children).forEach(function (c) { if (!keep[c._id]) c.remove(); });
    if (moved) v.cards.scrollLeft = 0;                       // the first card is the one the answer names first
  }
  function greeting() {
    var hi = el("div", "pcc-turn pcc-hi"), lines = ["<strong>Hi! \ud83d\udc4b</strong>", "I'm the Puro Classico assistant.",
      prefs().pid ? "Ask me about this find, or about sizing, QC photos and shipping." : "What are you looking for today?"];
    lines.forEach(function (t) { hi.appendChild(el("div", "pcc-m a", "<p>" + t + "</p>")); });
    return hi;
  }
  function render() {
    log.innerHTML = "";
    log.appendChild(el("div", "pcc-day", "Today"));
    log.appendChild(greeting());
    if (!state.msgs.length) {
      var sug = el("div", "pcc-sug");
      (prefs().pid ? SUGGEST_PRODUCT : SUGGEST).forEach(function (s) { var x = el("button"); x.type = "button"; x.textContent = s; x.addEventListener("click", function () { ask(s); }); sug.appendChild(x); });
      log.appendChild(sug);
    }
    state.msgs.forEach(function (m) { log.appendChild(m.role === "user" ? userTurn(m) : answerView(m).turn); });
    pinned = true; toBottom();
  }

  // ---------------------------------------------------------------- finds open in the app's product view
  // On the app (index.html defines openDetail and BY_ID), a card or a /product/<id> link in an answer opens the same product
  // view as a card in the grid. The chat closes for it and opens again when that view closes. Pages without the app, the
  // Buy button and cmd/ctrl/shift/middle clicks keep the ordinary link.
  var reopen = false;
  function findOf(a) {
    var m = /^\/product\/([^/?#]+)\/?$/.exec(a.getAttribute("href") || ""), id = "";
    if (!m) return null;
    try { id = decodeURIComponent(m[1]); } catch (e) { return null; }
    try { return typeof openDetail === "function" && typeof BY_ID !== "undefined" && BY_ID ? BY_ID[id] || null : null; } catch (e) { return null; }
  }
  function watchDrawer() {
    var dr = D.getElementById("drawer");
    if (!dr || dr.__pccObs || !W.MutationObserver) return;
    dr.__pccObs = new MutationObserver(function () {
      if (!reopen || dr.classList.contains("open")) return;
      reopen = false;
      // after the app has put focus back on the page, so the chat keeps it
      setTimeout(function () { if (state.open) return; setOpen(true); if (!fine.matches) log.focus({ preventScroll: true }); }, 60);
    });
    dr.__pccObs.observe(dr, { attributes: true, attributeFilter: ["class"] });
  }
  function openFind(e) {
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a || !log.contains(a) || a.classList.contains("pcc-buy")) return;
    if (e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var p = findOf(a); if (!p) return;
    e.preventDefault();
    watchDrawer(); reopen = true;
    setOpen(false, true);
    try { openDetail(p); } catch (x) { reopen = false; location.href = a.href; }
  }

  // ---------------------------------------------------------------- talking to /api/chat
  function hide() { ss.set(OKKEY, "0"); if (root) { D.documentElement.classList.remove("pcc-lock"); root.remove(); } }
  function stop(silent) { if (ctl) { ctl.silent = !!silent; try { ctl.abort(); } catch (e) {} } }
  function retry(m) {
    if (busy) return;
    var i = state.msgs.indexOf(m), u = i > 0 ? state.msgs[i - 1] : null;
    if (!u || u.role !== "user") return;
    state.msgs.splice(i - 1, 2); save(); render(); ask(u.content);
  }
  function ask(text) {
    text = String(text || "").trim().slice(0, MAXLEN);
    if (!text || busy) return;
    busy = true; input.value = ""; grow(); sendState();
    var history = state.msgs.filter(function (m) { return !m.err && m.content; }).map(function (m) { return { role: m.role, content: m.content.slice(0, MAXLEN) }; });
    history.push({ role: "user", content: text });
    var me = { role: "assistant", content: "", pending: true }, um = { role: "user", content: text };
    var sg = log.querySelector(".pcc-sug"); if (sg) sg.remove();   // the suggestions go with the first message; the greeting stays
    state.msgs.push(um, me);
    var ut = userTurn(um), v = answerView(me);
    ut.classList.add("pcc-new"); v.turn.classList.add("pcc-new");
    log.appendChild(ut); log.appendChild(v.turn);
    pinned = true; jump.classList.remove("on"); toBottom(); save();
    log.setAttribute("aria-busy", "true");

    // Paint at most once per frame (and on a timer, for when frames are throttled in a hidden tab).
    var due = false, tick = function () { if (!due) return; due = false; paint(v, true); follow(); };
    var later = function () { if (due) return; due = true; frame(tick); setTimeout(tick, 150); };
    var failed = false;
    // An error after part of the answer keeps that part, with a note and Try again.
    var fail = function (msg, canRetry) {
      failed = true; me.retry = !!canRetry;
      if (me.content && !me.err) me.note = "The answer was cut off.";
      else { me.content = msg || "Sorry, something went wrong. Please try again."; me.err = true; }
    };
    var my = ctl = W.AbortController ? new AbortController() : null;
    var finish = function () {
      delete me.pending;
      if (my && my.silent) return;                          // "New chat" while it was writing: this answer is gone
      var aborted = my && my.signal.aborted;
      busy = false; ctl = null; log.setAttribute("aria-busy", "false");
      if (aborted && !failed) { if (me.content) me.note = "Stopped"; else { me.content = "Stopped."; me.err = true; } me.retry = true; }
      else if (!me.content) fail("Sorry, no answer came back. Please try again.", true);
      due = false; paint(v, false); sendState(); follow(); save();
    };
    fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, credentials: "same-origin", signal: my ? my.signal : undefined,
      body: JSON.stringify({ messages: history.slice(-10), ctx: prefs(), v: 2, sid: state.sid }) })
      .then(function (r) {
        if (r.status === 503) { hide(); return; }
        if (!r.ok || !r.body || !r.body.getReader) return r.json().then(function (j) { fail(j && j.error, r.status !== 429 && r.status !== 413); }, function () { fail(null, true); });
        var reader = r.body.getReader(), dec = new TextDecoder(), buf = "";
        var line = function (s) {
          if (!s.trim()) return;
          var o; try { o = JSON.parse(s); } catch (e) { return; }
          if (o.t === "text" && typeof o.v === "string") { me.content += o.v; later(); }
          else if (o.t === "status") { v.status = o.v; if (!me.content) paint(v, true); }
          else if (o.t === "finds" && Array.isArray(o.v)) { me.finds = o.v.slice(0, 8); setCards(v, me.finds, true); follow(); }
          else if (o.t === "error") { fail(o.v, true); }
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
      .catch(function () { if (!(my && my.signal.aborted)) fail("The connection dropped. Please try again.", true); })
      .then(finish, finish);
  }

  // ---------------------------------------------------------------- start: only when the assistant is set up
  function ready() { build(); W.pcChatReady = true; try { D.dispatchEvent(new Event("pc-chat-ready")); } catch (e) {} }
  function start() {
    var ok = ss.get(OKKEY);
    if (ok === "0") return;
    if (ok === "1") return ready();
    fetch("/api/chat", { method: "GET", credentials: "same-origin" }).then(function (r) {
      if (r.ok) { ss.set(OKKEY, "1"); ready(); } else if (r.status === 503) ss.set(OKKEY, "0");
    }).catch(function () {});
  }
  if (D.readyState === "loading") D.addEventListener("DOMContentLoaded", start); else start();
})();
