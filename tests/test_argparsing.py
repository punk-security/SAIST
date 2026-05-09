import pytest

from util import argparsing


def parse_with(monkeypatch, argv):
    monkeypatch.setattr(argparsing.sys, "argv", ["saist"] + argv)
    return argparsing.parse_args()


def test_parse_args_sets_defaults_for_filesystem(monkeypatch, tmp_path):
    args = parse_with(monkeypatch, ["--llm", "faike", "filesystem", str(tmp_path)])

    assert args.SCM == "filesystem"
    assert args.path == str(tmp_path)
    assert args.path_for_comparison is None
    assert args.llm == "faike"
    assert args.llm_api_key is None
    assert args.llm_model is None
    assert args.llm_rate_limit == 10
    assert args.ollama_base_uri == "http://localhost:11434"
    assert args.openai_base_uri is None
    assert args.interactive is False
    assert args.disable_tools is False
    assert args.deep is False
    assert args.web is False
    assert args.web_port == 8080
    assert args.web_host == "127.0.0.1"
    assert args.ci is False
    assert args.csv is False
    assert args.csv_path == "results.csv"
    assert args.pdf is False
    assert args.pdf_filename == "report.pdf"
    assert args.disable_caching is False
    assert args.cache_folder == "SAISTCache"
    assert args.skills_path == ".saist/skills"
    assert args.disable_skills is False
    assert args.generate_skills is False
    assert args.overwrite_skills is False
    assert args.skills_max_bytes == 60000
    assert args.skills_sample_files == 80
    assert args.skills_sample_bytes == 12000
    assert args.project_name is None
    assert args.skip_line_length_check is False
    assert args.max_line_length == 1000
    assert args.include is None
    assert args.exclude is None
    assert args.dry_run is False
    assert args.verbose == 0


def test_parse_args_accepts_all_global_scan_options(monkeypatch, tmp_path):
    args = parse_with(
        monkeypatch,
        [
            "--llm",
            "openai",
            "--llm-api-key",
            "test-key",
            "--llm-model",
            "gpt-test",
            "--llm-rate-limit",
            "3",
            "--ollama-base-uri",
            "http://ollama.example",
            "--openai-base-uri",
            "http://openai.example",
            "--interactive",
            "--disable-tools",
            "--deep",
            "--web",
            "--web-port",
            "9999",
            "--web-host",
            "0.0.0.0",
            "--ci",
            "--csv",
            "--csv-path",
            str(tmp_path / "results.csv"),
            "--pdf",
            "--pdf-filename",
            str(tmp_path / "report.pdf"),
            "--disable-caching",
            "--cache-folder",
            str(tmp_path / "cache"),
            "--skills-path",
            str(tmp_path / "skills"),
            "--disable-skills",
            "--skills-max-bytes",
            "321",
            "--skills-sample-files",
            "4",
            "--skills-sample-bytes",
            "500",
            "--project-name",
            "Project X",
            "--skip-line-length-check",
            "--max-line-length",
            "222",
            "--include",
            "**/*.py",
            "-i",
            "**/*.js",
            "--exclude",
            "build/",
            "-e",
            "*.min.js",
            "--dry-run",
            "-vv",
            "filesystem",
            str(tmp_path / "app"),
            "--path-for-comparison",
            str(tmp_path / "base"),
        ],
    )

    assert args.SCM == "filesystem"
    assert args.path == str(tmp_path / "app")
    assert args.path_for_comparison == str(tmp_path / "base")
    assert args.llm == "openai"
    assert args.llm_api_key == "test-key"
    assert args.llm_model == "gpt-test"
    assert args.llm_rate_limit == 3
    assert args.ollama_base_uri == "http://ollama.example"
    assert args.openai_base_uri == "http://openai.example"
    assert args.interactive is True
    assert args.disable_tools is True
    assert args.deep is True
    assert args.web is True
    assert args.web_port == 9999
    assert args.web_host == "0.0.0.0"
    assert args.ci is True
    assert args.csv is True
    assert args.csv_path == str(tmp_path / "results.csv")
    assert args.pdf is True
    assert args.pdf_filename == str(tmp_path / "report.pdf")
    assert args.disable_caching is True
    assert args.cache_folder == str(tmp_path / "cache")
    assert args.skills_path == str(tmp_path / "skills")
    assert args.disable_skills is True
    assert args.generate_skills is False
    assert args.overwrite_skills is False
    assert args.skills_max_bytes == 321
    assert args.skills_sample_files == 4
    assert args.skills_sample_bytes == 500
    assert args.project_name == "Project X"
    assert args.skip_line_length_check is True
    assert args.max_line_length == 222
    assert args.include == [["**/*.py"], ["**/*.js"]]
    assert args.exclude == [["build/"], ["*.min.js"]]
    assert args.dry_run is True
    assert args.verbose == 2


def test_parse_args_accepts_skill_generation_options(monkeypatch, tmp_path):
    args = parse_with(
        monkeypatch,
        [
            "--llm",
            "faike",
            "--generate-skills",
            "--overwrite-skills",
            "--skills-path",
            "custom-skills",
            "--skills-max-bytes",
            "123",
            "--skills-sample-files",
            "2",
            "--skills-sample-bytes",
            "3",
            "filesystem",
            str(tmp_path),
        ],
    )

    assert args.llm == "faike"
    assert args.SCM == "filesystem"
    assert args.path == str(tmp_path)
    assert args.generate_skills is True
    assert args.overwrite_skills is True
    assert args.skills_path == "custom-skills"
    assert args.skills_max_bytes == 123
    assert args.skills_sample_files == 2
    assert args.skills_sample_bytes == 3


def test_parse_args_accepts_git_subcommand_options(monkeypatch, tmp_path):
    args = parse_with(
        monkeypatch,
        [
            "--llm",
            "faike",
            "git",
            str(tmp_path),
            "--ref-for-compare",
            "develop",
            "--ref-to-compare",
            "feature",
            "--commit-for-compare",
            "abc123",
            "--commit-to-compare",
            "def456",
        ],
    )

    assert args.SCM == "git"
    assert args.path == str(tmp_path)
    assert args.ref_for_compare == "develop"
    assert args.ref_to_compare == "feature"
    assert args.commit_for_compare == "abc123"
    assert args.commit_to_compare == "def456"


def test_parse_args_sets_git_subcommand_defaults(monkeypatch, tmp_path):
    args = parse_with(monkeypatch, ["--llm", "faike", "git", str(tmp_path)])

    assert args.SCM == "git"
    assert args.path == str(tmp_path)
    assert args.ref_for_compare == "main"
    assert args.ref_to_compare == "HEAD"
    assert args.commit_for_compare is None
    assert args.commit_to_compare is None


def test_parse_args_accepts_github_subcommand_options(monkeypatch):
    args = parse_with(
        monkeypatch,
        [
            "--llm",
            "faike",
            "github",
            "owner/repo",
            "--github-token",
            "github-token",
            "123",
        ],
    )

    assert args.SCM == "github"
    assert args.repository == "owner/repo"
    assert args.github_token == "github-token"
    assert args.pr == "123"


def test_parse_args_accepts_poem_subcommand(monkeypatch):
    args = parse_with(monkeypatch, ["--llm", "faike", "poem"])

    assert args.SCM == "poem"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["--llm", "openai", "filesystem", "/tmp/project"],
            "You must provide an api key",
        ),
        (
            ["--llm", "faike", "--interactive", "filesystem", "/tmp/project"],
            "Faike LLM",
        ),
        (
            ["--llm", "ollama", "--interactive", "filesystem", "/tmp/project"],
            "cannot use the interactive shell with ollama",
        ),
        (
            ["--llm", "faike", "--generate-skills", "poem"],
            "Cannot generate SAIST skills while using the poem command",
        ),
        (
            ["--llm", "faike", "--generate-skills", "--disable-skills", "filesystem", "/tmp/project"],
            "Cannot use --generate-skills together with --disable-skills",
        ),
        (
            ["--llm", "faike", "--disable-tools", "filesystem", "/tmp/project"],
            "Filesystem scans without --deep require tool use",
        ),
    ],
)
def test_parse_args_rejects_invalid_combinations(monkeypatch, capsys, argv, message):
    with pytest.raises(SystemExit) as exc_info:
        parse_with(monkeypatch, argv)

    assert exc_info.value.code == 2
    assert message in capsys.readouterr().out


def test_parse_args_rejects_bedrock_api_key(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_with(monkeypatch, ["--llm", "bedrock", "--llm-api-key", "nope", "filesystem", "/tmp/project"])

    assert exc_info.value.code == 2
    assert "Do not provide an API key for bedrock" in capsys.readouterr().out


def test_parse_args_accepts_pdf_without_external_renderer_dependency(monkeypatch):
    args = parse_with(monkeypatch, ["--llm", "faike", "--pdf", "filesystem", "/tmp/project"])

    assert args.pdf is True
