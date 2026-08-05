from __future__ import annotations

from decimal import Decimal

from src.repository import DataRepository
from src.utils import money, stable_unique


class OrderProductAgent:
    name = "order_product_agent"

    def __init__(self, repository: DataRepository):
        self.repository = repository

    def run(self, order_id: str, include_product_context: bool = True) -> dict:
        order = self.repository.require_order(order_id)
        items = self.repository.items_by_order.get(order_id, [])
        seller_ids = stable_unique(row["seller_id"] for row in items)
        product_ids = stable_unique(row["product_id"] for row in items)

        categories: list[str] = []
        if include_product_context:
            for product_id in product_ids:
                product = self.repository.products.get(product_id)
                if product and product.get("product_category_name"):
                    categories.append(product["product_category_name"])
            categories = stable_unique(categories)

        return {
            "order": order,
            "items": items,
            "item_ids": [f'{order_id}:{row["order_item_id"]}' for row in items],
            "seller_ids": seller_ids,
            "product_ids": product_ids if include_product_context else [],
            "category_names": categories,
            "item_total_brl": money(sum((Decimal(row["price"]) for row in items), Decimal("0"))),
            "freight_total_brl": money(sum((Decimal(row["freight_value"]) for row in items), Decimal("0"))),
            "item_count": len(items),
            "seller_count": len(seller_ids),
            "category_count": len(categories),
        }

