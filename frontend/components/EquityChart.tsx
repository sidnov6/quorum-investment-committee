"use client";
import {
  Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Line,
} from "recharts";
import { fmtUSD } from "@/lib/api";

type Point = { date: string; value: number; benchmark?: number | null };

export default function EquityChart({ data, showBenchmark = true, height = 320 }:
  { data: Point[]; showBenchmark?: boolean; height?: number }) {
  if (!data?.length)
    return <div className="flex h-64 items-center justify-center text-sm text-ink-faint">No data yet.</div>;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#635bff" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#635bff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8792a2" }} minTickGap={48}
          tickLine={false} axisLine={{ stroke: "#e6ebf1" }}
          tickFormatter={(d) => String(d).slice(2, 7)} />
        <YAxis tick={{ fontSize: 11, fill: "#8792a2" }} tickLine={false} axisLine={false}
          width={64} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{ borderRadius: 12, border: "1px solid #e6ebf1",
            boxShadow: "0 8px 24px rgba(10,37,64,0.08)", fontSize: 12 }}
          formatter={(v: any, name) => [fmtUSD(v), name === "value" ? "QUORUM" : "Benchmark"]}
        />
        <Area type="monotone" dataKey="value" stroke="#635bff" strokeWidth={2.5}
          fill="url(#g)" dot={false} />
        {showBenchmark && (
          <Line type="monotone" dataKey="benchmark" stroke="#8792a2" strokeWidth={1.5}
            strokeDasharray="4 4" dot={false} />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
