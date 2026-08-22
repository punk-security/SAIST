from . import ModelInterface
from openai import AsyncOpenAI

from ..adapters.openai_responses import OpenAIResponsesAdapter
from ..tools import Tool

class OpenAIInterface(ModelInterface):
    def __init__(self, api_key: str, tools: list[Tool], model: str | None = None, api_override: str | None = None):
        self.adapter = OpenAIResponsesAdapter(
            client=AsyncOpenAI(
                api_key=api_key,
                base_url=api_override
            ),
            model=model or "gpt-4o",
            tools=tools
        )
