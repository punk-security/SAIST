from abc import ABC, abstractmethod

from events import SAISTEvent, SAISTEventResponse

from llm.tools import Tool

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from saistrun import SAISTRun

class SAISTStrategy(ABC):
    """
    Base class for all implement strategies within SAIST
    """

    run: "SAISTRun"

    def __init__(self, run: "SAISTRun"):
        self.run = run

    @property
    @abstractmethod
    def tools(self) -> list[Tool]: ...

    @property
    @abstractmethod
    def system_prompt_part(self) -> str: ...

    @abstractmethod
    async def handle_event(self, event: SAISTEvent) -> SAISTEventResponse | None: ...
