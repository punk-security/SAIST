from typing import Callable, TypedDict

from .adapters import BaseScmAdapter


class Review:
    pass

class Comment:
    pass


class File(TypedDict):
    filename: str
    patch: str


class Scm:
    def __init__(self, adapter: BaseScmAdapter):
        self.adapter = adapter

    def get_changed_files(self) -> list[File]:
        """
        Retrieves the full list of changed files in a pull request (including patch diffs),
        handling GitHub API pagination.

        Returns:
            A list of dicts, each with:
            - filename (str)
            - patch (str): the unified diff (if available)
        """
        return self.adapter.get_changed_files()

    async def read_file_contents(self, filename: str):
        """
        Asynchronously reads the contents of a file.

        Parameters:
        filename (str): The name of the file to read.

        Returns:
        str: The full contents of the file as a string.

        Raises:
        FileNotFoundError: If the specified file does not exist.
        IOError: If an error occurs while reading the file.
        """
        return await self.adapter.get_file_contents(filename)

    async def list_files(self) -> list[str]:
        """
        Lists all files available to the scanner, relative to the source root.
        """
        return await self.adapter.list_files()

    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[dict[str, str | int]]:
        """
        Searches files available to the scanner using a Python regular expression.

        Args:
            pattern: Python regular expression to search for. Inline flags like (?i) are supported.
            file_pattern: Optional glob for limiting files, for example **/*.py.
            max_results: Maximum number of matches to return.
        """
        return await self.adapter.regex_search(pattern, file_pattern, max_results)

    def tool_functions(self) -> list[Callable]:
        """
        Returns the SCM helper functions exposed to the LLM.
        """
        return [self.read_file_contents, self.list_files, self.regex_search]

    def detect_prompt(self) -> str:
        return self.adapter.detect_prompt()

    def summary_prompt(self) -> str:
        return self.adapter.summary_prompt()

    def create_review(self, comment, review_comments, request_changes):
        self.adapter.create_review(comment, review_comments, request_changes)
