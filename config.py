"""
config.py — Đọc cấu hình từ file .env.

Newbie lưu ý: KHÔNG hard-code API key vào code. Ta để key trong file .env
(file này KHÔNG commit lên Git — xem .gitignore). Code chỉ đọc key ra lúc chạy.
"""

import os
from dotenv import load_dotenv

# Nạp các biến trong file .env vào biến môi trường (environment variables).
load_dotenv()

# API key của Gemini. Lấy free tại: https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model dùng để gọi. Free tier chỉ có các model dòng Flash / Flash-Lite.
# Mặc định "gemini-flash-latest" — đây là ALIAS luôn trỏ tới bản Flash mới nhất của Google,
# nên code không bị lỗi thời khi Google ra model mới (ví dụ gemini-2.5-flash đã bị chặn
# với tài khoản mới). Muốn ghim 1 model cụ thể thì đặt MODEL=... trong .env.
MODEL = os.getenv("MODEL", "gemini-flash-latest")

# Các model dự phòng, ngăn cách bằng dấu phẩy. Có thể để trống nếu chỉ muốn retry model chính.
MODEL_FALLBACKS = tuple(
    model.strip()
    for model in os.getenv("MODEL_FALLBACKS", "gemini-flash-lite-latest").split(",")
    if model.strip()
)
ALLOW_FALLBACK = os.getenv("ALLOW_FALLBACK", "false").lower() in {"1", "true", "yes"}
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = float(os.getenv("RETRY_BASE_SECONDS", "2"))
RATE_LIMIT_WAIT_SECONDS = float(os.getenv("RATE_LIMIT_WAIT_SECONDS", "60"))

# temperature = độ "ngẫu hứng" của model. Với việc trích xuất/chấm điểm ta cần
# ổn định & bám sát dữ liệu → để thấp.
TEMPERATURE = 0.1
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")

# Thư mục chứa các file prompt (.jinja).
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts", "templates")


def require_api_key() -> str:
    """Trả về API key, báo lỗi rõ ràng nếu chưa cấu hình."""
    if not GEMINI_API_KEY:
        raise SystemExit(
            "❌ Chưa có GEMINI_API_KEY.\n"
            "   1) Copy file .env.example thành .env\n"
            "   2) Lấy key free tại https://aistudio.google.com/apikey\n"
            "   3) Dán key vào dòng GEMINI_API_KEY=... trong .env"
        )
    return GEMINI_API_KEY
