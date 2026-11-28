// Subcategories (28 Nov 2026, owner: "make the categories way better"): a second level under the big categories, so the
// 4,500 tops can be browsed as T-shirts, Hoodies, Jerseys and so on. ONE table for the whole site:
//  - pages.js: the chip row on the category hubs, the subcategory hubs (/category/<cat>/<sub>) and their sitemap entries.
//  - index.html: the chip row above All Finds when one category is picked, and the filter behind it. It reads a copy of
//    SUB_DATA between the "SUB-DATA-BEGIN" / "SUB-DATA-END" markers. That copy is generated: after changing SUB_DATA run
//    python3 scripts/sync_weights.py (it rewrites the block in index.html and fails when the two differ in --check mode).
// A find's subcategory is its item type (itemTypeOf in weights.js: the words of its title, else its category) looked up in
// the list of its own category below. No field is stored per find: the server and the app work it out from the same title,
// brand and category, so they always agree, and a new find has its subcategory as soon as it is in the catalogue.
// This replaces data/subcats.json (15 Nov 2026), which came from the AI vision pass and had no type for about 3 in 10 tops.
// A type that is not listed under the find's category (an "other ..." type, a rare one, or an odd one such as a jacket filed
// under Tops) gives no subcategory: the find stays under its category, just not under a chip.
// A subcategory exists when it has at least SUB_DATA.min finds a visitor can see, and a category shows subcategories only
// when at least two of them exist (one chip would be the category again).
// Each entry: [slug, name, item types]. Names are sentence case. Slugs are unique across all categories, because the app's
// ?sub= address names a subcategory without its category.
import { itemTypeOf } from "./weights.js";

/* SUB-JSON-BEGIN */
export const SUB_DATA = {
  "min": 12,
  "cats": {
    "Tops": [["t-shirts", "T-shirts", ["T-shirts and tops"]], ["hoodies", "Hoodies", ["hoodies"]], ["jerseys", "Jerseys", ["jerseys"]],
      ["sweatshirts", "Sweatshirts", ["sweatshirts and crewnecks"]], ["sweaters", "Sweaters and cardigans", ["sweaters and cardigans"]],
      ["tracksuits", "Tracksuits and sets", ["tracksuits and sets", "short sets"]], ["polos", "Polo shirts", ["polo shirts"]],
      ["shirts", "Shirts", ["shirts"]], ["quarter-zips", "Quarter-zips", ["quarter-zips"]]],
    "Outerwear": [["coats", "Jackets and coats", ["jackets and coats"]], ["puffers", "Puffer jackets", ["puffer jackets"]],
      ["vests", "Vests and gilets", ["vests and gilets"]]],
    "Shoes": [["trainers", "Sneakers", ["sneakers and shoes"]], ["slides", "Slides and sandals", ["sandals and slides"]], ["boots", "Boots", ["boots"]],
      ["loafers", "Loafers", ["loafers"]], ["heels", "Heels", ["heels"]]],
    "Pants": [["joggers", "Pants and joggers", ["pants and joggers"]], ["jeans", "Jeans", ["jeans"]]],
    "Accessories": [["jewellery", "Jewellery", ["jewellery"]], ["belts", "Belts", ["belts"]], ["watches", "Watches", ["watches"]],
      ["socks", "Socks and underwear", ["socks and underwear"]], ["sunglasses", "Sunglasses", ["sunglasses"]], ["scarves", "Scarves", ["scarves"]],
      ["wallets", "Wallets", ["wallets and cardholders"]], ["ties", "Ties", ["ties"]], ["perfume", "Perfume", ["perfumes"]]]
  }
};
/* SUB-JSON-END */

const TYPE_SUB = {}, META = {};   // category -> item type -> slug; slug -> { slug, name, cat }
for (const [cat, list] of Object.entries(SUB_DATA.cats)) for (const [slug, name, types] of list) {
  META[slug] = { slug, name, cat };
  for (const t of types) (TYPE_SUB[cat] || (TYPE_SUB[cat] = {}))[t] = slug;
}
// A slug from a URL must be the table's own key ("constructor" is a key of every plain object).
export const subMeta = s => Object.prototype.hasOwnProperty.call(META, s) ? META[s] : null;
// The find's subcategory slug, "" for none. Kept per find object: a find's title and category never change in a running
// server (a partner swap changes its listing and price only).
const MEMO = new WeakMap();
export function subOf(p) {
  let s = MEMO.get(p);
  if (s === undefined) { const m = TYPE_SUB[p.cat]; s = (m && m[itemTypeOf(p)]) || ""; MEMO.set(p, s); }
  return s;
}
// The subcategories that exist in one category's list (the finds a visitor can see): [{ slug, name, n }] in table order,
// or [] when fewer than two reach SUB_DATA.min.
export function subsIn(cat, list) {
  const L = Object.prototype.hasOwnProperty.call(SUB_DATA.cats, cat) ? SUB_DATA.cats[cat] : null;
  if (!L) return [];
  const n = {};
  for (const p of list) { const s = subOf(p); if (s) n[s] = (n[s] || 0) + 1; }
  const out = L.filter(([s]) => (n[s] || 0) >= SUB_DATA.min).map(([slug, name]) => ({ slug, name, n: n[slug] }));
  return out.length >= 2 ? out : [];
}
// A name inside a sentence: "hoodies", "sweaters and cardigans", but "T-shirts" keeps its capital.
export const subLower = name => name.replace(/^[A-Z](?!-)/, c => c.toLowerCase());
// A name for titles and the h1, in the title case the other hub titles use ("Polo Shirts", "T-Shirts", "Slides and Sandals").
export const subTitle = name => name.replace(/(^|[ -])([a-z])/g, (m, a, b) => a + b.toUpperCase()).replace(/ And /g, " and ");
