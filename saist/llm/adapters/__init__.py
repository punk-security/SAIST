import logging
from typing import Callable, List, Optional, Type

from pydantic_ai import Agent, Tool

from typing import Type

from pydantic import BaseModel

logger = logging.getLogger("saist.llm.adapters")

class BaseLlmAdapter:
    model_options = None

    def get_model_options(self):
        return {'temperature': 0.0} | self.model_options if self.model_options is not None else {}

    async def prompt_structured(self, system_prompt: str, user_prompt: str, response_format: Type[BaseModel], tool_fns: Optional[List[Callable]] = None) -> BaseModel:
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        agent = Agent(self.model, result_type = response_format, tools=tools, system_prompt=system_prompt)
        response = await agent.run( user_prompt=user_prompt, model_settings=self.get_model_options())
        logger.getChild(self.__class__.__name__).debug("prompt_structured response", extra={'response_data': response.data, 'prompt': user_prompt})
        return response.data

    async def prompt(self, system_prompt: str, user_prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        agent = Agent(self.model, system_prompt=system_prompt, tools=tools)
        response = await agent.run(user_prompt=user_prompt, model_settings=self.get_model_options())
        logger.getChild(self.__class__.__name__).debug("prompt response", extra={'response_data': response.data, 'prompt': user_prompt})
        return response.data
    
    def generate_agent(self, system_prompt: str = None, tool_fns: Optional[List[Callable]] = None):
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        return Agent(self.model, system_prompt=system_prompt, tools=tools)
