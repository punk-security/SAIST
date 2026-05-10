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
    DETECT_PROMPT = """
You are performing a penetration test style review across the entire application codebase.
The supplied input is one file from the application. It may be represented as a unified diff from an empty file, but you should treat it as application code in scope for a whole-codebase security assessment.
Use tools aggressively to map routes, controllers, models, middleware, policies, serializers, templates, jobs, and configuration before deciding what is exploitable.
Trace attacker-controlled input from entrypoint to sink and trace authorization decisions from identity source to protected action.
Look for business logic vulnerabilities across files: cross-tenant data access, horizontal/vertical privilege escalation, order/payment/state-machine manipulation, invitation or password-reset abuse, webhook forgery, unsafe admin actions, and background jobs that trust user-controlled state.
Report vulnerabilities that are present in the application, even when the exploit depends on interactions across multiple files.
Avoid one-file lint findings unless that file alone proves a reachable vulnerability.
"""

    SUMMARY_PROMPT = """
This summary is for a penetration test style review across the entire application codebase.
Summarize exploitable application risks, affected trust boundaries, likely business impact, and the highest-impact fixes. Do not summarize generic best practices.
"""

    async def get_file_contents(self, filename: str):
        logger.debug(f"get_file_contents: reading file {filename} under {self.compare_path}")
        try:
            file_path = self._resolve_under_root(filename)

            async with aiofiles.open(file_path, mode="rb") as f:
                data = await f.read()

            return data.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug(f"get_file_contents: file is not valid UTF-8, skipping: {filename}")
            return None
        except (FileNotFoundError, IsADirectoryError):
            logger.debug(f"get_file_contents: file does not exist or is not readable: {filename}")
            return None
        except Exception as e:
            logger.warning(f"get_file_contents: could not read {filename}: {e}")
            return None

    def __init__(self, compare_path: PathLike[AnyStr] | str, base_path: Optional[PathLike[AnyStr] | str] = None):
        self.base_path = base_path
        self.compare_path = compare_path

    def create_review(self, comment, review_comments, request_changes):
        write_findings(comment,review_comments,request_changes)

    def get_changed_files(self) -> list[File]:
        return list(self._iter_changed_files())

    async def list_files(self) -> list[str]:
        """
        Lists all regular files under the comparison path.
        Paths are relative to the comparison path and use POSIX separators.
        """
        root = self._root_path()
        files = []

        for path in root.rglob("*"):
            try:
                resolved_path = path.resolve()
            except OSError as e:
                logger.warning(f"Could not resolve file path {path}: {e}")
                continue

            if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
                continue

            files.append(path.relative_to(root).as_posix())

        return sorted(files)

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

    def _root_path(self) -> pathlib.Path:
        return pathlib.Path(self.compare_path).resolve()

    def _resolve_under_root(self, filename: str) -> pathlib.Path:
        root = self._root_path()
        file_path = (root / filename).resolve()

        if not file_path.is_relative_to(root):
            raise Exception(f"Tried to access file outside of the root: {filename}")

        return file_path
