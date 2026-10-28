# Puro Classico design system (v7, 25 Oct 2026)

One look for every page: **qualit.ly's dark, hairline-and-card style with modern Apple calm**. Near-black ground, thin grey borders, rounded cards with real gaps, white pill buttons, a floating glass header and small monospace labels. Light mode follows Apple: soft grey ground, white cards, near-black ink. The product photo does the talking; everything around it stays quiet. We borrow the style, never qualit.ly's branding: our logo, red MyCNBox button and copy stay ours.

- **`/ds.css`** holds the tokens and components for the server-rendered pages (brand, category, agent, guide, tool and product pages) and the static pages `how-to-order.html`, `privacy.html` and `terms.html`, which use the same `header.h` markup as the server pages. The v7 rules are the block at the end of the file.
- **`links.html`** (the TikTok link-in-bio page) does not load `ds.css`: it keeps a copy of the dark tokens in its own `<style>`. Change both when a dark token changes.
- **`index.html`** (the catalogue app, also used by the hub pages) has its own stylesheet with the same tokens. The v7 layer is the block that starts `v7 design layer` at the end of the main `<style>`, and it wins over the older layers above it.
- **Fonts are self-hosted** in `/fonts/`: `instrument-sans-latin.woff2` (Instrument Sans 400–700, text and headings) and `jetbrains-mono-latin.woff2` (JetBrains Mono 400–500, small labels only). Both OFL.
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
| `--glass` | 72% surface | 72% white | Floating header (with an 18 px backdrop blur) |
| `--accent` | `#8EA6DC` | `#0066CC` | Small highlights only (the light value passes 4.5:1 as link text on every light surface) |
| `--brand-red` | `#D9301E` | same | MyCNBox call to action only |
| `--font` (app: `--f-body`, `--f-disp`) | Instrument Sans | | All text |
| `--mono` (app: `--f-code`) | JetBrains Mono | | Eyebrow labels, brand lines on cards, small metadata |

In the app, `--f-mono` stays the body font on purpose: older components use it for normal UI text. Use `--f-code` for monospace.

- **Type:** headings 600 weight with tight negative letter spacing (h1 `-0.035em`), body 16 px, small 13.5 px. Eyebrows: 11.5 px JetBrains Mono, uppercase, 0.14em letter spacing, `--muted`.
- **Spacing:** a 4 px grid (`--s1` 4 … `--s8` 64). Card grids have 16 px gaps.
- **Radius:** controls are pills, inputs 14 px, cards 18 px, the floating header 20 px (16 px on phones).

## Rules

1. **Cards are real cards.** Product cards sit on `--surface` with a 1 px `--line` border and 18 px radius: photo on top (hairline under it), then brand (mono), title and price. Hover lifts 2 px and darkens the border.
2. **The header floats.** A rounded glass bar inset 12 px from the edges, over the page glow. No hard line between header and page. At 820 px and below the bar grows to two rows (logo and MyCNBox button, then the nav, which scrolls sideways) and scrolls away with the page instead of sticking.
3. **One primary action per view.** It is a solid ink pill (`.btn.light` / `.btn.primary`). Everything else is an outline pill or a text link.
4. **The red is only for MyCNBox.** Never for errors, decoration or other agents.
5. **Monospace is for labels, never for buttons or body text.**
6. **Borders for structure, shadows only for things that float** (menus, popovers; a soft shadow on cards in light mode only).
7. **Numbers use `tabular-nums`.**
8. **Motion:** 150–200 ms colour, border and transform changes, `scale(.96)` when a button is pressed (`.98` for wide buttons). Nothing animates on page load. Hover effects go inside `@media (hover:hover)` so a tap on a phone does not leave them on. A control that presses in also turns off the grey tap highlight (`-webkit-tap-highlight-color:transparent` on that control); product cards, which do not press in, and plain links keep the system highlight. With `prefers-reduced-motion`, keep opacity and colour fades and drop the animation of anything that moves or scales.
9. **Every colour comes from a token.** No hex codes in page code.
10. **Sizes:** touch targets at least 44 px (including the header logo link, nav links on touch screens and footer links on the static pages); inputs use 16 px text so iPhones don't zoom in.
11. **Agent menus show the agent's logo** next to its name (`AGENT_LOGO` / `agentIco()` in `index.html`).
12. **Copy:** short, plain and factual. No em dashes. Make no claims the data can't back up.
13. **Accessible by default:** pages with a header start with a skip link (`.skip-link` to `<main id="main">` on server and static pages; the app's skips to the search box), every `<nav>` has an `aria-label` (`header.h` uses "Main"), and decorative glyphs get `aria-hidden`.

## Components in `ds.css`

`.skip-link` · `header.h` (floating glass bar with logo, nav and CTA) · `.btn` (`.light`/`.primary`, `.red`, `.sm`) · `.bc` breadcrumbs · `.lead` · `.prose` · `.facts` · `.chips` · `.note` · `.eyebrow` · `.g` grid + `.c` card (`.ci` photo, `.qb` QC badge, `.cb` text, `.cbr` mono brand line) · `.pg` pager · product page (`.pd`, `.pimg`, `.qcs` (with `.qc-h`, and `.qc-load`/`.qc-none` for photos loaded on request), `.price`, `.buybox` with `.buy-main`, `.buy-hint`, `.buy-or`, `.buy-alt`, the phone `.buybar`, `.buy-gone` link-check notice, `dl.kv`) · `.steps` · `.faq` · `.tool` · `.gl` (card grid on /guides and /tools) · `.toc` ("On this page" box in long guides) · `footer.f`.
