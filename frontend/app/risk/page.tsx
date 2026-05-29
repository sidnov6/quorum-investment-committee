"use client";
import Link from "next/link";
import { useLastRun } from "@/lib/useLastRun";
import { PageHeader, StatCard, Badge, Spinner } from "@/components/ui";
import { fmtPct } from "@/lib/api";

export default function RiskDesk() {
  const { run, loading } = useLastRun();
  if (loading) return <Spinner label="Loading risk assessment…" />;
  if (!run?.risk_assessment)
    return <Empty />;

  const r = run.risk_assessment;
  const port = r.portfolio || {};
  const c = r.constraints || {};

  return (
    <div>
      <PageHeader title="Risk Desk"
        subtitle={`Quantitative downside & hard limits · as of ${run.mandate?.as_of_date}`}
        action={r.veto ? <Badge tone="bear">VETO ACTIVE</Badge> : <Badge tone="bull">within limits</Badge>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Portfolio vol (ann.)" value={port.annualized_vol != null ? fmtPct(port.annualized_vol) : "—"}
          sub={`limit ${fmtPct(c.max_portfolio_vol || 0)}`} />
        <StatCard label="1-day VaR (95%)" value={port.var_1d_hist != null ? fmtPct(port.var_1d_hist) : "—"}
          accent="text-bear" sub="historical" />
        <StatCard label="Max drawdown (hist.)" value={port.max_drawdown != null ? fmtPct(port.max_drawdown) : "—"}
          accent="text-bear" />
        <StatCard label="Sharpe (lookback)" value={port.sharpe != null ? port.sharpe.toFixed(2) : "—"} />
      </div>

      {r.veto && (
        <div className="mb-6 rounded-xl border border-bear/30 bg-bear/5 p-4 text-sm text-bear">
          <span className="font-semibold">Risk Officer veto:</span> {r.veto_reason}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-subtle text-left text-xs uppercase tracking-wide text-ink-faint">
            <tr>
              {["Ticker", "Ann. vol", "Beta", "Max DD", "1d VaR", "Sharpe"].map((h) => (
                <th key={h} className="px-4 py-3 font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(r.per_ticker).map(([t, m]: any) => (
              <tr key={t} className="border-t border-surface-line">
                <td className="px-4 py-3 font-mono font-semibold text-ink">{t}</td>
                {m.available ? (
                  <>
                    <td className="px-4 py-3 font-mono">{fmtPct(m.annualized_vol)}</td>
                    <td className="px-4 py-3 font-mono">{m.beta ?? "—"}</td>
                    <td className="px-4 py-3 font-mono text-bear">{fmtPct(m.max_drawdown)}</td>
                    <td className="px-4 py-3 font-mono text-bear">{fmtPct(m.var_1d_hist)}</td>
                    <td className="px-4 py-3 font-mono">{m.sharpe}</td>
                  </>
                ) : (
                  <td colSpan={5} className="px-4 py-3 text-ink-faint">insufficient data</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-ink-faint">
        All metrics computed deterministically (NumPy/SciPy) from point-in-time prices — never by the LLM.
        Constraints: max {fmtPct(c.max_position_weight || 0)} per position, max {fmtPct(c.max_portfolio_vol || 0)} portfolio vol.
      </p>
    </div>
  );
}

function Empty() {
  return (
    <div className="card p-10 text-center">
      <p className="text-sm text-ink-soft">No committee run yet.</p>
      <Link href="/convene" className="btn-primary mt-4">Convene a committee</Link>
    </div>
  );
}
