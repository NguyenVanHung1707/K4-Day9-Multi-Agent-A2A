"""
Data loader — nạp 9 CSV Olist một lần, cache trong RAM, expose các hàm tra cứu
theo order_id để các agent dùng chung (tránh mỗi agent tự đọc CSV riêng).
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent / "data"


class OlistData:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.orders = pd.read_csv(data_dir / "olist_orders_dataset.csv")
        self.items = pd.read_csv(data_dir / "olist_order_items_dataset.csv")
        self.payments = pd.read_csv(data_dir / "olist_order_payments_dataset.csv")
        self.reviews = pd.read_csv(data_dir / "olist_order_reviews_dataset.csv")
        self.customers = pd.read_csv(data_dir / "olist_customers_dataset.csv")
        self.products = pd.read_csv(data_dir / "olist_products_dataset.csv")
        self.sellers = pd.read_csv(data_dir / "olist_sellers_dataset.csv")
        self.category_translation = pd.read_csv(data_dir / "product_category_name_translation.csv")
        self.geolocation = pd.read_csv(data_dir / "olist_geolocation_dataset.csv")

        # Index để tra cứu nhanh
        self._orders_by_id = self.orders.set_index("order_id", drop=False)
        self._customers_by_id = self.customers.set_index("customer_id", drop=False)

    # ---------- Order ----------
    def get_order(self, order_id: str):
        """Trả về Series order hoặc None nếu không tồn tại."""
        if order_id in self._orders_by_id.index:
            row = self._orders_by_id.loc[order_id]
            if isinstance(row, pd.DataFrame):  # trùng id (không nên xảy ra)
                row = row.iloc[0]
            return row
        return None

    def get_items(self, order_id: str) -> pd.DataFrame:
        return self.items[self.items.order_id == order_id].sort_values("order_item_id")

    def get_payments(self, order_id: str) -> pd.DataFrame:
        return self.payments[self.payments.order_id == order_id].sort_values("payment_sequential")

    def get_customer(self, customer_id: str):
        if customer_id in self._customers_by_id.index:
            row = self._customers_by_id.loc[customer_id]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return row
        return None

    def get_related_orders(self, customer_unique_id: str, exclude_order_id: str) -> list[str]:
        cust_ids = self.customers[self.customers.customer_unique_id == customer_unique_id].customer_id.tolist()
        related = self.orders[
            self.orders.customer_id.isin(cust_ids) & (self.orders.order_id != exclude_order_id)
        ]
        # giữ thứ tự ổn định theo purchase timestamp
        related = related.sort_values("order_purchase_timestamp")
        return related.order_id.tolist()

    def get_products(self, product_ids: list[str]) -> pd.DataFrame:
        return self.products[self.products.product_id.isin(product_ids)]

    def get_category_english(self, category_name: str) -> str | None:
        if category_name is None or (isinstance(category_name, float)):
            return None
        row = self.category_translation[self.category_translation.product_category_name == category_name]
        if row.empty:
            return category_name  # fallback: giữ tên gốc nếu không có bản dịch
        return row.iloc[0].product_category_name_english

    def get_sellers(self, seller_ids: list[str]) -> pd.DataFrame:
        return self.sellers[self.sellers.seller_id.isin(seller_ids)]


_singleton: OlistData | None = None


def get_data() -> OlistData:
    global _singleton
    if _singleton is None:
        _singleton = OlistData()
    return _singleton
