"""
extract.py — BƯỚC 1 & 2 của pipeline: PDF -> chữ -> CV có cấu trúc.

Luồng:
    file PDF  --(pymupdf4llm)-->  văn bản Markdown
    văn bản   --(Gemini + schema)-->  từng phần CV (basics, work, education, skills, projects)

Ta trích xuất TỪNG PHẦN bằng một prompt riêng cho mỗi phần. Vì sao không hỏi 1 lần cho cả CV?
  - Mỗi prompt tập trung 1 việc -> model ít nhầm, kết quả sạch hơn.
  - Đây cũng là cách bản gốc hiring-agent làm. Dễ mở rộng (thêm phần 'awards'...).
"""

from datetime import datetime

import pymupdf
import pymupdf4llm

import llm
from models import Resume
from prompts.template_manager import TemplateManager

_tm = TemplateManager()

# "Luật chơi" chung cho mọi lần trích xuất. Nhắc model chỉ lấy thông tin CÓ THẬT
# trong CV, không bịa. Structured output đã lo phần định dạng JSON giúp ta rồi.
EXTRACTION_SYSTEM = (
    "Bạn là công cụ trích xuất thông tin từ CV. "
    "Chỉ lấy dữ liệu THỰC SỰ xuất hiện trong CV, tuyệt đối không bịa thêm. "
    "Nếu một trường không có trong CV thì để trống (null). "
    f"Ngày hiện tại là {datetime.now().date().isoformat()}. "
    "Nếu endDate là Present/trống/tương lai, giữ nguyên để code xác định đang học; "
    "không tự điền ngày tốt nghiệp dự kiến."
)


def pdf_to_text(pdf_path: str) -> str:
    """Bước 1: đọc text Markdown và giữ lại các hyperlink có trong PDF."""
    text = pymupdf4llm.to_markdown(pdf_path)

    # pymupdf4llm giữ nhãn liên kết (ví dụ "GitHub") nhưng có thể bỏ URI đích.
    # Đưa các URI thật vào context để bước trích xuất không đánh mất chúng.
    document = pymupdf.open(pdf_path)
    try:
        links = []
        for page in document:
            for link in page.get_links():
                uri = link.get("uri", "")
                if uri.startswith(("http://", "https://")) and uri not in links:
                    links.append(uri)
    finally:
        document.close()

    if links:
        text += "\n\n## Các liên kết trong CV\n" + "\n".join(f"- {link}" for link in links)

    return text


def extract_resume(cv_text: str, *, model=None, fallback_model=None, allow_fallback=None) -> Resume:
    """
    Bước 2: từ văn bản CV, gọi Gemini trích xuất từng phần rồi gom thành 1 Resume.

    Mỗi phần dùng:
      - 1 file prompt .jinja (câu nói với AI)
      - 1 schema (khuôn dữ liệu mong muốn) truyền cho Gemini
    """
    print("   • Trích xuất toàn bộ CV (basics, work, education, skills, projects, awards)...")
    return llm.ask_json(
        EXTRACTION_SYSTEM, _tm.render("resume", text_content=cv_text), Resume,
        model=model, fallback_model=fallback_model, allow_fallback=allow_fallback, phase="extraction"
    )


def resume_to_text(resume: Resume) -> str:
    """
    Biến Resume (đã có cấu trúc) trở lại thành văn bản gọn gàng để đưa vào bước chấm điểm.
    Vì sao lại đổi ngược ra text? Vì bước chấm điểm chỉ cần "đọc hiểu" toàn bộ CV,
    một đoạn text sạch sẽ, đã chuẩn hoá thì dễ cho model hơn PDF thô ban đầu.
    """
    lines = []
    b = resume.basics
    if b:
        lines.append(f"# {b.name or 'Ứng viên'}")
        contacts = " | ".join(
            value for value in (b.email, b.phone, b.linkedin, b.location) if value
        )
        if contacts:
            lines.append(f"Liên hệ: {contacts}")
        if b.summary:
            lines.append(f"Giới thiệu: {b.summary}")

    if resume.work:
        lines.append("\n## Kinh nghiệm làm việc")
        for w in resume.work:
            when = f"{w.startDate or '?'} - {w.endDate or '?'}"
            lines.append(f"- {w.position or ''} @ {w.company or ''} ({when})")
            if w.summary:
                lines.append(f"  {w.summary}")

    if resume.education:
        lines.append("\n## Học vấn")
        for e in resume.education:
            lines.append(
                f"- {e.studyType or ''} {e.area or ''} — {e.institution or ''} ({e.startDate or '?'} - {e.endDate or 'Present'})"
            )

    if resume.skills:
        lines.append("\n## Kỹ năng")
        for s in resume.skills:
            kws = ", ".join(s.keywords or [])
            lines.append(f"- {s.name or ''}: {kws}")

    if resume.projects:
        lines.append("\n## Dự án")
        for p in resume.projects:
            techs = ", ".join(p.technologies or [])
            link = f" [{p.url}]" if p.url else " (không có link)"
            lines.append(f"- {p.name or ''}{link}: {p.description or ''}")
            if techs:
                lines.append(f"  Công nghệ: {techs}")

    if resume.awards:
        lines.append("\n## Giải thưởng và thành tích")
        for award in resume.awards:
            details = " — ".join(
                part for part in (award.issuer, award.date) if part
            )
            label = f"{award.title or ''} ({details})" if details else award.title or ''
            lines.append(f"- {label}: {award.description or ''}")

    return "\n".join(lines)
