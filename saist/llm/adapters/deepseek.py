from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

class DeepseekAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "deepseek-chat"
        self.model = OpenAIModel(
            model,
            provider = DeepSeekProvider( api_key=api_key ),
        )
        self.model_name = self.model.model_name
        self.model_vendor = 'DeepSeek'

