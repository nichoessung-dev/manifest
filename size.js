/* Size helper on product pages and in the app's find view (owner, 19 Nov 2026: "make a size recomendation based on users
   weigth and heigth"). The visitor types height and weight once (kept in localStorage "pc.body") and picks a fit; the
   helper answers with one of the sizes the listing sells.
   1. The seller's chart (data/sizes/<last two digits>.json, scripts/bake_sizes.py from scripts/listing_details.py):
      recommended height/weight ranges first, else chest (tops, jackets), waist (pants, shorts) or foot length (shoes)
      compared with the body measure estimated from height and weight plus room for the fit.
   2. No chart: the same estimate as /tools/size-estimator (functions/_lib/tools9.js sizeFor), one size up for Chinese
      sizing, matched to the listing's own size names.
   window.pcSize.mount(el, {id, cat, g}) fills el. Clothes and shoes only. */
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
    if (!cache[k]) cache[k] = fetch("/data/sizes/" + k + ".json").then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
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

  var CSS = ".pcsz{min-width:0;max-width:100%;margin-top:14px;border-top:1px solid var(--line);padding-top:4px}.pcsz-b{display:flex;align-items:center;gap:10px;width:100%;min-height:44px;border:0;background:none;color:var(--ink);font:inherit;font-size:14px;font-weight:500;text-align:left;cursor:pointer;padding:0}" +
    ".pcsz-b .ic{width:28px;height:28px;border-radius:50%;background:var(--surface-2);display:grid;place-items:center;flex:none}.pcsz-b .r{margin-left:auto;color:var(--muted);font-weight:400}" +
    ".pcsz-p{padding:6px 0 10px}.pcsz-g{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px}.pcsz-g label{min-width:0;display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}" +
    ".pcsz-in{min-width:0;display:flex;align-items:center;border:1px solid var(--line-2,var(--line));border-radius:12px;padding:0 10px;height:42px;background:var(--surface)}.pcsz-in input{flex:1;min-width:0;width:100%;border:0;background:none;color:var(--ink);font:inherit;font-size:15px;outline:none}" +
    ".pcsz-in span{color:var(--muted);font-size:13px}.pcsz-seg{display:flex;gap:6px;margin:10px 0 0}.pcsz-seg button{flex:1;min-width:0;height:36px;border-radius:999px;border:1px solid var(--line-2,var(--line));background:none;color:var(--ink);font:inherit;font-size:13px;cursor:pointer}" +
    ".pcsz-seg button.on{background:var(--ink);color:var(--bg,#fff);border-color:transparent}.pcsz-u{border:0;background:none;color:var(--muted);font:inherit;font-size:12px;text-decoration:underline;cursor:pointer;padding:0;margin-top:8px}" +
    ".pcsz-out{margin-top:12px;padding:14px;border-radius:14px;background:var(--surface-2)}.pcsz-out b{font-size:22px;display:block;line-height:1.2}.pcsz-out p{margin:4px 0 0;font-size:13px;color:var(--muted);line-height:1.45}.pcsz-out small{display:block;margin-top:6px;font-size:12px;color:var(--muted)}";

  function mount(el, p) {
    var kind = CATS[p && p.cat]; if (!el || !kind || el.getAttribute("data-pcsz")) return; el.setAttribute("data-pcsz", "1");
    if (!document.getElementById("pcsz-css")) { var st = document.createElement("style"); st.id = "pcsz-css"; st.textContent = CSS; document.head.appendChild(st); }
    var b = store(), imp = b.u === "i", data, loaded = false;
    var RULER = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.3 8.7 8.7 21.3a1 1 0 0 1-1.4 0l-4.6-4.6a1 1 0 0 1 0-1.4L15.3 2.7a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/></svg>';
    el.className = "pcsz";
    el.innerHTML = '<button type="button" class="pcsz-b" aria-expanded="false"><span class="ic">' + RULER + '</span><span>Find my size</span><span class="r"></span></button><div class="pcsz-p" hidden></div>';
    var btn = el.querySelector(".pcsz-b"), pane = el.querySelector(".pcsz-p"), right = el.querySelector(".r");
    function form() {
      var shoe = kind === "shoes";
      pane.innerHTML = '<div class="pcsz-g">' +
        (imp ? '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="ft" placeholder="5"><span>ft</span><input inputmode="numeric" data-k="in" placeholder="10"><span>in</span></div></label>'
          : '<label>Height<div class="pcsz-in"><input inputmode="numeric" data-k="h" placeholder="178"><span>cm</span></div></label>') +
        '<label>Weight<div class="pcsz-in"><input inputmode="numeric" data-k="w" placeholder="' + (imp ? "165" : "75") + '"><span>' + (imp ? "lb" : "kg") + "</span></div></label>" +
        (shoe ? '<label style="grid-column:1/-1">Your usual shoe size (EU, optional)<div class="pcsz-in"><input inputmode="decimal" data-k="eu" placeholder="43"><span>EU</span></div></label>' : "") + "</div>" +
        '<div class="pcsz-seg" role="group" aria-label="Fit">' + ["s", "r", "l"].map(function (k) { return '<button type="button" data-fit="' + k + '">' + FIT[k].t + "</button>"; }).join("") + "</div>" +
        '<button type="button" class="pcsz-u">' + (imp ? "Use cm and kg" : "Use ft and lb") + '</button><div class="pcsz-out" hidden aria-live="polite"></div>';
      var v = function (k) { var i = pane.querySelector('[data-k="' + k + '"]'); return i ? parseFloat(String(i.value).replace(",", ".")) : NaN; };
      var set = function (k, x) { var i = pane.querySelector('[data-k="' + k + '"]'); if (i && x) i.value = x; };
      if (b.h) { if (imp) { var t = b.h / 2.54; set("ft", Math.floor(t / 12)); set("in", Math.round(t % 12)); } else set("h", Math.round(b.h)); }
      if (b.w) set("w", Math.round(imp ? b.w / 0.4536 : b.w));
      if (b.eu) set("eu", b.eu);
      var fit = b.fit || "r";
      function seg() { [].forEach.call(pane.querySelectorAll("[data-fit]"), function (x) { x.classList.toggle("on", x.getAttribute("data-fit") === fit); }); }
      seg();
      function run() {
        var h = imp ? (v("ft") * 12 + (v("in") || 0)) * 2.54 : v("h"), w = imp ? v("w") * 0.4536 : v("w"), eu = v("eu");
        var out = pane.querySelector(".pcsz-out");
        if (!(h >= 130 && h <= 220 && w >= 35 && w <= 200)) { out.hidden = true; right.textContent = ""; return; }
        b = { h: Math.round(h), w: Math.round(w * 10) / 10, fit: fit, u: imp ? "i" : "", eu: eu >= 33 && eu <= 50 ? eu : (b.eu || 0) }; save(b);
        if (!loaded) { out.hidden = false; out.innerHTML = "<p>Checking the seller's size chart...</p>"; return; }
        var r = pick(kind, b, data);
        out.hidden = false;
        if (r.ask) { out.innerHTML = "<p>" + r.why + "</p>"; right.textContent = ""; return; }
        out.innerHTML = "<b>Size " + esc(r.size) + "</b><p>" + r.why + "</p><small>" + (r.chart ? "Based on this listing's size chart." : "An estimate: this listing has no size chart we could read. When in doubt, ask the seller through your agent.") + "</small>";
        right.textContent = "Size " + r.size;
      }
      [].forEach.call(pane.querySelectorAll("input"), function (i) { i.addEventListener("input", run); });
      [].forEach.call(pane.querySelectorAll("[data-fit]"), function (x) { x.addEventListener("click", function () { fit = x.getAttribute("data-fit"); seg(); run(); }); });
      pane.querySelector(".pcsz-u").addEventListener("click", function () { imp = !imp; b.u = imp ? "i" : ""; save(b); form(); });
      el.__run = run; run();
    }
    btn.addEventListener("click", function () {
      var open = pane.hidden; pane.hidden = !open; btn.setAttribute("aria-expanded", open ? "true" : "false");
      if (open && !pane.firstChild) form();
      if (open) { var f = pane.querySelector("input"); if (f && !f.value) try { f.focus({ preventScroll: true }); } catch (e) {} }
    });
    load(p.id).then(function (d) { data = d; loaded = true; if (el.__run) el.__run(); else if (b.h && b.w) { var r = pick(kind, { h: b.h, w: b.w, fit: b.fit || "r", eu: b.eu }, d); if (r.size) right.textContent = "Size " + r.size; } });
  }
  window.pcSize = { mount: mount, pick: pick };
  [].forEach.call(document.querySelectorAll("[data-pcsz-id]"), function (el) { mount(el, { id: el.getAttribute("data-pcsz-id"), cat: el.getAttribute("data-pcsz-cat") }); });
})();
