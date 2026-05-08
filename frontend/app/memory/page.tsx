"use client";
import React, { useEffect, useState } from "react";
import { memoryApi } from "@/lib/api";

export default function MemoryPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { memoryApi.get().then(setData); }, []);
  if (!data) return null;
  return (
    <ul>
      {data.memories.map((m: any) => (
        <li key={m.field}>{m.field}: {String(m.value)} ({m.source})</li>
      ))}
    </ul>
  );
}
