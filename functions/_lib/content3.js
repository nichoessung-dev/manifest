// Second batch of "best X rep" model pages and guides (2026-09-30). Merged into MODELS / GUIDES in pages.js.

export const MODELS3 = [
  { slug: "corteiz-tracksuits", name: "Corteiz tracksuits & hoodies", rx: "corteiz.*(tracksuit|track|hoodie|jogger)", intro: "Corteiz tracksuits, hoodies and joggers — the Alcatraz logo pieces are the most-wanted drops from the London label.", qc: ["Alcatraz logo size, print or embroidery quality", "fabric weight (it should feel heavy, not thin)", "cuffs, drawcords and the neck tag"] },
  { slug: "trapstar-jacket", name: "Trapstar jackets", rx: "trapstar.*(jacket|puffer|irongate|windbreaker|shooters)", intro: "Trapstar Irongate puffers, Shooters windbreakers and jackets, the London streetwear staple.", qc: ["Irongate T logo shape and badge placement", "puffer fill and loft", "zips, poppers and inner tags"] },
  { slug: "trapstar-tracksuit", name: "Trapstar tracksuits & hoodies", rx: "trapstar.*(tracksuit|track|hoodie)", intro: "Trapstar tracksuits and hoodies with chenille, embroidered or printed logos.", qc: ["chenille or embroidery density", "logo spelling and spacing", "fabric weight and the fit of the joggers"] },
  { slug: "stone-island-hoodie", name: "Stone Island hoodies & sweatshirts", rx: "stone island.*(hoodie|sweat|crewneck)", intro: "Stone Island hoodies and crewnecks with the compass badge on the left sleeve.", qc: ["compass badge stitching and the two buttons", "badge colours and the back of the badge", "garment-dye colour evenness"] },
  { slug: "hellstar-hoodie", name: "Hellstar hoodies", rx: "hellstar.*(hoodie|sweat|zip)", intro: "Hellstar hoodies and zips with bold puff and screen prints.", qc: ["print sharpness and puff height", "colour accuracy against retail photos", "fabric weight and the cropped boxy fit"] },
  { slug: "broken-planet-hoodie", name: "Broken Planet hoodies & pants", rx: "broken planet.*(hoodie|sweat|zip|pant)", intro: "Broken Planet Market hoodies and sweatpants with puff-print graphics.", qc: ["puff print height and texture", "wash or dye colour", "graphic spelling and placement"] },
  { slug: "syna-world-tracksuit", name: "Syna World tracksuits", rx: "syna.*(tracksuit|track|hoodie|jogger|short)", intro: "Syna World tracksuits, hoodies and shorts from Central Cee's label.", qc: ["Syna logo embroidery or print", "colour accuracy", "fabric weight and the jogger fit"] },
  { slug: "stussy-hoodie", name: "Stüssy hoodies", rx: "st[uü]ssy.*(hoodie|sweat|zip)", intro: "Stüssy hoodies and zips with the signature script logo.", qc: ["script logo shape (compare letter by letter)", "print or embroidery quality", "neck tag and fabric weight"] },
  { slug: "gallery-dept-jeans", name: "Gallery Dept. jeans", rx: "gallery dept.*(jean|flare|denim|pant)", intro: "Gallery Dept. flared and painted jeans, each designed to look hand-finished.", qc: ["paint splatter placement and colour", "the flare shape and length", "back patch and hardware"] },
  { slug: "amiri-jeans", name: "Amiri jeans", rx: "amiri.*(jean|denim)", intro: "Amiri MX1 and distressed jeans with leather or bandana panels.", qc: ["distressing and panel placement", "hardware engraving", "the slim, stacked fit"] },
  { slug: "purple-brand-jeans", name: "Purple Brand jeans", rx: "purple brand.*(jean|denim)", intro: "Purple Brand skinny jeans with waxed, painted or distressed finishes.", qc: ["wash and coating finish", "the back patch and tags", "fit through the thigh and leg opening"] },
  { slug: "chrome-hearts-jewelry", name: "Chrome Hearts jewellery", rx: "chrome hearts.*(ring|necklace|bracelet|chain|cross|pendant|earring)", intro: "Chrome Hearts rings, crosses, chains and bracelets in the gothic sterling-silver style.", qc: ["depth and sharpness of the engraving", "weight (silver pieces should feel solid)", "clasp quality and the stamped markings"] },
  { slug: "cartier-bracelet", name: "Cartier bracelets & rings", rx: "cartier.*(love|juste|bracelet|ring)", intro: "Cartier Love and Juste un Clou style bracelets and rings.", qc: ["screw motif spacing and depth", "colour of the gold or rose-gold finish", "engraving on the inside"] },
  { slug: "rolex-watches", name: "Rolex watches", rx: "rolex(?!.*clock)", intro: "Submariner, Datejust, Daytona and GMT-Master styles. Watches have the widest quality range of anything on the spreadsheet, so read QC photos closely.", qc: ["dial printing, date magnification and indices alignment", "bezel alignment and insert colour", "bracelet finish and the clasp engraving"] },
  { slug: "goyard-wallet-bag", name: "Goyard wallets & bags", rx: "goyard", intro: "Goyard card holders, wallets, totes and the Saint Louis bag with the chevron canvas.", qc: ["chevron pattern alignment across seams", "painted canvas colour", "edge paint and stitching"] },
  { slug: "louis-vuitton-bags", name: "Louis Vuitton bags & wallets", rx: "louis vuitton.*(bag|keepall|wallet|pouch|backpack|tote|duffle|messenger)", intro: "Keepalls, pouches, wallets and messengers in monogram and Damier canvas.", qc: ["monogram alignment and symmetry at the seams", "heat stamp font and spacing", "stitch count and edge paint on the handles"] },
  { slug: "lv-gucci-hermes-belts", name: "Designer belts (LV, Gucci, Hermès)", rx: "(louis vuitton|gucci|herm[eè]s).*belt", intro: "Designer belts: the LV Initiales, Gucci GG and Hermès H buckle.", qc: ["buckle shape, weight and plating", "leather or canvas quality", "the stamping on the back of the strap"] },
  { slug: "designer-sunglasses", name: "Designer sunglasses", rx: "sunglass", intro: "Sunglasses from Cartier, Tom Ford, Saint Laurent, Balenciaga and more.", qc: ["logo engraving on the temples", "hinge quality and frame symmetry", "lens tint and any lens etching"] },
  { slug: "football-shirts", name: "Football shirts", rx: "football jersey|(manchester|real madrid|barcelona|psg|paris saint|chelsea|arsenal|liverpool|juventus|ac milan|inter milan|bayern|dortmund|brazil|argentina|portugal|england|france|germany|italy|spain|netherlands).*(jersey|kit|shirt)", intro: "Club and national-team football shirts, home and away.", qc: ["crest and sponsor logo quality (heat-pressed or stitched)", "fabric texture (fan vs player version)", "name and number printing if customised"] },
  { slug: "asics-sneakers", name: "Asics sneakers", rx: "asics.*(sneaker|shoe|gel|kayano|running|trainer)", intro: "Asics Gel runners, the retro-tech trainers that became an everyday favourite.", qc: ["the stripe shape and placement", "mesh and overlay quality", "sole shape and the size tag"] },
  { slug: "gucci-ace", name: "Gucci Ace sneakers", rx: "gucci.*(ace|sneaker|trainer)", intro: "The Gucci Ace leather sneaker with the web stripe, plus other Gucci trainers.", qc: ["web stripe colours and stitching", "embroidered bee or motif", "leather quality and toe shape"] },
  { slug: "yeezy-slide", name: "Yeezy Slides & Foam Runners", rx: "yeezy.*(slide|foam)", intro: "Yeezy Slides and Foam Runners in every colourway.", qc: ["foam colour and texture", "the sole pattern and the footbed text", "sizing (Slides run small)"] },
  { slug: "ugg-boots", name: "UGG boots", rx: "\\bugg\\b", intro: "UGG Classic and Tasman styles in suede with a sheepskin-style lining.", qc: ["lining thickness", "suede colour and texture", "heel label and the sole logo"] },
  { slug: "hermes-oran-sandals", name: "Hermès Oran sandals", rx: "herm[eè]s.*(oran|sandal|chypre|slipper|slide)", intro: "The Hermès Oran sandal with the H cut-out, plus Chypre and other Hermès sandals.", qc: ["the H cut-out shape and edge finish", "leather colour and grain", "footbed stamping"] },
  { slug: "lacoste-polo", name: "Lacoste polo shirts", rx: "lacoste.*polo", intro: "The classic Lacoste piqué polo with the crocodile patch, an old-money staple.", qc: ["crocodile patch detail and placement", "piqué texture", "collar shape and the placket buttons"] },
  { slug: "ralph-lauren-quarter-zip", name: "Ralph Lauren quarter-zips", rx: "ralph lauren.*(quarter|1/4|half.?zip)", intro: "Ralph Lauren quarter-zip and half-zip knits, the easiest old-money layer.", qc: ["pony embroidery detail", "knit texture and weight", "zip pull and collar shape"] },
  { slug: "moncler-gilet", name: "Moncler gilets", rx: "moncler.*(gilet|vest)", intro: "Moncler down gilets, the lighter alternative to the puffer.", qc: ["fill and loft", "logo patch on the chest", "zip, snaps and inner tags"] },
  { slug: "essentials-tee", name: "Fear of God Essentials tees", rx: "essentials.*(tee|t-shirt)", intro: "Essentials tees with the rubber or printed ESSENTIALS logo.", qc: ["logo font and spacing", "fabric weight and the boxy fit", "neck tag and seams"] },
  { slug: "essentials-sweatpants", name: "Fear of God Essentials sweatpants & shorts", rx: "essentials.*(sweatpant|jogger|pant|short)", intro: "Essentials sweatpants and shorts, the matching half of the hoodie set.", qc: ["logo placement on the leg", "fleece weight", "cuffs and drawcord tips"] },
  { slug: "represent-hoodie", name: "Represent hoodies", rx: "represent.*(hoodie|sweat|tee)", intro: "Represent hoodies and tees from the Manchester label.", qc: ["print or embroidery quality", "the heavyweight fabric", "fit and neck tag"] },
  { slug: "palm-angels-tracksuit", name: "Palm Angels tracksuits", rx: "palm angels.*(track|hoodie|pant)", intro: "Palm Angels track jackets and pants with the side stripes.", qc: ["side stripe width and placement", "logo text and font", "zip and cuff quality"] },
  { slug: "off-white-hoodie", name: "Off-White hoodies & tees", rx: "off.?white.*(hoodie|tee|t-shirt|sweat)", intro: "Off-White hoodies and tees with the diagonal arrows and quoted text.", qc: ["arrow print alignment", "text font and spacing", "fabric weight"] },
  { slug: "supreme-box-logo", name: "Supreme Box Logo", rx: "supreme.*(box logo|bogo)", intro: "The Supreme Box Logo tee and hoodie, the most recognisable streetwear logo.", qc: ["box logo letter spacing and the 'e' shape", "embroidery or print quality", "neck tag"] },
  { slug: "cp-company-jacket", name: "C.P. Company jackets", rx: "c\\.?p\\.? company.*(jacket|goggle|overshirt|coat|shell)", intro: "C.P. Company goggle jackets and overshirts with the lens detail.", qc: ["goggle lens placement and clarity", "fabric texture", "badge and inner tags"] },
  { slug: "rick-owens-sneakers", name: "Rick Owens sneakers", rx: "rick owens.*(ramones|geobasket|sneaker|boot|shoe|dunk)", intro: "Rick Owens Ramones, Geobaskets and boots.", qc: ["sole shape and thickness", "leather or canvas quality", "the pentagram and tongue details"] },
  { slug: "celine-bag", name: "Celine bags", rx: "celine.*(bag|triomphe|wallet)", intro: "Celine Triomphe bags and wallets.", qc: ["Triomphe hardware shape and finish", "canvas or leather quality", "stitching and edge paint"] },
];

export const GUIDES3 = {
  "what-is-a-rep-spreadsheet": {
    title: "What Is a Rep Spreadsheet? How to Use One (2026)",
    desc: "A rep spreadsheet is a list of product links from Weidian, Taobao and 1688 that you open in a shopping agent. Here's how to use one.",
    h1: "What is a rep spreadsheet?",
    body: `<p class="lead">A <strong>rep spreadsheet</strong> is a curated list of product links from Chinese marketplaces (Weidian, Taobao and 1688), usually with photos, prices and links that open each item in a shopping agent. Most started as Google Sheets; <a href="/">Puro Classico</a> is a searchable version with 9,000+ finds.</p>
<h2>How to use a rep spreadsheet</h2><ol class="steps">
<li><strong>Browse or search.</strong> Filter by brand, category or price, or sort by most viewed.</li>
<li><strong>Check the QC photos.</strong> Finds marked "QC" have real warehouse photos from earlier buyers (<a href="/guides/how-to-qc">how to read them</a>).</li>
<li><strong>Open it in your agent.</strong> Tap Buy to open the listing in MyCNBox, KakoBuy, Oopbuy, LoveGoBuy or Sugargoo, or convert any link with the <a href="/tools/link-converter">link converter</a>.</li>
<li><strong>Order, inspect and ship.</strong> The agent buys the item, photographs it at the warehouse and ships your parcel. Watch the <a href="/how-to-order">2-minute video</a>.</li></ol>
<h2>What makes a good spreadsheet</h2><ul><li><strong>Working links</strong> — dead links are the most common problem with old Google Sheets.</li><li><strong>QC photos</strong> so you can judge quality before buying.</li><li><strong>Search and filters</strong> instead of scrolling thousands of rows.</li><li><strong>Agent-neutral links</strong> so you can use the agent you prefer.</li></ul>
<h2>Spreadsheets by agent</h2><p><a href="/mycnbox-spreadsheet">MyCNBox</a> · <a href="/kakobuy-spreadsheet">KakoBuy</a> · <a href="/oopbuy-spreadsheet">Oopbuy</a> · <a href="/lovegobuy-spreadsheet">LoveGoBuy</a> · <a href="/sugargoo-spreadsheet">Sugargoo</a></p>`,
    faq: [["Is a rep spreadsheet free?", "Yes. Puro Classico is free to browse; you only pay the seller, the agent's fees and shipping when you order."], ["Which agent should I use with a spreadsheet?", "Any agent that accepts Weidian, Taobao and 1688 links works. See our best shopping agent guide for a comparison."], ["How often is the spreadsheet updated?", "New finds are added regularly and the most-viewed items rise to the top automatically."]],
  },
  "pandabuy-alternatives": {
    title: "Best Pandabuy Alternatives in 2026 (Agents That Still Work)",
    desc: "Pandabuy stopped operating in 2024. These shopping agents work the same way — paste a Weidian, Taobao or 1688 link, get QC photos and ship.",
    h1: "Pandabuy alternatives",
    body: `<p class="lead">Pandabuy was one of the most-used shopping agents until it stopped operating in 2024. Old Pandabuy spreadsheet links no longer work, but every item on them was a normal Weidian, Taobao or 1688 listing — so you can buy the same things through another agent.</p>
<h2>Agents that work the same way</h2><ul>
<li><strong>MyCNBox</strong> — new-user coupons, QC photos included, simple checkout. <a href="/guides/mycnbox-review">Review</a> · <a href="/mycnbox-spreadsheet">spreadsheet</a>.</li>
<li><strong>KakoBuy</strong> — popular with the rep community. <a href="/guides/kakobuy-vs-mycnbox">KakoBuy vs MyCNBox</a> · <a href="/kakobuy-spreadsheet">spreadsheet</a>.</li>
<li><strong>Oopbuy</strong>, <strong>LoveGoBuy</strong> and <strong>Sugargoo</strong> — all accept the same marketplace links. <a href="/guides/best-shopping-agent">Compare agents</a>.</li></ul>
<h2>How to move an old Pandabuy link to a new agent</h2><ol class="steps"><li>Copy the old Pandabuy link (it contains the original item link or ID).</li><li>Paste it into the <a href="/tools/link-converter">link converter</a>; it extracts the Weidian, Taobao or 1688 item ID.</li><li>Open the item in the agent of your choice.</li></ol>
<p>Or skip the old sheets: <a href="/">browse 9,000+ working finds</a>, sorted by what people view most.</p>`,
    faq: [["Is Pandabuy still working?", "No. Pandabuy stopped operating in 2024, so its links and spreadsheets no longer work."], ["Can I still buy items from old Pandabuy spreadsheets?", "Usually yes. The items were ordinary Weidian, Taobao or 1688 listings; convert the link and open it in another agent. Some listings will have been removed by the seller."], ["What is the closest Pandabuy alternative?", "MyCNBox and KakoBuy work the same way: paste a link, pay, get QC photos, then ship."]],
  },
  "rep-glossary": {
    title: "Rep Terms Explained: QC, GL/RL, W2C, Batch, Haul & More",
    desc: "A glossary of rep and shopping-agent slang: QC, GL/RL, W2C, batch, haul, LC, retail, 1:1, rehearsal packaging and more.",
    h1: "Rep terms glossary",
    body: `<p class="lead">New to reps? These are the terms you'll see on spreadsheets, Reddit and Discord.</p>
<style>.gloss dt{font-weight:700;margin-top:14px}.gloss dd{margin:4px 0 0;color:var(--muted)}</style><dl class="gloss">
<dt>QC (quality check)</dt><dd>Photos your agent takes of the item at its warehouse before you ship. <a href="/guides/how-to-qc">How to read QC photos</a>.</dd>
<dt>GL / RL</dt><dd>Green light (happy, ship it) / red light (a flaw — exchange or return it while it's still at the warehouse).</dd>
<dt>W2C</dt><dd>"Where to cop" — someone asking for the link to an item.</dd>
<dt>Batch</dt><dd>A production run from a particular factory. Different batches of the same model can vary a lot in quality.</dd>
<dt>Haul</dt><dd>A parcel of several items shipped together, or a post showing everything someone bought.</dd>
<dt>Agent</dt><dd>A service that buys from Chinese marketplaces for you, inspects items and ships internationally. <a href="/guides/best-shopping-agent">Best agents</a>.</dd>
<dt>Weidian / Taobao / 1688</dt><dd>The Chinese marketplaces where most finds are listed. Guides: <a href="/guides/how-to-buy-from-weidian">Weidian</a>, <a href="/guides/how-to-buy-from-taobao">Taobao</a>, <a href="/guides/how-to-buy-from-1688">1688</a>.</dd>
<dt>Shipping line</dt><dd>The courier route your agent uses; each has its own price, speed and weight limits. <a href="/guides/shipping-lines">Shipping lines explained</a>.</dd>
<dt>Volumetric weight</dt><dd>Shipping is charged on size as well as weight, which is why people remove shoe boxes. Try the <a href="/tools/weight-estimator">weight estimator</a>.</dd>
<dt>Rehearsal (rehearsal packaging)</dt><dd>Your agent packs the parcel and shows you its final weight and size before you pay for shipping.</dd>
<dt>Retail</dt><dd>The authentic product from the brand, used as the reference when comparing QC photos.</dd>
<dt>1:1 / budget</dt><dd>Seller shorthand for how close a copy aims to be; budget versions are cheaper and less accurate. Always judge from QC photos, not the label.</dd>
<dt>LC</dt><dd>"Legit check" — asking others to compare an item with retail.</dd>
<dt>Spreadsheet</dt><dd>A curated list of finds with links. <a href="/guides/what-is-a-rep-spreadsheet">What is a rep spreadsheet?</a></dd>
</dl>`,
    faq: [["What does GL and RL mean?", "GL means green light (the item looks right, ship it) and RL means red light (there's a flaw, so exchange or return it before shipping)."], ["What does W2C mean?", "W2C means 'where to cop' — a request for the link to an item."], ["What is a batch?", "A production run from one factory. The same model can come in several batches of different quality."]],
  },
  "how-to-find-reps": {
    title: "How to Find Reps: Spreadsheets, Image Search & Seller Stores",
    desc: "Four reliable ways to find a specific rep: spreadsheets, reverse image search, searching inside your agent and following good seller stores.",
    h1: "How to find reps",
    body: `<p class="lead">Looking for a specific item? These are the four methods experienced buyers use, from quickest to most thorough.</p>
<h2>1. Search a spreadsheet</h2><p>Search <a href="/">Puro Classico</a> by brand or item name. Results show photos, prices and whether real QC photos exist. Start with <a href="/best">best reps by model</a> for the most-wanted items.</p>
<h2>2. Reverse image search</h2><p>Many agents have an image-search box: upload a photo of the item and it finds matching Taobao and 1688 listings. Pick listings with many sales and good ratings.</p>
<h2>3. Search inside your agent</h2><p>Agents translate searches into Chinese. Search the brand and item name, then sort by sales. Check the <a href="/tools/qc-checker">QC checker</a> for photos of any listing you find.</p>
<h2>4. Follow good seller stores</h2><p>When you find a seller whose QC photos look right, look at their other listings — good sellers are usually good across their range.</p>
<h2>Before you buy</h2><ul><li>Look for real QC photos rather than seller photos (<a href="/guides/how-to-qc">how</a>).</li><li>Check sizing in centimetres (<a href="/guides/sizing">sizing guide</a>).</li><li>Estimate shipping first with the <a href="/tools/shipping-calculator">shipping calculator</a>.</li></ul>`,
    faq: [["What is the fastest way to find a rep?", "Search a spreadsheet like Puro Classico first; if it's not there, use your agent's image search."], ["How do I know if a seller is good?", "Look at real QC photos from other buyers, the listing's sales count and the seller's ratings inside your agent."]],
  },
};

// Short search term per model for titles/H1 ("Best Rolex Reps"); defaults to the model name.
export const MODEL_TERM = {
  "maison-margiela-gat": "Margiela GAT", "moncler-puffer": "Moncler Puffer", "stone-island-overshirt": "Stone Island Overshirt",
  "corteiz-cargos": "Corteiz Cargo", "corteiz-alcatraz": "Corteiz Alcatraz", "essentials-hoodie": "Essentials Hoodie",
  "ralph-lauren-cable-knit": "Ralph Lauren Cable Knit", "ralph-lauren-polo": "Ralph Lauren Polo", "loro-piana-summer-walk": "Loro Piana Summer Walk",
  "arcteryx-jacket": "Arc'teryx Jacket", "canada-goose-parka": "Canada Goose", "chrome-hearts-hoodie": "Chrome Hearts Hoodie", "sp5der-hoodie": "Sp5der Hoodie",
  "denim-tears-hoodie": "Denim Tears Hoodie", "bape-shark-hoodie": "Bape Shark Hoodie", "burberry-scarf": "Burberry Scarf", "dior-b23": "Dior B23",
  "corteiz-tracksuits": "Corteiz Tracksuit", "trapstar-jacket": "Trapstar Jacket", "trapstar-tracksuit": "Trapstar Tracksuit", "stone-island-hoodie": "Stone Island Hoodie",
  "hellstar-hoodie": "Hellstar Hoodie", "broken-planet-hoodie": "Broken Planet", "syna-world-tracksuit": "Syna World Tracksuit", "stussy-hoodie": "Stüssy Hoodie",
  "gallery-dept-jeans": "Gallery Dept Jeans", "amiri-jeans": "Amiri Jeans", "purple-brand-jeans": "Purple Brand Jeans", "chrome-hearts-jewelry": "Chrome Hearts Jewelry",
  "cartier-bracelet": "Cartier Love Bracelet", "rolex-watches": "Rolex", "goyard-wallet-bag": "Goyard", "louis-vuitton-bags": "Louis Vuitton Bag",
  "lv-gucci-hermes-belts": "Designer Belt", "designer-sunglasses": "Designer Sunglasses", "football-shirts": "Football Shirt", "asics-sneakers": "Asics",
  "gucci-ace": "Gucci Ace", "yeezy-slide": "Yeezy Slide", "ugg-boots": "UGG", "hermes-oran-sandals": "Hermès Oran", "lacoste-polo": "Lacoste Polo",
  "ralph-lauren-quarter-zip": "Ralph Lauren Quarter Zip", "moncler-gilet": "Moncler Gilet", "essentials-tee": "Essentials Tee", "essentials-sweatpants": "Essentials Sweatpants",
  "represent-hoodie": "Represent Hoodie", "palm-angels-tracksuit": "Palm Angels Tracksuit", "off-white-hoodie": "Off-White Hoodie", "supreme-box-logo": "Supreme Box Logo",
  "cp-company-jacket": "C.P. Company Jacket", "rick-owens-sneakers": "Rick Owens", "celine-bag": "Celine Bag",
};
