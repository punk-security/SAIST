import asyncio

from util.skills import (
    format_analysis_skills,
    generate_skill_files,
    load_analysis_skills,
    project_root_from_args,
    resolve_skills_dir,
    skills_prompt_digest,
)


def test_load_analysis_skills_reads_markdown_in_order_and_respects_byte_limit(tmp_path):
    skills_dir = tmp_path / ".saist" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "b.md").write_text("second skill", encoding="utf-8")
    (skills_dir / "a.md").write_text("first skill with a long body", encoding="utf-8")
    (skills_dir / "empty.md").write_text("   ", encoding="utf-8")

    skills = load_analysis_skills(skills_dir, max_bytes=12)

    assert len(skills) == 1
    assert skills[0].path.name == "a.md"
    assert skills[0].content == "first skill"
    assert skills[0].truncated is True


def test_format_analysis_skills_wraps_guidance_with_source_names(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "routing.md").write_text("# Routing\nUse controllers.", encoding="utf-8")

    prompt_text = format_analysis_skills(load_analysis_skills(skills_dir))

    assert "Application analysis skills" in prompt_text
    assert "routing.md" in prompt_text
    assert "Use controllers." in prompt_text
    assert "Use this context to validate exploitability and business impact" in prompt_text
    assert "not to report generic best-practice advice" in prompt_text


def test_project_root_and_skills_dir_resolution(tmp_path):
    args = type("Args", (), {"SCM": "filesystem", "path": str(tmp_path)})()

    assert project_root_from_args(args) == tmp_path.resolve()
    assert resolve_skills_dir(tmp_path, ".saist/skills") == (tmp_path / ".saist" / "skills").resolve()
    assert resolve_skills_dir(tmp_path, str(tmp_path / "absolute")) == tmp_path / "absolute"


def test_skills_prompt_digest_changes_with_content():
    assert skills_prompt_digest("auth model") == skills_prompt_digest("auth model")
    assert skills_prompt_digest("auth model") != skills_prompt_digest("routing model")


def test_generate_skill_files_samples_project_and_sanitizes_filenames(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    (project_root / "package.json").write_text('{"dependencies": {"express": "latest"}}\n', encoding="utf-8")
    skills_dir = project_root / ".saist" / "skills"

    class FakeLlm:
        def __init__(self):
            self.user_prompt = None

        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            self.user_prompt = user_prompt
            return response_format.model_validate(
                {
                    "skills": [
                        {
                            "filename": "../Authorization Model!!",
                            "content": "# Authorization\nCheck tenant boundaries.",
                        }
                    ]
                }
            )

    llm = FakeLlm()
    result = asyncio.run(
        generate_skill_files(
            llm=llm,
            project_root=project_root,
            skills_dir=skills_dir,
            max_files=5,
            max_file_bytes=300,
        )
    )

    output_file = skills_dir / "authorization-model.md"
    assert result.skills_dir == skills_dir
    assert result.written == [output_file]
    assert result.skipped == []
    assert result.sampled_files == 2
    assert output_file.read_text(encoding="utf-8") == "# Authorization\nCheck tenant boundaries.\n"
    assert "authorization-model.md" in llm.user_prompt
    assert "package.json" in llm.user_prompt


def test_generate_skill_files_preserves_existing_files_unless_overwrite_is_enabled(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "routes.py").write_text("routes = []\n", encoding="utf-8")
    skills_dir = project_root / ".saist" / "skills"
    skills_dir.mkdir(parents=True)
    output_file = skills_dir / "application-routing.md"
    output_file.write_text("# Existing\nKeep me.\n", encoding="utf-8")

    class FakeLlm:
        async def prompt_structured(self, system_prompt, user_prompt, response_format, tool_fns=None):
            return response_format.model_validate(
                {
                    "skills": [
                        {
                            "filename": "application-routing.md",
                            "content": "# New\nReplace me when asked.",
                        }
                    ]
                }
            )

    skipped = asyncio.run(
        generate_skill_files(
            llm=FakeLlm(),
            project_root=project_root,
            skills_dir=skills_dir,
            overwrite=False,
        )
    )
    assert skipped.written == []
    assert skipped.skipped == [output_file]
    assert output_file.read_text(encoding="utf-8") == "# Existing\nKeep me.\n"

    overwritten = asyncio.run(
        generate_skill_files(
            llm=FakeLlm(),
            project_root=project_root,
            skills_dir=skills_dir,
            overwrite=True,
        )
    )
    assert overwritten.written == [output_file]
    assert overwritten.skipped == []
    assert output_file.read_text(encoding="utf-8") == "# New\nReplace me when asked.\n"
