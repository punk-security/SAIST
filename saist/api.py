import dataclasses
import glob
import os.path
import pathlib
import re
from typing import Optional, Callable, List

import pydantic
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from main import _get_llm_adapter
from llm.adapters import BaseLlmAdapter

workdir = os.path.curdir

def set_workdir(directory: str) -> None:
    """
    Sets the working directory to the given directory.
    :param directory:
    """
    global workdir
    workdir = directory


async def list_files():
    """
    List all files in the working directory.
    :return: a list of all strings in the directory
    """
    files = glob.glob(workdir + "/**/*", recursive=True)
    print("Listing files")

    return files

class FindFileResults(pydantic.BaseModel):
    filename: str
    results: list[str]

def find_in_file(filename: str, regex_patterns: list[str]) -> list[FindFileResults]:
    """
    Finds occurrences of the specified patterns in a single file.
    Glob is NOT supported.
    :param filename: A single, absolute path to a file to scan
    :param regex_patterns: The patterns to match against
    :return:
    """

    print("Finding in", filename, "regex pattern", regex_patterns)
    results = []

    try:
        if pathlib.Path(filename).is_dir():
            return []

        with open(os.path.join(workdir, filename), "r") as file:
            for pattern in regex_patterns:
                results.append(FindFileResults(filename=filename, results=re.findall(pattern, file.read())))
    except Exception as e:
        print(e)
    return results

def find_in_files(pattern: str, regex_patterns: List[str]) -> List[FindFileResults]:
    """
    Finds occurrences of the specified patterns in files matching a glob pattern.

    :param pattern: A glob pattern (e.g., '/path/to/files/*.txt') to match files
    :param regex_patterns: The patterns to match against
    :return: A list of FindFileResults for all matching files
    """
    print("Finding in files matching", pattern, "with patterns", regex_patterns)
    results = []
    try:
        for filename in glob.glob(pattern, recursive=True):
            results += find_in_file(filename, regex_patterns)
    except Exception as e:
        print(e)

    return results

@dataclasses.dataclass
class Args:
    llm_model: str
    llm: str
    llm_api_key: str

class Api:
    def __init__(self, system_prompt: Optional[str] = None):
        self._adapter: Optional[BaseLlmAdapter] = None
        self._system_prompt = system_prompt
        self._tools = []
        self._agent: Optional[Agent] = None
        self._messages = []

    async def init(self, provider_name: str, model_name: str, api_key: str, system_prompt: Optional[str] = None):
        self._adapter = await _get_llm_adapter(Args(llm_model=model_name, llm=provider_name, llm_api_key=api_key))
        self._agent = self._adapter.generate_agent(system_prompt=system_prompt, tool_fns=self._tools)

    def set_default_tools(self):
        self._tools = [list_files, find_in_file, find_in_files]

    def add_tool(self, tool_fn: Callable):
        self._tools.append(tool_fn)

    def clear(self):
        self._messages = []

    async def prompt(self, user_prompt: str):
        result = await self._agent.run(
            user_prompt=user_prompt,
            message_history=self._messages,
            usage_limits=UsageLimits(request_limit=500)
        )

        self._messages = result.all_messages()

        print(result.output)



