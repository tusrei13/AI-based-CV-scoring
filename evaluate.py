"""
evaluate.py — BƯỚC 3 của pipeline: chấm điểm ứng viên.

Đưa toàn bộ CV (dạng text đã chuẩn hoá) + bộ tiêu chí cho Gemini, yêu cầu trả về
điểm từng nhóm KÈM bằng chứng (evidence). "Kèm bằng chứng" chính là điểm mấu chốt:
model không chỉ phun ra con số mà phải giải thích vì sao — nên kết quả kiểm chứng được.

Khác bản gốc: bản này BỎ phần đọc dữ liệu GitHub. Chỉ chấm dựa trên nội dung CV.
"""

import llm
from datetime import datetime

from models import Evaluation, JobDescription
from scoring import invalid_quotes, unsupported_skills
from prompts.template_manager import TemplateManager

_tm = TemplateManager()


def analyze_job_description(job_description: str, *, model=None, fallback_model=None, allow_fallback=None) -> JobDescription:
    if not job_description.strip():
        return JobDescription(level="Fresher")
    return llm.ask_json(
        "Bạn là chuyên viên tuyển dụng. Chỉ trích xuất yêu cầu thực sự có trong JD, không thêm yêu cầu.",
        _tm.render("job_description", job_description=job_description),
        JobDescription,
        model=model, fallback_model=fallback_model, allow_fallback=allow_fallback, phase="jd",
    )


def evaluate_resume(cv_text: str, job_description: str = "", *, resume=None, job: JobDescription | None = None, evidence_text: str | None = None, model=None, fallback_model=None, allow_fallback=None) -> Evaluation:
    """Chấm CV; tổng điểm, cap và coverage được tính lại bằng code ở main/scoring."""
    job = job or analyze_job_description(job_description, model=model, fallback_model=fallback_model, allow_fallback=allow_fallback)
    unsupported = unsupported_skills(resume) if resume else []
    system_prompt = _tm.render("evaluation_system", today=datetime.now().date().isoformat())
    user_prompt = _tm.render(
        "evaluation_criteria",
        text_content=cv_text,
        job_description=job.model_dump_json(indent=2),
        unsupported_skills=unsupported or ["Không xác định"],
        today=datetime.now().date().isoformat(),
    )
    evaluation = llm.ask_json(system_prompt, user_prompt, Evaluation, model=model, fallback_model=fallback_model, allow_fallback=allow_fallback, phase="evaluation")
    quote_source = evidence_text or cv_text
    bad_quotes = invalid_quotes(evaluation, quote_source)
    if bad_quotes:
        feedback = "Các quote sau không xuất hiện nguyên văn trong CV, hãy thay bằng quote hợp lệ: " + " | ".join(bad_quotes)
        retry_prompt = user_prompt + "\n\nPHẢN HỒI VALIDATION:\n" + feedback
        evaluation = llm.ask_json(system_prompt, retry_prompt, Evaluation, model=model, fallback_model=fallback_model, allow_fallback=allow_fallback, phase="evaluation-retry")
        remaining_invalid = invalid_quotes(evaluation, quote_source)
        if remaining_invalid:
            for category in evaluation.scores.model_dump().keys():
                item = getattr(evaluation.scores, category)
                item.evidence_quotes = [quote for quote in item.evidence_quotes if quote not in remaining_invalid]
                item.confidence = "low"
                item.gaps.append("Có quote không khớp văn bản CV sau lần retry")
    return evaluation
