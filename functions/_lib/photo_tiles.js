// Dark mode photo tiles (owner, 26 Nov 2026). In dark mode a product photo that is a transparent cut-out sits on the
// category grey (#262626, the tile of the category circles) and is shown as it is: no brightness filter, no blend. Every
// other photo keeps the light tile (#DEDEDE with brightness .8706), and light mode is unchanged. The photo box of a
// cut-out carries the class "pc-cut", which ds.css and index.html style. It is set on the server through isCut() in
// site.js, in the app through pcCut() in index.html (same test; it gets TILE_LIGHT from functions/_middleware.js as
// window.PC_TILE_LIGHT) and in the header search on server pages through /search-index.json (search_index.js).

// A cut-out is a photo at one of these addresses (photo-edge run of 25 Nov 2026 and the earlier cut-outs):
//   products/pc2/<id>-e1.webp or <id>-t1.webp (Supabase, or the site's copy img/m/pc2/<id>-e1[.v<n>].webp),
//   img/rl/<id>-e1.webp, img/fr/<id>-e1.webp, and products/store2/<name>-t1.webp (store photos).
export const CUT_RX = /^\/(?:storage\/v1\/object\/public\/products|img\/m)\/pc2\/[\w-]+-[et]1(?:\.v[\w-]+)?\.webp$|^\/img\/(?:rl|fr)\/[\w-]+-e1\.webp$|^\/storage\/v1\/object\/public\/products\/store2\/[\w.-]+-t1\.webp$/;
// The path of a photo address as CUT_RX reads it: the Supabase address inside /api/img?u=, without host, Cloudflare
// resize prefix (/cdn-cgi/image/...) or query.
export function cutPath(u) {
  u = String(u || "");
  const q = u.indexOf("/api/img?");
  if (q >= 0) { try { u = new URLSearchParams(u.slice(q + 9)).get("u") || ""; } catch (e) { u = ""; } }
  return u.replace(/^https?:\/\/[^/]+/, "").replace(/^\/cdn-cgi\/image\/[^/]+/, "").replace(/[?#].*$/, "");
}

// The finds whose photo keeps the light tile in dark mode although it may be a cut-out, with the reason (review of the
// photo-edge run, 25 Nov 2026: 41 half see-through, 22 with a prop or backdrop, 8 that are not cut-outs). This list is
// the only copy: add or remove an id here, then raise PRODUCT_TPL in pages.js so cached pages pick the change up.
export const TILE_LIGHT = {
  "7673294189": "a faint figure from the backdrop is kept next to it",
  "7509414855": "a white dust cloth kept with the bag, plain on #262626",
  "6620905012": "a white strip of the stand under the hem, plain on #262626",
  "7237596685": "a white strip of the stand under the hem, plain on #262626",
  "7759262976": "a white strip of the stand under the hem, plain on #262626",
  "7798030435": "a white strip of the stand under the hem, plain on #262626",
  "7780725454": "a white surface kept under the bag, plain on #262626",
  "7717221359": "held by a white glove, plain on #262626",
  "7672788361": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7675202584": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7675251744": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7676274278": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7677436795": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7680428832": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7680503866": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7708648884": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "5014331360": "shown on a clear acrylic stand, plain on #262626",
  "7721409990": "shown on a white display bust, plain on #262626",
  "7704571152": "shown on a white display form, plain on #262626",
  "7592879251": "shown on a white mannequin head, plain on #262626",
  "7742892345": "shown on a white mannequin head, plain on #262626",
  "7742967747": "shown on a white mannequin head, plain on #262626",
  "7291656463": "shown on a white pedestal, plain on #262626",
  "7778420206": "shown on white watch cushions, plain on #262626",
  "7733032421": "the display frame lines cannot be taken out cleanly",
  "7672171457": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672313259": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672317251": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672715493": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672766669": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672786373": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7672823927": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7673237097": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7673313861": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7673315831": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675091536": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675157252": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675208488": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675220264": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675241904": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675259650": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675259790": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675295262": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675752664": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675803344": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676185446": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676232932": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676246572": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676303828": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676305748": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677460637": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677464519": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677515795": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677519727": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677525687": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677537657": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7680468108": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7680482098": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7732199741": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7734197243": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7734254163": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7737177212": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7737279709": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7737636100": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7737657814": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7738000575": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "696593485678": "the white backdrop is kept inside the bracelet",
  "7717215573": "the white backdrop is kept inside the necklace",
  "7720288484": "the white backdrop is kept inside the necklace",
  "7511987664": "white pads kept beside the bag, plain on #262626",
  "6636749467": "white pieces of the stand at the bottom, plain on #262626",
};
export const TILE_LIGHT_IDS = new Set(Object.keys(TILE_LIGHT));
// The same ids for the app, as the script functions/_middleware.js puts at the top of every app page.
export const TILE_LIGHT_JS = `<script>window.PC_TILE_LIGHT="${[...TILE_LIGHT_IDS].join(" ")}"</script>`;
