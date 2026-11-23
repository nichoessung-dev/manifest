/* Size helper on product pages and in the app's find view (owner, 19 Nov 2026: "make a size recomendation based on users
   weigth and heigth"). The visitor types height and weight once (kept in localStorage "pc.body") and picks a fit; the
   helper answers with one of the sizes the listing sells.
   1. The seller's chart (data/sizes/<last two digits>.json, scripts/bake_sizes.py from scripts/listing_details.py):
      recommended height/weight ranges first, else chest (tops, jackets), waist (pants, shorts) or foot length (shoes)
      compared with the body measure estimated from height and weight plus room for the fit.
   2. No chart: the same estimate as /tools/size-estimator (functions/_lib/tools9.js sizeFor), one size up for Chinese
      sizing, matched to the listing's own size names.
   window.pcSize.mount(el, {id, cat, g}) fills el. Clothes and shoes only.
   23 Nov 2026 (owner: "a size chart and a recommended size for every visitor"): always open, the size up front once height
   and weight are known, and the seller's chart as a table with that size highlighted (was a folded "Find my size" row). */
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
      var hw = rows.filter(function (r) { return r[1].h0 && r[1].w0; });
      if (hw.length >= 2 && kind !== "shoes") {
        var best = null, bs = 1e9, sc = [];
        hw.forEach(function (r, i) { var m = r[1], s = dist(b.h, m.h0, m.h1 || m.h0) / 3 + dist(b.w, m.w0, m.w1 || m.w0) / 2; sc.push(s); if (s < bs - 0.01) { bs = s; best = i; } });
        var near = best + 1 < hw.length && sc[best + 1] - bs < 0.6 ? hw[best + 1][0] : "";
        var j = Math.max(0, Math.min(hw.length - 1, best + (b.fit === "l" ? 1 : 0)));
        var m = hw[best][1];
        return { size: hw[j][0], chart: true, why: "The seller's chart suggests " + esc(hw[best][0]) + " for " + Math.round(m.h0) + " to " + Math.round(m.h1 || m.h0) + " cm and " + Math.round(m.w0) + " to " + Math.round(m.w1 || m.w0) + " kg." + (j !== best ? " One size up for a loose fit." : near && b.fit !== "l" ? " You're between " + esc(hw[best][0]) + " and " + esc(near) + ": take " + esc(near) + " if you like more room." : "") };
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

  /* The card (owner, 23 Nov 2026: "a size chart and a recommended size for every visitor based on weight and height").
     Always open under the buy button. First time: height and weight right there. After that: "Recommended: L" on every
     find, the fit, and the seller's size chart as a table with that size highlighted. */
  var CSS = ".pcsz{min-width:0;max-width:100%;box-sizing:border-box;margin-top:16px;padding:14px;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--ink)}" +
    ".pcsz-hd{display:flex;align-items:center;gap:10px;min-height:32px}.pcsz-hd .ic{width:28px;height:28px;border-radius:50%;background:var(--surface-2);display:grid;place-items:center;flex:none}" +
    ".pcsz-t{margin:0;font-size:15px;font-weight:600;line-height:1.2}.pcsz-edit{margin:-6px -4px -6px auto;min-height:44px;padding:0 6px;border:0;background:none;color:var(--muted);font:inherit;font-size:13px;text-decoration:underline;text-underline-offset:3px;cursor:pointer}" +
    ".pcsz-sub{margin:6px 0 0;font-size:13px;line-height:1.45;color:var(--muted)}" +
    ".pcsz-g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-top:12px}.pcsz-g label{min-width:0;display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}" +
    ".pcsz-in{min-width:0;display:flex;align-items:center;gap:4px;box-sizing:border-box;height:44px;padding:0 12px;border:1px solid var(--line-2,var(--line));border-radius:12px;background:var(--surface)}" +
    ".pcsz-in:focus-within{border-color:var(--ink)}.pcsz-in input{flex:1;min-width:0;width:100%;padding:0;border:0;background:none;color:var(--ink);font:inherit;font-size:16px;outline:none}.pcsz-in span{color:var(--muted);font-size:13px}" +
    ".pcsz-row{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}" +
    ".pcsz-seg{display:inline-flex;gap:2px;padding:3px;border-radius:999px;background:var(--surface-2)}.pcsz-seg button{min-height:38px;padding:0 14px;border:0;border-radius:999px;background:none;color:var(--ink);font:inherit;font-size:13px;cursor:pointer}" +
    ".pcsz-seg button.on{background:var(--fill,var(--ink));color:var(--fill-ink,#fff)}.pcsz-u{min-height:44px;margin-left:auto;padding:0 2px;border:0;background:none;color:var(--muted);font:inherit;font-size:12px;text-decoration:underline;text-underline-offset:3px;cursor:pointer}" +
    ".pcsz-res{margin-top:12px;padding:14px;border-radius:12px;background:var(--surface-2)}.pcsz-rec{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}" +
    ".pcsz-rl{font-size:13px;color:var(--muted)}.pcsz-rec b{font-size:26px;line-height:1.1}.pcsz-for{font-size:13px;color:var(--muted)}" +
    ".pcsz-why{margin:6px 0 0;font-size:13px;line-height:1.45}.pcsz-src{margin:6px 0 0;font-size:12px;line-height:1.45;color:var(--muted)}" +
    ".pcsz-ch{margin-top:14px}.pcsz-chh{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px 8px;font-size:14px;font-weight:600}.pcsz-chh span{font-size:12px;font-weight:400;color:var(--muted)}" +
    ".pcsz-tw{max-width:100%;margin-top:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:12px}" +
    ".pcsz table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}.pcsz th,.pcsz td{padding:9px 10px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line);color:var(--ink)}" +
    ".pcsz thead th{font-size:12px;font-weight:500;color:var(--muted);background:var(--surface-2)}.pcsz tbody tr:last-child>*{border-bottom:0}.pcsz tbody th{font-weight:600}" +
    ".pcsz tr.on>*{background:color-mix(in srgb,var(--ink) 9%,transparent)}.pcsz tr.on th small{margin-left:6px;font-size:11px;font-weight:500;color:var(--muted)}" +
    ".pcsz-sold{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:12px;font-size:12px;color:var(--muted)}" +
    ".pcsz-sold i{font-style:normal;min-width:36px;height:32px;box-sizing:border-box;padding:0 10px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line-2,var(--line));border-radius:8px;font-size:13px;color:var(--ink)}" +
    ".pcsz-sold i.on{background:var(--fill,var(--ink));color:var(--fill-ink,#fff);border-color:transparent}";
  var RULER = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.3 8.7 8.7 21.3a1 1 0 0 1-1.4 0l-4.6-4.6a1 1 0 0 1 0-1.4L15.3 2.7a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/></svg>';
  // chart columns in this order; ranges (height, weight) show as "170-180"
  var COLS = [["h", "Height"], ["w", "Weight"], ["ch", "Chest"], ["sh", "Shoulder"], ["le", "Length"], ["wa", "Waist"], ["hi", "Hip"], ["in", "Inseam"], ["ft", "Foot"]];
  function num(x, imp, kg) { if (x == null || x === "") return ""; var v = imp ? (kg ? x / 0.4536 : x / 2.54) : x; v = Math.round(v * 10) / 10; return String(v).replace(/\.0$/, ""); }
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
    var units = imp ? "inches" + (cols.some(function (c) { return c[0] === "w"; }) ? " and lb" : "") : "cm" + (cols.some(function (c) { return c[0] === "w"; }) ? " and kg" : "");
    var mine = size ? norm(size) : "";
    return '<div class="pcsz-ch"><div class="pcsz-chh">Size chart<span>From the seller, in ' + units + mode + '</span></div><div class="pcsz-tw"><table><thead><tr><th scope="col">Size</th>' +
      cols.map(function (c) { return '<th scope="col">' + c[1] + "</th>"; }).join("") + "</tr></thead><tbody>" +
      rows.map(function (r) { var on = mine && norm(r[0]) === mine; return "<tr" + (on ? ' class="on"' : "") + '><th scope="row">' + esc(r[0]) + (on ? "<small>Yours</small>" : "") + "</th>" +
        cols.map(function (c) { return "<td>" + (cell(r[1], c[0], imp) || "") + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div></div>";
  }
  function soldHtml(d, size) {
    var sold = ((d && d.s) || []).filter(function (s) { return s && s.length <= 8; }); if (!sold.length || (d && d.c && d.c.length >= 2)) return "";
    var mine = size ? norm(size) : "";
    return '<div class="pcsz-sold"><span>Sizes this listing sells:</span>' + sold.slice(0, 16).map(function (s) { return "<i" + (mine && norm(s) === mine ? ' class="on"' : "") + ">" + esc(s) + "</i>"; }).join("") + "</div>";
  }

  function mount(el, p) {
    var kind = CATS[p && p.cat]; if (!el || !kind || el.getAttribute("data-pcsz")) return; el.setAttribute("data-pcsz", "1");
    if (!document.getElementById("pcsz-css")) { var st = document.createElement("style"); st.id = "pcsz-css"; st.textContent = CSS; document.head.appendChild(st); }
    var b = store(), imp = b.u === "i", fit = b.fit || "r", data = null, loaded = false, shoe = kind === "shoes";
    var ok = function () { return b.h >= 130 && b.h <= 220 && b.w >= 35 && b.w <= 200 && (!shoe || b.eu >= 33); };
    var editing = !ok();
    el.className = "pcsz";
    el.innerHTML = '<div class="pcsz-hd"><span class="ic">' + RULER + '</span><h3 class="pcsz-t">Your size</h3><button type="button" class="pcsz-edit" hidden>Edit</button></div>' +
      '<div class="pcsz-f"></div><div class="pcsz-out" aria-live="polite"></div><div class="pcsz-c"></div>';
    var edit = el.querySelector(".pcsz-edit"), fbox = el.querySelector(".pcsz-f"), out = el.querySelector(".pcsz-out"), cbox = el.querySelector(".pcsz-c");
    function bodyText() {
      var h = imp ? Math.floor(b.h / 2.54 / 12) + " ft " + Math.round((b.h / 2.54) % 12) + " in" : Math.round(b.h) + " cm";
      var w = imp ? Math.round(b.w / 0.4536) + " lb" : Math.round(b.w) + " kg";
      return "For " + h + ", " + w + (shoe && b.eu ? ", EU " + b.eu : "") + ", " + FIT[fit].t.toLowerCase() + " fit";
    }
    function segHtml() { return '<div class="pcsz-seg" role="group" aria-label="Fit">' + ["s", "r", "l"].map(function (k) { return '<button type="button" data-fit="' + k + '" aria-pressed="' + (k === fit) + '"' + (k === fit ? ' class="on"' : "") + ">" + FIT[k].t + "</button>"; }).join("") + "</div>"; }
    function wireSeg(box) { [].forEach.call(box.querySelectorAll("[data-fit]"), function (x) { x.addEventListener("click", function () { fit = x.getAttribute("data-fit"); if (ok()) { b.fit = fit; save(b); } [].forEach.call(box.querySelectorAll("[data-fit]"), function (y) { var on = y === x; y.classList.toggle("on", on); y.setAttribute("aria-pressed", on); }); result(); }); }); }
    function form() {
      edit.hidden = true;
      fbox.innerHTML = '<p class="pcsz-sub">Enter it once and every find shows your size. Saved on this device only.</p><div class="pcsz-g">' +
        (imp ? '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="ft" placeholder="5" aria-label="Height, feet"><span>ft</span><input inputmode="numeric" data-k="in" placeholder="10" aria-label="Height, inches"><span>in</span></div></label>'
          : '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="h" placeholder="178"><span>cm</span></div></label>') +
        '<label>Weight<div class="pcsz-in"><input inputmode="numeric" data-k="w" placeholder="' + (imp ? "165" : "75") + '"><span>' + (imp ? "lb" : "kg") + "</span></div></label>" +
        (shoe ? '<label style="grid-column:1/-1">Your usual shoe size (EU)<div class="pcsz-in"><input inputmode="decimal" data-k="eu" placeholder="43"><span>EU</span></div></label>' : "") + "</div>" +
        '<div class="pcsz-row">' + segHtml() + '<button type="button" class="pcsz-u">' + (imp ? "Use cm and kg" : "Use ft and lb") + "</button></div>";
      var v = function (k) { var i = fbox.querySelector('[data-k="' + k + '"]'); return i ? parseFloat(String(i.value).replace(",", ".")) : NaN; };
      var set = function (k, x) { var i = fbox.querySelector('[data-k="' + k + '"]'); if (i && x) i.value = x; };
      if (b.h) { if (imp) { var t = b.h / 2.54; set("ft", Math.floor(t / 12)); set("in", Math.round(t % 12)); } else set("h", Math.round(b.h)); }
      if (b.w) set("w", Math.round(imp ? b.w / 0.4536 : b.w));
      if (b.eu) set("eu", b.eu);
      function read() {
        var h = imp ? (v("ft") * 12 + (v("in") || 0)) * 2.54 : v("h"), w = imp ? v("w") * 0.4536 : v("w"), eu = v("eu");
        b = { h: Math.round(h) || 0, w: Math.round(w * 10) / 10 || 0, fit: fit, u: imp ? "i" : "", eu: eu >= 33 && eu <= 50 ? eu : (b.eu || 0) };
        if (ok()) save(b);
        result();
      }
      [].forEach.call(fbox.querySelectorAll("input"), function (i) { i.addEventListener("input", read); });
      wireSeg(fbox);
      fbox.querySelector(".pcsz-u").addEventListener("click", function () { imp = !imp; b.u = imp ? "i" : ""; if (ok()) save(b); form(); result(); });
    }
    function summary() {
      edit.hidden = false;
      fbox.innerHTML = '<div class="pcsz-row">' + segHtml() + "</div>";
      wireSeg(fbox);
    }
    function result() {
      var r = ok() && loaded ? pick(kind, { h: b.h, w: b.w, fit: fit, eu: b.eu }, data) : null;
      if (!ok()) out.innerHTML = "";
      else if (!loaded) out.innerHTML = '<div class="pcsz-res"><p class="pcsz-src">Checking the seller\'s size chart...</p></div>';
      else if (r.ask || !r.size) out.innerHTML = '<div class="pcsz-res"><p class="pcsz-why">' + r.why + "</p></div>";
      else out.innerHTML = '<div class="pcsz-res"><div class="pcsz-rec"><span class="pcsz-rl">Recommended</span><b>' + esc(r.size) + '</b><span class="pcsz-for">' + bodyText() + "</span></div>" +
        '<p class="pcsz-why">' + r.why + '</p><p class="pcsz-src">' + (r.chart ? "Based on this listing's size chart." : "An estimate: this listing has no size chart we could read. When in doubt, ask the seller through your agent.") + "</p></div>";
      var size = r && !r.ask ? r.size : "";
      cbox.innerHTML = loaded ? chartHtml(data, size, imp) + soldHtml(data, size) : "";
    }
    edit.addEventListener("click", function () { editing = true; form(); result(); var f = fbox.querySelector("input"); if (f) try { f.focus({ preventScroll: true }); } catch (e) {} });
    if (editing) form(); else summary();
    result();
    load(p.id).then(function (d) { data = d; loaded = true; result(); });
  }
  window.pcSize = { mount: mount, pick: pick };
  [].forEach.call(document.querySelectorAll("[data-pcsz-id]"), function (el) { mount(el, { id: el.getAttribute("data-pcsz-id"), cat: el.getAttribute("data-pcsz-cat") }); });
})();
