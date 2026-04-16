from typing import Optional
import os
from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider

class AzureAdapter(BaseLlmAdapter):
    def __init__(self, endpoint: str, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "gpt-5.4-nano"
        self.model = OpenAIModel(
            model,
            provider = AzureProvider( 
                api_key=api_key,
                azure_endpoint = endpoint,
                )
            )
        self.model_name = model
        self.model_vendor = 'Azure'
