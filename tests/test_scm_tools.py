import asyncio

from scm import Scm
from scm.adapters import BaseScmAdapter


class StubAdapter(BaseScmAdapter):
    def create_review(self, comment, review_comments, request_changes):
        return None

    def get_changed_files(self):
        return []

    async def get_file_contents(self, file_path: str):
        return f"contents for {file_path}"


class ToolAdapter(StubAdapter):
    async def list_files(self):
        return ["app.py", "README.md"]

    async def regex_search(self, pattern: str, file_pattern: str = "**/*", max_results: int = 100):
        return [{"filename": "app.py", "line_number": 1, "column": 1, "match": pattern, "line": pattern}]


def test_scm_exposes_llm_tool_functions_in_order():
    scm = Scm(ToolAdapter())

    assert [tool.__name__ for tool in scm.tool_functions()] == [
        "read_file_contents",
        "list_files",
        "regex_search",
    ]


def test_scm_delegates_file_tools_to_adapter():
    scm = Scm(ToolAdapter())

    assert asyncio.run(scm.read_file_contents("app.py")) == "contents for app.py"
    assert asyncio.run(scm.list_files()) == ["app.py", "README.md"]
    assert asyncio.run(scm.regex_search("needle")) == [
        {
            "filename": "app.py",
            "line_number": 1,
            "column": 1,
            "match": "needle",
            "line": "needle",
        }
    ]


def test_base_adapter_file_tool_stubs_do_not_error():
    scm = Scm(StubAdapter())

    assert asyncio.run(scm.list_files()) == []
    assert asyncio.run(scm.regex_search("needle")) == []
