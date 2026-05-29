"use client";
import { useEffect, useState } from "react";
import { getJSON } from "@/lib/api";

export function useLastRun() {
  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const cached = localStorage.getItem("quorum:lastRun");
        if (cached) { setRun(JSON.parse(cached)); setLoading(false); return; }
      } catch {}
      try {
        const runs = await getJSON("/api/committee/runs");
        if (runs?.length) setRun(await getJSON(`/api/committee/runs/${runs[0].id}`));
      } catch {}
      setLoading(false);
    })();
  }, []);

  return { run, loading };
}
