import os
from flask import Flask, render_template_string
from typing import List
from models import FindingEnriched  # Update as needed for your project
import json

class FindingsServer:
    def __init__(self):
        self.app = Flask(__name__)
        @self.app.route("/")
        def index():
            return render_template_string(self._load_template(), findings=self.findings)

    def run(self, enriched_findings: List[FindingEnriched]):
        self.findings = list([dict(x) for x in enriched_findings])
        self.app.run(port=8080)

    def _load_template(self) -> str:
        # Load template.html from the same directory as this file
        template_path = os.path.join(os.path.dirname(__file__), "template.html")
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
