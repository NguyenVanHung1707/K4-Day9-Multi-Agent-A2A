"""
Delivery Agent — tính delivery_variance_hours và seller handoff variance.

delivery_variance_hours = order_delivered_customer_date - order_estimated_delivery_date
handoff_variance_hours  = order_delivered_carrier_date - shipping_limit_date SỚM NHẤT của seller

Chỉ được Coordinator gọi khi order_status = delivered (Router bỏ qua agent
này cho canceled/unavailable — xem coordinator.py) vì các order đó gần như
chắc chắn không có order_delivered_customer_date.
"""
from __future__ import annotations
import pandas as pd
from data_loader import OlistData

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _fmt(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.to_datetime(ts).strftime(TS_FORMAT)


def _hours_diff(later, earlier) -> float | None:
    if later is None or earlier is None or pd.isna(later) or pd.isna(earlier):
        return None
    delta = pd.to_datetime(later) - pd.to_datetime(earlier)
    return round(delta.total_seconds() / 3600.0, 2)


def run(data: OlistData, order_id: str, order_row, items_df) -> dict:
    delivered_at = order_row.order_delivered_customer_date
    estimated_at = order_row.order_estimated_delivery_date
    carrier_handoff_at = order_row.order_delivered_carrier_date

    delivery_variance_hours = _hours_diff(delivered_at, estimated_at)

    seller_handoff_analysis = []
    late_handoff_seller_ids = []
    if items_df is not None and not items_df.empty:
        for seller_id, grp in items_df.groupby("seller_id", sort=False):
            shipping_limit_at = grp.shipping_limit_date.min()
            handoff_variance_hours = _hours_diff(carrier_handoff_at, shipping_limit_at)
            late_handoff = (handoff_variance_hours is not None) and (handoff_variance_hours > 0)
            seller_handoff_analysis.append({
                "seller_id": seller_id,
                "shipping_limit_at": _fmt(shipping_limit_at),
                "handoff_variance_hours": handoff_variance_hours,
                "late_handoff": late_handoff,
            })
            if late_handoff:
                late_handoff_seller_ids.append(seller_id)
        # giữ thứ tự ổn định theo thứ tự xuất hiện trong order_items (không sort lại)
        order_of_appearance = items_df.seller_id.drop_duplicates().tolist()
        seller_handoff_analysis.sort(key=lambda r: order_of_appearance.index(r["seller_id"]))
        late_handoff_seller_ids = [s for s in order_of_appearance if s in late_handoff_seller_ids]

    is_late = delivery_variance_hours is not None and delivery_variance_hours > 0

    return {
        "delivery_analysis": {
            "delivered_at": _fmt(delivered_at),
            "estimated_delivery_at": _fmt(estimated_at),
            "carrier_handoff_at": _fmt(carrier_handoff_at),
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids,
        },
        "is_late": is_late,
        "late_handoff_seller_ids": late_handoff_seller_ids,
    }


def skipped_result() -> dict:
    """Dùng khi Router bỏ qua Delivery Agent (order canceled/unavailable)."""
    return {
        "delivery_analysis": {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
        },
        "is_late": False,
        "late_handoff_seller_ids": [],
    }
