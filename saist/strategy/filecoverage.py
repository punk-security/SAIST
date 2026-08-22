import asyncio
from pathlib import Path
from typing import override
import typing

from llm.tools import Tool

import events
from saistrun import SAISTRun

from . import SAISTStrategy

class FileCoverageStrategy(SAISTStrategy):
    """
    A strategy that blocks run termnination until all files have been reviewed, and provides a tool to list outstanding files.
    """

    _files_lock = asyncio.Lock()
    _files: set[Path] = None # type: ignore

    @staticmethod
    async def list_outstanding_files(_run: SAISTRun, _strategy: "FileCoverageStrategy"):
        return list(_strategy._files or [])

    @property
    @override
    def tools(self) -> list[Tool]:
        return [
            Tool(self.list_outstanding_files)
        ]

    @property
    @override
    def system_prompt_part(self) -> str:
        return """
You are operating in a mode that mandates that all files be reviewed before the run can be terminated. Calls to terminate the run will be prevented.

A list of outstanding files can be fetched through the provided tool.
"""

    @override
    async def handle_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        match event:
            case events.RunInitialized():
                type(self)._files = set(self.run.files.copy())
            case events.FileReviewed(path=path):
                async with self._files_lock:
                    typing.cast(set[Path], self._files).remove(path)
            case events.BeforeTerminateRun():
                if len(self._files):
                    return events.PreventTerminal(f"You are operating in a mode that mandates that all files be reviewed before the run can be terminated. There are {len(self._files)} file{'' if len(self._files) ==  1 else 's'} remaining to be reviewed.")

        return events.Skip()
