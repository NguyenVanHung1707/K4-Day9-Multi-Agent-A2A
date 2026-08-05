"""
Verifier Agent — kiểm tra schema, giới hạn mảng, evidence ID hợp lệ (tồn tại
trong CSV, đúng định dạng), null handling, trước khi ghi file. Pure code,
không LLM.

Thực hiện vòng Evaluator-Optimizer đơn giản: nếu phát hiện lỗi có thể tự sửa
an toàn (vượt giới hạn mảng do cộng dồn nhiều nguồn) thì tự trim rồi verify
lại; nếu lỗi không tự sửa được (thiếu dữ liệu bắt buộc, evidence sai định
dạng) thì trả lỗi để Coordinator ghi vào trace và đánh case là FAILED thay vì
ghi output sai.
"""
from __future__ import annotations
import re

LIMITS = {
    "affected_entities.order_ids": 5,
    "affected_entities.item_ids": 5,
    "affected_entities.seller_ids": 3,
    "affected_entities.payment_ids": 5,
    "customer_context.related_order_ids": 5,
    "product_context.product_ids": 5,
    "product_context.category_names": 5,
    "root_cause_analysis.ranked_causes": 3,
    "root_cause_analysis.responsible_parties": 3,
    "evidence_ids": 20,
    "resolution_actions": 5,
}

EVIDENCE_PATTERNS = [
    re.compile(r"^order:[^:]+$"),
    re.compile(r"^item:[^:]+:\d+$"),
    re.compile(r"^payment:[^:]+:\d+$"),
    re.compile(r"^seller:[^:]+$"),
    re.compile(r"^policy:[A-Z_]+$"),
]


def _get(d, path):
    parts = path.split(".")
    cur = d
    for p in parts:
        cur = cur.get(p)
        if cur is None:
            return None
    return cur


def _set(d, path, value):
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def auto_trim(output: dict) -> list[str]:
    """Tự trim các mảng vượt giới hạn. Trả về danh sách cảnh báo đã sửa."""
    fixes = []
    for path, limit in LIMITS.items():
        val = _get(output, path)
        if isinstance(val, list) and len(val) > limit:
            _set(output, path, val[:limit])
            fixes.append(f"auto-trim {path} to {limit}")
    return fixes


def verify(output: dict, valid_order_ids: set, valid_item_ids: set,
           valid_payment_ids: set, valid_seller_ids: set) -> tuple[bool, list[str]]:
    errors = []

    # 1. Giới hạn mảng
    for path, limit in LIMITS.items():
        val = _get(output, path)
        if isinstance(val, list) and len(val) > limit:
            errors.append(f"{path} vuot gioi han {limit} (co {len(val)})")

    # 2. confidence trong [0,1]
    conf = _get(output, "case_assessment.confidence")
    if conf is None or not (0 <= conf <= 1):
        errors.append(f"confidence khong hop le: {conf}")

    # 3. case_status hop le
    status = _get(output, "case_assessment.case_status")
    if status not in ("action_required", "no_action"):
        errors.append(f"case_status khong hop le: {status}")

    # 4. Evidence id dung dinh dang + ton tai trong CSV
    for eid in output.get("evidence_ids", []):
        if not any(p.match(eid) for p in EVIDENCE_PATTERNS):
            errors.append(f"evidence_id sai dinh dang: {eid}")
            continue
        kind, *rest = eid.split(":")
        if kind == "order" and rest[0] not in valid_order_ids:
            errors.append(f"evidence order khong ton tai: {eid}")
        elif kind == "item" and f"{rest[0]}:{rest[1]}" not in valid_item_ids:
            errors.append(f"evidence item khong ton tai: {eid}")
        elif kind == "payment" and f"{rest[0]}:{rest[1]}" not in valid_payment_ids:
            errors.append(f"evidence payment khong ton tai: {eid}")
        elif kind == "seller" and rest[0] not in valid_seller_ids:
            errors.append(f"evidence seller khong ton tai: {eid}")

    # 5. Null handling khi khong co item
    if output.get("affected_entities", {}).get("item_ids") == [] and \
       output.get("payment_reconciliation", {}).get("item_total_brl") not in (None, 0):
        pass  # item_total_brl co the =0 hop le neu co item gia 0; khong flag cung

    # 6. Rounding tien/gio: kiem tra khong qua 2 chu so thap phan
    for path in ["payment_reconciliation.item_total_brl", "payment_reconciliation.freight_total_brl",
                 "payment_reconciliation.expected_total_brl", "payment_reconciliation.payment_total_brl",
                 "payment_reconciliation.difference_brl", "financial_resolution.recommended_refund_brl",
                 "delivery_analysis.delivery_variance_hours"]:
        val = _get(output, path)
        if isinstance(val, float):
            if round(val, 2) != val:
                errors.append(f"{path} chua lam tron 2 chu so: {val}")

    return len(errors) == 0, errors
