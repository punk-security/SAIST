import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_PATH = ".saist/skills"
DEFAULT_SKILL_MAX_BYTES = 60000
DEFAULT_SKILL_SAMPLE_FILES = 80
DEFAULT_SKILL_SAMPLE_BYTES = 12000

SKILL_SPECS = [
    (
        "application-routing.md",
        "How requests, jobs, events, routes, controllers, handlers, and API endpoints are wired.",
    ),
    (
        "authentication-and-session.md",
        "How users, service accounts, API clients, sessions, tokens, cookies, and identity providers work.",
    ),
    (
        "authorization-model.md",
        "How access control decisions are made, including roles, permissions, policies, ownership checks, and tenancy boundaries.",
    ),
    (
        "framework-specific-concerns.md",
        "Framework conventions and security footguns that matter when reviewing this application.",
    ),
    (
        "data-model-and-persistence.md",
        "Important models, repositories, migrations, query patterns, and places where data integrity or isolation matters.",
    ),
    (
        "input-validation-and-trust-boundaries.md",
        "Where untrusted input enters the application and how validation, parsing, escaping, and serialization are handled.",
    ),
    (
        "dependency-and-configuration.md",
        "Security-sensitive dependencies, configuration patterns, environment variables, deployment assumptions, and feature flags.",
    ),
    (
        "security-sensitive-flows.md",
        "High-risk workflows such as payments, password reset, invitations, admin actions, file upload, webhooks, and background jobs.",
    ),
]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "SAISTCache",
    "__pycache__",
    "bin",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "target",
    "vendor",
}

TEXT_EXTENSIONS = {
    ".cs",
    ".css",
    ".env",
    ".go",
    ".graphql",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".md",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".sql",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".xml",
    ".yaml",
    ".yml",
}

IMPORTANT_FILENAMES = {
    ".env.example",
    "app.py",
    "application.yml",
    "application.yaml",
    "build.gradle",
    "cargo.toml",
    "composer.json",
    "docker-compose.yml",
    "dockerfile",
    "gemfile",
    "go.mod",
    "main.py",
    "manage.py",
    "middleware.py",
    "package.json",
    "pom.xml",
    "program.cs",
    "pyproject.toml",
    "requirements.txt",
    "routes.rb",
    "settings.py",
    "startup.cs",
    "urls.py",
}

IMPORTANT_PATH_TERMS = {
    "admin",
    "api",
    "auth",
    "config",
    "controller",
    "guard",
    "handler",
    "identity",
    "middleware",
    "migration",
    "model",
    "permission",
    "policy",
    "route",
    "schema",
    "security",
    "service",
    "session",
    "tenant",
    "user",
    "validation",
    "webhook",
}


@dataclass(frozen=True)
class AnalysisSkill:
    path: Path
    content: str
    truncated: bool = False


@dataclass(frozen=True)
class SkillGenerationResult:
    skills_dir: Path
    written: list[Path]
    skipped: list[Path]
    sampled_files: int


class GeneratedSkillFile(BaseModel):
    filename: Annotated[
        str,
        Field(description="Markdown filename for the generated skill file, such as authorization-model.md"),
    ]
    content: Annotated[
        str,
        Field(description="Durable Markdown instructions for future SAIST security analysis runs"),
    ]


class GeneratedSkillFiles(BaseModel):
    skills: list[GeneratedSkillFile]


def project_root_from_args(args) -> Path:
    if getattr(args, "SCM", None) in {"filesystem", "git"} and getattr(args, "path", None):
        return Path(args.path).expanduser().resolve()

    return Path.cwd().resolve()


def resolve_skills_dir(project_root: Path, skills_path: str) -> Path:
    configured_path = Path(skills_path).expanduser()
    if configured_path.is_absolute():
        return configured_path

    return (project_root / configured_path).resolve()


def load_analysis_skills(skills_dir: Path, max_bytes: int = DEFAULT_SKILL_MAX_BYTES) -> list[AnalysisSkill]:
    if max_bytes <= 0:
        return []

    if not skills_dir.exists():
        return []

    if not skills_dir.is_dir():
        logger.warning("Skills path exists but is not a directory: %s", skills_dir)
        return []

    skills: list[AnalysisSkill] = []
    remaining = max_bytes

    for path in sorted(skills_dir.rglob("*.md")):
        if not path.is_file():
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("Skill file is not valid UTF-8, skipping: %s", path)
            continue

        content = content.strip()
        if not content:
            continue

        truncated = False
        encoded_length = len(content.encode("utf-8"))
        if encoded_length > remaining:
            content = content.encode("utf-8")[:remaining].decode("utf-8", errors="ignore").strip()
            truncated = True

        if content:
            skills.append(AnalysisSkill(path=path, content=content, truncated=truncated))

        remaining -= min(encoded_length, remaining)
        if remaining <= 0:
            break

    return skills


def format_analysis_skills(skills: list[AnalysisSkill]) -> str:
    if not skills:
        return ""

    sections = [
        "Application analysis skills:",
        "The following project-specific skill files are guidance for this review. Use them to understand routing, identity, authorization, framework conventions, trust boundaries, and security-sensitive flows. Treat them as context, not proof of a vulnerability. Report only vulnerabilities that are present in the diff being reviewed.",
    ]

    for skill in skills:
        marker = " (truncated)" if skill.truncated else ""
        sections.append(f"\n--- {skill.path.name}{marker} ---\n{skill.content}")

    return "\n".join(sections)


def skills_prompt_digest(skills_prompt: str) -> str:
    return hashlib.sha256(skills_prompt.encode("utf-8")).hexdigest()[:16]


async def generate_skill_files(
    llm,
    project_root: Path,
    skills_dir: Path,
    max_files: int = DEFAULT_SKILL_SAMPLE_FILES,
    max_file_bytes: int = DEFAULT_SKILL_SAMPLE_BYTES,
    overwrite: bool = False,
) -> SkillGenerationResult:
    repository_profile, sampled_files = _build_repository_profile(
        project_root=project_root,
        skills_dir=skills_dir,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
    )

    existing_skills = load_analysis_skills(skills_dir)

    system_prompt = """
You are an application security architecture analyst generating durable SAIST skill files.
Skill files teach future security scans how this application works. They are not one-off vulnerability findings.

Rules:
- Generate concise Markdown files with instructions future reviews can use.
- Use the requested filenames where possible.
- Do not invent facts. If the sampled files do not prove something, say what is unknown and what should be inspected.
- Capture conventions, security boundaries, review heuristics, and framework-specific risks.
- Avoid secrets, credentials, and long code excerpts.
- Focus on how to analyze future diffs in this application.
"""

    user_prompt = f"""
Generate SAIST skill files for this application.

Requested skill files:
{_format_skill_specs()}

Existing skill files, if any, should be preserved in spirit and improved from the sampled application context:
{_format_existing_skills(existing_skills)}

Application context:
{repository_profile}
"""

    generated = await llm.prompt_structured(system_prompt, user_prompt, GeneratedSkillFiles)

    skills_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []

    for skill in generated.skills:
        filename = _safe_skill_filename(skill.filename)
        if not filename:
            continue

        output_path = skills_dir / filename
        content = skill.content.strip()
        if not content:
            continue

        if output_path.exists() and not overwrite:
            skipped.append(output_path)
            continue

        output_path.write_text(content + "\n", encoding="utf-8")
        written.append(output_path)

    return SkillGenerationResult(
        skills_dir=skills_dir,
        written=written,
        skipped=skipped,
        sampled_files=sampled_files,
    )


def _format_skill_specs() -> str:
    return "\n".join(f"- {filename}: {description}" for filename, description in SKILL_SPECS)


def _format_existing_skills(skills: list[AnalysisSkill]) -> str:
    if not skills:
        return "No existing skill files were found."

    return "\n\n".join(f"--- {skill.path.name} ---\n{skill.content}" for skill in skills)


def _build_repository_profile(
    project_root: Path,
    skills_dir: Path,
    max_files: int,
    max_file_bytes: int,
) -> tuple[str, int]:
    if not project_root.exists() or not project_root.is_dir():
        raise FileNotFoundError(f"Project root does not exist or is not a directory: {project_root}")

    candidates = _rank_candidate_files(project_root, skills_dir)
    selected = candidates[:max(0, max_files)]

    inventory = "\n".join(f"- {relative_path}" for _, relative_path, _ in candidates[:300])
    excerpts = []

    for _, relative_path, absolute_path in selected:
        content = _read_sample(absolute_path, max_file_bytes)
        if not content:
            continue
        excerpts.append(f"--- {relative_path} ---\n{content}")

    profile = [
        f"Project root: {project_root}",
        "Repository file inventory, ranked for security architecture discovery:",
        inventory or "No candidate files were found.",
        "Selected file excerpts:",
        "\n\n".join(excerpts) or "No readable file excerpts were found.",
    ]

    return "\n\n".join(profile), len(selected)


def _rank_candidate_files(project_root: Path, skills_dir: Path) -> list[tuple[int, str, Path]]:
    candidates: list[tuple[int, str, Path]] = []

    for current_root, dirnames, filenames in os.walk(project_root):
        current_path = Path(current_root)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not _should_skip_directory(current_path / dirname, skills_dir)
        ]

        for filename in filenames:
            absolute_path = current_path / filename
            if not absolute_path.is_file() or _is_under(absolute_path, skills_dir):
                continue

            try:
                relative_path = absolute_path.relative_to(project_root)
            except ValueError:
                continue

            score = _score_path(relative_path)
            if score <= 0:
                continue

            candidates.append((score, relative_path.as_posix(), absolute_path))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates


def _should_skip_directory(path: Path, skills_dir: Path) -> bool:
    name = path.name
    if name in EXCLUDED_DIR_NAMES:
        return True

    if name.startswith(".") and name not in {".github"}:
        return True

    return _is_under(path, skills_dir)


def _score_path(relative_path: Path) -> int:
    path_text = relative_path.as_posix().lower()
    filename = relative_path.name.lower()
    suffix = relative_path.suffix.lower()

    if suffix and suffix not in TEXT_EXTENSIONS:
        return 0

    score = 0
    if filename in IMPORTANT_FILENAMES:
        score += 100

    for term in IMPORTANT_PATH_TERMS:
        if term in path_text:
            score += 20

    if suffix in TEXT_EXTENSIONS:
        score += 10

    score -= min(len(relative_path.parts), 10)
    return score


def _read_sample(path: Path, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""

    try:
        with path.open("rb") as file:
            data = file.read(max_bytes + 1)
    except OSError as e:
        logger.debug("Unable to read sample file %s: %s", path, e)
        return ""

    if b"\x00" in data:
        return ""

    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace").strip()
    if truncated:
        text += "\n[truncated]"

    return text


def _safe_skill_filename(filename: str) -> str:
    cleaned = Path(filename).name.lower().strip()
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", cleaned)
    cleaned = cleaned.strip(".-_")

    if not cleaned:
        return ""

    if not cleaned.endswith(".md"):
        cleaned += ".md"

    return cleaned


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
