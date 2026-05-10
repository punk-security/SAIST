import asyncio
import csv
import json

from models import Finding
from util.caching import (
    filesystem_tool_findings_from_cache_file,
    findings_from_cache_file,
    hash_file,
    hash_files,
    store_filesystem_tool_findings_to_cache_file,
    store_findings_to_cache_file,
)
from util.output import write_csv


def make_finding(**overrides):
    values = {
        "file": "app.py",
        "snippet": "danger()",
        "title": "Dangerous call",
        "issue": "A dangerous call was introduced.",
        "recommendation": "Remove the dangerous call.",
        "validation_steps": ["Call the affected endpoint.", "Confirm the dangerous behavior is reachable."],
        "cwe": "CWE-20",
        "priority": 5,
        "line_number": 7,
    }
    values.update(overrides)
    return Finding.model_validate(values)


def test_hash_file_hashes_scm_file_contents():
    class FakeScm:
        async def read_file_contents(self, filename):
            assert filename == "app.py"
            return "same content\n"

    assert asyncio.run(hash_file(FakeScm(), "app.py")) == "f953bbd204bb867e48a6ff774cffa3dcffd02c6580e8f1d00c37dbbaa743d6c8"


def test_hash_files_includes_file_names_contents_and_extra_context():
    class FakeScm:
        async def read_file_contents(self, filename):
            return {"app.py": "same content\n", "binary.gz": None}[filename]

    first = asyncio.run(hash_files(FakeScm(), ["binary.gz", "app.py"], extra="iteration prompt"))
    second = asyncio.run(hash_files(FakeScm(), ["app.py", "binary.gz"], extra="iteration prompt"))
    different_extra = asyncio.run(hash_files(FakeScm(), ["app.py", "binary.gz"], extra="other prompt"))

    assert first == second
    assert first != different_extra


def test_findings_cache_round_trip(tmp_path):
    cache_file = tmp_path / "finding.json"
    finding = make_finding(priority=8)

    store_findings_to_cache_file("app.py", [finding], str(cache_file))
    loaded = findings_from_cache_file(str(cache_file))

    assert loaded == [finding]


def test_filesystem_tool_findings_cache_round_trip(tmp_path):
    cache_file = tmp_path / "shallow.json"
    finding = make_finding(priority=8)

    store_filesystem_tool_findings_to_cache_file(
        iteration=2,
        filenames=["app.py", "settings.py"],
        findings=[finding],
        files_read={"settings.py"},
        cache_file=str(cache_file),
    )

    loaded_findings, files_read = filesystem_tool_findings_from_cache_file(str(cache_file))

    assert loaded_findings == [finding]
    assert files_read == {"settings.py"}


def test_findings_cache_returns_empty_list_for_null_findings(tmp_path):
    cache_file = tmp_path / "empty.json"
    cache_file.write_text(json.dumps({"path": "app.py", "findings": None}), encoding="utf-8")

    assert findings_from_cache_file(str(cache_file)) == []


def test_write_csv_writes_finding_fields(tmp_path):
    csv_path = tmp_path / "findings.csv"
    finding = make_finding(cwe="CWE-89", priority=9)

    write_csv([finding], str(csv_path))

    with csv_path.open(newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows == [
        {
            "file": "app.py",
            "snippet": "danger()",
            "title": "Dangerous call",
            "issue": "A dangerous call was introduced.",
            "recommendation": "Remove the dangerous call.",
            "validation_steps": '["Call the affected endpoint.", "Confirm the dangerous behavior is reachable."]',
            "cwe": "CWE-89",
            "priority": "9",
            "line_number": "7",
        }
    ]
