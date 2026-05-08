"use client";
import React from "react";

interface Point { at: string; price: number }

export function PriceHistoryChart({ data }: { data: Point[] }) {
  return (
    <div data-testid="price-chart" style={{ width: "100%", height: 300, position: "relative" }}>
      {data.map((p, i) => (
        <span key={i} style={{ position: "absolute", left: `${i * 60}px`, bottom: `${p.price / 10}px`, fontSize: 10 }}>
          {p.price}
        </span>
      ))}
    </div>
  );
}
