import base64
import logging
import urllib.parse
from os import PathLike

import requests
import os

from requests import Request
from requests.auth import AuthBase
from requests.exceptions import HTTPError

from . import BaseScmAdapter

logger = logging.getLogger(__name__)

class GithubAuth(AuthBase):
    def __init__(self, github_token: str):
        self.token = github_token

    def __call__(self, r: Request):
        r.headers['Authorization'] = f"Bearer {self.token}"

        return r

class Github(BaseScmAdapter):
    API_BASE_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
    DETECT_PROMPT = """
You are analyzing a diff of code that needs security review.
The supplied input is a single file's unified diff from a GitHub pull request.
Focus on exploitable vulnerabilities introduced, exposed, or materially changed by this pull request.
Use tools to retrieve the full file and related files to validate whether the changed code is reachable, attacker-controlled, and crosses a security boundary.
Report only vulnerabilities anchored to changed lines in the original diff. Do not report pre-existing best-practice issues unless the pull request makes them exploitable or materially worse.
For business logic changes, inspect surrounding authorization, state transition, tenancy, payment, invitation, webhook, or admin-flow code before deciding.
"""

    SUMMARY_PROMPT = """
This summary is for a GitHub pull request diff-based code security review.
Summarize exploitable risks introduced or changed by the pull request, including business impact and affected security boundaries. Do not summarize generic best practices.
"""

    def __init__(self, github_token, repo, pr_number):
        self.github_token = github_token
        self.repo = repo  # "owner/repo"
        self.pr_number = pr_number

        if not self.github_token:
            raise ValueError("Missing GITHUB_TOKEN. Check your workflow permissions: pull-requests: write")
        if not self.repo or not self.pr_number:
            raise ValueError("Missing GITHUB_REPOSITORY or PR_NUMBER.")

        self.owner, self.repository = self.repo.split("/")

        self.requests = requests.Session()
        self.requests.headers.update({
            "Accept": "application/vnd.github.v3+json"
        })

        self.requests.auth = GithubAuth(github_token=self.github_token)
        self.commit_sha = self.get_pull_request_head_sha()

    async def get_file_contents(self, file_path: PathLike[str] | str):
        """
        Retrieve the contents of a file specified by file_path.
        Args:
            file_path: The file path of the file, relative to the repository root.

        Returns:
            str: A string containing the contents of the file
        Raises:
            Exception: When an invalid result is returned from the github api
        """

        clean_path = urllib.parse.urlparse(file_path).path
        clean_url = f"{self.API_BASE_URL}/repos/{self.repo}/contents/{clean_path}?ref={self.commit_sha}"

        res = self.requests.get(clean_url, headers={"Content-Type": "application/vnd.github.object+json"})
        try:
            res.raise_for_status()
        except HTTPError:
            if res.status_code == 404:
                logger.warning(f"get_file_contents {clean_path}: file does not exist at PR head; skipping.")
                return None
            raise

        json_res = res.json()

        match json_res:
            case {'encoding': 'base64', 'content': content}:
                try:
                    return base64.b64decode(content).decode("UTF-8")
                except UnicodeEncodeError:
                    logger.warning(f"get_file_contents {clean_path}: File contents is not valid UTF-8; skipping.")
                    return ""
            case {'encoding': encoding}:
                raise Exception(f"Unhandled encoding: {encoding}")
            case _:
                raise Exception("Unexpected response format")

    def get_pull_request_head_sha(self):
        """
        Retrieves the current HEAD commit SHA of the pull request,
        so we can attach our review comments to the correct commit.
        """
        url = f"{self.API_BASE_URL}/repos/{self.repo}/pulls/{self.pr_number}"
        resp = self.requests.get(url)
        resp.raise_for_status()
        pr_data = resp.json()
        return pr_data["head"]["sha"]


    def create_review(self, comment, review_comments, request_changes=True):
        """
        Submits a review to the PR with line-level comments.
        'review_comments' is a list of dicts with keys: path, position, body.
        """
        url = f"https://api.github.com/repos/{self.repo}/pulls/{self.pr_number}/reviews"
        event_type = "REQUEST_CHANGES" if request_changes else "COMMENT"

        data = {
            "body": comment,
            "commit_id": self.commit_sha,
            "event": event_type,
            "comments": review_comments
        }
        logger.debug("create_review: creating github review", extra={'data': data})
        resp = self.requests.post(url, json=data)
        logger.debug("create_review: response", extra={'content': resp.content})
        resp.raise_for_status()

    def get_changed_files(self):
        """
        Retrieves the full list of changed files in a pull request (including patch diffs),
        handling GitHub API pagination.

        Returns:
            A list of dicts, each with:
            - filename (str)
            - patch (str): the unified diff (if available)
        """

        all_files = []
        page = 1
        per_page = 100  # GitHub max per page

        while True:
            url = f"{self.API_BASE_URL}/repos/{self.repo}/pulls/{self.pr_number}/files?per_page={per_page}&page={page}"
            resp = self.requests.get(url)
            resp.raise_for_status()
            files_page = resp.json()
            if not files_page:
                break
            all_files.extend(file for file in files_page if file.get("status") != "removed")
            page += 1

        return all_files

    @staticmethod
    def likely():
        return os.getenv("GITHUB_TOKEN",None) is not None
