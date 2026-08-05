from __future__ import annotations

from src.utils import parse_timestamp, stable_unique, variance_hours


class DeliveryAgent:
    name = "delivery_agent"

    def run(self, order_result: dict) -> dict:
        order = order_result["order"]
        carrier_at = order.get("order_delivered_carrier_date") or None
        delivered_at = order.get("order_delivered_customer_date") or None
        estimated_at = order.get("order_estimated_delivery_date") or None

        analysis = []
        late_sellers = []
        for seller_id in order_result["seller_ids"]:
            limits = [
                row["shipping_limit_date"]
                for row in order_result["items"]
                if row["seller_id"] == seller_id and row.get("shipping_limit_date")
            ]
            shipping_limit = min(limits, key=parse_timestamp) if limits else None
            handoff_variance = variance_hours(carrier_at, shipping_limit)
            late_handoff = handoff_variance is not None and handoff_variance > 0
            analysis.append({
                "seller_id": seller_id,
                "shipping_limit_at": shipping_limit,
                "handoff_variance_hours": handoff_variance,
                "late_handoff": late_handoff,
            })
            if late_handoff:
                late_sellers.append(seller_id)

        return {
            "delivered_at": delivered_at,
            "estimated_delivery_at": estimated_at,
            "carrier_handoff_at": carrier_at,
            "delivery_variance_hours": variance_hours(delivered_at, estimated_at),
            "seller_handoff_analysis": analysis,
            "late_handoff_seller_ids": stable_unique(late_sellers),
        }
