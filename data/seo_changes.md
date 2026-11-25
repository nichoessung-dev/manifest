# SEO changes

Every SEO change to the site, newest first: what changed, why, which URLs, and how to undo it. The checks behind the
decisions: data/seo_ranks.json (Google positions and the index check of 22 Nov 2026, scripts/seo_ranks.py),
data/seo_ranks_markets.json (the spreadsheet searches in ten countries, 23 Nov 2026), data/seo_ranks_best.json (the
searches of the model pages added on 23 Nov 2026, checked before they existed) and data/seo_page_clicks.json (buy clicks
per page by visit source and country, buy clicks per find, site searches; scripts/seo_page_clicks.py).

## 25 Nov 2026: guide layout v12, guide titles, agents compared, agent FAQs, hub boilerplate

The audit behind it (crawl of all 1,028 sitemap pages and 150 product pages, Search Console 6 months to 22 Nov 2026, mobile
Core Web Vitals in the lab, the top results for the head terms): the scratchpad file seo_audit.md of that session.

- Guide layout (all 18 guides, renderGuide in pages.js, "guide layout v12" in ds.css): a hero with the lead, reading time,
  "Open the spreadsheet" plus one tool or page that fits the guide, and three catalogue facts; from 1024px a side column
  that stays in view ("On this page" with the section being read marked, and a spreadsheet card); below 1024px "On this
  page" folds into one row and the product page's bar carries the spreadsheet button once the hero button is off screen
  (gone again at the closing panel); the guide's 8 finds moved from the end of the page into the text (a swipeable row on
  phones); "How we check this guide"; a closing panel with the spreadsheet button; related guides as cards. Wide tables
  scroll in their own box with the first column held. Article data gains image, mainEntityOfPage and inLanguage, and
  og:type is "article" on guides. The guides index got the same buttons and facts.
- Titles and descriptions where Search Console showed impressions but few clicks: how-to-qc (7,900 impressions, 0.3%),
  how-to-buy-from-weidian (6,000, 0.6%), best-shopping-agent (5,000, 1.0%), kakobuy-vs-mycnbox (711, 1.8%), sizing (494,
  1.6%), rep-glossary (338, 0.6%).
- QC guide: "Real QC photos, and what to check in them", three sets of banked buyer QC photos (sneakers, a polo, a belt)
  with what to check in each (content.js qcEx, pages.js qcExamples). People searching "qc photos", "qc pics" and "qc
  pictures" land on this guide and want to see QC photos.
- Best shopping agent and KakoBuy vs MyCNBox: the agents side by side (fee, per-parcel charge, warehouse check, free storage,
  new-user offer) and the cheapest 1 kg line per country from shipping_lines.js (pages.js AGENT_FACTS, agentCompare). Same
  facts and dates as the agent spreadsheets; nothing ranked. The KakoBuy vs MyCNBox table had no facts and an unsourced
  "community" row.
- Agent spreadsheets (MyCNBox, KakoBuy, Oopbuy, LoveGoBuy, Sugargoo): up to five more questions each, the ones the pages
  above ours answer (what it is, free, official, how often updated, shipping prices from the agent's estimator), and an
  "<agent> guides" link list (coupon code, KakoBuy vs MyCNBox, best agent, QC guide). Titles unchanged.
- Hubs: the homepage's "agent-neutral rep finds spreadsheet" block (about 290 words and 4 questions) is no longer repeated
  on every hub (hubApp in the middleware); each hub keeps its own About block.
- Counts: a page is only kept in the edge cache when the hidden finds were read (reported.js reportedOk), and a failed read
  is tried again on the next request. The crawl found /mycnbox-spreadsheet saying 1,938 finds with QC photos while the
  other agents said 1,267.
- Descriptions over 160 characters shortened: /tools/size-estimator, /tools/parcel-tracker, /cnfans-spreadsheet,
  /how-to-order, /about. The product pages and the rep spreadsheet guide said "1:47 video"; the video is 56 seconds.
- PRODUCT_TPL w112, DS_VER 39 (the static pages were on ?v=23).
- Undo: the renderGuide block and the "guide layout v12" CSS block; the title, desc, updated, qcEx and compare fields in
  content.js, content2.js and content3.js; agentFaqMore and agentGuides in hubSpec; the section#seo rule in hubApp;
  reportedOk in reported.js and keep() in the middleware.

## 23 Nov 2026: the Chrome Hearts "jewellery" page is named for what it lists

- What: /best/chrome-hearts-jewelry is now "Best Chrome Hearts Cross Reps" (title, h1, intro and QC checklist). The URL stays.
- Why: its pattern matches "cross", so 62 of its 75 listings are cross-print clothing, not jewellery, while the page ranks
  for "chrome hearts reps" (5th UK, 9th US on 23 Nov). The owner chose to rename it to match rather than cut it to about 10
  jewellery finds.
- Undo: functions/_lib/content3.js, the "chrome-hearts-jewelry" entries in MODELS3 and MODEL_TERM.

## 23 Nov 2026: the spreadsheet searches, 34 model pages, agent shipping lines

The baseline, taken before these changes (Serper, 467 credits): data/seo_ranks_markets.json has the 16 spreadsheet searches
in the US, UK, Germany, Sweden, Poland, Canada, Norway, the Netherlands, Denmark and Australia (the ten countries with the
most buy clicks), looked up to the top 30; data/seo_ranks_best.json has one search per new model page in the US and UK.
What it showed: the rep spreadsheet guide is 2nd to 6th for "rep spreadsheet" in all ten countries and 2nd to 6th for "reps
spreadsheet" in five, and the homepage is in none; the guide (not /taobao-spreadsheet) is 8th to 14th for "taobao
spreadsheet"; /mycnbox-spreadsheet is 4th for "mycnbox spreadsheet" in eight countries but not in the US or UK top 30; page 8
of the 1688 list (which no longer exists) is 7th to 11th for "1688 spreadsheet"; we are in no top 30 for "weidian
spreadsheet", "finds spreadsheet", "oopbuy spreadsheet", "lovegobuy spreadsheet", "cnfans spreadsheet" or "qc spreadsheet".
Google buy clicks come from many countries (data/seo_page_clicks.json "google_countries_by_page"): /kakobuy-spreadsheet
most from Denmark, the US, the UK, Poland and the Netherlands, /sugargoo-spreadsheet from Czechia, Sweden and the UK. What
ranks above us: Reddit threads, sites named after the search (kakobuyspreadsheet.gg, sugargoo.net, taobao-spreadsheet.net,
cnfan-sheet.com, 1688links.net), finders with an FAQ and live QC data (rep.tools, finderqc.com, goodsqc.com) and, for
"weidian spreadsheet", weidian.com shops. Most say "updated daily" and "2026" and hold far fewer finds than we do; what they
have that we lack is links from elsewhere (the link drafts for the owner are a separate file, not on the site).

- Real counts: the Weidian, Taobao, 1688, QC, agent and agent x QC/budget spreadsheets count only the finds a visitor can
  see (not hidden after reports or the photo check, listing not gone): "Weidian Spreadsheet 2026: 10,280 Rep Finds" where it
  said 13,770, Taobao 229 (was 460), 1688 179 (was 370), QC 1,273 (was 1,969). Their pages 2 and up and the sitemap list
  the same finds, so /weidian-spreadsheet/173 to /229, /1688-spreadsheet/4 to /7 and some Taobao pages now 301 to page 1
  (rescue() in the middleware). The site-wide QC count (homepage tile, guides) comes from the same bake as the finds count:
  "1,300+" where server pages said "1,900+". Code: shown() and setHidden() in site.js (the middleware hands over the hidden
  set from data/reported.json), findShown in pages.js, QC_PLUS in site.js.
- Rep spreadsheet, reps spreadsheet, fashion reps spreadsheet, finds spreadsheet: one page, /guides/what-is-a-rep-spreadsheet,
  the page Google already shows. Title "Rep Spreadsheet 2026: 10,600+ Finds and How to Use One", h1 "Rep spreadsheet: 10,600+
  finds and how to use one", a description with the finds and QC counts. It now opens with the spreadsheet itself: its 8 most
  popular finds with buy buttons, the counts by category (visible finds), the finds added in the last 7 days, and links to
  every spreadsheet by agent, marketplace and style with those words as the link text. Its lead says "rep spreadsheet (or
  finds spreadsheet)" and where spreadsheets started (FashionReps, Discord). The homepage title is left as it is
  (it carries the brand searches); its footer link "Rep spreadsheet" still goes to the homepage.
- Taobao, 1688 and Weidian spreadsheets: the rep spreadsheet guide links each with its name as the link text, and the
  how-to-buy guides' button says "Open the Weidian spreadsheet: N finds" (was "See all N Weidian finds"). Each marketplace
  spreadsheet gets "New <marketplace> finds this week" (how many were added in 7 days, the 8 newest).
- Agent spreadsheets (KakoBuy, Sugargoo, Oopbuy): "<agent> shipping lines and prices", a table of the three cheapest lines
  and the fastest one to the US, UK, Germany and Sweden for a 1 kg parcel (branded clothing where the estimator asks for a
  goods type; KakoBuy's was given none), read from each agent's own estimator on 23 Nov 2026 (functions/_lib/shipping_lines.js says how; read them again before relying on the prices for more
  than a few weeks). MyCNBox's estimator needs an account, so its page shows the figures MyCNBox publishes on its homepage
  (12.5 days dispatch to delivery, 99.5% delivered, real parcel samples with their lines, warehouse times for 16 to 22 Nov).
  LoveGoBuy's site sits behind a browser check, so its page has no table. All five get "New finds this week" with a link that
  opens each new find on that agent. The titles of the agent pages are unchanged (they bring most of the Google buy clicks).
- Oopbuy's new-user offer corrected to what Oopbuy showed on 23 Nov 2026: a ¥3,500 bundle plus 15% off shipping (the
  copy of 9 Nov said a 30% off coupon). Code: content.js AGENT_INTRO.oopbuy and agentBrandCopy.
- QC spreadsheet: the page for "qc spreadsheet". Title "QC Spreadsheet 2026: N Finds With Buyer QC Photos", h1 "QC
  Spreadsheet: Finds With Buyer QC Photos", breadcrumb and footer link "QC spreadsheet", and an About block with its finds by
  category and the QC checklist for each item type.
- QC finder (/tools/qc-checker, for "qc finder" and "qc photos reps"): two sections under How It Works: what each agent's
  warehouse check covers (from the agents' help centres, the same facts as their spreadsheets) and the 12 finds with the
  most buyer QC photos on record, linked to their QC photos. toolShell (site.js) takes the new `extra`.
- CNFans spreadsheet: says what happened, with dates (the daily site check found a maintenance page until 16 Nov 2026 and
  cnfans.com has not loaded since 18 Nov 2026), compares the five agents that open every find (QC check, free storage,
  new-user offer, from their spreadsheets' sources) and explains old links. The footer links it. scripts/health_check.py now
  reports OK while cnfans.com does not load and warns when it loads again. The Pandabuy alternatives guide got one sentence
  on the same dates.
- 34 new model pages, /best/<model> (functions/_lib/content5.js): puffer-jacket, gilet, windbreaker, bomber-jacket,
  ralph-lauren-jacket, moncler-windbreaker, louis-vuitton-clothing, chrome-hearts-jacket, zip-hoodie, quarter-zip, cardigan,
  lacoste-sweatshirt, cp-company-hoodie, essentials-crewneck-tracksuit, dior-oblique, tracksuit, rick-owens-pants,
  chrome-hearts-jeans, carhartt-pants, jorts, ralph-lauren-shorts, swim-shorts, designer-loafers, hermes-shoes,
  balenciaga-boots, bape-bapesta, travis-scott, nike-nocta, beanie, cap, scarf, wallet-cardholder, designer-belts,
  designer-socks. Chosen from the site searches made 5+ times in 3+ hours in 30 days (puffer 80 searches, belt 117, beanie 49,
  cap 40, quarter zip 18, nocta 30 ...), the views and buy clicks of the finds each would list (puffer jackets 2,182 buy
  clicks in 60 days, zip hoodies 1,287) and Google results with rep threads and spreadsheets in the top 9 (Serper, 23 Nov).
  Built only with 12+ visible finds and 2+ marked as having buyer QC photos; they list only visible finds. Left out: Gucci GG
  clothing and Balenciaga jeans (one find with QC photos each), Margiela numbers and Hermès ties (hardly any rep results), a
  second Golden Goose page (mostly Super-Stars). The Moncler page is named for windbreakers because "moncler jacket rep"
  already finds /best/moncler-puffer. Google's own suggestions leave out rep searches, so they could not be used.
- Linking the model pages: product pages of their finds (the earlier pages keep first claim), brand pages (a cross-brand
  page only on the brands with the most finds on it), category hubs ("Best reps by model", new), the /best index, the
  homepage's "Best reps by model" row (puffer jackets, zip hoodies, tracksuits, quarter-zips) and sitemap-pages.xml. Every
  model page's "More models" list now shows related models (same category or brand) instead of the same first 14.
- Speed: the marketplace facts are kept per hidden set (platFacts), so sitemap-pages.xml builds in about 1 s instead of 3.
- PRODUCT_TPL w97 and w98. URLs: /guides/what-is-a-rep-spreadsheet, /weidian-spreadsheet, /taobao-spreadsheet, /1688-spreadsheet,
  /qc-spreadsheet, /cnfans-spreadsheet, /mycnbox-spreadsheet, /kakobuy-spreadsheet, /oopbuy-spreadsheet,
  /sugargoo-spreadsheet, /lovegobuy-spreadsheet, /tools/qc-checker, /best, the 34 /best pages, /category/*, /brand/* (model
  links), the guides how-to-buy-from-weidian, -taobao and -1688 and pandabuy-alternatives. All of them, and the 66 list
  pages that now redirect, were sent to IndexNow (data/indexnow_2026-11-23.txt, scripts/indexnow.py list).
- Undo: functions/_lib/content5.js out of MODELS in pages.js (the pages go, their URLs 301 to their brand by rescue());
  shipping_lines.js and the shipAbout/freshAbout calls in hubSpec; findShown back to plain lists in platFacts, hubList,
  the agent and QC counts; QC_PLUS back to plusOf(P...); the guide's title, h1, desc and body in content3.js and the stats
  block in renderGuide; CNFANS and the CNFans spec; the QC spec and qcFinderExtra; the footer links in site.js and index.html.
- Left as it is, for the owner: /best/chrome-hearts-jewelry matches "cross" in clothing titles, so 62 of its 75 listings are
  jeans, hoodies and tees. Fixing the pattern leaves about 10 jewellery finds, and the page ranks for "chrome hearts reps"
  (5th UK, 9th US), so it needs a decision. Brand pages still count hidden finds in their titles ("Moncler Reps Spreadsheet
  2026: 367 Finds" where the app shows fewer); the same shown() would fix them, but that changes about 200 ranking titles.

## 23 Nov 2026: the sign-up card waits for the second page view

- What: the sign-up card (the gate in index.html) no longer opens over the first page a visitor sees. It opens on the
  second page view: a later page load (counted in localStorage "pc.views") or a move inside the app on the first page (a
  find opened, another section, a search, the back button). Everything else about it is unchanged (once per browser).
- Why: the owner's call on the open point below. Google counts a card that covers the page on a phone visitor's first view
  as an intrusive pop-up. The first page now stays clean, and the Google sign-in files load later on first visits too.
- Undo: index.html, the end of the "entry auth gate" block: put back `setTimeout(check,700);` in place of the pc.views lines.

## 22 Nov 2026: owner pages for the big searches, product pages, About page

- QC finder: /tools/qc-checker is now the page for "qc finder" searches (title "QC Finder: Real Buyer QC Photos for Any Rep
  Link", h1, description, the name in the tools lists and footers) with a 5-question FAQ and FAQPage data. The pages that
  rank for "qc finder" are tools that find QC photos for a link, which is what this page does. /qc-spreadsheet became the
  "QC Photos Spreadsheet" (title, h1, breadcrumb, links to it) so the two stop competing; neither ranked in the top 30 for
  either search (data/seo_ranks.json). The link converter got a 4-question FAQ for "link converter" searches.
- Rep spreadsheet: the footers on every page now link the homepage as "Rep spreadsheet" (it had only "Finds" and "Home"),
  and the QC photos spreadsheet joined the footer list.
- Product pages: a "What to check in the QC photos" list for each find (the model's own checklist when the find is on a
  best model page, otherwise its category's), a link to its marketplace spreadsheet ("Weidian spreadsheet") in Details,
  and alt text on the extra photo thumbnails. PRODUCT_TPL w86.
- About page: /about (who runs the site under the brand name, how finds are checked, how the site is paid for, contact),
  with AboutPage data, in the sitemap and both footers. The homepage Organization data lists the Discord as well as TikTok.
- Undo: functions/_lib/pages.js (TOOL_SEO, TOOL_FAQ, TOOL_H1, the /qc-spreadsheet spec, CAT_QC and qcCheck, renderAbout,
  the Marketplace line, storeThumbs alt), functions/_lib/site.js (footer, TOOL_LINKS), functions/_middleware.js (the /about
  route), index.html (footer links, sameAs). Commit 18d65837.

## 22 Nov 2026: 86 agent copies of brand pages point at the brand page

- What: 86 of the 170 agent x brand pages (for example /lovegobuy-spreadsheet/adidas, /mycnbox-spreadsheet/moncler) now
  have a canonical to /brand/<brand> and left sitemap-pages.xml. The other 84, which Google visitors buy from, keep their
  own canonical. The 25 agent x style pages (old money, grisch, shoes, QC, budget) are unchanged. List and rule:
  functions/_lib/seo_canon.js.
- Why: each lists the same finds as its brand page with 65 to 67% of the same text. None of the 86 had a buy click from a
  Google visitor in 60 days (data/seo_page_clicks.json) or a Google position in data/seo_ranks.json, while the kept 84 had
  3,250 Google buy clicks between them. The canonical gathers their signals on the brand page.
- URLs: the 86 paths in functions/_lib/seo_canon.js.
- Undo: empty AGENT_BRAND_CANON in functions/_lib/seo_canon.js (pages, canonicals and sitemap go back as they were).
  Commit e6852ce3.

## 22 Nov 2026: pages 2 and up of every list get their own title and description

- What: page N of a brand, category, Weidian/Taobao/1688, old money, new finds or best model list now has a title like
  "Weidian Spreadsheet, Page 124: Nike, Adidas, New Balance" and a description made from its own finds (their brands or
  item types, prices, QC photos). Page 1 and every canonical are unchanged (pages 2+ were already canonical to themselves).
- Why: page N had page 1's title plus ": Page N" and a near copy of its description. Google showed some of them in place of
  page 1 (page 8 of the 1688 spreadsheet for "1688 spreadsheet", page 2 of Acne Studios for "acne studios reps"). The list's
  own words stay first in the title, so the page 2 that ranks for "acne studios reps" keeps them.
- URLs: /brand/<brand>/<n>, /category/<cat>/<n>, /weidian-spreadsheet/<n>, /taobao-spreadsheet/<n>, /1688-spreadsheet/<n>,
  /old-money/<n>, /new/<n>, /best/<model>/<n> (n of 2 and up).
- Undo: functions/_lib/pages.js, hub(): put back `fitTitle(n > 1 ? title.replace(...": Page N") : title)` and the old
  `Page ${n}: ${desc}` description, and drop pageNMeta() and the `key` arguments. Commit a2ac4199.

## 22 Nov 2026: the rep spreadsheet guide says what it is

- What: /guides/what-is-a-rep-spreadsheet is titled "Rep Spreadsheet 2026: What It Is and How to Use One" (was "Rep
  Spreadsheet 2026: 9,000+ Finds, 2,000+ With QC Photos") with a description to match.
- Why: the old title read like the homepage, so the two pages competed for "rep spreadsheet". The guide ranks 3rd for
  "what is a rep spreadsheet" and 4th for "reps spreadsheet 2026", so "Rep Spreadsheet 2026" stays first in the title.
- Undo: functions/_lib/content3.js, GUIDES3["what-is-a-rep-spreadsheet"].title and .desc. Commit a2ac4199.

## 22 Nov 2026: hubs and the homepage load two heavy files later

- What: /data/also.json (related finds, about 500 KB over the wire) loads on the visitor's first tap, key press or scroll,
  when For you is picked, or when a find opens, instead of on every page view once the page is idle (also.js, now
  /also.js?v=2). Google's sign-in script, button and font (about 210 KB) load once the page has finished loading and the
  browser is idle, or at once when the visitor touches the sign-up card, instead of the moment the card opens (index.html).
  The similar finds row is drawn again when the related finds arrive after a find has opened.
- Why: both loaded on every phone visit while the page itself was still loading. Measured with Playwright (Pixel 5
  profile, 150 ms round trip, 1.6 Mbps, 4x CPU slowdown, empty cache, median of 3): the Weidian hub fully loaded in
  10.9 s instead of 11.9 s and moved 2,135 KB instead of 2,637 KB; the homepage 7.3 s instead of 11.0 s and 1,801 KB
  instead of 2,386 KB. The main content showed at about 2.4 s before and after (both files already came after it).
  The first version still started Google's script when the card opened under a resting mouse pointer (pointerover);
  the second commit listens to real touches, clicks, keys and mouse moves only. Commits cdfa2555 and 2d9eabb0.
- Undo: also.js: put back the idle loader at the end of the file (requestIdleCallback after "load") and /also.js?v=1;
  index.html: in the sign-in block call load() in go() for the gate again and drop whenLoaded().

## Decided and left as it is (22 Nov 2026)

- Pages 2 and up stay in sitemap-pages.xml: they now have titles and descriptions of their own, and one of them ranks
  (/brand/acne-studios/2, 5th for "acne studios reps" in the US). Their canonicals point at themselves.
- Product pages keep ItemPage data, not Product with Offer: Google's shopping policies exclude these listings.
- IndexNow: every sitemap URL was sent on 22 Nov 2026 (workflow run "IndexNow", mode all) and the 86 agent pages that now
  point at their brand page were sent separately.
- The sign-up card: decided 23 Nov 2026 (owner), it waits for the second page view (see above).
