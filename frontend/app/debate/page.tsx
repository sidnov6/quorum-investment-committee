"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { API, agentColor } from "@/lib/api";
import { Badge, PillarBar, Spinner } from "@/components/ui";

const AGENT_LABEL: Record<string, string> = {
  chair: "Chair", research: "Research", bull: "Bull", bear: "Bear",
  macro: "Macro", risk: "Risk Officer", pm: "Portfolio Mgr", critic: "Critic",
};

function DebateInner() {
  const sp = useSearchParams();
  const [turns, setTurns] = useState<any[]>([]);
  const [screen, setScreen] = useState<any[]>([]);
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [status, setStatus] = useState("idle");
  const [final, setFinal] = useState<any>(null);
  const [live, setLive] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  function start() {
    setTurns([]); setScreen([]); setShortlist([]); setFinal(null);
    setStatus("convening"); setLive(true);
    const params = new URLSearchParams();
    params.set("as_of_date", sp.get("as_of") || new Date().toISOString().slice(0, 10));
    params.set("shortlist_k", sp.get("k") || "8");
    if (sp.get("candidates")) params.set("candidates", sp.get("candidates")!);

    const es = new EventSource(`${API}/api/committee/stream?${params.toString()}`);
    esRef.current = es;
    es.addEventListener("turn", (e: any) => {
      const t = JSON.parse(e.data);
      if (t.kind === "brief" && t.agent === "chair") {
        setScreen(t.payload?.screen || []);
        setShortlist(t.payload?.shortlist || []);
      }
      setStatus(t.kind === "decision" ? "deciding" : t.agent);
      setTurns((prev) => [...prev, t]);
    });
    es.addEventListener("final", (e: any) => {
      const f = JSON.parse(e.data);
      setFinal(f);
      setStatus(f.status);
      setLive(false);
      try { localStorage.setItem("quorum:lastRun", JSON.stringify(f)); } catch {}
      es.close();
    });
    es.onerror = () => { setLive(false); es.close(); };
  }

  useEffect(() => { start(); return () => esRef.current?.close(); // eslint-disable-next-line
  }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns]);

  const side = (a: string) => (a === "bull" ? "left" : a === "bear" ? "right" : "center");

  return (
    <div>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-ink">Debate Floor</h1>
          <p className="mt-1 text-sm text-ink-soft">
            As of {sp.get("as_of") || "today"} · watch the committee reason in real time.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {live && (
            <span className="chip bg-brand/10 text-brand">
              <span className="live-dot mr-1 inline-block h-2 w-2 rounded-full bg-brand" />
              {AGENT_LABEL[status] || status}
            </span>
          )}
          <button onClick={start} disabled={live} className="btn-primary">
            {live ? "In session…" : "Re-convene"}
          </button>
        </div>
      </div>

      {/* Screen / shortlist */}
      {screen.length > 0 && (
        <div className="card mb-6 p-5 animate-fadeUp">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">Universe screen → shortlist</h3>
            <span className="text-xs text-ink-faint">{screen.length} names ranked by composite</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {[...screen].sort((a, b) => b.composite - a.composite).map((r) => (
              <span key={r.ticker}
                className={`chip border ${r.shortlisted
                  ? "border-brand/30 bg-brand/10 text-brand"
                  : "border-surface-line bg-white text-ink-faint"}`}
                title={`${r.sector} · composite ${r.composite}`}>
                {r.ticker} <span className="ml-1 opacity-60">{r.composite > 0 ? "+" : ""}{r.composite}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Live transcript: bull left, bear right, others center */}
      <div className="card p-2 sm:p-5">
        <div className="max-h-[60vh] space-y-2 overflow-y-auto px-1">
          {turns.length === 0 && <div className="p-8"><Spinner label="Convening the committee…" /></div>}
          {turns.map((t, i) => {
            const s = side(t.agent);
            return (
              <div key={i} className={`flex animate-fadeUp ${
                s === "left" ? "justify-start" : s === "right" ? "justify-end" : "justify-center"}`}>
                <div className={`max-w-[80%] rounded-xl border px-4 py-2.5 text-sm ${
                  s === "left" ? "border-bull/20 bg-bull/[0.04]"
                  : s === "right" ? "border-bear/20 bg-bear/[0.04]"
                  : "border-surface-line bg-surface-subtle"}`}>
                  <div className="mb-1 flex items-center gap-2">
                    <span className={`text-xs font-bold ${agentColor[t.agent] || "text-ink-soft"}`}>
                      {AGENT_LABEL[t.agent] || t.agent}
                    </span>
                    {t.payload?.ticker && <Badge>{t.payload.ticker}</Badge>}
                    {t.kind === "rebuttal" && <Badge tone="warn">rebuttal</Badge>}
                    {typeof t.payload?.confidence === "number" &&
                      <span className="text-[10px] text-ink-faint">conf {t.payload.confidence}</span>}
                  </div>
                  <p className="leading-relaxed text-ink">{t.content}</p>
                  {t.payload?.evidence?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {t.payload.evidence.map((c: any, j: number) => (
                        <span key={j} className="chip bg-white text-ink-faint border border-surface-line"
                          title={`${c.source} · ${c.as_of}`}>
                          {c.field}={typeof c.value === "number" ? c.value : c.value} ✓
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Decision summary + links */}
      {final?.decision && (
        <div className="card mt-6 p-6 animate-fadeUp">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-ink">Recommendation</h3>
            <div className="flex items-center gap-2">
              {final.status === "escalated"
                ? <Badge tone="warn">escalated · unresolved dissent</Badge>
                : <Badge tone="bull">decided</Badge>}
              <Badge tone="brand">confidence {final.decision.confidence}</Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {final.decision.positions.filter((p: any) => p.target_weight > 0).map((p: any) => (
              <span key={p.ticker} className="chip bg-brand/10 text-brand">
                {p.ticker} {(p.target_weight * 100).toFixed(1)}%
              </span>
            ))}
            <span className="chip bg-surface-subtle text-ink-soft">
              CASH {(final.decision.cash_weight * 100).toFixed(1)}%
            </span>
          </div>
          <p className="mt-3 text-sm text-ink-soft">{final.decision.rationale}</p>
          <div className="mt-5 flex gap-3">
            <Link href="/memo" className="btn-primary">Open decision memo →</Link>
            <Link href="/risk" className="btn-ghost">View risk desk</Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Debate() {
  return (
    <Suspense fallback={<Spinner label="Loading…" />}>
      <DebateInner />
    </Suspense>
  );
}
