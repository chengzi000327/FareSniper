"""ValueJudge：使用 MODEL_JUDGE 生成值得买信号和一句话建议（PRD 6.3）。"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.infrastructure.llm.prompt_loader import load_prompt

_FALLBACK_SYSTEM_PROMPT = """你是机票价值判断助手，帮用户判断当前机票是否值得买。

## 任务
对每张票，输出触发的值得买信号列表和一句话购买建议。

## 判断逻辑（先推理再输出结论）
对每张票依次判断：
1. lowest_price 与 history_avg_90d 的差值百分比，差值 > 15% 触发"历史低价"信号
2. 是否在用户心理价位内（由 preference_matched 字段传入）
3. 出行日期是否为节假日（由 is_holiday 字段传入）
4. 综合以上，生成不超过20字的一句话建议：先告诉用户买/不买/观望，再给最关键的一条理由

## 输出格式
JSON数组：
[{"flight_no":"HU7833","signals":["历史低价","符合心理价位"],"advice":"建议现在买，比均价低43%且在预算内"}]

## 限制
- advice 不超过20字
- 历史数据不足时，signals为[]，advice输出"数据有限，仅供参考"
- 不捏造数据，只用传入数据做判断
- is_holiday=true 时可在 advice 文案中提及节假日，但不得将"节假日稀缺"写入 signals 数组
- 只输出JSON，不加解释"""


def _system_prompt() -> str:
    text = load_prompt("value_judge")
    return text if text and "[value_judge]" not in text else _FALLBACK_SYSTEM_PROMPT


class ValueJudge:
    def __init__(self, llm_client=None, model: str = "qwen-plus") -> None:
        self.llm_client = llm_client
        self.model = model

    async def judge(
        self,
        flights: list[dict[str, Any]],
        pref_results: list[dict[str, Any]],
        is_holiday_map: dict[str, bool],
    ) -> list[dict[str, Any]]:
        """返回每个航班的 signals + advice。"""
        if not flights:
            return []

        use_llm = (
            self.llm_client
            and getattr(self.llm_client, "_provider", "mock") != "mock"
            and getattr(self.llm_client, "_api_key", "")
        )

        if use_llm:
            result = await self._judge_via_llm(flights, pref_results, is_holiday_map)
            if result:
                return result

        return self._judge_heuristic(flights, pref_results, is_holiday_map)

    async def _judge_via_llm(
        self,
        flights: list[dict[str, Any]],
        pref_results: list[dict[str, Any]],
        is_holiday_map: dict[str, bool],
    ) -> list[dict[str, Any]] | None:
        pref_map = {p.get("flight_no", ""): p for p in pref_results}

        payload = []
        for f in flights:
            key = f.get("flight_no", f.get("id", ""))
            pref = pref_map.get(key, {})
            payload.append({
                "flight_no": key,
                "lowest_price": f.get("lowest_price", f.get("price", 0)),
                "history_avg_90d": f.get("history_avg_90d"),
                "is_holiday": is_holiday_map.get(f.get("depart_date", ""), False),
                "preference_matched": pref.get("matched", False),
                "preference_reasons": pref.get("reasons", []),
            })

        user_msg = json.dumps(payload, ensure_ascii=False)
        try:
            raw = await self.llm_client.chat_completion([
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_msg},
            ])
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return None

    def _judge_heuristic(
        self,
        flights: list[dict[str, Any]],
        pref_results: list[dict[str, Any]],
        is_holiday_map: dict[str, bool],
    ) -> list[dict[str, Any]]:
        pref_map = {p.get("flight_no", ""): p for p in pref_results}
        results = []
        for f in flights:
            key = f.get("flight_no", f.get("id", ""))
            pref = pref_map.get(key, {})
            lowest = f.get("lowest_price", f.get("price", 0))
            avg_90d = f.get("history_avg_90d")
            holiday = is_holiday_map.get(f.get("depart_date", ""), False)

            signals: list[str] = []
            advice = ""

            if avg_90d and avg_90d > 0:
                ratio = (avg_90d - lowest) / avg_90d
                pct = int(ratio * 100)
                if ratio > 0.15:
                    signals.append("历史低价")
            else:
                ratio = 0.0
                pct = 0

            if pref.get("matched"):
                for r in pref.get("reasons", []):
                    if "心理价位" in r:
                        signals.append("符合心理价位")
                        break
                for r in pref.get("reasons", []):
                    if "出行习惯" in r:
                        signals.append("符合出行习惯")
                        break

            within_budget = any("心理价位" in r for r in pref.get("reasons", []))

            if not avg_90d:
                advice = "数据有限，仅供参考"
            elif "历史低价" in signals and within_budget:
                advice = f"建议现在买，比均价低{pct}%且在预算内"
            elif "历史低价" in signals and not within_budget:
                advice = f"历史低位，但当前价格偏高"
            elif within_budget:
                advice = "在预算内，价格正常可继续关注"
            elif holiday and ratio > 0.05:
                advice = "节假日难得低价，可考虑入手"
            else:
                advice = "价格正常，可继续关注"

            # advice 截断到 20 字
            if len(advice) > 20:
                advice = advice[:20]

            results.append({"flight_no": key, "signals": signals, "advice": advice})

        return results
