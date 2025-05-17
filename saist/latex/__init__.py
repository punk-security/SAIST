from dataclasses import dataclass
from models import FindingContext
from jinja2 import Environment, FileSystemLoader
import subprocess
from shutil import which
import logging

logger = logging.getLogger(__name__)

# TODO: Exception handling and container 'awareness'
@dataclass
class Latex:
    _DEFAULT_TEX_TEMPLATE = "report.tex.jinja"
    _DEFAULT_OUTPUT_DIR = "build"

    findings: list[FindingContext]
    comment: str

    def _render_tex(self) -> str:
        template = Environment(loader=FileSystemLoader("latex/tex")).get_template(
            self._DEFAULT_TEX_TEMPLATE
        )

        return template.render({"findings": self.findings, "comment": self.comment})

    def _write_tex(self, tex_path: str):
        with open(tex_path, "w") as fp:
            fp.write(self._render_tex())
            logger.info(f"Written TeX file to '{tex_path}'")

    def output_pdf(self, tex_path: str, pdf_path: str):
        if which("latexmk") == None:
            logger.error("[Error] Unable to find 'latexmk' binary in $PATH needed for PDF report building")
            exit(1)

        self._write_tex(tex_path)

        _ = subprocess.run(["latexmk", "-pdf", f"-outdir={self._DEFAULT_OUTPUT_DIR}", tex_path])
        # _ = subprocess.run(["latexmk", "-c", f"-outdir={self._DEFAULT_OUTPUT_DIR}"])
