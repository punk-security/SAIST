import logging
from typing import Callable, List, Optional, Type

from pydantic_ai import Agent, Tool
from pydantic_ai.settings import ModelSettings

from pydantic import BaseModel

logger = logging.getLogger("saist.llm.adapters")

THINKING_CHOICES = ("minimal", "low", "medium", "high", "xhigh", "disabled")
DISABLED_THINKING = "disabled"


def pydantic_ai_supports_thinking() -> bool:
    return "thinking" in getattr(ModelSettings, "__annotations__", {})


class BaseLlmAdapter:
    model_options = None
    model_vendor = ''
    model_name = ''

    def __init__(self, thinking: str = "medium"):
        self.thinking = thinking

    def get_model_options(self):
        options = {"temperature": 0.0}
        if self.model_options is not None:
            options.update(self.model_options)

        if pydantic_ai_supports_thinking():
            options["thinking"] = False if self.thinking == DISABLED_THINKING else self.thinking
        elif self.thinking != DISABLED_THINKING:
            logger.getChild(self.__class__.__name__).debug(
                "Installed pydantic-ai version does not support model_settings.thinking; ignoring setting."
            )

        return options

    async def _run_agent(self, agent: Agent, user_prompt: str):
        model_settings = self.get_model_options()
        try:
            return await agent.run(user_prompt=user_prompt, model_settings=model_settings)
        except Exception as e:
            if "thinking" not in str(e).lower() or "thinking" not in model_settings:
                raise

            fallback_settings = {key: value for key, value in model_settings.items() if key != "thinking"}
            logger.getChild(self.__class__.__name__).warning(
                "Model or provider rejected model_settings.thinking; retrying without it."
            )
            return await agent.run(user_prompt=user_prompt, model_settings=fallback_settings)

    async def prompt_structured(self, system_prompt: str, user_prompt: str, response_format: Type[BaseModel], tool_fns: Optional[List[Callable]] = None) -> BaseModel:
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        agent = Agent(self.model, output_type = response_format, tools=tools, system_prompt=system_prompt)
        response = await self._run_agent(agent, user_prompt)
        logger.getChild(self.__class__.__name__).debug("prompt_structured response", extra={'response_data': response.output, 'prompt': user_prompt})
        return response.output

    async def prompt(self, system_prompt: str, user_prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        agent = Agent(self.model, system_prompt=system_prompt, tools=tools)
        response = await self._run_agent(agent, user_prompt)
        logger.getChild(self.__class__.__name__).debug("prompt response", extra={'response_data': response.output, 'prompt': user_prompt})
        return response.output
    
    def generate_agent(self, system_prompt: str = None, tool_fns: Optional[List[Callable]] = None):
        tools = [Tool(fn) for fn in tool_fns] if tool_fns else []
        return Agent(self.model, system_prompt=system_prompt, tools=tools, model_settings=self.get_model_options())
