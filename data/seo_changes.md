# SEO changes

Every SEO change to the site, newest first: what changed, why, which URLs, and how to undo it. The checks behind the
decisions: data/seo_ranks.json (Google positions and the index check of 22 Nov 2026, scripts/seo_ranks.py) and
data/seo_page_clicks.json (buy clicks per page by visit source, scripts/seo_page_clicks.py).

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
- For the owner: the sign-up card that covers the page a moment after a visitor arrives counts as an intrusive pop-up for
  phone visitors from Google. Showing it from the second page view, or not to visitors from search, is the owner's call.
