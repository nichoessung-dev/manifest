// Node test for the subcategories (functions/_lib/subcats.js, 28 Nov 2026): node scripts/test_subcats.mjs
// The table names item types of functions/_lib/weights.js by their labels, so a renamed label there would quietly empty a
// subcategory: every label must still be one itemTypeOf() can return. Also checks the slugs, the copy in index.html, and
// that the category hubs, the subcategory hubs and the sitemap agree. No network.
import assert from "node:assert/strict";
import fs from "node:fs";
import { SUB_DATA, subOf, subsIn, subMeta } from "../functions/_lib/subcats.js";
import { WT_DATA, itemTypeOf } from "../functions/_lib/weights.js";
import { CATS, P, idx, shown } from "../functions/_lib/site.js";
import { hubSpec, hubList, hubParts, sitemapPages } from "../functions/_lib/pages.js";

// the table
const labels = new Set([...WT_DATA.types.map(t => t[0]).filter(Boolean), ...Object.values(WT_DATA.catType)]);
const slugs = [];
for (const [cat, list] of Object.entries(SUB_DATA.cats)) {
  assert.ok(CATS[cat], `${cat} is a category`);
  for (const [slug, name, types] of list) {
    assert.match(slug, /^[a-z][a-z0-9-]*$/, `slug ${slug}`);
    assert.ok(!/[–—]/.test(name) && name[0] === name[0].toUpperCase() && name.slice(1) === name.slice(1).toLowerCase(), `${name}: sentence case, no dashes`);
    for (const t of types) assert.ok(labels.has(t), `${cat} > ${name}: "${t}" is not an item type of weights.js`);
    slugs.push(slug);
  }
}
assert.equal(new Set(slugs).size, slugs.length, "slugs are unique across categories (?sub= names one alone)");
assert.equal(subMeta("constructor"), null);

// index.html carries the same table (scripts/sync_weights.py)
const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
const m = html.match(/\/\*SUB-DATA-BEGIN\*\/(.*?)\/\*SUB-DATA-END\*\//s);
assert.ok(m, "index.html has the SUB-DATA block");
assert.deepEqual(JSON.parse(m[1]), SUB_DATA, "index.html's copy is in sync: run python3 scripts/sync_weights.py");

// every find: a subcategory of its own category, or none
for (const p of P) { const s = subOf(p); if (s) { assert.equal(subMeta(s).cat, p.cat); assert.ok(SUB_DATA.cats[p.cat].some(x => x[0] === s && x[2].includes(itemTypeOf(p)))); } }

// hubs and sitemap
const { byCat } = idx();
let n = 0;
for (const [cat, meta] of Object.entries(CATS)) {
  const list = (byCat.get(cat) || []).filter(shown), subs = subsIn(cat, list), spec = hubSpec("/category/" + meta.slug);
  assert.equal((spec.subs ? spec.subs.list : []).length, subs.length, `${cat}: the hub's chip row`);
  for (const x of subs) {
    n++;
    assert.ok(x.n >= SUB_DATA.min);
    const path = `/category/${meta.slug}/${x.slug}`, sp = hubSpec(path);
    assert.ok(sp, path);
    assert.equal(hubList(sp).list.length, x.n, `${path}: its finds`);
    assert.ok(sp.desc.length <= 160 && !/replica|fake|1:1/i.test(sp.title + sp.desc + sp.h), `${path}: title and description`);
    assert.match(hubParts(sp).head, new RegExp(`"subcat":"${x.slug}"`));
  }
  assert.equal(hubSpec(`/category/${meta.slug}/nope`), null, "an unknown subcategory is a 404");
}
assert.ok(n >= 20, `${n} subcategory hubs`);
const sm = await sitemapPages().text();
assert.equal((sm.match(/\/category\/[a-z0-9-]+\/[a-z][a-z0-9-]*<\/loc>/g) || []).length, n, "every subcategory hub is in the sitemap");
console.log(`subcategories ok: ${slugs.length} in the table, ${n} hubs`);
