"use client";
import React, { useEffect, useState, use } from "react";
import { priceHistoryApi } from "@/lib/api";
import { PriceHistoryChart } from "@/components/PriceHistoryChart";

export default function PriceHistoryPage({ params }: { params: Promise<{ route: string }> }) {
  const { route } = use(params);
  const [origin, destination] = route.split("-");
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    priceHistoryApi.get(origin, destination, 30).then(setData);
  }, [origin, destination]);
  if (!data) return null;
  return <PriceHistoryChart data={data.points} />;
}
