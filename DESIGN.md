# Puro Classico design system

One look for every page: calm, neutral and editorial, like a good fashion shop. The product photo does the talking; everything around it stays quiet.

- **`/ds.css`** holds the tokens and components for the server-rendered pages (brand, category, agent, guide, tool and product pages) and the static pages (`how-to-order.html`, `privacy.html`, `terms.html`).
- **`index.html`** (the catalogue app) has its own stylesheet but uses the same tokens. They are in the block that starts `design system, 17 Oct 2026`.
- **Changing `ds.css`?** Raise `DS_VER` in `functions/_lib/site.js` and the `?v=` in the static pages, so browsers fetch the new file. To make product pages render again, also raise `PRODUCT_TPL` in `functions/_lib/pages.js`.

## Tokens

| Token | Dark (default) | Light | Use |
|---|---|---|---|
| `--bg` | `#0B0B0C` | `#FAFAF8` | Page background |
| `--surface` / `--surface-2` | `#141415` / `#1D1D1F` | `#FFF` / `#F1F0EC` | Panels, hover fills |
| `--ink` / `--ink-2` | `#F4F4F2` / `#D4D3CF` | `#111110` / `#2E2D2A` | Headings / body text |
| `--muted` / `--faint` | `#A3A2A0` / `#6F6E6C` | `#5E5D59` / `#8A8984` | Secondary text / labels |
| `--line` / `--line-2` | 8% / 16% white | 9% / 16% black | Dividers / control borders |
| `--fill` / `--fill-ink` | ink / bg | ink / white | Primary button |
| `--accent` | `#CDB287` champagne | `#8A6A3D` | Small highlights only: link underlines, checkmarks, focus details |
| `--brand-red` | `#D9301E` | same | MyCNBox call to action only |
| `--studio-a/b` | warm light greys | | Background behind every product photo |

- **Type:** Inter. Sizes: h1 `clamp(30,4.6vw,48)`, h2 `clamp(22,2.6vw,28)`, body 16 px, small 13.5 px, labels 11–12 px uppercase with 0.08–0.12em letter spacing. Headings are 700 weight with tight negative letter spacing.
- **Spacing:** a 4 px grid (`--s1` 4 … `--s8` 64).
- **Radius:** controls are pills (`--r-pill`), cards and photos 16 px (`--r-lg`), large panels 22 px (`--r-xl`).

## Rules

1. **The photo is the card.** Product cards have no box, no border and no shadow: a rounded studio-grey photo, then brand (small caps), title (2 lines max) and price under it.
2. **One primary action per view.** It is a solid ink pill (`.btn.light` / `.btn.primary`). Everything else is an outline pill (`.btn`) or a text link.
3. **The red is only for MyCNBox.** Never use it for errors, decoration or other agents.
4. **The gold accent is seasoning.** Use it for underlines, checkmarks and small highlights, never for large fills or body text.
5. **Use borders for structure, shadows for things that float.** Shadows go on menus, popovers and tool panels; dividers are 1 px `--line`.
6. **Numbers use `tabular-nums`.** This covers prices, counts and stats.
7. **Motion:** 150 ms colour and opacity changes, `scale(.96)` when a button is pressed, and a 4% photo zoom on hover. Nothing animates on page load. Respect `prefers-reduced-motion`.
8. **Every colour comes from a token.** Write no hex codes in page code. Inline styles may use `var(--muted)` and similar.
9. **Sizes:** touch targets are at least 44 px, and inputs use 16 px text so iPhones don't zoom in.
10. **Copy:** short, plain and factual. Make no claims the data can't back up.

## Components in `ds.css`

`header.h` (sticky glass bar with logo, nav and CTA) · `.btn` (`.light`/`.primary`, `.red`, `.sm`) · `.bc` breadcrumbs · `.lead` · `.prose` · `.facts` · `.chips` · `.note` · `.eyebrow` · `.g` grid + `.c` card (`.ci` photo, `.qb` QC badge, `.cb` text) · `.pg` pager · product page (`.pd`, `.pimg`, `.qcs`, `.price`, `.buy`, `dl.kv`) · `.steps` · `.faq` · `.tool` · `footer.f`.
