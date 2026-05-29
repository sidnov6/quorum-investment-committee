"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getJSON, postJSON, fmtUSD, fmtPct } from "@/lib/api";
import { StatCard } from "@/components/ui";
import EquityChart from "@/components/EquityChart";

export default function Overview() {
  const [health, setHealth] = useState<any>(null);
  const [bt, setBt] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJSON("/api/health").then(setHealth).catch(() => {});
    (async () => {
      try {
        const list = await getJSON("/api/backtest/list");
        if (list?.length) setBt(await getJSON(`/api/backtest/${list[0].id}`));
      } catch {}
      setLoading(false);
    })();
  }, []);

  const m = bt?.metrics;

  return (
    <div>
      {/* Hero */}
      <div className="stripe-hero relative mb-8 overflow-hidden rounded-2xl px-8 py-12 text-white shadow-lift animate-fadeUp">
        <div className="relative z-10 max-w-2xl">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium backdrop-blur">
            <span className="live-dot h-2 w-2 rounded-full bg-emerald-400" />
            {health ? `${health.universe_size} names · ${health.llm?.[0]} engine` : "connecting…"}
          </div>
          <h1 className="text-4xl font-extrabold leading-tight tracking-tight">
            The AI <span className="gradient-text">investment committee</span> that argues before it decides.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-white/70">
            A bull, a bear, a macro strategist, a quant risk officer and a portfolio manager
            debate from real market data across structured rounds — then converge on a
            documented, fully-sourced allocation. Every figure traces to a filing or a price.
          </p>
          <div className="mt-7 flex gap-3">
            <Link href="/convene" className="btn-primary !bg-white !text-ink">Convene a committee →</Link>
            <Link href="/backtest" className="btn-ghost !text-white hover:!bg-white/10">View backtest</Link>
          </div>
        </div>
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full stripe-gradient opacity-40 blur-3xl" />
      </div>

      {/* Headline stats from latest backtest */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Latest evaluated track record</h2>
        {bt && <span className="text-xs text-ink-faint">{bt.start} → {bt.end}</span>}
      </div>
      {loading ? (
        <div className="card p-8 text-sm text-ink-faint">Loading…</div>
      ) : !bt ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink-soft">No backtest yet.</p>
          <Link href="/backtest" className="btn-primary mt-4">Run your first backtest</Link>
        </div>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Portfolio value" value={fmtUSD(bt.final_value)}
              sub={`from ${fmtUSD(bt.starting_cash)}`} />
            <StatCard label="Total return" value={fmtPct(m.total_return)}
              accent={m.total_return >= 0 ? "text-bull" : "text-bear"}
              sub={`vs SPY ${fmtPct(m.benchmark?.total_return || 0)}`} />
            <StatCard label="Sharpe" value={m.sharpe?.toFixed(2)}
              sub={`vol ${fmtPct(m.annualized_vol)}`} />
            <StatCard label="Max drawdown" value={fmtPct(m.max_drawdown)} accent="text-bear"
              sub="peak-to-trough" />
          </div>
          <div className="card p-5">
            <EquityChart data={bt.equity_curve} />
          </div>
        </>
      )}

      {/* How it works */}
      <h2 className="mb-3 mt-10 text-lg font-semibold text-ink">How the committee works</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Grounded in real data", "SEC EDGAR fundamentals, point-in-time prices, news & macro — every quantitative claim is verified against fetched data or rejected."],
          ["Genuine disagreement", "Bull and bear write independently, then rebut. A risk officer can veto. A critic stress-tests for groupthink. Dissent is preserved, never averaged away."],
          ["Honest by construction", "Point-in-time snapshots prevent lookahead, trades cost money, and the system flags low-confidence or unresolved calls. Decision-support, not an alpha claim."],
        ].map(([t, d]) => (
          <div key={t} className="card p-5">
            <div className="mb-2 h-8 w-8 rounded-lg stripe-gradient" />
            <div className="font-semibold text-ink">{t}</div>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">{d}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
