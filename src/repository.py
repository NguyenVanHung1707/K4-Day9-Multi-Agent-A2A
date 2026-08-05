from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


class DataRepository:
    """Read-only, indexed view of the CSV facts used by the agents."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.orders = self._index_one("olist_orders_dataset.csv", "order_id")
        self.customers = self._index_one("olist_customers_dataset.csv", "customer_id")
        self.products = self._index_one("olist_products_dataset.csv", "product_id")
        self.sellers = self._index_one("olist_sellers_dataset.csv", "seller_id")
        self.items_by_order = self._index_many("olist_order_items_dataset.csv", "order_id")
        self.payments_by_order = self._index_many("olist_order_payments_dataset.csv", "order_id")

        self.orders_by_unique_customer: dict[str, list[dict[str, str]]] = defaultdict(list)
        for order in self.orders.values():
            customer = self.customers.get(order["customer_id"])
            if customer:
                self.orders_by_unique_customer[customer["customer_unique_id"]].append(order)

    def _rows(self, filename: str) -> Iterable[dict[str, str]]:
        with (self.data_dir / filename).open("r", encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle)

    def _index_one(self, filename: str, key: str) -> dict[str, dict[str, str]]:
        return {row[key]: row for row in self._rows(filename)}

    def _index_many(self, filename: str, key: str) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in self._rows(filename):
            result[row[key]].append(row)
        return result

    def require_order(self, order_id: str) -> dict[str, str]:
        try:
            return self.orders[order_id]
        except KeyError as exc:
            raise ValueError(f"Order not found in CSV: {order_id}") from exc

    def evidence_exists(self, evidence_id: str) -> bool:
        parts = evidence_id.split(":")
        if len(parts) == 2 and parts[0] == "order":
            return parts[1] in self.orders
        if len(parts) == 3 and parts[0] == "item":
            return any(row["order_item_id"] == parts[2] for row in self.items_by_order.get(parts[1], []))
        if len(parts) == 3 and parts[0] == "payment":
            return any(row["payment_sequential"] == parts[2] for row in self.payments_by_order.get(parts[1], []))
        if len(parts) == 2 and parts[0] == "seller":
            return parts[1] in self.sellers
        if len(parts) == 2 and parts[0] == "policy":
            return parts[1] in {
                "SELLER_HANDOFF_AFTER_LIMIT",
                "CARRIER_DELIVERED_AFTER_ESTIMATE",
                "ORDER_CANCELED_AFTER_PAYMENT",
                "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                "MULTIPLE_PAYMENTS_RECONCILED",
                "DELIVERY_WITHIN_ESTIMATE",
            }
        return False

