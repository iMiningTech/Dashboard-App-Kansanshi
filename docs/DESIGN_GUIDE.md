# MMU Operations — Design Guide (preliminary)

> Starting point for a fuller style guide. Captures the stack, brand system, and the
> design rules already followed across the Kansanshi MMU dashboard, its PDF reports, and
> its emails — so they can be standardised as the template for future iMining customer
> dashboards. Feed this to a design pass to expand into a full style guide.

## 1. Product & principle
A mining-operations analytics dashboard (Orica @ Kansanshi). **iMining drives the theme;
the customer appears only as a logo** — so spinning up a new customer means swapping the
logo and palette, nothing structural. Audience is mine operations management: the design
favours *decision-first clarity* over decoration.

## 2. Stack
- **Front-end:** Next.js (app router, static export) · React · TypeScript · Tailwind ·
  Recharts · lucide-react icons. Hosted on S3 + CloudFront.
- **Reports:** the same app rendered in a print layout, captured to PDF by headless
  Chrome (Puppeteer). **A4 is not a hard constraint** — optimise for looking good; users
  fit-to-page when printing.
- **Emails:** table-based HTML with inline styles (the only thing email clients render
  reliably), logo embedded via CID.
- Brand tokens are CSS variables in `web/app/globals.css`; data colours in `web/lib/colors.ts`.

## 3. Brand palette
| Token | Hex | Use |
|---|---|---|
| iMining Navy | `#002841` | Primary — headings, text, sidebar, email/report header band |
| iMining Orange | `#f5911e` | Accent — the single thing to act on, pills, rules, "Waiting on mine" |
| OK / green | `#59A14F` | Good / target met |
| Warn / amber | `#f5911e` | Caution |
| Bad / red | `#E15759` | Genuine exceptions only (breakdowns, violations) |
| App background | `#f4f7f9` | Page bg |
| Surface | `#ffffff` | Cards |
| Muted text | `#647682` | Secondary text |

There's a 15-colour **MASTER_PALETTE** (Tableau-derived) for when a chart genuinely needs
many distinct series, plus fixed per-activity and per-category colour maps so the same
activity is always the same colour everywhere.

## 4. The chart design rules (the opinionated part)
These were applied deliberately — keep them:
1. **One colour, not a rainbow.** Categorical bars use a single brand navy, with the
   single *actionable* bar (the max/outlier) in orange, and inline value labels. Colour
   only carries meaning where it must (e.g. RAG compliance, or encoded categories).
2. **Reserve red.** Red means a real exception (breakdown, safety violation) — never
   "this bar is just the biggest".
3. **Performance vs target, not a sea of red.** Utilisation shows neutral bars + a dashed
   target line, turning green only when target is beaten — normal days don't read as alarms.
4. **Status-aware KPI tiles.** A coloured top-accent (ok/warn/bad) + value tint; tiles are
   clickable to drill in (click-hints stripped in print).
5. **The "responsibility lens"** — the signature exhibit. Every logged hour is bucketed by
   *who owns the time* into one stacked bar: Productive · Movement · Safety/Admin ·
   **Waiting on mine** (brand amber — the client exhibit, defended separately from idle) ·
   Idle/Standby (neutral grey) · Breakdown (red). Order is fixed left→right.
6. **Pies/donuts:** inside-slice % labels in print (clip-safe), a wrapping multi-line
   legend, small slices (<5–7%) drop their label.
7. **Sentence-case titles, right-aligned numeric table columns, collapse n=1 charts to a
   centred stat** (a lone full-width bar reads oddly).
8. **Site time everywhere.** All timestamps render in Kansanshi time (Africa/Lusaka, UTC+2),
   never the viewer's zone.

## 5. Report (PDF) design language
- Per-page header = **navy band** (iMining white logo left, orange report-type pill right)
  → **orange accent rule** → white title row ("MMU Operations — Kansanshi · <tab>", date
  range, "Generated … · Powered by iMining") with the **Orica logo** on the right. The
  Orica logo can't sit on navy (its own navy clashes), hence Orica-on-white below the band.
- Compact, dense, professional: tight card padding, small table type, single-line rows,
  KPI tiles in one row.
- One report section per page; charts pinned to a fixed width for deterministic rendering
  (see `CLAUDE.md` → `PRINT_CHART_W`).

## 6. Email design language
- 600px centred card. **Navy header band** (white iMining logo + orange report-type pill)
  → orange accent rule → white body (title, date range, one-line body) → footer ("Powered
  by iMining" + one-click unsubscribe). Logo embedded via CID so it shows with images off.
- Same navy/orange/pill language as the report header — the two are intentionally consistent.

## 7. What to standardise next (for the full style guide)
- Type scale & spacing tokens (currently Tailwind defaults + ad-hoc print sizes).
- Component inventory (Card, Stat, ChartCard, BarH/BarV/StackedBar/Donut/AreaTrend,
  HourHeatmap, ResponsibilityBar) with usage rules.
- A documented "new customer" checklist (logo, palette, customer/site name, data API).
- Iconography conventions (lucide), empty-state patterns ("none logged"), and the
  click-to-drill interaction model.
