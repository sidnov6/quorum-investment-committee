"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON, postJSON, fmtUSD, fmtPct } from "@/lib/api";
import { PageHeader, StatCard, Badge, Spinner } from "@/components/ui";
import EquityChart from "@/components/EquityChart";
import Subscribe from "@/components/Subscribe";

export default function Portfolio() {
  const [snap, setSnap] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [asOf, setAsOf] = useState("");

  async function load() {
    try { setSnap(await getJSON("/api/portfolio")); } catch {}
    setLoading(false);
  }
  useEffect(() => { load(); setAsOf(new Date().toISOString().slice(0, 10)); }, []);

  async function runToday() {
    setRunning(true);
    try {
      await postJSON(`/api/portfolio/run-today${asOf ? `?as_of_date=${asOf}` : ""}`, {});
      await load();
    } catch {}
    setRunning(false);
  }

  if (loading) return <Spinner label="Loading paper portfolio…" />;

  const curve = (snap?.curve || []).map((c: any) => ({ date: c.date, value: c.value }));
  const ret = snap?.total_return || 0;

  return (
    <div>
      <PageHeader title="Paper Portfolio"
        subtitle="The live $10,000 account — one continuous track record that moves only when a committee meeting fires. Distinct from the simulated backtests. No real capital is traded."
        action={
          <div className="flex items-center gap-2">
            <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
              className="rounded-lg border border-surface-line px-3 py-2 text-sm" />
            <button onClick={runToday} disabled={running} className="btn-primary">
              {running ? "Convening…" : "Run committee for date"}
            </button>
          </div>
        } />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Portfolio value" value={fmtUSD(snap?.value || 10000)}
          sub={snap?.last_run ? `last run ${snap.last_run}` : "not started"} />
        <StatCard label="Total return" value={fmtPct(ret)}
          accent={ret >= 0 ? "text-bull" : "text-bear"} sub="since inception" />
        <StatCard label="Cash" value={fmtUSD(snap?.cash || 0)} />
        <StatCard label="Holdings" value={snap?.holdings?.length || 0} sub="positions" />
      </div>

      {curve.length > 1 ? (
        <div className="card mb-6 p-5"><EquityChart data={curve} showBenchmark={false} /></div>
      ) : (
        <div className="card mb-6 p-8 text-center">
          <p className="text-sm text-ink-soft">
            No track record yet. Pick a date and run the committee to start building one —
            run it across several dates to grow the curve.
          </p>
        </div>
      )}

      {snap?.holdings?.length > 0 && (
        <>
          <h3 className="mb-3 text-sm font-semibold text-ink">Current holdings</h3>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface-subtle text-left text-xs uppercase tracking-wide text-ink-faint">
                <tr>{["Ticker", "Company", "Sector", "Shares", "Price", "Value"].map((h) =>
                  <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr>
              </thead>
              <tbody>
                {snap.holdings.map((h: any) => (
                  <tr key={h.ticker} className="border-t border-surface-line">
                    <td className="px-4 py-3 font-mono font-semibold text-ink">{h.ticker}</td>
                    <td className="px-4 py-3 text-ink-soft">{h.name}</td>
                    <td className="px-4 py-3"><Badge>{h.sector}</Badge></td>
                    <td className="px-4 py-3 font-mono">{h.shares}</td>
                    <td className="px-4 py-3 font-mono">{fmtUSD(h.price)}</td>
                    <td className="px-4 py-3 font-mono font-semibold">{fmtUSD(h.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="mt-8">
        <Subscribe />
      </div>

      <p className="mt-4 text-xs text-ink-faint">
        The committee runs automatically every weekday (GitHub Actions cron →
        <span className="font-mono"> POST /api/daily/run</span>), restructures within risk limits,
        scans held names for sudden drops or negative news, and emails subscribers their report.
      </p>
    </div>
  );
}
