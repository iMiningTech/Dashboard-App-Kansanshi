"use client";

import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, Legend,
  CartesianGrid, PieChart, Pie, AreaChart, Area,
} from "recharts";
import { Card, CardBody } from "@/components/ui";
import { MASTER_PALETTE } from "@/lib/colors";

const AXIS = { fontSize: 12, fill: "rgb(100 116 130)" };
const GRID = "rgb(224 230 235)";

export function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardBody>
        <div className="mb-1 text-sm font-semibold text-fg">{title}</div>
        {subtitle && <div className="mb-3 text-xs text-muted">{subtitle}</div>}
        {children}
      </CardBody>
    </Card>
  );
}

// Horizontal bar, one row per category, each coloured from a map.
export function BarH({ data, colorMap, height = 360, xLabel }:
  { data: { name: string; value: number }[]; colorMap?: Record<string, string>; height?: number; xLabel?: string }) {
  if (!data.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 16, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
          <XAxis type="number" tick={AXIS} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -2, ...AXIS } : undefined} />
          <YAxis type="category" dataKey="name" width={150} tick={AXIS} />
          <Tooltip />
          <Bar dataKey="value" radius={[0, 5, 5, 0]}>
            {data.map((d, i) => <Cell key={i} fill={colorMap?.[d.name] || MASTER_PALETTE[i % MASTER_PALETTE.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Stacked/grouped vertical bar. rows: [{ x, [series]: number }]. series with colours.
export function StackedBar({ rows, xKey, series, colorMap, height = 420, stacked = true }:
  { rows: Record<string, unknown>[]; xKey: string; series: string[]; colorMap: Record<string, string>; height?: number; stacked?: boolean }) {
  if (!rows.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ left: 8, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey={xKey} tick={AXIS} />
          <YAxis tick={AXIS} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Bar key={s} dataKey={s} stackId={stacked ? "a" : undefined}
                 fill={colorMap[s] || MASTER_PALETTE[i % MASTER_PALETTE.length]} radius={stacked ? 0 : [4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Donut({ data, colorMap, height = 380 }:
  { data: { name: string; value: number }[]; colorMap?: Record<string, string>; height?: number }) {
  if (!data.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%" paddingAngle={1}>
            {data.map((d, i) => <Cell key={i} fill={colorMap?.[d.name] || MASTER_PALETTE[i % MASTER_PALETTE.length]} />)}
          </Pie>
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AreaTrend({ rows, xKey, series, colorMap, height = 320 }:
  { rows: Record<string, unknown>[]; xKey: string; series: string[]; colorMap: Record<string, string>; height?: number }) {
  if (!rows.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ left: 8, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey={xKey} tick={AXIS} />
          <YAxis tick={AXIS} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Area key={s} type="monotone" dataKey={s} stackId="a"
                  stroke={colorMap[s] || MASTER_PALETTE[i % MASTER_PALETTE.length]}
                  fill={colorMap[s] || MASTER_PALETTE[i % MASTER_PALETTE.length]} fillOpacity={0.7} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DataTable({ columns, rows, csvName }:
  { columns: { key: string; label: string }[]; rows: Record<string, unknown>[]; csvName?: string }) {
  function downloadCsv() {
    const header = columns.map((c) => `"${c.label}"`).join(",");
    const body = rows.map((r) => columns.map((c) => `"${String(r[c.key] ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = csvName || "export.csv"; a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div>
      <div className="max-h-80 overflow-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-bg text-left text-xs uppercase tracking-wide text-muted">
            <tr>{columns.map((c) => <th key={c.key} className="px-3 py-2 font-medium">{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={columns.length} className="px-3 py-6 text-center text-muted">No records.</td></tr>
            ) : rows.map((r, i) => (
              <tr key={i} className="border-t border-border hover:bg-bg/60">
                {columns.map((c) => <td key={c.key} className="px-3 py-2">{String(r[c.key] ?? "—")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {csvName && rows.length > 0 && (
        <button onClick={downloadCsv} className="mt-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs hover:bg-bg">
          ⬇ Download CSV
        </button>
      )}
    </div>
  );
}

function Empty() {
  return <div className="py-12 text-center text-sm text-muted">No data for the current filters.</div>;
}
