import asyncio
import base64

from scm.adapters.github import Github


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def github_with_session(session):
    adapter = Github.__new__(Github)
    adapter.requests = session
    adapter.repo = "owner/repo"
    adapter.pr_number = "123"
    adapter.commit_sha = "abc123"
    return adapter


def test_github_changed_files_excludes_removed_files():
    session = FakeSession(
        [
            FakeResponse(
                [
                    {"filename": "app.py", "status": "modified", "patch": "@@ -1 +1 @@"},
                    {"filename": "deleted.py", "status": "removed", "patch": "@@ -1 +0 @@"},
                ]
            ),
            FakeResponse([]),
        ]
    )
    adapter = github_with_session(session)

    changed_files = adapter.get_changed_files()

    assert changed_files == [{"filename": "app.py", "status": "modified", "patch": "@@ -1 +1 @@"}]


def test_github_get_file_contents_returns_none_for_missing_pr_head_file():
    session = FakeSession([FakeResponse(status_code=404)])
    adapter = github_with_session(session)

    assert asyncio.run(adapter.get_file_contents("deleted.py")) is None


def test_github_get_file_contents_decodes_base64_content():
    content = base64.b64encode(b"print('hello')\n").decode()
    session = FakeSession([FakeResponse({"encoding": "base64", "content": content})])
    adapter = github_with_session(session)

    assert asyncio.run(adapter.get_file_contents("app.py")) == "print('hello')\n"
