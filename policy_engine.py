"""
Policy Agent — rule engine thuần (KHÔNG dùng LLM) áp EC_POLICY_V2 theo đúng
thứ tự ưu tiên mục 4 README. Đây là quyết định kiến trúc quan trọng: bảng
policy là logic if-elif xác định, giao cho LLM 9B tự suy luận có rủi ro sai số
học/sai thứ tự ưu tiên -> code thuần đảm bảo đúng 100% quy tắc, LLM chỉ dùng
ở Coordinator để diễn giải ngôn ngữ tự nhiên (xem llm_client.py).
"""
from __future__ import annotations

MAX_ROOT_CAUSES = 3
MAX_RESPONSIBLE_PARTIES = 3
MAX_ACTIONS = 5

PLATFORM_ID = "OLIST_PLATFORM"
LOGISTICS_ID = "LOGISTICS_PROVIDER"


def determine_primary_issue(order_status: str, payment_total: float, is_late: bool,
                             late_handoff_seller_ids: list, split_payment: bool,
                             reconciled) -> tuple[str, str]:
    """Trả về (primary_issue, root_cause_code) theo đúng thứ tự ưu tiên bảng mục 4."""
    if order_status == "canceled" and payment_total > 0:
        return "canceled_order_paid", "ORDER_CANCELED_AFTER_PAYMENT"
    if order_status == "unavailable" and payment_total > 0:
        return "unavailable_order_paid", "ORDER_UNAVAILABLE_AFTER_PAYMENT"
    if is_late and len(late_handoff_seller_ids) > 0:
        return "late_delivery_seller", "SELLER_HANDOFF_AFTER_LIMIT"
    if is_late and len(late_handoff_seller_ids) == 0:
        return "late_delivery_logistics", "CARRIER_DELIVERED_AFTER_ESTIMATE"
    if split_payment and reconciled:
        return "valid_split_payment", "MULTIPLE_PAYMENTS_RECONCILED"
    if (not is_late) and reconciled:
        return "unsupported_late_claim", "DELIVERY_WITHIN_ESTIMATE"

    # Fallback không có trong bảng gốc: đơn giao đúng hạn nhưng payment KHÔNG
    # khớp và không phải split payment. README không định nghĩa nhánh này;
    # quyết định kỹ thuật: xử lý an toàn như unsupported_late_claim (không tự
    # tạo refund khi không có quy tắc rõ ràng) nhưng hạ confidence ở caller.
    return "unsupported_late_claim", "DELIVERY_WITHIN_ESTIMATE"


def build_case_assessment(primary_issue: str, secondary_issues: list[str], is_fallback: bool) -> dict:
    action_required_issues = {"canceled_order_paid", "unavailable_order_paid",
                               "late_delivery_seller", "late_delivery_logistics"}
    case_status = "action_required" if primary_issue in action_required_issues else "no_action"
    confidence = 0.6 if is_fallback else (0.95 if case_status == "action_required" else 0.9)
    return {
        "primary_issue": primary_issue,
        "secondary_issues": secondary_issues,
        "case_status": case_status,
        "confidence": confidence,
    }


def build_root_cause_and_financial(primary_issue: str, root_cause_code: str,
                                    payment_total: float, freight_total,
                                    late_handoff_seller_ids: list[str]) -> tuple[dict, dict]:
    ranked_causes = [{"cause_code": root_cause_code, "rank": 1}][:MAX_ROOT_CAUSES]

    responsible_parties = []
    refund = 0.0
    if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
        responsible_parties = [{"party_type": "platform", "party_id": PLATFORM_ID}]
        refund = round(payment_total, 2)
    elif primary_issue == "late_delivery_seller":
        for sid in late_handoff_seller_ids[:MAX_RESPONSIBLE_PARTIES]:
            responsible_parties.append({"party_type": "seller", "party_id": sid})
        refund = round(freight_total, 2) if freight_total is not None else 0.0
    elif primary_issue == "late_delivery_logistics":
        responsible_parties = [{"party_type": "logistics_provider", "party_id": LOGISTICS_ID}]
        refund = round(freight_total, 2) if freight_total is not None else 0.0
    # valid_split_payment / unsupported_late_claim: không có responsible, refund 0

    root_cause_analysis = {
        "ranked_causes": ranked_causes,
        "responsible_parties": responsible_parties[:MAX_RESPONSIBLE_PARTIES],
    }
    financial_resolution = {
        "currency": "BRL",
        "recommended_refund_brl": refund,
    }
    return root_cause_analysis, financial_resolution


import os

# --- Cac diem README KHONG quy dinh ro -> de duoi dang bien de A/B thu ---
# VARIANT_REFUND_COMPLETION:
#   "example" (mac dinh) = chi them verify_refund_completion cho case full
#      refund (canceled/unavailable). Cach nay bam theo VI DU MAU o README
#      muc 6: vi du do la EC_002 (moi con so trung khop) va co
#      case_status=action_required nhung KHONG co verify_refund_completion.
#   "rule"  = them cho MOI case action_required. Cach nay bam theo doan van
#      muc 4 liet ke cac action bo sung ma chi neu duy nhat 1 ngoai le.
VARIANT_REFUND_COMPLETION = os.environ.get("VARIANT_REFUND_COMPLETION", "example").lower()


def build_actions(primary_issue: str, case_status: str, secondary_issues: list[str]) -> list[str]:
    primary_action_map = {
        "canceled_order_paid": "issue_full_refund",
        "unavailable_order_paid": "issue_full_refund",
        "late_delivery_seller": "refund_freight",
        "late_delivery_logistics": "refund_freight",
        "valid_split_payment": "explain_valid_split_payment",
        "unsupported_late_claim": "reject_late_refund",
    }
    actions = [primary_action_map[primary_issue]]

    if primary_issue == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary_issue == "late_delivery_logistics":
        actions.append("review_carrier_delay")

    # verify_refund_completion CHI danh cho case full-refund (issue_full_refund):
    # canceled_order_paid / unavailable_order_paid. Case_status=action_required
    # KHONG phai dieu kien dung - vi du mau chinh thuc trong README (mau
    # late_delivery_seller, case_status=action_required) khong co
    # verify_refund_completion trong resolution_actions, chi co
    # review_seller_handoff + verify_payment_allocation. late_delivery_* da
    # co review_seller_handoff/review_carrier_delay lam buoc theo doi rieng.
    if VARIANT_REFUND_COMPLETION == "rule":
        if case_status == "action_required":
            actions.append("verify_refund_completion")
    else:  # "example"
        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            actions.append("verify_refund_completion")

    if "multi_seller_order" in secondary_issues:
        actions.append("coordinate_multi_seller_case")

    if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
        actions.append("verify_payment_allocation")

    return actions[:MAX_ACTIONS]


SECONDARY_ORDER = ["multi_item_order", "multi_seller_order", "split_payment",
                    "repeat_customer", "multiple_categories"]


def build_secondary_issues(flags: dict) -> list[str]:
    return [name for name in SECONDARY_ORDER if flags.get(name)]
