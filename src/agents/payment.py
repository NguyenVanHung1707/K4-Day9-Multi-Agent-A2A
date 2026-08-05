from __future__ import annotations

from decimal import Decimal

from src.repository import DataRepository
from src.utils import money, stable_unique


class PaymentAgent:
    name = "payment_agent"

    def __init__(self, repository: DataRepository):
        self.repository = repository

    def run(self, order_id: str, order_result: dict) -> dict:
        payments = self.repository.payments_by_order.get(order_id, [])
        payment_total = sum((Decimal(row["payment_value"]) for row in payments), Decimal("0"))
        has_items = order_result["item_count"] > 0

        if has_items:
            expected = Decimal(str(order_result["item_total_brl"])) + Decimal(str(order_result["freight_total_brl"]))
            difference = payment_total - expected
            expected_value = money(expected)
            difference_value = money(difference)
            reconciled = abs(difference) <= Decimal("0.10")
        else:
            expected_value = None
            difference_value = None
            reconciled = None

        return {
            "payments": payments,
            "payment_ids": [f'{order_id}:{row["payment_sequential"]}' for row in payments],
            "payment_total_brl": money(payment_total),
            "payment_types": stable_unique(row["payment_type"] for row in payments),
            "payment_count": len(payments),
            "expected_total_brl": expected_value,
            "difference_brl": difference_value,
            "reconciled": reconciled,
        }

