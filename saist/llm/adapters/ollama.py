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


    async def initialize(self):
        if not await self._check_ollama_status():
            raise ConnectionError("Ollama server unreachable or misconfigured.")

    async def _check_ollama_status(self):
        try:
            version_info = await self.client.show(self.model)
            return bool(version_info)
        except Exception as e:
            logger.error("Ollama check failed: %s", e)
            return False

    def get_model_options(self) -> Dict[str, Any]:
        return {'temperature': 0.0}

    async def prompt_structured(self, system_prompt: str, user_prompt: str, response_format: Type[BaseModel], tool_fns: Optional[List[Callable]] = None) -> BaseModel:
        messages = [{"role": "system", "content": system_prompt},{"role": "user", "content": user_prompt}]

        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options=self.get_model_options(),
            format = response_format.model_json_schema()
        )

        logger.getChild(self.__class__.__name__).debug("prompt_structured initial response", extra={'response_data': response, 'prompt': user_prompt})

        if response.message and response.message.content:
            parsed = response_format.model_validate_json(response.message.content)
            return parsed
        else:
            raise ValueError("No structured response received from model")

    async def prompt(self, system_prompt: str, user_prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        messages = [{"role": "system", "content": system_prompt},{"role": "user", "content": user_prompt}]

        response = await self.client.chat(
            model=self.model,
            messages=messages,
            options=self.get_model_options(),
        )

        logger.getChild(self.__class__.__name__).info("prompt initial response", extra={'response_data': response, 'prompt': user_prompt})

        return response.message.content if response.message else None

    def generate_agent(self, system_prompt: str = None, tool_fns: Optional[List[Callable]] = None):
        #TODO: OLLAMA AGENT FOR SHELL
        return None

