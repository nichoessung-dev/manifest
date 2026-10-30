// /search-index.json (round 6, item 10): the compact catalogue the header search on server pages loads on first use
// (pcs.js standalone mode), and that the QC checker and link converter read to know a find's marketplace (item 22).
// Built from the server catalogue P on the first request per isolate and kept in memory until the view stats change.
// Columnar and gzip friendly: brands, categories, platforms and image folders are tables, each row points into them.
//   {"v":BUILT,"n":count,"pre":[image folder, ...,""],"cats":[[CATS key, slug]],"brands":[[name, hub slug or ""]],
//    "plat":["weidian",...],"rows":[[id,title,brandIdx|-1,catIdx,platIdx,cny,usd,qc,preIdx,imgRest,pop,itemId|0]]}
// Listings the weekly link check found dead are left out (the app hides them); sold-out ones stay.
// pop = score(p) rounded (views and favourites when stats are loaded), usd = Math.round(cny * USD_RATE) as money() does.
import { P, gone, score, BUILT, CATS, idx, USD_RATE, rawImg } from "./site.js";

// FNV-1a 32-bit as 8 hex characters (the ETag suffix, and the stats fingerprint in the cache key).
export function fnv8(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return ("0000000" + h.toString(16)).slice(-8);
}

let MEM = null;   // { ix, ver, body, etag }

// A short fingerprint of the view stats behind the popularity numbers: idx() is rebuilt whenever new stats load, and
// its ranking of the most viewed finds changes with them. Used in the shared cache key so isolates agree.
export function statsVersion() {
  const top = idx().all.slice(0, 200);
  return fnv8(top.map(p => p.id + ":" + Math.round(score(p))).join(","));
}

// The index built in this isolate, when it is still current (same idx(), so same stats); else null.
export const cachedIndex = () => (MEM && MEM.ix === idx() ? MEM : null);

export function buildSearchIndex() {
  const ix = idx();
  if (MEM && MEM.ix === ix) return MEM;
  const live = P.filter(p => gone(p) !== "dead");
  // image folders: every folder used by 20+ finds gets an entry; "" (the full URL in imgRest) is always last
  const fc = new Map();
  for (const p of live) { const u = rawImg(p), k = u.lastIndexOf("/"); if (k > 0) { const f = u.slice(0, k + 1); fc.set(f, (fc.get(f) || 0) + 1); } }
  const pre = [...fc.entries()].filter(e => e[1] >= 20).sort((a, b) => b[1] - a[1]).map(e => e[0]);
  pre.push("");
  const catKeys = Object.keys(CATS), catIdx = new Map(catKeys.map((k, i) => [k, i])), cats = catKeys.map(k => [k, CATS[k].slug]);
  const plat = [], platIdx = new Map(), brands = [], brandIdx = new Map();
  const rows = [];
  for (const p of live) {
    let bi = -1;
    if (p.brand) { bi = brandIdx.get(p.brand); if (bi == null) { bi = brands.length; brandIdx.set(p.brand, bi); brands.push([p.brand, ix.brandSlug.get(p.brand) || ""]); } }
    let ci = catIdx.get(p.cat);
    if (ci == null) { ci = cats.length; catIdx.set(p.cat, ci); cats.push([p.cat, ""]); }
    const pl = p.platform || "weidian";
    let pi = platIdx.get(pl); if (pi == null) { pi = plat.length; platIdx.set(pl, pi); plat.push(pl); }
    const u = rawImg(p);
    let k = pre.length - 1;
    for (let j = 0; j < pre.length - 1; j++) if (u.indexOf(pre[j]) === 0) { k = j; break; }
    const cny = +p.cny || 0;
    rows.push([String(p.id), p.title, bi, ci, pi, cny, Math.round(cny * USD_RATE), p.qc || 0, k, u.slice(pre[k].length), Math.round(score(p)),
      p.itemId && String(p.itemId) !== String(p.id) ? String(p.itemId) : 0]);
  }
  const body = JSON.stringify({ v: BUILT, n: rows.length, pre, cats, brands, plat, rows });
  MEM = { ix, ver: statsVersion(), body, etag: `"${BUILT}-${fnv8(body)}"` };
  return MEM;
}
