from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

class OpenAiAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "gpt-4o"
        self.model = OpenAIModel(
            model,
            provider = OpenAIProvider( api_key=api_key )
        )
