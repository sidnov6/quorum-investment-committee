"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getJSON } from "@/lib/api";
import { PageHeader, Badge } from "@/components/ui";

export default function Convene() {
  const router = useRouter();
  const [universe, setUniverse] = useState<any>(null);
  const [asOf, setAsOf] = useState("");
  const [k, setK] = useState(8);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [useAll, setUseAll] = useState(true);

  useEffect(() => {
    getJSON("/api/universe").then(setUniverse).catch(() => {});
    setAsOf(new Date().toISOString().slice(0, 10));
  }, []);

  function toggle(t: string) {
    const n = new Set(selected);
    n.has(t) ? n.delete(t) : n.add(t);
    setSelected(n);
  }

  function convene() {
    const params = new URLSearchParams();
    params.set("as_of", asOf);
    params.set("k", String(k));
    if (!useAll && selected.size) params.set("candidates", Array.from(selected).join(","));
    router.push(`/debate?${params.toString()}`);
  }

  return (
    <div>
      <PageHeader title="Convene a committee"
        subtitle="Set the mandate. The committee will screen the universe, debate a shortlist, and recommend an allocation." />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-1">
          <h3 className="mb-4 font-semibold text-ink">Mandate</h3>

          <label className="stat-label">As-of date (point-in-time)</label>
          <input type="date" value={asOf} max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => setAsOf(e.target.value)}
            className="mt-1 w-full rounded-lg border border-surface-line px-3 py-2 text-sm" />
          <p className="mt-1 text-xs text-ink-faint">
            Use a past date to backtest the committee — it sees no data after this day.
          </p>

          <label className="stat-label mt-5 block">Shortlist size: {k}</label>
          <input type="range" min={3} max={14} value={k}
            onChange={(e) => setK(Number(e.target.value))}
            className="mt-2 w-full accent-brand" />

          <label className="mt-5 flex items-center gap-2 text-sm font-medium text-ink-soft">
            <input type="checkbox" checked={useAll} onChange={(e) => setUseAll(e.target.checked)}
              className="accent-brand" />
            Screen the full {universe?.count ?? ""}-name universe
          </label>

          <button onClick={convene} className="btn-primary mt-6 w-full">
            Convene committee →
          </button>
        </div>

        <div className="card p-6 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-ink">Universe</h3>
            <span className="text-xs text-ink-faint">
              {useAll ? "All names in play" : `${selected.size} selected`}
            </span>
          </div>
          {!universe ? (
            <p className="text-sm text-ink-faint">Loading…</p>
          ) : (
            <div className="space-y-4">
              {Object.entries(universe.sectors).map(([sector, ts]: any) => (
                <div key={sector}>
                  <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                    {sector}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {ts.map((t: string) => {
                      const on = useAll || selected.has(t);
                      return (
                        <button key={t} onClick={() => !useAll && toggle(t)}
                          className={`chip border transition ${
                            on ? "border-brand/30 bg-brand/10 text-brand"
                               : "border-surface-line bg-white text-ink-soft hover:border-brand/30"
                          } ${useAll ? "cursor-default" : "cursor-pointer"}`}>
                          {t}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
