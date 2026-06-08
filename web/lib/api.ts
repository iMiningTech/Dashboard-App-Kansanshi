// Thin client for the Kansanshi data API. Base URL + optional token come from
// env (NEXT_PUBLIC_*). See .env.local.example.

const BASE = process.env.NEXT_PUBLIC_API_BASE || "";
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: TOKEN ? { "x-api-token": TOKEN } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json();
}

export type Asset = {
  fleet_no: string;
  display_name?: string;
  active?: boolean;
  plant?: string;
  sort_order?: number;
};

export type MmuStatus = {
  fleet_no: string;
  status?: string;
  operator?: string;
  operator_last?: string;
  last_activity?: string;
  last_seen?: string;
  since?: string;
  plant?: string;
};

export type TimelineRow = {
  session_id?: string;
  mmu_id?: string;
  operator_name?: string;
  activity_type?: string;
  activity_category?: string;
  duration_minutes?: number;
  start_timestamp?: string;
  reporting_date?: string;
  is_exception?: boolean;
  exception_reason?: string;
};

export type PrestartRow = {
  mmu_id?: string;
  operator_name?: string;
  inspection_timestamp?: string;
  checklist_category?: string;
  checklist_item?: string;
  status?: string;
  fault_number?: string;
  comment?: string;
  fault_flag?: boolean;
  reporting_date?: string;
};

export type DashboardData = {
  window: string;
  generated_at: string | null;
  pending: boolean;
  timeline: TimelineRow[];
  prestart: PrestartRow[];
  exceptions: Record<string, unknown>[];
};

export const api = {
  assets: () => get<{ count: number; items: Asset[] }>("/assets"),
  liveMmu: () => get<{ count: number; items: MmuStatus[] }>("/live/mmu"),
  liveSessions: () => get<{ count: number; items: Record<string, unknown>[] }>("/live/sessions"),
  dashboard: (window = "30d") => get<DashboardData>(`/dashboard?window=${window}`),
};
