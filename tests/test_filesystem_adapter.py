import asyncio

from scm.adapters.filesystem import FilesystemAdapter


def test_filesystem_adapter_lists_text_files_and_skips_binary_files(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\xff\xfe\x00\x00")

    adapter = FilesystemAdapter(compare_path=str(tmp_path))
    changed_files = adapter.get_changed_files()

    assert [file["filename"] for file in changed_files] == ["app.py"]
    assert "+print('hello')" in changed_files[0]["patch"]


def test_filesystem_adapter_reads_file_contents(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    adapter = FilesystemAdapter(compare_path=str(tmp_path))

    contents = asyncio.run(adapter.get_file_contents("app.py"))

    assert contents == "print('hello')\n"


def test_filesystem_adapter_lists_all_files(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\xff\xfe\x00\x00")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "settings.py").write_text("DEBUG = True\n", encoding="utf-8")

    adapter = FilesystemAdapter(compare_path=str(tmp_path))

    assert asyncio.run(adapter.list_files()) == ["app.py", "image.bin", "nested/settings.py"]


def test_filesystem_adapter_regex_searches_text_files(tmp_path):
    (tmp_path / "app.py").write_text("SECRET_KEY = 'dev'\nprint(SECRET_KEY)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("SECRET_KEY is documented here\n", encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\xff\xfe\x00\x00")

    adapter = FilesystemAdapter(compare_path=str(tmp_path))
    matches = asyncio.run(adapter.regex_search(r"SECRET_KEY", file_pattern="**/*.py"))

    assert matches == [
        {
            "filename": "app.py",
            "line_number": 1,
            "column": 1,
            "match": "SECRET_KEY",
            "line": "SECRET_KEY = 'dev'",
        },
        {
            "filename": "app.py",
            "line_number": 2,
            "column": 7,
            "match": "SECRET_KEY",
            "line": "print(SECRET_KEY)",
        },
    ]


def test_filesystem_adapter_regex_search_returns_error_for_invalid_regex(tmp_path):
    adapter = FilesystemAdapter(compare_path=str(tmp_path))

    result = asyncio.run(adapter.regex_search("["))

    assert result[0]["error"].startswith("Invalid regex:")
    assert result[0]["pattern"] == "["


def test_filesystem_adapter_returns_none_for_missing_or_outside_file(tmp_path):
    adapter = FilesystemAdapter(compare_path=str(tmp_path))

    assert asyncio.run(adapter.get_file_contents("missing.py")) is None
    assert asyncio.run(adapter.get_file_contents("/etc/passwd")) is None


def test_filesystem_adapter_compares_base_and_compare_paths(tmp_path):
    base_path = tmp_path / "base"
    compare_path = tmp_path / "compare"
    base_path.mkdir()
    compare_path.mkdir()
    (base_path / "app.py").write_text("value = 'old'\n", encoding="utf-8")
    (compare_path / "app.py").write_text("value = 'new'\n", encoding="utf-8")
    (compare_path / "new_only.py").write_text("ignored by current dircmp implementation\n", encoding="utf-8")

    adapter = FilesystemAdapter(compare_path=str(compare_path), base_path=str(base_path))
    changed_files = adapter.get_changed_files()

    assert [file["filename"] for file in changed_files] == ["app.py"]
    assert "-value = 'old'" in changed_files[0]["patch"]
    assert "+value = 'new'" in changed_files[0]["patch"]
