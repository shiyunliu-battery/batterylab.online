import argparse
import json
import pathlib
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def resolve_font_family() -> dict[str, str]:
    candidates = [
        (
            "TimesNewRoman",
            pathlib.Path("C:/Windows/Fonts/times.ttf"),
            pathlib.Path("C:/Windows/Fonts/timesbd.ttf"),
        ),
        (
            "LiberationSerif",
            pathlib.Path("C:/Windows/Fonts/LiberationSerif-Regular.ttf"),
            pathlib.Path("C:/Windows/Fonts/LiberationSerif-Bold.ttf"),
        ),
        (
            "DejaVuSerif",
            pathlib.Path("C:/Windows/Fonts/DejaVuSerif.ttf"),
            pathlib.Path("C:/Windows/Fonts/DejaVuSerif-Bold.ttf"),
        ),
    ]

    for family_name, regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            regular_font = f"{family_name}-Regular"
            bold_font = f"{family_name}-Bold"
            if regular_font not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(regular_font, str(regular_path)))
            if bold_font not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bold_font, str(bold_path)))
            return {"regular": regular_font, "bold": bold_font}

    return {"regular": "Times-Roman", "bold": "Times-Bold"}


def normalize_text(value: str) -> str:
    return (
        str(value or "")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2015", "-")
        .replace("\u2212", "-")
        .replace("\u00a0", " ")
    )


def paragraph_text(value: str) -> str:
    normalized = normalize_text(value).strip()
    return escape(normalized)


def build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    text_color = HexColor("#172026")
    muted_color = HexColor("#4C5A63")
    fonts = resolve_font_family()

    return {
        "title": ParagraphStyle(
            "ExperimentPlanTitle",
            parent=sample["Title"],
            fontName=fonts["bold"],
            fontSize=16,
            leading=20,
            textColor=text_color,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "heading1": ParagraphStyle(
            "ExperimentPlanHeading1",
            parent=sample["Heading1"],
            fontName=fonts["bold"],
            fontSize=13,
            leading=16,
            textColor=text_color,
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "heading2": ParagraphStyle(
            "ExperimentPlanHeading2",
            parent=sample["Heading2"],
            fontName=fonts["bold"],
            fontSize=11.5,
            leading=14,
            textColor=text_color,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "heading3": ParagraphStyle(
            "ExperimentPlanHeading3",
            parent=sample["Heading3"],
            fontName=fonts["bold"],
            fontSize=11,
            leading=13.5,
            textColor=text_color,
            alignment=TA_LEFT,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "ExperimentPlanBody",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=11,
            leading=15,
            textColor=text_color,
            alignment=TA_LEFT,
            spaceBefore=0,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "ExperimentPlanBullet",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=11,
            leading=15,
            textColor=text_color,
            leftIndent=16,
            firstLineIndent=0,
            spaceBefore=0,
            spaceAfter=4,
        ),
        "reference": ParagraphStyle(
            "ExperimentPlanReference",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=10.5,
            leading=14,
            textColor=text_color,
            leftIndent=18,
            firstLineIndent=-18,
            spaceBefore=0,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "ExperimentPlanFooter",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9,
            leading=10.5,
            textColor=muted_color,
            alignment=TA_LEFT,
        ),
    }


def add_footer(canvas, doc) -> None:
    canvas.saveState()
    footer_font = resolve_font_family()["regular"]
    canvas.setFont(footer_font, 8.5)
    canvas.setFillColor(HexColor("#5B6870"))
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin,
        10 * mm,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def build_story(payload: dict[str, Any], available_width: float) -> list[Any]:
    title = paragraph_text(payload.get("title") or "Experiment Plan")
    blocks = payload.get("blocks") or []
    styles = build_styles()
    fonts = resolve_font_family()
    story: list[Any] = [Paragraph(title, styles["title"]), Spacer(1, 4)]

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = str(block.get("type") or "paragraph").strip().lower()
        text = paragraph_text(str(block.get("text") or ""))
        if not text:
            continue

        if block_type == "heading1":
            story.append(Paragraph(text, styles["heading1"]))
            continue
        if block_type == "heading2":
            story.append(Paragraph(text, styles["heading2"]))
            continue
        if block_type == "heading3":
            story.append(Paragraph(text, styles["heading3"]))
            continue
        if block_type in {"bullet", "numbered"}:
            marker = normalize_text(str(block.get("marker") or "-")).strip() or "-"
            story.append(
                Paragraph(paragraph_text(f"{marker} {str(block.get('text') or '')}"), styles["bullet"])
            )
            continue
        if block_type == "reference":
            marker = normalize_text(str(block.get("marker") or "")).strip()
            reference_text = normalize_text(str(block.get("text") or "")).strip()
            story.append(
                Paragraph(
                    paragraph_text(f"{marker} {reference_text}".strip()),
                    styles["reference"],
                )
            )
            continue
        if block_type == "table":
            headers = block.get("headers") if isinstance(block.get("headers"), list) else []
            rows = block.get("rows") if isinstance(block.get("rows"), list) else []
            if headers:
                table_rows = [[Paragraph(paragraph_text(str(cell or "")), styles["body"]) for cell in headers]]
                for row in rows:
                    if not isinstance(row, list):
                        continue
                    padded_row = list(row[: len(headers)])
                    while len(padded_row) < len(headers):
                        padded_row.append("")
                    table_rows.append(
                        [
                            Paragraph(paragraph_text(str(cell or "")), styles["body"])
                            for cell in padded_row
                        ]
                    )
                column_count = max(len(headers), 1)
                col_width = available_width / column_count
                table = Table(
                    table_rows,
                    repeatRows=1,
                    hAlign="LEFT",
                    colWidths=[col_width] * column_count,
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F4F1EB")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#172026")),
                            ("FONTNAME", (0, 0), (-1, 0), fonts["bold"]),
                            ("FONTNAME", (0, 1), (-1, -1), fonts["regular"]),
                            ("FONTSIZE", (0, 0), (-1, -1), 10.2),
                            ("LEADING", (0, 0), (-1, -1), 12.8),
                            ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#D5D9DD")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#FBFAF8")]),
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 8))
            continue

        story.append(Paragraph(text, styles["body"]))

    return story


def render_pdf(input_path: pathlib.Path, output_path: pathlib.Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=normalize_text(str(payload.get("title") or "Experiment Plan")),
        author="Battery Lab Assistant",
    )

    story = build_story(payload, doc.width)
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an experiment plan PDF.")
    parser.add_argument("--input", required=True, help="Path to the JSON payload.")
    parser.add_argument("--output", required=True, help="Path to the output PDF.")
    args = parser.parse_args()

    render_pdf(pathlib.Path(args.input), pathlib.Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
