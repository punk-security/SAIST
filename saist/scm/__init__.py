from os import PathLike
from typing import TypedDict

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

    def create_review(self, comment, review_comments, request_changes):
        self.adapter.create_review(comment, review_comments, request_changes)
