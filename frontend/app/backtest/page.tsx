"use client";
import { useState } from "react";
import { postJSON, fmtUSD, fmtPct } from "@/lib/api";
import { PageHeader, StatCard, Badge, Spinner } from "@/components/ui";
import EquityChart from "@/components/EquityChart";

export default function Backtest() {
  const [start, setStart] = useState("2023-01-01");
  const [end, setEnd] = useState("2024-12-31");
  const [reb, setReb] = useState(21);
  const [cash, setCash] = useState(10000);
  const [running, setRunning] = useState(false);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");

  function validate(): string {
    if (!start || !end) return "Pick both a start and end date.";
    if (new Date(end) <= new Date(start)) return "End date must be after the start date.";
    if (new Date(end) > new Date()) return "End date can't be in the future.";
    if (!Number.isFinite(reb) || reb < 1) return "Rebalance must be at least 1 trading day.";
    if (!Number.isFinite(cash) || cash <= 0) return "Starting cash must be greater than $0.";
    const days = (new Date(end).getTime() - new Date(start).getTime()) / 86400000;
    if (days < reb) return "Date range is shorter than one rebalance period.";
    return "";
  }

  async function run() {
    const v = validate();
    if (v) { setErr(v); setRes(null); return; }
    setRunning(true); setErr(""); setRes(null);
    try {
      const r = await postJSON("/api/backtest/run", {
        start, end, rebalance_days: reb, starting_cash: cash,
      });
      if (r.error) setErr(r.error); else setRes(r);
    } catch (e: any) { setErr(String(e.message || e)); }
    setRunning(false);
  }

  const invalid = validate();
  const m = res?.metrics;

  return (
    <div>
      <PageHeader title="Backtest"
        subtitle="A simulated 'what-if' replay of the committee across a historical date range — results vary by range/settings and are separate from the live Paper Portfolio. Point-in-time, costs included, no lookahead." />

      <div className="card mb-6 p-5">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <Field label="Start"><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="inp" /></Field>
          <Field label="End"><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="inp" /></Field>
          <Field label="Rebalance (days)"><input type="number" value={reb} onChange={(e) => setReb(+e.target.value)} className="inp" /></Field>
          <Field label="Starting cash"><input type="number" value={cash} onChange={(e) => setCash(+e.target.value)} className="inp" /></Field>
          <div className="flex items-end">
            <button onClick={run} disabled={running || !!invalid} title={invalid || ""}
              className="btn-primary w-full">
              {running ? "Running…" : "Run backtest"}
            </button>
          </div>
        </div>
        {invalid ? (
          <p className="mt-3 text-xs font-medium text-bear">⚠ {invalid}</p>
        ) : (
          <p className="mt-3 text-xs text-ink-faint">
            Screens the full 51-name universe and convenes the committee every {reb} trading
            {reb === 1 ? " day" : " days"}. First run for a date range fetches data (slower);
            subsequent runs are cached.
          </p>
        )}
      </div>

      {running && <div className="card p-8"><Spinner label="Convening committees across history…" /></div>}
      {err && <div className="rounded-xl border border-bear/30 bg-bear/5 p-4 text-sm text-bear">{err}</div>}

      {res && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Final value" value={fmtUSD(res.final_value)} sub={`from ${fmtUSD(res.starting_cash)}`} />
            <StatCard label="Total return" value={fmtPct(m.total_return)}
              accent={m.total_return >= 0 ? "text-bull" : "text-bear"}
              sub={`SPY ${fmtPct(m.benchmark?.total_return || 0)}`} />
            <StatCard label="Alpha vs SPY" value={m.alpha_vs_benchmark != null ? fmtPct(m.alpha_vs_benchmark) : "—"}
              accent={(m.alpha_vs_benchmark || 0) >= 0 ? "text-bull" : "text-bear"} />
            <StatCard label="Sharpe / Max DD" value={`${m.sharpe?.toFixed(2)}`}
              sub={`drawdown ${fmtPct(m.max_drawdown)}`} />
          </div>

          <div className="card mb-6 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Equity curve vs benchmark</h3>
              <div className="flex gap-3 text-xs">
                <span className="flex items-center gap-1"><span className="h-2 w-3 rounded bg-brand" /> QUORUM</span>
                <span className="flex items-center gap-1"><span className="h-2 w-3 rounded bg-ink-faint" /> SPY</span>
              </div>
            </div>
            <EquityChart data={res.equity_curve} />
          </div>

          <h3 className="mb-3 text-sm font-semibold text-ink">Committee meetings ({res.meetings.length})</h3>
          <div className="card divide-y divide-surface-line">
            {res.meetings.map((mt: any, i: number) => (
              <div key={i} className="flex items-center justify-between px-5 py-3 text-sm">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-ink-soft">{mt.date}</span>
                  <Badge tone={mt.status === "escalated" ? "warn" : "neutral"}>{mt.macro || "n/a"}</Badge>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-1.5">
                  {mt.decision.positions.filter((p: any) => p.target_weight > 0).slice(0, 6).map((p: any) => (
                    <span key={p.ticker} className="chip bg-brand/10 text-brand">
                      {p.ticker} {(p.target_weight * 100).toFixed(0)}%
                    </span>
                  ))}
                  <span className="ml-2 text-xs text-ink-faint">{fmtUSD(mt.port_value_before)}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      <style jsx global>{`.inp{width:100%;border:1px solid #e6ebf1;border-radius:8px;padding:8px 12px;font-size:14px}
        .inp:focus{outline:2px solid rgba(99,91,255,.3);border-color:#635bff}`}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="stat-label mb-1 block">{label}</label>
      {children}
    </div>
  );
}
