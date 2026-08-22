from typing import override

from . import ModelInterface
from anthropic import AsyncAnthropic

from ..adapters.anthropic_messages import AnthropicMessagesAdapter
from ..tools import Tool

class AnthropicInterface(ModelInterface):
    def __init__(self, api_key: str, tools: list[Tool], model: str | None = None, api_override: str | None = None):
        model = model or "claude-3-7-sonnet-latest"
        self._model_name = model

        self.adapter = AnthropicMessagesAdapter(
            client=AsyncAnthropic(
                api_key=api_key,
                base_url=api_override
            ),
            model=model or "claude-3-7-sonnet-latest",
            tools=tools
        )
