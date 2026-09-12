# Manifest

A product catalogue for Weidian / Taobao / 1688 finds, with QC photos, agent
affiliate links, accounts, saved items (stars) and comments.

Static front-end (one `index.html`) + Supabase (auth + database). Deploys to
Cloudflare Pages.

## Files
- `index.html` — the whole app (HTML + CSS + JS in one file)
- `terms.html`, `privacy.html` — legal pages (review before relying on them)
- `robots.txt`, `sitemap.xml` — SEO
- `_headers` — security headers + CSP for Cloudflare Pages

## Deploy (Cloudflare Pages)
1. Push this folder to a GitHub repo.
2. Cloudflare dashboard → Workers & Pages → Create → Pages → connect the repo.
3. Framework preset: **None**. Build command: empty. Output directory: `/`.
4. Deploy. You get a `*.pages.dev` URL (add a custom domain later).

## After first deploy
- In `index.html`, replace `REPLACE-WITH-YOUR-DOMAIN` (canonical + og) and in
  `robots.txt` / `sitemap.xml`. Put your email in `terms.html` / `privacy.html`.
- **Supabase → Authentication → URL Configuration:** set Site URL to your
  deployed URL and add it to Redirect URLs, or magic-link / Google / Apple
  sign-in won't return to your site.

## Where to change things
- **Product data:** `loadProducts()` near the top of the `<script>` in
  `index.html`. Swap the sample array for a fetch of your real feed (same shape).
- **Affiliate links:** `AGENTS` object + `AFFILIATE_REF` ("LHYDVW").
- **Supabase keys:** `SUPABASE_URL` / `SUPABASE_KEY` (the publishable key is meant
  to be public; security is enforced by Row Level Security in the database).

## Enable Google / Apple sign-in (buttons are already in the UI)
- **Google (free):** Google Cloud Console → create an OAuth client → paste the
  client ID + secret into Supabase → Authentication → Providers → Google.
- **Apple (needs a paid Apple Developer account, ~$99/yr):** create a Service ID
  + key in the Apple developer portal → paste into Supabase → Providers → Apple.
  Skip this until you want it; email + Google cover most sign-ins.

## Database
Already created in Supabase: `profiles`, `favorites`, `comments` (with row-level
security) and a `star_counts()` function that powers the public star counter.
