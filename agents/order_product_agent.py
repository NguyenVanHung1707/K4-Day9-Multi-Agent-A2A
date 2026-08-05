"""
Order & Product Agent — join order_items -> products -> sellers -> category
translation. Cũng phát hiện các secondary flag: multi_item_order,
multi_seller_order, multiple_categories.

Xử lý đúng case order 0 item (6/50 case thật là order_status=unavailable):
item/seller/product/category đều trả mảng rỗng, không suy diễn.
"""
from __future__ import annotations
import pandas as pd
from data_loader import OlistData

MAX_ITEM_IDS = 5
MAX_SELLER_IDS = 3
MAX_PRODUCT_IDS = 5
MAX_CATEGORY_NAMES = 5


def run(data: OlistData, order_id: str) -> dict:
    items_df = data.get_items(order_id)

    if items_df.empty:
        # README muc 4: chi expected_total_brl/difference_brl/reconciled phai
        # la null khi khong co item row. item_total_brl/freight_total_brl la
        # tong tren tap rong => 0.0, KHONG phai null (payment_agent.py dung
        # co "has_items" rieng de quyet dinh null-hoa 3 truong con lai).
        return {
            "items_df": items_df,
            "item_ids": [],
            "seller_ids": [],
            "product_ids": [],
            "category_names": [],
            "item_total_brl": 0.0,
            "freight_total_brl": 0.0,
            "has_items": False,
            "secondary_flags": {
                "multi_item_order": False,
                "multi_seller_order": False,
                "multiple_categories": False,
            },
        }

    item_ids = [f"{order_id}:{iid}" for iid in items_df.order_item_id.tolist()][:MAX_ITEM_IDS]
    seller_ids_all = items_df.seller_id.drop_duplicates().tolist()
    seller_ids = seller_ids_all[:MAX_SELLER_IDS]

    product_ids_all = items_df.product_id.drop_duplicates().tolist()
    product_ids = product_ids_all[:MAX_PRODUCT_IDS]

    # category_names lay TRUC TIEP cot products.product_category_name (tieng
    # Bo Dao Nha, nguyen ban trong CSV). KHONG dich sang tieng Anh qua
    # product_category_name_translation.csv: README muc 2 liet ke day du cac
    # khoa join can dung va KHONG he nhac toi file translation, nen gia tri
    # duoc cham gan nhu chac chan la gia tri goc trong cot CSV.
    products_df = data.get_products(product_ids_all)
    cat_map = dict(zip(products_df.product_id, products_df.product_category_name))
    categories_all = []
    for pid in product_ids_all:
        raw_cat = cat_map.get(pid)
        if raw_cat is not None and not pd.isna(raw_cat) and raw_cat not in categories_all:
            categories_all.append(raw_cat)
    category_names = categories_all[:MAX_CATEGORY_NAMES]

    item_total = round(float(items_df.price.sum()), 2)
    freight_total = round(float(items_df.freight_value.sum()), 2)

    return {
        "items_df": items_df,
        "item_ids": item_ids,
        "seller_ids": seller_ids,
        "product_ids": product_ids,
        "category_names": category_names,
        "item_total_brl": item_total,
        "freight_total_brl": freight_total,
        "has_items": True,
        "secondary_flags": {
            "multi_item_order": len(items_df) >= 2,
            "multi_seller_order": len(seller_ids_all) >= 2,
            "multiple_categories": len(categories_all) >= 2,
        },
    }
