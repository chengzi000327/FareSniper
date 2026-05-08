"use client";
import React, { useEffect, useState } from "react";
import { alertsApi } from "@/lib/api";

export default function PersonalPage() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { alertsApi.list().then(setData); }, []);
  if (!data) return null;
  return (
    <ul>
      {data.alerts.map((a: any) => (
        <li key={a.id}>{a.origin}-{a.destination} ≤ {a.target_price}</li>
      ))}
    </ul>
  );
}
