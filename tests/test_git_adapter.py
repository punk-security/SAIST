import asyncio

from git import Actor, Repo

from scm.adapters.git import GitAdapter


AUTHOR = Actor("SAIST Tests", "tests@example.com")


def commit(repo, message):
    return repo.index.commit(message, author=AUTHOR, committer=AUTHOR)


def test_git_adapter_reads_and_lists_files_at_compare_commit(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "settings.py").write_text("DEBUG = True\n", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\xff\xfe\x00\x00")
    repo.index.add(["app.py", "nested/settings.py", "image.bin"])
    head = commit(repo, "initial")

    adapter = GitAdapter(repo_path=tmp_path, base_commit=head.hexsha, compare_commit=head.hexsha)

    assert asyncio.run(adapter.list_files()) == ["app.py", "image.bin", "nested/settings.py"]
    assert asyncio.run(adapter.get_file_contents("nested/settings.py")) == "DEBUG = True\n"
    assert asyncio.run(adapter.get_file_contents("../outside.py")) is None
    assert asyncio.run(adapter.get_file_contents("image.bin")) is None


def test_git_adapter_regex_searches_compare_commit_files(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "app.py").write_text("SECRET_KEY = 'dev'\nprint(SECRET_KEY)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("SECRET_KEY is documented here\n", encoding="utf-8")
    repo.index.add(["app.py", "README.md"])
    head = commit(repo, "initial")

    adapter = GitAdapter(repo_path=tmp_path, base_commit=head.hexsha, compare_commit=head.hexsha)
    matches = asyncio.run(adapter.regex_search(r"SECRET_KEY", file_pattern="**/*.py", max_results=1))

    assert matches == [
        {
            "filename": "app.py",
            "line_number": 1,
            "column": 1,
            "match": "SECRET_KEY",
            "line": "SECRET_KEY = 'dev'",
        }
    ]


def test_git_adapter_get_changed_files_uses_base_to_compare_patch(tmp_path):
    repo = Repo.init(tmp_path)
    (tmp_path / "app.py").write_text("value = 'old'\n", encoding="utf-8")
    repo.index.add(["app.py"])
    base = commit(repo, "base")

    (tmp_path / "app.py").write_text("value = 'new'\n", encoding="utf-8")
    repo.index.add(["app.py"])
    compare = commit(repo, "compare")

    adapter = GitAdapter(repo_path=tmp_path, base_commit=base.hexsha, compare_commit=compare.hexsha)
    changed_files = adapter.get_changed_files()

    assert [file["filename"] for file in changed_files] == ["app.py"]
    assert "-value = 'old'" in changed_files[0]["patch"]
    assert "+value = 'new'" in changed_files[0]["patch"]
