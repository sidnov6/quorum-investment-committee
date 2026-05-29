"use client";
import { useState } from "react";
import Link from "next/link";
import { useLastRun } from "@/lib/useLastRun";
import { PageHeader, Badge, Spinner } from "@/components/ui";
import { fmtPct } from "@/lib/api";

export default function Memo() {
  const { run, loading } = useLastRun();
  const [gate, setGate] = useState<"pending" | "approved" | "rejected">("pending");

  if (loading) return <Spinner label="Loading decision memo…" />;
  if (!run?.decision)
    return (
      <div className="card p-10 text-center">
        <p className="text-sm text-ink-soft">No decision yet.</p>
        <Link href="/convene" className="btn-primary mt-4">Convene a committee</Link>
      </div>
    );

  const d = run.decision;
  const invested = d.positions.filter((p: any) => p.target_weight > 0);

  return (
    <div>
      <PageHeader title="Decision Memo"
        subtitle={`Investment Committee recommendation · as of ${run.mandate?.as_of_date}`}
        action={
          <div className="flex items-center gap-2">
            {run.status === "escalated"
              ? <Badge tone="warn">escalated</Badge> : <Badge tone="bull">decided</Badge>}
            <Badge tone="brand">confidence {d.confidence}</Badge>
            <button onClick={() => window.print()} className="btn-ghost">Export PDF</button>
          </div>
        } />

      {/* Allocation */}
      <div className="card mb-6 p-6">
        <h3 className="mb-4 font-semibold text-ink">Recommended allocation</h3>
        <div className="mb-4 flex h-3 w-full overflow-hidden rounded-full bg-surface-subtle">
          {invested.map((p: any, i: number) => (
            <div key={p.ticker} title={`${p.ticker} ${fmtPct(p.target_weight)}`}
              style={{ width: `${p.target_weight * 100}%`,
                background: `hsl(${245 - i * 18} 90% ${62 + i * 2}%)` }} />
          ))}
          <div style={{ width: `${d.cash_weight * 100}%` }} className="bg-surface-line" />
        </div>
        <div className="space-y-2">
          {invested.map((p: any) => (
            <div key={p.ticker} className="flex items-center justify-between border-b border-surface-line py-2 text-sm last:border-0">
              <div className="flex items-center gap-3">
                <span className="font-mono font-bold text-ink">{p.ticker}</span>
                <Badge tone={p.action === "buy" ? "bull" : p.action === "avoid" ? "bear" : "neutral"}>
                  {p.action}
                </Badge>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-ink-faint">conf {p.confidence}</span>
                <span className="w-14 text-right font-mono font-semibold text-brand">
                  {fmtPct(p.target_weight)}
                </span>
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between py-2 text-sm">
            <span className="font-mono font-semibold text-ink-soft">CASH</span>
            <span className="font-mono font-semibold text-ink-soft">{fmtPct(d.cash_weight)}</span>
          </div>
        </div>
      </div>

      {/* Rationale + dissent */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="mb-2 font-semibold text-ink">PM rationale</h3>
          <p className="text-sm leading-relaxed text-ink-soft">{d.rationale}</p>
        </div>
        <div className="card border-bear/20 p-6">
          <h3 className="mb-2 font-semibold text-bear">Strongest surviving counter-argument</h3>
          <p className="text-sm leading-relaxed text-ink-soft">
            {d.surviving_counterargument || "No material dissent survived the debate."}
          </p>
          {run.critique?.findings?.length > 0 && (
            <div className="mt-4">
              <div className="stat-label mb-1">Critic findings</div>
              <ul className="list-disc space-y-1 pl-5 text-xs text-ink-soft">
                {run.critique.findings.map((f: string, i: number) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Human gate */}
      <div className="card mt-6 p-6">
        <h3 className="mb-3 font-semibold text-ink">Human gate</h3>
        {gate === "pending" ? (
          <div className="flex items-center gap-3">
            <button onClick={() => setGate("approved")} className="btn-primary !bg-bull">Approve</button>
            <button className="btn-ghost">Edit weights</button>
            <button onClick={() => setGate("rejected")} className="btn-ghost !text-bear">Reject</button>
            <span className="ml-2 text-xs text-ink-faint">
              The committee recommends; a human decides. No capital is deployed.
            </span>
          </div>
        ) : (
          <Badge tone={gate === "approved" ? "bull" : "bear"}>
            {gate === "approved" ? "Approved by reviewer (paper)" : "Rejected by reviewer"}
          </Badge>
        )}
      </div>

      <p className="mt-4 text-xs text-ink-faint">
        Ran {run.rounds_run} debate round(s) · {run.audit_trail?.length || 0} audited agent turns ·
        engine {run.audit_trail?.[0]?.model || "deterministic"}. Decision-support only; not financial advice.
      </p>
    </div>
  );
}
