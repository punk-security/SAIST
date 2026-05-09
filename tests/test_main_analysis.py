import asyncio
import time
from types import SimpleNamespace

import main as saist_main
from models import Finding, Findings
from scm.adapters.filesystem import FilesystemAdapter
from scm.adapters.git import GitAdapter as RealGitAdapter
from scm.adapters.github import Github as RealGithub
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

        def detect_prompt(self):
            return FilesystemAdapter.DETECT_PROMPT

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
    assert "not to produce a best-practice checklist" in llm.system_prompt
    assert "penetration test style review across the entire application codebase" in llm.system_prompt
    assert "cross-tenant data access" in llm.system_prompt


def test_analyze_single_file_uses_git_diff_prompt_for_git_adapter():
    class CapturingLlm:
        def __init__(self):
            self.system_prompt = None

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.system_prompt = system_prompt
            return Findings(findings=[])

    class GitAdapter:
        def tool_functions(self):
            return []

        def detect_prompt(self):
            return RealGitAdapter.DETECT_PROMPT

    llm = CapturingLlm()
    result = asyncio.run(
        saist_main.analyze_single_file(
            scm=GitAdapter(),
            adapter=llm,
            filename="app.py",
            patch_text="@@ -1 +1 @@\n-old\n+new\n",
            disable_tools=False,
        )
    )

    assert result == []
    assert "analyzing a diff of code that needs security review" in llm.system_prompt
    assert "git comparison" in llm.system_prompt
    assert "anchored to changed lines" in llm.system_prompt
    assert "pre-existing best-practice issues" in llm.system_prompt
    assert "penetration test style review" not in llm.system_prompt


def test_analyze_single_file_uses_github_pull_request_prompt():
    class CapturingLlm:
        def __init__(self):
            self.system_prompt = None

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.system_prompt = system_prompt
            return Findings(findings=[])

    class Github:
        def tool_functions(self):
            return []

        def detect_prompt(self):
            return RealGithub.DETECT_PROMPT

    llm = CapturingLlm()
    result = asyncio.run(
        saist_main.analyze_single_file(
            scm=Github(),
            adapter=llm,
            filename="app.py",
            patch_text="@@ -1 +1 @@\n-old\n+new\n",
            disable_tools=False,
        )
    )

    assert result == []
    assert "GitHub pull request" in llm.system_prompt
    assert "Report only vulnerabilities anchored to changed lines" in llm.system_prompt
    assert "business logic changes" in llm.system_prompt


def test_filesystem_tool_analysis_sends_file_inventory_and_tracks_coverage():
    class CapturingLlm:
        def __init__(self):
            self.system_prompt = None
            self.user_prompt = None
            self.tool_names = None

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.system_prompt = system_prompt
            self.user_prompt = user_prompt
            self.tool_names = [tool.__name__ for tool in tool_fns]
            read_file_contents = next(tool for tool in tool_fns if tool.__name__ == "read_file_contents")
            regex_search = next(tool for tool in tool_fns if tool.__name__ == "regex_search")
            await read_file_contents("app.py")
            await regex_search("SECRET", "**/*.py", 10)
            return Findings(
                findings=[
                    Finding(
                        file="app.py",
                        snippet="SECRET",
                        title="Secret",
                        issue="Issue",
                        recommendation="Fix it.",
                        cwe="CWE-798",
                        priority=6,
                        line_number=1,
                    )
                ]
            )

    class FakeScm:
        async def read_file_contents(self, filename):
            return "SECRET = 'dev'\n"

        async def list_files(self):
            return ["app.py", "settings.py"]

        async def regex_search(self, pattern, file_pattern="**/*", max_results=100):
            return [{"filename": "settings.py", "line_number": 1, "column": 1, "match": "SECRET", "line": "SECRET = 'dev'"}]

        def detect_prompt(self):
            return FilesystemAdapter.DETECT_PROMPT

    llm = CapturingLlm()
    findings, files_read = asyncio.run(
        saist_main.generate_findings_with_filesystem_tools(
            scm=FakeScm(),
            llm=llm,
            filenames=["app.py", "settings.py"],
            disable_tools=False,
            analysis_skills="Skill guidance",
        )
    )

    assert [finding.file for finding in findings] == ["app.py"]
    assert files_read == {"app.py", "settings.py"}
    assert "Application file inventory" in llm.user_prompt
    assert "- app.py" in llm.user_prompt
    assert "- settings.py" in llm.user_prompt
    assert "penetration test style review across the entire application codebase" in llm.system_prompt
    assert "Trace attacker-controlled input from entrypoint to sink" in llm.system_prompt
    assert "Skill guidance" in llm.system_prompt
    assert llm.tool_names == ["read_file_contents", "list_files", "regex_search"]


def test_filesystem_tool_analysis_iterations_respect_concurrency_limit():
    class CountingLlm:
        def __init__(self):
            self.calls = 0
            self.active = 0
            self.max_active = 0

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return Findings(
                findings=[
                    Finding(
                        file="app.py",
                        snippet="SECRET",
                        title=f"Secret {self.calls}",
                        issue=f"Issue {self.calls}",
                        recommendation="Fix it.",
                        cwe="CWE-798",
                        priority=6,
                        line_number=1,
                    )
                ]
            )

    class FakeScm:
        async def read_file_contents(self, filename):
            return "SECRET = 'dev'\n"

        async def list_files(self):
            return ["app.py"]

        async def regex_search(self, pattern, file_pattern="**/*", max_results=100):
            return []

        def detect_prompt(self):
            return FilesystemAdapter.DETECT_PROMPT

    llm = CountingLlm()
    findings, files_read = asyncio.run(
        saist_main.generate_findings_with_filesystem_tools_iterations(
            scm=FakeScm(),
            llm=llm,
            filenames=["app.py"],
            disable_tools=False,
            analysis_skills="",
            iterations=5,
            max_concurrent=2,
        )
    )

    assert llm.calls == 5
    assert llm.max_active == 2
    assert len(findings) == 5
    assert files_read == set()


def test_filesystem_tool_analysis_iterations_run_concurrently():
    class SlowLlm:
        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            await asyncio.sleep(0.05)
            return Findings(findings=[])

    class FakeScm:
        async def read_file_contents(self, filename):
            return ""

        async def list_files(self):
            return ["app.py"]

        async def regex_search(self, pattern, file_pattern="**/*", max_results=100):
            return []

        def detect_prompt(self):
            return FilesystemAdapter.DETECT_PROMPT

    started = time.perf_counter()
    asyncio.run(
        saist_main.generate_findings_with_filesystem_tools_iterations(
            scm=FakeScm(),
            llm=SlowLlm(),
            filenames=["app.py"],
            disable_tools=False,
            analysis_skills="",
            iterations=3,
            max_concurrent=3,
        )
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.12


def test_print_coverage_reports_read_percentage(capsys):
    saist_main.print_coverage({"app.py"}, ["app.py", "settings.py"])

    assert "LLM file coverage: 1/2 files read (50.0%)" in capsys.readouterr().out


def test_dedupe_findings_keeps_highest_priority_for_same_file_line_and_cwe():
    low = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "Low duplicate",
            "issue": "Lower severity issue",
            "recommendation": "Fix it.",
            "cwe": "CWE-20",
            "priority": 4,
            "line_number": 10,
        }
    )
    high = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "High duplicate",
            "issue": "Higher severity issue",
            "recommendation": "Fix it now.",
            "cwe": "CWE-20",
            "priority": 8,
            "line_number": 10,
        }
    )
    different_line = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "other_danger()",
            "title": "Different line",
            "issue": "Different issue",
            "recommendation": "Fix this too.",
            "cwe": "CWE-20",
            "priority": 5,
            "line_number": 11,
        }
    )

    deduped = saist_main.dedupe_findings([low, high, different_line])

    assert deduped == [high, different_line]


def test_get_llm_adapter_applies_thinking_option_to_adapter():
    args = SimpleNamespace(
        llm="faike",
        llm_model="Fake LLM",
        llm_api_key=None,
        thinking="xhigh",
        ollama_base_uri="http://localhost:11434",
    )

    adapter = asyncio.run(saist_main._get_llm_adapter(args))

    assert adapter.thinking == "xhigh"


def test_get_llm_adapter_builds_azure_foundry_adapter():
    args = SimpleNamespace(
        llm="azure-foundry",
        llm_model="gpt-5-mini",
        llm_api_key="azure-key",
        azure_openai_endpoint="https://example.openai.azure.com/openai/v1/",
        azure_openai_api_version=None,
        thinking="high",
        ollama_base_uri="http://localhost:11434",
    )

    adapter = asyncio.run(saist_main._get_llm_adapter(args))

    assert adapter.model_vendor == "Azure AI Foundry"
    assert adapter.model_name == "gpt-5-mini"
    assert adapter.thinking == "high"


def test_dedupe_findings_keeps_first_for_same_priority():
    first = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "First duplicate",
            "issue": "First issue",
            "recommendation": "First fix.",
            "cwe": "CWE-20",
            "priority": 7,
            "line_number": 10,
        }
    )
    second = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "Second duplicate",
            "issue": "Second issue",
            "recommendation": "Second fix.",
            "cwe": "CWE-20",
            "priority": 7,
            "line_number": 10,
        }
    )

    assert saist_main.dedupe_findings([first, second]) == [first]


def test_diff_review_comments_are_built_after_dedupe():
    first = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "First duplicate",
            "issue": "First issue",
            "recommendation": "First fix.",
            "cwe": "CWE-20",
            "priority": 5,
            "line_number": 10,
        }
    )
    second = Finding.model_validate(
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "Second duplicate",
            "issue": "Second issue",
            "recommendation": "Second fix.",
            "cwe": "CWE-20",
            "priority": 9,
            "line_number": 10,
        }
    )

    deduped = saist_main.dedupe_findings([first, second])
    comments = saist_main.build_diff_review_comments(deduped, {"app.py": {10: 14}})

    assert len(comments) == 1
    assert comments[0]["position"] == 13
    assert "Second issue" in comments[0]["body"]


def test_filesystem_shallow_scan_generates_missing_skills(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "app.py").write_text("print('hello')\n", encoding="utf-8")

    class FakeLlm:
        model_name = "fake-model"

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            return response_format.model_validate(
                {
                    "skills": [
                        {
                            "filename": "authorization-model.md",
                            "content": "# Authorization\nGenerated for test.",
                        }
                    ]
                }
            )

    class EmptyFilesystemAdapter:
        def get_changed_files(self):
            return []

        async def get_file_contents(self, filename):
            return ""

        async def list_files(self):
            return []

        async def regex_search(self, pattern, file_pattern="**/*", max_results=100):
            return []

        def create_review(self, comment, review_comments, request_changes):
            raise AssertionError("review should not be created when no files are listed")

    args = SimpleNamespace(
        SCM="filesystem",
        path=str(project_root),
        path_for_comparison=None,
        llm="faike",
        llm_model=None,
        thinking="medium",
        verbose=0,
        generate_skills=False,
        skills_path=".saist/skills",
        skills_sample_files=5,
        skills_sample_bytes=300,
        overwrite_skills=False,
        disable_skills=False,
        skills_max_bytes=60000,
        deep=False,
        include=None,
        exclude=None,
        dry_run=False,
        disable_tools=False,
        skip_line_length_check=False,
        max_line_length=1000,
        llm_rate_limit=1,
        iterations=3,
        disable_caching=True,
        cache_folder=str(tmp_path / "cache"),
        interactive=False,
        csv=False,
        web=False,
        pdf=False,
        ci=False,
        project_name=None,
    )

    async def fake_get_llm_adapter(parsed_args):
        return FakeLlm()

    monkeypatch.setattr(saist_main, "parse_args", lambda: args)
    monkeypatch.setattr(saist_main, "_get_llm_adapter", fake_get_llm_adapter)
    monkeypatch.setattr(saist_main, "_get_scm_adapter", lambda parsed_args: EmptyFilesystemAdapter())

    asyncio.run(saist_main.main())

    skill_file = project_root / ".saist" / "skills" / "authorization-model.md"
    assert skill_file.read_text(encoding="utf-8") == "# Authorization\nGenerated for test.\n"


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


def test_generate_summary_uses_scm_specific_prompt():
    class CapturingLlm:
        def __init__(self):
            self.system_prompt = None

        def prompt(self, system_prompt, user_prompt):
            self.system_prompt = system_prompt
            return "summary"

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

    llm = CapturingLlm()
    assert saist_main.generate_summary_from_findings(llm, [finding], RealGithub.SUMMARY_PROMPT) == "summary"
    assert "GitHub pull request diff-based code security review" in llm.system_prompt
