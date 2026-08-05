import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional


class DataEngine:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.load_data()

    def load_data(self):
        orders_path = os.path.join(self.data_dir, "olist_orders_dataset.csv")
        customers_path = os.path.join(self.data_dir, "olist_customers_dataset.csv")
        items_path = os.path.join(self.data_dir, "olist_order_items_dataset.csv")
        payments_path = os.path.join(self.data_dir, "olist_order_payments_dataset.csv")
        products_path = os.path.join(self.data_dir, "olist_products_dataset.csv")
        sellers_path = os.path.join(self.data_dir, "olist_sellers_dataset.csv")
        translation_path = os.path.join(self.data_dir, "product_category_name_translation.csv")

        self.df_orders = pd.read_csv(orders_path)
        self.df_customers = pd.read_csv(customers_path)
        self.df_items = pd.read_csv(items_path)
        self.df_payments = pd.read_csv(payments_path)
        self.df_products = pd.read_csv(products_path)
        self.df_sellers = pd.read_csv(sellers_path)
        self.df_translation = pd.read_csv(translation_path)

        # Indexing for fast lookup
        self.orders_by_id = self.df_orders.set_index("order_id").to_dict("index")
        self.customers_by_id = self.df_customers.set_index("customer_id").to_dict("index")
        
        # Groupings
        self.items_by_order = self.df_items.groupby("order_id")
        self.payments_by_order = self.df_payments.groupby("order_id")
        self.products_by_id = self.df_products.set_index("product_id").to_dict("index")
        
        # Customer unique ID to order_ids map
        orders_with_cust = self.df_orders.merge(self.df_customers[['customer_id', 'customer_unique_id']], on='customer_id', how='left')
        self.orders_by_unique_cust = orders_with_cust.groupby("customer_unique_id")["order_id"].apply(list).to_dict()

        # Translation map
        self.category_translation = dict(zip(self.df_translation['product_category_name'], self.df_translation['product_category_name_english']))

    def parse_dt(self, dt_str: Any) -> Optional[datetime]:
        if pd.isna(dt_str) or not dt_str:
            return None
        try:
            return datetime.strptime(str(dt_str).strip(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def format_dt(self, dt_obj: Optional[datetime]) -> Optional[str]:
        if dt_obj is None:
            return None
        return dt_obj.strftime("%Y-%m-%d %H:%M:%S")

    def analyze_case_data(self, claimed_order_id: str) -> Dict[str, Any]:
        """
        Calculates all deterministic values for a given order_id according to Olist dataset & EC_POLICY_V2 rules.
        """
        order_row = self.orders_by_id.get(claimed_order_id)
        if not order_row:
            raise ValueError(f"Order ID {claimed_order_id} not found in orders dataset.")

        customer_id = order_row["customer_id"]
        order_status = order_row["order_status"]

        # Parse order timestamps
        delivered_at_dt = self.parse_dt(order_row.get("order_delivered_customer_date"))
        estimated_at_dt = self.parse_dt(order_row.get("order_estimated_delivery_date"))
        carrier_handoff_at_dt = self.parse_dt(order_row.get("order_delivered_carrier_date"))

        # Customer context
        cust_row = self.customers_by_id.get(customer_id, {})
        customer_unique_id = cust_row.get("customer_unique_id", "")
        all_cust_orders = self.orders_by_unique_cust.get(customer_unique_id, [])
        related_order_ids = [oid for oid in all_cust_orders if oid != claimed_order_id][:5]
        repeat_customer = len(related_order_ids) > 0

        # Items & Product context
        items_list = []
        if claimed_order_id in self.items_by_order.groups:
            items_df = self.items_by_order.get_group(claimed_order_id)
            items_list = items_df.to_dict("records")

        has_items = len(items_list) > 0

        item_ids = []
        product_ids = []
        category_names = []
        seller_ids_set = set()
        seller_ids_ordered = []

        item_total_brl = 0.0
        freight_total_brl = 0.0
        earliest_shipping_limit_dt: Optional[datetime] = None

        seller_shipping_limits: Dict[str, datetime] = {}

        for item in items_list:
            order_item_id = item["order_item_id"]
            pid = item["product_id"]
            sid = item["seller_id"]
            price = float(item["price"])
            freight = float(item["freight_value"])
            shipping_limit_dt = self.parse_dt(item["shipping_limit_date"])

            item_ids.append(f"{claimed_order_id}:{order_item_id}")
            if pid not in product_ids:
                product_ids.append(pid)
            if sid not in seller_ids_set:
                seller_ids_set.add(sid)
                seller_ids_ordered.append(sid)

            prod_row = self.products_by_id.get(pid, {})
            cat_name_pt = prod_row.get("product_category_name")
            if cat_name_pt and not pd.isna(cat_name_pt):
                # Primary: raw category_name from products.csv (e.g. beleza_saude)
                if cat_name_pt not in category_names:
                    category_names.append(cat_name_pt)

            item_total_brl += price
            freight_total_brl += freight

            if shipping_limit_dt:
                if sid not in seller_shipping_limits or shipping_limit_dt < seller_shipping_limits[sid]:
                    seller_shipping_limits[sid] = shipping_limit_dt
                if earliest_shipping_limit_dt is None or shipping_limit_dt < earliest_shipping_limit_dt:
                    earliest_shipping_limit_dt = shipping_limit_dt

        # Payments context
        payments_list = []
        if claimed_order_id in self.payments_by_order.groups:
            payments_df = self.payments_by_order.get_group(claimed_order_id)
            payments_list = payments_df.to_dict("records")

        payment_ids = []
        payment_types = []
        payment_total_brl = 0.0

        for pay in payments_list:
            seq = pay["payment_sequential"]
            ptype = pay["payment_type"]
            pval = float(pay["payment_value"])
            payment_ids.append(f"{claimed_order_id}:{seq}")
            if ptype not in payment_types:
                payment_types.append(ptype)
            payment_total_brl += pval

        # Calculations
        if has_items:
            expected_total_brl = round(item_total_brl + freight_total_brl, 2)
            item_total_brl_out = round(item_total_brl, 2)
            freight_total_brl_out = round(freight_total_brl, 2)
            payment_total_brl_out = round(payment_total_brl, 2)
            difference_brl = round(payment_total_brl_out - expected_total_brl, 2)
            reconciled = bool(abs(difference_brl) <= 0.10)
        else:
            expected_total_brl = None
            item_total_brl_out = None
            freight_total_brl_out = None
            payment_total_brl_out = round(payment_total_brl, 2)
            difference_brl = None
            reconciled = None

        # Delivery variance hours
        delivery_variance_hours = None
        if delivered_at_dt and estimated_at_dt:
            delivery_variance_hours = round((delivered_at_dt - estimated_at_dt).total_seconds() / 3600.0, 2)

        # Handoff variance & Seller analysis
        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        if has_items and carrier_handoff_at_dt:
            for sid in seller_ids_ordered:
                ship_lim_dt = seller_shipping_limits.get(sid)
                if ship_lim_dt:
                    variance_h = round((carrier_handoff_at_dt - ship_lim_dt).total_seconds() / 3600.0, 2)
                    is_late = carrier_handoff_at_dt > ship_lim_dt
                    seller_handoff_analysis.append({
                        "seller_id": sid,
                        "shipping_limit_at": self.format_dt(ship_lim_dt),
                        "handoff_variance_hours": variance_h,
                        "late_handoff": is_late
                    })
                    if is_late and sid not in late_handoff_seller_ids:
                        late_handoff_seller_ids.append(sid)

        # Flags for Policy Evaluation
        is_delivered_late = False
        if delivered_at_dt and estimated_at_dt and delivered_at_dt > estimated_at_dt:
            is_delivered_late = True

        multi_item_order = len(items_list) >= 2
        multi_seller_order = len(seller_ids_ordered) >= 2
        split_payment = len(payments_list) >= 2
        multiple_categories = len(category_names) >= 2

        return {
            "claimed_order_id": claimed_order_id,
            "order_status": order_status,
            "customer_context": {
                "customer_unique_id": customer_unique_id,
                "related_order_ids": related_order_ids[:5]
            },
            "product_context": {
                "product_ids": product_ids[:5],
                "category_names": category_names[:5]
            },
            "affected_entities": {
                "order_ids": [claimed_order_id][:5],
                "item_ids": item_ids[:5],
                "seller_ids": seller_ids_ordered[:3],
                "payment_ids": payment_ids[:5]
            },
            "delivery_analysis": {
                "delivered_at": self.format_dt(delivered_at_dt),
                "estimated_delivery_at": self.format_dt(estimated_at_dt),
                "carrier_handoff_at": self.format_dt(carrier_handoff_at_dt),
                "delivery_variance_hours": delivery_variance_hours,
                "seller_handoff_analysis": seller_handoff_analysis,
                "late_handoff_seller_ids": late_handoff_seller_ids
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": item_total_brl_out,
                "freight_total_brl": freight_total_brl_out,
                "expected_total_brl": expected_total_brl,
                "payment_total_brl": payment_total_brl_out,
                "difference_brl": difference_brl,
                "reconciled": reconciled,
                "payment_types": payment_types
            },
            "raw_flags": {
                "has_items": has_items,
                "is_delivered_late": is_delivered_late,
                "late_handoff_count": len(late_handoff_seller_ids),
                "multi_item_order": multi_item_order,
                "multi_seller_order": multi_seller_order,
                "split_payment": split_payment,
                "repeat_customer": repeat_customer,
                "multiple_categories": multiple_categories
            }
        }
