// Default to the deployed backend so the production bundle never references localhost.
// Local dev overrides this via .env.development.local (NEXT_PUBLIC_API_URL=127.0.0.1:8077).
export const API =
  process.env.NEXT_PUBLIC_API_URL || "https://quorum-api-a81d.onrender.com";

export async function getJSON<T = any>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export async function postJSON<T = any>(path: string, body: any): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const fmtUSD = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n ?? 0);

export const fmtPct = (n: number, digits = 1) =>
  `${(n * 100).toFixed(digits)}%`;

export const agentColor: Record<string, string> = {
  bull: "text-bull", bear: "text-bear", risk: "text-warn",
  macro: "text-macro", pm: "text-brand", critic: "text-ink",
  research: "text-ink-soft", chair: "text-ink-soft",
};
