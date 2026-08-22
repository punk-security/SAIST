import asyncio
import fnmatch
import logging
import re
from typing import AsyncGenerator, override
from pathlib import Path, PurePosixPath

import aiofiles

from util.output import write_findings

from . import FileProvider, SearchMatch

logger = logging.getLogger(__name__)

class FilesystemProvider(FileProvider):
    root: Path

    def __init__(self, path: Path):
        self.root = path.resolve()

    @property
    @override
    def system_prompt_part(self) -> str | None:
        return None

    async def _iter_files(self) -> AsyncGenerator[Path, None]:
        stack = [self.root]

        while len(stack):
            current = stack.pop()

            for path in current.iterdir():
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root):
                    continue

                if resolved.is_file():
                    if resolved.suffix.lower() not in [
                        ".c", ".cpp", ".h", ".hpp",
                        ".py", ".js", ".jsx", ".ts", ".tsx",
                        ".java", ".cs", ".go", ".php", ".rb",
                        ".swift", ".scala", ".kt", ".m", ".mm",
                        ".rs", ".sh"
                    ]:
                        continue
                    yield resolved.relative_to(self.root)
                if resolved.is_dir():
                    stack.append(resolved)

            await asyncio.sleep(0)

    @override
    async def list_files(self) -> list[Path]:
        return [path async for path in self._iter_files()]

    @override
    async def read_file_contents(self, path: Path) -> str | None:
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise Exception(f"Tried to access file outside of the root: {path}")

        data: bytes

        async with aiofiles.open(resolved, mode="rb") as f:
            data = await f.read()

        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            logger.debug(f"get_file_contents: file is not valid UTF-8, skipping: {path}")
            return None

    @override
    async def search(self, pattern: str) -> list[SearchMatch]:
        return await self.regex_search(re.escape(pattern))

    @override
    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[SearchMatch]:
        try:
            regex = re.compile(pattern)
        except:
            return []

        matches: list[SearchMatch] = []

        async for path in self._iter_files():
            if file_pattern != "**/*":
                _path = PurePosixPath(path)
                patterns = [file_pattern]
                if file_pattern.startswith("**/"):
                    patterns.append(file_pattern[3:])

                if any(path.match(pattern) or fnmatch.fnmatch(str(path), pattern) for pattern in patterns):
                    continue

            content = await self.read_file_contents(path)
            if content is None:
                continue

            for line_number, full_line in enumerate(content.split("\n")):
                for match in regex.finditer(full_line):
                    matches.append(
                        SearchMatch(
                            path=path,
                            line_number=line_number,
                            column=match.start() + 1,
                            match=match.group(0),
                            full_line=full_line
                        )
                    )

                    if len(matches) == max_results:
                        return matches

        return matches

    #region SAIST Backwards Compatibility
    def create_review(self, comment, review_comments, request_changes):
        write_findings(comment,review_comments,request_changes)
