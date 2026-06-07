# iMining ATLAS — Style Guide

This document is the source of truth for visual language, components, and patterns when building the iMining ATLAS app. Drop this file into the project root as `CLAUDE.md` (or read it explicitly) so Claude Code uses it as context for every change.

---

## 1. Product context

ATLAS is an **asset management** app for iMining. It serves both internal staff and external customers, and centralizes:

- **Asset register** — master list of equipment/assets with latest status
- **Sites** — physical locations where assets are deployed
- **Maintenance history** — work logs, QC logs from production, breakdown reports
- **Tickets** — service requests, issues, and active jobs (open / scheduled / in progress / completed)
- **Inventory** — parts and spares
- **Reports** — analytics, breakdown stats, exports
- **Dashboards** — sliced by site or purpose

Users are operations, maintenance, and QC staff. They are **data-heavy** users on desktop primarily, but the app must also work on tablets in the field. Optimize for **scannability, density, and trustworthiness** over visual flourish.

---

## 2. Brand identity

ATLAS OPS is the product. iMining is the parent. The visual identity has **three marks expressed at different scales** — the globe motif is the connective tissue running through all of them.

| Mark | When to use | Files |
|------|-------------|-------|
| **App icon** — "i" with globe-as-dot | PWA launch screen, favicon, app stores, mobile home screen, browser tab, anywhere the brand appears at ≤256px | `atlas-icon-master.svg` (default with navy bg), `atlas-icon-no-bg.svg`, `atlas-icon-favicon.svg` (≤48px simplified), `atlas-icon-maskable.svg` (Android PWA) |
| **Wordmark** — "ATLAS OPS" with globe-as-O | Login page hero, marketing pages, deck title slides, docs header, email signatures, large brand moments | `Wordmark/atlas-ops-wordmark.svg` — all-orange, works on both light and dark surfaces |
| **Short name** — "ATLAS" | In-app sidebar header (paired with app icon), page titles, browser title, casual references in UI copy | Set as text using `font-family: Inter; font-weight: 800`. Paired with the app icon at 24-36px when used as a brand element. |

**The globe lives everywhere.** Same composition (ring + subtle equator + meridian + one primary pin + three supporting pins) appears in three places:

1. As the **dot of the 'i'** in the app icon
2. As the **O in OPS** in the wordmark
3. As a **simplified single-pin variant** in the favicon

Anywhere you'd otherwise reach for a generic logo placeholder, pick the right mark for the size and context — never a fourth invented mark.

**Parent attribution** appears as a footer or sub-element: "An iMining product" with the iMining 'i' inline, or the full iMining wordmark from `/iMining Logo - Web/`. Use it on the login page, in the about screen, and in email footers.

**Tone:** Industrial, confident, calm. Not playful. Not corporate-sterile either — the warm orange keeps it human.

---

## 3. Color tokens

### 3.1 Brand palette (from iMining CI)

| Name        | Hex       | Role                                          |
|-------------|-----------|-----------------------------------------------|
| `navy`      | `#002741` | Primary dark — nav rail, headings, dark bg    |
| `orange`    | `#F7941D` | Primary action / brand accent                 |
| `peach`     | `#FCBA63` | Secondary accent / hover highlight            |
| `cream`     | `#FFDAA2` | Tertiary accent / soft fills                  |

### 3.2 Neutrals (for surfaces, text, borders)

| Name            | Hex       | Role                                  |
|-----------------|-----------|---------------------------------------|
| `ink`           | `#0F1924` | Primary text on light                 |
| `ink-2`         | `#1F2937` | Secondary text                        |
| `muted`         | `#6B7785` | Tertiary text / labels / captions     |
| `line`          | `#E6EAEE` | Borders, dividers                     |
| `surface`       | `#FFFFFF` | Card / panel background               |
| `surface-2`     | `#F6F7F9` | Page background                       |
| `surface-3`     | `#EEF1F4` | Subtle fills (table stripe, chip bg)  |

### 3.3 Semantic / status colors

Used for asset/work-order status badges, alerts, and toasts. Chosen to be visually distinct from the brand orange.

| Name         | Hex       | Use                                              |
|--------------|-----------|--------------------------------------------------|
| `success`    | `#16A34A` | Operational, passed QC, completed                |
| `warning`    | `#EAB308` | Maintenance due, attention needed                |
| `danger`     | `#DC2626` | Breakdown, failed QC, overdue                    |
| `info`       | `#2563EB` | Neutral notice                                   |

**Important:** `warning` is more yellow than the brand orange — never use brand orange for warning states; it must always read as the action/brand color, not as a status.

### 3.4 Tailwind config

Drop this into `tailwind.config.js`:

```js
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          navy:   '#002741',
          orange: '#F7941D',
          peach:  '#FCBA63',
          cream:  '#FFDAA2',
        },
        ink:     { DEFAULT: '#0F1924', 2: '#1F2937' },
        muted:   '#6B7785',
        line:    '#E6EAEE',
        surface: { DEFAULT: '#FFFFFF', 2: '#F6F7F9', 3: '#EEF1F4' },
        status: {
          success: '#16A34A',
          warning: '#EAB308',
          danger:  '#DC2626',
          info:    '#2563EB',
        },
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '10px',
        lg: '16px',
        xl: '20px',
        '2xl': '28px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,25,36,0.04), 0 1px 3px rgba(15,25,36,0.06)',
        pop:  '0 12px 32px -8px rgba(0,39,65,0.25)',
      },
    },
  },
};
```

### 3.5 CSS variables (non-Tailwind fallback)

```css
:root {
  --brand-navy: #002741;
  --brand-orange: #F7941D;
  --brand-peach: #FCBA63;
  --brand-cream: #FFDAA2;

  --ink: #0F1924;
  --ink-2: #1F2937;
  --muted: #6B7785;
  --line: #E6EAEE;
  --surface: #FFFFFF;
  --surface-2: #F6F7F9;
  --surface-3: #EEF1F4;

  --success: #16A34A;
  --warning: #EAB308;
  --danger:  #DC2626;
  --info:    #2563EB;

  --radius-sm: 6px;
  --radius:    10px;
  --radius-lg: 16px;
  --shadow-card: 0 1px 2px rgba(15,25,36,0.04), 0 1px 3px rgba(15,25,36,0.06);
}
```

---

## 4. Typography

- **Sans:** Inter (load from Google Fonts or self-host). Falls back to `system-ui`.
- **Mono:** JetBrains Mono — for asset IDs, codes, timestamps, and any tabular numeric data.

### Scale

| Token       | Size / line-height | Weight | Use                                  |
|-------------|--------------------|--------|--------------------------------------|
| `display`   | 32px / 1.15        | 700    | Page hero (rare)                     |
| `h1`        | 24px / 1.25        | 700    | Page title                           |
| `h2`        | 20px / 1.3         | 600    | Section heading                      |
| `h3`        | 16px / 1.4         | 600    | Subsection / card title              |
| `body`      | 14px / 1.55        | 400    | Default body text                    |
| `body-lg`   | 16px / 1.55        | 400    | Marketing / long-form                |
| `small`     | 13px / 1.5         | 400    | Captions, meta, table cells          |
| `xs`        | 12px / 1.45        | 500    | Labels, tags                         |
| `xxs`       | 11px / 1.4         | 600    | Uppercase eyebrows (`letter-spacing: 0.05em; text-transform: uppercase`) |

**Numeric data:** always use `font-variant-numeric: tabular-nums` in tables and dashboards so columns of numbers align.

---

## 5. Spacing scale

4px-based scale. Tailwind defaults align to this — prefer Tailwind classes over raw values.

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96`

- **Inline gap inside a component:** 8 or 12
- **Between related elements in a card:** 12 or 16
- **Between sections:** 24 or 32
- **Page edge padding:** 24 (mobile) / 32 (tablet) / 48 (desktop)

---

## 6. Shape language

- **Inputs / buttons:** 8px radius (`rounded-md`)
- **Cards / panels:** 10px radius (`rounded`)
- **Modals / large surfaces:** 16-20px radius (`rounded-lg` / `rounded-xl`)
- **Badges / pills:** fully rounded (`rounded-full`)
- **App icon container:** 28px radius at 512px — matches iOS app icon convention

Never use sharp 0px corners except for full-bleed sections that touch the viewport edge.

---

## 7. Iconography

### Nav icons

7 duotone SVGs in `Nav Icons/` covering all main sections. Use them at **22-24px** in the sidebar.

```
nav-01-dashboard.svg     · Dashboard / overview
nav-02-assets.svg        · Asset register (tag motif)
nav-03-sites.svg         · Locations (pin motif)
nav-04-maintenance.svg   · Maintenance history (wrench)
nav-05-tickets.svg       · Service requests / jobs (ticket stub)
nav-06-inventory.svg     · Parts/spares (3D box)
nav-07-reports.svg       · Analytics (bar chart)
```

**Style:** Solid orange `#F7941D` shape + peach `#FCBA63` accent. Never recolor them outside the brand palette. If you need a "muted" version for an inactive state, drop the opacity to 0.55 — do not change colors.

### Other icons

For glyphs not in the nav set (close, chevrons, search, filter, etc.), use **Lucide** (`lucide-react`). Stroke icons at `1.75px` weight, in `currentColor`. Set `color: var(--ink)` or the contextual text color.

Do **not** mix multiple icon families. Lucide + the custom nav icons is the only combination.

---

## 8. Components

### 8.1 Buttons

```
Primary       bg: orange       text: white       hover: brand-peach (full opacity)
Secondary     bg: surface-3    text: ink         border: line
Ghost         bg: transparent  text: ink         hover bg: surface-3
Destructive   bg: danger       text: white       hover: 90% opacity
Link          bg: none         text: orange      underline on hover
```

- Height: 36px (default), 32px (compact), 44px (large/CTA)
- Horizontal padding: `px-4` default
- Border radius: 8px
- Focus ring: 2px orange outline with 2px offset (`focus:ring-2 focus:ring-brand-orange focus:ring-offset-2`)

### 8.2 Inputs

- Background `surface`, border `line` (1px), text `ink`
- Padding: `px-3 py-2`, height 36px to match buttons
- Focus: border becomes `brand-orange`, no inner glow
- Placeholder color: `muted`
- Labels: 13px `muted` above the input with 4px gap

### 8.3 Cards

- Background `surface`, border `1px line`, radius 10px, shadow `card`
- Inner padding: 20px (default) or 16px (compact)
- Title: `h3` style, with optional eyebrow above (`xxs` style)

### 8.4 Tables (critical — asset register is the heart of the app)

- Header: `surface-3` background, `xxs` uppercase labels, `muted` text
- Row height: 44px (default), 36px (dense)
- Row divider: 1px `line` between rows
- Hover: row background becomes `surface-2`
- Selected: row background `rgba(247,148,29,0.08)` and left border 2px orange
- Numeric columns: right-aligned, tabular-nums
- Asset IDs: mono font, `ink-2` color
- Status column: use a status badge (see 8.5)
- Empty state: centered message with a soft illustration and a primary CTA

### 8.5 Status badges

Pill shape (`rounded-full`), 22-24px tall, 10-12px horizontal padding, 12px text, 600 weight, with a small dot before the label.

```
Operational     bg: success/10   text: success   dot: success
Due soon        bg: warning/12   text: warning-700  dot: warning
Overdue / down  bg: danger/10    text: danger    dot: danger
Decommissioned  bg: surface-3    text: muted     dot: muted
```

Use `Operational` as the default green for assets in good standing. Be sparing with colored badges in a dense table — too many colored pills next to each other becomes noise.

### 8.6 Forms

- One column on mobile, two columns on desktop where labels are short
- Field gap: 16px vertical
- Required indicator: orange asterisk (`*`) after the label
- Error: 1px `danger` border, error message below in `danger` color, 12px
- Helper text: below input, `muted` 12px

### 8.7 Modals

- Backdrop: `rgba(0, 39, 65, 0.5)` (navy at 50%)
- Modal surface: white, radius 20px, shadow `pop`
- Width: 480px (default), 640px (form), 960px (full content)
- Header has 20px padding, body 24px padding, footer 16-20px with right-aligned actions

### 8.8 Tabs

- Underline style: 2px orange underline on active tab
- Inactive tab text: `muted`; active: `ink`
- Tab row sits on `line` 1px bottom border

---

## 9. Layout

### Primary app layout

```
┌────────────────────────────────────────────────────────────┐
│  ╔═══════╗                                                 │
│  ║ ATLAS ║  Top bar: search · notifications · user menu    │
│  ╠═══════╣────────────────────────────────────────────────┤
│  ║       ║                                                 │
│  ║ Nav   ║         Main content                            │
│  ║ (260) ║                                                 │
│  ║       ║                                                 │
│  ╚═══════╝                                                 │
└────────────────────────────────────────────────────────────┘
```

- **Sidebar:** 260px wide, `brand-navy` background, fixed left
- **Top bar:** 56px tall, white, 1px bottom border `line`
- **Main:** `surface-2` background, 32-48px padding

### Sidebar pattern

- Logo at top: 36-40px icon + ATLAS wordmark
- Nav items: 22px icon + label, 10-12px padding, 8px gap, 2px between items
- Active state: tinted orange background `rgba(247,148,29,0.14)`, white label, 4px orange right-edge accent bar
- Inactive state: `rgba(255,255,255,0.72)` label
- Hover: background `rgba(255,255,255,0.06)`

### Page content patterns

- **Index pages (Assets, Sites, etc.):** Page title + filter row + table + pagination
- **Detail pages:** Breadcrumb + entity header (name, status badge, primary action) + tabbed content (Overview, History, Maintenance, Documents)
- **Dashboard:** Grid of KPI cards across the top, then 2-column grid of charts and lists below

---

## 10. Dark mode

Defer dark mode to v2. The brand reads as a light-mode-first product (white surfaces, navy nav, orange accents). If implementing later:

- Page background: `#0B1726` (slightly darker than brand-navy for contrast)
- Surface: `brand-navy` `#002741`
- Surface-2: `#06304E`
- Text: white `rgba(255,255,255,0.92)`
- Muted: `rgba(255,255,255,0.55)`
- Lines: `rgba(255,255,255,0.10)`
- Brand orange and status colors stay the same (they hold up on dark)

---

## 11. Motion

Be restrained — this is a data app, not a marketing site.

- Hover transitions: 120ms ease-out
- Modal open: 180ms ease-out, slight scale (0.97 → 1) + fade
- Toast slide-in: 240ms ease-out
- Avoid layout-shifting animations on data load — use skeletons instead

---

## 12. Accessibility

- **Contrast:** body text on surface ≥ 7:1, large text ≥ 4.5:1. Brand orange on white is 3.0:1 — only use it for icons, illustrations, and large/bold elements, **never small body text on white**.
- **Focus rings:** always visible, never `outline: none` without a replacement. Use `focus-visible` so it doesn't appear on mouse clicks.
- **Status not by color alone:** every status badge has a text label and an icon/dot — never communicate state with color only (color-blind users + dense tables).
- **Forms:** label every input, associate errors with `aria-describedby`, never use placeholder as label.

---

## 13. Asset / domain conventions

- **Asset IDs** are mono-font, uppercase, with a tag glyph prefix in detail pages.
- **Dates** in tables: `DD MMM YY` (e.g., `12 Mar 26`). Detail pages may use `DD MMM YYYY, HH:mm`.
- **Numeric ranges** use `–` (en-dash) not `-`. Currencies use the configured locale.
- **Empty states** name what's missing and offer a primary action ("No assets here yet — Add asset").
- **Loading**: skeletons (1.2s shimmer) over spinners for content. Spinners only for sub-second action feedback.

---

## 14. Do / Don't

**Do**
- Use Tailwind utility classes; extract to components only when a pattern repeats 3+ times.
- Keep tables dense — operations users want to see more rows, not bigger ones.
- Show status with both color *and* label.
- Use the nav icon set for the seven main sections; Lucide for everything else.
- Render numeric data right-aligned with `tabular-nums`.

**Don't**
- Don't introduce new colors. If you need a tint, derive it from the palette (e.g., `orange/10`).
- Don't use brand orange for warning/danger states.
- Don't use icon-only buttons without an `aria-label`.
- Don't mix more than two icon families (custom nav set + Lucide is the rule).
- Don't add drop shadows beyond `shadow-card` and `shadow-pop`.
- Don't use border radius > 28px outside the app icon itself.

---

## 15. File / folder conventions

```
src/
  app/                 # routes (Next.js app dir) or pages
  components/
    ui/                # primitives — Button, Input, Badge, Card, Modal, Tabs
    layout/            # Sidebar, TopBar, PageHeader, EmptyState
    domain/            # Asset-, Ticket-, Site- specific composites
  lib/                 # utilities (date formatting, fetch wrappers)
  styles/              # tailwind base + globals.css
  assets/
    brand/             # app icon SVGs (master, no-bg, favicon, maskable)
    wordmark/          # ATLAS OPS wordmark SVGs (light + inverted)
    nav/               # nav-01 ... nav-07 SVGs
```

- Components are PascalCase. Files match component name. One default export per file unless co-locating.
- Tailwind classes preferred in JSX. Use `@apply` sparingly, only in `globals.css` for true base styles.

---

## 16. When adding new patterns

If you find yourself building something this guide doesn't cover (a new component, a new layout, a new color), **stop and ask before inventing**. Brand consistency is fragile — one off-palette button across the app erodes the whole identity. Add the new pattern to this file as part of the same PR that introduces it.
