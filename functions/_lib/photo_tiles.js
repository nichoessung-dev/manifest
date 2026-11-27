// Dark mode photo tiles (owner, 26 Nov 2026). In dark mode a product photo that is a transparent cut-out sits on the
// category grey (#262626, the tile of the category circles) and is shown as it is: no brightness filter, no blend. Every
// other photo keeps the light tile (#DEDEDE with brightness .8706), and light mode is unchanged. The photo box of a
// cut-out carries the class "pc-cut", which ds.css and index.html style. It is set on the server through isCut() in
// site.js, in the app through pcCut() in index.html (same test; it gets TILE_LIGHT from functions/_middleware.js as
// window.PC_TILE_LIGHT) and in the header search on server pages through /search-index.json (search_index.js).

// A cut-out is a photo at one of these addresses (photo-edge run of 25 Nov 2026 and the earlier cut-outs):
//   products/pc2/<id>-e1.webp or <id>-t1.webp (Supabase, or the site's copy img/m/pc2/<id>-e1[.v<n>].webp),
//   img/rl/<id>-e1.webp, img/fr/<id>-e1.webp, img/cut/<id>-e1.webp (the re-cut of 26 Nov 2026: scripts/photo_recut_apply.py,
//   data/photo_recut.json), and products/store2/<name>-t1.webp (store photos),
//   products/pc/<id>.webp, img/p/ and img/p2/ (26 Nov 2026: every one of the 1,845 that loads is a cut-out, checked).
export const CUT_RX = /^\/(?:storage\/v1\/object\/public\/products|img\/m)\/pc2\/[\w-]+-[et]1(?:\.v[\w-]+)?\.webp$|^\/img\/(?:rl|fr|cut)\/[\w-]+-e1\.webp$|^\/storage\/v1\/object\/public\/products\/store2\/[\w.-]+-t1\.webp$|^\/storage\/v1\/object\/public\/products\/pc\/[\w-]+\.webp$|^\/img\/p2?\/[\w-]+\.webp$/;
// The path of a photo address as CUT_RX reads it: the Supabase address inside /api/img?u=, without host, Cloudflare
// resize prefix (/cdn-cgi/image/...) or query.
export function cutPath(u) {
  u = String(u || "");
  const q = u.indexOf("/api/img?");
  if (q >= 0) { try { u = new URLSearchParams(u.slice(q + 9)).get("u") || ""; } catch (e) { u = ""; } }
  return u.replace(/^https?:\/\/[^/]+/, "").replace(/^\/cdn-cgi\/image\/[^/]+/, "").replace(/[?#].*$/, "");
}

// The finds whose photo keeps the light tile in dark mode although it may be a cut-out, with the reason (review of the
// photo-edge run, 25 Nov 2026: 41 half see-through, 22 with a prop or backdrop, 8 that are not cut-outs; the re-cut of
// 26 Nov 2026, data/photo_recut.json, gave 30 of those 49 a clean cut-out and took them off: 17 and 2 are left). This list is
// the only copy: add or remove an id here, then raise PRODUCT_TPL in pages.js so cached pages pick the change up.
export const TILE_LIGHT = {
  "7509414855": "a white dust cloth kept with the bag, plain on #262626",
  "7717221359": "held by a white glove, plain on #262626",
  "7680428832": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "7708648884": "not a cut-out (the photo has no transparency, it is a plain photo on its own background)",
  "5014331360": "shown on a clear acrylic stand, plain on #262626",
  "7704571152": "shown on a white display form, plain on #262626",
  "7742892345": "shown on a white mannequin head, plain on #262626",
  "7778420206": "shown on white watch cushions, plain on #262626",
  "7672715493": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675241904": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675295262": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7675803344": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7676232932": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7677515795": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7680468108": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "7737657814": "the old cut-out leaves the item half see-through: murky on #262626 (needs a new cut-out)",
  "6636749467": "white pieces of the stand at the bottom, plain on #262626",
};
export const TILE_LIGHT_IDS = new Set(Object.keys(TILE_LIGHT));
// The same ids for the app, as the script functions/_middleware.js puts at the top of every app page.
// Finds whose own photo is a transparent cut-out at an address CUT_RX does not know (img/p, img/p2, img/fr without -e1,
// products/pc and products/store): each photo checked for real transparency on 26 Nov 2026 (15% or more see-through
// pixels), the light list left out. Only the find's own photo counts, not its other gallery photos.
export const TILE_CUT_IDS = new Set("1004752923420 1019651039477 4261053639 4266605214 4380572774 4528251115 4881359690 4906253529 547276651722 5782661893 6289054660 6375784450 6532928992 6611979864 6646357483 6716583439 677989357267 7018439280 7230414547 7231806587 7233949100 7244818321 7246750960 7255395534 7271199746 7280214525 7280264052 7286333182 7294857785 7297417785 7310506402 7322430128 740333013030 7408052054 7411539879 7447925231 7451981290 7460052129 746801458197 7468401317 7468583149 7498910877 7510008361 7511182213 7519525216 7520856902 7523917431 7530833884 7539696765 7549272748 7553359982 7555693504 7563973209 7568192821 7568821648 7571374839 7572414981 7576583381 7578520838 7584606843 7590879974 7613573235 7614595612 7616404424 7633706726 7638946262 7641869736 7643072971 7643100615 7643114491 7645975387 7647547734 7651677804 7653801473 765572182030 7655723864 7656868228 7657202943 7663734281 7669726223 7674858492 7675153310 7675788248 7675843316 7677433025 7697488658 7705659361 7705672927 7705790885 7706300213 7706320031 7708634954 7708655180 7708720002 7708725994 7709109370 7710297442 7710342682 7710399464 7710404292 7710407670 7710915428 7710989811 7717215469 7717231227 7717260949 7720237134 7720262748 7723740768 7725706759 7725728559 7728091069 7728108867 7728423700 7728570755 7728574481 7728738210 7728880989 7728955939 7730119566 7731048984 7731118630 7731171934 7731187610 7731238228 7731478698 7734287791 7735197630 7735280075 7736077748 7737128603 7737220505 7737230400 7737231238 7737559442 7739786803 7767962483 7767997777 776834980271 7770950536 7771492546 7771803372 7778238818 7778392674 7779137091 7786423067 7790611448 7791514418 779652898394 7808305261 7811812951 7822521712 7883520345 803122863831 803450504856 835914589462 842477997350 844207943975 846177667601 849786036555 860475096075 900738030952 918932928316 922830285119 923275906239 924458142833 960508930674 969492407302 976896164628 982073021643 993380137528 998431478098".split(" "));
export const TILE_LIGHT_JS = `<script>window.PC_TILE_LIGHT="${[...TILE_LIGHT_IDS].join(" ")}";window.PC_TILE_CUT="${[...TILE_CUT_IDS].join(" ")}"</script>`;
