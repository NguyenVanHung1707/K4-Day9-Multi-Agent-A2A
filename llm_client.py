"""
LLM client — bọc gọi Gemini API cho model Gemma-2-9B-It (<=10B params, đúng
ràng buộc mục 9.1 README).

Model KHÔNG dùng để tính toán số liệu (join dữ liệu, delivery variance, payment
reconciliation, policy rule) — toàn bộ phần đó là code thuần (data_loader.py,
policy_engine.py) để đảm bảo đúng 100% quy tắc nghiệp vụ, không phụ thuộc độ
chính xác của model 9B.

LLM chỉ được dùng ở đúng chỗ cần hiểu ngôn ngữ tự nhiên: đọc
`customer_request.message` (tiếng Việt tự do) và sinh một đoạn diễn giải case
ngắn gọn cho nhân viên đọc — log vào trace.jsonl, KHÔNG đưa vào output JSON vì
schema output là cố định, thêm field lạ sẽ bị coi là sai schema.

Dùng SDK "google-genai" (KHÔNG dùng "google-generativeai" — package đó đã bị
Google deprecated). Lý do đổi SDK: key sinh trên AI Studio hiện nay có dạng
"AQ.xxx" (Auth key mới) thay vì "AIzaSy..." (Standard key cũ). SDK cũ
"google-generativeai" có nhiều báo cáo lỗi 401 ACCESS_TOKEN_TYPE_UNSUPPORTED /
"API key not valid" với key dạng AQ. vì đi qua route REST cũ không tương
thích; SDK mới "google-genai" xử lý đúng key AQ. ngay trong nội bộ.

Nếu không có mạng / API lỗi, tự động fallback graceful (không crash) để
pipeline không bao giờ treo/chết vì lý do hạ tầng — số liệu case vẫn đúng,
chỉ mất phần diễn giải ngôn ngữ tự nhiên (log lại lỗi trong trace.jsonl).
"""
from __future__ import annotations
import os
import time
import logging

logger = logging.getLogger("llm_client")

MODEL_NAME = "gemma-2-9b-it"  # <=10B parameters — theo README mục 9.1
PROVIDER = "google-genai (Gemini API)"
TIMEOUT_MS = 20_000  # tranh treo pipeline neu mang loi/bi chan

_client = None
_init_error: str | None = None


def _init():
    global _client, _init_error
    if _client is not None or _init_error is not None:
        return
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _init_error = "missing GEMINI_API_KEY"
        return
    try:
        from google import genai
        # google-genai tu nhan dien va xu ly dung ca key dang cu "AIzaSy..."
        # lan key dang moi "AQ...." (Auth key AI Studio hien tai).
        _client = genai.Client(api_key=api_key)
    except Exception as e:  # pragma: no cover
        _init_error = f"{type(e).__name__}: {e}"


def summarize_case(case_id: str, customer_message: str, evidence_digest: dict) -> dict:
    """
    Gọi Gemma-2-9B-It sinh diễn giải ngắn cho case. Trả về dict để ghi vào
    trace.jsonl:
      { "model": ..., "provider": ..., "prompt": ..., "output": ..., "latency_ms": ..., "ok": bool, "error": str|None, "mode": str }
    """
    _init()
    prompt = (
        "Ban la nhan vien ho tro khach hang thuong mai dien tu. "
        f"Khach hang phan anh: \"{customer_message}\". "
        f"Du lieu da xac minh: {evidence_digest}. "
        "Viet 2-3 cau tieng Viet giai thich ket luan cho khach hang, "
        "chi dua tren du lieu da cho, khong duoc bia them su kien."
    )
    start = time.time()
    if _client is None:
        return {
            "model": MODEL_NAME,
            "provider": PROVIDER,
            "prompt": prompt,
            "output": None,
            "latency_ms": 0,
            "ok": False,
            "error": _init_error or "client not initialized",
            "mode": "SKIPPED_NO_NETWORK_OR_KEY",
        }
    try:
        from google.genai import types
        resp = _client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
            ),
        )
        latency_ms = round((time.time() - start) * 1000, 1)
        return {
            "model": MODEL_NAME,
            "provider": PROVIDER,
            "prompt": prompt,
            "output": resp.text,
            "latency_ms": latency_ms,
            "ok": True,
            "error": None,
            "mode": "LIVE",
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 1)
        logger.warning("LLM call failed for %s: %s", case_id, e)
        return {
            "model": MODEL_NAME,
            "provider": PROVIDER,
            "prompt": prompt,
            "output": None,
            "latency_ms": latency_ms,
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "mode": "ERROR",
        }
