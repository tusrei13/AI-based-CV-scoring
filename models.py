"""
models.py — Định nghĩa "hình dạng dữ liệu" bằng Pydantic.

Đây là phần QUAN TRỌNG NHẤT để hiểu một AI project kiểu này.
Ý tưởng: LLM trả về chữ (text), nhưng ta muốn dữ liệu có CẤU TRÚC (structured).
Ta khai báo trước "dữ liệu phải trông như thế này" bằng Pydantic, rồi bắt Gemini
trả JSON đúng đúng khuôn đó (gọi là "structured output" / "JSON mode").

=> Không phải tự tay parse chuỗi, không đoán mò, ít bug. Model buộc phải điền
   đúng các trường mình cần.

File này gồm 2 nhóm schema:
  1) Schema CV        — kết quả bước TRÍCH XUẤT (extract.py)
  2) Schema Chấm điểm — kết quả bước CHẤM ĐIỂM (evaluate.py)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ======================================================================
# 1) SCHEMA CV — rút gọn từ chuẩn "JSON Resume" (jsonresume.org)
#    Mỗi class = một khối thông tin trong CV. Optional = có thể thiếu.
# ======================================================================


class Basics(BaseModel):
    """Thông tin cơ bản của ứng viên."""

    name: Optional[str] = Field(default=None, description="Họ tên đầy đủ")
    email: Optional[str] = Field(default=None, description="Email")
    phone: Optional[str] = Field(default=None, description="Số điện thoại")
    linkedin: Optional[str] = Field(default=None, description="URL LinkedIn")
    location: Optional[str] = Field(default=None, description="Thành phố / nơi ở")
    summary: Optional[str] = Field(default=None, description="Giới thiệu bản thân")


class Work(BaseModel):
    """Một dòng kinh nghiệm làm việc."""

    company: Optional[str] = Field(default=None, description="Tên công ty")
    position: Optional[str] = Field(default=None, description="Chức danh")
    startDate: Optional[str] = Field(default=None, description="Ngày bắt đầu (YYYY-MM)")
    endDate: Optional[str] = Field(default=None, description="Ngày kết thúc hoặc 'Hiện tại'")
    summary: Optional[str] = Field(default=None, description="Mô tả công việc / thành tựu")


class Education(BaseModel):
    """Một dòng học vấn."""

    institution: Optional[str] = Field(default=None, description="Tên trường")
    area: Optional[str] = Field(default=None, description="Ngành học")
    studyType: Optional[str] = Field(default=None, description="Bậc học (Cử nhân, Thạc sĩ...)")
    startDate: Optional[str] = Field(default=None, description="Ngày bắt đầu")
    endDate: Optional[str] = Field(default=None, description="Ngày kết thúc")
    expectedGraduation: Optional[str] = Field(default=None, description="Ngày dự kiến tốt nghiệp nếu CV nêu")


class Skill(BaseModel):
    """Một nhóm kỹ năng, ví dụ nhóm 'Ngôn ngữ lập trình'."""

    name: Optional[str] = Field(default=None, description="Tên nhóm kỹ năng")
    keywords: Optional[List[str]] = Field(default=None, description="Các kỹ năng cụ thể")


class Project(BaseModel):
    """Một dự án cá nhân / đồ án."""

    name: Optional[str] = Field(default=None, description="Tên dự án")
    description: Optional[str] = Field(default=None, description="Mô tả dự án")
    url: Optional[str] = Field(default=None, description="Link (GitHub / demo) nếu có")
    technologies: Optional[List[str]] = Field(default=None, description="Công nghệ dùng")


class Award(BaseModel):
    """Một giải thưởng, thành tích hoặc cuộc thi nổi bật."""

    title: Optional[str] = Field(default=None, description="Tên giải thưởng hoặc thành tích")
    issuer: Optional[str] = Field(default=None, description="Tổ chức hoặc cuộc thi")
    date: Optional[str] = Field(default=None, description="Thời gian đạt được")
    description: Optional[str] = Field(default=None, description="Mô tả thành tích")


class Resume(BaseModel):
    """CV hoàn chỉnh — gom tất cả các phần lại sau khi trích xuất xong."""

    basics: Optional[Basics] = None
    work: Optional[List[Work]] = None
    education: Optional[List[Education]] = None
    skills: Optional[List[Skill]] = None
    projects: Optional[List[Project]] = None
    awards: Optional[List[Award]] = None


class JDRequirement(BaseModel):
    text: str = Field(description="Một yêu cầu nguyên văn hoặc gần nguyên văn từ JD")
    kind: str = Field(description="must_have hoặc nice_to_have")
    aliases: List[str] = Field(default_factory=list, description="Tên gọi tương đương nếu có")


class JobDescription(BaseModel):
    level: str = Field(description="Intern, Fresher, Junior, Middle hoặc Senior")
    must_have: List[JDRequirement] = Field(default_factory=list)
    nice_to_have: List[JDRequirement] = Field(default_factory=list)
    domain: Optional[str] = None
    language_requirements: List[str] = Field(default_factory=list)


class CoverageItem(BaseModel):
    requirement: str
    kind: str
    status: str = Field(description="met, partial, not_evidenced hoặc missing")
    evidence_quote: Optional[str] = None
    rationale: str = ""


# ======================================================================
# 2) SCHEMA CHẤM ĐIỂM — kết quả của bước đánh giá ứng viên
#    Giữ 4 nhóm điểm giống bản gốc hiring-agent (tổng tối đa 100),
#    cộng điểm thưởng và trừ điểm.
# ======================================================================


class CategoryScore(BaseModel):
    """Điểm của MỘT nhóm tiêu chí, kèm bằng chứng để giải thích được."""

    score: float = Field(default=0, description="Điểm đề xuất, code sẽ clamp")
    max: int = Field(default=0, description="Điểm tối đa tham khảo")
    confidence: str = Field(default="low", description="high, medium hoặc low")
    evidence_quotes: List[str] = Field(default_factory=list, description="Trích nguyên văn từ CV")
    gaps: List[str] = Field(default_factory=list, description="Thông tin còn thiếu hoặc chưa kiểm chứng")
    rationale: str = Field(default="", description="Tối đa 2 câu tiếng Việt")


class Scores(BaseModel):
    """Các nhóm cho cả hai profile; code chỉ dùng nhóm phù hợp với level JD."""

    job_fit: CategoryScore = Field(default_factory=CategoryScore)
    practical_experience_projects: CategoryScore = Field(default_factory=CategoryScore)
    technical_skills: CategoryScore = Field(default_factory=CategoryScore)
    education: CategoryScore = Field(default_factory=CategoryScore)
    languages: CategoryScore = Field(default_factory=CategoryScore)
    credibility: CategoryScore = Field(default_factory=CategoryScore)
    presentation: CategoryScore = Field(default_factory=CategoryScore)
    potential_soft_skills: CategoryScore = Field(default_factory=CategoryScore)
    work_experience: CategoryScore = Field(default_factory=CategoryScore)
    projects_portfolio: CategoryScore = Field(default_factory=CategoryScore)
    education_certifications: CategoryScore = Field(default_factory=CategoryScore)
    soft_skills: CategoryScore = Field(default_factory=CategoryScore)


class Evaluation(BaseModel):
    """Toàn bộ kết quả chấm điểm mà Gemini phải trả về."""

    scores: Scores
    coverage: List[CoverageItem] = Field(default_factory=list)
    key_strengths: List[str] = Field(default_factory=list, description="2-4 điểm mạnh có bằng chứng")
    red_flags: List[str] = Field(default_factory=list)
    interview_questions: List[str] = Field(default_factory=list)
    cv_improvement_suggestions: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)


# Điểm tối đa từng nhóm — dùng ở main.py để "chặn trần" điểm, KHÔNG tin tuyệt đối
# vào con số 'max' do LLM tự điền (LLM đôi khi bịa lệch).
INTERN_RUBRIC = {
    "job_fit": ("Độ phù hợp JD", 20),
    "practical_experience_projects": ("Dự án & kinh nghiệm thực tế", 30),
    "technical_skills": ("Kỹ năng", 20),
    "education": ("Học vấn", 10),
    "languages": ("Ngoại ngữ", 5),
    "credibility": ("Nhất quán & độ tin cậy", 5),
    "presentation": ("Trình bày", 5),
    "potential_soft_skills": ("Tiềm năng & soft skills", 5),
}

JUNIOR_RUBRIC = {
    "job_fit": ("Độ phù hợp JD", 25),
    "work_experience": ("Kinh nghiệm làm việc", 25),
    "technical_skills": ("Kỹ năng", 15),
    "projects_portfolio": ("Dự án/GitHub/OSS", 10),
    "education_certifications": ("Học vấn & chứng chỉ", 5),
    "languages": ("Ngoại ngữ", 5),
    "credibility": ("Nhất quán & độ tin cậy", 8),
    "presentation": ("Trình bày", 3),
    "soft_skills": ("Soft skills", 4),
}
