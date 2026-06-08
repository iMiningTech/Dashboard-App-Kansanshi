"use client";

import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import {
  LayoutDashboard, AlertCircle, AlertTriangle, BarChart3, ClipboardCheck, Timer, CalendarRange,
  User, Activity, RefreshCw, Truck,
} from "lucide-react";
import { api, type DashboardData, type MmuStatus, type PrestartRow } from "@/lib/api";
import { Card, CardBody, Stat, Badge } from "@/components/ui";
import { ChartCard, BarH, StackedBar, Donut, AreaTrend, DataTable } from "@/components/charts";
import {
  filterTimeline, filterPrestart, sessionSummary, sessionsWithEnd, activityTimeline,
  kpis, uniqueSorted, groupSum, groupCount,
} from "@/lib/data";
import { ACTIVITY_COLOURS, CATEGORY_COLOURS, BUCKET_COLOURS, ACTIVITY_BUCKET, paletteMap, activityColour } from "@/lib/colors";
import { fmtTime } from "@/lib/utils";

const VIEWS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "logouts", label: "Missing Shift-Ends", icon: AlertCircle },
  { id: "util", label: "MMU Utilization", icon: BarChart3 },
  { id: "prestart", label: "Pre-start Faults", icon: ClipboardCheck },
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

export default function Dashboard() {
  const [raw, setRaw] = useState<DashboardData | null>(null);
  const [live, setLive] = useState<MmuStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewId>("overview");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lo, setLo] = useState("");
  const [hi, setHi] = useState("");
  const [loBound, setLoBound] = useState("");
  const [hiBound, setHiBound] = useState("");

  async function load() {
    setLoading(true); setError(null);
    try {
      const [d, m] = await Promise.all([api.dashboard("90d"), api.liveMmu()]);
      setRaw(d); setLive(m.items || []);
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

  const allMmus = useMemo(() => uniqueSorted((raw?.timeline || []).map((t) => t.mmu_id)), [raw]);

  // Filtered + derived
  const d = useMemo(() => {
    const tl = filterTimeline(raw?.timeline || [], selected, lo || "0000", hi || "9999");
    const ps = filterPrestart(raw?.prestart || [], selected, lo || "0000", hi || "9999");
    const sessions = sessionSummary(tl);
    const ended = sessionsWithEnd(tl);
    const noEnd = sessions.filter((s) => !s.clocked_out);
    const act = activityTimeline(tl);
    return { tl, ps, sessions, ended, noEnd, act, k: kpis(tl, ps) };
  }, [raw, selected, lo, hi]);

  function toggleMmu(m: string) {
    setSelected((prev) => { const n = new Set(prev); n.has(m) ? n.delete(m) : n.add(m); return n; });
  }

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar (iMining navy) ── */}
      <aside className="hidden w-64 shrink-0 flex-col bg-sidebar text-sidebarfg md:flex">
        <div className="flex h-16 items-center gap-2 px-5">
          <Image src="/imining_white.png" alt="iMining" width={120} height={28} style={{ height: 26, width: "auto" }} />
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

          <div className="mb-1 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-sidebarfg/60">
            <span>MMUs</span>
            {selected.size > 0 && <button onClick={() => setSelected(new Set())} className="text-accent2 normal-case">clear</button>}
          </div>
          <div className="max-h-48 space-y-1 overflow-auto pr-1">
            {allMmus.map((m) => (
              <label key={m} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 hover:bg-white/10">
                <input type="checkbox" checked={selected.size === 0 || selected.has(m)} onChange={() => toggleMmu(m)} />
                <span>{m}</span>
              </label>
            ))}
          </div>
          <div className="mt-3 text-xs text-sidebarfg/50">
            {d.tl.length.toLocaleString()} activities · {d.ps.length.toLocaleString()} inspections
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-6">
          <div className="flex items-center gap-3">
            <Image src="/orica_logo.png" alt="Orica" width={90} height={28} style={{ height: 24, width: "auto" }} />
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
              {/* SITE STATUS — always on top */}
              <SiteStatus live={live} prestart={raw?.prestart || []} />
              {/* KPIs */}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <Stat label="Shift sessions" value={d.k.totalSessions} />
                <Stat label="Active MMUs" value={d.k.activeMmus} />
                <Stat label="Missing shift-ends" value={d.k.missingLogouts} sub={`${d.k.missingPct.toFixed(0)}% of sessions`} />
                <Stat label="Pre-start faults" value={d.k.faults} />
              </div>

              {view === "overview" && <OverviewView d={d} />}
              {view === "logouts" && <LogoutsView d={d} />}
              {view === "util" && <UtilView d={d} />}
              {view === "prestart" && <PrestartView d={d} />}
              {view === "perf" && <PerfView d={d} />}
              {view === "timeline" && <TimelineView d={d} selected={selected} />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/* ── Site status (real-time current_mmu) ── */
function SiteStatus({ live, prestart }: { live: MmuStatus[]; prestart: PrestartRow[] }) {
  // (MMU, date) pairs that have a pre-start on record — to flag units whose
  // last shift had no pre-start inspection logged.
  const prestartKeys = new Set(
    prestart.map((p) => `${p.mmu_id}|${(p.reporting_date || "").slice(0, 10)}`)
  );
  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-fg"><Truck size={16} /> Site Status — current snapshot</div>
      {live.length === 0 ? <div className="text-sm text-muted">No live MMU state yet.</div> : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {live.map((m) => {
            const active = (m.status || "").toUpperCase() === "ON_SHIFT";
            const day = (m.last_seen || "").slice(0, 10);
            const noPrestart = !!m.fleet_no && !!day && !prestartKeys.has(`${m.fleet_no}|${day}`);
            return (
              <Card key={m.fleet_no}>
                <CardBody>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-fg">{m.fleet_no}</span>
                    <Badge tone={active ? "ok" : "muted"}>{active ? "On shift" : "Off shift"}</Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-sm text-muted"><User size={14} /> {m.operator || m.operator_last || "—"}</div>
                  <div className="mt-1 flex items-center gap-2 text-sm text-fg"><Activity size={14} className="text-accent" /> {m.last_activity || "—"}</div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-xs text-muted">{fmtTime(m.last_seen)}</span>
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

/* ── Overview: a compact mix of the headline charts ── */
function OverviewView({ d }: { d: D }) {
  const mix = groupSum(d.act, (r) => r.activity_type || "Other", (r) => r.duration_hours)
    .map((x) => ({ name: x.name, value: round1(x.value) })).sort((a, b) => b.value - a.value);
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <ChartCard title="Fleet-wide activity mix" subtitle="Hours by activity (capped 4h/event)">
        <Donut data={mix} colorMap={ACTIVITY_COLOURS} />
      </ChartCard>
      <ChartCard title="Activity hours by category">
        <BarH data={mix.slice(0, 10)} colorMap={ACTIVITY_COLOURS} />
      </ChartCard>
    </div>
  );
}

/* ── Missing shift-ends ── */
function LogoutsView({ d }: { d: D }) {
  const byOp = groupCount(d.noEnd, (s) => s.operator_name || "—").sort((a, b) => a.value - b.value);
  const byDate = groupCount(d.noEnd, (s) => s.reporting_date || "—").sort((a, b) => a.name.localeCompare(b.name));
  const rows = d.noEnd.map((s) => ({ Operator: s.operator_name, MMU: s.mmu_id, Date: s.reporting_date, Start: fmtTime(s.shift_start || undefined) }));
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Missing shift-end logs by operator"><BarH data={byOp} colorMap={paletteMap(byOp.map((x) => x.name))} /></ChartCard>
        <ChartCard title="Missing shift-end logs by date"><BarH data={byDate} colorMap={paletteMap(byDate.map((x) => x.name))} /></ChartCard>
      </div>
      <ChartCard title="Session detail">
        <DataTable columns={[{ key: "Operator", label: "Operator" }, { key: "MMU", label: "MMU" }, { key: "Date", label: "Date" }, { key: "Start", label: "Shift Start" }]}
          rows={rows} csvName="missing_shift_end.csv" />
      </ChartCard>
    </div>
  );
}

/* ── MMU Utilization ── */
function UtilView({ d }: { d: D }) {
  const piv = pivot(d.act, (r) => r.mmu_id || "—", (r) => r.activity_type || "Other", (r) => r.duration_hours);
  piv.data.forEach((row) => piv.series.forEach((s) => (row[s] = round1(Number(row[s]) || 0))));
  const colourMap: Record<string, string> = {};
  piv.series.forEach((s, i) => (colourMap[s] = activityColour(s, i)));
  const mix = groupSum(d.act, (r) => r.activity_type || "Other", (r) => r.duration_hours).map((x) => ({ name: x.name, value: round1(x.value) }));
  const daily = pivot(d.act, (r) => (r.reporting_date || "").slice(0, 10), (r) => r.activity_type || "Other", (r) => r.duration_hours);
  daily.data.sort((a, b) => String(a.x).localeCompare(String(b.x)));
  return (
    <div className="space-y-6">
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
  const byMmu = groupCount(faults, (p) => p.mmu_id || "—").sort((a, b) => a.value - b.value);
  const byCat = groupCount(faults, (p) => p.checklist_category || "—").sort((a, b) => b.value - a.value);
  const byItem = groupCount(faults, (p) => (p.checklist_item || "—")).sort((a, b) => b.value - a.value).slice(0, 15)
    .map((x) => ({ name: x.name.length > 48 ? x.name.slice(0, 48) + "…" : x.name, value: x.value }));
  const rows = faults.map((p) => ({ MMU: p.mmu_id, Date: p.reporting_date, Category: p.checklist_category, Item: p.checklist_item, Status: p.status }));
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Fault flags by MMU"><BarH data={byMmu} colorMap={paletteMap(byMmu.map((x) => x.name))} /></ChartCard>
        <ChartCard title="Faults by checklist category"><Donut data={byCat} colorMap={CATEGORY_COLOURS} /></ChartCard>
      </div>
      <ChartCard title="Top 15 most flagged items"><BarH data={byItem} height={430} /></ChartCard>
      <ChartCard title="Fault records">
        <DataTable columns={[{ key: "MMU", label: "MMU" }, { key: "Date", label: "Date" }, { key: "Category", label: "Category" }, { key: "Item", label: "Item" }, { key: "Status", label: "Status" }]}
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
