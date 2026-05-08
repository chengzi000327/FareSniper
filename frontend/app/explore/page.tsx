"use client";
import React, { useEffect, useState } from "react";
import { recApi } from "@/lib/api";

export default function ExplorePage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { recApi.list().then(setData); }, []);
  if (!data) return null;
  return (
    <ul>
      {data.cards.map((c: any) => (
        <li key={c.title}><span>{c.title}</span> — {c.reason}</li>
      ))}
    </ul>
  );
}
