import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import MemoryPage from "@/app/memory/page";
import { MemoryPage as SharedMemoryPage } from "@/components/memory-page";

const { getMemory } = vi.hoisted(() => ({
  getMemory: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { getMemory },
}));

const populatedMemory = {
  memories: [
    {
      field: "budget",
      value: 1200,
      label: "心理价位",
      value_display: "¥1,200",
      source: "auto",
    },
    {
      field: "frequent_cities",
      value: ["三亚", "成都"],
      label: "常去城市",
      value_display: "三亚、成都",
      source: "manual",
    },
    {
      field: "preferred_airlines",
      value: ["中国国航"],
      label: "偏好航司",
      value_display: "中国国航",
      source: "auto",
    },
    {
      field: "constraints",
      value: ["direct_only", "avoid_redeye"],
      label: "出行习惯",
      value_display: "只看直飞、避开红眼航班",
      source: "manual",
    },
  ],
  query_history: [
    {
      id: "query-1",
      query: {
        text: "7月25日北京到三亚的直飞机票",
        intent: {
          origin: { city_name: "北京" },
          destination: { city_name: "三亚" },
        },
      },
      created_at: "2026-07-18T14:30:00+08:00",
    },
    {
      id: "query-2",
      query: {
        text: "上海飞成都下周五",
        intent: { origin: "上海", destination: "成都" },
      },
      created_at: "2026-07-17T09:05:00+08:00",
    },
  ],
};

function openJournal() {
  fireEvent.click(screen.getByRole("button", { name: /打开记忆/ }));
}

function selectChapter(name: string) {
  fireEvent.click(screen.getByRole("button", { name }));
}

beforeEach(() => {
  getMemory.mockReset();
});

test("the memory route reuses the shared journal component", () => {
  expect(MemoryPage).toBe(SharedMemoryPage);
});

test("derives all four journal chapters from real memory and query history", async () => {
  getMemory.mockResolvedValue(populatedMemory);

  render(<MemoryPage />);
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1));
  openJournal();

  expect(await screen.findByText("心理价位：¥1,200")).toBeInTheDocument();
  expect(screen.getByText("常去城市：三亚、成都")).toBeInTheDocument();
  expect(screen.getByText("偏好航司：中国国航")).toBeInTheDocument();

  selectChapter("习惯");
  expect(screen.getByText("出行习惯：只看直飞、避开红眼航班")).toBeInTheDocument();
  expect(screen.getByText("系统自动学习：心理价位 ¥1,200")).toBeInTheDocument();

  selectChapter("想法");
  expect(screen.getByText("北京 → 三亚")).toBeInTheDocument();
  expect(screen.getByText("上海 → 成都")).toBeInTheDocument();
  expect(screen.getByText("7月25日北京到三亚的直飞机票")).toBeInTheDocument();

  selectChapter("历史");
  expect(screen.getByText("7月25日北京到三亚的直飞机票")).toBeInTheDocument();
  expect(screen.getByText(/2026.*07.*18.*14:30/)).toBeInTheDocument();
});

test("shows neutral empty states instead of invented preferences or stories", async () => {
  getMemory.mockResolvedValue({ memories: [], query_history: [] });

  render(<MemoryPage />);
  openJournal();

  expect(await screen.findByText("还没有记录出行偏好")).toBeInTheDocument();

  selectChapter("习惯");
  expect(screen.getByText("还没有形成可展示的出行习惯")).toBeInTheDocument();

  selectChapter("想法");
  expect(screen.getByText("最近查询里还没有可整理的路线")).toBeInTheDocument();

  selectChapter("历史");
  expect(screen.getByText("还没有搜索记录")).toBeInTheDocument();

  expect(screen.queryByText(/海岛与松弛感/)).not.toBeInTheDocument();
  expect(screen.queryByText(/五一、端午、暑假/)).not.toBeInTheDocument();
  expect(screen.queryByText(/上海 → 三亚是近期最深/)).not.toBeInTheDocument();
});

test("keeps the journal neutral when memory loading fails", async () => {
  getMemory.mockRejectedValue(new Error("offline"));

  render(<MemoryPage />);
  openJournal();

  expect(await screen.findByText("暂时无法读取记忆数据")).toBeInTheDocument();
  expect(screen.queryByText(/更容易被海岛/)).not.toBeInTheDocument();
});
