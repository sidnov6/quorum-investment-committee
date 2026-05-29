"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/", label: "Overview", icon: "M3 12l9-9 9 9M5 10v10h14V10" },
  { href: "/portfolio", label: "Paper Portfolio", icon: "M3 3v18h18M7 14l4-4 3 3 5-6" },
  { href: "/convene", label: "Convene Committee", icon: "M12 5v14M5 12h14" },
  { href: "/debate", label: "Debate Floor", icon: "M4 5h16v10H8l-4 4z" },
  { href: "/risk", label: "Risk Desk", icon: "M12 3l9 4v6c0 5-3.8 8-9 9-5.2-1-9-4-9-9V7z" },
  { href: "/memo", label: "Decision Memo", icon: "M6 2h9l5 5v15H6zM15 2v5h5" },
  { href: "/backtest", label: "Backtest", icon: "M4 19V5m0 14h16M8 15l3-4 3 2 4-6" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="fixed left-0 top-0 z-30 hidden h-screen w-64 flex-col border-r border-surface-line bg-white lg:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="stripe-gradient flex h-9 w-9 items-center justify-center rounded-xl text-white shadow-sm">
          <span className="text-lg font-extrabold">Q</span>
        </div>
        <div>
          <div className="text-[15px] font-bold tracking-tight text-ink">QUORUM</div>
          <div className="text-[11px] font-medium text-ink-faint">Investment Committee</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {nav.map((n) => {
          const active = path === n.href;
          return (
            <Link key={n.href} href={n.href}
              className={`nav-item ${active ? "nav-item-active" : ""}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d={n.icon} />
              </svg>
              {n.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-4 py-4">
        <div className="rounded-xl bg-surface-subtle p-3 text-[11px] leading-relaxed text-ink-faint">
          <span className="font-semibold text-ink-soft">Decision-support only.</span> Not
          financial advice. No live capital is traded — paper portfolio, grounded in real data.
        </div>
      </div>
    </aside>
  );
}
