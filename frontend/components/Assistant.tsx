"use client";
import { useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string; model?: string; tickers?: string[] };

const SUGGESTIONS = [
  "Why did the committee pick its top holding?",
  "How risky is my portfolio?",
  "Explain the bull vs bear case for NVDA",
  "What does the macro regime mean for my positions?",
];

export default function Assistant() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function send(q?: string) {
    const question = (q ?? input).trim();
    if (!question || busy) return;
    setInput("");
    const next = [...msgs, { role: "user" as const, content: question }];
    setMsgs(next);
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/assistant/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: next.slice(-6) }),
      });
      const d = await r.json();
      setMsgs((m) => [...m, { role: "assistant", content: d.answer, model: d.model, tickers: d.tickers }]);
    } catch {
      setMsgs((m) => [...m, { role: "assistant",
        content: "I couldn't reach the committee server. Make sure the API is running." }]);
    }
    setBusy(false);
  }

  return (
    <>
      {/* Floating launcher */}
      <button onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full
                   stripe-gradient text-white shadow-lift transition hover:scale-105 active:scale-95"
        aria-label="Open assistant">
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
            strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[560px] max-h-[calc(100vh-7rem)] w-[400px]
                        max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border
                        border-surface-line bg-white shadow-lift animate-fadeUp">
          {/* Header */}
          <div className="stripe-hero flex items-center gap-3 px-4 py-3 text-white">
            <div className="stripe-gradient flex h-9 w-9 items-center justify-center rounded-xl font-extrabold">Q</div>
            <div className="flex-1">
              <div className="text-sm font-semibold">Portfolio Assistant</div>
              <div className="text-[11px] text-white/60">Explains the committee · grounded in real data</div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 space-y-3 overflow-y-auto bg-surface-subtle px-3 py-4">
            {msgs.length === 0 && (
              <div className="space-y-3">
                <div className="rounded-xl border border-surface-line bg-white p-3 text-sm text-ink-soft">
                  👋 Hi! I'm your portfolio assistant. Ask me why the committee made a decision,
                  how risky a position is, or anything about the stocks in your universe.
                </div>
                <div className="space-y-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)}
                      className="block w-full rounded-lg border border-surface-line bg-white px-3 py-2 text-left
                                 text-xs font-medium text-ink-soft transition hover:border-brand/40 hover:text-brand">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm leading-relaxed ${
                  m.role === "user" ? "bg-brand text-white"
                  : "border border-surface-line bg-white text-ink"}`}>
                  {m.content}
                  {m.role === "assistant" && m.tickers && m.tickers.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {m.tickers.map((t) => <span key={t} className="chip bg-brand/10 text-brand">{t}</span>)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-xl border border-surface-line bg-white px-3 py-2.5">
                  <div className="flex gap-1">
                    <span className="adot" /><span className="adot" style={{ animationDelay: ".15s" }} />
                    <span className="adot" style={{ animationDelay: ".3s" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="border-t border-surface-line bg-white p-2.5">
            <div className="flex items-end gap-2">
              <textarea value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                rows={1} placeholder="Ask about your portfolio…"
                className="max-h-24 flex-1 resize-none rounded-lg border border-surface-line px-3 py-2 text-sm
                           outline-none focus:border-brand" />
              <button onClick={() => send()} disabled={busy || !input.trim()}
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-white
                           transition hover:bg-brand-dark disabled:opacity-40">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" /></svg>
              </button>
            </div>
            <p className="mt-1 px-1 text-[10px] text-ink-faint">Decision-support only · not financial advice</p>
          </div>
        </div>
      )}
      <style jsx global>{`
        .adot{width:6px;height:6px;border-radius:9999px;background:#8792a2;display:inline-block;
              animation:bounce 1s infinite ease-in-out}
      `}</style>
    </>
  );
}
