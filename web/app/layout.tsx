import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { LayoutDashboard, Truck, ClipboardCheck, AlertTriangle } from "lucide-react";

export const metadata: Metadata = {
  title: "Kansanshi MMU Operations",
  description: "Live MMU operations dashboard",
};

const NAV = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Fleet Status", icon: Truck },
  { label: "Pre-Start", icon: ClipboardCheck },
  { label: "Exceptions", icon: AlertTriangle },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="hidden w-60 shrink-0 border-r border-border bg-surface md:block">
            <div className="flex h-16 items-center gap-2 border-b border-border px-5">
              <div className="h-7 w-7 rounded-lg bg-brand" />
              <span className="font-semibold">Kansanshi Ops</span>
            </div>
            <nav className="p-3">
              {NAV.map(({ label, icon: Icon }, i) => (
                <a key={label} href="#"
                   className={`mb-1 flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${i === 0 ? "bg-brand/10 text-brand font-medium" : "text-muted hover:bg-bg"}`}>
                  <Icon size={18} /> {label}
                </a>
              ))}
            </nav>
          </aside>

          {/* Main */}
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-6">
              <h1 className="text-lg font-semibold">MMU Operations</h1>
              <span className="text-xs text-muted">Kansanshi Mine · live</span>
            </header>
            <main className="flex-1 overflow-auto p-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
