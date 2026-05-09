from dataclasses import dataclass
from html import escape
import datetime
import logging
import os

from llm.adapters import BaseLlmAdapter
from models import FindingContext
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, XPreformatted
from reportlab.platypus.tableofcontents import TableOfContents

logger = logging.getLogger("saist.reportlab_pdf")

PUNK_BG_HEX = "#111B29"
PUNK_SECONDARY_HEX = "#0C2540"
PUNK_SECONDARY_LIGHT_HEX = "#2E3848"
PUNK_TEXT_HEX = "#DDEEF2"
PUNK_MUTED_HEX = "#AFC3CB"
PUNK_BLUE_HEX = "#5BBFCF"
PUNK_PURPLE_HEX = "#A25DCE"
PUNK_ORANGE_HEX = "#CE985D"
PUNK_GREEN_HEX = "#87CE5D"
PUNK_RED_HEX = "#CE5D5D"
PUNK_BG = colors.HexColor(PUNK_BG_HEX)
PUNK_SECONDARY = colors.HexColor(PUNK_SECONDARY_HEX)
PUNK_SECONDARY_LIGHT = colors.HexColor(PUNK_SECONDARY_LIGHT_HEX)
PUNK_TEXT = colors.HexColor(PUNK_TEXT_HEX)
PUNK_MUTED = colors.HexColor(PUNK_MUTED_HEX)
PUNK_BLUE = colors.HexColor(PUNK_BLUE_HEX)
PUNK_PURPLE = colors.HexColor(PUNK_PURPLE_HEX)
PUNK_ORANGE = colors.HexColor(PUNK_ORANGE_HEX)
PUNK_GREEN = colors.HexColor(PUNK_GREEN_HEX)
PUNK_RED = colors.HexColor(PUNK_RED_HEX)
PUNK_WHITE = colors.white
PRINT_BG = colors.white
PRINT_TEXT = colors.HexColor("#132033")
PRINT_MUTED = colors.HexColor("#52616F")
PRINT_PANEL = colors.HexColor("#F5F8FA")
PRINT_PANEL_ALT = colors.HexColor("#EEF4F7")
PRINT_BORDER = colors.HexColor("#D8E3E8")
PRINT_CODE_BG = colors.HexColor("#F7FAFC")
PRINT_CODE_HIGHLIGHT = colors.HexColor("#E8F6E8")
RAINBOW_HEX = [PUNK_BLUE_HEX, PUNK_PURPLE_HEX, PUNK_ORANGE_HEX, PUNK_GREEN_HEX, PUNK_RED_HEX]
RAINBOW = [colors.HexColor(color) for color in RAINBOW_HEX]
CONTENT_WIDTH = 6.7 * inch
ISSUE_LABEL_WIDTH = 1.0 * inch
CODE_LINE_NUMBER_WIDTH = 0.62 * inch
FRAME_INNER_WIDTH = A4[0] - (2 * 0.65 * inch) - 12
CONTENT_RIGHT_INDENT = max(0, FRAME_INNER_WIDTH - CONTENT_WIDTH)


def _font_asset_path(filename: str) -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "fonts", filename))


def _register_pathway_extreme() -> str:
    font_path = _font_asset_path("PathwayExtreme.ttf")
    if not os.path.exists(font_path):
        logger.warning("Pathway Extreme font file missing, falling back to Helvetica")
        return "Helvetica"

    try:
        pdfmetrics.registerFont(TTFont("PathwayExtreme", font_path))
        return "PathwayExtreme"
    except Exception as e:
        logger.warning(f"Could not register Pathway Extreme font, falling back to Helvetica: {e}")
        return "Helvetica"


FONT_REGULAR = _register_pathway_extreme()
FONT_BOLD = FONT_REGULAR if FONT_REGULAR != "Helvetica" else "Helvetica-Bold"
FONT_MONO = "Courier"


class SaistDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        level = getattr(flowable, "_saist_toc_level", None)
        if level is not None:
            key = getattr(flowable, "_saist_toc_key", None)
            if key:
                self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))


@dataclass
class ReportLabPdf:
    _DEFAULT_OUTPUT_DIR = "reporting"

    llm: BaseLlmAdapter
    project: str
    findings: list[FindingContext]
    comment: str

    def run(self, args):
        pdf_path = os.path.join(self._DEFAULT_OUTPUT_DIR, args.pdf_filename)
        self.generated_at = datetime.datetime.now().isoformat(sep=" ", timespec="minutes")
        self.scm_adapter = self._scm_adapter_from_args(args)
        self.target = self._target_from_args(args)

        try:
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            doc = SaistDocTemplate(
                pdf_path,
                pagesize=A4,
                rightMargin=0.65 * inch,
                leftMargin=0.65 * inch,
                topMargin=0.65 * inch,
                bottomMargin=0.65 * inch,
                title=self._document_title(),
                author="SAIST",
            )
            doc.multiBuild(self._story(), onFirstPage=self._draw_page, onLaterPages=self._draw_page)
        except Exception as e:
            logger.error(f"Unable to write ReportLab PDF file to '{pdf_path}': {e}")
            exit(1)

        print(f"Written ReportLab PDF report to '{pdf_path}'")

    def _story(self) -> list:
        styles = self._styles()
        story = self._cover_story(styles)

        story.extend(
            [
                PageBreak(),
                Paragraph("Report contents", styles["Heading1"]),
                self._table_of_contents(styles),
                PageBreak(),
                self._toc_heading("Summary", styles["Heading1"], 0, "summary"),
                self._text_panel(self.comment or "No summary was generated.", styles),
                Spacer(1, 0.28 * inch),
                Paragraph("Issue summary", styles["Heading2"]),
                self._issue_summary_table(styles),
                PageBreak(),
                self._toc_heading("Issues", styles["Heading1"], 0, "issues"),
                Paragraph(
                    self._escaped(f"{len(self.findings)} issues reviewed with code context and remediation guidance."),
                    styles["Body"],
                ),
                Spacer(1, 0.18 * inch),
            ]
        )

        if not self.findings:
            story.append(self._text_panel("No issues were provided.", styles))
            return story

        for index, finding in enumerate(self.findings, start=1):
            if index > 1:
                story.append(PageBreak())

            story.extend(self._finding_story(index, finding, styles))

        return story

    def _cover_story(self, styles: dict[str, ParagraphStyle]) -> list:
        story = []
        logo_path = self._logo_path()
        if logo_path:
            logo = Image(logo_path, width=1.15 * inch, height=1.40 * inch)
            logo.hAlign = "CENTER"
            story.extend([Spacer(1, 0.25 * inch), logo, Spacer(1, 0.20 * inch)])
        else:
            story.append(Spacer(1, 0.70 * inch))

        story.extend(
            [
                Paragraph("Punk Security", styles["Title"]),
                Spacer(1, 0.12 * inch),
                Paragraph(self._cover_title_markup(), styles["CoverSubtitle"]),
                Spacer(1, 0.30 * inch),
                self._metadata_table(styles),
                Spacer(1, 0.18 * inch),
                self._disclaimer_panel(styles),
            ]
        )

        return story

    def _table_of_contents(self, styles: dict[str, ParagraphStyle]) -> TableOfContents:
        toc = TableOfContents()
        toc.levelStyles = [styles["TocLevel0"], styles["TocLevel1"]]
        toc.dotsMinLevel = 0
        return toc

    def _finding_story(self, index: int, finding: FindingContext, styles: dict[str, ParagraphStyle]) -> list:
        priority_label, priority_color = self._priority(finding.priority)
        metadata = [
            ["Priority", priority_label],
            ["CWE", finding.cwe or "Not specified"],
            ["File", finding.file],
            ["Line", str(finding.line_number)],
        ]

        table = Table(metadata, colWidths=[ISSUE_LABEL_WIDTH, CONTENT_WIDTH - ISSUE_LABEL_WIDTH], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), PRINT_PANEL_ALT),
                    ("BACKGROUND", (1, 1), (1, -1), PRINT_BG),
                    ("BACKGROUND", (1, 0), (1, 0), priority_color),
                    ("TEXTCOLOR", (0, 0), (0, -1), PRINT_MUTED),
                    ("TEXTCOLOR", (1, 1), (-1, -1), PRINT_TEXT),
                    ("TEXTCOLOR", (1, 0), (1, 0), PUNK_BG if priority_label in {"Low", "Medium"} else PUNK_WHITE),
                    ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, PRINT_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        return [
            Paragraph(self._escaped(f"ISSUE {index:02d}"), styles["Eyebrow"]),
            self._toc_heading(
                self._escaped(f"{finding.cwe} - {finding.file} - {finding.title}"),
                styles["Heading2"],
                1,
                f"issue-{index}",
            ),
            Spacer(1, 0.1 * inch),
            table,
            Spacer(1, 0.18 * inch),
            Paragraph("Issue", styles["Heading3"]),
            Spacer(1, 0.08 * inch),
            self._text_panel(finding.issue, styles),
            Spacer(1, 0.20 * inch),
            Paragraph("Recommendation", styles["Heading3"]),
            Spacer(1, 0.08 * inch),
            self._text_panel(finding.recommendation or "Not applicable.", styles),
            Spacer(1, 0.18 * inch),
            Paragraph("Affected code", styles["Heading3"]),
            self._context_table(finding, styles),
        ]

    def _styles(self) -> dict[str, ParagraphStyle]:
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="Project",
                parent=styles["Heading2"],
                alignment=TA_CENTER,
                textColor=PUNK_WHITE,
                spaceAfter=12,
            )
        )
        styles.add(
            ParagraphStyle(
                name="MutedCenter",
                parent=styles["BodyText"],
                alignment=TA_CENTER,
                textColor=PUNK_MUTED,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Eyebrow",
                parent=styles["BodyText"],
                fontSize=8,
                leading=10,
                textColor=PUNK_SECONDARY,
                fontName=FONT_BOLD,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="EyebrowCenter",
                parent=styles["Eyebrow"],
                alignment=TA_CENTER,
                textColor=PUNK_GREEN,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CoverSubtitle",
                parent=styles["BodyText"],
                alignment=TA_CENTER,
                textColor=PUNK_TEXT,
                fontName=FONT_BOLD,
                fontSize=20,
                leading=26,
            )
        )
        styles.add(
            ParagraphStyle(
                name="Body",
                parent=styles["BodyText"],
                leading=14,
                textColor=PRINT_TEXT,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CodeLine",
                parent=styles["Code"],
                fontName=FONT_MONO,
                fontSize=6.8,
                leading=8,
                textColor=PRINT_TEXT,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CodeNumber",
                parent=styles["CodeLine"],
                textColor=PRINT_MUTED,
                alignment=TA_CENTER,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CodeLineHighlight",
                parent=styles["CodeLine"],
                textColor=PRINT_TEXT,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CodeNumberHighlight",
                parent=styles["CodeNumber"],
                textColor=PRINT_TEXT,
                fontName=FONT_MONO,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PanelLabel",
                parent=styles["Eyebrow"],
                textColor=PUNK_SECONDARY,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PanelBody",
                parent=styles["Body"],
                backColor=PRINT_PANEL,
                borderColor=PRINT_BORDER,
                borderWidth=0.4,
                borderPadding=8,
                rightIndent=CONTENT_RIGHT_INDENT,
                leading=14,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="MetadataLabel",
                parent=styles["BodyText"],
                fontName=FONT_BOLD,
                fontSize=8,
                leading=10,
                textColor=PUNK_GREEN,
            )
        )
        styles.add(
            ParagraphStyle(
                name="MetadataValue",
                parent=styles["BodyText"],
                fontSize=9,
                leading=11,
                textColor=PUNK_TEXT,
                spaceAfter=0,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CoverDisclaimerLabel",
                parent=styles["MetadataLabel"],
                fontSize=8,
                leading=10,
                textColor=PUNK_ORANGE,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CoverDisclaimer",
                parent=styles["BodyText"],
                fontSize=8.5,
                leading=11,
                textColor=PUNK_MUTED,
                spaceAfter=0,
            )
        )
        styles.add(
            ParagraphStyle(
                name="TocLevel0",
                parent=styles["BodyText"],
                fontName=FONT_BOLD,
                fontSize=11,
                leading=15,
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=8,
                textColor=PUNK_SECONDARY,
            )
        )
        styles.add(
            ParagraphStyle(
                name="TocLevel1",
                parent=styles["TocLevel0"],
                fontName=FONT_REGULAR,
                fontSize=9,
                leading=12,
                leftIndent=18,
                firstLineIndent=0,
                spaceBefore=4,
                textColor=PRINT_MUTED,
            )
        )
        styles.add(
            ParagraphStyle(
                name="IssueSummaryHeader",
                parent=styles["BodyText"],
                fontName=FONT_BOLD,
                fontSize=9,
                leading=11,
                textColor=PUNK_WHITE,
            )
        )
        styles.add(
            ParagraphStyle(
                name="IssueSummaryCell",
                parent=styles["Body"],
                fontSize=9,
                leading=11,
                textColor=PRINT_TEXT,
                spaceAfter=0,
            )
        )
        styles.add(
            ParagraphStyle(
                name="IssueSummaryId",
                parent=styles["IssueSummaryCell"],
                fontName=FONT_BOLD,
                textColor=PUNK_SECONDARY,
            )
        )
        styles.add(
            ParagraphStyle(
                name="IssueSummarySeverity",
                parent=styles["IssueSummaryCell"],
                alignment=TA_CENTER,
                fontName=FONT_BOLD,
            )
        )

        styles["Title"].alignment = TA_CENTER
        styles["Title"].fontSize = 28
        styles["Title"].leading = 32
        styles["Title"].textColor = PUNK_WHITE
        styles["Title"].fontName = FONT_BOLD
        styles["BodyText"].fontName = FONT_REGULAR
        styles["Heading1"].fontName = FONT_BOLD
        styles["Heading2"].fontName = FONT_BOLD
        styles["Heading3"].fontName = FONT_BOLD
        styles["Heading1"].textColor = PUNK_SECONDARY
        styles["Heading2"].textColor = PUNK_SECONDARY
        styles["Heading3"].textColor = PUNK_SECONDARY
        styles["Heading1"].spaceBefore = 12
        styles["Heading1"].spaceAfter = 10
        styles["Heading2"].spaceBefore = 8
        styles["Heading2"].spaceAfter = 8
        styles["Heading3"].spaceBefore = 6
        styles["Heading3"].spaceAfter = 4

        return styles

    @staticmethod
    def _toc_heading(text: str, style: ParagraphStyle, level: int, key: str) -> Paragraph:
        paragraph = Paragraph(text, style)
        paragraph._saist_toc_level = level
        paragraph._saist_toc_key = key
        return paragraph

    def _document_title(self) -> str:
        if self.project:
            return f"SAIST report - {self.project}"
        return "SAIST report"

    def _cover_title_markup(self) -> str:
        if self.project:
            project_line = self._escaped(self.project)
            return f"AI generated code review of<br/>{project_line}<br/>by {self._rainbow_saist_markup()}"
        return f"AI generated code review<br/>by {self._rainbow_saist_markup()}"

    @staticmethod
    def _rainbow_saist_markup() -> str:
        return "".join(f'<font color="{color}">{letter}</font>' for letter, color in zip("SAIST", RAINBOW_HEX))

    def _model_text(self) -> str:
        parts = [self.llm.model_vendor, self.llm.model_name]
        return ": ".join(part for part in parts if part)

    @staticmethod
    def _scm_adapter_from_args(args) -> str:
        return getattr(args, "SCM", None) or "Not specified"

    @staticmethod
    def _target_from_args(args) -> str:
        scm = getattr(args, "SCM", None)

        if scm in {"filesystem", "git"}:
            return getattr(args, "path", None) or "Not specified"

        if scm == "github":
            repository = getattr(args, "repository", None)
            pr = getattr(args, "pr", None)
            if repository and pr:
                return f"{repository} pull request #{pr}"
            return repository or "Not specified"

        return getattr(args, "path", None) or getattr(args, "repository", None) or "Not specified"

    def _disclaimer_panel(self, styles: dict[str, ParagraphStyle]) -> Table:
        table = Table(
            [
                [Paragraph("Disclaimer", styles["CoverDisclaimerLabel"])],
                [
                    Paragraph(
                        """
                        This report has not been created by the expert testing team at Punk Security. 
                        
                        It is created by SAIST, an open-source tool developed by Punk Security that uses AI to analyze code and generate findings. The findings and recommendations in this report are generated by an AI model based on the input provided to SAIST.
                        """,
                        styles["CoverDisclaimer"],
                    )
                ],
            ],
            colWidths=[CONTENT_WIDTH],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PUNK_BG),
                    ("BOX", (0, 0), (-1, -1), 0.45, PUNK_SECONDARY_LIGHT),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.0, PUNK_ORANGE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                    ("TOPPADDING", (0, 1), (-1, 1), 0),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ]
            )
        )
        return table

    def _metadata_table(self, styles: dict[str, ParagraphStyle]) -> Table:
        rows = [
            ["Date", getattr(self, "generated_at", "Not specified")],
            ["Model", self._model_text() or "Not specified"],
            ["SCM adapter", getattr(self, "scm_adapter", "Not specified")],
            ["Target", getattr(self, "target", "Not specified")],
        ]
        table_rows = [
            [
                Paragraph(self._escaped(label), styles["MetadataLabel"]),
                Paragraph(self._escaped(value), styles["MetadataValue"]),
            ]
            for label, value in rows
        ]

        table = Table(table_rows, colWidths=[1.35 * inch, 5.35 * inch], hAlign="LEFT")
        table_style = [
            ("BACKGROUND", (0, 0), (-1, -1), PUNK_BG),
            ("BOX", (0, 0), (-1, -1), 0.45, PUNK_SECONDARY_LIGHT),
            ("LINEABOVE", (0, 0), (-1, 0), 1.0, PUNK_BLUE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, -1), 12),
            ("RIGHTPADDING", (0, 0), (0, -1), 8),
            ("LEFTPADDING", (1, 0), (1, -1), 4),
            ("RIGHTPADDING", (1, 0), (1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
        for row_index in range(len(table_rows) - 1):
            table_style.append(("LINEBELOW", (0, row_index), (-1, row_index), 0.25, PUNK_SECONDARY_LIGHT))
        table.setStyle(TableStyle(table_style))
        return table

    def _issue_summary_table(self, styles: dict[str, ParagraphStyle]) -> Table:
        rows = [
            [
                Paragraph("Issue ID", styles["IssueSummaryHeader"]),
                Paragraph("Title", styles["IssueSummaryHeader"]),
                Paragraph("Severity", styles["IssueSummaryHeader"]),
            ]
        ]

        for index, finding in enumerate(self.findings, start=1):
            severity, severity_color = self._priority(finding.priority)
            rows.append(
                [
                    Paragraph(self._escaped(f"ISSUE {index:02d}"), styles["IssueSummaryId"]),
                    Paragraph(self._escaped(finding.title), styles["IssueSummaryCell"]),
                    Paragraph(self._escaped(severity), styles["IssueSummarySeverity"]),
                ]
            )

        if len(rows) == 1:
            rows.append(
                [
                    Paragraph("-", styles["IssueSummaryCell"]),
                    Paragraph("No issues were provided.", styles["IssueSummaryCell"]),
                    Paragraph("-", styles["IssueSummaryCell"]),
                ]
            )

        table = Table(rows, colWidths=[1.1 * inch, 4.35 * inch, 1.25 * inch], hAlign="LEFT", repeatRows=1)
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), PUNK_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), PUNK_WHITE),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("BACKGROUND", (0, 1), (-1, -1), PRINT_BG),
            ("GRID", (0, 0), (-1, -1), 0.25, PRINT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]

        for row_index, finding in enumerate(self.findings, start=1):
            _, severity_color = self._priority(finding.priority)
            if row_index % 2 == 0:
                table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), PRINT_PANEL))
            table_style.extend(
                [
                    ("BACKGROUND", (2, row_index), (2, row_index), severity_color),
                    ("TEXTCOLOR", (2, row_index), (2, row_index), PUNK_BG if finding.priority <= 7 else PUNK_WHITE),
                ]
            )

        table.setStyle(TableStyle(table_style))
        return table

    def _text_panel(self, text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
        return Paragraph(self._paragraph_markup(text), styles["PanelBody"])

    def _context_table(self, finding: FindingContext, styles: dict[str, ParagraphStyle]) -> Table:
        lines = finding.context.splitlines() if finding.context else [""]
        rows = []

        for offset, line in enumerate(lines):
            line_number = finding.context_start + offset
            highlighted = line_number == finding.line_number
            rows.append(
                [
                    str(line_number),
                    XPreformatted(self._escaped(line) or " ", styles["CodeLineHighlight" if highlighted else "CodeLine"]),
                ]
            )

        table = Table(rows, colWidths=[CODE_LINE_NUMBER_WIDTH, CONTENT_WIDTH - CODE_LINE_NUMBER_WIDTH], hAlign="LEFT", repeatRows=0)
        table_style = [
            ("BACKGROUND", (0, 0), (-1, -1), PRINT_CODE_BG),
            ("BACKGROUND", (0, 0), (0, -1), PRINT_PANEL_ALT),
            ("GRID", (0, 0), (-1, -1), 0.2, PRINT_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (0, -1), FONT_MONO),
            ("FONTSIZE", (0, 0), (0, -1), 6.8),
            ("LEADING", (0, 0), (0, -1), 8),
            ("TEXTCOLOR", (0, 0), (0, -1), PRINT_MUTED),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]

        for index, _ in enumerate(lines):
            line_number = finding.context_start + index
            if line_number == finding.line_number:
                table_style.extend(
                    [
                        ("BACKGROUND", (0, index), (-1, index), colors.HexColor("#1D3A2A")),
                        ("BACKGROUND", (0, index), (-1, index), PRINT_CODE_HIGHLIGHT),
                        ("TEXTCOLOR", (0, index), (-1, index), PRINT_TEXT),
                        ("FONTNAME", (0, index), (0, index), "Courier-Bold"),
                    ]
                )

        table.setStyle(TableStyle(table_style))
        return table

    @staticmethod
    def _logo_path() -> str | None:
        path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "assets",
                "PunkSecurityLogo.png",
            )
        )
        return path if os.path.exists(path) else None

    @staticmethod
    def _draw_page(canvas, doc):
        width, height = A4
        canvas.saveState()
        page_is_cover = doc.page == 1
        canvas.setFillColor(PUNK_SECONDARY if page_is_cover else PRINT_BG)
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.setFillColor(PUNK_SECONDARY)
        canvas.rect(0, height - 0.38 * inch, width, 0.38 * inch, stroke=0, fill=1)
        ReportLabPdf._draw_rainbow_bar(canvas, width, height - 0.40 * inch)

        if not page_is_cover:
            canvas.setFillColor(PUNK_WHITE)
            canvas.setFont(FONT_REGULAR, 8)
            canvas.drawString(0.65 * inch, height - 0.25 * inch, "SAIST AI generated code review")
            canvas.drawRightString(width - 0.65 * inch, 0.35 * inch, f"Page {doc.page}")
            ReportLabPdf._draw_rainbow_bar(canvas, width, 0.22 * inch)

        canvas.restoreState()

    @staticmethod
    def _draw_rainbow_bar(canvas, width: float, y: float):
        segment_width = width / len(RAINBOW)
        for index, color in enumerate(RAINBOW):
            canvas.setFillColor(color)
            canvas.rect(index * segment_width, y, segment_width + 1, 0.035 * inch, stroke=0, fill=1)

    @staticmethod
    def _escaped(value) -> str:
        return escape(str(value or ""))

    def _paragraph_markup(self, value: str) -> str:
        escaped = self._escaped(value)
        return escaped.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")

    @staticmethod
    def _priority(priority: int):
        if priority > 8:
            return "Critical", PUNK_RED
        if priority > 7:
            return "High", PUNK_RED
        if priority > 4:
            return "Medium", PUNK_ORANGE
        return "Low", PUNK_BLUE
