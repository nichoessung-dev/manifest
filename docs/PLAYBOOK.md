# Spreadsheet Site Playbook

How the puroclassico.com engine works, and how to launch more spreadsheet sites from it.

Checked against the code on 26 Nov 2026 (commit `d09bebcc`). Working rules (shipping a change, version bumps, copy rules,
owner decisions) are in `CLAUDE.md` at the repo root, and the design system is in `DESIGN.md`. This playbook links to
them and does not repeat them.

**Where to start:** decide the basics (section 5), choose the strategy and do the config refactor (3.1), then work
through 3.2 to 3.10. Section 2 is the list of everything that must change; section 4 is what to keep.

1. How the engine works
2. What is specific to Puro Classico
3. Launch checklist for a new site
4. Rules and lessons that made the site good
5. What to decide before building

---

## 1. How the engine works

### The big picture

| Part | Where | What it does |
|---|---|---|
| The app | `index.html` (one big file) | The spreadsheet people use: search, filters, product view, sign-in, saves, 10 languages, 12 currencies. It also holds the whole catalogue. |
| The server | `functions/` (Cloudflare Pages Functions) | Builds the pages Google reads, caches them at the edge, runs small APIs. |
| The database | Supabase | Accounts, saves, comments, view and click counts, reports, partner swaps, photo storage. |
| The bots | `.github/workflows/*.yml` running `scripts/*.py` | Rebuild data on a schedule and commit the results to the repo. |
| Hosting | Cloudflare Pages, project `manifest` | Every push to `main` deploys. There is no build step: the repo is the site. |

One loop drives everything: a bot reads Supabase or the marketplaces, writes a file (for example `data/stats.json` or
`functions/_lib/signals.js`), commits it, Cloudflare deploys, and the site reads the new file. Commits that only save bot
state end with `[skip ci]`, so they do not deploy.

### How a page is served

- **Homepage and hubs** (`/`, `/spreadsheet`, `/brand/x`, `/category/x`, `/<agent>-spreadsheet`): `functions/_middleware.js`
  takes `index.html` and, with `HTMLRewriter`, swaps in the page's title, description, canonical, h1, structured data and
  the first 60 product cards as real HTML. It strips the inline catalogue and app code and links `/catalog.js` (3 parts),
  `/app.js` and `/app.css` instead. The result is kept in the edge cache for an hour. In the browser the app starts with the
  hub's filter already set (`window.PC_PAGE`).
- **Product pages** (`/product/<id>`): built on the server by `renderProduct()` in `functions/_lib/pages.js`, called from
  `functions/product/[id].js`, cached for a day.
- **Pages 2 and up, guides, tools, `/brands`, `/best`, `/about`**: plain server pages from `pages.js`, with the shared
  header and footer from `functions/_lib/site.js` and the stylesheet `ds.css`.
- **Unknown paths** get a real 404, not the app with a 200. Hubs that no longer exist get one 301 to the closest live page
  (`rescue()` in the middleware).

### Where the catalogue lives

The catalogue (15,060 rows, about 10,600 visible) is the JSON block `<script type="application/json" id="pc-catalog">`
inside `index.html`. That block is the source of truth. The rest is generated from it:

| Generated file | Made by | Used by |
|---|---|---|
| `functions/_lib/catalog.js` | `scripts/gen_catalog.py` | Every server page |
| `functions/_lib/rowdays.js` | `scripts/gen_rowdays.py` (from git history) | Sitemap dates |
| `products.json` | `scripts/sync_catalog.py` | Emails, Discord and Telegram drops, IndexNow |
| `/catalog.js?p=0..2` | the middleware, per request | Visitors' browsers |

The Catalog sync workflow runs the three scripts on every push that changes `index.html`. Import scripts
(`scripts/import_rl.py`, `scripts/import_friend.py`) append rows. Repair scripts (`scripts/apply_catalog_ai.py`,
`scripts/prices.py`) make small exact edits. Never edit generated files by hand.

The root `sitemap.xml` is legacy: `sync_catalog.py` still writes it, but the middleware answers `/sitemap.xml` itself with
an index of `/sitemap-pages.xml` and `/sitemap-products.xml` (`sitemapIndex()` in `pages.js`). There is no `_routes.json`,
so the middleware sees every request.

### File map: root

| File | What it does |
|---|---|
| `index.html` | The app and the inline catalogue (table below) |
| `ds.css` | Design system for all server pages and the static pages |
| `pcs.js`, `pcs.css` | Search engine and suggestion panel (app and server pages) |
| `size.js` | Size advice from height, weight and the seller's chart (`data/sizes/NN.json`) |
| `track.js` | Counts Buy clicks, searches and visit time (posts to `/api/click`, `/api/search`, `/api/visit`) |
| `chat.js` | Shopping assistant widget, desktop only (talks to `/api/chat`) |
| `also.js`, `feedback.js` | "People also liked" (`data/also.json`); feedback pop-up for heavy users |
| `stats.html` | `/stats` dashboard (noindex) from `data/dashboard.json` and Supabase |
| `admin.html` | `/admin` owner dashboard; protected calls send `ADMIN_TOKEN` |
| `partner.html`, `partner_swaps.sql` | Partner portal and database for link swaps |
| `how-to-order.html`, `privacy.html`, `terms.html` | Static pages with copies of the server header scripts (`THEME_HEAD`, `PAGE_JS` in `site.js`) |
| `links.html` | TikTok link-in-bio page, with its own copy of the tokens |
| `lab/` | Private, noindex area for trying homepage designs |
| `_headers` | Security headers, CSP and cache times for static files |
| `robots.txt`, `llms.txt` | Crawler rules; a site summary for AI search |
| `manifest.webmanifest`, `favicon.png`, `img/pwa/`, `img/wordmark.webp`, `logo-*.png`, `og.png` | Name, icons, logo, share image |
| `BingSiteAuth.xml`, `4709775d5b756bba3e9c31d8ee85aef1.txt` | Bing ownership; IndexNow key |
| `store-gallery.json` | Extra store photo angles for the app |
| `discord_posted.json`, `month_queue.json` and other root JSON | Bot state |
| `img/` (1.4 GB) | `img/m/` mirrored Supabase photos, `img/rl`, `img/fr`, `img/cut`, `img/white` cut-outs, `img/agents/` logos, `img/cat/` category photos |

### File map: inside `index.html`

Find parts by id or comment; line numbers move.

| Part | Marker | What it does |
|---|---|---|
| Head | top of file | Title, meta, Google verification tag, JSON-LD, theme script, early fetch of `data/*.json` (`window.PC_PRE`) |
| Styles | `<style data-split="css">` blocks | All app CSS, served as `/app.css` |
| Icons | `svg#pc-icons` | One icon set, same names as `ICONS` in `site.js` |
| Header | `.masthead` | Logo, nav, search, sign in, Discord, globe menu |
| Homepage | `section.hero`, `#v9-home` | Hero search, category circles, rows, tools strip |
| Spreadsheet | `#grid`, `#grid-sk` | The grid and its skeleton |
| Product view | `aside#drawer` | The find view (a bottom sheet on phones) |
| Dialogs | `#auth-modal`, `#settings-modal`, `#gate` | Sign-in, preferences, sign-up gate |
| Tool pages | `section.page[hidden]` | In-app tools; homepage only |
| SEO block, footer | `section#seo`, `footer` | Homepage text and FAQ; links |
| Catalogue | `script#pc-catalog` | The source of truth |
| Data layer | the script after it | `AGENT_REFS`, `AGENT_ORDER`, `AGENT_REG`, `AGENTS`, `BRAND_ALIAS`, `loadProducts()` |
| App code | `<script data-split="js">` | Supabase client, translations `T`, currencies `CUR`, baked `VIEW_COUNTS`, `POPULAR`, `PC_BEST`, filters, `swapFirst()`, QC photos, auth (Google `CID`, `HOSTS`), welcome-bonus links `WB_LINKS`, router. Served as `/app.js` |
| Later scripts | comments "v9 home sections", "v8 motion layer", "Welcome flow" | Homepage rows (`railOk()`), motion, welcome tour |

### File map: `functions/`

| File | What it does |
|---|---|
| `_middleware.js` | Router for every request: redirects, 404s, edge cache, hubs as the app, `/spreadsheet`, `/catalog.js`, `/app.js`, `/app.css`, `/search-index.json`, sitemaps, `/discord`, verification file, security headers on Function answers, noindex on previews, the `fb.` partner copy |
| `_lib/site.js` | Server core: catalogue index, view stats, `score()`, `indexable()`, agents (`REFS`, `AGENTS`, `AGENT_ORDER`), `CATS`, brand hubs (`BRAND_MIN`), header, footer, `page()`, `liveCopy()`, `DS_VER`, `DISCORD_INVITE` |
| `_lib/pages.js` | Every server page and sitemap; `hubSpec()`; `PRODUCT_TPL` |
| `_lib/content.js` to `content5.js` | Editorial copy: category, agent and brand intros, model pages, guides |
| `_lib/tools9.js`, `weights.js` | Shipping calculator, size estimator, parcel tracker; item weights |
| `_lib/subcats.js` | Subcategories (T-shirts, Hoodies ...): the chips on the category hubs and above All Finds, the `/category/<cat>/<sub>` hubs. One table on top of `weights.js` item types, copied into `index.html` by `sync_weights.py` |
| `_lib/sp_hero.js`, `photo_tiles.js`, `seo_canon.js` | `/spreadsheet` hero; dark-tile rules; canonical exceptions |
| `_lib/search_index.js`, `search_vocab.js`, `views.js`, `reported.js`, `also.js`, `reddit_kb.js`, `shipping_lines.js` | Search index; AI search words; page view counter; hidden finds; related finds; chat tips; agent shipping prices |
| Generated `_lib` files | `catalog.js`, `rowdays.js`, `counts.js`, `signals.js`, `link_swaps.js`, `price_checks.js`, `photo_quality.js`, `store_gallery.js` |
| `api/*` | `chat`, `ai-search`, `image-search`, `qc`, `qc-check`, `link`, `img` (photo proxy), `click`, `search`, `visit`, `report`, `feedback`, `geo`, `live-sample`, `hio-check` (a trial) |
| `go/[agent].js` | Counted MyCNBox redirect with the codes (`CODES`, `REFER_ID`) |
| `r/[code].js`, `unsubscribe.js`, `e/[[path]].js` | Member referral cookie; one-click unsubscribe; email click and open tracking (Email v2, new) |

### File map: `scripts/` by job

Every script explains itself in its first lines.

| Job | Scripts |
|---|---|
| Catalogue | `gen_catalog.py`, `sync_catalog.py`, `gen_rowdays.py`, `clean_catalog.py`, `catalog_common.py`, `import_*.py`, `match_friend.py`, `catalog_ai.py`, `apply_catalog_ai.py`, `claude_enrich.py`, `sync_weights.py` (item types and subcategories into `index.html`) |
| Prices, links, sizes | `prices.py`, `price_rule.py`, `check_links.py`, `listing_details.py`, `bake_sizes.py` |
| Photos | `clean_photos.py`, `mirror_photos.py`, `photo_quality.py`, `photo_hide.py`, `photo_fix.py`, `seller_photos.py`, `store_photos_*.py`, `photo_white.py`, `photo_edge*.py`, `photo_cut_*.py`, `rate_photos.py` |
| QC photos | `qc_bank.py`, `apply_qc_counts.py`, `qc_best.py`, `qc_ai.py`, `qc_badge.py`, `qc_rebadge.py`, `oopbuy_qc.py` |
| Stats and SEO | `bake_stats.py`, `bake_also.py`, `bake_counts.py`, `bake_reports.py`, `gen_signals.py`, `seo_ranks.py`, `seo_page_clicks.py`, `indexnow.py`, `health_check.py` |
| Partner, email | `bake_swaps.py`, `friend_swaps.py`; `newsletter.py`, `mail_links.py` |
| Social | `discord_drops.py`, `telegram_drops.py`, `make_short.py`, `post_short.py`, `make_finds.py`, `finds_plan.py`, `month_*.py`, `make_rug.py`, `pins.py` |
| SQL, tests | `buy_clicks.sql`, `link_reports.sql`, `site_visits.sql`, `email_v2.sql`; `test_*.py`, `test_*.mjs` |

### Workflows that keep the site alive

| Workflow | When (UTC) | Does |
|---|---|---|
| `catalog-sync.yml` | on push of `index.html` | Regenerates the catalogue files |
| `stats.yml` | every 6 h | `data/stats.json`, `data/dashboard.json`, `data/also.json`, `signals.js` |
| `reports.yml` | every 2 h | Hidden finds (`data/reported.json`), counts |
| `swaps.yml` | every 15 min | Partner swaps |
| `prices.yml`, `link-check.yml` | twice a day; Mondays | Weidian prices; dead listings (`data/link_health.json`) |
| `qc-bank.yml`, `mirror-photos.yml` | nightly; hourly | QC photos into storage; photo copies into `img/m/` |
| `welcome.yml`, `newsletter.yml` | every 15 min; daily | Emails |
| `health.yml`, `indexnow.yml` | daily | Health check (a red run emails the owner); IndexNow pings |
| `discord-drops.yml`, `telegram-drops.yml` | daily | New finds to the community |

`finds.yml`, `shorts.yml`, `month-*.yml`, `pins.yml`, `rug-*.yml` and similar are the social media factory (Postiz,
ElevenLabs, image models); a new site needs none of them at launch. A few more run on a schedule to improve data
(`enrich.yml`, `qc-best.yml`, `seller-photos.yml`, `reddit-kb.yml`, the friend jobs). The photo jobs run by hand.

### The `data/` files the live site reads

| File | Written by | Read by |
|---|---|---|
| `stats.json`, `dashboard.json` | `bake_stats.py` | Ranking everywhere; `/stats`, trending searches |
| `link_health.json` | `check_links.py` | Dead listings, "Links checked" dates |
| `reported.json` | `bake_reports.py` | Hidden finds on every list |
| `link_swaps.json`, `photo_quality.json`, `qc_best.json` | their scripts | The app |
| `also.json` | `bake_also.py` | Related finds (app and product pages) |
| `qc_bank.json`, `qc_ai.json` | `qc_bank.py`, `qc_ai.py` | QC photos and AI QC notes |
| `sizes/NN.json`, `reddit_kb.json` | `bake_sizes.py`, `reddit_kb.py` | Size advice; chat tips |

The other files in `data/` are working records of the photo, price and SEO jobs.

---

## 2. What is specific to Puro Classico

All of this must change for a new site. Today most values are typed by hand in many files, which is the main reason
for the refactor in section 3.

| What | Where | Search for |
|---|---|---|
| Brand name | About 60 files: titles in `pages.js`, header and footer in `site.js`, `content*.js`, `index.html`, static pages, `newsletter.py`, `llms.txt`, `manifest.webmanifest` | `Puro Classico`, `puroclassico` |
| Domain | `SITE` in `site.js` and most scripts; canonical and og tags in `index.html` and static pages; `robots.txt`; `llms.txt`; several places in `_middleware.js`; `HOME`, `OWN`, `ALLOW` in `e/[[path]].js`; host checks in `thumbOf()`, `cdnOf()` (`index.html`), `pcs.js`, `track.js`, `chat.js` | `www.puroclassico.com`, `puroclassico\.com` |
| Pages address | `PAGES_DEV` in `_middleware.js`; `ORIGIN` in `api/report.js`, `search.js`, `visit.js`, `feedback.js`; `views.js`; `HOSTS` in `index.html` | `manifest-bq9` |
| Logo, icons | `img/wordmark.webp` (header mask), `logo-mark.png`, `logo-wordmark.png`, `favicon.png`, `img/pwa/*`, `og.png`, `media/links-avatar.png`, email logo `products/email/logo.png` in storage, QR badge `scripts/qc_badge_tpl.png` | |
| Colours | `:root` tokens in `ds.css`; the app's copy in `index.html`; copies in `stats.html`, `admin.html`, `partner.html`, `links.html`; `theme-color` | `--bg`, `--ink`, `--fill` |
| Copy | Hero and `section#seo` in `index.html`, translations `T`, `content*.js`, `CATS` headings, legal pages, emails, the chat prompt in `api/chat.js` | |
| Agent codes | `index.html`: `AFFILIATE_REF`, `AGENT_REFS`, `AGENT_REG`, `WB_LINKS`, sign-up links. `site.js`: `REFS`, `MYCNBOX_INVITE`, `AGENT_SWAP_JS`. `pages.js`: `AGENT_JS`, agent fact tables. `go/[agent].js`: `CODES`, `REFER_ID`. `_middleware.js`: `FB_INVITE`, `FB_RE`. Copy in `content.js`, `content2.js`, `content3.js`, `how-to-order.html`, `links.html`, `privacy.html`, `terms.html`, `newsletter.py` | each code, `inviteCode=`, `referId=` |
| Agent list | `AGENT_ORDER` and `AGENTS` (index.html, site.js), the `A` list in `pages.js`, `AG` in `track.js`, `AGENTS` in `api/click.js`, `AGENT_NAMES` in `stats.html`, `ALLOW` in `e/[[path]].js`, `img/agents/` | agent keys |
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY` and the preconnect in `index.html`; `SB`, `KEY` in `stats.html`, `partner.html`; `SUPA` in every API function and most scripts; `PREFIX` in `gen_catalog.py` (three storage hosts today); `SG_PUB` in `pages.js`; photo hosts in `api/img.js`; the session key in `AUTH_NAME_JS` (`site.js`) and copies in the static pages, `size.js`, `track.js` | `uptpghuduqjqmrxwatbm`, `sb_publishable_` |
| Google sign-in | `CID` and the allowed hosts `HOSTS` in `index.html` | `apps.googleusercontent.com` |
| Verification | Google meta tag in `index.html`; `VERIFY` file route in `_middleware.js`; `BingSiteAuth.xml`; IndexNow key file and `KEY` in `scripts/indexnow.py` | `google-site-verification` |
| Discord, socials | `DISCORD_INVITE` in `site.js` (the only real place; `/discord` redirects to it); `sameAs` in `index.html` and `renderAbout()`; TikTok handle in `finds_plan.py` | `discord.gg`, `tiktok.com/@` |
| Sitemaps, robots | Built from `SITE`; the Sitemap line in `robots.txt` | |
| Analytics | Cloudflare Web Analytics (dashboard switch, allowed in the CSP); first-party counts in Supabase; live viewers from open tabs plus a cron Worker outside the repo (`puroclassico-live-sampler`) | |
| Email sender | Secrets `PLUNK_FROM`, `PLUNK_FROM_NAME`; defaults and the Brevo sender in `newsletter.py` | `news@` |
| Partner copy | `fb.` rules in `_middleware.js`, `go/[agent].js`, `newsletter.py`; `logo-fb-wordmark.png` | `AADAXV` |
| Repo, project | `REPO` in `scripts/health_check.py`; project `manifest` in `scripts/wait_live.sh`; the gh command in `CLAUDE.md` | |
| Niche data | `CATS`, `BRAND_ALIAS`, `FOOTER_BRANDS`, `BRAND_ALLOW`, `GUIDE_LINKS` (`site.js`); `CAT_QC`, `STYLE_HUBS`, `AGENT_STYLES` (`pages.js`); `OLD_MONEY` (`content.js`); `weights.js`; `subcats.js`; `PCS_ALIAS` (`pcs.js`); `POP_BRANDS` and category tiles (`index.html`); the category list in about 20 files | `Outerwear` |

### Silent failures

These break without any error:

- A new domain missing from the `ORIGIN` regexes: the APIs answer OK and store nothing.
- A new domain missing from `HOSTS` in `index.html`: the Google sign-in button never shows.
- A new domain not matched by the host checks in `thumbOf()`, `cdnOf()` and `pcs.js`: every photo loads full size,
  and the site gets slow.
- An agent missing from `AG` in `track.js` or `AGENTS` in `api/click.js`: its clicks are never counted. This happened
  to Boonbuy and was fixed in commit `15d178c5`.
- The old project ref in `AUTH_NAME_JS`: server pages never show the signed-in name.
- Supabase Auth without the new domain in Site URL and Redirect URLs: sign-in links do not come back to the site.
- Different `UNSUB_SECRET` values in GitHub and Cloudflare: unsubscribe and email links fail.
- A new bot state file not added to `PRIVATE` in the middleware: it is public (`month_queue.json` and
  `slides_used.json` are not on that list today).

### Secrets and variables

**Cloudflare Pages** (Settings, Variables and Secrets, for Production and Preview): `SUPABASE_SERVICE_KEY` (all
counting, reports, partner data), `ANTHROPIC_API_KEY` (chat, photo search, AI QC notes), `ADMIN_TOKEN`, `UNSUB_SECRET`,
`QUALITLY_KEY` (QC photos), `REPORT_SALT`, optional `CHAT_MODEL`, `IMAGE_SEARCH_MODEL`, `QC_CHECK_MODEL`,
`HIOBUY_API_KEY`. Binding: `AI` (Workers AI, for `/api/ai-search`).

**GitHub Actions secrets** (every name the workflows use):

| Group | Secrets |
|---|---|
| Core | `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` (automatic) |
| Email | `PLUNK_API_KEY`, `PLUNK_FROM`, `PLUNK_FROM_NAME`, `UNSUB_SECRET`, `BREVO_API_KEY` (old provider) |
| QC photos | `QUALITLY_KEY`, `OOPBUY_APP_ID`, `OOPBUY_AES_KEY`, `OOPBUY_SIGN_SECRET` |
| Community | `DISCORD_WEBHOOK`, `DROPS_ROLE_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `MYCNBOX_WEBHOOK` |
| Search, images | `SERPER_API_KEY`, `BRAVE_API_KEY` (the key check also tries `BRAVE`, `BRAVE_KEY`, `BRAVE_SEARCH_API_KEY`), `OPENAI_API_KEY`, `GEMINI_API_KEY` |
| Social video | `POSTIZ_API_KEY`, `ELEVENLABS_API_KEY`, `HEDRA_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY` |

**GitHub variables** (switches): `FINDS_LIVE`, `FINDS_PAUSED`, `SLIDES_LIVE`, `SHORTS_LIVE`, `SHORTS_VOICE`,
`MONTH_LIVE`, `MONTH_DAYS`, `PINTEREST_BOARD`, `TIKTOK_BRANDED`, `SEARCH_PROVIDER`, `SELLER_PHOTOS_AUTO_APPLY`.

### Leftover check

After rebranding, none of these may appear outside `data/` and `img/`: `puroclassico`, `Puro Classico`,
`uptpghuduqjqmrxwatbm`, `manifest-bq9`, `LHYDVW`, `AACPYA`, `AADAXV`, `FUUsSCGqQf`, `googleaea131de20fbf72e`,
`4709775d5b756bba3e9c31d8ee85aef1`, and every code in `AGENT_REFS`. Check with `grep -rIl -e <string> .`

---

## 3. Launch checklist for a new site

### 3.1 Choose the strategy first

| | A. Copy the repo | B. One engine, many sites | C. One deployment, many domains |
|---|---|---|---|
| How | Copy, then search and replace | One engine repo, one small repo per site, settings in one config file | The middleware picks settings by host name, as `fb.puroclassico.com` does today |
| First site | Fastest | Slower: one refactor first | Fast, but only for the same catalogue |
| Later fixes | Repeated by hand in every copy | Made once, merged into every site | Made once |
| Main risk | Copies drift; old codes left behind | The refactor itself | All sites share one file limit, one build quota, one outage and one catalogue |
| Best for | One extra site, short term | Three or more sites with their own catalogues | Co-branded partner or influencer copies |

**Recommendation: B**, and keep C for co-branded copies of the same catalogue. One repo per site fits this engine:
the bots commit each site's data, and Cloudflare caps files per deployment. A branch per site does not work, because
GitHub runs scheduled workflows only on the default branch, so the bots would never update the other sites. If a
second site is needed within days, start with A, but do the refactor before site three.

**The refactor that makes B possible.** Do it in the engine first with no visible change, and compare the HTML of about
30 key pages on a preview deployment before and after.

1. **One config file** (`site.json`): name, domain, pages.dev name, logo paths, colours, Discord and socials,
   Supabase URL, ref and publishable key, Google client ID, verification codes, IndexNow key, email sender, default
   agent and currency, categories, feature switches (chat, QC tools, partner swaps).
2. **One agent table** (`agents.json`): key, name, domain, logo, item link pattern, sign-up link, codes, order. Today
   the 17 agents are typed into more than a dozen lists across seven files.
3. **Generators** in the style the repo already uses (`sync_weights.py` writes a block between markers): one script
   writes `functions/_lib/site_config.js`, stamps a config block into `index.html` and the static pages, and a
   `scripts/site_config.py` module feeds the Python scripts.
4. **The catalogue out of `index.html`** into `data/catalog.json`, so the engine file holds no site data.
   `catalogJs()` in the middleware, `loadProducts()` and every script that reads the `pc-catalog` tag change with it.
   Do the same for the baked `VIEW_COUNTS`, `POPULAR` and `PC_BEST`.
5. **Niche content in its own folder**: `content*.js`, `CATS`, `CAT_QC`, `weights.js`, brand lists.
6. **The leftover check in CI**, failing when another site's strings appear.
7. **The full database schema in the engine** (see 3.3).

After that, a new site is a config file, an agent table, content, a catalogue and accounts.

### 3.2 Repo

- [ ] Create the site repo from the engine. Leave out `img/m`, `img/rl`, `img/fr`, `img/cut`, `img/white`, `data/*`,
      root state files, `lab/`, `media/` and the git history (the current `.git` is 3.4 GB).
- [ ] Public or private: Actions minutes are free on public repos; private repos have a monthly quota, and these jobs
      run every 10 to 15 minutes.
- [ ] Disable the social media workflows until you need them.
- [ ] GitHub turns off schedules in a public repo after 60 days without activity. A quiet new site can stop updating.

### 3.3 Supabase

- [ ] New project. URL and publishable key go in the config; the service key only in secrets.
- [ ] Tables and functions. In the repo: `scripts/buy_clicks.sql`, `link_reports.sql`, `site_visits.sql`,
      `email_v2.sql`, `partner_swaps.sql`, and `chat_logs` in a comment in `functions/api/chat.js`. **Not in the repo**
      (comments point to a missing `OWNER_SQL.sql` and `SQL.md`): `profiles`, `favorites`, `comments`, `product_views`,
      `product_page_views`, `search_log`, `link_clicks`, `product_reports`, and the functions `star_counts`,
      `my_referrals`, `claim_referral_code`, `bump_product_view`, `bump_referral_click`, `site_stats`,
      `purge_search_log`, `purge_product_page_views`. Export the schema once from the current project (Supabase
      CLI: `supabase db dump -f schema.sql`, which dumps the schema by default) and keep it in the engine.
- [ ] Row Level Security on every table. The publishable key is public by design; RLS is the protection.
- [ ] Storage: a public bucket `products` (folders `pc`, `pc2`, `qc`, `qc-live`, `store`, `store2`, `email`, `stats`);
      the private `feedback` bucket is made on first use.
- [ ] Auth: Site URL and Redirect URLs on the new domain; email sign-in; Google with a new OAuth client (its ID is
      `CID`).

### 3.4 Cloudflare

- [ ] New Pages project from the repo: framework None, build command empty, output `/` (`README.md`).
- [ ] Custom domain on `www.`, plus a Cloudflare rule that redirects the bare domain to `www.` (the code only
      redirects the pages.dev address).
- [ ] The environment variables and the `AI` binding from section 2.
- [ ] Image transformations on for the domain: thumbnails use `/cdn-cgi/image/width=400,...` (`THUMB` in `site.js`,
      `thumbOf()` in `index.html`). Without them server cards fall back to full-size photos.
- [ ] Web Analytics on. Optional: a cron Worker that POSTs to `/api/live-sample` every 5 minutes.
- [ ] Builds: this repo made 40 to 140 deploying commits a day from 19 to 26 Nov 2026. Check your plan's monthly
      build limit, and keep `[skip ci]` on commits that only change state.

### 3.5 The first catalogue

Each row of the catalogue block:

| Field | Example | Notes |
|---|---|---|
| `id` | `"760438413422"` | Marketplace item id, as text |
| `platform` | `"taobao"` | `weidian`, `taobao` or `1688` |
| `itemId` | | Only when the buy link needs another id |
| `title`, `brand` | `"Ralph Lauren Crewneck Navy"`, `"Ralph Lauren"` | Brand, item, colour; spellings merged by `BRAND_ALIAS` |
| `cat` | `"Tops"` | A key of `CATS` |
| `price`, `usd` | `240`, `33.6` | Yuan, and yuan times 0.14 |
| `img` | photo URL | One clean photo of the item alone |
| `variants` | `[["Navy Blue", 240]]` | Options with prices |
| `qc` | `306` | 0 without buyer QC photos; 1, or a count, with them |
| `g` | `"m"` | `m` or `w` |
| `seller`, `rating`, `views` | | `rating` and `views` stay 0 (views come from `stats.json`) |

- [ ] Write an import script for your source, modelled on `scripts/import_rl.py`: append only, skip ids already there,
      stop before the file limit.
- [ ] Run `scripts/clean_catalog.py`, then push; Catalog sync does the rest.
- [ ] Start with a few hundred good finds. A brand gets a hub from 20 finds (`BRAND_MIN`). A product page is indexable
      only with QC photos, a "best" pick or real views (`indexable()` in `site.js`), so a new site ranks through its hubs
      first.
- [ ] The link check and price check read Weidian only (Taobao and 1688 block them). A source outside Weidian, Taobao
      and 1688 needs new agent links, QC photos, link and price checks.

### 3.6 Photos

- [ ] Keep originals in Supabase storage. Visitors get them through `/api/img` (edge cached), and `mirror_photos.py`
      copies them into `img/m/` while the repo stays under 19,000 files (Cloudflare allows 20,000 per deployment).
- [ ] Make every main photo a centred cut-out with `clean_photos.py` (no drawing, a fidelity check). Cut-outs get the
      dark tile in dark mode (`photo_tiles.js`).
- [ ] Hide finds with bad photos (`photo_hide.py`) rather than show them.

### 3.7 SEO pages

- [ ] Rewrite `content*.js` for the niche: category, agent and brand intros, guides, model pages. Every agent fact
      carries the day it was read.
- [ ] Update `CATS`, `FOOTER_BRANDS`, `GUIDE_LINKS`, `FOOTER_GUIDES`, `STYLE_HUBS`, the agent page lists
      (`AGENT_INTRO`, `AGENT_BRAND_AGENTS`) and the agent page regexes in `_middleware.js` and `pages.js`.
- [ ] Write `llms.txt`, `robots.txt`, `/about` and `/guides/how-we-check` (who runs the site, how finds are checked).
- [ ] Verify the domain in Google Search Console and Bing, submit `/sitemap.xml`, make a new IndexNow key.

### 3.8 Emails

- [ ] A Plunk account with the sending domain verified; secrets `PLUNK_API_KEY`, `PLUNK_FROM`, `PLUNK_FROM_NAME`,
      `UNSUB_SECRET` (the same value in Cloudflare).
- [ ] New copy and logo in `scripts/newsletter.py`; try the test mode of `welcome.yml` first.
- [ ] Check one-click unsubscribe (`functions/unsubscribe.js`).
- [ ] Name the real email provider in `privacy.html` (it still says Brevo).

### 3.9 Stats

- [ ] Run the Stats workflow by hand once. Until `data/stats.json` exists, hubs have no server cards and pages are
      cached only briefly. `/stats` fills as the tables get rows.

### 3.10 Before you announce

- [ ] The leftover check passes.
- [ ] Each agent's Buy button opens the right item with your code; sign-up links carry your codes; `/go/mycnbox`
      redirects (it is the only agent `/go/` serves).
- [ ] A test Buy click lands in `buy_clicks` and a test search in `search_log`.
- [ ] Email and Google sign-in work on the new domain; a saved find is still there after a reload.
- [ ] Photos load as resized copies (`/cdn-cgi/image/...` in the network tab), not full size.
- [ ] A product, brand, category and agent page each answer 200, are under 2 MB, have cards in the HTML and the right
      title and canonical. An unknown path answers 404.
- [ ] `/sitemap.xml`, `/robots.txt`, the verification files and the IndexNow key answer on the new domain; the
      pages.dev address redirects; previews say noindex.
- [ ] Light and dark mode, a 360 px phone, a slow connection.
- [ ] The welcome email arrives and unsubscribe works.
- [ ] `scripts/health_check.py` adapted (pages, Discord invite, sitemaps, unsubscribe, data freshness, buy clicks,
      welcome emails) and running daily.

---

## 4. Rules and lessons that made the site good

Details are in `DESIGN.md` and `CLAUDE.md`. Here is why each one matters for a new site.

### Design

- The photo does the talking; everything else is quiet: neutral tokens, hairline borders, one solid primary button per
  view, every colour from a token, tabular numbers.
- 44 px touch targets, 16 px text in inputs, a skip link, an `aria-label` on every nav, focus never hidden under a bar.
- Motion: only transform and opacity, nothing animates on load, hover effects for mice only, all off with reduced motion.
- The v7 token table at the top of `DESIGN.md` is older than `ds.css` v9 (Inter, a neutral palette). Treat `:root` in
  `ds.css` as the live tokens.

### Calm loading

- Nothing jumps. The server sends real cards, and the app takes them over without reloading photos or reshuffling.
- Every photo has a skeleton tile of its own size and fades in once loaded. The first frame waits until the grid is
  parsed (`<link rel="expect">`).
- Data that orders a list (stats, link check, swaps) is fetched from the head (`window.PC_PRE`), so the grid is drawn
  once.

### Dark-mode photo tiles

- Light mode: photos on white, blended with multiply. Dark mode: a transparent cut-out sits on `#262626`; any other
  photo keeps a light tile. One test on both sides, `isCut()` in `site.js` and `pcCut()` in `index.html`, with the rules
  in `photo_tiles.js`. Change them together.

### SEO structure

- **Hubs carry the site**: brand, category, agent, agent x brand, marketplace, style, QC and model ("best") pages, plus
  guides and tools. Page 1 is the app with server cards; pages 2 and up are server pages with their own titles.
- **Product pages** are indexable only with QC photos, a curated pick or real demand, and only one listing per group of
  same-named finds. The rest are `noindex,follow`.
- **Canonicals** point to the page itself on `www.`; agent x brand pages without Google buyers point to the brand page
  (`seo_canon.js`). One 301 hop fixes slashes and capitals, dead hubs 301 to the closest live page, and unknown paths
  are real 404s.
- **Sitemaps**: an index with pages and products; `lastmod` only from a real date, never "today".
- **Structured data**: Organization, WebSite, CollectionPage and FAQPage on the homepage; CollectionPage,
  BreadcrumbList and FAQPage on hubs; ItemPage and BreadcrumbList on products; Article on guides; WebApplication on
  tools. No Product or Offer markup on finds.
- **Live numbers**: counts in copy come from `counts.js` and `liveCopy()`. Never type a count into new copy.
- **Titles** stay near 60 characters; the site name is dropped first (`fitTitle()`).
- **IndexNow** pings only pages that really changed.
- **Log every SEO change** in `data/seo_changes.md`: what, why, which URLs, how to undo.

### Speed

- Google reads only the first 2 MB of a file, so the catalogue goes out in 3 parts and the app code as `/app.js` and
  `/app.css`, cached under `index.html`'s ETag.
- Hubs and product pages sit in the edge cache. The key holds the catalogue date (`BUILT`), `PRODUCT_TPL`, the swap
  version and the ETag, so a deploy never serves an old copy.
- 400 px thumbnails through Cloudflare, the first photos eager and the rest lazy, photos mirrored into the site so
  visitors never wait on Supabase.
- The Early Hints `link` header names only files whose address never changes, because Pages replays an old one.

### Version bumps

The caches are keyed on version numbers, so a change without a bump can stay invisible: raise `PRODUCT_TPL` in
`pages.js` for HTML, and `DS_VER` in `site.js` plus the `?v=` in the static pages for `ds.css`. Exact rules: "Shipping
a change" in `CLAUDE.md`.

### Partner-first ordering

- Revenue is agent commission plus the partner's store. A partner swap sends a find's Buy buttons to the partner's
  listing (`partner.html`, `bake_swaps.py`).
- On the server swapped finds outrank everything (`score()` in `site.js`). In the app, plain browsing is about 97%
  partner finds (`swapFirst()`), while search, brands and categories show everything, partner finds first. Emails show
  almost only partner finds. Agents are listed by what they earn (`AGENT_ORDER`).

### Copy

- Short, plain and factual, with dates on facts and affiliate links labelled. No em or en dashes. Avoid "replica",
  "fake" and "1:1" (rules in `CLAUDE.md`).
- `index.html` still breaks these rules in places: "replica" in the meta keywords and an FAQ answer, and 35 en dashes in
  old tutorial copy. Do not carry those into a new site.

### Privacy

- Counts are aggregates: no IP addresses and no user ids in the click, search and visit tables, and bots and prefetches
  are skipped. Keep `privacy.html` true to what the site does.

### How deploys are verified

- Push, wait for the deploy (`scripts/wait_live.sh`), look at the live page with Playwright, read headers such as
  `x-ssr-cache`, and let `health_check.py` run daily. Steps: `CLAUDE.md`.
- Each of these broke once without anyone noticing: an expired Discord invite, the QC quota running out mid-month,
  emails failing for days while runs stayed green, pages over 2 MB, an agent's clicks not counted, bot pushes racing
  (now retried 5 times), QC records lost when the repo was restarted from an old copy. Make every failure loud.
- Try big design changes in `/lab` first.

---

## 5. What to decide before building

| Decision | Ask | Why it matters here |
|---|---|---|
| Niche | What do people search for? Do they already use spreadsheets? | Hubs need volume: 20+ finds per brand, hundreds per category |
| Audience | Countries, languages, phone or computer, where they come from | Currency, language, shipping lines, social channels |
| Agents | Which agents serve them, with affiliate codes and item links that open for signed-out visitors? | The agent table, agent pages, revenue |
| Data source | Your own curation, a partner store, a list shared with written permission? | Import script, photos, QC photos, checks |
| Revenue | Agent commission, a partner store, or both? Who comes first? | Partner-first rules, emails, agent order |
| Budget | AI and API costs, QC quota, owner hours per week | Photo jobs, QC bank, video jobs |

### Legal and platform risks

- **Trademarks and counterfeits.** Many finds copy branded designs. In many countries selling or promoting
  counterfeit goods is illegal, and earning commission on them can count as promoting. Brands send takedowns, sue and
  have domains seized. Wording rules change the tone, not the legal position. Unbranded goods, Chinese brands and
  original designs carry far less risk. Get legal advice for each target country.
- **Agents close.** Pandabuy stopped in 2024, Mulebuy shut down, and CNFans stopped loading (`/cnfans-spreadsheet`).
  Support several agents and keep the link converter.
- **Service terms.** Cloudflare, Supabase, GitHub, Plunk and the AI providers have terms that can cover this content.
  A ban takes down the site, the data or the bots, so keep backups of the database and photos elsewhere.
- **Search and social.** Google can drop pages; TikTok, Discord and Reddit ban accounts. Spread traffic across
  channels and own the email list.
- **Affiliate programmes** change or end. Read each agent's terms.
- **Privacy law.** Accounts and emails bring GDPR duties for EU visitors: a true privacy page, working unsubscribe,
  deletion on request.
- **Photos and lists** only with permission.

### Go or no-go

- [ ] A clear audience with real search demand
- [ ] At least three working agents with your codes
- [ ] A data source you may use, with a few hundred finds ready
- [ ] A legal check for the target countries
- [ ] Accounts ready: domain, Cloudflare, Supabase, GitHub, email provider
- [ ] Owner time for a weekly check of `/stats`, the health check and Search Console
