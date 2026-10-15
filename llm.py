"""
llm.py — Nơi DUY NHẤT gọi tới Gemini.

Toàn bộ project chỉ có 1 hàm để nói chuyện với AI: ask_json().
Gom hết vào 1 chỗ giúp newbie dễ hiểu "AI được gọi ở đâu" và dễ đổi nhà cung cấp
sau này (ví dụ đổi sang Ollama chạy local — xem bài tập trong README).

Điểm hay nhất ở đây: STRUCTURED OUTPUT.
Ta đưa cho Gemini một "khuôn" Pydantic (response_schema) và bảo nó
"trả JSON đúng khuôn này". Gemini tự đảm bảo output là JSON hợp lệ,
nên ta KHÔNG phải tự cắt chuỗi / vá lỗi JSON như cách làm cũ.
"""

import json
import random
import re
import time

from google import genai
from google.genai import errors
from google.genai import types

import config

# Tạo client 1 lần rồi dùng lại. Khởi tạo "lazy" (chỉ tạo ở lần gọi AI đầu tiên)
# để các bước không cần AI — như đọc PDF — vẫn chạy được dù chưa có API key.
_client = None
CALL_LOG = []
CALL_RECORDS = []
LAST_WARNING = ""


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.require_api_key())
    return _client


def _is_daily_quota_error(error) -> bool:
    """
    429 có 2 loại: hết quota THEO PHÚT (chờ rồi thử lại được) và hết quota
    THEO NGÀY (chờ bao lâu cũng vô ích, phải đợi qua ngày hoặc đổi model/bật billing).
    Google phân biệt 2 loại này bằng quotaId chứa chữ "PerDay".
    """
    return "PerDay" in str(error)


def ask_json(system_prompt: str, user_prompt: str, schema, *, model=None, fallback_model=None, allow_fallback=None, phase="unknown"):
    """
    Gửi 1 câu hỏi cho Gemini và nhận về dữ liệu ĐÚNG KHUÔN `schema`.

    Tham số:
        system_prompt: "vai trò / luật chơi" cho model (ví dụ: 'Bạn là nhà tuyển dụng...').
        user_prompt:   nội dung cụ thể cần xử lý (ví dụ: text của CV).
        schema:        một class Pydantic, HOẶC list[PydanticModel], mô tả output.

    Trả về:
        Một object Pydantic (hoặc list object) đã được điền dữ liệu.
    """
    primary = model or config.MODEL
    fallback_enabled = config.ALLOW_FALLBACK if allow_fallback is None else allow_fallback
    fallbacks = tuple(x for x in (fallback_model,) if x) or config.MODEL_FALLBACKS
    models = tuple(dict.fromkeys((primary, *(fallbacks if fallback_enabled else ()))))
    request_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=config.TEMPERATURE,
        response_mime_type="application/json",
        response_schema=schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    response = None
    last_retryable_error = None
    for model in models:
        for attempt in range(config.MAX_RETRIES):
            try:
                response = _get_client().models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=request_config,
                )
                if model != config.MODEL:
                    global LAST_WARNING
                    LAST_WARNING = f"Đã fallback từ {primary} sang {model}."
                    print(f"   -> chuyển sang model dự phòng: {model}")
                CALL_LOG.append(model)
                CALL_RECORDS.append({"model": model, "phase": phase})
                break
            except errors.APIError as error:
                if error.code not in (429, 503):
                    raise

                last_retryable_error = error

                # Hết quota THEO NGÀY: thử lại vô ích, tốn thêm request thật mỗi lần.
                # Dừng ngay với model này, sang model dự phòng (nếu có) luôn.
                if error.code == 429 and _is_daily_quota_error(error):
                    print(f"   -> {model} đã hết quota trong NGÀY, bỏ qua model này...")
                    break

                if attempt == config.MAX_RETRIES - 1:
                    break

                if error.code == 429:
                    retry_delay = re.search(r"retryDelay[^0-9]*(\d+)", str(error))
                    wait_time = float(retry_delay.group(1)) if retry_delay else config.RATE_LIMIT_WAIT_SECONDS * (2**attempt)
                    wait_time += random.uniform(0, min(10, wait_time * 0.2))
                    print(f"   -> Gemini 429, thử lại sau {wait_time:.1f}s...")
                else:
                    wait_time = (
                        config.RETRY_BASE_SECONDS * (2**attempt)
                        + random.uniform(0, 1)
                    )
                    print(f"   -> Gemini 503, thử lại sau {wait_time:.1f}s...")
                time.sleep(wait_time)

        if response is not None:
            break

    if response is None:
        if last_retryable_error is not None and _is_daily_quota_error(last_retryable_error):
            raise RuntimeError(
                "Tất cả model đã hết quota FREE TIER trong ngày hôm nay "
                f"(thử: {', '.join(models)}). Hãy đợi quota reset vào ngày mai, "
                "đổi sang model khác trong config.py, hoặc bật billing cho API key."
            ) from last_retryable_error
        raise last_retryable_error or RuntimeError("Gemini không trả về kết quả.")

    # google-genai tự parse JSON thành object Pydantic, nằm ở response.parsed.
    # Phòng hờ: nếu vì lý do nào đó parsed rỗng, ta tự parse từ text.
    if response.parsed is not None:
        return response.parsed

    data = json.loads(response.text)
    if isinstance(data, list):
        item_model = schema.__args__[0]  # trường hợp schema = list[Model]
        return [item_model(**x) for x in data]
    return schema(**data)