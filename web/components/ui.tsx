// Small shadcn-style primitives (Tailwind + tokens). Hand-rolled so there's no
// CLI step; extend freely. This is the component vocabulary the team reuses.
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-2xl border border-border bg-surface shadow-sm", className)}>
      {children}
    </div>
  );
}

export function CardBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("p-4", className)}>{children}</div>;
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <Card>
      <CardBody className="text-center">
        <div className="text-sm text-muted">{label}</div>
        <div className="mt-1 text-3xl font-semibold tracking-tight">{value}</div>
        {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
      </CardBody>
    </Card>
  );
}

export function Badge({ tone = "muted", children }: { tone?: "ok" | "muted" | "warn" | "danger"; children: ReactNode }) {
  const tones: Record<string, string> = {
    ok: "bg-ok/10 text-ok",
    warn: "bg-warn/10 text-warn",
    danger: "bg-danger/10 text-danger",
    muted: "bg-muted/10 text-muted",
  };
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}
