from dataclasses import dataclass
from models import FindingContext
from llm.adapters import BaseLlmAdapter
from jinja2 import Environment, FileSystemLoader
import subprocess
import logging
import os
import re
import datetime

logger = logging.getLogger("saist.latex")


# TODO: Container 'awareness'
@dataclass
class Latex:
    _DEFAULT_TEX_TEMPLATE = "report.tex.jinja"
    _DEFAULT_OUTPUT_DIR = "reporting"

    llm: BaseLlmAdapter
    project: str
    findings: list[FindingContext]
    comment: str

    def run(self, args):
        pdf_path = os.path.join(self._DEFAULT_OUTPUT_DIR, args.pdf_filename)
        tex_path = os.path.join(self._DEFAULT_OUTPUT_DIR, args.tex_filename)

        self._write_tex(tex_path)
        logger.info(f"Written TeX file to: '{tex_path}'")

        if args.pdf:
            print("\n📝 Generating PDF report...")

            rc = subprocess.run(
                ["latexmk", "-pdf", f"-outdir={self._DEFAULT_OUTPUT_DIR}", tex_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
            ).returncode

            if rc != 0:
                logger.error(f"Unable to build PDF '{tex_path}' -> '{pdf_path}'")
                exit(1)

            print(f"✨ Written report to '{pdf_path}'\n")

            logger.debug(f"Cleaning up auxiliary files in '{self._DEFAULT_OUTPUT_DIR}'")
            subprocess.run(["latexmk", "-c"], cwd=self._DEFAULT_OUTPUT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, )

    def _render_tex(self) -> str:
        env = Environment(
            loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "tex"))
        )
        env.globals.update(escape_tex=self._escape_tex)
        template = env.get_template(self._DEFAULT_TEX_TEMPLATE)
        template.globals['now'] = datetime.datetime.now().isoformat(sep=' ', timespec='minutes')
        return template.render({"model": self.llm, "project": self.project, "findings": self.findings, "comment": self.comment})
    
    def _write_tex(self, tex_path: str):
        try:
            os.makedirs(os.path.dirname(tex_path), exist_ok=True)
            with open(tex_path, "w") as fp:
                fp.write(self._render_tex())
        except Exception as e:
            logger.error(f"Unable to write TeX file to '{tex_path}': {e}")
            exit(1)

    def _escape_tex(self, text: str) -> str:
        if not text:
            return ""

        specials = {
            "&":  r"\&",
            "%":  r"\%",
            "$":  r"\$",
            "_":  r"\_",
            "{":  r"\{",
            "}":  r"\}",
            "#":  r"\#",
            "~":  r"\textasciitilde{}",
            "^":  r"\^{}",
            "\\": r"\textbackslash{}",
        }

        def repl(match: re.Match) -> str:
            char = match.group(0)
            return specials[char]

        pattern = r'.(?<=[&%$_{}#~^\\])'
        return re.sub(pattern, repl, text)
