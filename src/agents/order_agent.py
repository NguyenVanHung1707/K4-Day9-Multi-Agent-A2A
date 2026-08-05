"""
Order Agent: Query order, items, products, sellers
"""

from typing import Dict, Any, List
from src.data_processing.db_helper import DatabaseHelper
from src.utils.config import (
    MAX_ORDER_IDS, MAX_ITEM_IDS, MAX_SELLER_IDS, 
    MAX_PRODUCT_IDS, MAX_CATEGORY_NAMES
)


class OrderAgent:
    """Agent for order and product context retrieval"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
    
    def investigate(self, order_id: str) -> Dict[str, Any]:
        """
        Investigate order, items, products, and sellers
        
        Args:
            order_id: Order ID to investigate
            
        Returns:
            Dict with affected_entities and product_context
        """
        with DatabaseHelper(self.db_path) as db:
            # Get order items with product details
            items = db.get_order_with_products(order_id)
            
            if not items:
                return {
                    "affected_entities": {
                        "order_ids": [order_id],
                        "item_ids": [],
                        "seller_ids": [],
                    },
                    "product_context": {
                        "product_ids": [],
                        "category_names": []
                    },
                    "items_raw": []
                }
            
            # Build item_ids
            item_ids = [
                f"{order_id}:{item['order_item_id']}" 
                for item in items
            ][:MAX_ITEM_IDS]
            
            # Get unique sellers
            seller_ids = list(set(item['seller_id'] for item in items))[:MAX_SELLER_IDS]
            
            # Get unique products
            product_ids = list(set(item['product_id'] for item in items))[:MAX_PRODUCT_IDS]
            
            # Get unique categories (English names)
            category_names = []
            for item in items:
                cat_name = item.get('product_category_name_english')
                if cat_name and cat_name not in category_names:
                    category_names.append(cat_name)
            category_names = category_names[:MAX_CATEGORY_NAMES]
            
            return {
                "affected_entities": {
                    "order_ids": [order_id][:MAX_ORDER_IDS],
                    "item_ids": item_ids,
                    "seller_ids": seller_ids,
                },
                "product_context": {
                    "product_ids": product_ids,
                    "category_names": category_names
                },
                "items_raw": items  # Keep raw data for other agents
            }


if __name__ == "__main__":
    # Test order agent
    agent = OrderAgent()
    result = agent.investigate("9b75cdaf2d85857ef023980e15d01546")
    print("Order Agent Result:")
    print(f"  order_ids: {result['affected_entities']['order_ids']}")
    print(f"  item_ids: {len(result['affected_entities']['item_ids'])} items")
    print(f"  seller_ids: {len(result['affected_entities']['seller_ids'])} sellers")
    print(f"  product_ids: {len(result['product_context']['product_ids'])} products")
    print(f"  categories: {result['product_context']['category_names']}")
