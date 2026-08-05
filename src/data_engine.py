"""
Data Engine for Olist Brazilian E-Commerce Dataset.
Indexes all 9 CSV files in memory for fast lookup and precise metric calculation.
"""

import os
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

class DataEngine:
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.customers_by_id: Dict[str, Dict[str, Any]] = {}
        self.customer_orders: Dict[str, List[str]] = {}  # customer_unique_id -> list of order_ids
        self.order_items: Dict[str, List[Dict[str, Any]]] = {}  # order_id -> list of items
        self.order_payments: Dict[str, List[Dict[str, Any]]] = {}  # order_id -> list of payments
        self.products: Dict[str, Dict[str, Any]] = {}
        self.sellers: Dict[str, Dict[str, Any]] = {}
        self.category_translation: Dict[str, str] = {}
        
        self._load_data()

    def _load_data(self):
        # 0. Load Category Translation
        trans_path = os.path.join(self.data_dir, "product_category_name_translation.csv")
        if os.path.exists(trans_path):
            with open(trans_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    pt = row.get("product_category_name")
                    en = row.get("product_category_name_english")
                    if pt and en:
                        self.category_translation[pt] = en
        # 1. Load Customers & Index by customer_id and customer_unique_id
        cust_path = os.path.join(self.data_dir, "olist_customers_dataset.csv")
        cust_unique_map = {}  # customer_id -> customer_unique_id
        if os.path.exists(cust_path):
            with open(cust_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    cid = row["customer_id"]
                    cuid = row["customer_unique_id"]
                    self.customers_by_id[cid] = row
                    cust_unique_map[cid] = cuid
                    if cuid not in self.customer_orders:
                        self.customer_orders[cuid] = []

        # 2. Load Orders
        orders_path = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        if os.path.exists(orders_path):
            with open(orders_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    oid = row["order_id"]
                    cid = row["customer_id"]
                    row["customer_unique_id"] = cust_unique_map.get(cid, "")
                    self.orders[oid] = row
                    cuid = row["customer_unique_id"]
                    if cuid and cuid in self.customer_orders:
                        self.customer_orders[cuid].append(oid)

        # 3. Load Order Items
        items_path = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        if os.path.exists(items_path):
            with open(items_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    oid = row["order_id"]
                    if oid not in self.order_items:
                        self.order_items[oid] = []
                    self.order_items[oid].append(row)

        # 4. Load Order Payments
        payments_path = os.path.join(self.data_dir, "olist_order_payments_dataset.csv")
        if os.path.exists(payments_path):
            with open(payments_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    oid = row["order_id"]
                    if oid not in self.order_payments:
                        self.order_payments[oid] = []
                    self.order_payments[oid].append(row)

        # 5. Load Products
        products_path = os.path.join(self.data_dir, "olist_products_dataset.csv")
        if os.path.exists(products_path):
            with open(products_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.products[row["product_id"]] = row

        # 6. Load Sellers
        sellers_path = os.path.join(self.data_dir, "olist_sellers_dataset.csv")
        if os.path.exists(sellers_path):
            with open(sellers_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.sellers[row["seller_id"]] = row

    def parse_dt(self, dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str or dt_str.strip() == "":
            return None
        try:
            return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def analyze_case(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id, {})
        items = self.order_items.get(order_id, [])
        payments = self.order_payments.get(order_id, [])
        
        cuid = order.get("customer_unique_id", "")
        all_cust_orders = self.customer_orders.get(cuid, []) if cuid else []
        related_order_ids = [oid for oid in all_cust_orders if oid != order_id]

        # Product & Seller info
        product_ids = []
        category_names = []
        seller_ids = []
        
        # Preserve original array ordering without duplicates
        for item in items:
            pid = item.get("product_id")
            if pid and pid not in product_ids:
                product_ids.append(pid)
                prod = self.products.get(pid, {})
                cat = prod.get("product_category_name")
                if cat:
                    cat_en = self.category_translation.get(cat, cat)
                    if cat_en and cat_en not in category_names:
                        category_names.append(cat_en)
            
            sid = item.get("seller_id")
            if sid and sid not in seller_ids:
                seller_ids.append(sid)

        # Delivery Timestamps & Analysis
        delivered_at_str = order.get("order_delivered_customer_date")
        estimated_delivery_at_str = order.get("order_estimated_delivery_date")
        carrier_handoff_at_str = order.get("order_delivered_carrier_date")

        dt_delivered = self.parse_dt(delivered_at_str)
        dt_estimated = self.parse_dt(estimated_delivery_at_str)
        dt_carrier_handoff = self.parse_dt(carrier_handoff_at_str)

        delivery_variance_hours = None
        if dt_delivered and dt_estimated:
            delivery_variance_hours = round((dt_delivered - dt_estimated).total_seconds() / 3600.0, 2)

        # Seller handoff analysis
        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        if items:
            # Group items by seller to find earliest shipping limit for each seller
            seller_limits: Dict[str, List[datetime]] = {}
            for item in items:
                sid = item.get("seller_id")
                limit_str = item.get("shipping_limit_date")
                dt_limit = self.parse_dt(limit_str)
                if sid and dt_limit:
                    if sid not in seller_limits:
                        seller_limits[sid] = []
                    seller_limits[sid].append(dt_limit)

            for sid in seller_ids:
                limits = seller_limits.get(sid, [])
                if limits and dt_carrier_handoff:
                    earliest_limit = min(limits)
                    variance_h = round((dt_carrier_handoff - earliest_limit).total_seconds() / 3600.0, 2)
                    is_late = variance_h > 0
                    if is_late:
                        late_handoff_seller_ids.append(sid)
                    seller_handoff_analysis.append({
                        "seller_id": sid,
                        "shipping_limit_at": earliest_limit.strftime("%Y-%m-%d %H:%M:%S"),
                        "handoff_variance_hours": variance_h,
                        "late_handoff": is_late
                    })
                elif limits:
                    earliest_limit = min(limits)
                    seller_handoff_analysis.append({
                        "seller_id": sid,
                        "shipping_limit_at": earliest_limit.strftime("%Y-%m-%d %H:%M:%S"),
                        "handoff_variance_hours": None,
                        "late_handoff": False
                    })

        # Payment Reconciliation
        payment_ids = [f"{order_id}:{p.get('payment_sequential')}" for p in payments]
        payment_types = []
        for p in payments:
            ptype = p.get("payment_type")
            if ptype and ptype not in payment_types:
                payment_types.append(ptype)

        payment_total_brl = round(sum(float(p.get("payment_value", 0.0)) for p in payments), 2)

        if items:
            item_total_brl = round(sum(float(item.get("price", 0.0)) for item in items), 2)
            freight_total_brl = round(sum(float(item.get("freight_value", 0.0)) for item in items), 2)
            expected_total_brl = round(item_total_brl + freight_total_brl, 2)
            difference_brl = round(payment_total_brl - expected_total_brl, 2)
            reconciled = abs(difference_brl) <= 0.10
        else:
            item_total_brl = None
            freight_total_brl = None
            expected_total_brl = None
            difference_brl = None
            reconciled = None

        return {
            "order": order,
            "items": items,
            "payments": payments,
            "customer_unique_id": cuid,
            "related_order_ids": related_order_ids,
            "product_ids": product_ids,
            "category_names": category_names,
            "seller_ids": seller_ids,
            "delivery_analysis": {
                "delivered_at": delivered_at_str if delivered_at_str else None,
                "estimated_delivery_at": estimated_delivery_at_str if estimated_delivery_at_str else None,
                "carrier_handoff_at": carrier_handoff_at_str if carrier_handoff_at_str else None,
                "delivery_variance_hours": delivery_variance_hours,
                "seller_handoff_analysis": seller_handoff_analysis,
                "late_handoff_seller_ids": late_handoff_seller_ids
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": item_total_brl,
                "freight_total_brl": freight_total_brl,
                "expected_total_brl": expected_total_brl,
                "payment_total_brl": payment_total_brl,
                "difference_brl": difference_brl,
                "reconciled": reconciled,
                "payment_types": payment_types
            },
            "payment_ids": payment_ids
        }
