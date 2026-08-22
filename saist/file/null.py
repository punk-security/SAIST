from dataclasses import dataclass
from pathlib import Path
from typing import override

from . import FileProvider, SearchMatch

class NullProvider(FileProvider):
    """
    A null provider. Just returns empty / None for all functions.
    """

    @property
    @override
    def system_prompt_part(self) -> str | None:
        return None

    @override
    async def list_files(self) -> list[Path]:
        return []

    @override
    async def read_file_contents(self, path: Path) -> str | None:
        return None

    @override
    async def search(self, pattern: str) -> list[SearchMatch]:
        return []

    @override
    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[SearchMatch]:
        return []
