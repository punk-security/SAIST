from models import FindingContext
from reportlab_pdf import ReportLabPdf


class FakeLlm:
    model_vendor = "Fake AI"
    model_name = "fake-model"


STATIC_SUMMARY = (
    "SAIST reviewed the example application changes and found three issues across input validation, "
    "authorization, and secret handling. The issues below are static sample data used to verify the "
    "ReportLab PDF output path."
)


def example_findings():
    return [
        FindingContext.model_validate(
            {
                "file": "app/views.py",
                "snippet": "db.execute('select * from users where name = ' + username)",
                "title": "SQL injection through string concatenation",
                "issue": (
                    "User-controlled input is concatenated directly into a SQL query. "
                    "An attacker could provide crafted input that changes the query structure, reads data for other "
                    "users, or bypasses application-level checks. This example deliberately uses a longer issue "
                    "paragraph so the PDF renderer exercises multi-line issue text without letting the panel overlap "
                    "the section title. The vulnerable construction also makes later review difficult because the "
                    "query behaviour is hidden inside string assembly rather than expressed through a database API "
                    "that separates commands from values. If this pattern is copied into nearby handlers, the same "
                    "weakness can spread across multiple lookup and reporting paths."
                ),
                "recommendation": (
                    "Use parameterized queries for every user-controlled value and keep validation focused on the "
                    "expected username format before the database call is made. Add a regression test that passes "
                    "characters commonly used in SQL injection payloads and confirms they are treated as data rather "
                    "than executable SQL. This longer recommendation verifies that remediation text wraps cleanly in "
                    "the generated report. Review adjacent database calls for similar string concatenation and move "
                    "shared query construction into a small helper if the same lookup pattern appears in more than "
                    "one place. Prefer a fix that is obvious to future maintainers, because defensive query handling "
                    "is only reliable when it remains easy to spot during code review."
                ),
                "cwe": "CWE-89",
                "priority": 9,
                "line_number": 42,
                "context": (
                    "def lookup_user(username):\n"
                    "    audit('lookup', username)\n"
                    "    db.execute('select * from users where name = ' + username)\n"
                    "    return db.fetchone()"
                ),
                "context_start": 40,
                "context_end": 43,
            }
        ),
        FindingContext.model_validate(
            {
                "file": "app/api/admin.py",
                "snippet": "return export_customer_records(customer_id)",
                "title": "Missing tenant authorization check",
                "issue": "The export endpoint reads customer records without checking that the requester owns the tenant.",
                "recommendation": "Enforce a tenant ownership check before exporting customer data.",
                "cwe": "CWE-862",
                "priority": 8,
                "line_number": 88,
                "context": (
                    "@route('/admin/customers/<customer_id>/export')\n"
                    "def export_customer(customer_id):\n"
                    "    require_login()\n"
                    "    return export_customer_records(customer_id)"
                ),
                "context_start": 85,
                "context_end": 88,
            }
        ),
        FindingContext.model_validate(
            {
                "file": "settings.py",
                "snippet": "API_TOKEN = 'dev-token-123'",
                "title": "Hardcoded API token",
                "issue": "A static API token is stored in source code and could be exposed through the repository.",
                "recommendation": "Load secrets from a managed secret store or environment variable.",
                "cwe": "CWE-798",
                "priority": 5,
                "line_number": 12,
                "context": (
                    "DEBUG = False\n"
                    "SERVICE_URL = 'https://api.example.test'\n"
                    "API_TOKEN = 'dev-token-123'\n"
                    "TIMEOUT_SECONDS = 10"
                ),
                "context_start": 10,
                "context_end": 13,
            }
        ),
    ]


def test_reportlab_pdf_writes_pdf_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = type(
        "Args",
        (),
        {
            "pdf_filename": "example-issues.pdf",
            "SCM": "filesystem",
            "path": "/example/project",
        },
    )()

    ReportLabPdf(
        llm=FakeLlm(),
        project="Example Project",
        findings=example_findings(),
        comment=STATIC_SUMMARY,
    ).run(args)

    pdf_path = tmp_path / "reporting" / "example-issues.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert pdf_path.stat().st_size > 1000


def test_reportlab_pdf_splits_long_summary_across_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = type(
        "Args",
        (),
        {
            "pdf_filename": "long-summary.pdf",
            "SCM": "filesystem",
            "path": "/example/project",
        },
    )()
    long_summary = "\n\n".join(
        f"Executive Summary paragraph {index}. "
        "The assessment identified several high-impact findings and includes enough detail to span "
        "multiple pages without forcing the text into a single unbreakable table cell."
        for index in range(70)
    )

    ReportLabPdf(
        llm=FakeLlm(),
        project="Example Project",
        findings=example_findings(),
        comment=long_summary,
    ).run(args)

    pdf_path = tmp_path / "reporting" / "long-summary.pdf"
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
