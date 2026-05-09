import asyncio

from llm import adapters
from llm.adapters import BaseLlmAdapter
from llm.adapters.faike import FaikeAdapter
from models import Findings


def test_model_options_include_pydantic_thinking_level_when_supported(monkeypatch):
    monkeypatch.setattr(adapters, "pydantic_ai_supports_thinking", lambda: True)
    adapter = BaseLlmAdapter(thinking="high")

    assert adapter.get_model_options()["thinking"] == "high"


def test_model_options_map_disabled_thinking_to_false(monkeypatch):
    monkeypatch.setattr(adapters, "pydantic_ai_supports_thinking", lambda: True)
    adapter = BaseLlmAdapter(thinking="disabled")

    assert adapter.get_model_options()["thinking"] is False


def test_model_options_omit_thinking_when_pydantic_ai_does_not_support_it(monkeypatch):
    monkeypatch.setattr(adapters, "pydantic_ai_supports_thinking", lambda: False)
    adapter = BaseLlmAdapter(thinking="xhigh")

    assert "thinking" not in adapter.get_model_options()


def test_faike_adapter_accepts_thinking_without_using_it():
    adapter = FaikeAdapter("", "Fake LLM", thinking="low")

    result = asyncio.run(
        adapter.prompt_structured(
            "system",
            "File: app.py\n@@ -0,0 +1 @@\n+[]\n",
            Findings,
        )
    )

    assert adapter.thinking == "low"
    assert result.findings[0].file == "app.py"
