from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.azure import AzureProvider


class AzureFoundryAdapter(BaseLlmAdapter):
    def __init__(
        self,
        model: str = None,
        api_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        thinking: str = "medium",
    ):
        super().__init__(thinking=thinking)
        if model is None:
            model = "gpt-5-mini"
        self.model = OpenAIResponsesModel(
            model,
            provider=AzureProvider(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=api_version,
            ),
        )
        self.model_name = self.model.model_name
        self.model_vendor = "Azure AI Foundry"
