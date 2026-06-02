"""验证 LLM prompt 注入了当前日期(北京时区),让模型能推算相对日期。"""
from __future__ import annotations

import re

import pytest

from backend.application.graph._now import today_cn


def test_today_cn_format():
    s = today_cn()
    assert re.match(r"\d{4}年\d{2}月\d{2}日 周[一二三四五六日]", s), s


def test_parse_intent_prompt_carries_today():
    """parse_intent 的模板能接受 today 变量并把它渲染进 system prompt。"""
    from backend.application.graph.nodes.parse_intent import _prompt

    msgs = _prompt.format_messages(
        message="北京到三亚明天出发", history=[], today=today_cn()
    )
    system = msgs[0].content
    assert today_cn() in system
    assert "明天" in system  # 相对日期推算规则在 prompt 里


@pytest.mark.asyncio
async def test_react_agent_injects_today(monkeypatch):
    """react_agent(线上主路径)把今天日期 prepend 进 system message。"""
    import backend.application.graph.nodes.react_agent as ra

    captured: dict = {}

    class _FakeChat:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages, **kw):
            captured["messages"] = messages

            class _AI:
                tool_calls: list = []
                content = "ok"

            return _AI()

    monkeypatch.setattr(ra, "build_chat_model", lambda role: _FakeChat())
    monkeypatch.setattr(ra, "load_available_tools", lambda: [])
    monkeypatch.setattr(ra, "load_prompt", lambda name: "SYSTEM {intent_definitions}")

    await ra.react_agent({"messages": [{"role": "user", "content": "明天北京到三亚"}]})

    system = captured["messages"][0]["content"]
    assert "今天是" in system
    assert today_cn() in system
    assert "depart_date" in system  # 提示 LLM 把日期参数算成具体日期
