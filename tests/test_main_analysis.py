import asyncio

import main as saist_main
from models import Finding, Findings
from util.skills import skills_prompt_digest


def test_analyze_single_file_includes_analysis_skills_in_system_prompt():
    class CapturingLlm:
        def __init__(self):
            self.system_prompt = None
            self.user_prompt = None
            self.tool_fns = None

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.system_prompt = system_prompt
            self.user_prompt = user_prompt
            self.tool_fns = tool_fns
            return Findings(findings=[])

    class FakeScm:
        async def read_file_contents(self, filename):
            return "print('hello')\n"

        async def list_files(self):
            return ["app.py"]

        async def regex_search(self, pattern, file_pattern="**/*", max_results=100):
            return []

        def tool_functions(self):
            return [self.read_file_contents, self.list_files, self.regex_search]

    llm = CapturingLlm()
    result = asyncio.run(
        saist_main.analyze_single_file(
            scm=FakeScm(),
            adapter=llm,
            filename="app.py",
            patch_text="@@ -0,0 +1 @@\n+print('hello')\n",
            disable_tools=False,
            analysis_skills="Skill: authorization requires tenant ownership checks.",
        )
    )

    assert result == []
    assert "Skill: authorization requires tenant ownership checks." in llm.system_prompt
    assert "File: app.py" in llm.user_prompt
    assert [tool.__name__ for tool in llm.tool_fns] == [
        "read_file_contents",
        "list_files",
        "regex_search",
    ]


def test_process_file_reuses_cache_for_same_skills_and_salts_cache_when_skills_change(tmp_path, monkeypatch):
    class CountingLlm:
        def __init__(self):
            self.calls = 0

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.calls += 1
            return Findings(findings=[])

    class FakeScm:
        async def read_file_contents(self, filename):
            return "print('same file')\n"

    async def no_sleep(delay):
        return None

    monkeypatch.setattr(saist_main.asyncio, "sleep", no_sleep)

    llm = CountingLlm()
    scm = FakeScm()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    for skills in ("routing skill", "routing skill", "auth skill"):
        asyncio.run(
            saist_main.process_file(
                scm=scm,
                llm=llm,
                filename="app.py",
                patch_text="@@ -0,0 +1 @@\n+print('same file')\n",
                disable_tools=True,
                disable_caching=False,
                cache_folder=str(cache_dir),
                analysis_skills=skills,
            )
        )

    cache_files = sorted(path.name for path in cache_dir.iterdir())
    assert llm.calls == 2
    assert len(cache_files) == 2
    assert any(skills_prompt_digest("routing skill") in name for name in cache_files)
    assert any(skills_prompt_digest("auth skill") in name for name in cache_files)


def test_analyze_single_file_returns_none_when_llm_raises():
    class FailingLlm:
        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            raise RuntimeError("model unavailable")

    class FakeScm:
        async def read_file_contents(self, filename):
            return "print('hello')\n"

    result = asyncio.run(
        saist_main.analyze_single_file(
            scm=FakeScm(),
            adapter=FailingLlm(),
            filename="app.py",
            patch_text="@@ -0,0 +1 @@\n+print('hello')\n",
            disable_tools=True,
        )
    )

    assert result is None


def test_context_from_finding_returns_context_window():
    class FakeScm:
        async def read_file_contents(self, filename):
            assert filename == "app.py"
            return "\n".join(f"line {index}" for index in range(1, 8))

    finding = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "line 4",
            "title": "Issue",
            "issue": "Issue",
            "recommendation": "Fix it.",
            "cwe": "CWE-20",
            "priority": 4,
            "line_number": 4,
        }
    )

    context, start, end = asyncio.run(saist_main.context_from_finding(FakeScm(), finding, context_size=2))

    assert start == 2
    assert end == 6
    assert context == "line 2\nline 3\nline 4\nline 5\nline 6"


def test_context_from_finding_returns_none_when_file_read_fails():
    class FailingScm:
        async def read_file_contents(self, filename):
            raise FileNotFoundError(filename)

    finding = Finding.model_validate(
        {
            "file": "missing.py",
            "snippet": "missing",
            "title": "Issue",
            "issue": "Issue",
            "recommendation": "Fix it.",
            "cwe": "CWE-20",
            "priority": 4,
            "line_number": 1,
        }
    )

    assert asyncio.run(saist_main.context_from_finding(FailingScm(), finding)) is None


def test_generate_summary_from_findings_returns_fallback_when_llm_raises():
    class FailingLlm:
        def prompt(self, system_prompt, user_prompt):
            raise RuntimeError("summary unavailable")

    finding = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "Issue",
            "issue": "Issue",
            "recommendation": "Fix it.",
            "cwe": "CWE-20",
            "priority": 4,
            "line_number": 1,
        }
    )

    assert (
        saist_main.generate_summary_from_findings(FailingLlm(), [finding])
        == "Security issues found. Please review the inline comments."
    )
