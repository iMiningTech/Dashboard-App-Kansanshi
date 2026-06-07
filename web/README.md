# Kansanshi Dashboard — Web (React / Next.js)

Professional front-end for the Kansanshi MMU operations data, reading the data
API (`docs/API.md` in the Jotform-AWS-API repo). Static-exported — drops onto
S3 + CloudFront. Auth is handled by iMining's site/edge (this app is gated by
your existing login; see "Hosting & security" below).

Stack: Next.js 14 (app router, static export) · Tailwind · lucide icons ·
Recharts. Brand tokens are CSS variables in `app/globals.css` — swap the CI
there, nothing else changes.

## Run locally
```bash
cd web
cp .env.local.example .env.local      # API base is prefilled
npm install
npm run dev                            # http://localhost:3000
```
It reads live data from the API immediately.

## Build (static) for hosting
```bash
npm run build        # outputs ./out  (static site)
```

## Hosting & security (for the iMining devs)
1. Upload `out/` to an S3 bucket, front it with CloudFront (HTTPS).
2. **Gate it behind iMining login** — iframe it into the authenticated site, or
   put Cognito/Lambda@Edge auth on the CloudFront distribution.
3. **Lock the data API perimeter too** (it's the real boundary): set the API's
   `ApiToken` and pass it as `NEXT_PUBLIC_API_TOKEN`, and/or restrict the API's
   `AllowedOrigin` to your domain, and/or proxy the API through your backend.

## Structure
```
app/layout.tsx   shell (sidebar, header, branding)
app/page.tsx     Overview: KPIs, activity-by-category chart, fleet status grid
lib/api.ts       typed client for the data API
components/ui.tsx shadcn-style primitives (Card, Stat, Badge) — reuse/extend
app/globals.css  brand tokens (swap CI here)
```

## Adding a dashboard/widget (the standard)
1. Add a typed call in `lib/api.ts` (or reuse `api.dashboard()`).
2. Build a component from the `components/ui.tsx` primitives + a Recharts chart.
3. Drop it into a page. No data logic in the front-end — that lives in the API.
