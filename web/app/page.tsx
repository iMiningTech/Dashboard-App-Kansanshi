"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import {
  LayoutDashboard, AlertCircle, AlertTriangle, BarChart3, ClipboardCheck, Timer, CalendarRange,
  User, Activity, RefreshCw, Truck,
} from "lucide-react";
import { api, type DashboardData, type MmuStatus, type PrestartRow, type Asset } from "@/lib/api";
import { Card, CardBody, Stat, Badge } from "@/components/ui";
import { ChartCard, BarH, BarV, StackedBar, Donut, AreaTrend, DataTable } from "@/components/charts";
import {
  filterTimeline, filterPrestart, sessionSummary, sessionsWithEnd, activityTimeline,
  kpis, uniqueSorted, groupSum, groupCount,
} from "@/lib/data";
import { ACTIVITY_COLOURS, CATEGORY_COLOURS, BUCKET_COLOURS, ACTIVITY_BUCKET, MASTER_PALETTE, paletteMap, activityColour } from "@/lib/colors";
import { fmtTime } from "@/lib/utils";

const VIEWS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "logouts", label: "Operator Metrics", icon: User },
  { id: "util", label: "MMU Utilization", icon: BarChart3 },
  { id: "prestart", label: "Faults & Breakdowns", icon: ClipboardCheck },
  { id: "perf", label: "Shift Performance", icon: Timer },
  { id: "timeline", label: "Shift Timeline", icon: CalendarRange },
] as const;
type ViewId = (typeof VIEWS)[number]["id"];

// Pivot grouped (x, series) sums into [{x, seriesA, seriesB,...}] + series list.
function pivot<T>(rows: T[], xKey: (r: T) => string, sKey: (r: T) => string, val: (r: T) => number) {
  const xs: string[] = []; const ss = new Set<string>();
  const m = new Map<string, Record<string, number | string>>();
  for (const r of rows) {
    const x = xKey(r), s = sKey(r);
    if (!m.has(x)) { m.set(x, { x }); xs.push(x); }
    const row = m.get(x)!;
    row[s] = (Number(row[s]) || 0) + val(r);
    ss.add(s);
  }
  return { data: xs.map((x) => m.get(x)!), series: Array.from(ss) };
}
const round1 = (n: number) => Math.round(n * 10) / 10;
// Inclusive day count between two YYYY-MM-DD strings (e.g. 1 May–30 May = 30).
const rangeDays = (lo: string, hi: string) =>
  lo && hi ? Math.round((Date.parse(hi + "T00:00:00Z") - Date.parse(lo + "T00:00:00Z")) / 86400000) + 1 : 0;
// Internal / QA submissions hidden from the customer view by default: anything
// containing "test" (e.g. "Justin James is testing") plus an explicit list of
// internal/dev names (matched exactly, case-insensitive — so a real operator
// named e.g. "Justin Banda" is NOT filtered).
const INTERNAL_OPERATORS = new Set(["justin james"]);
const isTestOperator = (name?: string | null) => {
  const n = (name || "").trim().toLowerCase();
  return /test/i.test(n) || INTERNAL_OPERATORS.has(n);
};

export default function Dashboard() {
  const [raw, setRaw] = useState<DashboardData | null>(null);
  const [live, setLive] = useState<MmuStatus[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewId>("overview");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [touched, setTouched] = useState(false);  // false = "all" (default); true = explicit selection
  const [hideTest, setHideTest] = useState(true);  // exclude internal test operators from customer view
  const [lo, setLo] = useState("");
  const [hi, setHi] = useState("");
  const [loBound, setLoBound] = useState("");
  const [hiBound, setHiBound] = useState("");

  async function load() {
    setLoading(true); setError(null);
    try {
      const [d, m, a] = await Promise.all([
        api.dashboard("90d"),
        api.liveMmu(),
        api.assets().catch(() => ({ items: [] as Asset[] })), // graceful if not deployed yet
      ]);
      setRaw(d); setLive(m.items || []); setAssets(a.items || []);
      const dates = uniqueSorted((d.timeline || []).map((t) => (t.reporting_date || "").slice(0, 10)));
      const min = dates[0] || "", max = dates[dates.length - 1] || "";
      setLoBound(min); setHiBound(max); setLo(min); setHi(max);
      setSelected(new Set());            // empty = all
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  function applyPreset(days: number | "mtd" | "all") {
    if (!hiBound) return;
    if (days === "all") { setLo(loBound); setHi(hiBound); return; }
    if (days === "mtd") { setLo(hiBound.slice(0, 8) + "01"); setHi(hiBound); return; }
    const d0 = new Date(hiBound + "T00:00:00Z");
    d0.setUTCDate(d0.getUTCDate() - (days - 1));
    setLo(d0.toISOString().slice(0, 10)); setHi(hiBound);
  }

  // The active billed fleet drives the MMU universe; fall back to data-derived
  // list if the assets registry isn't deployed yet.
  const activeSet = useMemo(() => new Set(assets.map((a) => a.fleet_no)), [assets]);
  const allMmus = useMemo(
    () => (assets.length
      ? [...assets].sort((a, b) => Number(a.sort_order ?? 999) - Number(b.sort_order ?? 999)).map((a) => a.fleet_no)
      : uniqueSorted((raw?.timeline || []).map((t) => t.mmu_id))),
    [assets, raw]
  );
  // Until the user touches the filter, "all" is selected. Then it's explicit
  // (empty = none). Always intersected with the active billed fleet.
  const effectiveSel = useMemo(() => (touched ? selected : new Set(allMmus)), [touched, selected, allMmus]);
  const effMmus = useMemo(
    () => (activeSet.size ? new Set([...effectiveSel].filter((m) => activeSet.has(m))) : effectiveSel),
    [effectiveSel, activeSet]
  );

  // Operator names are not case-sensitive ("Justin" and "justin" are one person).
  // Canonicalise every operator name to the most common spelling seen, so all
  // grouping/filtering downstream treats variants as a single operator.
  const canonOp = useMemo(() => {
    const counts = new Map<string, Map<string, number>>();
    const tally = (n?: string | null) => {
      const s = (n || "").trim();
      if (!s) return;
      const k = s.toLowerCase();
      const m = counts.get(k) || new Map<string, number>();
      m.set(s, (m.get(s) || 0) + 1);
      counts.set(k, m);
    };
    for (const r of raw?.timeline || []) tally(r.operator_name);
    for (const r of raw?.prestart || []) tally(r.operator_name);
    const out = new Map<string, string>();
    for (const [k, m] of counts) {
      let best = "", bc = -1;
      for (const [sp, c] of m) if (c > bc || (c === bc && sp < best)) { best = sp; bc = c; }
      out.set(k, best);
    }
    return (n?: string | null) => out.get((n || "").trim().toLowerCase()) ?? (n || "");
  }, [raw]);

  const d = useMemo(() => {
    // Internal/QA submissions are excluded from the customer view by default;
    // the sidebar toggle exposes them when needed. Operator names canonicalised.
    const cn = <T extends { operator_name?: string }>(r: T): T => ({ ...r, operator_name: canonOp(r.operator_name) });
    const keep = (r: { operator_name?: string }) => !hideTest || !isTestOperator(r.operator_name);
    const tlSrc = (raw?.timeline || []).filter(keep).map(cn);
    const psSrc = (raw?.prestart || []).filter(keep).map(cn);
    const tl = filterTimeline(tlSrc, effMmus, lo || "0000", hi || "9999");
    const ps = filterPrestart(psSrc, effMmus, lo || "0000", hi || "9999");
    const sessions = sessionSummary(tl);
    const ended = sessionsWithEnd(tl);
    const noEnd = sessions.filter((s) => !s.clocked_out);
    const act = activityTimeline(tl);
    return { tl, ps, sessions, ended, noEnd, act, k: kpis(tl, ps) };
  }, [raw, effMmus, lo, hi, hideTest, canonOp]);

  function toggleMmu(m: string) {
    const base = touched ? selected : new Set(allMmus);
    const n = new Set(base);
    if (n.has(m)) n.delete(m); else n.add(m);
    setSelected(n); setTouched(true);
  }
  function selectAll() { setSelected(new Set(allMmus)); setTouched(true); }
  function selectNone() { setSelected(new Set()); setTouched(true); }

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar (iMining navy) ── */}
      <aside className="hidden w-64 shrink-0 flex-col bg-sidebar text-sidebarfg md:flex">
        <div className="flex h-16 items-center gap-2 px-5">
          <Image src="/imining_white.png" alt="iMining" width={240} height={56} style={{ height: 52, width: "auto" }} />
        </div>
        <nav className="px-3">
          {VIEWS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setView(id)}
              className={`mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm ${view === id ? "bg-accent text-white font-medium" : "text-sidebarfg/80 hover:bg-white/10"}`}>
              <Icon size={18} /> {label}
            </button>
          ))}
        </nav>

        {/* Filters */}
        <div className="mt-4 border-t border-white/10 px-4 py-4 text-sm">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-sidebarfg/60">Date range</div>
          <div className="mb-2 flex flex-wrap gap-1">
            {([["7d", 7], ["30d", 30], ["90d", 90], ["MTD", "mtd"], ["All", "all"]] as const).map(([label, v]) => (
              <button key={label} onClick={() => applyPreset(v as number | "mtd" | "all")}
                className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-xs hover:bg-white/15">{label}</button>
            ))}
          </div>
          <div className="mb-4 flex flex-col gap-2">
            <input type="date" value={lo} min={loBound} max={hiBound} onChange={(e) => setLo(e.target.value)}
              className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-sidebarfg" />
            <input type="date" value={hi} min={loBound} max={hiBound} onChange={(e) => setHi(e.target.value)}
              className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-sidebarfg" />
          </div>

          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-sidebarfg/60">
            <span>MMUs</span>
            <span className="flex gap-2 normal-case">
              <button onClick={selectAll} className="text-accent2 hover:underline">All</button>
              <button onClick={selectNone} className="text-accent2 hover:underline">None</button>
            </span>
          </div>
          <div className="max-h-56 space-y-1 overflow-auto pr-1">
            {allMmus.map((m) => (
              <label key={m} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 hover:bg-white/10">
                <input type="checkbox" checked={touched ? selected.has(m) : true} onChange={() => toggleMmu(m)} />
                <span>{m}</span>
              </label>
            ))}
          </div>

          <label className="mt-4 flex cursor-pointer items-center gap-2 border-t border-white/10 pt-4 text-xs text-sidebarfg/80">
            <input type="checkbox" checked={hideTest} onChange={() => setHideTest((v) => !v)} />
            <span>Hide test data</span>
          </label>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-6">
          <div className="flex items-center gap-3">
            <Image src="/orica_logo.png" alt="Orica" width={180} height={56} style={{ height: 48, width: "auto" }} />
            <span className="text-lg font-semibold text-fg">MMU Operations — Kansanshi</span>
          </div>
          <button onClick={load} className="flex items-center gap-1 rounded-xl border border-border px-3 py-1.5 text-sm hover:bg-bg">
            <RefreshCw size={15} /> Refresh
          </button>
        </header>

        <main className="flex-1 overflow-auto p-6">
          {error && <Card><CardBody><div className="flex items-center gap-2 text-danger"><AlertCircle size={18} /> {error}</div></CardBody></Card>}
          {loading ? <div className="text-sm text-muted">Loading…</div> : (
            <div className="space-y-6">
              {view === "overview" && <OverviewView d={d} live={live} assets={assets} prestart={raw?.prestart || []} />}
              {view === "logouts" && <OperatorMetricsView d={d} />}
              {view === "util" && <UtilView d={d} fleet={effMmus.size || allMmus.length} selectedDays={rangeDays(lo, hi)} />}
              {view === "prestart" && <PrestartView d={d} />}
              {view === "perf" && <PerfView d={d} />}
              {view === "timeline" && <TimelineView d={d} selected={effMmus} />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/* ── Site status: one fixed tile per active billed asset, merged with live state ── */
function SiteStatus({ assets, live, prestart }: { assets: Asset[]; live: MmuStatus[]; prestart: PrestartRow[] }) {
  const prestartKeys = new Set(prestart.map((p) => `${p.mmu_id}|${(p.reporting_date || "").slice(0, 10)}`));
  const liveByFleet = new Map(live.map((m) => [m.fleet_no, m]));
  // Base list is the active billed fleet; fall back to live list if the assets
  // registry isn't deployed yet.
  const base: Asset[] = assets.length
    ? [...assets].sort((a, b) => Number(a.sort_order ?? 999) - Number(b.sort_order ?? 999))
    : live.map((m) => ({ fleet_no: m.fleet_no, display_name: m.fleet_no }));

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-fg"><Truck size={16} /> Site Status — current snapshot</div>
      {base.length === 0 ? <div className="text-sm text-muted">No assets configured.</div> : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {base.map((asset) => {
            const m = liveByFleet.get(asset.fleet_no);
            const onShift = (m?.status || "").toUpperCase() === "ON_SHIFT";
            const day = (m?.last_seen || "").slice(0, 10);
            const noPrestart = !!m && !!day && !prestartKeys.has(`${asset.fleet_no}|${day}`);
            return (
              <Card key={asset.fleet_no}>
                <CardBody>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-fg">{asset.display_name || asset.fleet_no}</span>
                    <Badge tone={!m ? "muted" : onShift ? "ok" : "muted"}>
                      {!m ? "No data" : onShift ? "On shift" : "Off shift"}
                    </Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-sm text-muted"><User size={14} /> {m?.operator || m?.operator_last || "—"}</div>
                  <div className="mt-1 flex items-center gap-2 text-sm text-fg"><Activity size={14} className="text-accent" /> {m?.last_activity || "—"}</div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-xs text-muted">{m ? fmtTime(m.last_seen) : "No activity logged"}</span>
                    {noPrestart && (
                      <span className="flex items-center gap-1 text-xs font-medium text-warn" title="No pre-start inspection logged for this shift">
                        <AlertTriangle size={14} /> No pre-start
                      </span>
                    )}
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

type D = {
  tl: ReturnType<typeof filterTimeline>; ps: ReturnType<typeof filterPrestart>;
  sessions: ReturnType<typeof sessionSummary>; ended: Set<string>;
  noEnd: ReturnType<typeof sessionSummary>; act: ReturnType<typeof activityTimeline>;
  k: ReturnType<typeof kpis>;
};

/* ── Overview: site tiles + KPIs + live status pie + activity mix ── */
function OverviewView({ d, live, assets, prestart }:
  { d: D; live: MmuStatus[]; assets: Asset[]; prestart: PrestartRow[] }) {
  // Current fleet status — what each active unit is doing RIGHT NOW (live snapshot).
  const liveByFleet = new Map(live.map((m) => [m.fleet_no, m]));
  const fleet: { fleet_no: string }[] = assets.length ? assets : live.map((m) => ({ fleet_no: m.fleet_no }));
  const stateCount: Record<string, number> = {};
  for (const a of fleet) {
    const m = liveByFleet.get(a.fleet_no);
    const state = !m ? "No data"
      : (m.status || "").toUpperCase() !== "ON_SHIFT" ? "Off shift"
      : (m.last_activity || "On shift");
    stateCount[state] = (stateCount[state] || 0) + 1;
  }
  const statusData = Object.entries(stateCount).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  const statusColors: Record<string, string> = { ...ACTIVITY_COLOURS, "On shift": "#59A14F", "Off shift": "#BAB0AC", "No data": "#D7DBE0" };

  const mix = groupSum(d.act, (r) => r.activity_type || "Other", (r) => r.duration_hours)
    .map((x) => ({ name: x.name, value: round1(x.value) })).sort((a, b) => b.value - a.value);

  return (
    <div className="space-y-6">
      <SiteStatus assets={assets} live={live} prestart={prestart} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Shift sessions" value={d.k.totalSessions} />
        <Stat label="Active MMUs" value={d.k.activeMmus} />
        <Stat label="Missing shift-ends" value={d.k.missingLogouts} sub={`${d.k.missingPct.toFixed(0)}% of sessions`} />
        <Stat label="Pre-start faults" value={d.k.faults} />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Current fleet status" subtitle="What each unit is doing right now (live)">
          <Donut data={statusData} colorMap={statusColors} />
        </ChartCard>
        <ChartCard title="Fleet-wide activity mix" subtitle="Share of logged hours over the selected range">
          <Donut data={mix} colorMap={ACTIVITY_COLOURS} />
        </ChartCard>
      </div>
    </div>
  );
}

/* ── Operator Metrics ──
   Per-operator behaviour over the filtered period: pre-start compliance,
   missing shift-ends, benches loaded, and a per-operator daily shift-quality
   timeline. Pre-start rows carry operator_name, so pre-starts are matched to a
   shift by operator + MMU + reporting date (no cross-shift ambiguity). */
const GREEN = "#59A14F", AMBER = "#F1A340", RED = "#E15759";

function OperatorPicker({ all, selected, onChange }:
  { all: string[]; selected: Set<string>; onChange: (s: Set<string>) => void }) {
  const [open, setOpen] = useState(false);
  const label = selected.size === all.length ? "All operators"
    : selected.size === 0 ? "No operators"
    : `${selected.size} of ${all.length} operators`;
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-1.5 text-sm hover:bg-bg">
        {label} <span className="text-muted">▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute z-20 mt-1 w-64 rounded-xl border border-border bg-surface p-2 shadow-lg">
            <div className="mb-1 flex justify-between px-1 text-xs">
              <button onClick={() => onChange(new Set(all))} className="text-accent hover:underline">All</button>
              <button onClick={() => onChange(new Set())} className="text-accent hover:underline">None</button>
            </div>
            <div className="max-h-64 overflow-auto">
              {all.map((o) => (
                <label key={o} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-bg">
                  <input type="checkbox" checked={selected.has(o)}
                    onChange={() => { const n = new Set(selected); n.has(o) ? n.delete(o) : n.add(o); onChange(n); }} />
                  <span>{o}</span>
                </label>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function OperatorMetricsView({ d }: { d: D }) {
  const allOps = useMemo(() => uniqueSorted(d.sessions.map((s) => s.operator_name)), [d.sessions]);
  const [opSel, setOpSel] = useState<Set<string> | null>(null);  // null = all
  const effOps = opSel ?? new Set(allOps);
  const has = (op?: string | null) => effOps.has(op || "—");

  // Pre-start presence keyed by operator + MMU + reporting date.
  const keyOf = (op?: string | null, mmu?: string | null, date?: string | null) =>
    `${(op || "").trim()}|${(mmu || "").trim()}|${(date || "").slice(0, 10)}`;
  const psKeys = useMemo(() => new Set(d.ps.map((p) => keyOf(p.operator_name, p.mmu_id, p.reporting_date))), [d.ps]);

  const sessions = d.sessions.filter((s) => has(s.operator_name));
  const noEnd = d.noEnd.filter((s) => has(s.operator_name));

  // Per-operator rollup: shifts (logins), pre-starts done, shift-ends done.
  const opMap = new Map<string, { shifts: number; prestart: number; ended: number }>();
  for (const s of sessions) {
    const op = s.operator_name || "—";
    const r = opMap.get(op) || { shifts: 0, prestart: 0, ended: 0 };
    r.shifts++;
    if (psKeys.has(keyOf(s.operator_name, s.mmu_id, s.reporting_date))) r.prestart++;
    if (s.clocked_out) r.ended++;
    opMap.set(op, r);
  }
  const opStats = Array.from(opMap, ([operator, r]) => ({ operator, ...r, compliance: r.shifts ? r.prestart / r.shifts : 0 }));

  const benchAll = d.act.filter((a) => a.activity_type === "Loading Explosives" && has(a.operator_name));
  const benches = benchAll.length;
  const operators = opStats.length;
  const totalShifts = sessions.length;
  const totalPrestart = opStats.reduce((n, o) => n + o.prestart, 0);
  const overallCompliance = totalShifts ? totalPrestart / totalShifts : 0;

  // Operators to follow up: ≥3 shifts and under 60% pre-start compliance.
  const flagged = opStats.filter((o) => o.shifts >= 3 && o.compliance < 0.6).sort((a, b) => a.compliance - b.compliance);

  const byOp = groupCount(noEnd, (s) => s.operator_name || "—").sort((a, b) => a.value - b.value);
  const byDate = groupCount(noEnd, (s) => s.reporting_date || "—").sort((a, b) => a.name.localeCompare(b.name));

  const compBars = opStats.map((o) => ({ name: o.operator, value: Math.round(o.compliance * 100) })).sort((a, b) => a.value - b.value);
  const compColors: Record<string, string> = {};
  compBars.forEach((b) => (compColors[b.name] = b.value < 60 ? RED : b.value < 85 ? AMBER : GREEN));

  const benchByOp = groupCount(benchAll, (a) => a.operator_name || "—").sort((a, b) => b.value - a.value);

  // Single-operator daily shift-quality timeline (the per-operator drilldown).
  const single = effOps.size === 1 ? [...effOps][0] : null;
  const dayMap = new Map<string, { prestart: boolean; ended: boolean }>();
  if (single) {
    for (const s of d.sessions.filter((s) => (s.operator_name || "—") === single)) {
      const day = (s.reporting_date || "").slice(0, 10);
      if (!day) continue;
      const r = dayMap.get(day) || { prestart: false, ended: false };
      if (psKeys.has(keyOf(s.operator_name, s.mmu_id, s.reporting_date))) r.prestart = true;
      if (s.clocked_out) r.ended = true;
      dayMap.set(day, r);
    }
  }
  const dayData = Array.from(dayMap, ([day, r]) => {
    const score = (r.prestart ? 1 : 0) + (r.ended ? 1 : 0);  // 0,1,2
    return { name: day, value: score + 1 };                  // 1=poor, 2=partial, 3=good
  }).sort((a, b) => a.name.localeCompare(b.name));
  const dayColors: Record<string, string> = {};
  const dayLabels: Record<string, string> = {};
  for (const [day, r] of dayMap) {
    dayColors[day] = r.prestart && r.ended ? GREEN : r.prestart || r.ended ? AMBER : RED;
    dayLabels[day] = r.prestart && r.ended ? "Complete"
      : !r.prestart && r.ended ? "No pre-start"
      : r.prestart && !r.ended ? "No shift-end"
      : "Neither";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">Operator filter:</span>
        <OperatorPicker all={allOps} selected={effOps} onChange={setOpSel} />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Operators on shift" value={operators} sub="ran ≥1 shift in range" />
        <Stat label="Benches loaded" value={benches} sub="loading-explosives events" />
        <Stat label="Benches per operator" value={operators ? round1(benches / operators) : 0} />
        <Stat label="Pre-start compliance" value={`${Math.round(overallCompliance * 100)}%`} sub={`${totalPrestart} of ${totalShifts} shifts`} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Missing shift-end logs by operator"><BarH data={byOp} colorMap={paletteMap(byOp.map((x) => x.name))} xLabel="Sessions Without Shift End" yLabel="Operator" /></ChartCard>
        <ChartCard title="Missing shift-end logs by date"><BarV data={byDate} colorMap={paletteMap(byDate.map((x) => x.name))} xLabel="Date" yLabel="Sessions Without Shift End" /></ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Pre-start compliance by operator" subtitle="Share of shifts with a matching pre-start · green ≥85% · amber ≥60% · red <60%">
          <BarH data={compBars} colorMap={compColors} xLabel="Pre-start compliance (%)" yLabel="Operator" />
        </ChartCard>
        <Card>
          <CardBody>
            <div className="mb-1 text-sm font-semibold text-fg">Operators to follow up</div>
            <div className="mb-3 text-xs text-muted">≥3 shifts with under 60% pre-start compliance</div>
            {flagged.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted">No operators flagged — pre-start compliance looks healthy.</div>
            ) : (
              <div className="space-y-2">
                {flagged.map((o) => (
                  <div key={o.operator} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                    <span>{o.operator}</span>
                    <span className="flex items-center gap-2 text-muted">{o.prestart}/{o.shifts} shifts <Badge tone="danger">{Math.round(o.compliance * 100)}%</Badge></span>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <ChartCard title="Benches loaded by operator" subtitle="Each loading-explosives event ≈ one bench loaded">
        <BarH data={benchByOp} colorMap={paletteMap(benchByOp.map((x) => x.name))} xLabel="Benches loaded" yLabel="Operator" />
      </ChartCard>

      {single ? (
        <ChartCard title={`Daily shift quality — ${single}`}
          subtitle="Per day worked · green = pre-start + shift-end done · amber = one missing · red = both missing">
          <BarV data={dayData} colorMap={dayColors} barLabels={dayLabels} xLabel="Date" yLabel="Shift quality (3 = full)" height={300} />
        </ChartCard>
      ) : (
        <Card><CardBody>
          <div className="py-10 text-center text-sm text-muted">Select a single operator in the filter above to see their day-by-day shift-quality timeline.</div>
        </CardBody></Card>
      )}
    </div>
  );
}

/* ── MMU Utilization ── */
function UtilView({ d, fleet, selectedDays }: { d: D; fleet: number; selectedDays: number }) {
  // Distinct days with loading-explosives events, vs the selected range length.
  // Loading is the metric that matters — days with none aren't productive days.
  // Matches the fleet utilization chart below.
  const loadingDays = new Set(
    d.act.filter((r) => r.activity_type === "Loading Explosives").map((r) => (r.reporting_date || "").slice(0, 10)).filter(Boolean)
  ).size;
  const piv = pivot(d.act, (r) => r.mmu_id || "—", (r) => r.activity_type || "Other", (r) => r.duration_hours);
  piv.data.forEach((row) => piv.series.forEach((s) => (row[s] = round1(Number(row[s]) || 0))));
  const colourMap: Record<string, string> = {};
  piv.series.forEach((s, i) => (colourMap[s] = activityColour(s, i)));
  const mix = groupSum(d.act, (r) => r.activity_type || "Other", (r) => r.duration_hours).map((x) => ({ name: x.name, value: round1(x.value) }));
  const daily = pivot(d.act, (r) => (r.reporting_date || "").slice(0, 10), (r) => r.activity_type || "Other", (r) => r.duration_hours);
  daily.data.sort((a, b) => String(a.x).localeCompare(String(b.x)));

  // Loading-explosives fleet utilization: per activity day, how many distinct
  // MMUs logged a Loading Explosives event (= were actively loading), against
  // the reporting fleet size.
  const loadByDay = new Map<string, Set<string>>();
  for (const r of d.act) {
    if (r.activity_type !== "Loading Explosives") continue;
    const day = (r.reporting_date || "").slice(0, 10);
    const mmu = (r.mmu_id || "").trim();
    if (!day || !mmu) continue;
    (loadByDay.get(day) || loadByDay.set(day, new Set()).get(day)!).add(mmu);
  }
  const utilData = Array.from(loadByDay, ([name, set]) => ({ name, value: set.size })).sort((a, b) => a.name.localeCompare(b.name));
  const loadingEvents = d.act.filter((r) => r.activity_type === "Loading Explosives");
  const benches = loadingEvents.length;

  // Benches loaded per day, broken down by bench location (populated once the
  // pipeline captures Bench Location — re-run precompute to backfill).
  const hasBench = loadingEvents.some((r) => (r.bench_location || "").trim());
  const benchPiv = pivot(loadingEvents, (r) => (r.reporting_date || "").slice(0, 10), (r) => (r.bench_location || "").trim() || "Unspecified", () => 1);
  benchPiv.data.sort((a, b) => String(a.x).localeCompare(String(b.x)));
  const benchColors: Record<string, string> = {};
  benchPiv.series.forEach((s, i) => (benchColors[s] = MASTER_PALETTE[i % MASTER_PALETTE.length]));
  const benchRows = loadingEvents
    .map((r) => ({
      Date: (r.reporting_date || "").slice(0, 10),
      Time: (r.start_timestamp || "").slice(11, 16) || "—",
      MMU: r.mmu_id,
      "Bench Location": r.bench_location || "—",
      Specify: r.specify || "—",
      Operator: r.operator_name,
      _ts: r.start_timestamp || "",
    }))
    // Rows that carry bench/specify float to the top; then newest day first,
    // and chronological within a day so accidental consecutive logs sit together.
    .sort((a, b) => {
      const aFilled = a["Bench Location"] !== "—" || a.Specify !== "—";
      const bFilled = b["Bench Location"] !== "—" || b.Specify !== "—";
      if (aFilled !== bFilled) return aFilled ? -1 : 1;
      if (a.Date !== b.Date) return b.Date.localeCompare(a.Date);
      return String(a._ts).localeCompare(String(b._ts));
    });
  const peak = utilData.reduce((m, x) => Math.max(m, x.value), 0);
  const avg = utilData.length ? utilData.reduce((s, x) => s + x.value, 0) / utilData.length : 0;
  // colour each day by how much of the fleet was loading (green = high)
  const utilColors: Record<string, string> = {};
  utilData.forEach((x) => {
    const pct = fleet ? x.value / fleet : 0;
    utilColors[x.name] = pct >= 0.66 ? "#59A14F" : pct >= 0.33 ? "#F1A340" : "#E15759";
  });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat label="Reporting fleet" value={fleet} sub="MMUs in scope" />
        <Stat label="Days of loading data" value={`${loadingDays} / ${selectedDays}`} sub="loading days / selected days" />
        <Stat label="Benches loaded" value={benches} sub="loading-explosives events" />
        <Stat label="Peak MMUs loading" value={peak} sub="busiest day" />
        <Stat label="Avg MMUs loading / day" value={round1(avg)} />
      </div>

      <ChartCard title="Fleet utilization — MMUs loading explosives per day"
        subtitle={`Distinct MMUs that logged loading on each activity day · of ${fleet} reporting MMUs · green ≥⅔ · amber ≥⅓ · red <⅓ of fleet`}>
        <BarV data={utilData} colorMap={utilColors} xLabel="Date" yLabel="MMUs loading explosives" height={340} />
      </ChartCard>

      {hasBench && (
        <ChartCard title="Benches loaded per day by location" subtitle="Loading-explosives events stacked by bench location">
          <StackedBar rows={benchPiv.data} xKey="x" series={benchPiv.series} colorMap={benchColors} />
        </ChartCard>
      )}

      <ChartCard title="Loading-explosives detail"
        subtitle={hasBench ? "Each loading event with its bench location" : "Bench Location / Specify populate once the pipeline is re-run to capture them"}>
        <DataTable
          columns={[{ key: "Date", label: "Date" }, { key: "Time", label: "Time" }, { key: "MMU", label: "MMU" }, { key: "Bench Location", label: "Bench Location" }, { key: "Specify", label: "Specify" }, { key: "Operator", label: "Operator" }]}
          rows={benchRows} csvName="loading_explosives.csv" />
      </ChartCard>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Total activity hours by MMU"><StackedBar rows={piv.data} xKey="x" series={piv.series} colorMap={colourMap} /></ChartCard>
        <ChartCard title="Fleet-wide activity mix"><Donut data={mix} colorMap={ACTIVITY_COLOURS} /></ChartCard>
      </div>
      <ChartCard title="Daily activity hours trend"><AreaTrend rows={daily.data} xKey="x" series={daily.series} colorMap={colourMap} /></ChartCard>
    </div>
  );
}

/* ── Pre-start faults ── */
function PrestartView({ d }: { d: D }) {
  const faults = d.ps.filter((p) => p.fault_flag);
  const breakdowns = d.act.filter((r) => r.activity_type === "Breakdown");

  // Combined log count (pre-start faults + breakdown events) per MMU → worst unit.
  const logByMmu = new Map<string, number>();
  for (const f of faults) { const m = f.mmu_id || "—"; logByMmu.set(m, (logByMmu.get(m) || 0) + 1); }
  for (const b of breakdowns) { const m = b.mmu_id || "—"; logByMmu.set(m, (logByMmu.get(m) || 0) + 1); }
  let topMmu = "—", topN = 0;
  for (const [m, n] of logByMmu) if (n > topN) { topN = n; topMmu = m; }

  const byMmu = groupCount(faults, (p) => p.mmu_id || "—").sort((a, b) => a.value - b.value);
  const byCat = groupCount(faults, (p) => p.checklist_category || "—").sort((a, b) => b.value - a.value);
  const byItem = groupCount(faults, (p) => (p.checklist_item || "—")).sort((a, b) => b.value - a.value).slice(0, 5)
    .map((x) => ({ name: x.name.length > 48 ? x.name.slice(0, 48) + "…" : x.name, value: x.value }));
  const rows = faults.map((p) => ({ MMU: p.mmu_id, Date: p.reporting_date, Category: p.checklist_category, Item: p.checklist_item }));

  // ── Used-after-fault: an MMU flagged with a pre-start fault that still
  // loaded explosives later the same day (after the flag time). ──
  const ms = (s?: string) => { const t = Date.parse(s || ""); return isNaN(t) ? null : t; };
  const keyOf = (mmu?: string | null, date?: string | null) => `${(mmu || "").trim()}|${(date || "").slice(0, 10)}`;
  // earliest fault flag time + fault count per MMU/day
  const faultGroups = new Map<string, { time: string; items: number }>();
  for (const f of faults) {
    const k = keyOf(f.mmu_id, f.reporting_date);
    const t = f.inspection_timestamp || "";
    const g = faultGroups.get(k);
    if (!g) faultGroups.set(k, { time: t, items: 1 });
    else { g.items++; if (t && (!g.time || t < g.time)) g.time = t; }
  }
  // activity events grouped by MMU/day
  const actByKey = new Map<string, typeof d.act>();
  for (const a of d.act) { const k = keyOf(a.mmu_id, a.reporting_date); (actByKey.get(k) || actByKey.set(k, []).get(k)!).push(a); }
  const incidents: Record<string, unknown>[] = [];
  for (const [k, g] of faultGroups) {
    const flagMs = ms(g.time);
    if (flagMs == null) continue;  // need a real flag time to order against
    const after = (actByKey.get(k) || [])
      .filter((a) => a.activity_type === "Loading Explosives")
      .filter((a) => { const t = ms(a.start_timestamp); return t != null && t > flagMs; })
      .sort((a, b) => (a.start_timestamp || "").localeCompare(b.start_timestamp || ""));
    if (!after.length) continue;
    const [mmu, date] = k.split("|");
    const first = after[0];
    incidents.push({
      Date: date, MMU: mmu,
      "Flagged": g.time.slice(11, 16),
      "Faults": g.items,
      "First use after": `${(first.start_timestamp || "").slice(11, 16)} · ${first.activity_type}`,
      "Uses after": after.length,
      Operator: first.operator_name,
    });
  }
  incidents.sort((a, b) => String(b.Date).localeCompare(String(a.Date)));
  const incidentByMmu = groupCount(incidents, (r) => String(r.MMU)).sort((a, b) => a.value - b.value);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Pre-start fault flags" value={faults.length} sub="over selected dates" />
        <Stat label="Breakdowns logged" value={breakdowns.length} sub="breakdown events" />
        <Stat label="Most-flagged MMU" value={topMmu} sub={`${topN} faults + breakdowns`} />
        <Stat label="No. of times MMU used after pre-start fault" value={incidents.length} sub="loaded explosives same day" />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Pre-Start Fault Flags by MMU"><BarH data={byMmu} colorMap={paletteMap(byMmu.map((x) => x.name))} xLabel="Fault Flags" yLabel="MMU" /></ChartCard>
        <ChartCard title="Pre-Start Faults by checklist category"><Donut data={byCat} colorMap={CATEGORY_COLOURS} /></ChartCard>
      </div>
      <ChartCard title="Top 5 most flagged Pre-start items"><BarH data={byItem} height={260} /></ChartCard>

      <ChartCard title="Number of times an MMU was used to load explosives after a pre-start fault was logged on same day" subtitle="By MMU">
        {incidentByMmu.length
          ? <BarH data={incidentByMmu} colorMap={paletteMap(incidentByMmu.map((x) => x.name))} xLabel="Cases" yLabel="MMU" height={Math.max(160, incidentByMmu.length * 36)} />
          : <div className="py-10 text-center text-sm text-muted">No cases — flagged MMUs didn&apos;t load explosives again the same day.</div>}
      </ChartCard>
      <ChartCard title="Loaded explosives after fault logged"
        subtitle="Each case: when the fault was flagged vs the first loading-explosives event afterwards on that MMU the same day. Relies on accurate user-entered times.">
        <DataTable
          columns={[{ key: "Date", label: "Date" }, { key: "MMU", label: "MMU" }, { key: "Flagged", label: "Fault flagged" }, { key: "Faults", label: "Faults" }, { key: "First use after", label: "First load after" }, { key: "Uses after", label: "Loads after" }, { key: "Operator", label: "Operator" }]}
          rows={incidents} csvName="loaded_after_fault.csv" />
      </ChartCard>

      <ChartCard title="Pre-start fault records">
        <DataTable columns={[{ key: "MMU", label: "MMU" }, { key: "Date", label: "Date" }, { key: "Category", label: "Category" }, { key: "Item", label: "Item" }]}
          rows={rows} csvName="prestart_faults.csv" />
      </ChartCard>
    </div>
  );
}

/* ── Shift performance: time buckets + dead time + start summary ── */
function PerfView({ d }: { d: D }) {
  // buckets by MMU
  const bucketRows = d.act.map((r) => ({ ...r, bucket: ACTIVITY_BUCKET[r.activity_type || ""] || "Other" }));
  const piv = pivot(bucketRows, (r) => r.mmu_id || "—", (r) => r.bucket, (r) => r.duration_hours);
  piv.data.forEach((row) => piv.series.forEach((s) => (row[s] = round1(Number(row[s]) || 0))));

  // dead time: first activity per session vs shift_start
  const firstBySession = new Map<string, number>();
  for (const r of d.act) {
    if (!r.session_id || !r.start_timestamp) continue;
    const t = new Date(r.start_timestamp).getTime();
    if (!firstBySession.has(r.session_id) || t < firstBySession.get(r.session_id)!) firstBySession.set(r.session_id, t);
  }
  const dead = d.sessions.filter((s) => s.shift_start && firstBySession.has(s.session_id)).map((s) => {
    const gap = (firstBySession.get(s.session_id)! - new Date(s.shift_start!).getTime()) / 60000;
    return { name: `${s.operator_name} (${s.reporting_date})`, value: Math.max(0, round1(gap)) };
  }).sort((a, b) => a.value - b.value);

  // start summary table
  const byOp = new Map<string, number[]>();
  for (const s of d.sessions) if (s.operator_name && s.shift_start) {
    const dt = new Date(s.shift_start); const h = dt.getHours() + dt.getMinutes() / 60;
    (byOp.get(s.operator_name) || byOp.set(s.operator_name, []).get(s.operator_name)!).push(h);
  }
  const fmtH = (h: number) => `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.round((h % 1) * 60)).padStart(2, "0")}`;
  const summary = Array.from(byOp, ([op, hrs]) => ({
    Operator: op, Sessions: hrs.length, Earliest: fmtH(Math.min(...hrs)), Latest: fmtH(Math.max(...hrs)),
    "Avg Start": fmtH(hrs.reduce((a, b) => a + b, 0) / hrs.length),
  }));

  return (
    <div className="space-y-6">
      <ChartCard title="Time breakdown by MMU" subtitle="Productive · Movement · Downtime · Maintenance · Safety/Admin">
        <StackedBar rows={piv.data} xKey="x" series={piv.series} colorMap={BUCKET_COLOURS} />
      </ChartCard>
      <ChartCard title="Shift start summary by operator">
        <DataTable columns={[{ key: "Operator", label: "Operator" }, { key: "Sessions", label: "Sessions" }, { key: "Earliest", label: "Earliest" }, { key: "Latest", label: "Latest" }, { key: "Avg Start", label: "Avg Start" }]} rows={summary} />
      </ChartCard>
      <ChartCard title="Dead time — shift start to first logged activity (min)">
        <BarH data={dead} colorMap={paletteMap(dead.map((x) => x.name))} height={Math.max(300, dead.length * 26)} />
      </ChartCard>
    </div>
  );
}

/* ── Shift timeline (single MMU) — day breakdown table; visual gantt next pass ── */
function TimelineView({ d, selected }: { d: D; selected: Set<string> }) {
  if (selected.size !== 1) {
    return <Card><CardBody><div className="text-sm text-muted">Select a single MMU in the left panel to view its shift timeline.</div></CardBody></Card>;
  }
  const breakdown = groupSum(d.act, (r) => r.activity_type || "Other", (r) => Number(r.duration_minutes) || 0)
    .map((x) => ({ Activity: x.name, Minutes: Math.round(x.value) })).sort((a, b) => b.Minutes - a.Minutes);
  return (
    <ChartCard title="Activity breakdown" subtitle="Visual Gantt timeline lands in the next pass">
      <DataTable columns={[{ key: "Activity", label: "Activity" }, { key: "Minutes", label: "Minutes" }]} rows={breakdown} />
    </ChartCard>
  );
}
