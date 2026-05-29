"use client";
import { fmtPct } from "@/lib/api";

export function PageHeader({ title, subtitle, action }:
  { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-8 flex items-end justify-between gap-4 animate-fadeUp">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ label, value, sub, accent }:
  { label: string; value: React.ReactNode; sub?: React.ReactNode; accent?: string }) {
  return (
    <div className="card p-5 animate-fadeUp">
      <div className="stat-label">{label}</div>
      <div className={`stat-value mt-1.5 ${accent || ""}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-ink-faint">{sub}</div>}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }:
  { children: React.ReactNode; tone?: "bull" | "bear" | "warn" | "brand" | "neutral" | "macro" }) {
  const tones: Record<string, string> = {
    bull: "bg-bull/10 text-bull",
    bear: "bg-bear/10 text-bear",
    warn: "bg-warn/10 text-warn",
    brand: "bg-brand/10 text-brand",
    macro: "bg-macro/10 text-macro",
    neutral: "bg-surface-subtle text-ink-soft",
  };
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

export function PillarBar({ label, value }: { label: string; value: number | null }) {
  if (value === null || value === undefined)
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="w-20 text-ink-faint">{label}</span>
        <span className="text-ink-faint">n/a</span>
      </div>
    );
  const pct = Math.abs(value) * 100;
  const pos = value >= 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 capitalize text-ink-soft">{label}</span>
      <div className="relative h-2 flex-1 rounded-full bg-surface-subtle">
        <div className="absolute left-1/2 top-0 h-2 w-px bg-surface-line" />
        <div
          className={`absolute top-0 h-2 rounded-full ${pos ? "bg-bull" : "bg-bear"}`}
          style={{ width: `${Math.min(pct / 2, 50)}%`, left: pos ? "50%" : undefined,
                   right: pos ? undefined : "50%" }}
        />
      </div>
      <span className={`w-10 text-right font-mono ${pos ? "text-bull" : "text-bear"}`}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-ink-soft">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      {label || "Working…"}
    </div>
  );
}

export function ReturnPill({ value }: { value: number }) {
  const pos = value >= 0;
  return (
    <span className={`chip ${pos ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear"}`}>
      {pos ? "▲" : "▼"} {fmtPct(Math.abs(value))}
    </span>
  );
}
