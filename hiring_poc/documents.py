"""Editable text report and escaped, printable HTML. No extra office runtime."""
from html import escape

from .analysis import JobAnalysis


def create_report(job: JobAnalysis, mode_label: str, notes: str = "") -> str:
    lines = ["채용 공고 분석 보고서", "=" * 32, "", f"분석 방식: {mode_label}", ""]
    for label, key in [("회사", "company"), ("직무", "role"), ("근무지", "location"),
                       ("고용형태", "employment_type"), ("경력", "experience"), ("마감일", "deadline")]:
        lines.append(f"{label}: {getattr(job, key) or '공고에 명시되지 않음'}")
    for title, items in [("주요 업무", job.responsibilities), ("필수 조건", job.required),
                         ("우대 사항", job.preferred), ("전형 절차", job.process)]:
        lines.extend(["", title, "-" * 24])
        if not items:
            lines.append("공고에서 확인하지 못했습니다.")
        for item in items:
            lines.extend([f"• {item.item}", f"  원문 근거: {item.evidence}"])
    lines.extend(["", "추가 확인 사항", "-" * 24])
    lines.extend(f"□ {item}" for item in job.missing_information)
    if not job.missing_information:
        lines.append("분석 결과에 별도 누락 항목이 없습니다. 원문과 대조해 주세요.")
    if notes.strip():
        lines.extend(["", "작성자 메모", "-" * 24, notes.strip()])
    return "\n".join(lines)


def report_html(title: str, body: str) -> bytes:
    # All user/model content is escaped; never render it as executable HTML.
    return ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
            f"<title>{escape(title)}</title><body><h1>{escape(title)}</h1>"
            f"<pre style='white-space:pre-wrap;font:16px/1.8 sans-serif'>{escape(body)}</pre>"
            "</body></html>").encode("utf-8")
