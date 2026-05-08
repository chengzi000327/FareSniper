import json
import pathlib
import asyncio
from dataclasses import dataclass, field
from langchain_core.messages import HumanMessage
from backend.application.graph.factory import get_graph

DATASET = pathlib.Path(__file__).parents[1] / "datasets" / "e2e_50.jsonl"


@dataclass
class BClassReport:
    scores: dict = field(default_factory=dict)
    cases: int = 0


async def run_b_class(sample: int = 30) -> BClassReport:
    cases = [json.loads(l) for l in DATASET.read_text().splitlines() if l.strip()][:sample]
    graph = get_graph()
    intent_hits = clarify_hits = signal_hits = advice_hits = format_hits = 0
    for c in cases:
        msg = c["input_sequence"][0]["user"]
        try:
            out = await graph.ainvoke({
                "request_user_id": "eval",
                "request_session_id": None,
                "messages": [HumanMessage(content=msg)],
                "clarify_count": 0,
                "fallback_triggered": False,
                "errors": [],
            })
            rsp = out["response"]
            format_hits += 1
            if rsp.deals:
                intent_hits += 1
            if rsp.recommendation:
                advice_hits += 1
                rec = rsp.recommendation
                text = rec.get("text", "") if isinstance(rec, dict) else getattr(rec, "text", "")
                if len(text) <= 20:
                    clarify_hits += 1
                signals = rec.get("signals") if isinstance(rec, dict) else getattr(rec, "signals", None)
                if signals:
                    signal_hits += 1
        except Exception:
            pass
    n = max(len(cases), 1)
    return BClassReport(
        scores={
            "intent_acc": intent_hits / n,
            "clarify_acc": clarify_hits / n,
            "signal_acc": signal_hits / n,
            "advice_relevance": advice_hits / n,
            "format_compliance": format_hits / n,
        },
        cases=n,
    )


if __name__ == "__main__":
    print(asyncio.run(run_b_class()))
