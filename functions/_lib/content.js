// Editorial copy for the hub pages and guides. Plain HTML strings; keep claims factual and general.
import { esc, money, isPH, views, productUrl, origUrl, icTile } from "./site.js";
import { itemTypeOf, typeGrams, boxedGrams } from "./weights.js";

export const CAT_INTRO = {
  Tops: `<p>Tops are the biggest part of the spreadsheet: hoodies, T-shirts, polos, sweaters and knitwear from Weidian, Taobao and 1688 sellers. They're also the easiest place to start, because they're light (cheap to ship) and sizing is simple to check against a measurement chart.</p><p>When the QC photos come in, check print and embroidery placement against the listing, the neck label and wash tag, and the stitching along the hem and cuffs. For knitwear, look at the texture up close, cheaper yarn shows as fuzz or uneven ribbing.</p>`,
  Outerwear: `<p>Jackets, puffers, fleeces and coats. Outerwear is where batches differ the most in materials, so it pays to compare QC photos before you buy: two listings that look identical in the seller photos can use very different fabric, fill and hardware.</p><p>In QC, check zips and snaps (branded pulls, smooth teeth), the fill and loft on puffers, badge and patch placement, and the inner labels. Outerwear is heavy and bulky, so it adds the most to your shipping. Choose a line that charges by actual weight if you can, or ask the warehouse to vacuum-pack or remove the box.</p>`,
  Shoes: `<p>Sneakers and shoes: runners, basketball shoes, designer trainers, boots and sandals. Shoes are the category where the batch (the factory run a seller sources from) matters most, so start with the finds that have the most buyer QC photos.</p><p>Check the shape (toe box and heel from the side), stitching around the toe and heel, logo size and placement, the size tag inside the tongue, and glue marks around the sole. Shoes are heavy with the box, ask your agent to ship without the box to save a lot on international shipping if you don't need it.</p>`,
  Pants: `<p>Jeans, cargo pants, tracksuit bottoms and trousers. Measure a pair you already own flat (waist, inseam, thigh) and compare it with the seller's size chart, because Asian sizing usually runs smaller than EU/US sizing.</p><p>In QC, look at the wash on denim, stitching on pockets and belt loops, hardware (buttons, rivets, zips) and the waistband label.</p>`,
  Shorts: `<p>Shorts, swim shorts and sweat shorts. Light, cheap to ship and a good first order. Check the waist (elastic vs. fixed), the length against the size chart, embroidery or print placement and the drawstring tips in the QC photos.</p>`,
  Bags: `<p>Backpacks, crossbody bags, totes and small leather goods. For bags, ask for extra QC photos if the default set doesn't show them: the hardware engraving, the stitching along edges and handles, the interior lining and the dust bag. Bags ship best without extra boxes, ask your agent to remove them to cut the parcel volume.</p>`,
  Accessories: `<p>Belts, jewellery, wallets, sunglasses, scarves and other small accessories. They're light and small, which makes them easy to add to a parcel you're already sending. In QC, look closely at engraving depth, clasp and buckle finish, and colour against the listing.</p>`,
  Headwear: `<p>Caps, beanies and bucket hats. Check the embroidery density and placement on the front logo, the inner tape and labels, and the adjuster or strap. Hats crush easily in a parcel, so ask the warehouse to pack them carefully or keep them in a box.</p>`,
  Toys: `<p>Toy and building-set finds. These are bulky compared with their weight, so check the box size before you ship and consider removing outer packaging if you don't need it.</p>`,
};

// Agent spreadsheet pages (/kakobuy-spreadsheet etc.). Rewritten 9 Nov 2026 so the five pages stop being near-copies of
// each other (an SEO audit measured 89% shared text). Each agent has its own:
//   lede, body   intro (renderAgent; for the app view, pages.js hubSpec uses body as "What is <agent>?", except MyCNBox)
//   desc(N, Q)   meta description; N = number of finds, Q = number marked as having buyer QC photos (both formatted)
//   about        [title, html] sections for the block under the app (hubSpec "about"), each about THAT agent
//   faq          its own questions (also the FAQPage JSON-LD)
// Sources, all read on 9 Nov 2026 unless noted. Re-read them before changing a number:
//   MyCNBox: help centre read 10 Oct 2026 for /guides/mycnbox-review (fees, 4 QC photos, 90 days, payment, returns);
//            mycnbox.com/FAQDetail?id=165 (EU shipping update, 22 Oct 2026) and id=74 (customs clearance and duties).
//   KakoBuy: kakobuy.com/service/help/question?id=63 (fees), id=1 (storage), id=89 (inspection), id=64 (payment);
//            kakobuy.com/tipdetail?id=51 (EU €3 per parcel) and id=57 (EU €2 handling fee covered); App Store listing.
//   Oopbuy:  oopbuy.com/notice/1740653781924810754 (fees), 1740664252140720130 (storage), 1740664942636404738
//            (inspection), 1740653409764216834 (tutorial), 1740656181012172801 (returns), 2062462174797901826 (delivery
//            time), 1740663384020455425 (customs), 1740661986205732866 (packaging); help centre menu (payment); App Store.
//   LoveGoBuy: lovegobuy.com/article/index?article_id=10075 (storage), 10019 (fees), 10086 (inspection), 10053
//            (payment), 10209 (EU €2 fee covered from 10 Nov 2026); home page (coupons, search, apps); App Store listing.
//   Sugargoo: home page (5 free photos, 100-day storage, 2,000+ routes); help pages "Service & Fee Instruction" and
//            "Commodity Storage Timeline"; notices "¥800 New User Coupon Pack" and "Union Handling Fee" (EU, 1 Nov 2026);
//            blog.sugargoo.com/?p=14031 (ordering and QC); App Store listing.
//   New-user offers: checked by the owner on 9 Nov 2026. Link formats: AGENTS in site.js (what our buttons open).
// Rules: facts only (no fee or number without a source), no ranking of agents against each other, no em or en dashes.
const STEPS = items => `<ol class="steps ic-steps-list">${items.map(([i, h, t]) => `<li>${icTile(i)}<strong>${h}</strong> ${t}</li>`).join("")}</ol>`;
const GLANCE = items => `<ul>${items.map(([h, t]) => `<li><strong>${h}:</strong> ${t}</li>`).join("")}</ul>`;
const SRC = t => `<p style="font-size:13px;color:var(--muted)">${t}</p>`;
const WRAP = t => `<span style="overflow-wrap:anywhere">${t}</span>`;

export const AGENT_INTRO = {
  mycnbox: { title: "MyCNBox Spreadsheet 2026", lede: "Tap Buy on any find below and the listing opens pre-filled in MyCNBox, ready for your size and colour.",
    body: `<p>MyCNBox is a shopping agent: you pay MyCNBox for the item and the short delivery to its warehouse in China, it buys from the Weidian, Taobao or 1688 seller, takes QC photos when the item arrives, and ships your items together in one parcel when you're ready. It's our most-used agent and the one we recommend for first orders.</p><p>Each find below opens the exact listing inside MyCNBox, no copying links or translating. New users can claim the MyCNBox new-user coupon bundle (advertised as up to $500) when they sign up through Puro Classico.</p><p>New to agents? Watch the <a href="/how-to-order">1:47 how-to-order video</a> first.</p>`,
    desc: (N, Q) => `The MyCNBox spreadsheet: ${N} rep finds that open pre-filled in MyCNBox, ${Q} marked as having QC photos. 4 QC photos per item, 90-day storage, $500 coupons.`,
    about: [
      ["How to order on MyCNBox", STEPS([
        ["user-plus", "Sign up with invite code AACPYA.", `Our <a href="/guides/mycnbox-coupon-code">sign-up link</a> fills it in, and the new-user coupons (up to $500 in total) appear in your account. They are coupons, not cash: MyCNBox's help centre shows one coupon applied per parcel.`],
        ["cart", "Tap Buy via MyCNBox on a find.", `The button opens ${WRAP("mycnbox.com/goodsDetail")} with the marketplace and item ID already filled in, so all that is left is size, colour and quantity.`],
        ["camera", "Choose extra photos at checkout, not later.", "The standard check is 4 QC photos, done within one business day of the item reaching the warehouse. Detailed or multi-angle photos are a paid add-on that has to be picked when you place the order."],
        ["warehouse", "Check the Warehouse tab.", "Your items wait there for free for 90 days while you collect the rest of your haul."],
        ["truck", "Submit a parcel under Parcels.", "Select your items, pick a line, apply one coupon and pay the estimated shipping. After packing, any overpayment goes back to your balance and a shortfall is paid before the parcel leaves."]])],
      ["MyCNBox fees, storage and payment", GLANCE([
        ["Service fee", "none on purchases, according to its help centre; paid add-ons include reinforced packaging, video QC and multi-angle photos"],
        ["QC photos", "4 standard photos within one business day of arrival"],
        ["Free storage", "90 days at the warehouse"],
        ["Payment", "Visa, Mastercard, Apple Pay, Google Pay, Klarna and iDEAL, plus some local wallets"],
        ["Apps", "iOS and Android"]]) + SRC(`From MyCNBox's help centre, read 10 October 2026. More detail, including what unhappy customers report: <a href="/guides/mycnbox-review">Is MyCNBox legit?</a> Our MyCNBox links are affiliate links.`)],
      ["Shipping to the EU from MyCNBox", `<p>Since 22 October 2026, MyCNBox's EU lines that include tax cost €2 more per parcel. In return, once you have paid for shipping, MyCNBox covers any further customs duties assessed on that parcel, and it prepares the new product identification (PID) data with its logistics partners, so there is nothing extra to declare.</p><p>EU options that do not include import tax, among them the relevant EMS and UPS services, were suspended at the same time until EU customs explain how recipients should pay. On any line marked [tax excluded], duties can still be charged on arrival, and an express carrier such as UPS may send that bill after delivery; MyCNBox's help centre says those charges stay yours.</p>${SRC("From MyCNBox's help centre (EU shipping update and customs clearance pages), read 9 November 2026.")}`],
      ["Returns and refunds on MyCNBox", `<p>A return to the seller has to be requested within 5 days of the item reaching the warehouse. It costs the domestic shipping, ¥12 return shipping and a ¥10 warehouse fee, and some sellers refuse returns, so look at your QC photos on the day they arrive.</p><p>Refunds are credited to your MyCNBox balance, not to your card. You can spend the balance on your next order, or take it out for a $1 withdrawal fee.</p>`],
      ["Opening any Weidian, Taobao or 1688 link on MyCNBox", `<p>MyCNBox only needs two things from a listing: the marketplace and the item ID. A Weidian find with item ID 7539696765 opens as ${WRAP("mycnbox.com/goodsDetail?mallType=weidian&amp;itemId=7539696765")}, and a Taobao or 1688 find works the same way with its own marketplace name.</p><p>Found an item somewhere else, in a Discord post or another spreadsheet? Paste it into the <a href="/tools/link-converter">link converter</a> and it gives you the MyCNBox link.</p>`],
      ["Tips for MyCNBox orders", `<ul>
<li><strong>Shoes, bags and jackets:</strong> decide on the detailed photos when you order. With only 4 standard shots you may not see the size tag, the sole or the hardware up close.</li>
<li><strong>One coupon per parcel:</strong> collect a few items and send one bigger parcel, so the larger coupons in the bundle get used.</li>
<li><strong>EU address?</strong> Pick a line that includes tax; the €2 per parcel covers the duties on it.</li></ul>`]],
    faq: [["Does MyCNBox charge a service fee?", "MyCNBox's help centre says it charges no service fee on purchases. You pay the item price and the seller's delivery to the warehouse, then international shipping when you send your parcel. Add-ons such as detailed QC photos and reinforced packaging cost extra (read on 10 October 2026)."],
          ["How many QC photos does MyCNBox take?", "4 standard photos per item, within one business day of it reaching the warehouse. More detailed photos are an add-on you choose when placing the order."],
          ["How long does MyCNBox store my items for free?", "90 days. After that you pay to extend the storage, or the items are discarded, so submit your parcel in time."],
          ["Do I pay customs on a MyCNBox parcel to the EU?", "On MyCNBox's EU lines that include tax, no: since 22 October 2026 those lines cost €2 more per parcel, and MyCNBox covers further customs duties assessed on the parcel once shipping is paid."],
          ["How do the MyCNBox new-user coupons work?", "Sign up with invite code AACPYA and a coupon bundle advertised as up to $500 appears in your account. It is a set of coupons with minimum spends, mostly for shipping, and one coupon is used per parcel."],
          ["Can I open these finds on another agent?", "Yes. Every product page on Puro Classico also has KakoBuy, Oopbuy, LoveGoBuy and Sugargoo buttons, and browsing the spreadsheet is free."]] },

  kakobuy: { title: "KakoBuy Spreadsheet 2026", lede: "Every find here opens on KakoBuy's own item page with the original Weidian, Taobao or 1688 listing already loaded.",
    body: `<p>KakoBuy is one of the most widely used shopping agents for Weidian, Taobao and 1688 finds. Its help centre describes the purchasing service as free of handling fees: you pay the item price and the seller's delivery to the KakoBuy warehouse, then international shipping and a customs declaration charge (generally ¥8 per parcel, depending on the line) when you send your parcel. Optional extras are paid for separately.</p><p>The only thing this page changes is the button: each find opens straight on KakoBuy, so there is nothing to copy, paste or translate. New KakoBuy members can claim up to $410 in new-user coupons with invite code w5war.</p>`,
    desc: (N, Q) => `The KakoBuy spreadsheet: ${N} rep finds that open on KakoBuy in one tap, ${Q} marked as having QC photos. KakoBuy's fees, 100-day storage and EU customs.`,
    about: [
      ["How to order on KakoBuy", STEPS([
        ["user-plus", "Register with invite code w5war.", `The <a href="/guides/kakobuy-coupon-code">KakoBuy invite link</a> applies it for you. The new-user coupons (up to $410 in total) come as several smaller coupons with minimum spends, mostly for shipping.`],
        ["link", "Tap Buy via KakoBuy.", "The original listing loads on KakoBuy's item page. Pick your size and colour and pay for the item and its delivery to the warehouse."],
        ["camera", "Check the arrival photos.", "KakoBuy inspects the item's appearance: model, style and size. Clothing, bags, suitcases and shoes are opened; sealed items and other products are checked from the outside only."],
        ["box", "Submit your waybill within 100 days.", "Storage runs for 100 days from the status \"in storage\". KakoBuy emails a reminder after 90 days, and items still waiting after 100 days are treated as abandoned."],
        ["truck", "Pay the shipping.", "International shipping is worked out from weight, line and destination; KakoBuy's Estimate tool gives a figure before you submit."]])],
      ["KakoBuy fees, storage and inspection", GLANCE([
        ["Purchasing service", "no handling fee on top of the item and shipping, according to its help centre"],
        ["Customs declaration", "generally ¥8 per parcel, depending on the shipping method"],
        ["Free storage", "100 days; 60 days for abnormal packages (ones that arrive without a matching order or complete details)"],
        ["Inspection", "appearance, model, style and size"],
        ["App", "KakoBuy on iOS, in English and Simplified Chinese"]]) + SRC("From KakoBuy's help centre and App Store listing, read 9 November 2026. Our KakoBuy links are affiliate links.")],
      ["Paying on KakoBuy", `<p>KakoBuy's help centre lists PayPal, international credit cards, Alipay and WeChat Pay for topping up your balance. A PayPal top-up is converted to US dollars, at a rate KakoBuy says follows the Bank of China, and carries a handling charge of 3.5% + $0.30. Alipay and WeChat Pay have no handling charge, but the money can take from 1 to 60 minutes to show up in your KakoBuy account.</p><p>On a large haul that PayPal charge is worth a quick sum before you top up.</p>`],
      ["KakoBuy and EU customs", `<p>Since 1 July 2026 the EU can charge a fixed duty per product category on parcels under €150, so a parcel with T-shirts, shoes and a bag could count three times. KakoBuy's announcement says it charges €3 per parcel however many categories are inside, added to the shipping cost, and covers the rest itself.</p><p>For the extra €2 EU customs handling fee that started on 1 November 2026, KakoBuy announced it covers the fee for eligible shipments. It also lists tax-free routes for buyers in the United States. Both offers can change, so read the current announcement on KakoBuy before you choose a line.</p>${SRC("From KakoBuy's announcements of 22 June and 20 October 2026, read 9 November 2026.")}`],
      ["How a Weidian or Taobao link opens on KakoBuy", `<p>KakoBuy's item page reads the whole marketplace address, so our button passes the full listing link: ${WRAP("kakobuy.com/item/details?url=")} followed by, for example, ${WRAP("https://weidian.com/item.html?itemID=7539696765")}. It is the same idea as ordering on KakoBuy by pasting a product link.</p><p>KakoBuy also offers Forwarding, for parcels a seller sends to its warehouse on your behalf.</p>`],
      ["Tips for KakoBuy orders", `<ul>
<li><strong>Measure before you buy:</strong> KakoBuy's check confirms model, style and size, not how a piece fits you. Compare a garment you own with the seller's chart, or use the <a href="/tools/size-estimator">size estimator</a>.</li>
<li><strong>Forwarded parcels:</strong> a package that arrives without complete order details only gets 60 days of storage, so fill in the details as soon as you send it.</li>
<li><strong>Several item types in one EU parcel</strong> do not cost extra under KakoBuy's €3 per parcel rule, which makes one combined parcel easier to plan.</li></ul>`]],
    faq: [["Does KakoBuy charge a service fee?", "KakoBuy's help centre says it charges no handling fee on purchases. The total is the item price with domestic delivery, international shipping and a customs declaration charge of generally ¥8 per parcel. Optional value-added services cost extra."],
          ["How long can items stay in the KakoBuy warehouse?", "100 days from the status \"in storage\", with a reminder email after 90 days. Abnormal packages, ones that cannot be matched to an order, are kept for 60 days."],
          ["What does KakoBuy check in QC?", "The item's appearance: model, style and size. Clothing, bags, suitcases and shoes are opened for the check; sealed items and other products are only checked from the outside."],
          ["How can I pay on KakoBuy?", "PayPal (3.5% + $0.30 handling charge), international credit cards, Alipay and WeChat Pay, according to its help centre (read 9 November 2026)."],
          ["How does KakoBuy handle EU customs?", "KakoBuy's announcements say it charges €3 per EU parcel for the category-based duty, whatever the number of categories, and covers the €2 EU handling fee that started on 1 November 2026 for eligible shipments."],
          ["What is the KakoBuy invite code?", "w5war. Signing up with it unlocks up to $410 in new-user coupons, split into smaller coupons with minimum spends."]] },

  oopbuy: { title: "Oopbuy Spreadsheet 2026", lede: "Oopbuy links for every find: the item opens on Oopbuy with the marketplace and item ID already set.",
    body: `<p>Oopbuy buys from Weidian, Taobao and 1688 for you, keeps your items in its warehouse and ships them together in one parcel. Its help centre says nothing is charged apart from the item (with the seller's delivery to the warehouse), international shipping and a customs declaration fee of generally ¥8 per parcel. Value-added services are optional.</p><p>New Oopbuy users get a ¥3,500 coupon bundle plus a 30% off coupon (a minimum spend applies). Every find on this page opens directly on Oopbuy, so you can claim the coupons and place your first order in the same visit.</p>`,
    desc: (N, Q) => `The Oopbuy spreadsheet: ${N} rep finds with direct Oopbuy links, ${Q} marked as having QC photos. Oopbuy's fees, 90-day storage, packing tips and returns.`,
    about: [
      ["How to order on Oopbuy", STEPS([
        ["gift", "Register and collect your coupons.", "Oopbuy's own tutorial puts \"get your coupon\" straight after registering: a ¥3,500 bundle plus a 30% off coupon with a minimum spend."],
        ["cart", "Tap Buy via Oopbuy.", "Select style, size and quantity, add your details and pay; the order then shows under \"View order\"."],
        ["camera", "Read the inspection photos.", "On arrival Oopbuy checks quantity, colour, size and other specifications, then takes the item out of the courier box and repacks it in an Oopbuy self-sealing bag. Some items, such as oversized ones, stay in their original box."],
        ["box", "Create a waybill in My Warehouse.", "Wait until every item you want in the parcel is in stock, select them all, choose packing and insurance, and pay the estimated shipping."],
        ["truck", "Settle the real cost in My Shipments.", "Once the parcel is packed you pay the actual shipping; if you paid too much, the difference goes back to your account. Tracking is under My Waybill."]])],
      ["Oopbuy fees, storage and payment", GLANCE([
        ["Fees", "item price, international shipping and a customs declaration fee (generally ¥8 per parcel); value-added services optional"],
        ["Free storage", "90 days from the status \"received\", with an email before it runs out; extensions cost 10 CNY per 30 days"],
        ["Abnormal packages", "kept for 30 days"],
        ["Payment", "account top-up, international credit cards, PayPal and Klarna"],
        ["App", "Oopbuy on iOS, which shows a product's weight before you order"]]) + SRC("From Oopbuy's help centre and App Store listing, read 9 November 2026. Our Oopbuy links are affiliate links.")],
      ["Packing an Oopbuy parcel", `<p>Oopbuy's packaging page has advice per type of haul. Clothes only: choose Simple Packaging and add vacuum bags, on the lines that offer it. Shoes with clothes: Carton Packaging, with the shoe boxes removed or folded and the clothes vacuum-packed around them. Puffer jackets and other bulky pieces: vacuum bags, which cut the volume you pay for. Bubble wrap and stretch film are the cheap way to add protection.</p><p>Oopbuy also warns that a parcel over 10 kg, or one with many of the same item, is more likely to be treated as a commercial shipment by customs, so split a very large haul.</p>`],
      ["Delivery time and customs on Oopbuy", `<p>After you submit a parcel, Oopbuy gives about 15 to 30 days to your address, depending on the destination, and sends a tracking number.</p><p>For the UK and the EU, Oopbuy's customs page notes that the low-value tax exemption is gone and every import is subject to VAT. For parcels worth up to €150 (£135 in the UK), Oopbuy's system usually collects the VAT when you order or submit the parcel, which tends to speed up clearance. Customs risks on a parcel (returns, fines or taxes) are the buyer's.</p>${SRC("From Oopbuy's Delivery Time and Customs and Taxation pages, read 9 November 2026.")}`],
      ["Returns on Oopbuy", `<p>You can ask for a return or exchange within 5 days (120 hours) of the order showing \"Stocked in\". Oopbuy takes the request to the seller, who has the final say. Custom-made pieces, items with the tags removed, underwear and second-hand goods are among the types listed as not eligible. If the listing had free shipping you pay the return postage; if not, you pay both the delivery to the warehouse and the return.</p>`],
      ["How a link opens on Oopbuy", `<p>Oopbuy's product pages are built from the marketplace and the item ID: a Weidian find with item ID 7539696765 opens as ${WRAP("oopbuy.com/product/weidian/7539696765")}, and Taobao and 1688 finds use taobao or 1688 in the same place. Oopbuy's search bar also takes a pasted product link, and its app has added support for more link formats over time.</p>`],
      ["Tips for Oopbuy orders", `<ul>
<li><strong>Check photos the same week:</strong> the 5-day return window starts when the item is stocked in, so a late look at the photos can cost you the return.</li>
<li><strong>Not covered by the check:</strong> Oopbuy lists colour difference and size error as outside its inspection. Compare the photos with the listing and measure against the size chart yourself (<a href="/guides/how-to-qc">how to read QC photos</a>).</li>
<li><strong>Collecting a big haul?</strong> Past the free 90 days, storage is 10 CNY per 30 days, which can be cheaper than sending two parcels.</li></ul>`]],
    faq: [["Does Oopbuy charge a service fee?", "Its help centre says no other fees are charged apart from the product, international shipping and customs declaration (generally ¥8 per parcel). Value-added services are optional and paid separately."],
          ["How long does Oopbuy store items?", "90 days free from the status \"received\". After that you can extend storage at 10 CNY per 30 days. Abnormal packages are kept for 30 days."],
          ["Can I return an item on Oopbuy?", "You can request a return or exchange within 5 days (120 hours) after the order shows \"Stocked in\". The final decision is the seller's, and you pay the return shipping."],
          ["How long does Oopbuy shipping take?", "About 15 to 30 days from submitting the parcel to delivery, depending on the destination, according to Oopbuy's help centre."],
          ["Which payment methods does Oopbuy accept?", "Oopbuy's help centre lists account top-up, international credit cards, PayPal and Klarna (read 9 November 2026)."],
          ["What do new Oopbuy users get?", "A ¥3,500 new-user coupon bundle plus a 30% off coupon. A minimum spend applies, and the coupons are claimed after registering."]] },

  lovegobuy: { title: "LoveGoBuy Spreadsheet 2026", lede: "LoveGoBuy links for every find, with what LoveGoBuy's own help centre says about storage, QC and costs.",
    body: `<p>LoveGoBuy is a shopping agent for Weidian, Taobao, Tmall and 1688. On its own site you search by keyword, paste a product link or upload a photo to find a matching item. From Puro Classico you skip that step: each find opens on LoveGoBuy's product page with the platform and item ID filled in.</p><p>Its help centre breaks the cost down as the item price with domestic delivery, international shipping and a customs declaration charge of generally ¥8 per parcel. New users can claim up to $141 in new-user shipping coupons: a set of freight coupons with different minimum spends, plus a 30% off shipping coupon.</p>`,
    desc: (N, Q) => `The LoveGoBuy spreadsheet: ${N} rep finds with direct LoveGoBuy links, ${Q} marked as having QC photos. Its 60-day storage, QC scope and $141 in coupons.`,
    about: [
      ["How to order on LoveGoBuy", STEPS([
        ["gift", "Sign up and claim the shipping coupons.", "The new-user set is worth up to $141 in total. Each freight coupon has its own minimum shipping fee, and a few have none."],
        ["cart", "Tap Buy via LoveGoBuy.", "Choose your size and colour and pay for the item and its delivery to the warehouse."],
        ["camera", "Look at the arrival check.", "LoveGoBuy's inspectors check the outside of the item: colour, large damage, stains, size, model and version number. Size is judged from the label and tag."],
        ["clock", "Ship within 60 days.", "Storage runs for 60 days from the status \"stored\". Items without a parcel order after that are treated as given up."],
        ["truck", "Estimate, then send.", "LoveGoBuy has its own Estimation page for shipping; compare a few lines for your country and weight before you submit the parcel."]])],
      ["LoveGoBuy costs, storage and payment", GLANCE([
        ["Costs", "item price with domestic delivery, international shipping, and customs declaration (generally ¥8 per parcel)"],
        ["Free storage", "60 days from the status \"stored\""],
        ["Payment", "international credit cards, PayPal and account top-up"],
        ["Apps", "iOS and Android; the App Store listing also advertises a free high-definition video quality check"]]) + SRC("From LoveGoBuy's help centre, home page and App Store listing, read 9 November 2026. Our LoveGoBuy links are affiliate links.")],
      ["What LoveGoBuy's QC check covers", `<p>When an item reaches the warehouse, LoveGoBuy's inspectors look at its appearance: colour, large areas of damage, stains, size, model and version number. For clothing the size is read from the label and tag, against any remark you left on the order.</p><p>Colour difference, exact measurements and how a piece wears are outside the check. For electronics only the outside is looked at: sealed boxes stay closed and nothing is switched on. If something the check should have caught is wrong when your parcel arrives, LoveGoBuy's after-sales service takes the request.</p>`],
      ["LoveGoBuy and EU customs", `<p>For the EU's new €2 customs handling fee on parcels from outside the EU, LoveGoBuy announced that it covers this fee for eligible new parcels submitted from 00:00 Beijing time on 10 November 2026, and that its logistics team prepares the customs documents (PID). Parcels submitted before that time are not covered.</p>${SRC("From LoveGoBuy's announcement \"Adjustment to EU Customs Fee Policy\", read 9 November 2026.")}`],
      ["Finding items on LoveGoBuy", `<p>Our button opens a find as ${WRAP("lovegobuy.com/product?platform=weidian&amp;id=7539696765")} (for a Weidian item with that ID), so the search step is done for you. On LoveGoBuy itself you can search Taobao, Tmall, 1688 and Weidian by keyword, paste a link, or upload a photo with its image search. Its Discord has experienced buyers who answer questions.</p>`],
      ["Tips for LoveGoBuy orders", `<ul>
<li><strong>Plan around 60 days:</strong> that is a short window for a slow multi-week haul, so order the items you want in one parcel close together.</li>
<li><strong>Bring your own measurements:</strong> the check reads the size on the label, so compare a garment you own with the seller's chart (<a href="/guides/sizing">sizing guide</a>).</li>
<li><strong>Find sold out?</strong> LoveGoBuy's image search can turn up the same item from another seller; upload the photo from the find's page here.</li></ul>`]],
    faq: [["How long does LoveGoBuy store items?", "60 days from the status \"stored\". If no parcel order has been submitted by then, the goods are treated as given up."],
          ["What does LoveGoBuy check in QC?", "The appearance of the item: colour, large damage, stains, size, model and version number, with size read from the label. Colour difference and exact measurements are outside the check."],
          ["What does LoveGoBuy charge?", "Its help centre gives the total as the item price with domestic delivery, international shipping and a customs declaration charge of generally ¥8 per parcel."],
          ["Does LoveGoBuy pay the EU €2 customs fee?", "LoveGoBuy announced it covers the €2 EU customs handling fee for eligible new parcels submitted from 10 November 2026 (Beijing time)."],
          ["What are the LoveGoBuy new-user coupons?", "Up to $141 in shipping coupons: freight coupons with different minimum spends plus a 30% off shipping coupon, claimed after signing up."],
          ["Can I paste a Weidian link into LoveGoBuy?", "Yes, its search bar takes a product link, a keyword or a photo. From Puro Classico you can skip that: the Buy via LoveGoBuy button opens the listing directly."]] },

  sugargoo: { title: "Sugargoo Spreadsheet 2026", lede: "Sugargoo links for every find: the button loads the original listing into Sugargoo's product page for you.",
    body: `<p>Sugargoo is one of the longer-running shopping agents. Its home page sums the service up in three steps: paste a link and pay; QC and storage, with 5 free photos and 100 days of storage; then shipping on more than 2,000 routes worldwide. Every find below does the first step for you by handing the original Weidian, Taobao or 1688 link to Sugargoo.</p><p>New users get ¥800 in international shipping coupons (14 coupons, valid for 90 days from the day you claim them) plus 100 points. Only one coupon can be used per parcel, so plan your parcels around the bigger ones.</p>`,
    desc: (N, Q) => `The Sugargoo spreadsheet: ${N} rep finds with direct Sugargoo links, ${Q} marked as having QC photos. 5 free QC photos, 100-day storage, ¥800 in coupons.`,
    about: [
      ["How to order on Sugargoo", STEPS([
        ["gift", "Register and open your coupons.", "The ¥800 pack lands under your username, then Coupons (in the app: My, then Coupons). They cover international shipping only."],
        ["cart", "Tap Buy via Sugargoo.", "Choose size, colour and quantity, add any extra services, and pay for the item and its delivery to the warehouse. A Sugargoo agent then confirms the order with the seller."],
        ["camera", "Review your 5 free photos.", "Sugargoo checks style, quantity, colour, size and model. Sealed packages are not opened; only the outside is compared with the listing."],
        ["box", "Combine items in the Packing Center.", "Pick the items for one parcel, enter your address and choose a route. Sugargoo's fee page lists a packing fee of ¥8 per parcel on top of the shipping."],
        ["truck", "Track it under My Parcel.", "Once the parcel has left, Check Logistics shows where it is."]])],
      ["Sugargoo costs, storage and QC", GLANCE([
        ["Costs", "product price with delivery to the warehouse, international shipping, a ¥8 packing fee per parcel, and optional value-added services"],
        ["QC photos", "5 free photos per item"],
        ["Free storage", "100 days from the status \"Has been Stored\"; 60 days for abnormal parcels"],
        ["Shipping", "more than 2,000 routes, with a Shipping Fee Estimation page to compare them"],
        ["App", "SUGARGOO on iOS"]]) + SRC("From Sugargoo's home page, help pages, blog and App Store listing, read 9 November 2026. Our Sugargoo links are affiliate links.")],
      ["How the Sugargoo coupon pack works", `<p>The new-user pack is 14 international shipping coupons worth ¥800 together, claimed in one go after you register and valid for 90 days. One coupon goes on each parcel. The coupons only reduce the shipping fee: value-added services are not discounted, and their cost does not count towards a coupon's minimum spend.</p><p>Sugargoo treats accounts that share a device, IP address or PayPal account as the same user, and each user can claim the pack once.</p>`],
      ["Sugargoo and EU customs", `<p>Sugargoo's notice explains the two EU charges now on parcels from outside the EU: a temporary tariff of €3 per item since 1 July 2026, and a Union Handling Fee of €2 per item since 1 November 2026, both counted per declaration item. Its example: a pen, a notebook and a key chain (three declaration items) come to €15, while two identical pens (one item) come to €5.</p><p>On postal and express lines those charges are the customer's. Sugargoo says its tax-free dedicated lines still avoid them, at slightly adjusted prices.</p>${SRC("From Sugargoo's notice on the EU \"Union Handling Fee\", read 9 November 2026.")}`],
      ["Opening links on Sugargoo", `<p>Sugargoo's product page takes the whole listing link: our button opens ${WRAP("sugargoo.com/#/home/productDetail?productLink=")} followed by the Weidian, Taobao or 1688 address. On Sugargoo itself you paste the same link into the search bar. Its app also names JD, Xianyu and Yupoo among the places it buys from, and Sugargoo offers Forwarding for parcels you send to its warehouse yourself.</p>`],
      ["Tips for Sugargoo orders", `<ul>
<li><strong>Coupons run out before storage does:</strong> the coupons last 90 days from claiming, your items 100 days in storage. Claim the pack when your first parcel is close, not on day one.</li>
<li><strong>Count your declaration items:</strong> on lines that pass on the EU charges, every extra declaration item adds €5 (€3 + €2), so a parcel of similar pieces costs less in fees.</li>
<li><strong>Compare routes first:</strong> Sugargoo posts regular updates on how fast each route is running; read the latest one, then check our <a href="/tools/shipping-calculator">shipping calculator</a>.</li></ul>`]],
    faq: [["Does Sugargoo charge a service fee?", "Sugargoo's fee page gives the purchase cost as the product price with domestic delivery plus international shipping. A packing fee of ¥8 per parcel applies, and value-added services are optional."],
          ["How many free QC photos does Sugargoo take?", "5 free photos per item, taken when it reaches the warehouse. They check style, quantity, colour, size and model."],
          ["How long does Sugargoo store items?", "100 days from the status \"Has been Stored\". Abnormal parcels, ones without an order or complete details, are kept for 60 days."],
          ["How do the Sugargoo new-user coupons work?", "New users get ¥800 in international shipping coupons (14 coupons) plus 100 points. The coupons are valid for 90 days from claiming, and one coupon can be used per parcel."],
          ["What does EU customs cost on a Sugargoo parcel?", "Sugargoo's notice gives €3 per declaration item (EU temporary tariff since 1 July 2026) plus €2 per item (Union Handling Fee since 1 November 2026) on postal and express lines; its tax-free lines avoid them at slightly adjusted prices."],
          ["How do I paste a link into Sugargoo?", "Copy the Weidian, Taobao or 1688 link and paste it into Sugargoo's search bar. From Puro Classico the Buy via Sugargoo button does this for you."]] },
};

// Agent x brand pages (/kakobuy-spreadsheet/ralph-lauren, 9 Nov 2026). An audit measured 93% shared text between them,
// so the copy is now built from that brand's own catalogue rows (finds, marketplaces, item types and their typical shipped
// weights, prices, finds marked as having QC photos, most viewed finds) together with the agent's own facts above (link
// format, QC check, returns, storage, EU customs), and each agent words it in its own way.
// pages.js hubSpec (agent x brand branch) calls agentBrandCopy(key, brand, slug, list) and uses { about, faq, desc }.
// Same rules as the brand hubs: p.qc >= 1 is "marked as having buyer QC photos", views only label a find from 5 views
// in 30 days, desc (the meta description) uses catalogue data only, and weights are typical figures per item type
// (weights.js), always called "about".
const AB_NF = n => n.toLocaleString("en-US");
const AB_PLAT = { weidian: "Weidian", taobao: "Taobao", "1688": "1688" };
const AB_CAT = { Tops: "tops", Outerwear: "outerwear", Shoes: "shoes", Pants: "pants", Shorts: "shorts", Bags: "bags", Accessories: "accessories", Headwear: "headwear", Toys: "toys" };
// What to look at in the photos, per item type (the same checks as the category intros above).
const AB_QC = { Tops: "print or embroidery placement, the neck label and the stitching at the hem and cuffs", Outerwear: "zips and snaps, badge placement, the fill and the inner labels",
  Shoes: "toe box and heel shape, the size tag inside the tongue and the stitching around the sole", Pants: "the wash, the pocket stitching and the buttons, rivets and zip",
  Shorts: "the waist, the length against the size chart and the embroidery", Bags: "the hardware engraving, the edge stitching and the lining",
  Accessories: "engraving depth, the clasp or buckle finish and the colour", Headwear: "the front embroidery, the inner tape and the strap", Toys: "the box and the parts count" };
const abList = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
const abKg = g => g >= 1000 ? `${(Math.round(g / 100) / 10).toFixed(1)} kg` : `${Math.round(g / 50) * 50} g`;
function abData(b, list) {
  const n = list.length, qc = list.filter(p => p.qc >= 1).length;
  const plat = {}; for (const p of list) plat[p.platform] = (plat[p.platform] || 0) + 1;
  const platOrder = Object.keys(plat).sort((x, y) => plat[y] - plat[x]);
  const cats = {}, catQc = {}; for (const p of list) { cats[p.cat] = (cats[p.cat] || 0) + 1; if (p.qc >= 1) catQc[p.cat] = (catQc[p.cat] || 0) + 1; }
  const catOrder = Object.keys(cats).filter(c => AB_CAT[c]).sort((x, y) => cats[y] - cats[x]);
  const types = {}; for (const p of list) { const t = itemTypeOf(p); if (typeGrams(t) && !/^other /.test(t)) types[t] = (types[t] || 0) + 1; }
  const typeOrder = Object.keys(types).sort((x, y) => types[y] - types[x]);
  const u = list.map(p => p.cny).filter(x => !isPH(x)).sort((x, y) => x - y);
  const top = list.filter(p => views(p)[1] >= 5).slice(0, 3);
  const ex = list[0];
  return { b, n, N: AB_NF(n), qc, pct: Math.round(qc * 100 / n), plat, platOrder, cats, catQc, catOrder, main: catOrder[0] || "Tops", types, typeOrder,
    t1: typeOrder[0] || "", t2: typeOrder[1] || "",
    lo: u.length ? money(u[0]) : "", hi: u.length ? money(u[u.length - 1]) : "", med: u.length ? money(u[Math.floor((u.length - 1) / 2)]) : "",
    top, ex, exId: ex.itemId || ex.id, exPlat: ex.platform };
}
const abPlat = d => abList(d.platOrder.map(k => `${AB_NF(d.plat[k])} ${AB_PLAT[k] || k}`)) + ` listing${d.n === 1 ? "" : "s"}`;
const abCats = d => d.catOrder.length === 1 ? `all ${AB_CAT[d.catOrder[0]]}` : `mostly ${AB_CAT[d.catOrder[0]]} (${AB_NF(d.cats[d.catOrder[0]])}) and ${AB_CAT[d.catOrder[1]]} (${AB_NF(d.cats[d.catOrder[1]])})`;
const abPrice = d => d.lo ? (d.lo === d.hi ? `listed at ${d.lo}` : `listed from ${d.lo} to ${d.hi}, half of them at ${d.med} or less`) : "";
const abQc = d => d.qc ? `${AB_NF(d.qc)} of the ${d.N} (${d.pct}%) are marked as having buyer QC photos on Puro Classico` : `None of them is marked as having buyer QC photos on Puro Classico yet`;
// QC photos on record per category, for the two biggest categories: "41 of the 120 tops and 12 of the 60 outerwear finds".
const abQcCats = d => abList(d.catOrder.slice(0, 2).map(c => `${AB_NF(d.catQc[c] || 0)} of the ${AB_NF(d.cats[c])} ${AB_CAT[c]}`));
const abTop = (d, lead) => d.top.length ? `<p>${lead} ${abList(d.top.map(p => `<a href="${productUrl(p)}">${esc(p.title)}</a> (${money(p.cny)})`))}.</p>` : "";
const abWrap = t => `<span style="overflow-wrap:anywhere">${esc(t)}</span>`;
const abHub = (d, key, name, s) => `<p>All of these also sit on the <a href="/brand/${s}">${esc(d.b)} reps spreadsheet</a>; the rest of the ${name} catalogue is on the <a href="/${key}-spreadsheet">${name} spreadsheet</a>.</p>`;
const abSteps = items => `<ol class="steps ic-steps-list">${items.map(([i, h, t]) => `<li>${icTile(i)}<strong>${h}</strong> ${t}</li>`).join("")}</ol>`;
// "puffer jackets (about 1.1 kg each shipped)"; shoes with and without the box.
const abType = (d, t) => !t ? "" : `${t} (about ${abKg(typeGrams(t))} each shipped${boxedGrams(t) ? `, ${abKg(boxedGrams(t))} with the box` : ""})`;
const abTypes = d => d.t1 ? `Most ${esc(d.b)} finds here are ${abType(d, d.t1)}${d.t2 ? `, followed by ${abType(d, d.t2)}` : ""}.` : "";
const abThree = d => d.t1 ? ` Three ${d.t1} come to roughly ${abKg(3 * typeGrams(d.t1))}${boxedGrams(d.t1) ? " without the boxes" : ""}.` : "";
const AB_OTHERS = key => abList(["MyCNBox", "KakoBuy", "Oopbuy", "LoveGoBuy", "Sugargoo"].filter(x => x.toLowerCase() !== key));
// The QC check that matters for the brand's main item type on KakoBuy: it opens garments, bags, suitcases and shoes only.
const kakoOpens = d => ["Accessories", "Headwear", "Toys"].includes(d.main) ? `${AB_CAT[d.main]} are not garments, bags or shoes, so KakoBuy checks most of these from the outside only` : `${AB_CAT[d.main]} are among the items KakoBuy opens for the check`;
// Oopbuy's own packing advice for the brand's main item type (its Packaging help page).
const OOP_PACK = { Outerwear: "vacuum bags, which Oopbuy calls a must for puffer jackets and other bulky pieces", Shoes: "Carton Packaging, with the shoe boxes removed or folded and any clothes vacuum-packed around them",
  Bags: "bubble wrap or stretch film, the cheap protection Oopbuy suggests", Accessories: "bubble wrap or stretch film, the cheap protection Oopbuy suggests" };
const oopPack = d => OOP_PACK[d.main] || "Simple Packaging with vacuum bags, on the lines that offer it, which Oopbuy suggests for parcels of clothes only";

const AGENT_BRAND = {
  mycnbox: (d, s) => {
    const B = esc(d.b), q = AB_QC[d.main];
    return {
      about: [
        [`${d.b} on MyCNBox, in numbers`, `<p class="lead">${d.N} ${B} finds${d.lo ? `, ${abPrice(d)}` : ""}. Each has a <strong>Buy via MyCNBox</strong> button that opens the listing pre-filled in MyCNBox.</p>
<p>The finds are ${abPlat(d)}, ${abCats(d)}. MyCNBox needs only the marketplace and the item ID, so the most viewed ${B} find opens as ${abWrap(`mycnbox.com/goodsDetail?mallType=${d.exPlat}&itemId=${d.exId}`)}.</p>${abTop(d, "Most viewed on Puro Classico in the last 30 days:")}${abHub(d, "mycnbox", "MyCNBox", s)}`],
        [`How to order ${d.b} on MyCNBox`, abSteps([["user-plus", "Sign up with code AACPYA.", `Up to $500 in new-user coupons, one used per parcel (<a href="/guides/mycnbox-coupon-code">how they work</a>).`],
          ["cart", `Open a ${B} find and tap Buy via MyCNBox.`, "Choose size and colour, and add detailed photos now if you want them."],
          ["camera", "Check the 4 photos in Warehouse.", `Returns must be asked for within 5 days of arrival. <a href="/guides/how-to-qc">How to read QC photos</a>.`],
          ["truck", "Ship within 90 days.", "Submit the parcel under Parcels and pay the estimated shipping; any difference is settled after packing."]])],
        [`Checking ${d.b} QC photos on MyCNBox`, `<p>${abQc(d)}: ${abQcCats(d)}. Whichever you pick, MyCNBox photographs your own item, 4 standard photos within one business day of arrival. Four shots may not show the ${q} up close, so for ${B} ${AB_CAT[d.main]} consider the detailed photo add-on, which has to be chosen when you order. A return costs the domestic shipping, ¥12 return shipping and a ¥10 warehouse fee, and has to be requested within 5 days.</p>`],
        [`Shipping ${d.b} from MyCNBox`, `<p>${abTypes(d)}${abThree(d)} MyCNBox keeps items for free for 90 days, so you can wait for a few ${B} pieces and pay one shipping fee. To an EU address, its tax-included lines cost €2 more per parcel and MyCNBox covers the duties on that parcel; its tax-excluded EU options are paused for now.</p>`]],
      faq: [[`How do I buy ${d.b} reps on MyCNBox?`, `Open one of the ${d.N} ${d.b} finds below and tap Buy via MyCNBox; the listing opens pre-filled. Pay for the item and the delivery to the warehouse, check the 4 standard QC photos, then submit your parcel within the 90 days of free storage.`],
            [`Will I get QC photos of my ${d.b} order on MyCNBox?`, `Yes, 4 standard photos within one business day of arrival, and more detailed ones if you choose that add-on when ordering. Separately, ${d.qc ? `${AB_NF(d.qc)} of the ${d.N} ${d.b} finds here are marked as having buyer QC photos` : `none of the ${d.b} finds here is marked as having buyer QC photos yet`}.`],
            [`What do ${d.b} reps cost on MyCNBox?`, d.lo ? `The ${d.N} finds are ${abPrice(d)}, before shipping. MyCNBox's help centre says it adds no service fee on purchases.` : `Prices are on each find. MyCNBox's help centre says it adds no service fee on purchases.`],
            [`Are these ${d.b} finds only for MyCNBox?`, `No. The same finds open on ${AB_OTHERS("mycnbox")}; every product page has a button for each agent.`]],
      desc: `${d.N} ${d.b} rep finds that open pre-filled in MyCNBox${d.lo ? `, ${d.lo} to ${d.hi}` : ""}, ${d.qc ? `${AB_NF(d.qc)} marked with buyer QC photos` : "with prices"}. 4 QC photos and 90 days of storage per item.` };
  },
  kakobuy: (d, s) => {
    const B = esc(d.b), q = AB_QC[d.main];
    return {
      about: [
        [`${d.b} on KakoBuy, in numbers`, `<p class="lead">${d.N} ${B} finds that open on KakoBuy's item page in one tap${d.lo ? `, ${abPrice(d)}` : ""}.</p>
<p>KakoBuy's item page works from the full marketplace address, so every button here hands over the original link. For the most viewed ${B} find that is ${abWrap(`kakobuy.com/item/details?url=${origUrl(d.ex)}`)}. The list is ${abPlat(d)}, ${abCats(d)}.</p>${abTop(d, "The ones visitors open most this month:")}${abHub(d, "kakobuy", "KakoBuy", s)}`],
        [`How to order ${d.b} on KakoBuy`, abSteps([["user-plus", "Register with code w5war.", `Up to $410 in new-user coupons (<a href="/guides/kakobuy-coupon-code">details</a>).`],
          ["link", `Tap Buy via KakoBuy on a ${B} find.`, "The original listing loads on KakoBuy; pick your size and colour."],
          ["card", "Pay.", "PayPal carries a 3.5% + $0.30 handling charge; KakoBuy lists none for Alipay and WeChat Pay."],
          ["truck", "Submit your waybill within 100 days.", "A customs declaration charge of generally ¥8 per parcel is added to the shipping."]])],
        [`Checking ${d.b} QC photos on KakoBuy`, `<p>${abQc(d)}, ${abQcCats(d)}. KakoBuy's own check covers model, style and size, and ${kakoOpens(d)}. It does not judge fit, so when the photos of your ${B} piece arrive, look at the ${q}, and compare the size with a piece you own.</p>`],
        [`Shipping ${d.b} from KakoBuy`, `<p>${abTypes(d)}${abThree(d)} With 100 days of storage you can collect several ${B} pieces before you submit one waybill.${d.t2 ? ` In the EU, KakoBuy charges €3 per parcel for the category-based duty however many item types are inside, so mixing ${d.t1} with other item types in one parcel still costs €3,` : " In the EU, KakoBuy charges €3 per parcel for the category-based duty however many item types are inside,"} and it covers the €2 EU handling fee on eligible shipments.</p>`]],
      faq: [[`How do I buy ${d.b} reps on KakoBuy?`, `Tap Buy via KakoBuy on any of the ${d.N} ${d.b} finds and the original listing loads on KakoBuy. Pay for the item and its delivery to the warehouse (KakoBuy's help centre lists no handling fee), check the photos, and submit a waybill within 100 days.`],
            [`Does KakoBuy QC check ${d.b} items?`, `KakoBuy checks the appearance: model, style and size, opening clothing, bags and shoes for it. On Puro Classico, ${d.qc ? `${AB_NF(d.qc)} of the ${d.N} ${d.b} finds are marked as having buyer QC photos` : `none of the ${d.b} finds is marked as having buyer QC photos yet`}.`],
            [`How much are ${d.b} reps on KakoBuy?`, d.lo ? `Listed prices run from ${d.lo} to ${d.hi} (half at ${d.med} or less) before shipping and the customs declaration charge of generally ¥8 per parcel.` : `Prices are on each find, before shipping and the customs declaration charge of generally ¥8 per parcel.`],
            [`Can I open these ${d.b} finds on another agent?`, `Yes: ${AB_OTHERS("kakobuy")} all have a button on every product page.`]],
      desc: `${d.N} ${d.b} reps that load on KakoBuy in one tap${d.lo ? ` (${d.lo} to ${d.hi})` : ""}${d.qc ? `, ${AB_NF(d.qc)} with buyer QC photos marked` : ""}, plus KakoBuy's QC check and 100-day storage.` };
  },
  oopbuy: (d, s) => {
    const B = esc(d.b), q = AB_QC[d.main];
    const per10 = d.t1 ? Math.ceil(10000 / typeGrams(d.t1)) : 0;
    return {
      about: [
        [`${d.b} on Oopbuy, in numbers`, `<p class="lead">${d.N} ${B} reps on Oopbuy${d.lo ? `, ${abPrice(d)}` : ""}: each find opens on Oopbuy with the marketplace and item ID already set.</p>
<p>On Oopbuy the most viewed ${B} find opens as ${abWrap(`oopbuy.com/product/${d.exPlat}/${d.exId}`)}. Across the list there are ${abPlat(d)}, ${abCats(d)}.</p>${abTop(d, "Most opened this month:")}${abHub(d, "oopbuy", "Oopbuy", s)}`],
        [`How to order ${d.b} on Oopbuy`, abSteps([["gift", "Register and get your coupon.", "A ¥3,500 new-user bundle plus a 30% off coupon (minimum spend applies)."],
          ["cart", `Tap Buy via Oopbuy on a ${B} find.`, "Select style, size and quantity, then pay."],
          ["camera", "Check the photos within 5 days.", "That is the return window after the item is stocked in."],
          ["box", "Create a waybill in My Warehouse.", "Storage is free for 90 days; pay the estimated shipping, then the actual cost after packing in My Shipments."]])],
        [`Checking ${d.b} QC photos on Oopbuy`, `<p>${abQc(d)} (${abQcCats(d)}). Oopbuy's arrival check compares quantity, colour, size and other specifications, then repacks the item in an Oopbuy bag. Colour difference and size error are outside that check, so compare the ${q} yourself, and do it soon: a return has to be requested within 5 days of "Stocked in".</p>`],
        [`Shipping ${d.b} from Oopbuy`, `<p>${abTypes(d)} For a parcel like that, Oopbuy's packing advice is ${oopPack(d)}.${per10 ? ` Around ${per10} ${d.t1} would pass 10 kg, the weight from which Oopbuy says customs are more likely to treat a parcel as commercial.` : ""} Oopbuy gives about 15 to 30 days from submitting the parcel to delivery, depending on the destination.</p>`]],
      faq: [[`How do I order ${d.b} reps on Oopbuy?`, `Pick one of the ${d.N} ${d.b} finds, tap Buy via Oopbuy, choose your size and pay. When the item is in your warehouse, create a waybill in My Warehouse within the 90 days of free storage.`],
            [`What does Oopbuy check on ${d.b} items?`, `Quantity, colour, size and other specifications; colour difference and size error are not covered. ${d.qc ? `${AB_NF(d.qc)} of the ${d.N} ${d.b} finds on Puro Classico are marked as having buyer QC photos.` : `None of the ${d.b} finds on Puro Classico is marked as having buyer QC photos yet.`}`],
            [`What do ${d.b} finds cost on Oopbuy?`, d.lo ? `They are listed from ${d.lo} to ${d.hi}, with half at ${d.med} or less. Oopbuy adds international shipping and a customs declaration fee of generally ¥8 per parcel.` : `Prices are on each find. Oopbuy adds international shipping and a customs declaration fee of generally ¥8 per parcel.`],
            [`Do these ${d.b} finds work on other agents?`, `Yes. ${AB_OTHERS("oopbuy")} each have a button on every product page.`]],
      desc: `${d.N} ${d.b} rep finds with direct Oopbuy links${d.lo ? `, ${d.lo} to ${d.hi}` : ""}${d.qc ? `, ${AB_NF(d.qc)} with buyer QC photos marked` : ""}. What Oopbuy checks, 90-day storage and its 5-day return window.` };
  },
  lovegobuy: (d, s) => {
    const B = esc(d.b), q = AB_QC[d.main];
    return {
      about: [
        [`${d.b} on LoveGoBuy, in numbers`, `<p class="lead">${d.N} ${B} finds with a direct LoveGoBuy link${d.lo ? `, ${abPrice(d)}` : ""}.</p>
<p>Each one skips LoveGoBuy's search bar: the most viewed ${B} find opens as ${abWrap(`lovegobuy.com/product?platform=${d.exPlat}&id=${d.exId}`)}. The list is ${abPlat(d)}, ${abCats(d)}.</p>${abTop(d, "What visitors open most this month:")}${abHub(d, "lovegobuy", "LoveGoBuy", s)}`],
        [`How to order ${d.b} on LoveGoBuy`, abSteps([["gift", "Sign up and claim the coupons.", "Up to $141 in new-user shipping coupons, each with its own minimum spend."],
          ["cart", `Tap Buy via LoveGoBuy on a ${B} find.`, "Choose your size and colour and pay for the item and warehouse delivery."],
          ["camera", "Check the arrival photos.", `Colour, damage, stains, size and model are checked. <a href="/guides/how-to-qc">How to read QC photos</a>.`],
          ["truck", "Ship within 60 days.", "Use LoveGoBuy's Estimation page to compare lines first."]])],
        [`Checking ${d.b} QC photos on LoveGoBuy`, `<p>${abQc(d)}; by type that is ${abQcCats(d)}. LoveGoBuy's inspectors check colour, stains, large damage, size and model, reading the size from the label, so the fit is yours to judge: compare the ${q} with the listing and your own measurements.</p>`],
        [`Shipping ${d.b} from LoveGoBuy`, `<p>${abTypes(d)}${abThree(d)} Storage on LoveGoBuy is 60 days from "stored", so order the ${B} pieces for one parcel close together. For EU addresses, LoveGoBuy covers the €2 EU customs handling fee on eligible parcels submitted from 10 November 2026 (Beijing time).</p>`]],
      faq: [[`How do I buy ${d.b} reps on LoveGoBuy?`, `Tap Buy via LoveGoBuy on one of the ${d.N} ${d.b} finds; the listing opens on LoveGoBuy's product page. Pay for the item and its delivery to the warehouse, check the photos, and send your parcel within the 60 days of storage.`],
            [`Does LoveGoBuy check ${d.b} items before shipping?`, `Yes, the appearance: colour, large damage, stains, size and model, with size read from the label. ${d.qc ? `${AB_NF(d.qc)} of the ${d.N} ${d.b} finds here are also marked as having buyer QC photos.` : `None of the ${d.b} finds here is marked as having buyer QC photos yet.`}`],
            [`What will ${d.b} reps cost on LoveGoBuy?`, d.lo ? `The finds are listed from ${d.lo} to ${d.hi} (half at ${d.med} or less). On top come international shipping and a customs declaration charge of generally ¥8 per parcel.` : `Prices are on each find. On top come international shipping and a customs declaration charge of generally ¥8 per parcel.`],
            [`Can I use these ${d.b} finds with another agent?`, `Yes. ${AB_OTHERS("lovegobuy")} also have a button on every product page.`]],
      desc: `${d.N} ${d.b} rep finds that open on LoveGoBuy${d.lo ? `, ${d.lo} to ${d.hi}` : ""}${d.qc ? `, ${AB_NF(d.qc)} with buyer QC photos marked` : ""}. LoveGoBuy's QC check, 60-day storage and shipping coupons.` };
  },
  sugargoo: (d, s) => {
    const B = esc(d.b), q = AB_QC[d.main];
    return {
      about: [
        [`${d.b} on Sugargoo, in numbers`, `<p class="lead">${d.N} ${B} finds that load straight into Sugargoo${d.lo ? `, ${abPrice(d)}` : ""}.</p>
<p>Sugargoo's product page takes the whole listing link, so the most viewed ${B} find opens as ${abWrap(`sugargoo.com/#/home/productDetail?productLink=${origUrl(d.ex)}`)}. In total there are ${abPlat(d)}, ${abCats(d)}.</p>${abTop(d, "Most viewed here in the last 30 days:")}${abHub(d, "sugargoo", "Sugargoo", s)}`],
        [`How to order ${d.b} on Sugargoo`, abSteps([["gift", "Register and open Coupons.", "¥800 in shipping coupons (14 coupons) plus 100 points for new users."],
          ["cart", `Tap Buy via Sugargoo on a ${B} find.`, "Choose size, colour and quantity, then pay for the item and its delivery to the warehouse."],
          ["camera", "Review your 5 free photos.", "Style, quantity, colour, size and model are checked."],
          ["box", "Pack it in the Packing Center.", "Pick a route within the 100 days of storage; a ¥8 packing fee applies per parcel."]])],
        [`Checking ${d.b} QC photos on Sugargoo`, `<p>${abQc(d)}, with ${abQcCats(d)}. Sugargoo adds 5 free photos of your own item when it reaches the warehouse, checking style, quantity, colour, size and model: use them to look at the ${q}. Sealed packages stay closed and are only compared with the listing from the outside.</p>`],
        [`Shipping ${d.b} from Sugargoo`, `<p>${abTypes(d)}${abThree(d)}${d.t2 ? ` On EU postal and express lines every declaration item costs €3 tariff plus a €2 handling fee, so a parcel mixing ${d.t1} with one other item type counts as two items and comes to €10; Sugargoo's tax-free lines avoid these at slightly adjusted prices.` : " On EU postal and express lines every declaration item costs €3 tariff plus a €2 handling fee; Sugargoo's tax-free lines avoid these at slightly adjusted prices."} Items can wait 100 days, while the ¥800 coupons last 90 days from claiming, one per parcel.</p>`]],
      faq: [[`How do I buy ${d.b} reps on Sugargoo?`, `Tap Buy via Sugargoo on one of the ${d.N} ${d.b} finds and the listing loads on Sugargoo. Pay for the item and its delivery to the warehouse, check the 5 free photos, then combine your items in the Packing Center within 100 days.`],
            [`How many QC photos will I get of a ${d.b} item on Sugargoo?`, `5 free photos per item. ${d.qc ? `On Puro Classico, ${AB_NF(d.qc)} of the ${d.N} ${d.b} finds are also marked as having buyer QC photos.` : `None of the ${d.b} finds on Puro Classico is marked as having buyer QC photos yet.`}`],
            [`What do ${d.b} reps cost on Sugargoo?`, d.lo ? `Listed prices go from ${d.lo} to ${d.hi}, half at ${d.med} or less. Sugargoo adds international shipping and a packing fee of ¥8 per parcel.` : `Prices are on each find. Sugargoo adds international shipping and a packing fee of ¥8 per parcel.`],
            [`Are these ${d.b} finds only for Sugargoo?`, `No, ${AB_OTHERS("sugargoo")} open them too, from the buttons on each product page.`]],
      desc: `${d.N} ${d.b} rep finds that load straight into Sugargoo${d.lo ? `, ${d.lo} to ${d.hi}` : ""}${d.qc ? `, ${AB_NF(d.qc)} with buyer QC photos marked` : ""}. 5 free QC photos and 100-day storage.` };
  },
};
// Two more questions per agent: storage and shipping, in that agent's terms (inserted before the "other agents" one).
const AB_FAQ2 = {
  mycnbox: d => [[`How long can my ${d.b} order wait at MyCNBox?`, `90 days for free from arrival at the warehouse, so there is time to collect a few ${d.b} pieces and ship them together. After that, storage has to be extended or the items are discarded.`],
    [`What does shipping ${d.b} to the EU cost on MyCNBox?`, `The line price for your parcel's weight${d.t1 ? ` (about ${abKg(typeGrams(d.t1))} for one of the ${d.t1})` : ""}, plus €2 per parcel on MyCNBox's tax-included EU lines, which then cover the customs duties on that parcel.`]],
  kakobuy: d => [[`How long can my ${d.b} order wait at KakoBuy?`, `100 days from the status "in storage". KakoBuy emails a reminder after 90 days, and items not submitted after 100 days are treated as abandoned.`],
    [`What does EU customs add to a ${d.b} parcel on KakoBuy?`, `€3 per parcel for the EU's category-based duty, whatever mix of item types is inside, added to the shipping cost. KakoBuy covers the €2 EU handling fee on eligible shipments.`]],
  oopbuy: d => [[`How long can my ${d.b} order wait at Oopbuy?`, `90 days free from the status "received", with an email before it ends. Extra time costs 10 CNY per 30 days.`],
    [`How should I pack ${d.b} on Oopbuy?`, `Oopbuy's packing advice for ${AB_CAT[d.main]} is ${oopPack(d)}. Keep the parcel under 10 kg if you can, since heavier parcels are more likely to be treated as commercial.`]],
  lovegobuy: d => [[`How long can my ${d.b} order wait at LoveGoBuy?`, `60 days from the status "stored". Without a parcel order by then the goods are treated as given up, so plan your ${d.b} haul within that window.`],
    [`Does LoveGoBuy charge the EU €2 fee on a ${d.b} parcel?`, `Not on eligible new parcels submitted from 10 November 2026 (Beijing time): LoveGoBuy announced it covers the €2 EU customs handling fee from then.`]],
  sugargoo: d => [[`How long can my ${d.b} order wait at Sugargoo?`, `100 days from the status "Has been Stored". The new-user shipping coupons last 90 days from claiming, so claim them close to your first parcel.`],
    [`What does EU customs add to a ${d.b} parcel on Sugargoo?`, `On postal and express lines, €3 tariff plus €2 handling fee per declaration item${d.t2 ? `, so ${d.t1} plus one other item type come to €10` : ""}. Sugargoo's tax-free lines avoid these at slightly adjusted prices.`]],
};
export function agentBrandCopy(key, b, s, list) {
  const f = AGENT_BRAND[key]; if (!f || !list || !list.length) return null;
  const d = abData(b, list), out = f(d, s);
  out.faq.splice(out.faq.length - 1, 0, ...AB_FAQ2[key](d));
  if (out.desc.length > 160) out.desc = out.desc.replace(/\. [^.]*\.$/, ".");   // drop the closing agent line before the snippet gets cut
  return out;
}

export const OLD_MONEY = {
  brands: ["Ralph Lauren", "Loro Piana", "Lacoste", "Burberry", "Moncler", "Hermes", "Maison Margiela", "Celine", "Loewe", "Brunello Cucinelli",
    "Golden Goose", "Zegna", "Max Mara", "Tom Ford", "Barbour", "Bottega Veneta", "Saint Laurent", "Ami", "Acne Studios", "Prada", "Miu Miu",
    "The Row", "Kiton", "Cartier", "Rolex", "Polo Ralph Lauren", "Sandro", "Arc'teryx Veilance"],
  // Brands /old-money links to (a chip) without their finds joining its list, so the page's count, title and first
  // page stay as they are. Move a name up into `brands` only as a deliberate decision that it belongs to the style.
  linked: ["Jacob Cohen"],
  intro: `<p>Old money, quiet luxury, "grisch", the understated look built on cashmere knits, cable sweaters, polos, loafers, quilted jackets and clean leather sneakers rather than big logos. It's where Puro Classico started, and it's the style most spreadsheets ignore.</p><p>This page collects finds from the brands that define the look (Ralph Lauren, Loro Piana, Brunello Cucinelli, Lacoste, Burberry, Moncler, Maison Margiela, Golden Goose and more), sorted with the most viewed first.</p><p>What to check in QC for this style: knit texture and ribbing on sweaters, the embroidery on small chest logos (it should be dense and clean), collar shape on polos, and the leather grain and stitching on shoes and belts. Colour matters more than usual here, compare the QC photo colour with the listing under neutral light.</p>`,
};

export const BRAND_INTRO = {
  "Corteiz": `<p>Corteiz (CRTZ) is the London streetwear label behind the Alcatraz logo, cargos and tracksuits. Its drops sell out quickly, which is why it's one of the most searched brands on rep spreadsheets. In QC, check the Alcatraz print or embroidery (sharpness, placement and size), the neck print and the fit: Corteiz pieces are cut boxy, so compare measurements rather than the size letter.</p>`,
  "Ralph Lauren": `<p>Ralph Lauren is the backbone of the old-money look: cable-knit sweaters, Oxford shirts, quarter-zips, polos and the Polo Bear. Most finds are affordable and easy first orders. In QC, zoom in on the pony embroidery (it should be dense with a clearly defined rider and mallet), the blue neck label, and the knit texture on sweaters.</p>`,
  "Nike": `<p>Nike covers everything from Tech Fleece and Dunks to Air Max and tracksuits. With so many models, compare the QC photos against retail photos of the same colourway: check the swoosh shape and placement, stitching quality, the size tag, and on sneakers the toe box and heel shape.</p>`,
  "Jordan": `<p>Jordan finds are mostly sneakers: Jordan 1, 3, 4 and 11 in many colourways. Batches vary a lot on Jordans, so prioritise listings with many QC photos. Check the shape from the side (heel "hourglass" on 1s), wings logo depth, stitching count and the size tag.</p>`,
  "Moncler": `<p>Moncler puffers and gilets are some of the most popular winter finds. Check the fill and loft (the jacket should look full, not flat), the felt or rubber logo patch on the sleeve, zips and snaps, and the inner tags. Puffers are light but bulky, ask for vacuum packing to reduce the volumetric weight.</p>`,
  "Stone Island": `<p>Stone Island is known for the compass badge on the left sleeve. In QC, check the badge (embroidery, colours and the two buttons holding it), garment-dyed colour consistency, and the inner labels. Overshirts and jackets are heavier, so factor that into shipping.</p>`,
  "Burberry": `<p>Burberry finds include the check scarves, trench coats, polos and shirts. The check pattern is the giveaway: in QC, look at how the stripes line up at seams and pockets, the colour of the camel base, and the TB or equestrian knight logo embroidery.</p>`,
  "Louis Vuitton": `<p>Louis Vuitton finds range from bags and small leather goods to belts, shoes and ready-to-wear. For leather goods, ask for close-up QC photos of the monogram alignment at seams, the heat stamp, stitching and hardware engraving.</p>`,
  "Dior": `<p>Dior finds include B23 and B27 sneakers, saddle bags, belts and the oblique-print ready-to-wear. Check oblique pattern alignment, hardware finish and logo fonts in the QC photos.</p>`,
  "Gucci": `<p>Gucci finds cover belts, loafers, bags and GG-monogram ready-to-wear. In QC, check the GG canvas alignment, the web stripe colours, hardware finish and the embossing on leather.</p>`,
  "Balenciaga": `<p>Balenciaga is best known on spreadsheets for the Track, Triple S and 3XL sneakers, plus oversized hoodies and tees. Chunky sneakers are heavy, so ship them without the box when you can. Check sole layering, logo prints and sizing (Balenciaga sneakers often run large).</p>`,
  "The North Face": `<p>The North Face Nuptse puffers, fleeces and shells are staple outerwear finds. Check the embroidered logo on chest and back, the fill on puffers, zips and the inner labels.</p>`,
  "Stussy": `<p>Stüssy tees, hoodies and knits are cheap, light and popular. Check the signature script logo (proportions and print quality), neck labels and fabric weight in the QC photos.</p>`,
  "Chrome Hearts": `<p>Chrome Hearts finds include hoodies, tees, hats, jewellery and eyewear. Check the horseshoe and cross graphics, print placement, and for jewellery the weight and engraving depth.</p>`,
  "Supreme": `<p>Supreme box-logo tees and hoodies, accessories and collab pieces. Check the box logo letter spacing and embroidery or print quality, plus the neck tag.</p>`,
  "Prada": `<p>Prada finds include nylon bags, the triangle-logo accessories, loafers and knitwear. Check the enamel triangle plate (shape, font and edges) and hardware finish.</p>`,
  "Lacoste": `<p>Lacoste polos, knits and tracksuits fit the clean, classic look. Check the crocodile embroidery (detailed, not blobby), the collar and placket, and the size label.</p>`,
  "Bape": `<p>Bape (A Bathing Ape) is known for camo, shark hoodies and Bapesta sneakers. Check camo pattern and colours, zip hardware on shark hoodies and the ape head logo.</p>`,
  "Amiri": `<p>Amiri jeans, knits and sneakers (MA-1, Skel). Check distressing and repair patches on denim, hardware and branding, and the fit: Amiri denim is slim.</p>`,
  "Loro Piana": `<p>Loro Piana is the definition of quiet luxury: cashmere knits, Summer Walk and Open Walk shoes, caps and overshirts. There are no big logos, so quality is all in the material: check knit texture, suede nap and colour against the listing.</p>`,
  "Golden Goose": `<p>Golden Goose Super-Star sneakers with the star and hand-distressed finish. Check the star shape and placement, the heel tab text, and that the distressing looks natural. Sizing is usually true to size in EU.</p>`,
  "Maison Margiela": `<p>Maison Margiela is best known for the GAT/Replica sneakers, Tabi boots and the four-stitch label. Check the stitch label on the back, sole shape and suede quality.</p>`,
  "Essentials": `<p>Fear of God Essentials hoodies, sweatpants and tees are a popular starter pick. Check the rubberised chest logo, fabric weight and the relaxed fit, they run oversized.</p>`,
  "Trapstar": `<p>Trapstar tracksuits, puffers and tees. Check the chenille or embroidered logos, zip pulls and the fit of tracksuit sets.</p>`,
  "Adidas": `<p>Adidas finds include Sambas, Gazelles, Campus and Yeezy-era sneakers plus tracksuits. Check the three-stripe placement, suede quality, gum sole colour and size tag.</p>`,
  "Hermes": `<p>Hermès finds include belts, sandals (Oran, Chypre), bracelets and small leather goods. Check the H buckle finish, leather grain and stamping.</p>`,
};

export const GUIDES = {
  "how-to-buy-from-weidian": {
    title: "How to Buy from Weidian (2026): Step-by-Step Guide with an Agent",
    desc: "Most Weidian sellers only ship inside China. How to buy from Weidian with a shopping agent in 6 steps: links, payment, QC photos, costs and delivery times.",
    h1: "How to buy from Weidian",
    updated: "2026-10-28",   // the day this text was revised; change it only when it is revised again
    finds: { platform: "weidian" },
    body: `<p class="lead">To buy from Weidian outside China, use a <strong>shopping agent</strong>: open the Weidian listing in the agent (every find on Puro Classico does this with one tap), pay for the item and its delivery to the agent's warehouse in China, check the QC photos, then ship everything in one parcel. You need an agent because most Weidian sellers only ship inside China, and sign-up and payment are built around Chinese phone numbers and payment apps.</p>
<p><a class="btn light" href="/">Browse 9,000+ Weidian, Taobao and 1688 finds →</a></p>
<h2>What is Weidian?</h2><p>Weidian (微店, "micro shop") is a Chinese shop platform, used mostly on phones, where independent sellers run their own small stores. It is run by a different company from Taobao and 1688, which belong to Alibaba. Many rep sellers list on Weidian: about nine in ten finds on Puro Classico are Weidian listings.</p>
<h2>What you need</h2><ul><li><strong>A shopping agent account.</strong> We use <a href="/mycnbox-spreadsheet">MyCNBox</a>; <a href="/kakobuy-spreadsheet">KakoBuy</a>, <a href="/oopbuy-spreadsheet">Oopbuy</a>, <a href="/lovegobuy-spreadsheet">LoveGoBuy</a> and <a href="/sugargoo-spreadsheet">Sugargoo</a> work the same way (<a href="/guides/best-shopping-agent">how to choose</a>).</li>
<li><strong>The Weidian link or item ID.</strong> A listing link looks like <code>weidian.com/item.html?itemID=…</code>. Share links copied from the Weidian app (youshop10.com) are often short links without the item ID: open one in your browser first and copy the full weidian.com link it leads to. The <a href="/tools/link-converter">link converter</a> turns any full Weidian link into a buy link for each agent.</li>
<li><strong>A payment method your agent accepts.</strong> You pay the agent, not Weidian. Accepted cards and wallets differ by agent, so check its payment page.</li></ul>
<h2>Step by step</h2><ol class="steps">
<li><strong>Find the item.</strong> Browse <a href="/">Puro Classico</a> by <a href="/brands">brand</a> or category, or paste a Weidian link into your agent's search bar.</li>
<li><strong>Pick size and colour.</strong> Weidian listings are in Chinese; the agent translates the options. Compare the seller's size chart in centimetres with a garment you own (<a href="/guides/sizing">sizing guide</a>).</li>
<li><strong>Pay for the item and domestic shipping.</strong> You pay the item price plus the short delivery from the seller to the agent's warehouse in China. International shipping is paid later.</li>
<li><strong>Wait for the item to reach the warehouse</strong>, often a few days. The agent then takes <strong>QC photos</strong>: real photos of your exact item.</li>
<li><strong>Check the QC photos.</strong> Look at logos, stitching, colour and the size tag (<a href="/guides/how-to-qc">how to read QC photos</a>). If something is wrong you can usually ask for a return or exchange before it ships; fees and time limits depend on the agent and the seller.</li>
<li><strong>Ship your parcel.</strong> Combine everything into one parcel, choose a shipping line (<a href="/guides/shipping-lines">shipping lines explained</a>) and pay the international shipping. Many agents refund the difference if the final cost is lower. Parcels usually arrive in roughly 1 to 3 weeks, depending on the line and your country.</li></ol>
<h2>What it costs</h2><p>Your total is the Weidian item price + domestic shipping to the warehouse (often free or a few dollars) + international shipping (charged on weight and box size) + any extras you choose, such as extra photos, insurance or vacuum packing. International shipping is usually the biggest variable, so combine several items into one parcel and remove shoe boxes you don't need. Get a rough figure first with the <a href="/tools/shipping-calculator">shipping calculator</a> (add your items and it estimates the weight too).</p>
<h2>Weidian, Taobao or 1688?</h2><p>Agents handle all three the same way. Weidian is where many rep sellers list, <a href="/guides/how-to-buy-from-taobao">Taobao</a> is China's biggest online marketplace, and <a href="/guides/how-to-buy-from-1688">1688</a> is Alibaba's wholesale site, where some listings have a minimum quantity.</p>
<h2>How we keep Weidian links working</h2><p>Weidian listings get deleted and sell out. We check every Weidian find on Puro Classico each week: listings found deleted are hidden from the spreadsheet, and sold-out ones are marked on their pages.</p>
<h2>Tips for a first Weidian order</h2><ul><li>Start with one or two items to learn the process.</li><li>Prefer finds with buyer QC photos (<a href="/qc-spreadsheet">QC photos spreadsheet</a>).</li><li>Keep your parcel's declared value and contents accurate, and follow your country's import rules.</li></ul>
<p>Prefer video? Watch the <a href="/how-to-order">1:47 how-to-order video</a>.</p>`,
    faq: [["Can I buy from Weidian without an agent?", "Rarely, if you live outside China. Most Weidian sellers only ship inside China, and sign-up and payment are built around Chinese phone numbers and payment apps, so an agent buys the item and ships it to you."],
          ["What is Weidian?", "A Chinese shop platform, used mostly on phones, where independent sellers run their own stores. Many rep sellers list there; about nine in ten finds on Puro Classico are Weidian listings."],
          ["Is Weidian the same as Taobao?", "No. Both are Chinese marketplaces, but Weidian is run by a different company from Taobao, which belongs to Alibaba. Agents support Weidian, Taobao and 1688."],
          ["How do I pay for Weidian items?", "You pay your shopping agent, not Weidian: the item price and domestic delivery first, international shipping when you send your parcel. Each agent lists the cards and wallets it accepts."],
          ["How long does Weidian shipping take?", "Usually a few days from the seller to the agent's warehouse, then roughly 1 to 3 weeks internationally, depending on the shipping line and your country."],
          ["What if a Weidian link does not open?", "The listing may have been deleted or sold out. A short share link (youshop10.com) has to be opened in a browser first to get the full weidian.com link, which the link converter can read."]],
  },
  "how-to-qc": {
    title: "How to Read QC Photos: Stitching, Hardware & Logo Checks",
    desc: "What are QC photos? A checklist for your agent's QC (quality check) pictures: stitching, hardware and zips, logos, colour and size tags, plus what GL/RL means.",
    h1: "QC photos: what they are and how to read them",
    updated: "2026-10-28",   // the day this text was revised; change it only when it is revised again
    finds: { qc: 1 },
    body: `<p class="lead">QC (quality check) photos are real photos of <em>your</em> item, taken by your agent's warehouse after it arrives from the seller and before it ships to you. They're your chance to catch problems while returns are still easy.</p>
<p>Want to see QC photos before you buy? Paste a Weidian, Taobao or 1688 link into the <a href="/tools/qc-checker">QC checker</a>, or browse the <a href="/qc-spreadsheet">QC photos spreadsheet</a>: 2,000+ finds our catalogue marks as having buyer QC photos from earlier orders.</p>
<h2>The 5-point checklist</h2><ol class="steps">
<li><strong>Logos and prints.</strong> Compare size, position and font with retail photos of the same item. Embroidery should be dense and clean; prints sharp, not blurry or cracked.</li>
<li><strong>Stitching.</strong> Look for straight, even stitching along seams, hems and pockets, and no loose threads or glue marks (on shoes check around the sole).</li>
<li><strong>Colour.</strong> Compare with the listing. Warehouse lighting can shift colours slightly, so compare against the other items in the same photo if unsure.</li>
<li><strong>Size tag and measurements.</strong> Make sure the size label matches what you ordered. Many agents photograph the item on a measuring mat, compare against the size chart.</li>
<li><strong>Defects.</strong> Stains, holes, scratches on hardware, uneven dye, wrong accessories.</li></ol>
<h2>GL or RL?</h2><p>On forums you'll see <strong>GL</strong> (green light, ship it) and <strong>RL</strong> (red light, return or exchange). Post your QC photos in our <a href="/discord">Discord</a> if you want a second opinion.</p>
<h2>Category tips</h2><ul><li><a href="/category/sneakers">Sneakers</a>: shape from the side, toe box, heel, logo depth, size tag inside the tongue.</li><li><a href="/category/jackets">Jackets</a>: zips, snaps and pulls, fill on puffers, patches and badges.</li><li><a href="/category/tops">Knitwear and tees</a>: knit texture, neck labels, embroidery density.</li><li><a href="/category/bags">Bags</a>: hardware engraving, edge stitching, lining.</li></ul>
<h2>Need more photos?</h2><p>Most agents offer extra or detailed photos for a small fee. It's worth it for expensive items like bags, shoes and outerwear.</p>
<h2>QC photos on Puro Classico</h2><p>A QC badge on a find's card means our catalogue has buyer QC photos on record for that listing. Open the find to see them; if they can't be loaded, your agent still photographs your own item at the warehouse. The <a href="/tools/qc-checker">QC photo checker</a> also reads shopping-agent links: paste a KakoBuy, Oopbuy, Sugargoo or MyCNBox product link and it finds the Weidian, Taobao or 1688 listing behind it.</p>`,
    faq: [["What does QC stand for?", "Quality check: real photos of your exact item taken by the agent's warehouse before it ships internationally."],
          ["Can I return an item after QC?", "Usually yes, as long as it has not shipped from the warehouse: the agent contacts the seller for you. Terms depend on the seller and agent, and domestic return shipping may apply."],
          ["Where can I see QC photos before I buy?", "Paste the product link into our QC checker, or open a find marked QC on Puro Classico. QC photos only exist for listings someone has already bought through an agent."],
          ["Can I ask for more QC photos?", "Most agents sell extra or detailed photos for a small fee. On some, such as MyCNBox, that add-on has to be chosen when you place the order, not after the item arrives."]],
  },
  "sizing": {
    title: "Rep Sizing Guide: Asian vs EU/US Sizes (and How to Measure)",
    desc: "Chinese sellers often use Asian sizing that runs small. How to measure your clothes, read size charts in cm, and pick the right size for reps.",
    h1: "Rep sizing guide",
    updated: "2026-10-29",   // the day this text was revised; change it only when it is revised again
    body: `<p class="lead">Do reps run small? Often, yes: many Weidian and Taobao sellers use Asian sizing, which tends to run about one size smaller than EU/US sizing, but not always. The only reliable method is to compare the seller's size chart in centimetres with a garment you own that fits.</p>
<h2>How to measure (5 minutes)</h2><ol class="steps">
<li>Take a piece you own that fits the way you like (same type: hoodie for a hoodie, jeans for jeans).</li>
<li>Lay it flat. Measure <strong>chest</strong> (pit to pit, then double it if the chart shows full chest), <strong>length</strong> (top of shoulder to hem) and <strong>sleeve</strong>. For pants: waist, inseam, thigh and leg opening.</li>
<li>Compare with the seller's size chart in centimetres (agents translate it). Pick the size closest to your measurements, not the letter.</li></ol>
<p>Want a quick starting point first? The <a href="/tools/size-estimator">size estimator</a> turns your height, weight and fit into a size to look for, and compares a seller's chart with a garment you own.</p>
<h2>Rules of thumb</h2><ul><li>Streetwear brands like <a href="/brand/essentials">Essentials</a> and <a href="/brand/corteiz">Corteiz</a> are cut oversized and boxy, so measurements matter more than the label.</li><li>For sneakers, use EU size and your foot length in cm; check whether the model runs large or small at retail.</li><li>Between sizes? For tops size up; for fitted items (polos, knits, jeans) compare waist and chest carefully.</li><li>Ask the warehouse to measure in the QC photos if the chart is unclear.</li><li>Brand notes from our brand pages: <a href="/brand/balenciaga">Balenciaga</a> sneakers often run large, <a href="/brand/amiri">Amiri</a> denim is slim, and <a href="/brand/golden-goose">Golden Goose</a> is usually true to size in EU.</li></ul>
<p>More: <a href="/guides/how-to-qc">how to read QC photos</a> · <a href="/how-to-order">how to order</a>.</p>`,
    faq: [["Do reps run small?", "Often, because many sellers use Asian sizing. Always check the seller's chart in centimetres against a garment you own."],
          ["Should I size up for reps?", "For tops, size up if you are between sizes or want a relaxed fit. For fitted items such as polos, knits and jeans, compare the chest and waist measurements instead of the size letter."],
          ["How do I pick a rep sneaker size?", "Use your EU size and your foot length in centimetres, compare them with the seller's chart, and check whether that model runs large or small at retail."]],
  },
  "best-shopping-agent": {
    title: "Best Shopping Agent 2026: MyCNBox vs KakoBuy vs Oopbuy vs Sugargoo",
    desc: "How to pick a shopping agent for Weidian, Taobao and 1688: what to compare (shipping, fees, QC photos), KakoBuy vs Oopbuy vs Sugargoo, and the agent we use.",
    h1: "Best shopping agent in 2026: how to choose",
    updated: "2026-10-28",   // the day this text was revised; change it only when it is revised again
    body: `<p class="lead">There is no single best shopping agent for everyone. MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo all buy from Weidian, Taobao and 1688, take QC photos at their warehouse and ship your items in one parcel, so the difference that usually matters most is the shipping price to your country. For a first order we recommend <a href="/mycnbox-spreadsheet">MyCNBox</a>, our most-used agent.</p>
<h2>What to compare</h2><ul><li><strong>Service fees</strong>: some agents charge a percentage per item, others none.</li><li><strong>Shipping lines</strong>: the choice of lines to your country, their prices and speed. This usually matters more than the service fee.</li><li><strong>QC photos</strong>: how many free photos, and how clear they are.</li><li><strong>Storage time</strong>: how long your items can wait in the warehouse for free while you collect a parcel.</li><li><strong>Payment and refunds</strong>: accepted cards and wallets, and whether shipping differences are refunded to your balance.</li><li><strong>Support</strong>: response time and language.</li></ul>
<h2>Agents we support</h2><p>Every find on Puro Classico has buy links for all of these, so you can use whichever you prefer:</p><ul>
<li><a href="/mycnbox-spreadsheet"><strong>MyCNBox</strong></a>, our most-used agent and the one we recommend for first orders; new-user coupon bundle when you sign up through us. <a href="/guides/mycnbox-review">Is MyCNBox legit?</a></li>
<li><a href="/kakobuy-spreadsheet"><strong>KakoBuy</strong></a>, very widely used, large community. <a href="/guides/kakobuy-vs-mycnbox">KakoBuy vs MyCNBox</a></li>
<li><a href="/oopbuy-spreadsheet"><strong>Oopbuy</strong></a></li><li><a href="/lovegobuy-spreadsheet"><strong>LoveGoBuy</strong></a></li><li><a href="/sugargoo-spreadsheet"><strong>Sugargoo</strong></a></li></ul>
<h2>KakoBuy vs Oopbuy vs Sugargoo</h2><p>The ordering flow is the same on all three: pay for the item and delivery to the warehouse, check the QC photos, then pay international shipping when you send your parcel. Every find on Puro Classico opens on each of them, so compare them on the same item: open a find, tap the buy button for two agents, and compare the service fee and the shipping estimate for your country and parcel weight before you pay.</p>
<h2>Test an agent with a small first order</h2><ol class="steps"><li>Sign up and check the new-member coupons (<a href="/guides/agent-coupons">all agent sign-up bonuses</a>).</li><li>Order one or two light items, such as a tee or a cap.</li><li>See how quickly the QC photos arrive and how clear they are.</li><li>Submit the parcel, and compare its shipping estimate with another agent's estimator for the same weight.</li></ol>
<div class="note">Disclosure: links to agents on Puro Classico are affiliate links: we may earn a commission at no extra cost to you. Fees and shipping prices change often, so check the agent's own pages before you order.</div>
<p>New to all this? Start with the <a href="/how-to-order">how-to-order video</a>.</p>`,
    faq: [["Which shopping agent is best for beginners?", "Any major agent works. We recommend MyCNBox for a first order because the listing opens pre-filled from Puro Classico and new users get a coupon bundle."],
          ["Can I use a different agent for each order?", "Yes. Every find on Puro Classico has links for MyCNBox, KakoBuy, Oopbuy, LoveGoBuy and Sugargoo."],
          ["KakoBuy vs Oopbuy vs Sugargoo: what is the difference?", "All three buy from the same Weidian, Taobao and 1688 listings, take QC photos at their warehouse and ship your items in one parcel, and every find on Puro Classico opens in each of them. What differs between them: service fees, the shipping lines and prices to your country, free QC photos, storage time and support. These change often, so check each agent's own fee page and put the same parcel weight into each shipping estimator before you order."],
          ["What is the difference between KakoBuy and Taobao?", "Taobao is a Chinese marketplace where sellers list items. KakoBuy is a shopping agent: it buys a Taobao, Weidian or 1688 item for you, takes QC photos of it at its warehouse and ships it abroad. You find the item on Taobao or a spreadsheet and order it through KakoBuy."]],
  },
};
