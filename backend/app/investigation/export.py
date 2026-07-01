import io
import json
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|bearer|token|secret)\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
)


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: sanitize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def export_case_json(case_payload: dict[str, Any]) -> bytes:
    sanitized = sanitize_payload(case_payload)
    return json.dumps(sanitized, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def export_case_pdf(case_payload: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = styles["BodyText"]

    story = [
        Paragraph("BotHunter AI — Investigation Case", title_style),
        Spacer(1, 0.3 * cm),
        Paragraph(
            f"Case ID: {case_payload.get('id', '—')}<br/>"
            f"Channel: {case_payload.get('channel_title', '—')}<br/>"
            f"Status: {case_payload.get('status', '—')}",
            body_style,
        ),
    ]

    decision_flow = case_payload.get("decision_flow") or {}
    if decision_flow:
        story.extend(
            [
                Paragraph("Decision Flow", section_style),
                Paragraph(
                    "Rule Engine → "
                    f"{decision_flow.get('rule_engine_decision', '—')} → "
                    f"AI → {decision_flow.get('ai_decision', '—')} → "
                    f"Final → {decision_flow.get('final_decision', '—')} → "
                    f"Human → {decision_flow.get('human_decision', '—')}",
                    body_style,
                ),
            ]
        )

    timeline = case_payload.get("timeline") or []
    if timeline:
        story.append(Paragraph("Timeline", section_style))
        rows = [["Stage", "Time", "Duration", "Result"]]
        for item in timeline:
            rows.append(
                [
                    str(item.get("title") or item.get("stage") or "—"),
                    str(item.get("timestamp") or "—"),
                    f"{item.get('duration_ms')} ms" if item.get("duration_ms") is not None else "—",
                    str(item.get("result") or "—"),
                ]
            )
        table = Table(rows, colWidths=[5 * cm, 4 * cm, 3 * cm, 5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)

    rules = case_payload.get("rule_inspection") or []
    if rules:
        story.append(Paragraph("Rule Inspector", section_style))
        for rule in rules:
            matched = "Matched" if rule.get("matched") else "Not matched"
            story.append(
                Paragraph(
                    f"<b>{rule.get('rule')}</b> — {matched} "
                    f"(+{rule.get('contribution', 0)})<br/>"
                    f"Condition: {rule.get('condition')}<br/>"
                    f"{rule.get('description')}",
                    body_style,
                )
            )
            story.append(Spacer(1, 0.15 * cm))

    doc.build(story)
    return buffer.getvalue()
