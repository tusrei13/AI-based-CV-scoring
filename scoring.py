"""Logic chấm điểm thuần code, độc lập với Gemini và dễ kiểm thử."""

import re
import unicodedata
from datetime import date, datetime
from statistics import median
from typing import Iterable

from models import Education, Evaluation, JobDescription, Resume, Scores, INTERN_RUBRIC, JUNIOR_RUBRIC


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = value.replace("•", " ").replace("·", " ")
    return re.sub(r"\s+", " ", value).strip()


def validate_quotes(quotes: Iterable[str], cv_text: str) -> list[str]:
    normalized_cv = normalize_text(cv_text)
    return [quote for quote in quotes if normalize_text(quote) and normalize_text(quote) in normalized_cv]


def invalid_quotes(evaluation: Evaluation, cv_text: str) -> list[str]:
    invalid = []
    for category in evaluation.scores.model_dump().values():
        invalid.extend(quote for quote in category.get("evidence_quotes", []) if quote not in validate_quotes(category.get("evidence_quotes", []), cv_text))
    invalid.extend(
        item.evidence_quote
        for item in evaluation.coverage
        if item.evidence_quote and not validate_quotes([item.evidence_quote], cv_text)
    )
    return invalid


def education_status(education: Iterable[Education] | None, today: date | None = None) -> tuple[str, list[str]]:
    today = today or datetime.now().date()
    entries = list(education or [])
    gaps = []
    studying = False
    for entry in entries:
        end = (entry.endDate or "").strip().lower()
        if not end or end in {"present", "current", "now", "nay", "hiện tại", "hien tai"}:
            studying = True
            if not entry.expectedGraduation:
                gaps.append("CV không nêu ngày dự kiến tốt nghiệp")
        else:
            years = re.findall(r"20\d{2}", end)
            if years and int(years[-1]) >= today.year:
                studying = True
    if studying:
        return "đang học", list(dict.fromkeys(gaps))
    return ("đã tốt nghiệp" if entries else "CV không nêu"), gaps


ALIASES = {
    "nodejs": "node",
    "node.js": "node",
    "nextjs": "next",
    "next.js": "next",
    "reactjs": "react",
    "react.js": "react",
    "postgresql": "postgres",
    "mongo": "mongodb",
}


def canonical_skill(skill: str) -> str:
    value = re.sub(r"[^a-z0-9+#.]", "", skill.lower())
    return ALIASES.get(value, value)


def unsupported_skills(resume: Resume) -> list[str]:
    skills = [keyword for group in (resume.skills or []) for keyword in (group.keywords or [])]
    evidence = " ".join(
        [p.description or "" for p in (resume.projects or [])]
        + [" ".join(p.technologies or []) for p in (resume.projects or [])]
        + [w.summary or "" for w in (resume.work or [])]
    )
    evidence_tokens = {canonical_skill(token) for token in re.findall(r"[a-zA-Z0-9+#.]+", normalize_text(evidence))}
    return [skill for skill in skills if canonical_skill(skill) not in evidence_tokens]


def coverage_score(coverage: Iterable, job: JobDescription) -> float:
    items = list(coverage)
    weighted = total = 0.0
    values = {"met": 1.0, "partial": 0.5}
    for item in items:
        weight = 2 if item.kind == "must_have" else 1
        total += weight
        weighted += weight * values.get(item.status, 0.0)
    return (weighted / total) if total else 0.0


def rubric_for_level(level: str) -> dict:
    return JUNIOR_RUBRIC if level.lower() in {"junior", "middle", "senior"} else INTERN_RUBRIC


def band_for_score(total: float) -> str:
    if total < 50:
        return "Reject"
    if total < 65:
        return "Hold/Backup"
    if total < 80:
        return "Interview"
    return "Strong Interview"


def finalize_scores(evaluation: Evaluation, level: str, coverage: list) -> tuple[float, dict, list[str]]:
    rubric = rubric_for_level(level)
    values = {}
    total = 0.0
    warnings = []
    for key, (_, maximum) in rubric.items():
        category = getattr(evaluation.scores, key)
        score = max(0.0, min(float(category.score), maximum))
        if key == "job_fit":
            score = round(coverage_score(coverage, JobDescription(level=level)), 4) * maximum if coverage else 0.0
        values[key] = {"label": rubric[key][0], "score": score, "max": maximum, "confidence": category.confidence, "evidence_quotes": category.evidence_quotes, "gaps": category.gaps, "rationale": category.rationale}
        total += score
    return round(min(total, 100.0), 1), values, warnings


def median_scores(evaluations: list[Evaluation], level: str) -> Evaluation:
    if len(evaluations) == 1:
        return evaluations[0]
    result = evaluations[0].model_copy(deep=True)
    rubric = rubric_for_level(level)
    for key in rubric:
        setattr(getattr(result, "scores"), key, getattr(evaluations[0].scores, key).model_copy(update={"score": median([float(getattr(item.scores, key).score) for item in evaluations])}))
    return result