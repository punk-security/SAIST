import difflib
import glob
import logging
import os.path
import pathlib
from filecmp import dircmp
from os import PathLike
from typing import Optional, AnyStr
from util.output import write_findings

import aiofiles

from . import BaseScmAdapter
from .. import File

logger = logging.getLogger(__name__)

class FilesystemAdapter(BaseScmAdapter):
    async def get_file_contents(self, filename: str):
        logger.debug(f"get_file_contents: reading file {filename} under {self.compare_path}")
        filename = os.path.join(self.compare_path, filename)
        try:
            if not pathlib.Path(filename).is_relative_to(self.compare_path):
                raise Exception(f"Tried to access file outside of the root: {filename}")

            async with aiofiles.open(filename, mode='r', encoding='utf-8') as f:
                contents = await f.read()

            return contents
        except Exception as e:
            logging.warn(f"ERR: {e}")

    def __init__(self, compare_path: PathLike[AnyStr] | str, base_path: Optional[PathLike[AnyStr] | str] = None):
        self.base_path = base_path
        self.compare_path = compare_path

    def create_review(self, comment, review_comments, request_changes):
        write_findings(comment,review_comments,request_changes)

    def get_changed_files(self) -> list[File]:
        return list(self._iter_changed_files())

    def _iter_changed_files(self) -> list[File]:
        logger.debug(f"Iterate changed files: base:{self.base_path}, compare:{self.compare_path}")

        if self.base_path is None:
            diffs = [path.replace("\\","/") for path in glob.glob("**/*", root_dir=self.compare_path, recursive=True,)]
            logger.debug("Changed file paths", extra={"paths": list(diffs)})

            for filename in [path for path in diffs if os.path.isfile(f"{self.compare_path}/{path}")]:
                a_path = f"{self.compare_path}/{filename}"

                try:
                    with open(a_path) as a:
                        patch = "".join(difflib.unified_diff([], a.readlines(), fromfile="", tofile=f""))

                        yield File(filename=filename, patch=patch)
                except UnicodeDecodeError:
                    # Binary file - ignore
                    logger.debug(f"File is not valid UTF-8, skipping: {a_path}")

            return None

        diffs = dircmp(self.base_path, self.compare_path)

        for filename in diffs.diff_files:
            a_path = f"{self.base_path}/{filename}"
            b_path = f"{self.compare_path}/{filename}"

            try:
                with open(a_path, "r") as a, open(b_path, "r") as b:
                    patch = "".join(difflib.unified_diff(a.readlines(), b.readlines(), fromfile="", tofile=""))

                    yield File(filename=filename, patch=patch)
            except UnicodeDecodeError:
                # Binary file - ignore
                logger.warning(f"File is not valid UTF-8, skipping: {a_path}, {b_path}")

    @staticmethod
    def likely():
        # TODO: implement proper logic
        return True
