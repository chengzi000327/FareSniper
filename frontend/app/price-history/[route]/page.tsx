"use client";
import React, { useEffect, useState } from "react";
import { priceHistoryApi } from "@/lib/api";
import { PriceHistoryChart } from "@/components/PriceHistoryChart";

export default function PriceHistoryPage({ params }: { params: { route: string } }) {
  const [origin, destination] = params.route.split("-");
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    priceHistoryApi.get(origin, destination, 30).then(setData);
  }, [origin, destination]);
  if (!data) return null;
  return <PriceHistoryChart data={data.points} />;
}
