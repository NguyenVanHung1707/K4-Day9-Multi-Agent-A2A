"""
Payment Agent — tổng hợp payment row, đối soát với item+freight.

expected_total_brl = sum(item.price) + sum(item.freight_value)
difference_brl = sum(payment.payment_value) - expected_total_brl
reconciled = abs(difference_brl) <= 0.10 BRL

Với order 0 item: CHỈ expected_total_brl / difference_brl / reconciled = null
(đúng nguyên văn README mục 4 - "expected_total_brl, difference_brl và
reconciled phải là null"). item_total_brl/freight_total_brl là tổng trên tập
rỗng nên vẫn phải là số 0.0, KHÔNG phải null - README không yêu cầu null 2
trường này, sai lệch này đã bị fix (trước đó code set nhầm cả 2 thành null).
"""
from __future__ import annotations
import os
from data_loader import OlistData

MAX_PAYMENT_IDS = 5
RECONCILE_TOLERANCE_BRL = 0.10

# README khong noi ro payment_types la TAP HOP cac loai hay DANH SACH theo
# tung payment row. De duoi dang bien de A/B thu:
#   "unique" (mac dinh) = khu trung lap, dung nghia "cac loai thanh toan"
#   "all"               = giu nguyen tung row theo payment_sequential
# Chi 4/50 case bi anh huong (case co >=2 row cung mot payment_type).
VARIANT_PAYMENT_TYPES = os.environ.get("VARIANT_PAYMENT_TYPES", "unique").lower()


def run(data: OlistData, order_id: str, item_total_brl, freight_total_brl, has_items: bool) -> dict:
    pay_df = data.get_payments(order_id)

    payment_total = round(float(pay_df.payment_value.sum()), 2) if not pay_df.empty else 0.0
    payment_ids = [f"{order_id}:{seq}" for seq in pay_df.payment_sequential.tolist()][:MAX_PAYMENT_IDS]
    if VARIANT_PAYMENT_TYPES == "all":
        payment_types = pay_df.payment_type.tolist()
    else:
        payment_types = pay_df.payment_type.drop_duplicates().tolist()

    if has_items:
        expected_total = round(item_total_brl + freight_total_brl, 2)
        difference = round(payment_total - expected_total, 2)
        reconciled = abs(difference) <= RECONCILE_TOLERANCE_BRL
    else:
        expected_total = None
        difference = None
        reconciled = None

    return {
        "payment_reconciliation": {
            "currency": "BRL",
            "item_total_brl": item_total_brl,
            "freight_total_brl": freight_total_brl,
            "expected_total_brl": expected_total,
            "payment_total_brl": payment_total,
            "difference_brl": difference,
            "reconciled": reconciled,
            "payment_types": payment_types,
        },
        "payment_ids": payment_ids,
        "payment_total_brl": payment_total,
        "n_payment_rows": len(pay_df),
        "secondary_flags": {
            "split_payment": len(pay_df) >= 2,
        },
    }
