from dataclasses import dataclass
from models import FindingContext
from jinja2 import Environment, FileSystemLoader


@dataclass
class Latex:
    _DEFAULT_TEX_TEMPLATE = "report.tex.jinja"

    findings: list[FindingContext]
    comment: str

    def _render_tex(self) -> str:
        template = Environment(loader=FileSystemLoader("saist/latex/tex")).get_template(
            self._DEFAULT_TEX_TEMPLATE
        )

        return template.render({"findings": self.findings, "comment": self.comment})

    def write_tex(self, tex_path: str):
        with open(tex_path, "w") as fp:
            fp.write(self._render_tex())
            print(f"Written tex file to {tex_path}")
