"use client";
import { useState } from "react";
import { API } from "@/lib/api";

export default function Subscribe() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "ok" | "err" | "busy">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.includes("@")) return;
    setState("busy");
    try {
      const r = await fetch(`${API}/api/subscribe`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const d = await r.json();
      setState(d.ok ? "ok" : "err");
    } catch { setState("err"); }
  }

  return (
    <div className="card p-6">
      <div className="flex items-start gap-4">
        <div className="stripe-gradient flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16v16H4zM4 7l8 6 8-6" /></svg>
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-ink">Daily portfolio report</h3>
          <p className="mt-0.5 text-sm text-ink-soft">
            Get the committee's daily decision, holdings, and any news-driven risk alerts in your inbox.
          </p>
          {state === "ok" ? (
            <div className="mt-3 rounded-lg bg-bull/10 px-3 py-2 text-sm font-medium text-bull">
              ✓ Subscribed — you'll get the next daily report.
            </div>
          ) : (
            <form onSubmit={submit} className="mt-3 flex gap-2">
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" required
                className="flex-1 rounded-lg border border-surface-line px-3 py-2 text-sm outline-none focus:border-brand" />
              <button type="submit" disabled={state === "busy"} className="btn-primary">
                {state === "busy" ? "…" : "Subscribe"}
              </button>
            </form>
          )}
          {state === "err" && <p className="mt-2 text-xs text-bear">Couldn't subscribe — try again.</p>}
          <p className="mt-2 text-[11px] text-ink-faint">
            Decision-support only · not financial advice · unsubscribe anytime.
          </p>
        </div>
      </div>
    </div>
  );
}
