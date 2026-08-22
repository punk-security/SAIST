from abc import ABC, abstractmethod
from ..roles import Message
from ..tools import Tool
from typing import Any, Generic, TypeVar

class APIAdapter(ABC):
    """
    An adapter between the abstracted representation of AI interactions and the provider's
    """
    client: Any
    model: str
    _tools_set: set[str]
    tools: Any
    tools_map: dict[str, Tool]
    options: dict | None

    @abstractmethod
    def tools_to_provider(self, tools: list[Tool]) -> Any:
        ...

    def __init__(self, client: Any, model: str, tools: list[Tool] = [], options: dict | None = None):
        self.client = client
        self.model = model
        self._tools_set = set()
        self.tools_map = {tool.name: tool for tool in tools}
        self.tools = self.tools_to_provider(tools)
        self.options = options

    def add_tools(self, tools: list[Tool]):
        new_tools = []
        for tool in tools:
            if tool.name in self._tools_set:
                continue
            self._tools_set.add(tool.name)
            new_tools.append(tool)

        self.tools.extend(self.tools_to_provider(new_tools))

    @abstractmethod
    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        ...
