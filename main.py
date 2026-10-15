"""CLI cho pipeline đọc PDF -> extraction -> phân tích JD -> đánh giá."""

import argparse
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import config
import evaluate
import extract
import llm
from models import Evaluation, INTERN_RUBRIC
from scoring import band_for_score, education_status, finalize_scores, median_scores, rubric_for_level, unsupported_skills, validate_quotes


CATEGORY_LABELS = {
    "job_fit": "🎯 Độ phù hợp JD",
    "practical_experience_projects": "🧪 Dự án & kinh nghiệm thực tế",
    "technical_skills": "💻 Kỹ năng",
    "education": "🎓 Học vấn",
    "languages": "🌍 Ngoại ngữ",
    "credibility": "🔎 Nhất quán & độ tin cậy",
    "presentation": "📄 Trình bày",
    "potential_soft_skills": "🤝 Tiềm năng & soft skills",
    "work_experience": "🏢 Kinh nghiệm làm việc",
    "projects_portfolio": "🚀 Dự án/GitHub/OSS",
    "education_certifications": "🎓 Học vấn & chứng chỉ",
    "soft_skills": "🤝 Soft skills",
}


def _cache_file(pdf_text: str) -> Path:
    digest = hashlib.sha256(pdf_text.encode("utf-8")).hexdigest()
    return Path(config.CACHE_DIR) / f"extraction-{digest}.json"


def load_or_extract(pdf_text: str, no_cache: bool, *, model=None, fallback_model=None, allow_fallback=None):
    path = _cache_file(pdf_text)
    if not no_cache and path.exists():
        try:
            from models import Resume
            print(f"   -> dùng extraction cache: {path.name}")
            return Resume.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    resume = extract.extract_resume(pdf_text, model=model, fallback_model=fallback_model, allow_fallback=allow_fallback)
    if not no_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resume.model_dump_json(indent=2), encoding="utf-8")
    return resume


def apply_caps(values: dict, resume, cv_text: str):
    skills = [keyword for group in (resume.skills or []) for keyword in (group.keywords or [])]
    unsupported = unsupported_skills(resume)
    if len(skills) >= 25 or (skills and len(unsupported) / len(skills) > 0.4):
        if "technical_skills" in values:
            values["technical_skills"]["score"] = min(values["technical_skills"]["score"], values["technical_skills"]["max"] * 0.7)
            values["technical_skills"]["gaps"].append("Skills dàn trải hoặc thiếu bằng chứng trong dự án/công việc")
    all_text = cv_text.lower()
    unverified_metric = any(word in all_text for word in ("simulated", "internal test", "synthetic", "mô phỏng", "test set nội bộ"))
    if unverified_metric:
        for key in ("practical_experience_projects", "projects_portfolio"):
            if key in values:
                values[key]["score"] = min(values[key]["score"], values[key]["max"] * 0.85)
        if "credibility" in values:
            values["credibility"]["score"] = min(values["credibility"]["score"], values["credibility"]["max"] * 0.8)
    return values, unsupported


def build_payload(resume, evaluation: Evaluation, job, cv_text: str, evaluations: list[Evaluation]):
    total, values, warnings = finalize_scores(evaluation, job.level, evaluation.coverage)
    values, unsupported = apply_caps(values, resume, cv_text)
    total = round(min(100.0, sum(item["score"] for item in values.values())), 1)
    status, education_gaps = education_status(resume.education)
    derived_gaps = list(education_gaps)
    derived_flags = []
    if not resume.work:
        derived_gaps.append("CV không nêu kinh nghiệm đi làm/thực tập")
        derived_flags.append("Chưa có bằng chứng kinh nghiệm đi làm/thực tập")
    if unsupported:
        derived_gaps.append(f"Skills chưa có bằng chứng: {', '.join(unsupported)}")
        derived_flags.append("Một số skills trong mục Skills chưa xuất hiện trong project/work")
    if not any(project.url for project in (resume.projects or [])):
        derived_gaps.append("Chưa có link demo/deploy/GitHub để kiểm chứng")
    if not any(token in cv_text.lower() for token in ("test", "ci/cd", "continuous integration")):
        derived_gaps.append("CV không nêu test hoặc CI/CD")
    if any(word in cv_text.lower() for word in ("simulated", "internal test", "synthetic", "mô phỏng", "test set nội bộ")):
        derived_gaps.append("Số liệu simulated/internal hoặc thiếu điều kiện đo chưa được xác minh")
        derived_flags.append("Có số liệu tự công bố chưa đủ điều kiện đo để kiểm chứng")
    red_flags = [flag for flag in evaluation.red_flags if flag != "không phát hiện"] + derived_flags
    invalid = []
    for item in values.values():
        invalid.extend([quote for quote in item["evidence_quotes"] if quote not in validate_quotes(item["evidence_quotes"], cv_text)])
    if invalid:
        warnings.append("Có evidence quote không khớp text PDF")
    if llm.LAST_WARNING:
        warnings.append(llm.LAST_WARNING)
    totals = [round(sum(max(0, min(float(getattr(run.scores, key).score), maximum)) for key, (_, maximum) in rubric_for_level(job.level).items()), 1) for run in evaluations]
    if len(totals) > 1 and max(totals) - min(totals) > 8:
        warnings.append("Các lần chạy không ổn định: độ lệch tổng điểm lớn hơn 8")
    if status == "đang học":
        warnings.append("Ứng viên đang học; không được ghi là đã tốt nghiệp")
    return {
        "candidate": (resume.basics.name if resume.basics and resume.basics.name else "Ứng viên"),
        "jd_level": job.level,
        "cv_education_status": status,
        "scores": values,
        "coverage": [item.model_dump() for item in evaluation.coverage],
        "total": total,
        "band": band_for_score(total),
        "level_comparison": f"CV hiện thể hiện mức {status}; JD yêu cầu {job.level}",
        "knockout_warnings": [f"Thiếu must-have: {item.requirement}" for item in evaluation.coverage if item.kind == "must_have" and item.status in {"missing", "not_evidenced"}],
        "key_strengths": evaluation.key_strengths[:4],
        "red_flags": list(dict.fromkeys(red_flags)) or ["không phát hiện"],
        "interview_questions": evaluation.interview_questions[:5],
        "cv_improvement_suggestions": evaluation.cv_improvement_suggestions,
        "gaps": list(dict.fromkeys(derived_gaps)),
        "unsupported_skills": unsupported,
        "reliability": {
            "models_used": list(dict.fromkeys(llm.CALL_LOG)),
            "warnings": warnings,
            "invalid_quotes": invalid,
            "github_unverified": "GitHub chưa được xác minh qua API công khai",
            "extraction_call_count": sum(record["phase"] == "extraction" for record in llm.CALL_RECORDS),
        },
    }


def print_report(payload):
    print("\n" + "=" * 64)
    print(f"📊 KẾT QUẢ ĐÁNH GIÁ CV: {payload['candidate']}")
    print("=" * 64)
    print(f"Level JD: {payload['jd_level']} | So sánh: {payload['level_comparison']}")
    print("\n📈 ĐIỂM TỪNG NHÓM:")
    for key, item in payload["scores"].items():
        print(f"\n{CATEGORY_LABELS.get(key, key)}: {item['score']:.1f}/{item['max']} ({item['confidence']})")
        print(f"   Evidence: {' | '.join(item['evidence_quotes']) or 'CV không nêu'}")
        print(f"   Gaps: {', '.join(item['gaps']) or 'Không có'}")
        if item["rationale"]:
            print(f"   Nhận định: {item['rationale']}")
    print(f"\n🎯 TỔNG ĐIỂM: {payload['total']:.1f}/100 | {payload['band']}")
    if payload["knockout_warnings"]:
        print("⚠️  CẢNH BÁO KNOCKOUT:")
        for item in payload["knockout_warnings"]:
            print(f"  - {item}")
    for title, key in (("ĐIỂM MẠNH", "key_strengths"), ("RED FLAGS/RỦI RO", "red_flags"), ("CẦN XÁC MINH KHI PHỎNG VẤN", "interview_questions"), ("GỢI Ý SỬA CV", "cv_improvement_suggestions")):
        print(f"\n{title}:")
        for index, value in enumerate(payload[key], 1):
            print(f"  {index}. {value}")
    print("\n🔒 ĐỘ TIN CẬY CỦA LẦN CHẤM:")
    print(f"   Model thực tế: {', '.join(payload['reliability']['models_used']) or 'chưa ghi nhận'}")
    for warning in payload["reliability"]["warnings"]:
        print(f"   ⚠️ {warning}")
    print(f"   {payload['reliability']['github_unverified']}")
    print("=" * 64 + "\n")


def run(args):
    if not os.path.exists(args.pdf):
        raise SystemExit(f"❌ Không tìm thấy file: {args.pdf}")
    print(f"📄 Đang đọc PDF: {args.pdf}")
    cv_text = extract.pdf_to_text(args.pdf)
    resume = load_or_extract(cv_text, args.no_cache, model=args.model, fallback_model=args.fallback_model, allow_fallback=config.ALLOW_FALLBACK)
    job_description = Path(args.jd).read_text(encoding="utf-8") if args.jd else ""
    job = evaluate.analyze_job_description(job_description, model=args.model, fallback_model=args.fallback_model, allow_fallback=config.ALLOW_FALLBACK)
    evaluations = []
    for index in range(args.runs):
        print(f"\n🧮 Đang chấm điểm lần {index + 1}/{args.runs}...")
        evaluations.append(evaluate.evaluate_resume(extract.resume_to_text(resume), job_description, resume=resume, job=job, evidence_text=cv_text, model=args.model, fallback_model=args.fallback_model, allow_fallback=config.ALLOW_FALLBACK))
    evaluation = median_scores(evaluations, job.level)
    payload = build_payload(resume, evaluation, job, cv_text, evaluations)
    if args.json:
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"📄 Đã ghi JSON: {args.json}")
    print_report(payload)


def parse_args():
    parser = argparse.ArgumentParser(description="Chấm CV bằng Gemini với rubric có kiểm chứng")
    parser.add_argument("pdf")
    parser.add_argument("jd", nargs="?", default="")
    parser.add_argument("--json", dest="json", default="", help="Ghi report JSON vào file")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--fallback-model", default=None)
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.model:
        config.MODEL = args.model
    if args.fallback_model:
        config.MODEL_FALLBACKS = (args.fallback_model,)
    config.ALLOW_FALLBACK = args.allow_fallback and not args.no_fallback
    run(args)
