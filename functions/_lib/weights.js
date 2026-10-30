// Item types and typical shipped weights (round 8, 30 Oct 2026): ONE table for the whole site.
//  - pages.js: itemType() (the related rings, brand facts and picks), the "Typical weight" fact and the estimated-weight
//    chip under the product title on /product/<id>.
//  - tools9.js: the shipping calculator's "Tap to add" items (ITEM_WEIGHTS is built from this table).
//  - index.html: the in-page product view reads a copy of WT_DATA between the "WT-DATA-BEGIN" / "WT-DATA-END" markers.
//    That copy is generated: after changing WT_DATA run  python3 scripts/sync_weights.py  (it rewrites the block in
//    index.html and fails when the two differ in --check mode).
// No real weights exist for the finds: a find's weight is the typical shipped weight of its item type (light packaging
// included), and the type comes from the words of the title (first match wins), else from the catalogue category.
// The numbers are the old weight estimator's; every page calls them an estimate and they never go into JSON-LD.
// WT_DATA is plain JSON (regexes as source strings, all case-insensitive) so the copy in index.html can be checked.
/* WT-JSON-BEGIN */
export const WT_DATA = {
  "types": [
    ["", "\\bbox set\\b"],
    ["caps and beanies", "\\bcaps?\\b|\\bhats?\\b|\\bbeanies?\\b|\\bbalaclavas?\\b|\\bvisors?\\b"],
    ["scarves", "\\bscar(f|ves)\\b"],
    ["sunglasses", "\\bsunglasses\\b|\\bglasses\\b"],
    ["suitcases", "\\bsuitcases?\\b|\\bluggage\\b"],
    ["bags", "\\bbags?\\b|\\bbackpacks?\\b|\\btotes?\\b|\\bduff(le|el)s?\\b|\\bpouch(es)?\\b|\\bkeepall\\b|\\bhandbags?\\b|\\bbriefcases?\\b|\\bspeedy\\b"],
    ["wallets and cardholders", "\\bwallets?\\b|\\bcard ?holders?\\b"],
    ["belts", "\\bbelts?\\b"],
    ["watches", "\\bwatch(es)?\\b|\\bdial\\b"],
    ["jewellery", "\\brings?\\b|\\bnecklaces?\\b|\\bbracelets?\\b|\\bchains?\\b|\\bpendants?\\b|\\bearrings?\\b"],
    ["socks and underwear", "\\bsocks\\b|\\bboxers\\b|\\bunderwear\\b|\\bbriefs\\b"],
    ["perfumes", "\\bperfumes?\\b|\\bfragrances?\\b|\\bcologne\\b"],
    ["T-shirts and tops", "\\bgraphic (?:t-?shirts?|tees?)\\b"],
    ["boots", "\\bboots?\\b|\\bbooties?\\b"],
    ["loafers", "\\bloafers?\\b"],
    ["sandals and slides", "\\bsandals?\\b|\\bslides?\\b|\\bslippers?\\b|\\bclogs?\\b|\\bflip flops?\\b|\\bmules\\b"],
    ["heels", "\\bheels?\\b|\\bpumps\\b"],
    ["sneakers and shoes", "\\bsneakers?\\b|\\btrainers?\\b|\\brunners?\\b|\\bshoes?\\b|\\bhigh-?tops?\\b"],
    ["dresses and skirts", "\\bdress(es)?\\b|\\bskirts?\\b"],
    ["short sets", "\\bshorts? sets?\\b|\\b(?:tees?|t-?shirts?|polos?)\\b.*\\bshorts\\b.*\\bsets?\\b"],
    ["tracksuits and sets", "\\btracksuits?\\b|\\btrack suits?\\b|\\bsets?\\b"],
    ["shorts", "\\bshorts\\b"],
    ["jeans", "\\bjeans\\b"],
    ["pants and joggers", "\\bpants\\b|\\btrousers\\b|\\bjoggers\\b|\\bsweatpants\\b|\\bleggings\\b|\\bcargos?\\b|\\boveralls\\b"],
    ["vests and gilets", "\\bvests?\\b(?! top)|\\bgilets?\\b"],
    ["puffer jackets", "\\bpuffers?\\b|(?:^| )down (?:jackets?|coats?|parkas?|vests?|gilets?|cardigans?)\\b|(?:^| )down$"],
    ["jackets and coats", "\\bjackets?\\b|\\bcoats?\\b|\\bparkas?\\b|\\bwindbreakers?\\b|\\bbombers?\\b|\\bovershirts?\\b|\\bblazers?\\b"],
    ["hoodies", "\\bhoodies?\\b"],
    ["quarter-zips", "\\bquarter.?zips?\\b|\\bhalf.?zips?\\b"],
    ["polo shirts", "\\bpolo shirts?\\b|\\bpolos?(?: (?:light |dark )?(?:black|white|grey|gray|navy|blue|cream|green|brown|pink|red|beige|tan|yellow|orange|purple|burgundy|olive|khaki|camel))?$"],
    ["T-shirts and tops", "\\bt-?shirts?\\b|\\btees?\\b|\\blong.?sleeves?\\b|\\btank tops?\\b|\\bvest tops?\\b"],
    ["sweaters and cardigans", "\\bsweaters?\\b|\\bcardigans?\\b|\\bknit(ted|wear)?\\b|\\bjumpers?\\b"],
    ["sweatshirts and crewnecks", "\\bsweatshirts?\\b|\\bcrewnecks?\\b"],
    ["jerseys", "\\bjerseys?\\b"],
    ["shirts", "\\bshirts?\\b|\\bblouses?\\b"],
    ["fleeces", "\\bfleeces?\\b"],
    ["ties", "\\bties?\\b(?![ -]?dye)"]
  ],
  "accessoryOnly": ["jewellery", "ties"],
  "catType": { "Tops": "other tops", "Outerwear": "other outerwear", "Shoes": "sneakers and shoes", "Pants": "pants and joggers", "Shorts": "shorts",
    "Bags": "bags", "Accessories": "other accessories", "Headwear": "caps and beanies", "Toys": "building sets and toys" },
  "grams": { "T-shirts and tops": 250, "polo shirts": 330, "shirts": 330, "jerseys": 300, "shorts": 350, "hoodies": 700,
    "sweaters and cardigans": 700, "sweatshirts and crewnecks": 700, "quarter-zips": 700, "fleeces": 700, "pants and joggers": 600,
    "jeans": 600, "tracksuits and sets": 1100, "short sets": 600, "dresses and skirts": 400, "vests and gilets": 600, "jackets and coats": 700,
    "puffer jackets": 1100, "sneakers and shoes": 900, "boots": 1300, "loafers": 800, "sandals and slides": 600, "heels": 700,
    "bags": 550, "suitcases": 3500, "caps and beanies": 220, "scarves": 250, "belts": 200, "wallets and cardholders": 200,
    "jewellery": 200, "watches": 250, "sunglasses": 200, "ties": 150, "socks and underwear": 200, "perfumes": 450,
    "other tops": 400, "other outerwear": 900, "other accessories": 200 },
  "boxed": { "sneakers and shoes": 1300, "boots": 1800, "loafers": 1200 },
  "calc": [["T-shirt", "T-shirts and tops"], ["Shirt / polo", "polo shirts"], ["Shorts", "shorts"], ["Hoodie / sweater", "hoodies"],
    ["Pants / jeans", "pants and joggers"], ["Light jacket", "jackets and coats"], ["Puffer / heavy jacket", "puffer jackets"],
    ["Sneakers (no box)", "sneakers and shoes"], ["Sneakers (with box)", "sneakers and shoes", "boxed"], ["Bag", "bags"],
    ["Cap / beanie", "caps and beanies"], ["Belt / small accessory", "belts"]]
};
/* WT-JSON-END */

const TYPES = WT_DATA.types.map(([label, re]) => [label, new RegExp(re, "i")]);
const ACCESSORY_ONLY = new Set(WT_DATA.accessoryOnly);
// Item type of a find, read from the words of its title (first match wins), else from its catalogue category.
// p: { title, brand, cat } (a catalogue row).
export function itemTypeOf(p) {
  let t = p.title || "";
  if (p.brand && t.toLowerCase().startsWith(p.brand.toLowerCase() + " ")) t = t.slice(p.brand.length + 1);
  if (p.cat !== "Toys")   // set names ("TIE Fighter", "Lord of the Rings") are not item types
    for (const [label, re] of TYPES) {
      if (!re.test(t)) continue;
      if (!label) break;                                                    // "box set": use the category
      if (ACCESSORY_ONLY.has(label) && p.cat !== "Accessories") continue;   // "Chain Logo T-Shirt" is not jewellery, "Tie-Dye" is not a tie
      return label;
    }
  return WT_DATA.catType[p.cat] || "other finds";
}
// Typical shipped weight of an item type in grams, 0 when there is no sensible figure (toys, "other finds").
export const typeGrams = t => WT_DATA.grams[t] || 0;
export const boxedGrams = t => WT_DATA.boxed[t] || 0;
// The shipping calculator's item list: [label, grams], same order as WT_DATA.calc.
export const CALC_ITEMS = WT_DATA.calc.map(([label, t, boxed]) => [label, boxed ? WT_DATA.boxed[t] : WT_DATA.grams[t]]);
// The rounded figure a page shows: 50 g steps under 1 kg, 0.1 kg steps from 1 kg. { short: "~250g", long: "250 g" }.
export function fmtGrams(g) {
  if (!(g > 0)) return null;
  const r = Math.round(g / 50) * 50;
  if (r < 1000) return { short: `~${r}g`, long: `${r} g` };
  const kg = (Math.round(g / 100) / 10).toFixed(1);
  return { short: `~${kg}kg`, long: `${kg} kg` };
}
