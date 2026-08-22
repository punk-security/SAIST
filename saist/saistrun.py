import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Type, TypeVar, get_args, cast
from functools import partial

from models import Finding

from llm.tools import Tool

from strategy import SAISTStrategy
from file import FileProvider, SearchMatch

from llm.roles import Message, MessageRole
from llm.interfaces import ModelInterface

import events

import logging

logger = logging.Logger(__name__)

A = TypeVar("A")

async def merge(*generators: AsyncGenerator[A, None]) -> AsyncGenerator[A, None]:
    queue = asyncio.Queue(maxsize=1)
    done = object()

    async def consume(generator):
        async for item in generator:
            await queue.put(item)
        await queue.put(done)

    tasks = [asyncio.create_task(consume(g)) for g in generators]

    remaining = len(tasks)
    while remaining:
        item = await queue.get()

        if item is done:
            remaining -= 1
        else:
            yield item

    await asyncio.gather(*tasks)

class SAISTRun():
    _model_interface: ModelInterface
    _file_provider: FileProvider
    _strategies: list[SAISTStrategy]

    _terminate_requested: bool
    _restart_requested: bool

    _tool_map: dict[str, tuple[Tool, SAISTStrategy | None]]

    messages: list[Message]

    run_event_queue: list[events.SAISTRunEvent]

    _files_lock = asyncio.Lock()
    files = []

    outputs = {}

    @classmethod
    def get_output(cls, name: str, default: Any = None) -> Any:
        if name not in cls.outputs:
            cls.outputs[name] = default

        return cls.outputs[name]

    @classmethod
    def set_output(cls, name: str, value: Any):
        cls.outputs[name] = value

    @property
    def system_prompt_part(self) -> str:
        return """
# Key Information
You are being driven through a non-interactive agentic harness. Messages you send will only be visible to yourself.

The harness operates by allowing you to perform actions within a "run" using tools. These tools are the only way for you to interact or cause effects.

A "run" is composed of a sequence if independent agentic conversations. Starting a new conversation is referred to as "restarting" a run, and is used to progress when there is nothing further to action on the current item of work.

If you believe that neither the current item of work nor any possible future items of work will be actionable, you should "terminate" the run. This ends all further agentic interaction, and causes the harness to collect any persistent data created during a run. You should avoid terminating the run unless all other potential avenues have been explored. You should ALWAYS prefer restarting a run over terminating it.

Some strategies may prevent the restarting or terminating of the run unless certain conditions are met. When this happens, a reason will be provided that explains how to continue.
"""

    async def broadcast_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        decision: events.SAISTEventResponse | None = None

        if isinstance(event, get_args(events.SAISTRunEvent)):
            self.run_event_queue.append(cast(events.SAISTRunEvent, event))

        logger.debug(f"Broadcasted event: {event}")

        for strategy in self._strategies:
            response = await strategy.handle_event(event)
            match response:
                case events.Skip():
                    continue
                case events.PreventTerminal():
                    return response
                case _:
                    decision = response

        return decision

    async def terminate_run(self, force=False):
        if force:
            self._terminate_requested = True
            return

        match await self.broadcast_event(events.BeforeTerminateRun()):
            case events.Prevent(reason=reason):
                return {
                    "status": "prevented",
                    "reason": reason or "Not specified"
                }
            case events.PreventTerminal(reason=reason, callback=callback):
                if callback is not None:
                    callback(self)
                return {
                    "status": "prevented",
                    "reason": reason or "Not specified"
                }

        self._terminate_requested = True

    async def restart_run(self):
        match await self.broadcast_event(events.BeforeRestartRun()):
            case events.Prevent(reason=reason):
                return
            case events.PreventTerminal(reason=reason, callback=callback):
                if callback is not None:
                    callback(self)
                return

        self._restart_requested = True

    async def read_file(self, path: Path) -> str | None:
        contents = await self._file_provider.read_file_contents(path)
        if contents is not None:
            await self.broadcast_event(events.FileRead(path=path))
        return contents

    async def list_files(self) -> list[Path]:
        return await self._file_provider.list_files()

    async def search(self, pattern: str) -> list[SearchMatch]:
        return await self._file_provider.search(pattern)

    async def regex_search(self, pattern: str) -> list[SearchMatch]:
        return await self._file_provider.regex_search(pattern)


    @staticmethod
    async def _request_run_terminate(_run: "SAISTRun", reason: str):
        """
        Request that the current run be terminated. 
        
        This should only be used when all possible current or future units of work are believed to be inactionable. Restarting the run is ALWAYS preferred to terminating it.
        """
        return await _run.terminate_run()

    @property
    def _tools(self) -> list[Tool]:
        return [
            Tool(self._request_run_terminate),
        ]

    def __init__(self):
        raise TypeError("SAISTRun must be created with 'await SAISTRun.create(...)'")

    @classmethod
    async def create(cls, model_interface: ModelInterface, file_provider: FileProvider, strategies: list[Callable[["SAISTRun"], SAISTStrategy]]) -> "SAISTRun":
        self = cls.__new__(cls)
    
        self._model_interface = model_interface
        self._file_provider = file_provider
        self._strategies = [strategy(self) for strategy in strategies]
        self._tool_map = {}
        self.run_event_queue = []

        for strategy in self._strategies:
            for tool in strategy.tools:
                if tool.name in self._tool_map:
                    raise ValueError(f"Duplicate tool found: {tool.name}")
                self._tool_map[tool.name] = (tool, strategy)

        for tool in self._tools:
            if tool.name in self._tool_map:
                raise ValueError(f"Duplicate tool found: {tool.name}")

            self._tool_map[tool.name] = (tool, None)

        self._terminate_requested = False
        self._restart_requested = False

        self.messages = []

        async with cls._files_lock:
            if len(cls.files) == 0:
                cls.files = await file_provider.list_files()

        await self.broadcast_event(events.RunInitialized())

        return self

    async def run(self) -> AsyncGenerator[events.SAISTRunEvent, None]:
        while not self._terminate_requested:
            # Compose the system message
            system_prompt = self.system_prompt_part or ""

            system_prompt += "You are provided with the following strategies in this run:\n- "
            system_prompt += "\n- ".join(strategy.__class__.__name__ for strategy in self._strategies)

            for strategy in self._strategies: 
                if strategy.system_prompt_part is not None:
                    system_prompt += f"\n# {strategy.__class__.__name__} Instructions:\n\n"
                    
                    system_prompt += strategy.system_prompt_part + "\n"

                if len(strategy.tools) != 0:
                    system_prompt += f"\n# {strategy.__class__.__name__} Tools:\n\n"

                    for tool in strategy.tools:
                        system_prompt += f"\n- {tool.name}"
                    system_prompt += "\n\n"

            if self._file_provider.system_prompt_part is not None:
                system_prompt += self._file_provider.system_prompt_part + "\n"

            self.messages = [
                MessageRole.System(system_prompt)
            ]

            await self.broadcast_event(events.BeforeRunStart())

            async for message in self._model_interface.iter_run(self.messages, list(map(lambda x: x[0], self._tool_map.values()))):
                logger.debug("="*40)
                logger.debug(self.messages)
                logger.debug("="*40)
                logger.debug("\n\n\n")
                for event in self.run_event_queue:
                    yield event
                self.run_event_queue.clear()

                match message:
                    case MessageRole.ToolCall(tool_call_id=tool_call_id, tool_name=name, arguments=arguments):
                        tool: Tool | None = None
                        strategy: SAISTStrategy | None = None
                        interface_tool = False
                        tool_strategy = self._tool_map.get(name)
                        if tool_strategy is None:
                            tool = self._model_interface.adapter.tools_map.get(name)
                            interface_tool = True
                        else:
                            (tool, strategy) = tool_strategy
                        if tool is None:
                            raise ValueError(f"Model tried to call non-existing tool: {name}")

                        tool_call = partial(tool.call, arguments)
                        if not interface_tool:
                            tool_call = partial(tool_call, _run=self)
                            if strategy is not None:
                                tool_call = partial(tool_call, _strategy=strategy)

                        call = await tool_call()
                        if not call['success']:
                            # TODO: Handle this better (retry logic etc)
                            logger.error(call['error'])
                            raise call['exception']

                        self.messages.append(MessageRole.ToolResponse(
                            tool_call_id=tool_call_id,
                            output=tool.serialize(call['result'])
                        ))

                        if self._terminate_requested or self._restart_requested:
                            for event in self.run_event_queue:
                                yield event
                            self.run_event_queue.clear()

                            if self._restart_requested:
                                self._restart_requested = False

                            break

    async def run_until_finished(self):
        async for _ in self.run():
            pass

class SAISTRunGroup():
    """
    Helper class for dealing with multiple concurrent SAISTRun
    """

    runs: list[SAISTRun]

    def __init__(self):
        raise TypeError("SAISTRun must be created with 'await SAISTRun.create(...)'")

    def get_output(self, name: str, default: Any) -> Any:
        return self.runs[0].get_output(name, default)

    @classmethod
    async def create(cls, model_interface: ModelInterface, file_provider: FileProvider, strategies: list[Callable[["SAISTRun"], SAISTStrategy]], concurrency: int = 1) -> "SAISTRunGroup":
        self = cls.__new__(cls)

        self.runs = [await SAISTRun.create(model_interface, file_provider, strategies) for _ in range(concurrency)]

        return self

    async def run(self) -> AsyncGenerator[events.SAISTRunEvent, None]:
        async for event in merge(*[run.run() for run in self.runs]):
            yield event

        for run in self.runs:
            await run.broadcast_event(events.BeforeFinalizeRun())
