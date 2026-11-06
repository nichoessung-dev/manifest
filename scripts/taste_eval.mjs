#!/usr/bin/env node
/* Offline check of the recommender (6 Nov 2026): how well the Swipe feed (feed.html) and the spreadsheet's "For you" sort
   (index.html, pcForYou) learn a visitor, from what that visitor did on the OTHER surface and on their own.

   Runs the real code from the two pages in a sandbox (Node's vm, a fake DOM, a fake clock, a seeded Math.random), with
   simulated visitors ("personas") who each have a hidden taste:
     black       likes black clothes and shoes
     rl-knits    likes Ralph Lauren knitwear (a little: other RL tops, other knits)
     cheap-shoes likes shoes under 150 CNY (about $20)
     mixed       likes Stone Island, Nike/Jordan sneakers and white tees
   Four experiments, each scored with hit@20 (how many of the first 20 finds the persona likes, expected value) and AUC
   (chance a liked find ranks above a not-liked one over the whole catalogue; 50% = guessing):
     A  sheet -> feed    the persona only uses the spreadsheet (filters, search, opens, hovers, scrolls past, saves,
                         unsaves, a QC look, a buy click), then opens the feed: the first 20 cards it deals.
     B  feed -> sheet    the persona only swipes 40 cards in the feed (with "Show less" and "Not interested" now and
                         then), then sorts the spreadsheet by For you: the first 20 rows.
     C  feed alone       30 swipes from a fresh start: likes in cards 21-30 (out of 10) and the feed's own measured AUC.
     D  both -> sheet    A's spreadsheet session, then B's swipes, then For you.
   What the spreadsheet logs is what track.js (and the hooks in index.html) of the given version log, so an old copy of
   the site is judged on the signals it really had.

   Usage:  node scripts/taste_eval.mjs [--dir <site folder>] [--seeds 5] [--persona black] [--json]   (DEBUG=1 prints top rows)
     --dir   folder with feed.html, index.html, track.js (default: this repo). The catalogue comes from index.html's inline
             copy and the view counts from data/stats.json in the same folder. Nothing is fetched or sent anywhere. */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2), opt = (k, d) => { const i = args.indexOf("--" + k); return i >= 0 ? args[i + 1] : d; };
const DIR = path.resolve(opt("dir", path.join(path.dirname(fileURLToPath(import.meta.url)), "..")));
const SEEDS = +opt("seeds", 5), ONLY = opt("persona", ""), JSON_OUT = args.includes("--json");
const read = (f) => fs.readFileSync(path.join(DIR, f), "utf8");
const FEED = read("feed.html"), INDEX = read("index.html"), TRACK = read("track.js");
const readJ = (f, d) => { try { return JSON.parse(read(f)); } catch (e) { return d; } };
const STATS = readJ("data/stats.json", { p: {} }), LH = readJ("data/link_health.json", {}), RP = readJ("data/reported.json", {});

/* ---------- catalogue (index.html's inline copy) ---------- */
const cm = INDEX.match(/<script type="application\/json" id="pc-catalog">([\s\S]*?)<\/script>/);
if (!cm) throw new Error("no inline catalogue in index.html");
const CAT = JSON.parse(cm[1]).filter((p) => p && p.id && p.img);
CAT.forEach((p) => { p.id = String(p.id); });
const DEAD = new Set([...(LH.dead || []), ...(RP.hidden || [])].map(String));

/* ---------- what this version of the site logs ---------- */
const capM = TRACK.match(/var CAP = \{([^}]*)\}/), KINDS = new Set(capM ? [...capM[1].matchAll(/(\w+)\s*:/g)].map((m) => m[1]) : ["v", "q", "b", "c", "f"]);
const LOGS = {
  impressions: KINDS.has("i"), hovers: KINDS.has("h"), unsaves: KINDS.has("n"),
  filters: /pcTaste\.f\(|pcTasteFilters/.test(INDEX),            // filter and sort choices, logged by the spreadsheet
};

/* ---------- seeded random ---------- */
function rng(seed) { let a = seed >>> 0 || 1; return () => { a ^= a << 13; a >>>= 0; a ^= a >>> 17; a ^= a << 5; a >>>= 0; return a / 4294967296; }; }

/* ---------- personas: P(like) for one find ---------- */
const low = (p) => (p.title || "").toLowerCase();
const isKnit = (p) => /knit|sweater|jumper|cardigan|cable/i.test(p.title || "");
const PERSONAS = {
  black: {
    like: (p) => (/\bblack\b/.test(low(p)) ? (["Bags", "Accessories", "Toys"].includes(p.cat) ? 0.5 : 0.9) : 0.04),
    sheet: { filters: { color: "black" }, search: ["black jacket"], scan: 45 },
  },
  "rl-knits": {
    like: (p) => (p.brand === "Ralph Lauren" ? (isKnit(p) ? 0.95 : p.cat === "Tops" ? 0.3 : 0.08) : isKnit(p) ? 0.2 : 0.02),
    sheet: { filters: { brand: "Ralph Lauren" }, search: ["ralph lauren sweater"], scan: 40 },
  },
  "cheap-shoes": {
    like: (p) => (p.cat === "Shoes" ? (p.price >= 5 && p.price < 150 ? 0.9 : p.price < 300 ? 0.25 : 0.04) : 0.02),
    sheet: { filters: { cat: "Shoes", pmax: 150, sort: "low" }, search: [], scan: 45 },
  },
  mixed: {
    like: (p) => (p.brand === "Stone Island" ? 0.8 : (p.brand === "Nike" || p.brand === "Jordan") && p.cat === "Shoes" ? 0.8
      : /\bwhite\b/.test(low(p)) && /\btee\b|t-shirt|tshirt/i.test(p.title || "") ? 0.6 : 0.03),
    sheet: { filters: {}, search: ["stone island", "nike dunk", "white tee"], scan: 30 },
  },
};

/* ---------- a tiny fake DOM, enough for both pages ---------- */
function fakeEl() {
  const store = {
    style: { setProperty() {}, removeProperty() {} }, dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    innerHTML: "", textContent: "", hidden: false, disabled: false, complete: false, naturalWidth: 0, firstChild: null,
  };
  const noop = () => {};
  const fns = {
    querySelector: () => fakeEl(), querySelectorAll: () => [], closest: () => null, contains: () => false,
    getBoundingClientRect: () => ({ left: 0, top: 0, right: 400, bottom: 640, width: 400, height: 640 }),
    animate: () => ({ cancel: noop, currentTime: 0 }), getAnimations: () => [], getClientRects: () => [],
    appendChild: (x) => x, insertBefore: (x) => x, remove: noop, removeAttribute: noop, setAttribute: noop, getAttribute: () => null,
    addEventListener: noop, removeEventListener: noop, focus: noop, setPointerCapture: noop, click: noop,
  };
  return new Proxy(store, {
    get(t, k) { if (k in t) return t[k]; if (k in fns) return fns[k]; if (k === Symbol.toPrimitive) return () => ""; if (typeof k === "symbol" || k === "then" || k === "decode") return undefined; return (t[k] = fakeEl()); },
    set(t, k, v) { t[k] = v; return true; },
  });
}
function makeEnv(ls, seed, pathName) {
  const LSm = new Map(Object.entries(ls || {}));
  const clock = { t: Date.UTC(2026, 10, 6, 12) };
  const timers = new Map(); let tid = 0;
  const R = rng(seed);
  const localStorage = { getItem: (k) => (LSm.has(k) ? LSm.get(k) : null), setItem: (k, v) => LSm.set(k, String(v)), removeItem: (k) => LSm.delete(k) };
  const document = {
    querySelector: () => fakeEl(), querySelectorAll: () => [], getElementById: () => fakeEl(), createElement: () => fakeEl(),
    addEventListener() {}, removeEventListener() {}, hidden: false, visibilityState: "visible", referrer: "",
    head: fakeEl(), body: fakeEl(), documentElement: fakeEl(), activeElement: fakeEl(),
  };
  class FDate extends Date { constructor(...a) { if (a.length) super(...a); else super(clock.t); } static now() { return clock.t; } }
  const g = {
    localStorage, sessionStorage: localStorage, document, console, URL, URLSearchParams, JSON, Promise, structuredClone,
    Date: FDate, Image: function () { return fakeEl(); },
    setTimeout: (fn, ms) => { const id = ++tid; timers.set(id, fn); return id; }, clearTimeout: (id) => timers.delete(id),
    setInterval: () => 0, clearInterval() {}, requestAnimationFrame: () => 0, cancelAnimationFrame() {},
    matchMedia: () => ({ matches: true, addEventListener() {}, addListener() {} }), innerWidth: 400, innerHeight: 800, scrollY: 0,
    addEventListener() {}, removeEventListener() {},
    location: { hostname: "localhost", pathname: pathName, search: "", origin: "http://localhost", href: "http://localhost" + pathName },
    history: { replaceState() {}, pushState() {} }, navigator: { userAgent: "node", vibrate() {} },
    performance: { now: () => clock.t },
    fetch: (u) => {
      const file = /stats\.json/.test(u) ? STATS : /link_health/.test(u) ? LH : /reported/.test(u) ? RP : null;
      return Promise.resolve({ ok: !!file, json: () => Promise.resolve(file) });
    },
  };
  g.window = g; g.self = g; g.globalThis = g;
  const ctx = vm.createContext(g);
  vm.runInContext("Math.random = (function (r) { return function () { return r(); }; })(__R); delete this.__R;", Object.assign(ctx, { __R: R }));
  return {
    ctx, LS: LSm, clock, R,
    flush() { for (let n = 0; n < 50 && timers.size; n++) { const fns = [...timers.values()]; timers.clear(); fns.forEach((f) => { try { f(); } catch (e) {} }); } },
    dump() { return Object.fromEntries(LSm); },
  };
}

/* ---------- the feed, with a test handle on its internals ---------- */
const feedScript = (() => {
  const all = [...FEED.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  const s = all.find((x) => x.includes("MODEL_KEY")); if (!s) throw new Error("feed script not found");
  const end = s.lastIndexOf("})();");
  const hook = `\nglobalThis.__F = { get M() { return M; }, get LR() { return LR; }, get MET() { return MET; }, get topC() { return topC; },
    get ALL() { return ALL; }, get FAVES() { return FAVES; }, newCard: newCard, decide: decide, moreSheet: moreSheet, sheet: sheet, lrp: lrp,
    score: score, get ready() { return ALL.length > 0 && !!topC; } };\n`;
  return s.slice(0, end) + hook + s.slice(end);
})();
async function runFeed(ls, seed) {
  const env = makeEnv(ls, seed, "/feed");
  env.ctx.PC_CATALOG = structuredClone(CAT); env.ctx.PC_CATALOG_GOT = 1; env.ctx.PC_CATALOG_WANT = 1;
  vm.runInContext(feedScript, env.ctx, { filename: "feed.html" });
  for (let i = 0; i < 20 && !(env.ctx.__F && env.ctx.__F.ready); i++) await new Promise((r) => setImmediate(r));
  if (!env.ctx.__F.ready) throw new Error("feed did not start");
  return { env, F: env.ctx.__F };
}
/* the most the persona likes any find of a brand: it only asks for less of a brand it has no use for */
const BMAX = new Map();
function brandMax(persona, b) {
  const key = persona.name + "|" + b;
  if (!BMAX.has(key)) BMAX.set(key, CAT.filter((p) => (p.brand || "?") === b).reduce((m, p) => Math.max(m, persona.like(p)), 0));
  return BMAX.get(key);
}
/* one swipe session: the persona decides each card from its hidden taste; slow on yes, fast on no, now and then a QC
   flick, "Show less <brand>" after the third no for one brand, "Not interested" after two no's for one brand+type */
function swipe(F, env, persona, n, R) {
  const out = [], noB = {}, noBT = {}, done = new Set();
  for (let i = 0; i < n; i++) {
    const c = F.topC; if (!c) break;
    const p = c.p, pr = persona.like(p), y = R() < pr ? 1 : 0;
    out.push({ p, y, pr });
    env.clock.t += y ? 4000 + R() * 5000 : 800 + R() * 1800;
    if (!y && R() < 0.15) c.photosSeen = 1;
    if (y && R() < 0.4) c.photosSeen = 1;
    if (!y) {
      const b = p.brand || "?", bt = b + "|" + p._t;
      noB[b] = (noB[b] || 0) + 1; noBT[bt] = (noBT[bt] || 0) + 1;
      const pick = (m) => { F.moreSheet(c); F.sheet.onclick({ target: { closest: () => ({ dataset: { m } }) } }); };
      if (noB[b] >= 3 && !done.has("b:" + b) && brandMax(persona, b) < 0.3) { done.add("b:" + b); pick("nb"); env.flush(); continue; }
      if (noBT[bt] >= 2 && !done.has(bt)) { done.add(bt); pick("ni"); env.flush(); continue; }
    }
    F.decide(y ? 1 : -1);
    env.flush();
  }
  env.flush();
  return out;
}

/* ---------- the spreadsheet's For you, from index.html ---------- */
const fyCode = (() => {
  const a = INDEX.indexOf('/* "For you" sort'), b = INDEX.indexOf("/* real popularity", a);
  if (a < 0 || b < 0) throw new Error("For you block not found");
  const s0 = INDEX.indexOf('if(s==="foryou"){'), s1 = INDEX.indexOf("return out.concat(tail); }", s0);
  if (s0 < 0 || s1 < 0) throw new Error("For you re-rank not found");
  return INDEX.slice(a, b) + "\nfunction __rank(list){ const s=\"foryou\";\n" + INDEX.slice(s0, s1 + "return out.concat(tail); }".length) + "\n return list; }\n";
})();
function runSheet(ls, seed) {
  const env = makeEnv(ls, seed, "/");
  const all = structuredClone(CAT).filter((p) => !DEAD.has(p.id));
  all.forEach((p) => { const v = (STATS.p || {})[p.id]; p.views = v ? v[1] || 0 : 0; p.views7 = v ? v[2] || 0 : 0; p._rnd = env.R(); });
  env.ctx.ALL = all; env.ctx.popScore = (p) => (p.views || 0) + (p.views7 || 0);
  vm.runInContext(fyCode, env.ctx, { filename: "index-foryou.js" });
  const fy = env.ctx.pcForYou(all.slice()), order = env.ctx.__rank(all.slice());
  return { order, score: (p) => fy.get(p) || 0, all };
}

/* ---------- a spreadsheet session, written the way this version of the site would log it ---------- */
function sheetSession(persona, R, clock) {
  const T = { q: [], v: [], b: [], c: [], f: [], i: [], h: [], n: [] }, faves = [];
  const now = () => (clock.t += 1000 + R() * 4000);
  const slugOf = (s) => String(s).toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const pop = (p) => { const v = (STATS.p || {})[p.id]; return v ? (v[1] || 0) + (v[2] || 0) : 0; };
  const base = CAT.filter((p) => !DEAD.has(p.id)).sort((a, b) => pop(b) - pop(a));
  const views = [];
  const F = persona.sheet.filters || {};
  // 1. the homepage as it opens (most popular), then the persona's filters, then its searches
  views.push(base);
  if (Object.keys(F).length) {
    let l = base.filter((p) => (!F.color || new RegExp("\\b" + F.color + "\\b").test(low(p))) && (!F.brand || p.brand === F.brand) && (!F.cat || p.cat === F.cat) && (!F.pmax || (p.price >= 5 && p.price < F.pmax)));
    if (F.sort === "low") l = l.slice().sort((a, b) => a.price - b.price);
    if (LOGS.filters) {
      if (F.color) T.f.push(["col:" + F.color, now()]);
      if (F.brand) T.f.push(["brand:" + slugOf(F.brand), now()]);
      if (F.cat) T.f.push(["cat:" + F.cat, now()]);
      if (F.pmax) T.f.push(["pr:0-" + F.pmax, now()]);
      if (F.sort) T.f.push(["sort:" + F.sort, now()]);
    } else if (F.brand) T.f.push(["brand:" + slugOf(F.brand), now()]);   // the old log only had brand-page and category-tile clicks
    else if (F.cat) T.f.push(["cat:" + F.cat, now()]);
    views.push(l);
  }
  for (const q of persona.sheet.search) {
    T.q.push([q, now()]);
    const toks = q.split(" ");
    views.push(base.filter((p) => toks.every((w) => ((p.brand || "") + " " + p.title).toLowerCase().includes(w))));
  }
  // 2. in each view the persona looks down the first rows. A find it likes is opened about half the time (at most 8 per
  //    view), sometimes saved, hovered, QC-checked or bought; the other liked ones and the rest are scrolled past (so
  //    "scrolled past" is a noisy no, as in real life). Now and then a find it does not like is peeked at for a few
  //    seconds, and one find saved by mistake is unsaved again.
  const seen = new Set(); let mistake = false;
  for (const l of views) {
    let opened = 0;
    for (const p of l.slice(0, persona.sheet.scan)) {
      if (seen.has(p.id)) continue; seen.add(p.id);
      const y = R() < persona.like(p);
      if (y && opened < 8 && R() < 0.55) {
        opened++;
        if (LOGS.hovers && R() < 0.5) T.h.push([p.id, now()]);
        T.v.push([p.id, now(), Math.round(15 + R() * 60)]);
        if (p.qc > 0 && R() < 0.35) T.c.push([p.id, now()]);
        if (R() < 0.3) faves.push(p.id);
        if (R() < 0.12) T.b.push([p.id, now()]);
      } else if (!y && R() < 0.03) {
        T.v.push([p.id, now(), Math.round(2 + R() * 4)]);                       // a peek
      } else {
        if (LOGS.impressions) T.i.push([p.id, now(), l === base ? 0 : 1]);
        if (!y && !mistake && R() < 0.05) { mistake = true; faves.push(p.id); if (LOGS.unsaves) T.n.push(["uf:" + p.id, now()]); faves.pop(); }
      }
    }
  }
  for (const k of Object.keys(T)) if (!T[k].length || !KINDS.has(k)) delete T[k];
  return { "pc.taste": JSON.stringify(T), "manifest.faves": JSON.stringify(faves) };
}

/* ---------- scores ---------- */
function auc(items, sc, persona) {
  const pos = [], neg = [];
  items.forEach((p) => { (persona.like(p) >= 0.5 ? pos : neg).push(sc(p)); });
  if (!pos.length || !neg.length) return null;
  neg.sort((a, b) => a - b);
  let w = 0;
  for (const v of pos) { let lo = 0, hi = neg.length; while (lo < hi) { const m = (lo + hi) >> 1; if (neg[m] < v) lo = m + 1; else hi = m; } let eq = lo; while (eq < neg.length && neg[eq] === v) eq++; w += lo + (eq - lo) / 2; }
  return w / (pos.length * neg.length);
}
const hits = (list, persona) => list.reduce((s, p) => s + persona.like(p), 0);
const mean = (a) => a.reduce((s, x) => s + x, 0) / (a.length || 1);

async function expA(persona, seed) {          // sheet -> feed
  const R = rng(seed * 7 + 1), clock = { t: Date.UTC(2026, 10, 6, 10) };
  const ls = sheetSession(persona, R, clock);
  const { F, env } = await runFeed(ls, seed);
  const cards = [F.topC.p]; for (let i = 0; i < 19; i++) { const c = F.newCard(); if (c) cards.push(c.p); }
  const items = F.ALL.filter((p) => p._img && !F.FAVES.has(p.id));
  return { hit: hits(cards, persona), auc: auc(items, (p) => F.lrp(p), persona) };
}
async function expB(persona, seed, lsStart) {  // feed -> sheet (lsStart: a spreadsheet session first, for D)
  const R = rng(seed * 13 + 5);
  const { F, env } = await runFeed(lsStart || {}, seed);
  swipe(F, env, persona, 40, R);
  const S = runSheet(env.dump(), seed);
  const fav = new Set(JSON.parse(env.LS.get("manifest.faves") || "[]"));
  const fresh = S.order.filter((p) => !fav.has(p.id));      // saved finds are known already: judge the new ones
  if (process.env.DEBUG) { console.error("--- " + (lsStart ? "D" : "B") + " seed " + seed); fresh.slice(0, 12).forEach((p) => console.error(persona.like(p).toFixed(2), S.score(p).toFixed(2), p.brand, "|", p.title));
    const lk = S.all.filter((p) => persona.like(p) >= 0.5).sort((a, b) => S.score(a) - S.score(b)); console.error("lowest liked:"); lk.slice(0, 8).forEach((p) => console.error(S.score(p).toFixed(2), p.brand, "|", p.title, p.cat, p.price));
    const sc = S.all.map(S.score).sort((a, b) => a - b); console.error("median", sc[sc.length >> 1].toFixed(2), "p90", sc[Math.floor(sc.length * 0.9)].toFixed(2)); }
  return { hit: hits(fresh.slice(0, 20), persona), auc: auc(S.all.filter((p) => !fav.has(p.id)), S.score, persona) };
}
async function expC(persona, seed) {          // the feed alone
  const R = rng(seed * 31 + 3);
  const { F, env } = await runFeed({}, seed);
  const out = swipe(F, env, persona, 30, R);
  const h = F.MET.h;
  const a = (() => { const pos = h.filter((x) => x[1]), neg = h.filter((x) => !x[1]); if (!pos.length || !neg.length) return null; let w = 0; pos.forEach((x) => neg.forEach((z) => { w += x[0] > z[0] ? 1 : x[0] === z[0] ? 0.5 : 0; })); return w / (pos.length * neg.length); })();
  return { hit: out.slice(20, 30).reduce((s, x) => s + x.pr, 0), auc: a };
}
async function expD(persona, seed) {
  const R = rng(seed * 7 + 1), clock = { t: Date.UTC(2026, 10, 6, 10) };
  return expB(persona, seed, sheetSession(persona, R, clock));
}

const res = {};
for (const [name, persona] of Object.entries(PERSONAS)) {
  persona.name = name;
  if (ONLY && name !== ONLY) continue;
  const r = { A: [], B: [], C: [], D: [] };
  for (let s = 1; s <= SEEDS; s++) {
    r.A.push(await expA(persona, s)); r.B.push(await expB(persona, s)); r.C.push(await expC(persona, s)); r.D.push(await expD(persona, s));
  }
  res[name] = Object.fromEntries(Object.entries(r).map(([k, v]) => [k, { hit: mean(v.map((x) => x.hit)), auc: mean(v.filter((x) => x.auc != null).map((x) => x.auc)) }]));
}
if (JSON_OUT) { console.log(JSON.stringify({ dir: DIR, logs: LOGS, res }, null, 1)); process.exit(0); }
const pct = (x) => (x == null || isNaN(x) ? "  -" : String(Math.round(x * 100)).padStart(3) + "%");
console.log("site: " + DIR + "\nlogged on the spreadsheet: " + Object.entries(LOGS).map(([k, v]) => k + (v ? " yes" : " no")).join(", ") + "  (" + SEEDS + " seeds)\n");
console.log("persona       A sheet->feed     B feed->sheet     C feed alone      D both->sheet");
console.log("              hit@20   AUC      hit@20   AUC      21-30/10  AUC     hit@20   AUC");
for (const [n, r] of Object.entries(res)) {
  console.log(n.padEnd(12) + "  " + [r.A, r.B].map((x) => x.hit.toFixed(1).padStart(5) + "   " + pct(x.auc) + "    ").join("") +
    r.C.hit.toFixed(1).padStart(5) + "    " + pct(r.C.auc) + "     " + r.D.hit.toFixed(1).padStart(5) + "   " + pct(r.D.auc));
}
const avg = (k, f) => mean(Object.values(res).map((r) => r[k][f]));
console.log("average       " + ["A", "B"].map((k) => avg(k, "hit").toFixed(1).padStart(5) + "   " + pct(avg(k, "auc")) + "    ").join("") +
  avg("C", "hit").toFixed(1).padStart(5) + "    " + pct(avg("C", "auc")) + "     " + avg("D", "hit").toFixed(1).padStart(5) + "   " + pct(avg("D", "auc")));
