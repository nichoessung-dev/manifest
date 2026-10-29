# Puro Classico design system (v7, 25 Oct 2026; v8 additions, 28 Oct 2026)

One look for every page: **qualit.ly's dark, hairline-and-card style with modern Apple calm**. Near-black ground, thin grey borders, rounded cards with real gaps, white pill buttons, a floating glass header and small monospace labels. Light mode follows Apple: soft grey ground, white cards, near-black ink. The product photo does the talking; everything around it stays quiet. We borrow the style, never qualit.ly's branding: our logo, red MyCNBox button and copy stay ours.

**v8** keeps that identity and adds Apple-grade craft: one motion system, display type, Liquid Glass lite on the bars, inset photo tiles, a bottom sheet for the product view on phones, page transitions and scroll-linked details. Every v8 effect is progressive (`@supports`, media queries, feature tests): without support the page is plain v7. The v8 rules are in the section [v8 additions](#v8-additions-28-oct-2026) below; where they change a v7 rule, the rule says so.

- **`/ds.css`** holds the tokens and components for the server-rendered pages (brand, category, agent, guide, tool and product pages) and the static pages `how-to-order.html`, `privacy.html` and `terms.html`, which use the same `header.h` markup as the server pages. The v7 rules are a block near the end of the file; the **v8 layer** is the last block and wins by order.
- **`links.html`** (the TikTok link-in-bio page) does not load `ds.css`: it keeps a copy of the dark tokens in its own `<style>`. Change both when a dark token changes.
- **`index.html`** (the catalogue app, also used by the hub pages) has its own stylesheet with the same tokens. The v7 layer is the block that starts `v7 design layer` at the end of the main `<style>`; the v8 layer comes after it. The app's motion script runs as its own classic `<script>` right after the app script; every feature in it is wrapped in try/catch.
- **Fonts are self-hosted** in `/fonts/`: `instrument-sans-latin.woff2` (Instrument Sans 400–700, text and headings) and `jetbrains-mono-latin.woff2` (JetBrains Mono 400–500, small labels only). Both OFL. v8 adds no fonts.
- **Changing `ds.css`?** Raise `DS_VER` in `functions/_lib/site.js` and the `?v=` in the static pages, so browsers fetch the new file. To make product and hub pages render again, also raise `PRODUCT_TPL` in `functions/_lib/pages.js`.

## Tokens

| Token | Dark (default) | Light | Use |
|---|---|---|---|
| `--bg` (app: `--ground`) | `#0B0D10` | `#F5F5F7` | Page background |
| `--surface` / `--surface-2` | `#121519` / `#181C21` | `#FFFFFF` / `#F0F0F2` | Cards and panels / hover fills |
| `--ink` / `--ink-2` | `#ECEFF2` / `#CBD1D7` | `#1D1D1F` / `#3A3A3C` | Headings / body text |
| `--muted` / `--faint` | `#99A2AB` / `#7C848D` | `#6E6E73` | Secondary text / labels |
| `--line` / `--line-2` | `#23272E` / `#323840` | `#E3E3E8` / `#D2D2D7` | Hairline borders / hover and control borders |
| `--fill` / `--fill-ink` | ink / bg | ink / white | Primary pill button |
| `--field-line` (v8, `ds.css`) | `#6B737C` | `#86868B` | Text field borders (3:1 or more on every fill) |
| `--glass` | 72% surface | 72% white | v7 floating header (v8 uses `--glass-fill`, below) |
| `--accent` | `#8EA6DC` | `#0066CC` | Small highlights, links in prose, the focus ring (the light value passes 4.5:1 as link text on every light surface) |
| `--brand-red` | `#D9301E` | same | MyCNBox call to action only |
| `--font` (app: `--f-body`, `--f-disp`) | Instrument Sans | | All text |
| `--mono` (app: `--f-code`) | JetBrains Mono | | Eyebrow labels, brand lines on cards, small metadata |

In the app, `--f-mono` stays the body font on purpose: older components use it for normal UI text. Use `--f-code` for monospace.

- **Type:** headings 600 weight with tight negative letter spacing (h1 `-0.035em`), body 16 px, small 13.5 px. Eyebrows: 11.5 px JetBrains Mono, uppercase, 0.14em letter spacing, `--muted` (pills above an h1 use the body font, see v8). (v8: display sizes, 17 px article copy, below.)
- **Spacing:** a 4 px grid (`--s1` 4 … `--s8` 64). Card grids have 16 px gaps (v8: 12 px on phones, 20 px from 1100 px).
- **Radius:** controls are pills, inputs 14 px, cards 18 px, the floating header 20 px (16 px on phones). (v8: cards 22 px, buy tile 28 px, header capsule 30 px from 821 px.)

## Rules

1. **Cards are real cards.** Product cards sit on `--surface` with a 1 px `--line` border: photo on top, then brand (mono), title and price. *v8:* 22 px radius (18 px on phones) with the photo inset in a light well (see Tiles). Hover (mouse only) lifts the card 3 px with a soft shadow and zooms the photo to 1.03 (server cards fade in a shadow on a pseudo-element, app cards use a drop-shadow filter).
2. **The header floats.** A rounded glass bar inset 12 px from the edges, over the page glow. No hard line between header and page. At 820 px and below the bar grows to two rows (logo and MyCNBox button, then the nav, which scrolls sideways) and scrolls away with the page instead of sticking. *v8:* from 821 px it is a capsule of Apple's glass whose shadow fades in over the first 48 px of scroll.
3. **One primary action per view.** It is a solid ink pill (`.btn.light` / `.btn.primary`). Everything else is an outline pill or a text link.
4. **The red is only for MyCNBox.** Never for errors, decoration or other agents.
5. **Monospace is for labels, never for buttons or body text.**
6. **Borders for structure, shadows only for things that float** (menus, popovers, the glass bars, a card lifted by hover; a soft resting shadow on cards in light mode only).
7. **Numbers use `tabular-nums`.**
8. **Motion:** use the v8 tokens below. Colour and border changes are 100 ms linear; a pressed control scales to `.96` (`.98` for wide buttons, `.985` for cards and index tiles, after an 80 ms delay so a scroll that starts on a card does not flicker). Nothing animates on page load, and content visible at load never starts hidden. Hover effects go inside `@media (hover:hover)`; hover movement (lift, zoom, nudge) inside `@media (hover:hover) and (pointer:fine)`. A control that presses in also turns off the grey tap highlight (`-webkit-tap-highlight-color:transparent` on that control); since v8 that includes product cards and index tiles. Plain links keep the system highlight. Animate only `transform`, `opacity` and `filter`; never `transition: all`. With `prefers-reduced-motion`, keep opacity and colour fades and drop everything that moves or scales (the base rule in `ds.css` stops every animation, scroll-driven ones included).
9. **Every colour comes from a token.** No hex codes in page code.
10. **Sizes:** touch targets at least 44 px (header logo link, nav links, chips, small buttons, pager, breadcrumb links, the brand pill, "On this page" rows and footer links on touch screens; a pseudo-element or padding extends the hit area where the visual is smaller). On phones the footer columns become wrapping rows of links under each heading (server and app alike), so 44 px rows keep the footer short. Inputs use 16 px text so iPhones don't zoom in, and a `--field-line` border (3:1 or more, WCAG 1.4.11).
11. **Agent menus show the agent's logo** next to its name (`AGENT_LOGO` / `agentIco()` in `index.html`).
12. **Copy:** short, plain and factual. No em dashes. Make no claims the data can't back up.
13. **Accessible by default:** pages with a header start with a skip link (`.skip-link` to `<main id="main">` on server and static pages; the app's skips to the search box), every `<nav>` has an `aria-label` (`header.h` uses "Main"), and decorative glyphs get `aria-hidden`. *v8:* the focus ring is 2 px `--accent` with a 2 px offset (text fields: accent border plus a 4 px halo; checkboxes and radios keep the ring); WCAG 2.2 AA contrast in both themes, including text on glass over any content. Focus never lands under a bar: `scroll-padding` on `html` clears the sticky header (from 821 px) and the phone buy bar (WCAG 2.4.11).

## v8 additions (28 Oct 2026)

### Motion tokens (same names and values in `ds.css` and the app's v8 layer)

| Token | Value | Use |
|---|---|---|
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` | Enters, presses |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | Moves between two places, morphs |
| `--ease-sheet` | `cubic-bezier(.32,.72,0,1)` | Sheets and bars presenting |
| `--ease-apple` | `cubic-bezier(.28,.11,.32,1)` | Stuck or scrolled bar background (with `--d-bar`) |
| `--ease-hover` | `cubic-bezier(0,0,.5,1)` | Tile hover (300 ms lift, 400 ms photo zoom) |
| `--d-1` / `--d-2` / `--d-bar` / `--d-3` / `--d-4` | 120 / 200 / 240 / 320 / 480 ms | Press / small UI / bar change / exits and menus / sheet enter |
| `--d-ctl` (`ds.css` only) | 100 ms, linear | Colour changes on controls |

Exits are faster than enters (a sheet enters in 480 ms and leaves in 320 ms). State changes use interruptible transitions; keyframes only for one-off entrances and scroll-driven effects.

### Display type
- Hub and index h1 `--fs-display` (40 to 76 px), guide and static-page h1 `--fs-title` (34 to 56 px), product h1 `--fs-product` (28 to 42 px); line-height 1.04 to 1.08, tracking `-0.035em` (`-0.04em` from 1069 px; Instrument Sans has no optical sizes). The app's homepage hero h1 goes up to 92 px.
- Big h1s get a quiet vertical ink fade (`--ink` to `--ink-2`, clipped to the text) with a solid fallback, a forced-colors fallback and a little padding so descenders are never cut.
- Section h2 `--fs-section` (26 to 40 px) with `--sec-gap` (56 to 96 px) above; h2s over link lists and in articles `--fs-section-sm` (22 to 28 px). Lead `--fs-lead` (18 to 21 px, `--muted`, about 40rem wide). Article copy `--fs-copy` 17 px at 1.6. `text-wrap: balance` on headings, `pretty` on copy.
- An eyebrow above an h1 is a small pill: hairline, translucent fill, specular top rim, 7 px `--accent` dot with a soft halo, Instrument Sans 13-14 px weight 500 in sentence case (29 Oct 2026: owner found the mono caps too technical) (`.eyebrow.pill`; positional selectors cover older markup). Other eyebrows ("Spreadsheets:", "On this page") stay plain labels.

### Glass (Liquid Glass lite)
- Only on the functional layer: the header bar, the phone buy bars, the app's stuck toolbar, menus, popovers and toasts. Never on content; product cards stay opaque, and the QC badge is a solid fill (no blur on a scrolling grid).
- Recipe: `--glass-fill` (80%) with `saturate(180%) blur(20px)` (literal values in `-webkit-backdrop-filter`, never `var()`), `--glass-line` hairline, an `inset 0 1px 0 var(--glass-rim)` specular edge, and `--glass-float` only while floating. Without blur support the fill is `--glass-solid` (88% dark, 92% light). The app's v8 layer uses the same `--glass-fill`, `--glass-solid` and `--glass-rim` values, so the header looks the same on both sides of a page transition.
- Text on glass uses `--ink` or `--ink-2`, never `--muted`: it must pass 4.5:1 with a light photo well or a dark garment behind the glass.
- Never animate the blur, never nest glass, and never animate opacity or filter on a parent of a glass element (it would cut the blur). `prefers-contrast: more` and `prefers-reduced-transparency` switch to the solid fill.

### Tiles
- Cards: radius `--r-card` 22 px with `--card-pad` 7 px around a 14 px well (concentric: 22 = 14 + 7 + 1 border); phones 18 / 5 / 12 px. The app's cards use the same numbers.
- The well stays light in both themes, so black and navy garments read; white photo backgrounds are multiplied into it (`mix-blend-mode: multiply`, isolated to the well). It is a flat `--well` (`#F5F5F7` light, `#E6E6EA` dark) on server pages and in the app (where v7's `--studio-a`/`--studio-b` gradient now points at `--well`); on server cards a 1 px `--well-edge` ring sits inside it. Real photos (QC thumbnails) get `--photo-edge` instead and no blend.
- The product photo tile uses `--tile-bg` (white in light mode). It is the LCP: it never fades or moves in.
- Index tiles (`.gl` on /guides and /tools) share the card radius, hover lift and press, with an arrow that nudges 3 px on hover.

### Product view
- Server product page: one column up to 820 px, two from 821 px; from 900 px wide and 820 px tall the photo column sticks under the header. Price in 28 to 34 px tabular numerals; the buy box is a 28 px tile around 16 px buttons (concentric). Up to 820 px the buy bar (`.buybar`) is a floating glass capsule (at most 560 px wide, centred) that rises on `--ease-sheet` once the main buy button scrolls away; with reduced motion it fades.
- App product view (`#drawer`): on computers a floating sheet from the right over a dimmed, lightly blurred page (enters 24 px plus fade on `--ease-sheet`, leaves faster). On phones (560 px and below) a bottom sheet 12 px below the top with 20 px corners, a 36 x 5 px grabber and a sticky glass buy bar (`.d-buybar`). Drag down on the grabber or the sheet header to close: it follows the finger, closes past `min(120px, 25%)` or on a flick, otherwise springs back. Back, Escape and history back stay the accessible ways to close.

### Transitions
- Cross-document view transitions on every page that loads `ds.css` and on the app (`@view-transition { navigation: auto }` inside `prefers-reduced-motion: no-preference`; Firefox ignores it): a short crossfade (220 ms into a server page; into the app its root keeps v7's 200 ms and the header group 220 ms, since the new page's CSS times the transition) while the header bar (`view-transition-name: site-header`, on `header.h > .w` from 821 px and on the app's `.masthead .mast-row`, except during the photo morph and under the product view) holds still. Safari drops `backdrop-filter` during a transition, which is one reason the glass fills stay at 80% or more.
- App only: opening a product from a card morphs the card photo into the product photo (same-document view transition, under 400 ms), only after a pointer click on a loaded photo.
- Cards the app adds after the first render (filters, infinite scroll) fade up 8 px in 360 ms, staggered 30 ms in a diagonal wave, with the delay capped at 210 ms. The first render never animates.

### Reveals and scroll effects
- Scroll-linked, never timed: `animation-timeline` behind `@supports`, off with reduced motion. Only for marketing sections (section h2s, FAQ, steps, notes, prose tables; the app's SEO blocks), never product grids or photos.
- Only elements whose top is below the first screen at load get the `.rv` class (a small script decides), so nothing in view at load starts faded. They fade in with a 12 px rise from the moment their top enters at the bottom edge until it is 20vh in (`animation-range: cover 0% cover 20vh`, server and app alike).
- The header shadow follows scroll over the first 48 px (`header.h.scrolled` from the layout script where scroll timelines are missing). The app's hero recedes slightly as it scrolls away; its content is fully visible at scroll 0.

### Hooks the scripts add (all optional; without them the page is static v7)
Server pages: `header.h.scrolled` and `.rv` (layout script in `site.js`). App (motion script; the exact names are listed at the top of the app's v8 layer): `html.v8-js`, `html.v8-motion`, `.masthead.scrolled`, `.toolbar.stuck`, `#grid .card.v8-enter` with the stagger index `--i`, `html.vt-morph` and the `v8-photo` transition name during the photo morph, the `#drawer .grabber` handle, `#drawer.v8-dragging`, the favourites strip arrows (`.strip-nav`), `#hero-strip.v8-manual`, and `.rv` on `#seo` and `.hub-seo`.

## Components in `ds.css`

`.skip-link` · `header.h` (floating glass bar with logo, nav and CTA) · `.btn` (`.light`/`.primary`, `.red`, `.sm`) · `.bc` breadcrumbs · `.lead` · `.prose` (`.byline`, `.gloss`, `.note`, tables) · `.facts` · `.chips` · `.note` · `.eyebrow` (`.eyebrow.pill` above an h1) · `.g` grid + `.c` card (`.ci` photo well, `.qb` QC badge, `.cb` text, `.cbr` mono brand line) · `.pg` pager · product page (`.pd` with `.pd-media` and `.pd-info` columns, `.pimg`, `.qcs` (with `.qc-h`, and `.qc-load`/`.qc-none` for photos loaded on request), `.price`, `.buybox` with `.buy-main`, `.buy-hint`, `.buy-or`, `.buy-alt`, the phone `.buybar`, `.buy-gone` link-check notice, `dl.kv`) · `.steps` · `.faq` · `.tool` · `.gl` (tile grid on /guides and /tools) · `.toc` ("On this page" tile in long guides) · `footer.f` (with `.disc` and `.legal` fine print) · `.rv` (scroll reveal).

## Round 4 (29 Oct 2026): header, category photos, motion, pages 2+

### Header (app `index.html` and server `ds.css` + `site.js header()`, same pixels)
- Row 56px + 1px hairline (57). Container 1280px with a 32px gutter (16px up to 640px). Logo box 104x28 (96x26 on
  phones), 24px from the logo to the nav.
- Nav items in this order: Finds `/`, Brands `/brands`, Tools `/tools`, Guides `/guides`, How to Order `/how-to-order`.
  Each item: 36px tall, 0 12px padding, pill radius, Inter 500 14px, `--muted`; hover `--surface-2` / `--hover` and
  `--ink`. The current item (`aria-current="page"`) is `--ink` on the pill background; the weight never changes.
- Tools = a link plus a 24x36 chevron button (`#tools-btn`, `aria-controls="tools-menu"`, "Tools menu"), margin-left
  -8px so the pair reads as one pill. The chevron always takes its 24px and only rotates. Server pages get the same
  `#tools-menu` (5 tools + All tools), opened by PAGE_JS (click, Esc returns focus, outside click closes). Under 1024px
  the app folds the links into that menu and the button shows its "Tools" label again.
- Current section: `navKey(path)` in `site.js` (`/`, `/category/*`, `/*-spreadsheet*`, `/old-money*`, `/best*`,
  `/product/*` = Finds; `/brands`, `/brand/*` = Brands; `/tools*`; `/guides*`; `/how-to-order`). index.html marks Finds;
  `_middleware.js hubApp()` moves `aria-current` for app hubs (brand hubs = Brands) before the first paint.
- One `.nl-pill` (last child of the nav, under the links) is anchored to the current item with CSS anchor positioning.
  Without anchor support the current item gets the background itself. No pill when nothing is current.
- Header search shell `#pcs-hd` after the nav: 240px field from 1280px (search icon, input, Cmd/Ctrl K hint), a 36px
  round button below that (44px on phones). On server pages it is a plain GET form to `/?q=`; the button, Cmd/Ctrl+K
  and "/" focus the field or open `/?s=1`.
- App right side: the Discord icon shows from 1500px (it is in the footer too) and the theme choice lives in the globe
  popover from 561 to 1279px, so the nav never shrinks and the search shell keeps its place.

### Page transitions
- Cross-document view transitions on every page (`@view-transition{navigation:auto}` under
  `prefers-reduced-motion:no-preference`, in index.html and ds.css). Named layers: `site-header` (the header, still),
  `nav-pill` (glides 260ms `--ease-in-out`), and one name per nav item (`nl-finds`, `nl-brands`, `nl-tools`,
  `nl-guides`, `nl-how`) so the link text always paints above the gliding pill. Root crossfade 200ms. In the app these
  names are off while the product photo morph runs (`html.vt-morph`, `body.pp-open`).

### Motion vocabulary
- Tokens on both sides: `--ease-out` (existing), `--ease-in-out` cubic-bezier(.65,0,.35,1), `--dur-1` 120ms (press,
  hover), `--dur-2` 200ms (menus, fades, page crossfade), `--dur-3` 320ms (drawer, sheet).
- Only `transform` and `opacity` move (plus colours on hover). Press: `scale(.96)` on pills and buttons, `.98` on
  cards (the app's product card keeps its own .985). Hover only inside `@media (hover:hover)`.
- Menus (`#tools-menu`, `#theme-menu`, the globe popover, the server tools menu and phone nav) open with
  `@starting-style` opacity 0 + `translateY(-4px) scale(.98)`, origin at the trigger; they close at once.
- Images: `html.js-fade` (set by the head script, with capture-phase load/error listeners that add `.is-in`) hides the
  category photos and the server card photos until loaded, then fades them in over 200ms. No JS, no fade.
- Rails (`.v9-rail`): `scroll-snap-type:x proximity`, arrows fade at the ends. Home rails ship 6 `.sk-card`
  skeletons each (image well + text bars in `--_mut`, opacity pulse 1.2s, static under reduced motion), replaced when
  the rows are built.
- Reduced motion: no view transitions, no transforms, no fades, no pulses (both stylesheets).

### Category circles
- The 8 `.v9-cat` tiles show one product photo each (`.v9-cat-ic.v9-cat-ph > img`, 64x64 attributes, first 5 eager,
  `alt` = the label, translated with it). Owner picks: Shoes `/img/cat/shoes.webp`, Tops find 7630051831, Outerwear
  7778392674, Pants 7683153496, Shorts 7779243114, Bags 953406678555, Accessories `/img/cat/accessories.webp`,
  Headwear `/img/cat/headwear.webp`.
- Light: the photo fills the `#F5F5F5` circle with `mix-blend-mode:multiply` at `scale(.86)` (white backgrounds
  disappear). Dark and the active tile: a 48px (44px phone) round inner well, no blend, a 1px `rgba(255,255,255,.06)`
  ring. Hover `scale(1.04)`, press `scale(.96)`.

### Brand and category pages 2+ (`pages.js hub()`, `.hub-p2` in ds.css)
- Compact head like the app hub: breadcrumbs, then the h1 (unchanged text, with its "page N") and the black pill
  "Open the full <Brand or category> spreadsheet" linking page 1 (full width under the h1 on phones). Facts as one muted
  line, chips as single rows; both scroll sideways on phones.
- The same server card (`div.c`, track.js attributes kept) on a grid of 5 / 4 / 3 / 2 columns (1280 / 1024 / 768 /
  below), gap 16px (10px phones), first 4 photos eager; pager centred, 44px targets on phones.

## Search (v9, round 4)

One search engine and one suggestion panel for the whole app. Everything runs in the browser; the optional AI helper
(`/api/ai-search`, see `OWNER_AI.md`) is only asked when a search has zero results.

### Where it lives
| Field | Where | Presentation |
|---|---|---|
| `#v9-q` in `#v9-hero-search` | home hero | dropdown under the field from 768px; phones (under 768px, or touch under 1024px): full-screen sheet on tap |
| `#pcs-hi` in `#pcs-hd` | masthead, every app page | field from 1280px (dropdown, min 560px wide); below 1280px the round button `#pcs-hb` opens the palette (768 to 1279px) or the sheet |
| `#pcs-oi` | palette / sheet | the overlay's own field |
| `#q`, `#pp-q` | grid toolbar, grid inside a find | plain inputs, same engine through `qMatcher()` (no panel) |

Server pages carry the same header shell (`site.js`, `ds.css`) as a plain GET form to `/?q=`; their button and Cmd/Ctrl+K
go to `/?s=1`, which opens the search in the app.

### Panel anatomy (`#pcs-panel`, built once, moved between hosts)
- Box: `--surface`, 1px `--line`, radius 12px, shadow `0 10px 30px -12px rgba(0,0,0,.25)` (dark `.6`), padding 6px,
  `max-height:min(70vh,600px)`, inner scroll, z-index 70 (drawer is 80, overlays 95).
- Section heading: 13px/600 `--muted`, sentence case, padding 8px 12px. No uppercase, no tracking.
- Row: min 44px (sheet 52px), radius 8px, active row `--surface-2` (mouse move sets it; no separate hover style);
  keyboard-active row also gets a 2px `--ink` inset outline.
- Empty field: Recent (clock icon, text, 36px remove button; "Clear" in the heading), Popular (32px pill chips, 13px/500,
  `--surface-2`; real data only: Stats job `search.top`, then `top_brands_7d`, then the most viewed brands), Categories
  (4 per row: 40px photo circle + name + count; sheet: 56px circles with the label under). Category photos use the same
  images and light/dark treatment as the home category row (light: multiply on the grey circle; dark: inner well,
  `0 0 0 1px rgba(255,255,255,.06)`).
- Typing: Did you mean (only after a typo fix), Brands (0 to 3, 32px tag tile, name with the matched part in bold, "N
  finds"), Categories (0 to 2), Products (up to 6 rows of 64px: 48px image well radius 8 `--surface-2`, title 14px/500
  with matched words in 600, "Brand · Category" 12px muted, price 14px/600 tabular, QC pill 20px when `qc >= 1`),
  then "Search all N results for “q”" sticky at the bottom (sheet: 48px primary pill).
- Item ID or a Weidian/Taobao/1688/agent link: "Open this find" with its row, or a link to the QC checker.
- Zero results: "No exact matches for “q”" (13px muted), Closest matches (finds with at least half of the words), the
  optional AI chip ("Try “…”" + small "AI" label, only when its words give results), Popular chips. Never a dead end.

### Palette and sheet
- Palette: fixed, `top:72px`, `width:min(640px,100vw - 32px)`, its field is a 48px bordered pill like the hero, close
  button on the right, backdrop `rgba(0,0,0,.24)`; `role="dialog" aria-modal="true"`.
- Sheet: `position:fixed;inset:0;z-index:95`, height follows `visualViewport` (`--pcs-vvh`), top bar 56px with a 44px
  back button and a 44px field (16px text, radius 12px, `--surface-2`), sides `max(16px, safe area)`. The page behind is
  `inert` and does not scroll; the browser Back button closes the sheet (it adds one history entry, removed on close).

### Keyboard and ARIA
Inputs are `role="combobox"` with `aria-controls="pcs-list"`, `aria-expanded`, `aria-activedescendant`; `#pcs-list` is the
`listbox`, sections are `group`s, rows and chips are `option`s with ids `pcs-o-N` in visual order. Arrow Down/Up move
(wrap), Enter chooses (no active row: Search all), Esc closes then clears, Tab closes the dropdown, Shift+Delete removes
a recent search, Cmd/Ctrl+K and "/" open search from anywhere ("/" not while typing in a field). `#pcs-live` announces
"N suggestions, M finds" 400ms after typing stops.

### Engine (in `<script id="pc-search">`, between `PCS-ENGINE-BEGIN` / `PCS-ENGINE-END`)
- Index built on first use in two idle parts (focus does not wait; a keystroke completes it), rebuilt when the catalogue
  size changes, popularity refreshed when the view stats or the sold-out list arrive. `window.PCS.stats` has the timings.
- Matching: every word must match (word prefix, plural, alias, or the closest catalogue word for a word with no hit at
  all: 1 edit for 4 to 7 letters, 2 from 8; never for words with digits). Aliases (`PCS_ALIAS` + the existing `Q_SYN`):
  brand nicknames, model codes, common misspellings, garment and colour words in Norwegian, Swedish, Danish, German,
  French, Spanish, Italian, Dutch and Chinese. Expansions are added, never replace the typed word, so the grid always
  finds at least what it found before.
- Ranking: match quality x field weight (brand 1.3, title 1.0, category 0.8, colour 0.7, seller 0.3), bonuses for the
  words in order in the title, the full brand name, the title starting with the first word, then popularity (views and
  saves), QC photos, minus sold out and placeholder prices. The grid's default sort uses the same score while a search
  is active.
- Tests: `V/r4/search_bench.js` + `search_golden.txt` (jsc), regenerate the AI vocabulary with `V/r4/build_vocab.py`.

### Motion
Dropdown and palette fade in with a 4 to 6px rise in 200ms `--ease-out`; the sheet rises 8px; chips and the header
button press to `scale(.96)`. Transform and opacity only; all of it is off under `prefers-reduced-motion: reduce`.
