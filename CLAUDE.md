# Kansanshi Dashboard — orientation (read me first)

Front-end + data-amalgamation for the Orica/Kansanshi **MMU Operations** dashboard.
It reads the data API served by the separate **`Jotform-AWS-API`** repo.

## ⚠️ Live vs legacy — read this first
This repo contains two generations of code. Don't confuse them:

| Path | Status | What it is |
|---|---|---|
| **`web/`** | **LIVE** — this is the dashboard | Next.js static-export app (the thing on CloudFront) |
| `precompute/` | **LIVE** | Lambda that amalgamates DynamoDB submissions → dashboard JSON in S3 |
| `src/`, `dashboard.py`, top-level `README.md` | **LEGACY** | Original Streamlit/CSV-normalizer tool. The Python in `src/` is **reused by `precompute/`** (vendored in at build), so it's not dead — but the Streamlit app itself is superseded by `web/`. |

The top-level `README.md` describes the *legacy CSV tool* — ignore it for the live app.
For the web app, read `web/README.md` and this file.

## Data flow (end to end)
```
JotForm ▶ ingest Lambda ▶ DynamoDB submissions        (Jotform-AWS-API repo)
                              │
            precompute Lambda │ (this repo, precompute/) reuses src/ Python pipeline
                              ▼
              S3  dashboard/<window>/{timeline,prestart,exceptions,meta}.json
                              │
                  data API    │ (Jotform-AWS-API repo, api/) GET /dashboard?window=…
                              ▼
                  web/ Next.js app (Recharts) ──renders──▶ browser + PDF reports
```
- **Live tiles & shift timeline** read DynamoDB directly via the API (`/live/*`,
  `/assets`) — real-time. **Everything else** (charts, KPIs, date bounds) reads the
  **precomputed** JSON, which lags by the precompute cadence.

## `precompute/` — the amalgamation Lambda
- Windows: `ROUTINE = 7d,30d,mtd` (refreshed on every submission via an SQS nudge) and
  `ALL = 7d,30d,90d,mtd` (refreshed by a 30-min EventBridge backstop — the only path
  that refreshes the heavy `90d`).
- **GOTCHA (fixed, keep it fixed):** the skip-guard must compare `newest_received`
  against the **stalest** of the windows being generated — NOT `windows[0]`. Guarding on
  `windows[0]` (=`7d`, kept fresh by the nudge) made the backstop skip forever and `90d`
  silently froze. The dashboard derives its date bounds from `90d`, so a stale `90d`
  makes "today" show no data. See `lambda_handler` in `precompute/lambda_function.py`.
- Reserved concurrency 1 (debounce). A manual invoke can hit
  `ReservedFunctionConcurrentInvocationLimitExceeded` — retry or use `--invocation-type Event`.
- Force a refresh: `aws lambda invoke --function-name orica-kansanshi-jotform-precompute-prod --payload '{"windows":["90d","30d","mtd"],"force":true}' --cli-binary-format raw-in-base64-out /tmp/pc.json`
- Deploy needs the pandas layer ARN: `make vendor && sam build && sam deploy --config-env prod --parameter-overrides "Environment=prod PandasLayerArn=arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:31"`

## `web/` — the Next.js app
- Stack: Next.js (app router, **static export** → `web/out/`), React, Tailwind, Recharts,
  lucide. Brand tokens are CSS variables in `app/globals.css`.
- `app/page.tsx` is one large client component holding **all** views (Overview, Operator
  Metrics, MMU Utilization, Faults & Breakdowns, Shift Performance, Shift Timeline) plus
  the report/print layout (`PrintReport`). `components/charts.tsx` + `ui.tsx` are the
  shared chart/primitive library. `lib/`: `api.ts` (typed API client), `colors.ts` (brand
  palette + responsibility buckets), `data.ts` (filtering/grouping), `utils.ts`
  (`fmtTime`), `print-context.ts` (PrintContext).
- Env (`web/.env.local`): `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_REPORT_API`,
  `NEXT_PUBLIC_SUBSCRIBE_API` (and optional `NEXT_PUBLIC_API_TOKEN`).
- Run locally: `cd web && npm install && npm run dev`. Build: `npm run build` → `web/out/`.

### Report / print mode
- The same app renders the PDF reports: visiting `?print=1&tabs=…&from=…&to=…&mmus=…&kind=…`
  triggers `PrintReport` (branded paged layout) instead of the app shell. The
  `Jotform-AWS-API` render service drives this URL in headless Chrome. `kind` ∈
  `daily|weekly|monthly|operator|custom` drives the header pill + whether live tiles show.
- **GOTCHA — chart width (`PRINT_CHART_W` in `components/charts.tsx`):** Recharts'
  `ResponsiveContainer` auto-measure is unreliable in the headless PDF renderer, so in
  print every chart is pinned to a **fixed px width** (`1040`), measured from the actual
  PDF. This is **coupled to the render service's 1240px viewport**. If you change the
  render viewport (or page margins), re-measure: render a PDF at 150dpi, measure
  card-content vs chart-content widths, update `PRINT_CHART_W`. Don't guess.
- Report header = "Option A": navy iMining band + orange pill + orange rule, then a white
  title row with the Orica logo (`.report-*` classes in `globals.css`). Mirrors the email.

## Hosting (S3 + CloudFront)
- `hosting/template.yaml` (private S3 + CloudFront with Origin Access Control) +
  `hosting/deploy.sh` (builds `web/`, deploys the stack, syncs `web/out`, invalidates).
- Deploy: `AWS_PROFILE=imining-dev ./hosting/deploy.sh`. Live: `https://d23k4zb8uvf2si.cloudfront.net`.
- Auth/gating is handled at the edge/site level (the app itself is unauthenticated). The
  data API is the real perimeter — lock its `AllowedOrigin`/`ApiToken` once gated.

## Other gotchas
- **Timezone:** `fmtTime` (`lib/utils.ts`) renders all timestamps in **Kansanshi time
  (Africa/Lusaka, UTC+2)**, never the viewer's local zone — so site time is consistent.
- **Test data** is hidden by default; add `?dev` to the URL to reveal the toggle. The
  filter matches "test" or exactly "justin james".
- Date picker is capped at today and 90 days back (matches the data window).
- See also `docs/AWS_DASHBOARD_SETUP.md` and `JOTFORM_DATA_CONTEXT.md` (data field reference).
- Design language / brand rules: `docs/DESIGN_GUIDE.md`.
