import asyncio
import csv
import json

from models import Finding
from util.caching import findings_from_cache_file, hash_file, store_findings_to_cache_file
from util.output import write_csv


def make_finding(**overrides):
    values = {
        "file": "app.py",
        "snippet": "danger()",
        "title": "Dangerous call",
        "issue": "A dangerous call was introduced.",
        "recommendation": "Remove the dangerous call.",
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


def test_findings_cache_round_trip(tmp_path):
    cache_file = tmp_path / "finding.json"
    finding = make_finding(priority=8)

    store_findings_to_cache_file("app.py", [finding], str(cache_file))
    loaded = findings_from_cache_file(str(cache_file))

    assert loaded == [finding]


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
            "cwe": "CWE-89",
            "priority": "9",
            "line_number": "7",
        }
    ]
