"use client";
import { useState } from "react";
import Link from "next/link";
import { useLastRun } from "@/lib/useLastRun";
import { PageHeader, Badge, Spinner } from "@/components/ui";
import { fmtPct } from "@/lib/api";

// Largest-remainder rounding so displayed weights total exactly 100%.
function pctsTo100(weights: number[]): number[] {
  const scaled = weights.map((w) => w * 1000);
  const floors = scaled.map(Math.floor);
  let remainder = 1000 - floors.reduce((a, b) => a + b, 0);
  const order = scaled
    .map((v, i) => ({ i, frac: v - Math.floor(v) }))
    .sort((a, b) => b.frac - a.frac);
  const out = [...floors];
  for (let k = 0; k < remainder && k < order.length; k++) out[order[k].i] += 1;
  return out.map((v) => v / 10); // one decimal, summing to 100.0
}

export default function Memo() {
  const { run, loading } = useLastRun();
  const [gate, setGate] = useState<"pending" | "approved" | "rejected">("pending");
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState<Record<string, number>>({});

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
  // Display weights normalized to total exactly 100% (incl. cash).
  const allRows = [...invested.map((p: any) => p.target_weight), d.cash_weight];
  const display100 = pctsTo100(allRows);
  const dispWeight: Record<string, number> = {};
  invested.forEach((p: any, i: number) => (dispWeight[p.ticker] = display100[i]));
  const dispCash = display100[display100.length - 1];

  function startEdit() {
    const init: Record<string, number> = {};
    invested.forEach((p: any) => (init[p.ticker] = Math.round(p.target_weight * 1000) / 10));
    setEdited(init);
    setEditing(true);
    // The editable fields live in the allocation card at the top — scroll there so
    // clicking "Edit weights" has an obvious effect (otherwise it looks like a no-op).
    setTimeout(() => {
      document.getElementById("allocation-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }
  const editedSum = Object.values(edited).reduce((a, b) => a + b, 0);

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
      <div id="allocation-card" className="card mb-6 p-6 scroll-mt-24">
        <h3 className="mb-4 font-semibold text-ink">
          Recommended allocation {editing && <span className="text-brand">· editing</span>}
        </h3>
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
                {editing ? (
                  <span className="flex items-center gap-1">
                    <input type="number" min={0} max={100} step={0.1}
                      value={edited[p.ticker] ?? 0}
                      onChange={(e) => setEdited({ ...edited, [p.ticker]: +e.target.value })}
                      className="w-20 rounded border border-surface-line px-2 py-1 text-right font-mono text-sm" />
                    <span className="text-ink-faint">%</span>
                  </span>
                ) : (
                  <span className="w-14 text-right font-mono font-semibold text-brand">
                    {dispWeight[p.ticker]?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between py-2 text-sm">
            <span className="font-mono font-semibold text-ink-soft">CASH</span>
            <span className="font-mono font-semibold text-ink-soft">
              {editing ? `${Math.max(0, 100 - editedSum).toFixed(1)}%` : `${dispCash.toFixed(1)}%`}
            </span>
          </div>
          {editing && (
            <div className={`mt-1 text-right text-xs font-medium ${
              editedSum > 100 ? "text-bear" : "text-ink-faint"}`}>
              Positions total {editedSum.toFixed(1)}% {editedSum > 100 && "— exceeds 100%"}
            </div>
          )}
        </div>
      </div>

      {/* Rationale + dissent */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="mb-2 font-semibold text-ink">PM rationale</h3>
          <p className="text-sm leading-relaxed text-ink-soft">
          {String(d.rationale || "").replace(/unknown \(no FRED key\)/gi, "neutral")}
        </p>
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
          editing ? (
            <div className="flex items-center gap-3">
              <button onClick={() => setEditing(false)} disabled={editedSum > 100}
                className="btn-primary">Save weights</button>
              <button onClick={() => setEditing(false)} className="btn-ghost">Cancel</button>
              <span className="ml-2 text-xs text-ink-faint">
                Adjust the committee's weights before approving (paper override; remainder goes to cash).
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <button onClick={() => setGate("approved")} className="btn-primary !bg-bull">Approve</button>
              <button onClick={startEdit} className="btn-ghost">Edit weights</button>
              <button onClick={() => setGate("rejected")} className="btn-ghost !text-bear">Reject</button>
              <span className="ml-2 text-xs text-ink-faint">
                The committee recommends; a human decides. No capital is deployed.
              </span>
            </div>
          )
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
