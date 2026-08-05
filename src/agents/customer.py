from __future__ import annotations

from src.config import MAX_RELATED_ORDERS
from src.repository import DataRepository


class CustomerAgent:
    name = "customer_agent"

    def __init__(self, repository: DataRepository):
        self.repository = repository

    def run(self, order_id: str, include_history: bool = True) -> dict:
        order = self.repository.require_order(order_id)
        customer = self.repository.customers.get(order["customer_id"])
        if customer is None:
            return {"customer_unique_id": None, "related_order_ids": [], "repeat_customer": False}

        unique_id = customer["customer_unique_id"]
        related = []
        if include_history:
            related = [
                item["order_id"]
                for item in self.repository.orders_by_unique_customer.get(unique_id, [])
                if item["order_id"] != order_id
            ][:MAX_RELATED_ORDERS]
        return {
            "customer_unique_id": unique_id,
            "related_order_ids": related,
            "repeat_customer": bool(related),
        }

