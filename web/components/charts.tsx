"use client";

import {
  ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, Legend,
  CartesianGrid, PieChart, Pie, AreaChart, Area, LabelList,
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
export function BarH({ data, colorMap, height = 360, xLabel, yLabel }:
  { data: { name: string; value: number }[]; colorMap?: Record<string, string>; height?: number; xLabel?: string; yLabel?: string }) {
  if (!data.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: yLabel ? 24 : 16, right: 16, bottom: xLabel ? 18 : 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
          <XAxis type="number" tick={AXIS} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, ...AXIS } : undefined} />
          <YAxis type="category" dataKey="name" width={150} tick={AXIS}
                 label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", style: { textAnchor: "middle" }, ...AXIS } : undefined} />
          <Tooltip />
          <Bar dataKey="value" radius={[0, 5, 5, 0]}>
            {data.map((d, i) => <Cell key={i} fill={colorMap?.[d.name] || MASTER_PALETTE[i % MASTER_PALETTE.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Vertical bar, one column per category (e.g. by date), with axis labels.
// `barLabels` maps name → a short status word drawn vertically inside the bar.
export function BarV({ data, colorMap, height = 360, xLabel, yLabel, barLabels }:
  { data: { name: string; value: number }[]; colorMap?: Record<string, string>; height?: number; xLabel?: string; yLabel?: string; barLabels?: Record<string, string> }) {
  if (!data.length) return <Empty />;
  const renderText = (p: { x?: number | string; y?: number | string; width?: number | string; height?: number | string; value?: string | number }) => {
    const x = Number(p.x) || 0, y = Number(p.y) || 0, width = Number(p.width) || 0, h = Number(p.height) || 0;
    const txt = barLabels?.[String(p.value)];
    if (!txt || width <= 0 || h < 28) return null;
    const cx = x + width / 2, cy = y + h / 2;
    return (
      <text x={cx} y={cy} transform={`rotate(-90 ${cx} ${cy})`} textAnchor="middle"
            dominantBaseline="central" fontSize={11} fontWeight={600} fill="#fff">{txt}</text>
    );
  };
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: yLabel ? 24 : 16, right: 16, bottom: xLabel ? 18 : 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis type="category" dataKey="name" tick={AXIS}
                 label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, ...AXIS } : undefined} />
          <YAxis type="number" allowDecimals={false} tick={AXIS}
                 label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", style: { textAnchor: "middle" }, ...AXIS } : undefined} />
          <Tooltip />
          <Bar dataKey="value" radius={[5, 5, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={colorMap?.[d.name] || MASTER_PALETTE[i % MASTER_PALETTE.length]} />)}
            {barLabels && <LabelList dataKey="name" content={renderText as never} />}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Stacked/grouped vertical bar. rows: [{ x, [series]: number }]. series with colours.
export function StackedBar({ rows, xKey, series, colorMap, height = 420, stacked = true, xLabel, yLabel }:
  { rows: Record<string, unknown>[]; xKey: string; series: string[]; colorMap: Record<string, string>; height?: number; stacked?: boolean; xLabel?: string; yLabel?: string }) {
  if (!rows.length) return <Empty />;
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ left: yLabel ? 16 : 8, right: 8, bottom: xLabel ? 44 : 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey={xKey} tick={AXIS}
                 label={xLabel ? { value: xLabel, position: "insideBottom", offset: -2, ...AXIS } : undefined} />
          <YAxis tick={AXIS}
                 label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", style: { textAnchor: "middle" }, ...AXIS } : undefined} />
          <Tooltip />
          <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
          {series.map((s, i) => (
            <Bar key={s} dataKey={s} stackId={stacked ? "a" : undefined}
                 fill={colorMap[s] || MASTER_PALETTE[i % MASTER_PALETTE.length]} radius={stacked ? 0 : [4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RAD = Math.PI / 180;
const LABEL_MIN = 0.07; // only slices ≥7% get a leader line + label; rest via hover/legend

// Custom label: draws the leader line AND the text together, so small slices
// render nothing at all (no dangling lines). Bigger slices get "Name %".
function donutLabel(p: {
  cx?: number; cy?: number; midAngle?: number; outerRadius?: number; percent?: number; name?: string;
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, percent = 0, name = "" } = p;
  if (percent < LABEL_MIN) return null;
  const cos = Math.cos(-midAngle * RAD), sin = Math.sin(-midAngle * RAD);
  const sx = cx + outerRadius * cos, sy = cy + outerRadius * sin;          // slice edge
  const mx = cx + (outerRadius + 16) * cos, my = cy + (outerRadius + 16) * sin; // elbow
  const right = cos >= 0;
  const ex = mx + (right ? 16 : -16), ey = my;
  return (
    <g>
      <path d={`M${sx},${sy}L${mx},${my}L${ex},${ey}`} stroke="rgb(160 170 180)" strokeWidth={1} fill="none" />
      <circle cx={sx} cy={sy} r={2} fill="rgb(160 170 180)" />
      <text x={ex + (right ? 4 : -4)} y={ey} textAnchor={right ? "start" : "end"} dominantBaseline="central"
            fontSize={11} fill="rgb(31 41 55)">
        {`${name} ${Math.round(percent * 100)}%`}
      </text>
    </g>
  );
}

export function Donut({ data, colorMap, height = 380 }:
  { data: { name: string; value: number }[]; colorMap?: Record<string, string>; height?: number }) {
  if (!data.length) return <Empty />;
  const colorOf = (name: string, i: number) => colorMap?.[name] || MASTER_PALETTE[i % MASTER_PALETTE.length];
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <PieChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="38%" outerRadius="60%"
               paddingAngle={1} labelLine={false} label={donutLabel}>
            {data.map((d, i) => <Cell key={i} fill={colorOf(d.name, i)} />)}
          </Pie>
          <Tooltip formatter={(v, n) => [v as number, n as string]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
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
