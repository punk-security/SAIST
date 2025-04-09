from abc import ABCMeta, abstractmethod
from os import PathLike


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
