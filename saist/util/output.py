import csv
import json
from typing import Iterable
from rich.console import Console
from rich.markdown import Markdown
import random
from util.argparsing import banner
from models import Finding

def print_banner():
    console = Console(width=120)
    console.print(banner)

def write_findings(comment, review_comments, request_changes):
    console = Console(width=120)
    if not review_comments:
        console.print("👍 - No issues found")
        return
    if request_changes:
        console.print(Markdown(comment))
        console.print("")
        console.print("")
        console.print("Findings:")
        for c in review_comments:
            console.print(Markdown("---"))
            console.print(Markdown(f"## {c['path']} Line {c['position']}\n\n"))
            console.print("")
            console.print(Markdown(c['body']))
            console.print(Markdown("---"))
        pass

def write_csv(findings: Iterable[Finding], csv_path: str):
    fieldnames = list(Finding.model_json_schema()["properties"].keys())
    
    with open(csv_path, "w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            writer.writerow(finding.model_dump())
        print(f"Written files to {csv_path}")
