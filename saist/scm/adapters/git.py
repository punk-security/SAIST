import io
import logging
from os import PathLike
from typing import Optional, Iterator

from scm import BaseScmAdapter, File
from git import Repo

from util.output import write_findings

logger = logging.getLogger(__name__)

class GitAdapter(BaseScmAdapter):
    async def get_file_contents(self, file_path: str):
        logger.debug(f"file_get_contents: Reading {file_path}")
        targetfile = self.compare_commit.tree / file_path
        with io.BytesIO(targetfile.data_stream.read()) as f:
            return f.read().decode('utf-8')

    def __init__(self, repo_path: Optional[PathLike]=None, base_branch: Optional[str] = None, compare_branch: Optional[str] = None, base_commit: Optional[str] = None, compare_commit: Optional[str] = None):
        self.repo_path = repo_path
        self.repo = self._repo()

        if compare_commit is not None:
            self.compare_commit = self.repo.commit(compare_commit)
        elif compare_branch is not None:
            try:
                self.compare_commit = self.repo.heads[compare_branch].commit
            except IndexError as _:
                # If we can't find it locally, try and resolve the ref on the default remote
                self.compare_commit = self.repo.remote().refs[compare_branch].commit
        else:
            logger.warning("No comparison commit provided. Defaulting to HEAD")
            self.compare_commit = self.repo.head.commit

        if base_commit is not None:
            self.base_commit = self.repo.commit(base_commit)
        elif base_branch is not None:
            logger.debug("Load repo heads", extra={"repo_heads": self.repo.heads})
            try:
                self.base_commit = self.repo.heads[base_branch].commit
            except IndexError as _:
                # If we can't find it locally, try and resolve the ref on the default remote
                self.base_commit = self.repo.remote().refs[base_branch].commit
        else:
            logger.warning("No base commit provided. Defaulting to main")
            self.base_commit = self.repo.heads['main'].commit

        if self.base_commit is None:
            logger.error("Could not resolve base commit")
            exit(-1)

        if self.compare_commit is None:
            logger.error("Could not resolve comparison commit")
            exit(-1)

    def _repo(self) -> Repo:
        repo = Repo(self.repo_path)

        return repo

    def _iter_diffs(self) -> Iterator[File]:
        diffs = self.compare_commit.diff(self.base_commit, create_patch=True)

        for diff in diffs:
            match diff.diff:
                case bytes(data):
                    yield File(filename=diff.a_path, patch=data.decode('UTF-8'))
                case data:
                    yield File(filename=diff.a_path, patch=data)

    def get_changed_files(self) -> list[File]:
        return list([f for f in self._iter_diffs() if f['filename'] != None])

    def create_review(self, comment, review_comments, request_changes):
        write_findings(comment,review_comments,request_changes)

    @staticmethod
    def likely():
        # TODO: determine logic
        return True
