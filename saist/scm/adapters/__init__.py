from abc import ABCMeta, abstractmethod
import fnmatch
from pathlib import PurePosixPath
import re


class BaseScmAdapter(metaclass=ABCMeta):
    @abstractmethod
    def create_review(self, comment, review_comments, request_changes):
        """
        Submits a review to the PR with line-level comments.
        'review_comments' is a list of dicts with keys: path, position, body.
        """
        pass

    @staticmethod
    def likely() -> bool:
        """
        Determines whether the adapter is likely to be applicable for the current environment.
        Used for auto-detection.
        """
        pass

    @abstractmethod
    def get_changed_files(self):
        pass

    @abstractmethod
    async def get_file_contents(self, file_path: str):
        pass

    async def list_files(self) -> list[str]:
        """
        Lists every file path available to this adapter, relative to the project root.
        Adapters that cannot enumerate files can return an empty list.
        """
        return []

    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[dict[str, str | int]]:
        """
        Searches available UTF-8 files using a Python regular expression.

        Args:
            pattern: Python regular expression to search for. Inline flags like (?i) are supported.
            file_pattern: Optional glob for limiting files, for example **/*.py.
            max_results: Maximum number of matches to return.

        Returns:
            A list of matches with filename, line_number, column, match, and line fields.
        """
        if max_results <= 0:
            return []

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return [{"error": f"Invalid regex: {e}", "pattern": pattern}]

        results = []
        for filename in await self.list_files():
            if not self._file_matches_pattern(filename, file_pattern):
                continue

            try:
                contents = await self.get_file_contents(filename)
            except Exception:
                continue

            if contents is None:
                continue

            for line_number, line in enumerate(contents.splitlines(), start=1):
                for match in regex.finditer(line):
                    results.append(
                        {
                            "filename": filename,
                            "line_number": line_number,
                            "column": match.start() + 1,
                            "match": match.group(0),
                            "line": line,
                        }
                    )
                    if len(results) >= max_results:
                        return results

        return results

    @staticmethod
    def _file_matches_pattern(filename: str, file_pattern: str) -> bool:
        if not file_pattern or file_pattern == "**/*":
            return True

        path = PurePosixPath(filename)
        patterns = [file_pattern]
        if file_pattern.startswith("**/"):
            patterns.append(file_pattern[3:])

        return any(path.match(pattern) or fnmatch.fnmatch(filename, pattern) for pattern in patterns)
