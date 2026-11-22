# SEO changes

Every SEO change to the site, newest first: what changed, why, which URLs, and how to undo it. The checks behind the
decisions: data/seo_ranks.json (Google positions and the index check of 22 Nov 2026, scripts/seo_ranks.py) and
data/seo_page_clicks.json (buy clicks per page by visit source, scripts/seo_page_clicks.py).

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
  `Page ${n}: ${desc}` description, and drop pageNMeta() and the `key` arguments.

## 22 Nov 2026: the rep spreadsheet guide says what it is

- What: /guides/what-is-a-rep-spreadsheet is titled "Rep Spreadsheet 2026: What It Is and How to Use One" (was "Rep
  Spreadsheet 2026: 9,000+ Finds, 2,000+ With QC Photos") with a description to match.
- Why: the old title read like the homepage, so the two pages competed for "rep spreadsheet". The guide ranks 3rd for
  "what is a rep spreadsheet" and 4th for "reps spreadsheet 2026", so "Rep Spreadsheet 2026" stays first in the title.
- Undo: functions/_lib/content3.js, GUIDES3["what-is-a-rep-spreadsheet"].title and .desc.

## 22 Nov 2026: hubs and the homepage load two heavy files later

- What: /data/also.json (related finds, about 500 KB over the wire) loads on the visitor's first tap, key press or scroll,
  when For you is picked, or when a find opens, instead of on every page view once the page is idle (also.js, now
  /also.js?v=2). Google's sign-in script, button and font (about 210 KB) load once the page has finished loading and the
  browser is idle, or at once when the visitor touches the sign-up card, instead of the moment the card opens (index.html).
  The similar finds row is drawn again when the related finds arrive after a find has opened.
- Why: both loaded on every phone visit while the page itself was still loading. Measured with Playwright on a Pixel 5
  profile, slow 4G, 4x CPU; numbers in the SEO report.
- Undo: also.js: put back the idle loader at the end of the file (requestIdleCallback after "load") and /also.js?v=1;
  index.html: in the sign-in block call load() in go() for the gate again and drop whenLoaded().
