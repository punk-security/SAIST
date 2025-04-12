from typing import Optional, Callable, Type, List, Dict, Any
import logging

from llm.adapters import BaseLlmAdapter

from pydantic import BaseModel

import ollama

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseLlmAdapter):
    def __init__(self, base_url: str, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "llama3:latest"
        self.model = model
        self.client = ollama.AsyncClient(host=base_url)

    def get_model_options(self) -> Dict[str, Any]:
        return {'temperature': 0.0}

    async def prompt_structured(self, prompt: str, response_format: Type[BaseModel], tool_fns: Optional[List[Callable]] = None) -> BaseModel:
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options=self.get_model_options(),
            format = response_format.model_json_schema()
        )

        logger.getChild(self.__class__.__name__).debug("prompt_structured initial response", extra={'response_data': response, 'prompt': prompt})

        if response.message and response.message.content:
            parsed = response_format.model_validate_json(response.message.content)
            return parsed
        else:
            raise ValueError("No structured response received from model")

    async def prompt(self, prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options=self.get_model_options(),
        )

        logger.getChild(self.__class__.__name__).info("prompt initial response", extra={'response_data': response, 'prompt': prompt})

        return response.message.content if response.message else None

    def generate_agent(self, system_prompt: str = None, tool_fns: Optional[List[Callable]] = None):
        #TODO: OLLAMA AGENT FOR SHELL
        return None

