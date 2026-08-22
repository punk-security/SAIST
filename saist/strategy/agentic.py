import asyncio
from dataclasses import asdict
import json
from pathlib import Path
from typing import override

from llm.tools import Tool

import events
from llm.roles import MessageRole
from saistrun import SAISTRun

from . import SAISTStrategy

class AgenticStrategy(SAISTStrategy):
    """
    A barebones agentic strategy.
    """
    @staticmethod
    async def list_files(_run: SAISTRun, _strategy: "AgenticStrategy"):
        """
        List all files.
        """
        return [str(p) for p in await _run.list_files()]

    @staticmethod
    async def read_file(_run: SAISTRun, _strategy: "AgenticStrategy", path: str):
        """
        Read a file and return its contents. The only files that are valid to read are whose paths have been returned by the other tools you have.
        """
        try:
            _path = Path(path)
        except:
            return {
                "error": "Malformed path."
            }

        try:
            file = await _run.read_file(_path)
            if file is None:
                raise Exception()
        except:
            return {
                "error": f"Failed to read file {_path}."
            }
        
        return file

    @staticmethod
    async def search(_run: SAISTRun, _strategy: "AgenticStrategy", pattern: str):
        """
        Search for a pattern across all files. This returns a list of objects with the following data:
            path: The path to the file
            line_number: The line number within the file
            column: The column at which the match starts
            match: The match itself
            full_line: The full line the match was found on
        """
        return [json.dumps(asdict(match), default=str) for match in await _run.search(pattern)]

    @staticmethod
    async def search_regex(_run: SAISTRun, _strategy: "AgenticStrategy", pattern: str):
        """
        Regex search for a pattern across all files. This returns a list of objects with the following data:
            path: The path to the file
            line_number: The line number within the file
            column: The column at which the match starts
            match: The match itself
            full_line: The full line the match was found on
        """
        return [json.dumps(asdict(match), default=str) for match in await _run.regex_search(pattern)]

    @property
    @override
    def tools(self) -> list[Tool]:
        return [
            Tool(self.list_files),
            Tool(self.read_file),
            Tool(self.search),
            Tool(self.search_regex),
        ]

    @property
    @override
    def system_prompt_part(self) -> str:
        return """
You are operating in an agentic capacity. Tools are provided for you to use for achieving your goal.

Before completing actions related to your goal, you should ensure you have made thorough use of the tools available in a multi-turn fashion.
"""

    @override
    async def handle_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        return events.Skip()
