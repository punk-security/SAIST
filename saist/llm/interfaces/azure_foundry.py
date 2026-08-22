from typing import override

from . import ModelInterface
from openai import AsyncOpenAI, AsyncAzureOpenAI

from ..adapters.openai_responses import OpenAIResponsesAdapter
from ..tools import Tool

class AzureFoundryInterface(ModelInterface):
    def __init__(self, api_key: str, tools: list[Tool], base_url: str | None = None, api_version: str | None = None, model: str | None = None):
        if base_url is None:
            raise ValueError("Must provide a API endpoint for Azure Foundry")
        if api_version is None:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        else:
            client=AsyncAzureOpenAI(
                api_key=api_key,
                base_url=base_url,
                api_version=api_version
            )

        self.adapter = OpenAIResponsesAdapter(
            client=client,
            model=model or "gpt-4o",
            tools=tools
        )
