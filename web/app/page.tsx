"use client";

import { useEffect, useMemo, useState } from "react";
import { Truck, User, Activity, AlertTriangle, RefreshCw } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { api, type MmuStatus, type DashboardData } from "@/lib/api";
import { Card, CardBody, Stat, Badge } from "@/components/ui";
import { fmtTime } from "@/lib/utils";

export default function Overview() {
  const [mmus, setMmus] = useState<MmuStatus[]>([]);
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [window, setWindow] = useState("30d");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [m, d] = await Promise.all([api.liveMmu(), api.dashboard(window)]);
      setMmus(m.items || []);
      setDash(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [window]);

  const onShift = mmus.filter((m) => (m.status || "").toUpperCase() === "ON_SHIFT").length;
  const activities = useMemo(
    () => (dash?.timeline || []).filter((t) => !["Shift Start", "Shift End"].includes(t.activity_type || "")),
    [dash]
  );
  const faults = (dash?.prestart || []).filter((p) => p.fault_flag).length;

  const byCategory = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const t of activities) {
      const k = t.activity_category || t.activity_type || "Other";
      acc[k] = (acc[k] || 0) + (Number(t.duration_minutes) || 0);
    }
    return Object.entries(acc)
      .map(([category, minutes]) => ({ category, hours: Math.round((minutes / 60) * 10) / 10 }))
      .sort((a, b) => b.hours - a.hours)
      .slice(0, 8);
  }, [activities]);

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted">
          {dash?.generated_at ? `Data as of ${fmtTime(dash.generated_at)}` : "Live"}
        </div>
        <div className="flex items-center gap-2">
          <select value={window} onChange={(e) => setWindow(e.target.value)}
                  className="rounded-xl border border-border bg-surface px-3 py-1.5 text-sm">
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="mtd">Month to date</option>
          </select>
          <button onClick={load} className="flex items-center gap-1 rounded-xl border border-border bg-surface px-3 py-1.5 text-sm hover:bg-bg">
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <Card><CardBody><div className="flex items-center gap-2 text-danger"><AlertTriangle size={18} /> {error}</div></CardBody></Card>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="MMUs tracked" value={loading ? "…" : mmus.length} />
        <Stat label="On shift now" value={loading ? "…" : onShift} sub={`${mmus.length - onShift} off shift`} />
        <Stat label="Activities logged" value={loading ? "…" : activities.length} sub={`window: ${window}`} />
        <Stat label="Pre-Start faults" value={loading ? "…" : faults} sub={`window: ${window}`} />
      </div>

      {/* Activity hours by category */}
      <Card>
        <CardBody>
          <div className="mb-3 text-sm font-medium">Activity hours by category</div>
          {byCategory.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted">No activity in this window.</div>
          ) : (
            <div style={{ width: "100%", height: 280 }}>
              <ResponsiveContainer>
                <BarChart data={byCategory} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--border))" />
                  <XAxis type="number" tick={{ fontSize: 12 }} />
                  <YAxis type="category" dataKey="category" width={140} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="hours" fill="rgb(var(--brand))" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Site status grid */}
      <div>
        <div className="mb-3 flex items-center gap-2 text-sm font-medium"><Truck size={16} /> Fleet status</div>
        {loading ? (
          <div className="text-sm text-muted">Loading…</div>
        ) : mmus.length === 0 ? (
          <div className="text-sm text-muted">No MMU activity yet.</div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {mmus.map((m) => {
              const active = (m.status || "").toUpperCase() === "ON_SHIFT";
              return (
                <Card key={m.fleet_no}>
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{m.fleet_no}</span>
                      <Badge tone={active ? "ok" : "muted"}>{active ? "On shift" : "Off shift"}</Badge>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-sm text-muted">
                      <User size={14} /> {m.operator || m.operator_last || "—"}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-sm">
                      <Activity size={14} className="text-brand" /> {m.last_activity || "—"}
                    </div>
                    <div className="mt-2 text-xs text-muted">{fmtTime(m.last_seen)}</div>
                  </CardBody>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
