from abc import ABC, abstractmethod
from dataclasses import dataclass
import io
from pathlib import Path

@dataclass
class SearchMatch:
    path: Path
    line_number: int
    column: int
    match: str
    full_line: str

class FileProvider(ABC):
    """
    A file provider; provides files to a SAIST run, optionally transforming them.

    Must implement at least logic to:
    - list all files
    - read file content
    - search for text in files
    - search for regex in files
    """

    @property
    @abstractmethod
    def system_prompt_part(self) -> str | None: ...

    @abstractmethod
    async def list_files(self) -> list[Path]: ...

    @abstractmethod
    async def read_file_contents(self, path: Path) -> str | None: ...

    @abstractmethod
    async def search(self, pattern: str) -> list[SearchMatch]: ...

    @abstractmethod
    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[SearchMatch]: ...
