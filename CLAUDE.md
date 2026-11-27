# Working on puroclassico.com

Read this first. It is the memory of how this site is built and of the owner's standing rules. The full architecture
and the guide to launching more sites from this engine are in `docs/PLAYBOOK.md`; the design system is in `DESIGN.md`.

## What this is
- A rep finds spreadsheet: about 10,600 fashion finds from Weidian, Taobao and 1688. Every find opens on 17 shopping
  agents through the site's invite links. Revenue: agent referral commissions and a partner store's sales.
- Static app `index.html` (one large file) on Cloudflare Pages, project `manifest`, live at https://www.puroclassico.com.
- `functions/`: Pages Functions. `functions/_middleware.js` renders and edge-caches the server pages (product pages,
  brand and category hubs, agent spreadsheets, guides, tools, sitemaps) with HTMLRewriter. `functions/api/*` are the
  APIs, `functions/go/*` the counted agent redirects.
- Supabase: auth and data. GitHub Actions (`.github/workflows/`) run the Python jobs in `scripts/`.

## How the owner wants answers
- Short. Most important thing first. Steps, not essays. Plain English (English is the owner's second language).
- Never use em dashes or en dashes, anywhere: chat, site copy, emails, code comments, commit messages.
- If you can do it, do it. Ask with clickable questions (AskUserQuestion) when a choice is the owner's.
- Any English text that goes to outside people (DMs, partner emails) is a draft the owner reviews before sending.
- Never put the owner's personal details in requests to outside services or in this public repository.

## Shipping a change
1. Work on `main` and deploy directly (this project does not use pull requests).
2. Push with the retry loop:
   `ok=0; for i in 1 2 3 4 5; do if git pull -q --rebase origin main && git push -q origin HEAD:main; then ok=1; break; fi; sleep $((i*3)); done`
3. Wait for the deploy: `bash scripts/wait_live.sh <commit>` (prints `live in <hash>`).
4. Check the live site with Playwright (Chromium is preinstalled; `require('playwright')`). Look at a screenshot
   before saying something is fixed.
5. Version bumps, every time they apply:
   - `PRODUCT_TPL` in `functions/_lib/pages.js` after any change to `index.html` or server-rendered HTML. It keys the
     edge cache. Add a short dated entry at the front of its comment.
   - `DS_VER` in `functions/_lib/site.js` after a `ds.css` change, plus the `?v=` in `how-to-order.html`,
     `privacy.html` and `terms.html`.
   - The `?v=` on `size.js`, `chat.js`, `track.js`, the `pcs.js` hash and `favicon.png` when those files change.
6. Never hand-edit the generated catalogue. Change the scripts and regenerate (`scripts/gen_catalog.py`,
   `scripts/sync_catalog.py`).

## Session limits to know
- GitHub: REST only (GraphQL is blocked). Run a workflow with
  `gh api -X POST repos/nichoessung-dev/manifest/actions/workflows/<file>/dispatches -f ref=main`.
  Secrets cannot be read or set from a session: the owner sets them in GitHub, Settings, Secrets and variables, Actions.
- Supabase: no management API from sessions. Database changes go in a `.sql` file in `scripts/`; the owner runs it in
  the Supabase SQL editor.
- Helper agents cannot push. They prepare a patch (`git format-patch -1 --stdout > file.patch`); the main session
  applies it with `git apply --3way`, bumps versions, pushes and verifies. Never commit another agent's unfinished
  work. `.claude/` is local only.

## Copy rules
- Avoid the words "replica", "fake" and "1:1" in site copy, emails and subjects.
- Sentence case. Short, calm copy.
- English is the default language and USD the default currency. Each changes only when the visitor picks one.

## Owner decisions (do not change unless the owner asks)
- Keep the current homepage layout. Under the rows, the tools are one slim strip of links.
- Sign-up checkbox and affiliate or partner wording: unchanged.
- Welcome tour: no agent sign-up step; MyCNBox is preselected in the agent step.
- The chat assistant shows on desktop only.
- Every list shows all its finds with partner finds first. Plain browsing (no filters) starts with the partner mix
  (about 3% other finds) and then continues with every other find, so the count is the whole sheet.
- Agent order starts: mycnbox, kakobuy, oopbuy, litbuy, boonbuy, hipobuy, joyagoo (`AGENT_ORDER` in `index.html` and
  `functions/_lib/site.js`).
- Size advice without a size chart: the member's usual size; one up only when the listing says Asian sizing.
- "View more" on homepage rows stays on the page: it picks that category and glides down to All Finds.
- Homepage rows show only top finds (clean cut-out photo, sane price, QC photos, real views), at most once per model.
- Favicon and app icons: the real logo (`logo-mark.png`, the script name in a ring), navy on a white disc.
- "Your style" picker: photo tiles (two per row, three finds fanned); Streetwear's middle photo is the Air Jordan 4 Black.
- Email: saved-find alerts only for partner finds (`ALERTS_PARTNER_ONLY` stays 1). Members who signed up while email
  was down get one "sorry this is late" welcome (`mailer.py backfill`, last 14 days). Weekly picks use partner finds.
- Email: no email settings page. The footer has Unsubscribe only; the unsubscribe page has a "Turn emails back on" undo.
  Logo watches, monogram bags and the luxury brands may go in emails, and alert and weekly-picks subjects name the
  brand. `EMAIL_LOGOS=0` takes out both.

## Systems worth knowing
- Dark-mode photo tiles: cut-outs sit on #262626. Rules in `functions/_lib/photo_tiles.js` (`CUT_RX`, `TILE_CUT_IDS`,
  `TILE_LIGHT`), mirrored in `index.html` (`pcCut()`).
- QC photos: banked once per find in Supabase storage `products/qc/` by `scripts/qc_bank.py` (nightly). The corner
  badge on QC photos is swapped for our QR code by `scripts/qc_badge.py`. Photo links carry `?b=2`. Sources:
  qualit.ly (key `QUALITLY_KEY`) and the Oopbuy QC API (`scripts/oopbuy_qc.py`, keys `OOPBUY_APP_ID`,
  `OOPBUY_AES_KEY`, `OOPBUY_SIGN_SECRET`, waiting for Oopbuy).
- Email (v2, 26 Nov 2026): `scripts/mailer.py` run by `.github/workflows/email.yml` every 15 minutes (welcome series
  W0 to W3, saved-find alerts, weekly picks, win-back, sunset; warm-up caps and stop lines built in). Provider per
  stream: Plunk by default, AhaSend as the switchable backup (`PROVIDER_AUTOMATED`, `PROVIDER_NEWS`). Clicks go through
  our own tracker `functions/e/[[path]].js` and are counted per email and link, not per person (Norwegian and EU rules);
  no per-person tracking (its switch lived on the removed settings page). Plunk's own tracking stays Disabled.
  Webhooks for bounces and complaints: `functions/api/email-hook.js`. Unsubscribe:
  `functions/unsubscribe.js` (GET shows a page, POST unsubscribes, via=undo turns emails back on). Numbers: `scripts/email_stats.py` into the Email
  section of `/stats`. Database: `scripts/email_v2.sql` then `scripts/email_v2_engine.sql`. Research behind it:
  the report "Email lifecycle deliverability and tracking". `newsletter.py`, `welcome.yml` and `newsletter.yml` are
  the old system, kept only for manual test runs.
- Archive import (26 Nov 2026): a reseller's sheet matched by image search to the ORIGINAL 1688 / Taobao listings.
  `scripts/import_archive.py stage <scored.csv>` (local, inputs outside the repo) writes `data/archive_import.json`
  (original listings only; the reseller map stays outside the repo); `.github/workflows/import-archive.yml` makes the
  cut-outs (`scripts/archive_photos.py`, Supabase `products/pc2/<id>-t1.webp`) and adds the finds with `"ar": 1`.
  `ar` = Archive style whatever the brand (`pcStyleMatch`) and ranks right after partner finds (`swapFirst`, `score()`).
  Never put a reseller id or link in the repo.
- Sheet import (27 Nov 2026): the Da Murphy finds sheet (`data/sheet_murphy_list.json`) as NORMAL finds (no `ar`, no
  swap; rugs and room decor under Accessories). `.github/workflows/import-sheet.yml`: `scripts/import_sheet.py stage`
  (Weidian via getItemSkuInfo, Taobao / 1688 from `data/sheet_murphy_details.json`, else "needs details"; one vision
  call names each find), then the Archive's photos and apply with `--set murphy`. Run until the report says `left 0`.
- Stats: `/stats` (`stats.html`, data from the stats workflow), visits through `/api/visit`.
- Preview the sign-up flow as a new visitor: `/?preview=signup`.
