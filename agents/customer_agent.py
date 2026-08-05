"""
Customer Agent — xác định customer identity và lịch sử order.
Deterministic (pandas lookup), không cần LLM vì đây là tra cứu có cấu trúc,
không phải hiểu ngôn ngữ tự nhiên.
"""
from __future__ import annotations
from data_loader import OlistData

MAX_RELATED_ORDERS = 5


def run(data: OlistData, order_id: str, order_row) -> dict:
    """
    Trả về:
      {
        "customer_context": {...},
        "secondary_flags": {"repeat_customer": bool},
      }
    """
    customer_id = order_row.customer_id
    customer_row = data.get_customer(customer_id)
    customer_unique_id = customer_row.customer_unique_id if customer_row is not None else None

    related_order_ids = []
    if customer_unique_id is not None:
        related_order_ids = data.get_related_orders(customer_unique_id, exclude_order_id=order_id)[:MAX_RELATED_ORDERS]

    return {
        "customer_context": {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids,
        },
        "secondary_flags": {
            "repeat_customer": len(related_order_ids) > 0,
        },
    }
