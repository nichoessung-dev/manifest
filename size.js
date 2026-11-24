/* Size helper on product pages and in the app's find view (owner, 19 Nov 2026: "make a size recomendation based on users
   weigth and heigth"). The visitor types height and weight once (kept in localStorage "pc.body") and picks a fit; the
   helper answers with one of the sizes the listing sells.
   1. The seller's chart (data/sizes/<last two digits>.json, scripts/bake_sizes.py from scripts/listing_details.py):
      recommended height/weight ranges first, else chest (tops, jackets), waist (pants, shorts) or foot length (shoes)
      compared with the body measure estimated from height and weight plus room for the fit.
   2. No chart: the same estimate as /tools/size-estimator (functions/_lib/tools9.js sizeFor), one size up for Chinese
      sizing, matched to the listing's own size names.
   window.pcSize.mount(el, {id, cat, g}) fills el. Clothes and shoes only.
   23 Nov 2026 (owner): the size step at sign-up (ask) and a subtle "We recommend size L" note on clothes (mount); see below.
   The note opens to the reason and the seller's chart. Replaces the "Find my size" row. */
(function () {
  "use strict";
  var KEY = "pc.body", CATS = { Tops: "top", Outerwear: "jacket", Pants: "pants", Shorts: "pants", Shoes: "shoes" };
  var L = ["XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL"], WA = [28, 30, 32, 34, 36, 38, 40, 42];
  var SH = [[22.5, 35], [23, 36], [23.5, 37], [24, 38], [24.5, 39], [25, 40], [25.5, 40.5], [26, 41], [26.5, 42], [27, 42.5], [27.5, 43], [28, 44], [28.5, 44.5], [29, 45], [29.5, 45.5], [30, 46], [30.5, 47]];
  var FIT = { s: { t: "Slim", ease: 6, step: -0.5, wa: 0, ft: 0.3 }, r: { t: "Regular", ease: 12, step: 0, wa: 2, ft: 0.6 }, l: { t: "Loose", ease: 22, step: 1, wa: 5, ft: 1 } };
  var cache = {};
  function store() { try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { return {}; } }
  function save(o) { try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (e) {} }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function load(id) {
    var k = String(id).slice(-2); if (k.length < 2) k = "0" + k;
    if (!cache[k]) cache[k] = fetch("/data/sizes/" + k + ".json?v=1").then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return cache[k].then(function (m) { return m[String(id)] || null; });
  }
  function norm(s) { s = String(s).toUpperCase().replace(/\s/g, ""); return s === "2XL" ? "XXL" : s === "XXXL" ? "3XL" : s === "XXXXL" ? "4XL" : s; }
  function letterIdx(s) { return L.indexOf(norm(s)); }
  function dist(v, a, b) { return v < a ? a - v : v > b ? v - b : 0; }
  // the body measures estimated from height and weight (adult, men's/unisex cut)
  function chestOf(b) { return 0.45 * b.w + 0.25 * b.h + 21; }
  function waistOf(b) { return 0.65 * b.w + 0.1 * b.h + 18; }
  function footOf(b) { if (b.eu) { var r = SH.filter(function (x) { return x[1] <= b.eu; }).pop() || SH[0]; return r[0]; } return 0.152 * b.h; }
  function shoeEu(b) { if (b.eu) return b.eu; var f = footOf(b), r = SH.filter(function (x) { return x[0] >= f - 0.05; })[0] || SH[SH.length - 1]; return r[1]; }

  // the answer: {size, why, chart: bool}
  function pick(kind, b, d) {
    var f = FIT[b.fit] || FIT.r, rows = (d && d.c) || [], sold = (d && d.s) || [];
    var flat = d && d.m === "flat";
    if (kind === "shoes" && !b.eu) return { size: "", chart: false, ask: true, why: "Add your usual EU shoe size above. Height alone is not enough for shoes." };
    if (rows.length) {
      // the seller's recommended height and/or weight per size (23 Nov 2026: weight-only charts count too; many give only weight)
      var hw = rows.filter(function (r) { return r[1].h0 || r[1].w0; });
      if (hw.length >= 2 && hw.filter(function (r) { return r[1].w0; }).length < hw.length && hw.filter(function (r) { return r[1].h0; }).length < hw.length) hw = [];
      if (hw.length >= 2 && kind !== "shoes") {
        var best = null, bs = 1e9, sc = [];
        hw.forEach(function (r, i) { var m = r[1], s = (m.h0 ? dist(b.h, m.h0, m.h1 || m.h0) / 3 : 0) + (m.w0 ? dist(b.w, m.w0, m.w1 || m.w0) / 2 : 0); sc.push(s); if (s < bs - 0.01) { bs = s; best = i; } });
        var near = best + 1 < hw.length && sc[best + 1] - bs < 0.6 ? hw[best + 1][0] : "";
        var j = Math.max(0, Math.min(hw.length - 1, best + (b.fit === "l" ? 1 : 0)));
        var m = hw[best][1];
        return { size: hw[j][0], chart: true, why: "The seller's chart suggests " + esc(hw[best][0]) + " for " + (m.h0 ? Math.round(m.h0) + " to " + Math.round(m.h1 || m.h0) + " cm" : "") + (m.h0 && m.w0 ? " and " : "") + (m.w0 ? Math.round(m.w0) + " to " + Math.round(m.w1 || m.w0) + " kg" : "") + "." + (j !== best ? " One size up for a loose fit." : near && b.fit !== "l" ? " You're between " + esc(hw[best][0]) + " and " + esc(near) + ": take " + esc(near) + " if you like more room." : "") };
      }
      if (kind === "shoes" && b.eu) {
        var same = rows.filter(function (r) { return Math.abs(parseFloat(r[0]) - b.eu) < 0.01 && r[1].ft; })[0];
        if (same) return { size: same[0], chart: true, why: "Your usual EU " + b.eu + ". This seller's " + esc(same[0]) + " is " + same[1].ft + " cm inside." };
      }
      if (kind === "shoes") {
        var ft = rows.filter(function (r) { return r[1].ft; });
        if (ft.length >= 2) {
          var foot = footOf(b), need = foot + f.ft, hit = ft.filter(function (r) { return r[1].ft >= need - 0.05; })[0];
          if (!hit) return { size: ft[ft.length - 1][0], chart: true, why: "Your foot is about " + foot.toFixed(1) + " cm, longer than this seller's biggest size (" + esc(ft[ft.length - 1][0]) + ", " + ft[ft.length - 1][1].ft + " cm). Check with the seller." };
          return { size: hit[0], chart: true, why: "Your foot is about " + foot.toFixed(1) + " cm" + (b.eu ? "" : " (a guess from your height: add your usual EU size for a better answer)") + ". " + esc(hit[0]) + " is " + hit[1].ft + " cm on the seller's chart." };
        }
      } else if (kind === "pants") {
        var wr = rows.filter(function (r) { return r[1].wa; });
        if (wr.length >= 2) {
          var bw = waistOf(b), tw = bw + f.wa, best2 = null, bd = 1e9;
          wr.forEach(function (r) { var g = r[1].wa * (flat || r[1].wa < 55 ? 2 : 1), dd = Math.abs(g - tw) + (g < bw ? 6 : 0); if (dd < bd) { bd = dd; best2 = [r[0], g]; } });
          return { size: best2[0], chart: true, why: "Your waist is about " + Math.round(bw) + " cm. " + esc(best2[0]) + " measures " + Math.round(best2[1]) + " cm on the seller's chart." };
        }
      } else {
        var cr = rows.filter(function (r) { return r[1].ch; });
        if (cr.length >= 2) {
          var bc = chestOf(b), tc = bc + f.ease + (kind === "jacket" ? 4 : 0), best3 = null, bd3 = 1e9;
          var needLen = 0.39 * b.h - 2;   // too short for a tall body counts against a size
          cr.forEach(function (r) { var g = r[1].ch * (flat || r[1].ch < 85 ? 2 : 1), dd = Math.abs(g - tc) + (g < bc + 2 ? 8 : 0) + (r[1].le ? Math.max(0, needLen - r[1].le) * 3 : 0); if (dd < bd3) { bd3 = dd; best3 = [r[0], g]; } });
          return { size: best3[0], chart: true, why: "Your chest is about " + Math.round(bc) + " cm. " + esc(best3[0]) + " is " + Math.round(best3[1]) + " cm round the chest on the seller's chart, room for a " + f.t.toLowerCase() + " fit." };
        }
      }
    }
    // no chart: estimate, matched to what the listing sells
    if (kind === "shoes") {
      var eu = shoeEu(b), opts = sold.map(function (s) { return [s, parseFloat(s)]; }).filter(function (x) { return x[1] >= 33 && x[1] <= 50; });
      var want = eu + (b.fit === "l" ? 0.5 : 0), hit2 = opts.filter(function (x) { return x[1] >= want - 0.01; })[0];
      return { size: hit2 ? hit2[0] : "EU " + want, chart: false, why: "Your usual EU " + eu + ". Most of these sellers use standard EU sizes." };
    }
    var s = 0.55 * (b.w - 50) / 10 + 0.45 * (b.h - 160) / 8 + 0.25 + f.step + (kind === "jacket" ? 0.5 : 0);
    var x = Math.max(0, Math.min(7, Math.floor(s))), a = Math.min(7, x + 1);
    if (kind === "pants") {
      var inch = Math.round(waistOf(b) / 2.54), nums = sold.map(function (z) { return [z, parseFloat(z)]; }).filter(function (z) { return z[1] >= 24 && z[1] <= 44; });
      if (nums.length) { var h3 = nums.filter(function (z) { return z[1] >= inch; })[0] || nums[nums.length - 1]; return { size: h3[0], chart: false, why: "Your waist is about " + inch + " inches." }; }
    }
    var letters = sold.filter(function (z) { return letterIdx(z) >= 0; });
    var label = L[a];
    if (letters.length) { var h4 = letters.filter(function (z) { return letterIdx(z) >= a; })[0] || letters[letters.length - 1]; label = h4; }
    return { size: label, chart: false, why: "You'd be " + L[x] + " in EU/US sizes. Chinese sizes run about one size small, so go one up." };
  }

  /* 23 Nov 2026 (owner: "a step in the signup where we ask for weight and height once, and then a subtle 'we recommend
     size X' on every product"): ask() is that step (height, weight, fit; app: right after sign-up, and once for members who
     signed up before), mount() the one-line note on a find. The size stays on the device ("pc.body"); "pc.size.asked" means
     the step was shown. Clothes only: height and weight can't size shoes. Signed out, the note invites a sign-up. */
  var AUTH_KEY = "sb-uptpghuduqjqmrxwatbm-auth-token";
  function member() {
    try { if (typeof ME !== "undefined" && ME) return true; } catch (e) {}
    try { var s = JSON.parse(localStorage.getItem(AUTH_KEY) || "null"); return !!(s && (s.user || (s.currentSession && s.currentSession.user))); } catch (e) { return false; }
  }
  function valid(b) { return !!b && b.h >= 130 && b.h <= 220 && b.w >= 35 && b.w <= 200; }
  function bodyText(b) {
    var imp = b.u === "i", fit = (FIT[b.fit] || FIT.r).t.toLowerCase();
    var h = imp ? Math.floor(b.h / 2.54 / 12) + " ft " + Math.round((b.h / 2.54) % 12) + " in" : Math.round(b.h) + " cm";
    return h + ", " + (imp ? Math.round(b.w / 0.4536) + " lb" : Math.round(b.w) + " kg") + ", " + fit + " fit";
  }
  var RULER = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.3 8.7 8.7 21.3a1 1 0 0 1-1.4 0l-4.6-4.6a1 1 0 0 1 0-1.4L15.3 2.7a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/></svg>';
  var CHEV = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
  // 23 Nov 2026 (owner: "so that the listing doesn't go down, extremely smooth"): the line keeps its height from the start
  // (no jump when the size arrives) and the details float over the page instead of pushing the buy button down.
  var CSS = ".pcrec-w{position:relative;min-height:30px;margin:8px 0 -2px}.pcrec{position:relative;display:inline-flex;align-items:center;gap:6px;min-height:30px;padding:0;border:0;background:none;color:var(--muted);font:inherit;font-size:13px;text-align:left;cursor:pointer;-webkit-tap-highlight-color:transparent;animation:pcrec-in .28s ease both}" +
    ".pcrec::before{content:\"\";position:absolute;inset:-7px -6px}@keyframes pcrec-in{from{opacity:0}to{opacity:1}}" +
    ".pcrec b{color:var(--ink);font-weight:600}.pcrec svg{flex:none}.pcrec-c{display:inline-flex;transition:transform .22s cubic-bezier(.2,.8,.2,1)}.pcrec[aria-expanded=true] .pcrec-c{transform:rotate(180deg)}.pcrec-ask span{text-decoration:underline;text-underline-offset:3px}" +
    "@media (hover:hover){.pcrec:hover{color:var(--ink)}}.pcrec:focus-visible{outline:2px solid var(--ink);outline-offset:3px;border-radius:6px}" +
    ".pcrec-d{position:absolute;left:0;top:calc(100% + 8px);z-index:40;box-sizing:border-box;width:min(420px,100%);max-height:min(70vh,560px);overflow:auto;overscroll-behavior:contain;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface);color:var(--ink);font-size:13px;line-height:1.45;" +
    "box-shadow:0 22px 48px -14px rgba(0,0,0,.38),0 2px 10px rgba(0,0,0,.12);opacity:0;visibility:hidden;transform:translateY(-6px) scale(.98);transform-origin:14px 0;pointer-events:none;" +
    "transition:opacity .16s ease,transform .24s cubic-bezier(.2,.8,.2,1),visibility 0s linear .24s}" +
    ".pcrec-w.open .pcrec-d{opacity:1;visibility:visible;transform:none;pointer-events:auto;transition:opacity .16s ease,transform .24s cubic-bezier(.2,.8,.2,1),visibility 0s}" +
    "@media (prefers-reduced-motion:reduce){.pcrec,.pcrec-d,.pcrec-w.open .pcrec-d,.pcrec-c{animation:none;transition:none}}" +
    ".pcrec-d p{margin:0 0 6px}.pcrec-s{color:var(--muted);font-size:12px}" +
    ".pcrec-e{min-height:40px;margin-top:2px;padding:0;border:0;background:none;color:var(--ink);font:inherit;font-size:13px;text-decoration:underline;text-underline-offset:3px;cursor:pointer}" +
    ".pcrec-d .pcsz-tw{max-width:100%;margin:8px 0 4px;overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px;background:var(--surface)}" +
    ".pcrec-d table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}.pcrec-d th,.pcrec-d td{padding:7px 9px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line)}" +
    ".pcrec-d thead th{font-weight:500;color:var(--muted)}.pcrec-d tbody tr:last-child>*{border-bottom:0}.pcrec-d tr.on>*{background:color-mix(in srgb,var(--ink) 9%,transparent);font-weight:600}" +
    ".pcsz-ov{position:fixed;inset:0;z-index:96;display:grid;place-items:center;padding:20px;overflow-y:auto;background:rgba(10,10,10,.55);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}" +
    ".pcsz-m{box-sizing:border-box;width:min(400px,calc(100vw - 32px));padding:26px 22px 18px;border-radius:22px;background:var(--surface,#fff);color:var(--ink,#111);box-shadow:0 30px 80px rgba(0,0,0,.35)}" +
    ".pcsz-m h2{margin:0;font-size:20px;line-height:1.2}.pcsz-sub{margin:8px 0 0;font-size:14px;line-height:1.45;color:var(--muted)}" +
    ".pcsz-g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-top:16px}.pcsz-g label{min-width:0;display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}" +
    ".pcsz-in{min-width:0;display:flex;align-items:center;gap:4px;box-sizing:border-box;height:46px;padding:0 12px;border:1px solid var(--line-2,var(--line));border-radius:12px;background:var(--surface)}" +
    ".pcsz-in:focus-within{border-color:var(--ink)}.pcsz-in input{flex:1;min-width:0;width:100%;padding:0;border:0;background:none;color:var(--ink);font:inherit;font-size:16px;outline:none}.pcsz-in span{color:var(--muted);font-size:13px}" +
    ".pcsz-fl{margin:14px 0 6px;font-size:12px;color:var(--muted)}.pcsz-seg{position:relative;display:flex;gap:2px;padding:3px;border-radius:999px;background:var(--surface-2)}" +
    // 24 Nov 2026 (owner: "make swapping between these clean and smooth"): one dark pill (.pcsz-thumb) slides under the
    // picked fit, the labels cross-fade their colour; a press scales the label a little. Reduced motion: no slide.
    ".pcsz-thumb{position:absolute;top:3px;bottom:3px;left:3px;width:calc((100% - 10px) / 3);border-radius:999px;background:var(--fill,var(--ink));pointer-events:none;transition:transform .32s cubic-bezier(.22,1,.36,1)}" +
    ".pcsz-seg[data-i=\"1\"] .pcsz-thumb{transform:translateX(calc(100% + 2px))}.pcsz-seg[data-i=\"2\"] .pcsz-thumb{transform:translateX(calc(200% + 4px))}" +
    ".pcsz-seg button{position:relative;z-index:1;flex:1;min-height:40px;padding:0 10px;border:0;border-radius:999px;background:none;color:var(--ink);font:inherit;font-size:14px;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:color .2s cubic-bezier(.22,1,.36,1),transform .12s cubic-bezier(.22,1,.36,1)}" +
    ".pcsz-seg button.on{color:var(--fill-ink,#fff);font-weight:600}.pcsz-seg button:active{transform:scale(.96)}" +
    "@media (prefers-reduced-motion:reduce){.pcsz-thumb{transition:none}.pcsz-seg button{transition:color .2s linear}.pcsz-seg button:active{transform:none}}" +
    ".pcsz-u{min-height:40px;margin-top:4px;padding:0;border:0;background:none;color:var(--muted);font:inherit;font-size:12px;text-decoration:underline;text-underline-offset:3px;cursor:pointer}" +
    ".pcsz-save{display:block;width:100%;height:48px;margin-top:10px;border:0;border-radius:999px;background:var(--fill,var(--ink));color:var(--fill-ink,#fff);font:inherit;font-size:15px;font-weight:600;cursor:pointer}.pcsz-save:disabled{opacity:.4;cursor:default}" +
    ".pcsz-skip{display:block;margin:4px auto 0;min-height:44px;padding:0 12px;border:0;background:none;color:var(--muted);font:inherit;font-size:14px;cursor:pointer}@media (hover:hover){.pcsz-skip:hover{color:var(--ink)}}" +
    ".pcsz-note{margin:2px 0 0;font-size:12px;color:var(--muted);text-align:center}";
  function css() { if (!document.getElementById("pcsz-css")) { var st = document.createElement("style"); st.id = "pcsz-css"; st.textContent = CSS; document.head.appendChild(st); } }
  // the seller's chart, shown when the note is opened; ranges (height, weight) as "170-180"
  var COLS = [["h", "Height"], ["w", "Weight"], ["ch", "Chest"], ["sh", "Shoulder"], ["le", "Length"], ["wa", "Waist"], ["hi", "Hip"], ["in", "Inseam"]];
  function num(x, imp, kg) { var v = imp ? (kg ? x / 0.4536 : x / 2.54) : x; v = Math.round(v * 10) / 10; return String(v).replace(/\.0$/, ""); }
  function cell(m, k, imp) {
    if (k === "h") return m.h0 ? num(m.h0, imp) + (m.h1 && m.h1 !== m.h0 ? "-" + num(m.h1, imp) : "") : "";
    if (k === "w") return m.w0 ? num(m.w0, imp, 1) + (m.w1 && m.w1 !== m.w0 ? "-" + num(m.w1, imp, 1) : "") : "";
    return m[k] ? num(m[k], imp) : "";
  }
  function chartHtml(d, size, imp) {
    var rows = (d && d.c) || []; if (rows.length < 2) return "";
    var cols = COLS.filter(function (c) { return rows.some(function (r) { return cell(r[1], c[0], imp) !== ""; }); });
    if (!cols.length) return "";
    var mode = d.m === "flat" ? ", measured flat" : d.m === "round" ? ", measured all the way round" : d.m === "body" ? ", body measurements" : "";
    var mine = size ? norm(size) : "";
    return '<p class="pcrec-s">The seller\'s size chart, in ' + (imp ? "inches" : "cm") + (cols.some(function (c) { return c[0] === "w"; }) ? (imp ? " and lb" : " and kg") : "") + mode + ".</p>" +
      '<div class="pcsz-tw"><table><thead><tr><th scope="col">Size</th>' + cols.map(function (c) { return '<th scope="col">' + c[1] + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) { return "<tr" + (mine && norm(r[0]) === mine ? ' class="on"' : "") + '><th scope="row">' + esc(r[0]) + "</th>" + cols.map(function (c) { return "<td>" + cell(r[1], c[0], imp) + "</td>"; }).join("") + "</tr>"; }).join("") +
      "</tbody></table></div>";
  }
  function signUp() {
    if (typeof openAuth === "function") { try { openAuth(); return; } catch (e) {} }
    location.href = "/?signin=1";
  }

  // the one-line note on a find
  function mount(el, p) {
    var kind = CATS[p && p.cat]; if (!el || !kind || kind === "shoes" || el.getAttribute("data-pcsz")) return; el.setAttribute("data-pcsz", "1");
    css(); el.className = "pcrec-w";
    var data = null, loaded = false, open = false;
    function render() {
      var b = store();
      if (!valid(b)) {
        var signed = member();
        el.innerHTML = '<button type="button" class="pcrec pcrec-ask">' + RULER + "<span>" + (signed ? "Get your size on every find" : "Sign up to see your size") + "</span></button>";
        el.firstChild.addEventListener("click", function () { if (member()) ask(); else signUp(); });
        return;
      }
      if (!loaded) { el.innerHTML = ""; return; }   // the line keeps its height (.pcrec-w min-height) until the size arrives
      var r = pick(kind, { h: b.h, w: b.w, fit: b.fit || "r", eu: b.eu }, data);
      if (!r || r.ask || !r.size) { el.innerHTML = ""; return; }
      el.innerHTML = '<button type="button" class="pcrec" aria-expanded="' + open + '" aria-controls="' + did + '">' + RULER + "<span>We recommend size <b>" + esc(r.size) + '</b></span><span class="pcrec-c">' + CHEV + "</span></button>" +
        '<div class="pcrec-d" id="' + did + '" role="region" aria-label="Your size" aria-hidden="' + !open + '"><p>' + r.why + '</p><p class="pcrec-s">' + (r.chart ? "From this listing\'s size chart" : "An estimate: this listing has no size chart we could read, so when in doubt ask the seller through your agent") +
        ". For " + bodyText(b) + ".</p>" + (r.chart ? chartHtml(data, r.size, b.u === "i") : "") + '<button type="button" class="pcrec-e">Change my size</button></div>';
      el.querySelector(".pcrec").addEventListener("click", function () { setOpen(!open); });
      el.querySelector(".pcrec-e").addEventListener("click", function () { setOpen(false); ask(); });
    }
    var did = "pcrec-" + String(p.id).replace(/[^\w-]/g, "");
    function outside(e) { if (!el.contains(e.target)) setOpen(false); }
    function onKey(e) { if (e.key !== "Escape" || !open) return; e.preventDefault(); e.stopImmediatePropagation(); setOpen(false); var t = el.querySelector(".pcrec"); if (t) try { t.focus({ preventScroll: true }); } catch (x) {} }
    function setOpen(v) {
      open = !!v; el.classList.toggle("open", open);
      var t = el.querySelector(".pcrec"), d = el.querySelector(".pcrec-d");
      if (t) t.setAttribute("aria-expanded", open ? "true" : "false"); if (d) d.setAttribute("aria-hidden", open ? "false" : "true");
      document.removeEventListener("pointerdown", outside, true); window.removeEventListener("keydown", onKey, true);
      if (open) { document.addEventListener("pointerdown", outside, true); window.addEventListener("keydown", onKey, true); }
    }
    function onSize() { if (!el.isConnected) { window.removeEventListener("pc-size", onSize); setOpen(false); return; } render(); if (open) setOpen(true); }
    window.addEventListener("pc-size", onSize);
    render();
    load(p.id).then(function (d) { data = d; loaded = true; render(); });
  }

  // the size step: height, weight and fit, once
  function ask() {
    css(); if (document.getElementById("pcsz-ask")) return;
    var b = store(), imp = b.u === "i", fit = b.fit || "r", prev = document.activeElement;
    var ov = document.createElement("div"); ov.id = "pcsz-ask"; ov.className = "pcsz-ov";
    ov.innerHTML = '<div class="pcsz-m" role="dialog" aria-modal="true" aria-labelledby="pcsz-h"><h2 id="pcsz-h">Get your size on every find</h2>' +
      '<p class="pcsz-sub">Tell us your height, weight and how you like things to fit. We\'ll show the size to pick on every find.</p><div class="pcsz-f"></div>' +
      '<button type="button" class="pcsz-save" disabled>Save my size</button><button type="button" class="pcsz-skip">Skip for now</button><p class="pcsz-note">Saved on this device. You can change it on any find.</p></div>';
    document.body.appendChild(ov);
    var box = ov.querySelector(".pcsz-f"), saveBtn = ov.querySelector(".pcsz-save");
    function v(k) { var i = box.querySelector('[data-k="' + k + '"]'); return i ? parseFloat(String(i.value).replace(",", ".")) : NaN; }
    function read() {
      var h = imp ? (v("ft") * 12 + (v("in") || 0)) * 2.54 : v("h"), w = imp ? v("w") * 0.4536 : v("w");
      return { h: Math.round(h) || 0, w: Math.round(w * 10) / 10 || 0, fit: fit, u: imp ? "i" : "", eu: b.eu || 0 };
    }
    function form() {
      var cur = read();
      box.innerHTML = '<div class="pcsz-g">' +
        (imp ? '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="ft" placeholder="5" aria-label="Height, feet"><span>ft</span><input inputmode="numeric" data-k="in" placeholder="10" aria-label="Height, inches"><span>in</span></div></label>'
          : '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="h" placeholder="178"><span>cm</span></div></label>') +
        '<label>Weight<div class="pcsz-in"><input inputmode="numeric" data-k="w" placeholder="' + (imp ? "165" : "75") + '"><span>' + (imp ? "lb" : "kg") + "</span></div></label></div>" +
        '<button type="button" class="pcsz-u">' + (imp ? "Use cm and kg" : "Use ft and lb") + '</button><p class="pcsz-fl">How do you like things to fit?</p>' +
        '<div class="pcsz-seg" role="group" aria-label="Fit" data-i="' + ["s", "r", "l"].indexOf(fit) + '"><span class="pcsz-thumb" aria-hidden="true"></span>' + ["s", "r", "l"].map(function (k) { return '<button type="button" data-fit="' + k + '" aria-pressed="' + (k === fit) + '"' + (k === fit ? ' class="on"' : "") + ">" + FIT[k].t + "</button>"; }).join("") + "</div>";
      var src = valid(cur) ? cur : b, set = function (k, x) { var i = box.querySelector('[data-k="' + k + '"]'); if (i && x) i.value = x; };
      if (src.h) { if (imp) { var t = src.h / 2.54; set("ft", Math.floor(t / 12)); set("in", Math.round(t % 12)); } else set("h", Math.round(src.h)); }
      if (src.w) set("w", Math.round(imp ? src.w / 0.4536 : src.w));
      [].forEach.call(box.querySelectorAll("input"), function (i) { i.addEventListener("input", check); });
      [].forEach.call(box.querySelectorAll("[data-fit]"), function (x) { x.addEventListener("click", function () { fit = x.getAttribute("data-fit");
        x.parentNode.setAttribute("data-i", String(["s", "r", "l"].indexOf(fit)));
        [].forEach.call(box.querySelectorAll("[data-fit]"), function (y) { var on = y === x; y.classList.toggle("on", on); y.setAttribute("aria-pressed", on ? "true" : "false"); }); }); });
      box.querySelector(".pcsz-u").addEventListener("click", function () { imp = !imp; form(); });
      check();
    }
    function check() { saveBtn.disabled = !valid(read()); }
    function key(e) {
      if (e.key === "Escape") { e.stopImmediatePropagation(); close(false); return; }
      if (e.key !== "Tab") return;
      var f = [].filter.call(ov.querySelectorAll("button,input"), function (x) { return !x.disabled && x.offsetParent !== null; }); if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    function close(saved) {
      try { localStorage.setItem("pc.size.asked", "1"); } catch (e) {}
      document.removeEventListener("keydown", key, true); ov.remove();
      try { if (prev && prev.focus) prev.focus({ preventScroll: true }); } catch (e) {}
      if (saved) try { window.dispatchEvent(new Event("pc-size")); } catch (e) {}
    }
    saveBtn.addEventListener("click", function () { var nb = read(); if (!valid(nb)) return; nb.t = Date.now(); save(nb); close(true); });   // t: the newer copy wins against the account's (index.html pcSizeSync)
    ov.querySelector(".pcsz-skip").addEventListener("click", function () { close(false); });
    ov.addEventListener("click", function (e) { if (e.target === ov) close(false); });
    document.addEventListener("keydown", key, true);
    form();
    var f0 = box.querySelector("input"); if (f0) try { f0.focus({ preventScroll: true }); } catch (e) {}
  }
  window.pcSize = { mount: mount, pick: pick, ask: ask };
  [].forEach.call(document.querySelectorAll("[data-pcsz-id]"), function (el) { mount(el, { id: el.getAttribute("data-pcsz-id"), cat: el.getAttribute("data-pcsz-cat") }); });
})();
