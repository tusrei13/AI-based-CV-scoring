from datetime import date

from models import CategoryScore, CoverageItem, Education, Evaluation, Project, Resume, Skill
from scoring import band_for_score, coverage_score, education_status, finalize_scores, unsupported_skills, validate_quotes


def test_quote_validation_normalizes_whitespace_and_bullets():
    assert validate_quotes(["• React   developer"], "React developer") == ["• React   developer"]
    assert validate_quotes(["not in cv"], "React developer") == []


def test_present_education_is_studying_and_has_gap():
    status, gaps = education_status([Education(institution="U", endDate="Present")], date(2026, 9, 29))
    assert status == "đang học"
    assert "ngày dự kiến tốt nghiệp" in gaps[0]


def test_unsupported_skills_use_aliases():
    resume = Resume(skills=[Skill(name="tech", keywords=["NodeJS", "Java", "JavaScript"])], projects=[])
    resume.projects = [Project(description="JavaScript app", technologies=["Node.js"])]
    assert unsupported_skills(resume) == ["Java"]


def test_coverage_weights_must_have_twice():
    items = [
        CoverageItem(requirement="React", kind="must_have", status="met"),
        CoverageItem(requirement="Docker", kind="nice_to_have", status="partial"),
    ]
    assert coverage_score(items, None) == 2.5 / 3


def test_bands_and_clamp_contract():
    assert band_for_score(49.9) == "Reject"
    assert band_for_score(65) == "Interview"
    assert band_for_score(80) == "Strong Interview"


def test_total_uses_rubric_and_clamps_llm_score():
    evaluation = Evaluation(scores={"job_fit": CategoryScore(score=999, max=999)})
    total, values, _ = finalize_scores(evaluation, "Fresher", [])
    assert total <= 100
    assert values["job_fit"]["score"] == 0
