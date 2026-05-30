"use client";
import {
  Area, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Line,
} from "recharts";
import { fmtUSD } from "@/lib/api";

type Point = { date: string; value: number; benchmark?: number | null };

// Adaptive money formatting: $525, $9.5k, $1.2M — never the misleading "$0k".
function money(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (a >= 10_000) return `$${(v / 1000).toFixed(0)}k`;
  if (a >= 1_000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
}

export default function EquityChart({ data, showBenchmark = true, height = 320 }:
  { data: Point[]; showBenchmark?: boolean; height?: number }) {
  if (!data?.length)
    return <div className="flex h-64 items-center justify-center text-sm text-ink-faint">No data yet.</div>;

  // Use a real time axis so gaps reflect elapsed time (fixes evenly-spaced index axis).
  const rows = data.map((d) => ({
    ...d,
    t: new Date(d.date).getTime(),
  }));
  const hasBench = showBenchmark && rows.some((r) => r.benchmark != null);

  const fmtDate = (t: number) => {
    const d = new Date(t);
    return `${String(d.getFullYear()).slice(2)}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#635bff" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#635bff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
        <XAxis
          dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
          tick={{ fontSize: 11, fill: "#8792a2" }} minTickGap={56}
          tickLine={false} axisLine={{ stroke: "#e6ebf1" }}
          tickFormatter={fmtDate}
        />
        <YAxis tick={{ fontSize: 11, fill: "#8792a2" }} tickLine={false} axisLine={false}
          width={64} tickFormatter={money} domain={["auto", "auto"]} allowDecimals={false} />
        <Tooltip
          contentStyle={{ borderRadius: 12, border: "1px solid #e6ebf1",
            boxShadow: "0 8px 24px rgba(10,37,64,0.08)", fontSize: 12 }}
          labelFormatter={(t: any) => new Date(t).toISOString().slice(0, 10)}
          formatter={(v: any, name) => [fmtUSD(v), name === "value" ? "QUORUM" : "Benchmark (SPY)"]}
        />
        <Area type="monotone" dataKey="value" name="value" stroke="#635bff" strokeWidth={2.5}
          fill="url(#g)" dot={false} />
        {hasBench && (
          <Line type="monotone" dataKey="benchmark" name="benchmark" stroke="#8792a2"
            strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
