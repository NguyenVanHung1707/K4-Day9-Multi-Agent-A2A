"""
LLM client — cho cac agent goi model ngon ngu.

=============================================================================
QUYET DINH CHON MODEL (README muc 9.1: "moi agent chi duoc su dung model
duoi hoac bang 10B parameters, chay local hoac qua provider tuy y")
=============================================================================
Model dang dung: **llama-3.1-8b-instant** qua **Groq API**.
    - Llama 3.1 8B Instruct -> 8 ty tham so, CONG BO CONG KHAI => <= 10B OK
    - Groq la provider hop le ("qua provider tuy y" - README muc 9.1)

!! LUU Y VONG DOI MODEL: Groq da thong bao ngung `llama-3.1-8b-instant` tu
   16/08/2026 (https://console.groq.com/docs/deprecations). Model van chay
   binh thuong o thoi diem nop bai. Model thay the Groq goi y la
   `openai/gpt-oss-20b` (20B) - VUOT 10B nen KHONG dung duoc cho bai nay;
   `gemma2-9b-it` (9B) tren Groq cung da bi tat tu 08/10/2025.
   => Sau 16/08/2026, phuong an <= 10B con lai la chay LOCAL bang Ollama:
      dat bien moi truong LLM_PROVIDER=ollama (xem OLLAMA_MODEL ben duoi).

Vi sao KHONG dung Gemini API: tai thoi diem lam bai, trang chinh thuc
https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api chi liet ke 2
model Gemma duoc ho tro, ca hai deu VUOT 10B:
    - gemma-4-31b-it        -> 31B params
    - gemma-4-26b-a4b-it    -> 26B tong / 4B active
va `gemma-2-9b-it` (9B) da bi Google GO khoi Gemini API (goi se loi 404).
Cac model dong (gemini-flash...) KHONG cong bo so tham so nen khong the
chung minh tuan thu rang buoc cua de bai.

Cac lua chon hop le khac (doi MODEL_NAME/PROVIDER ben duoi neu muon):
    Groq    : llama-3.1-8b-instant (8B, mac dinh), gemma2-9b-it (9B)
    Ollama  : gemma3:4b (4B), qwen3:8b (8B), llama3.1:8b (8B), mistral:7b (7B)

=============================================================================
PHAM VI DUNG LLM
=============================================================================
Model KHONG dung de tinh toan so lieu (join du lieu, delivery variance,
payment reconciliation, policy rule) — toan bo phan do la code thuan
(data_loader.py, policy_engine.py) de dam bao dung 100% quy tac nghiep vu,
khong phu thuoc do chinh xac cua model nho.

LLM chi dung o dung cho can hieu ngon ngu tu nhien: doc
`customer_request.message` (tieng Viet tu do) va sinh doan dien giai case
cho nhan vien doc — log vao trace.jsonl, KHONG dua vao output JSON vi
schema output la co dinh, them field la se bi coi la sai schema.

Neu mat mang / API loi, tu dong fallback graceful (khong crash pipeline) —
so lieu case van dung, chi mat phan dien giai.
"""
from __future__ import annotations
import json
import os
import re
import time
import logging
import urllib.error
import urllib.request

logger = logging.getLogger("llm_client")

# --- Khai bao model TRONG SOURCE CODE (README muc 9.4: ten model khong dat
# trong .env, phai o trong code va ghi lai trong metadata.json). Chi API KEY
# moi doc tu .env. ---
PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()

# Groq (mac dinh) — endpoint OpenAI-compatible
GROQ_MODEL = "llama-3.1-8b-instant"      # Llama 3.1 8B -> 8B params (<= 10B OK)
GROQ_PARAM_SIZE = "8B"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Ollama (du phong, chay local)
OLLAMA_MODEL = "gemma3:4b"               # Gemma 3 4B  -> 4B params (<= 10B OK)
OLLAMA_PARAM_SIZE = "4B"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

TIMEOUT_S = 60


def active_model() -> dict:
    """Thong tin model dang dung — main.py in ra, metadata.json tham chieu."""
    if PROVIDER == "ollama":
        return {"provider": f"Ollama local ({OLLAMA_HOST})", "model": OLLAMA_MODEL,
                "parameter_size": OLLAMA_PARAM_SIZE, "compliant_10b": True}
    return {"provider": "Groq API", "model": GROQ_MODEL,
            "parameter_size": GROQ_PARAM_SIZE, "compliant_10b": True}


def _build_prompt(customer_message: str, evidence_digest: dict) -> str:
    return (
        "Ban la nhan vien ho tro khach hang thuong mai dien tu. "
        f"Khach hang phan anh: \"{customer_message}\". "
        f"Du lieu da xac minh: {evidence_digest}. "
        "Viet 2-3 cau tieng Viet giai thich ket luan cho khach hang, "
        "chi dua tren du lieu da cho, khong duoc bia them su kien."
    )


# Groq dung Cloudflare o phia truoc. User-Agent mac dinh cua urllib
# ("Python-urllib/3.x") bi Cloudflare Browser Integrity Check chan va tra ve
# HTTP 403 "error code: 1010". Dat User-Agent thong thuong de tranh loi nay.
BASE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "K4-Day9-MultiAgent-A2A/1.0 (+python; urllib)",
}


MAX_RETRIES = 6          # so lan thu lai khi bi rate limit (HTTP 429)
DEFAULT_BACKOFF_S = 5.0  # cho bao lau neu API khong noi ro thoi gian cho


def _retry_after_seconds(body: str, headers) -> float:
    """Lay thoi gian can cho tu response 429.

    Groq tra ve message dang: "... Please try again in 3.57s ...".
    Neu khong parse duoc thi dung header Retry-After, cuoi cung la mac dinh.
    """
    m = re.search(r"try again in ([\d.]+)s", body)
    if m:
        try:
            return float(m.group(1)) + 0.5  # cong bien an toan
        except ValueError:
            pass
    if headers is not None:
        ra = headers.get("Retry-After")
        if ra:
            try:
                return float(ra) + 0.5
            except ValueError:
                pass
    return DEFAULT_BACKOFF_S


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON, tu dong cho va thu lai khi bi rate limit (HTTP 429).

    Groq free tier gioi han 6000 tokens/phut nen chay 50 case rat de cham
    tran. Response 429 co ghi ro thoi gian can cho -> doc lai va sleep dung
    bang do roi thu lai, thay vi bo cuoc va mat phan dien giai cua case.
    """
    data = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            url, data=data, headers={**BASE_HEADERS, **headers}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait_s = _retry_after_seconds(body, e.headers)
                logger.info("Rate limited (429), cho %.1fs roi thu lai (lan %d/%d)",
                            wait_s, attempt + 1, MAX_RETRIES)
                time.sleep(wait_s)
                last_err = f"HTTP 429 sau {attempt + 1} lan thu"
                continue
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from None
    raise RuntimeError(last_err or "khong goi duoc sau nhieu lan thu")


def _call_groq(prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("missing GROQ_API_KEY trong .env")
    data = _post_json(
        GROQ_URL,
        {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 300,
        },
        {"Authorization": f"Bearer {api_key}"},
    )
    return data["choices"][0]["message"]["content"]


def _call_ollama(prompt: str) -> str:
    data = _post_json(
        f"{OLLAMA_HOST}/api/generate",
        {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
         "options": {"temperature": 0.2}},
        {},
    )
    return data.get("response", "")


def summarize_case(case_id: str, customer_message: str, evidence_digest: dict) -> dict:
    """Goi LLM sinh dien giai ngan cho case. Tra ve dict de ghi vao trace.jsonl."""
    info = active_model()
    prompt = _build_prompt(customer_message, evidence_digest)
    start = time.time()
    try:
        text = _call_ollama(prompt) if PROVIDER == "ollama" else _call_groq(prompt)
        return {
            **info, "prompt": prompt, "output": text,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "ok": True, "error": None, "mode": "LIVE",
        }
    except Exception as e:
        logger.warning("LLM call failed for %s: %s", case_id, e)
        return {
            **info, "prompt": prompt, "output": None,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "ok": False, "error": f"{type(e).__name__}: {e}", "mode": "ERROR",
        }
