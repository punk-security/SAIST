from typing import Optional
import os
from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider

class AzureOpenAiAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "gpt-4o"
        if api_key:
            raise ValueError("Do not provide API keys for AZURE - use ENV variables")
        self.model = OpenAIModel(
            model,
            provider = AzureProvider( 
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_version = os.environ.get("AZURE_OPENAI_API_VERSION"), 
                )
        )
