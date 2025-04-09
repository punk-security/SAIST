from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

class OllamaAdapter(BaseLlmAdapter):
    def __init__(self, base_url: str, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "llama3.2"
        if api_key != None:
            provider = OpenAIProvider( 
                base_url = base_url,
                api_key=api_key
                )
        else:
            provider = OpenAIProvider( 
                base_url = base_url,
                )
        self.model = OpenAIModel(
            model,
            provider = provider
        )
