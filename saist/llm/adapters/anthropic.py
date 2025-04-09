from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

class AnthropicAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "claude-3-7-sonnet-latest"
        self.model = AnthropicModel(
            model,
            provider = AnthropicProvider( api_key=api_key )
        )

        self.model_options = {'max_tokens': 8192}
