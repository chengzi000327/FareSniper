from __future__ import annotations

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent


class DecisionMakerSkill(FareSniperAgent):
    """
    综合分析结果，生成购买建议。
    输入：context dict（含 preference_match 结果）
    输出：{"action": "buy_now|watch|skip", "text": str, "confidence": str, "signals": [...]}
    """

    async def reply(self, msg: Msg) -> Msg:
        context = msg.metadata if isinstance(msg.metadata, dict) else {}
        results = context.get("results", {})
        analysis = results.get("preference_match", {})

        decision = self._decide(analysis)

        import json
        return Msg(
            name="decision_maker",
            content=json.dumps(decision, ensure_ascii=False),
            role="assistant",
            metadata=decision,
        )

    def _decide(self, analysis: dict) -> dict:
        within_budget = analysis.get("within_budget", False)
        match_score = analysis.get("match_score", 0.0)
        lower_than_avg = analysis.get("lower_than_avg")
        signals: list[str] = []

        if within_budget and isinstance(lower_than_avg, float) and lower_than_avg >= 0.15:
            action, confidence = "buy_now", "high"
            text = "建议现在购买，当前价格低于均价且在预算内。"
            signals.append("低于均价15%+")
        elif within_budget:
            action, confidence = "buy_now", "medium"
            text = "可以考虑购买，价格在预算内。"
        elif match_score >= 0.7:
            action, confidence = "watch", "medium"
            text = "路线符合偏好，建议继续观察价格变化。"
        else:
            action, confidence = "watch", "low"
            text = "暂无明显购买信号，建议继续观察。"

        return {"action": action, "text": text, "confidence": confidence, "signals": signals}
