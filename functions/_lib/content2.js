// Second batch of editorial copy: more brand intros, model ("best X rep") pages, guides and tool pages.
// Keep claims general and factual — no invented prices, fees or dates.

const b = (what, check) => `<p>${what}</p><p><strong>What to check in QC:</strong> ${check}</p>`;

export const BRAND_INTRO2 = {
  "Fendi": b("Fendi finds centre on the FF monogram: Baguette and Peekaboo-style bags, belts, scarves, knitwear and slides.", "FF pattern alignment at seams and pockets, hardware finish and engraving, and the heat stamp inside bags."),
  "Gallery Dept": b("Gallery Dept is the LA label known for paint-splattered flared jeans, distressed hoodies and hand-drawn logo tees.", "the logo print, that paint splatter and distressing look deliberate rather than messy, and the flare shape of the jeans against the size chart."),
  "New Balance": b("New Balance finds are mostly lifestyle runners: the 550, 2002R, 9060, 990 series and more.", "the N logo shape and stitching, suede and mesh quality, sole shape from the side, and the size tag inside the tongue."),
  "Celine": b("Celine finds include the Triomphe logo pieces: bags, belts, caps, sunglasses and minimal tees.", "the Triomphe hardware (shape, edges and finish), logo font on tees and caps, and leather grain on bags."),
  "Saint Laurent": b("Saint Laurent finds range from Court Classic sneakers and Wyatt boots to belts, bags and knitwear with the YSL monogram.", "the YSL monogram proportions and spacing, leather quality, sole stitching on shoes and hardware finish on belts."),
  "Asics": b("Asics finds are mostly retro runners like the Gel-Kayano 14, Gel-NYC and GT-2160 — cheap to buy and popular for daily wear.", "the stripe shape and placement, gel window details, mesh quality and the size tag."),
  "Chanel": b("Chanel finds include quilted bags, ballet flats, slingbacks, jewellery and accessories with the interlocking CC.", "the CC logo overlap and proportions, quilting stitch spacing, chain weight and the stamps inside."),
  "Loewe": b("Loewe finds centre on the Anagram logo: Puzzle and Flamenco-style bags, knitwear, caps and leather goods.", "the Anagram embroidery or debossing, leather edges and stitching, and the colour against the listing."),
  "Broken Planet": b("Broken Planet is the London label behind the puff-print hoodies and sweatpants with space-themed graphics.", "the puff print (it should be raised and crisp, not flat), colour of the graphics, fabric weight and the neck label."),
  "Hellstar": b("Hellstar is known for flame and star graphics on hoodies, tees and flared sweatpants.", "print sharpness and colours, the fit of flared sweatpants against the size chart, and the neck print or tag."),
  "Sp5der": b("Sp5der is known for web-print hoodies and sweatpants in bright colours, often with rhinestone or puff details.", "the web graphic (puff or rhinestones should be even), colour accuracy under neutral light and the fit."),
  "Yeezy": b("Yeezy finds are mostly the 350 V2, Slides and Foam Runner.", "the primeknit pattern and stripe on the 350, midsole shape and texture, the heel tab and the size tag."),
  "Carhartt": b("Carhartt WIP finds include the Detroit jacket, double-knee pants, workwear shirts and the classic beanie.", "the square logo label, canvas weight and colour, and stitching on pockets and knees."),
  "On": b("On finds are running shoes like the Cloudmonster and Cloud 5, recognisable by the CloudTec sole pods.", "the shape and spacing of the sole pods, logo placement, upper mesh and the size tag."),
  "Goyard": b("Goyard finds centre on the chevron Goyardine canvas: Saint Louis totes, card holders and wallets.", "chevron alignment across seams, the painted look of the pattern, edge paint and leather trim."),
  "Ami": b("Ami Paris finds are mostly knitwear and sweatshirts with the red Ami de Coeur heart logo.", "the heart embroidery (shape, colour and density), knit texture and the neck label."),
  "Rick Owens": b("Rick Owens and DRKSHDW finds include Ramones and Geobasket sneakers, draped tees and cargo pants.", "sole shape and thickness, leather or canvas quality, and the proportions — Rick Owens fits are long and dropped."),
  "Denim Tears": b("Denim Tears is known for the cotton wreath print on jeans, hoodies and sweatpants.", "the wreath print (placement, colour and sharpness), the wash of the denim and the fit."),
  "Rolex": b("Watch finds in the Rolex style: Submariner, Datejust, Daytona and GMT-type models.", "dial print, the date magnifier, bezel alignment, bracelet finish and the movement described in the listing. Ask for extra photos and videos before shipping."),
  "Syna World": b("Syna World finds are mostly tracksuits, hoodies and tees with embroidered logos.", "logo embroidery density and placement, fabric weight and the fit of tracksuit sets."),
  "Versace": b("Versace finds include Medusa-head pieces, Barocco prints, shirts, belts and slides.", "the Medusa details, print alignment on Barocco pieces and hardware finish."),
  "Represent": b("Represent is the UK label behind the Owners Club hoodies and heavyweight tees.", "print and embroidery quality, fabric weight and the oversized fit against the size chart."),
  "Palace": b("Palace is the London skate label with the Tri-Ferg triangle logo on tees, hoodies and caps.", "the Tri-Ferg print or embroidery, neck labels and colour accuracy."),
  "Patagonia": b("Patagonia finds are mostly fleeces (Retro-X, Better Sweater), shells and caps with the P-6 logo.", "the P-6 patch, fleece texture and loft, and zip pulls."),
  "Under Armour": b("Under Armour finds are training and compression pieces.", "logo print or reflective details, fabric stretch and the size tag."),
  "Off-White": b("Off-White finds include diagonal-arrow hoodies and tees, the industrial belt and the zip-tie tag.", "arrow print placement and sharpness, the quotation-mark text and the belt lettering."),
  "Palm Angels": b("Palm Angels finds are track pants and jackets with side stripes, plus logo tees and hoodies.", "stripe lettering and placement, print quality and the fit."),
  "Bottega Veneta": b("Bottega Veneta finds centre on the intrecciato leather weave: pouches, Jodie-style bags, sandals and wallets.", "how even the weave is, leather softness and edges, and hardware."),
  "Acne Studios": b("Acne Studios finds include the face-patch knits and sweatshirts, scarves and jeans.", "the face patch (shape and stitching), knit texture and scarf fringe."),
  "Rhude": b("Rhude finds are tees, shorts and hoodies with bandana and racing-inspired graphics.", "print sharpness and colours, and the fit against the size chart."),
  "Salomon": b("Salomon finds are trail sneakers like the XT-6 and ACS Pro.", "the Quicklace system, sole shape and grip pattern, colour blocking and the size tag."),
  "Cartier": b("Cartier-style finds include Love and nail bracelets, rings and Santos/Tank-style watches.", "screw and nail motifs, engraving depth, weight and finish, and the clasp."),
  "Balmain": b("Balmain finds include logo knits, tees and jackets with embossed buttons.", "button embossing, logo print or knit and structured shoulders on jackets."),
  "Canada Goose": b("Canada Goose finds are parkas and vests like the Expedition and Chilliwack, with the round disc patch on the sleeve.", "the disc patch (colours and stitching), fill and loft, fur-trim quality and zips. Parkas are bulky, so compare shipping lines."),
  "Arc'teryx": b("Arc'teryx finds are shells and insulated jackets like the Beta, Alpha and Atom, with the embroidered bird logo.", "the bird logo embroidery, taped seams inside, water-resistant zips and the fit (Arc'teryx runs trim)."),
  "CP Company": b("C.P. Company finds include goggle hoodies and jackets and pieces with the lens on the sleeve.", "the goggle lenses and their frames, the sleeve lens badge and garment-dyed colour."),
  "Fear of God": b("Fear of God mainline finds (separate from Essentials) include hoodies, relaxed trousers and outerwear.", "fabric weight, the relaxed fit and branding details."),
  "Travis Scott": b("Travis Scott finds include Cactus Jack merch and the reverse-swoosh sneaker collaborations.", "the reverse swoosh placement and shape, suede quality and the tongue and heel details."),
  "Lululemon": b("Lululemon finds are athletic pieces like the ABC pants and Define jacket.", "fabric stretch and feel, the reflective logo and the waistband."),
  "Kith": b("Kith finds are box-logo hoodies, tees and caps.", "box-logo embroidery and letter spacing, fabric weight and colour."),
  "Cole Buxton": b("Cole Buxton is the London label for heavyweight, minimal basics: hoodies, tees and sweatpants.", "fabric weight and texture, the small logo detail and the boxy fit."),
  "Calvin Klein": b("Calvin Klein finds are mostly underwear, jeans and basics.", "the waistband logo, fabric feel and the size tag."),
  "Givenchy": b("Givenchy finds include 4G-logo pieces, bags, sneakers and tees.", "the 4G hardware or print, leather quality and logo fonts."),
  "Purple Brand": b("Purple Brand finds are mostly jeans with distinctive washes and coatings.", "the wash and coating against the listing, hardware and the fit."),
  "Eric Emanuel": b("Eric Emanuel is known for the EE mesh basketball shorts in many colourways.", "mesh quality, the EE embroidery and the inseam length."),
  "Puma": b("Puma finds include retro sneakers like the Speedcat and Palermo.", "the formstrip shape, suede quality and the sole."),
  "Valentino": b("Valentino finds include Rockstud shoes and bags and Open sneakers.", "stud size, shape and finish, leather quality and the stripe on Open sneakers."),
  "Omega": b("Omega-style watch finds include Speedmaster and Seamaster-type models.", "dial print, bezel alignment, bracelet finish and the movement described in the listing."),
  "Hoka": b("Hoka finds are cushioned runners like the Clifton and Bondi.", "midsole shape and thickness, logo placement and the size tag."),
  "Lego": b("Building-set finds, mostly large display sets.", "box condition, the piece count against the listing and the instruction booklets. Big boxes add a lot of volumetric weight."),
};

export const MODELS = [
  { slug: "golden-goose-super-star", name: "Golden Goose Super-Star", rx: "golden goose.*super.?star", intro: "The distressed Super-Star with the star on the side and the heel tab is the best-known Golden Goose model.", qc: ["star shape, size and placement", "the heel tab text and colour", "that the distressing looks natural, not painted on"] },
  { slug: "maison-margiela-gat", name: "Maison Margiela Replica / GAT sneakers", rx: "maison margiela.*(sneaker|gat|replica)", intro: "Margiela's Replica sneaker (the GAT shape) is the minimal old-money trainer: suede T-toe, gum sole and the four-stitch label.", qc: ["the four white stitches and number label on the heel", "suede quality and the T-toe shape", "gum sole colour"] },
  { slug: "nike-air-force-1", name: "Nike Air Force 1", rx: "air force 1|\\baf1\\b", intro: "The Air Force 1 is one of the most-bought sneakers of all time, in white-on-white and dozens of collab colourways.", qc: ["toe box shape (not too boxy)", "swoosh shape and stitching", "the AIR text on the midsole and the size tag"] },
  { slug: "nike-dunk", name: "Nike Dunk", rx: "\\bdunk\\b", intro: "Dunk Lows and Highs in panda and collab colourways are a staple on every spreadsheet.", qc: ["toe box and overall shape from the side", "swoosh placement", "stitching quality and the size tag"] },
  { slug: "air-jordan-1", name: "Air Jordan 1", rx: "jordan 1\\b|aj1", intro: "The Jordan 1 in High, Mid and Low. Shape varies a lot between batches, so buyer QC photos matter here.", qc: ["the heel hourglass shape (High)", "wings logo depth and placement", "swoosh shape and the size tag"] },
  { slug: "air-jordan-4", name: "Air Jordan 4", rx: "jordan 4\\b|aj4", intro: "The Jordan 4 with its mesh panels, wings and visible Air unit.", qc: ["tongue tag and Jumpman", "netting angle on the side panels", "heel tab and the visible Air unit"] },
  { slug: "nike-tech-fleece", name: "Nike Tech Fleece", rx: "tech fleece", intro: "Tech Fleece hoodies, joggers and full sets.", qc: ["zip and pocket placement", "fabric thickness and texture", "swoosh print or rubber logo"] },
  { slug: "adidas-samba", name: "Adidas Samba", rx: "samba", intro: "The Samba OG with its T-toe and gum sole, one of the most popular terrace sneakers.", qc: ["T-toe overlay shape", "three-stripe placement and gold lettering", "gum sole colour"] },
  { slug: "new-balance-2002r", name: "New Balance 2002R", rx: "2002r", intro: "The 2002R in grey and protection-pack colourways, a comfortable everyday runner.", qc: ["N logo shape and stitching", "mesh and suede quality", "sole shape and the size tag"] },
  { slug: "balenciaga-track", name: "Balenciaga Track", rx: "balenciaga.*track", intro: "The layered Track trainer. Heavy, so ship it without the box.", qc: ["layered sole construction", "logo prints on the side and tongue", "sizing (Balenciaga often runs large)"] },
  { slug: "moncler-puffer", name: "Moncler puffer jackets", rx: "moncler.*(puffer|down)", intro: "Moncler puffers and gilets, the most-bought winter finds on the spreadsheet.", qc: ["fill and loft (it should look full)", "felt or rubber logo patch on the sleeve", "zips, snaps and inner tags"] },
  { slug: "the-north-face-nuptse", name: "The North Face Nuptse", rx: "nuptse", intro: "The 1996 Nuptse puffer in black and colour-blocked versions.", qc: ["embroidered logo on chest and back", "baffle shape and fill", "zip and the stowable hood"] },
  { slug: "stone-island-overshirt", name: "Stone Island overshirts", rx: "stone island.*overshirt", intro: "Stone Island overshirts with the compass badge on the left sleeve.", qc: ["the compass badge and its two buttons", "garment-dyed colour", "inner labels"] },
  { slug: "corteiz-cargos", name: "Corteiz cargos", rx: "corteiz.*cargo", intro: "The Corteiz Guerillaz cargos, the most-searched Corteiz item.", qc: ["Alcatraz logo on the pocket", "fabric and pocket construction", "fit — Corteiz cargos are cut relaxed"] },
  { slug: "corteiz-alcatraz", name: "Corteiz Alcatraz tees & hoodies", rx: "alcatraz", intro: "Corteiz tees and hoodies with the Alcatraz logo.", qc: ["logo print or embroidery sharpness", "size and placement of the logo", "the boxy fit"] },
  { slug: "essentials-hoodie", name: "Fear of God Essentials hoodie", rx: "essentials.*hoodie", intro: "The Essentials hoodie, a popular first order: cheap, light and easy to size.", qc: ["the rubberised ESSENTIALS chest logo", "fabric weight", "the oversized fit"] },
  { slug: "ralph-lauren-cable-knit", name: "Ralph Lauren cable-knit sweaters", rx: "ralph lauren.*cable", intro: "The Ralph Lauren cable knit is the core old-money piece.", qc: ["cable definition and knit texture", "the small pony embroidery", "neck label and ribbing"] },
  { slug: "ralph-lauren-polo", name: "Ralph Lauren polo shirts", rx: "ralph lauren.*polo shirt", intro: "Classic Ralph Lauren piqué polos in every colour.", qc: ["pony embroidery density", "collar shape and placket", "the size label"] },
  { slug: "loro-piana-summer-walk", name: "Loro Piana Summer Walk & loafers", rx: "summer walk|loro piana.*loafer", intro: "The Summer Walk loafer is the definitive quiet-luxury shoe.", qc: ["suede nap and colour", "stitching around the toe", "sole and the small metal charm"] },
  { slug: "arcteryx-jacket", name: "Arc'teryx jackets", rx: "arc.?teryx.*(jacket|shell)", intro: "Arc'teryx Beta, Alpha and Atom-type jackets.", qc: ["bird logo embroidery", "taped seams inside", "water-resistant zips"] },
  { slug: "canada-goose-parka", name: "Canada Goose parkas", rx: "canada goose", intro: "Canada Goose parkas and vests with the disc patch.", qc: ["disc patch colours and stitching", "fill and fur trim", "zips and snaps"] },
  { slug: "chrome-hearts-hoodie", name: "Chrome Hearts hoodies", rx: "chrome hearts.*hoodie", intro: "Chrome Hearts zip and pullover hoodies with the horseshoe and cross graphics.", qc: ["graphic print quality", "cross or horseshoe details", "zip pulls"] },
  { slug: "sp5der-hoodie", name: "Sp5der hoodies", rx: "sp5der.*hoodie", intro: "Sp5der web hoodies in bright colourways.", qc: ["web print (puff or rhinestones)", "colour accuracy", "fit"] },
  { slug: "denim-tears-hoodie", name: "Denim Tears hoodies", rx: "denim tears.*hoodie", intro: "Denim Tears hoodies with the cotton wreath print.", qc: ["wreath print placement and colour", "fabric weight", "neck label"] },
  { slug: "bape-shark-hoodie", name: "Bape Shark hoodies", rx: "bape.*shark", intro: "The Bape full-zip Shark hoodie with the camo pattern.", qc: ["shark face print and zip up to the hood", "camo colours and pattern", "WGM lettering"] },
  { slug: "yeezy-350", name: "Yeezy 350 V2", rx: "yeezy.*350|350 v2", intro: "The Yeezy Boost 350 V2 in its many colourways.", qc: ["primeknit pattern and stripe", "midsole shape and texture", "heel tab"] },
  { slug: "burberry-scarf", name: "Burberry scarves", rx: "burberry.*scarf", intro: "Burberry check cashmere-style scarves, a classic gift find.", qc: ["check pattern alignment", "fringe and edges", "the label"] },
  { slug: "louis-vuitton-trainer", name: "Louis Vuitton Trainer", rx: "louis vuitton.*trainer", intro: "The LV Trainer basketball-style sneaker.", qc: ["sole shape and monogram details", "panel stitching", "tongue and heel branding"] },
  { slug: "dior-b23", name: "Dior B23 & B-series sneakers", rx: "b23|b22|b30", intro: "Dior's B23 high-tops in oblique canvas and the chunkier B22 and B30.", qc: ["oblique pattern clarity (B23)", "sole shape", "logo details"] },
];

export const GUIDES2 = {
  "how-to-buy-from-taobao": {
    title: "How to Buy from Taobao Internationally (2026 Step-by-Step)",
    desc: "Taobao doesn't ship most items abroad. Here's how to buy from Taobao with a shopping agent, including costs, QC photos and shipping.",
    h1: "How to buy from Taobao",
    body: `<p class="lead">Taobao is China's biggest online marketplace, with millions of independent shops. Most sellers only ship inside China and the site is in Chinese, so buyers abroad use a <strong>shopping agent</strong> to buy, inspect and ship for them.</p>
<h2>Step by step</h2><ol class="steps">
<li><strong>Find the item.</strong> Browse <a href="/">Puro Classico</a> (Taobao finds are marked "Taobao"), or copy a Taobao link — it looks like <code>item.taobao.com/item.htm?id=…</code>.</li>
<li><strong>Open it in your agent.</strong> Tap "Buy via MyCNBox" on a find, or paste the Taobao link into your agent's search bar. Our <a href="/tools/link-converter">link converter</a> does this for any link.</li>
<li><strong>Choose the size and colour</strong> (agents translate the options) and pay for the item plus domestic delivery to the agent's warehouse.</li>
<li><strong>Check the QC photos</strong> when it reaches the warehouse (<a href="/guides/how-to-qc">how to read them</a>).</li>
<li><strong>Combine items and ship.</strong> Pick a shipping line and pay international shipping — see <a href="/guides/shipping-lines">shipping lines explained</a>.</li></ol>
<h2>Taobao vs Weidian vs 1688</h2><ul><li><strong>Taobao</strong>: the biggest range; many shops, varied quality.</li><li><strong>Weidian</strong>: mobile shop platform where many rep sellers list (<a href="/guides/how-to-buy-from-weidian">guide</a>).</li><li><strong>1688</strong>: wholesale/factory prices, sometimes with minimum quantities (<a href="/guides/how-to-buy-from-1688">guide</a>).</li></ul>
<h2>Tips</h2><ul><li>Check the shop's ratings and recent reviews inside your agent.</li><li>Tmall listings are Taobao's branded-store side; agents handle them the same way.</li><li>Measure a garment you own and compare with the size chart in centimetres (<a href="/guides/sizing">sizing guide</a>).</li></ul>`,
    faq: [["Does Taobao ship internationally?", "Some items can be shipped abroad through Taobao's own programme, but most sellers only ship within China, so international buyers usually use a shopping agent."], ["Is it safe to buy from Taobao with an agent?", "Agents act as the buyer, check the item at their warehouse and send you QC photos before international shipping, which lowers the risk of receiving the wrong item."]],
  },
  "how-to-buy-from-1688": {
    title: "How to Buy from 1688.com (Factory Prices) with a Shopping Agent",
    desc: "1688 is Alibaba's Chinese wholesale site. How to buy single items from 1688 through a shopping agent, and what to watch for.",
    h1: "How to buy from 1688",
    body: `<p class="lead">1688.com is Alibaba's domestic wholesale marketplace. Prices are often close to factory prices, but it's built for Chinese businesses, so international buyers use a shopping agent.</p>
<h2>What's different about 1688</h2><ul><li><strong>Minimum order quantities:</strong> some listings require several pieces. Many clothing sellers allow single pieces; your agent shows the minimum.</li><li><strong>Plain listings:</strong> photos and titles are often basic, so buyer QC photos matter more.</li><li><strong>Prices can be tiered</strong> — cheaper per piece at higher quantities.</li></ul>
<h2>Step by step</h2><ol class="steps"><li>Find a 1688 find on <a href="/">Puro Classico</a> (marked "1688") or copy a link like <code>detail.1688.com/offer/….html</code>.</li><li>Open it in your agent (tap Buy, or use the <a href="/tools/link-converter">link converter</a>).</li><li>Check the minimum quantity and pick size and colour, then pay for the item plus delivery to the warehouse.</li><li>Check the QC photos, then combine items and ship.</li></ol>
<p>New to agents? Watch the <a href="/how-to-order">how-to-order video</a>.</p>`,
    faq: [["Can I buy a single item on 1688?", "Often yes for clothing and accessories, but some listings have a minimum order quantity. Your agent shows it before you pay."]],
  },
  "mycnbox-review": {
    title: "MyCNBox Review 2026: How It Works, Coupons, QC & Shipping",
    desc: "An honest look at MyCNBox: how ordering works, new-user coupons, QC photos, packing and shipping, and who it suits.",
    h1: "MyCNBox review",
    body: `<p class="lead">MyCNBox is a shopping agent for Taobao, Weidian and 1688. It's the agent we use most on Puro Classico, so here's how it works in practice. (Disclosure: our MyCNBox links are affiliate links.)</p>
<h2>How ordering works</h2><ol class="steps"><li>Open a listing (every Puro Classico find opens pre-filled in MyCNBox).</li><li>Pay for the item plus domestic delivery to the warehouse. International shipping is paid later.</li><li>MyCNBox buys from the seller; when the item arrives you get QC photos under <em>Warehouse</em>.</li><li>Select items and submit packing, choose a carrier, apply coupons and pay the estimated shipping. MyCNBox's guide says any difference is refunded to your balance if the final cost is lower.</li><li>Track the parcel under <em>Parcels</em>.</li></ol>
<h2>What stands out</h2><ul><li><strong>New-user coupons:</strong> MyCNBox advertises a new-user coupon bundle (shown as up to $500 on its site at the time of writing) — <a href="https://mycnbox.com/login/main-login?inviteCode=AACPYA" rel="sponsored noopener" target="_blank">claim it here</a>.</li><li><strong>Two-step payment:</strong> you only commit to shipping once you've seen the QC photos.</li><li><strong>Apps:</strong> iOS and Android apps as well as the website.</li><li><strong>Ratings:</strong> MyCNBox's own site shows a high Trustpilot score — check the latest reviews on Trustpilot yourself.</li></ul>
<h2>Who it suits</h2><p>First-time buyers who want a simple flow, and anyone ordering from Puro Classico, since every find opens directly in MyCNBox. If you already use another agent, every find also has KakoBuy, Oopbuy, LoveGoBuy and Sugargoo links — compare with <a href="/guides/kakobuy-vs-mycnbox">KakoBuy vs MyCNBox</a>.</p>
<p>Watch the full flow in our <a href="/how-to-order">1:47 video</a>.</p>`,
    faq: [["Is MyCNBox legit?", "MyCNBox is an established shopping agent with warehouse QC photos, public help pages and apps. As with any agent, start with a small order and check the latest independent reviews."], ["Does MyCNBox charge shipping upfront?", "No. You pay for the item and domestic delivery first, and international shipping only when you submit your parcel."]],
  },
  "kakobuy-vs-mycnbox": {
    title: "KakoBuy vs MyCNBox (2026): Which Shopping Agent Should You Use?",
    desc: "KakoBuy and MyCNBox compared: ordering flow, coupons, QC photos, shipping lines and which to pick for your first order.",
    h1: "KakoBuy vs MyCNBox",
    body: `<p class="lead">Both are full-service shopping agents for Taobao, Weidian and 1688, and the basic flow is identical: pay for the item, check QC photos at the warehouse, then combine and ship. The differences are in the details. (Disclosure: our agent links are affiliate links.)</p>
<h2>Side by side</h2><table style="width:100%;border-collapse:collapse"><tr><th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)"></th><th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">MyCNBox</th><th style="text-align:left;padding:8px;border-bottom:1px solid var(--line)">KakoBuy</th></tr>
<tr><td style="padding:8px;border-bottom:1px solid var(--line)">Marketplaces</td><td style="padding:8px;border-bottom:1px solid var(--line)">Taobao, Weidian, 1688</td><td style="padding:8px;border-bottom:1px solid var(--line)">Taobao, Weidian, 1688</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid var(--line)">From Puro Classico</td><td style="padding:8px;border-bottom:1px solid var(--line)">Listing opens pre-filled</td><td style="padding:8px;border-bottom:1px solid var(--line)">Listing opens pre-filled</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid var(--line)">New-user offer</td><td style="padding:8px;border-bottom:1px solid var(--line)">Coupon bundle (advertised up to $500)</td><td style="padding:8px;border-bottom:1px solid var(--line)">Welcome coupon bundle</td></tr>
<tr><td style="padding:8px;border-bottom:1px solid var(--line)">QC photos</td><td style="padding:8px;border-bottom:1px solid var(--line)">Yes, at the warehouse</td><td style="padding:8px;border-bottom:1px solid var(--line)">Yes, at the warehouse</td></tr>
<tr><td style="padding:8px">Community</td><td style="padding:8px">Growing</td><td style="padding:8px">Very large (Reddit, Discord)</td></tr></table>
<h2>How to choose</h2><ul><li><strong>Compare shipping to your country.</strong> Put the same parcel weight into both agents' shipping estimators — lines and prices change often and matter more than anything else.</li><li><strong>Use the new-user coupons</strong> on whichever you try first.</li><li><strong>You don't have to pick one forever</strong>: every Puro Classico find has links for both.</li></ul>
<p>Spreadsheets: <a href="/mycnbox-spreadsheet">MyCNBox spreadsheet</a> · <a href="/kakobuy-spreadsheet">KakoBuy spreadsheet</a> · <a href="/guides/best-shopping-agent">all agents compared</a>.</p>`,
    faq: [["Is KakoBuy or MyCNBox cheaper?", "It depends on your country and parcel. Compare the shipping estimate for the same weight in both agents before you order — shipping is usually the biggest cost difference."]],
  },
  "shipping-lines": {
    title: "Shipping Lines Explained: Economy, Tax-Free Lines, EMS & Express",
    desc: "How agent shipping lines work: economy vs special (tax-inclusive) lines vs EMS vs express couriers, volumetric weight and how to save on shipping.",
    h1: "Shipping lines explained",
    body: `<p class="lead">When you ship a parcel from your agent's warehouse you pick a <strong>shipping line</strong>. Lines differ in price, speed, tracking and how customs is handled — choosing well often matters more than the item price.</p>
<h2>Main types</h2><ul>
<li><strong>Economy / postal lines</strong>: cheapest, slowest, basic tracking.</li>
<li><strong>Special lines</strong> (often labelled "tax-free", "tax-inclusive" or by country, e.g. "UK Air Cargo"): built for a specific destination; some include import duties in the price. Read the line's notes in your agent.</li>
<li><strong>EMS</strong>: the international postal express service — usually mid-priced with decent tracking.</li>
<li><strong>Express couriers</strong> (DHL, FedEx, UPS): fastest and best tracking, but usually the most expensive and duties are typically charged on delivery.</li></ul>
<h2>Volumetric weight</h2><p>Carriers charge the higher of the actual weight and the <em>volumetric</em> weight, calculated from the box size (commonly length × width × height in cm ÷ 5,000 or 6,000, depending on the line). That's why shoe boxes are expensive to ship.</p>
<h2>How to save</h2><ul><li>Combine several items into one parcel.</li><li>Remove shoe boxes and extra packaging; vacuum-pack puffers and hoodies.</li><li>Compare two or three lines for your country in the agent's estimator.</li><li>Keep the declared value accurate and follow your country's import rules.</li></ul>
<p>Rough estimate: <a href="/tools/weight-estimator">weight estimator</a> → <a href="/tools/shipping-calculator">shipping calculator</a>.</p>`,
    faq: [["Which shipping line is fastest?", "Express couriers like DHL or FedEx are usually fastest, then EMS and special lines, then economy postal lines."], ["What is volumetric weight?", "A weight calculated from the box size. Carriers charge whichever is higher: the real weight or the volumetric weight."]],
  },
};

export const TOOLS = {
  "link-converter": { name: "Link Converter", title: "Rep Link Converter — Weidian, Taobao & 1688 to Any Agent · Puro Classico",
    desc: "Convert any Weidian, Taobao, 1688 or agent link into a buy link for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo. Free, instant.",
    lead: "Paste any Weidian, Taobao, 1688 or shopping-agent link and get a buy link for every agent.",
    about: "<p>The converter reads the marketplace and item ID from the link (it works with agent links too, like MyCNBox, KakoBuy or CNFans product URLs) and rebuilds it for each agent. Nothing is stored.</p>" },
  "qc-checker": { name: "QC Checker", title: "QC Photo Checker — Find Real QC Photos for Any Rep Link · Puro Classico",
    desc: "Paste a Weidian, Taobao or 1688 link or item ID to see real buyer QC photos before you order.",
    lead: "Paste a product link or item ID to see real warehouse QC photos from people who already bought it.",
    about: "<p>QC photos only exist for items someone has already bought through an agent, so newer listings may not have any yet. Learn <a href=\"/guides/how-to-qc\">how to read QC photos</a>.</p>" },
  "weight-estimator": { name: "Weight Estimator", title: "Rep Weight Estimator — Shipped Weight by Item Type · Puro Classico",
    desc: "Estimate the shipped weight of a hoodie, jacket, sneakers or other find before you pay for international shipping.",
    lead: "Pick an item type (or several) for a rough shipped weight including packaging.",
    about: "<p>These are typical shipped weights including light packaging. Your agent weighs the real parcel. Shoes in boxes and puffers take more space, which can raise the <a href=\"/guides/shipping-lines\">volumetric weight</a>.</p>" },
  "shipping-calculator": { name: "Shipping Calculator", title: "Rep Shipping Calculator — Estimate Agent Shipping Costs · Puro Classico",
    desc: "Ballpark international shipping costs from China by destination and weight for economy, registered and express lines.",
    lead: "Pick your destination and parcel weight for a ballpark cost on common line types.",
    about: "<p>Estimates only — real prices depend on the agent, line, box size and current promotions. Always check your agent's own estimator before paying. See <a href=\"/guides/shipping-lines\">shipping lines explained</a>.</p>" },
};
