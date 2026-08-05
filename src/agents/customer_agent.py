"""
Customer Agent: Query customer information and history
"""

from typing import Dict, Any, List
from src.data_processing.db_helper import DatabaseHelper
from src.utils.config import MAX_RELATED_ORDER_IDS


class CustomerAgent:
    """Agent for customer context retrieval"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
    
    def investigate(self, order_id: str) -> Dict[str, Any]:
        """
        Investigate customer context for an order
        
        Args:
            order_id: Order ID to investigate
            
        Returns:
            Dict with customer_unique_id and related_order_ids
        """
        with DatabaseHelper(self.db_path) as db:
            # Get order to find customer_id
            order = db.get_order(order_id)
            if not order:
                return {
                    "customer_unique_id": None,
                    "related_order_ids": []
                }
            
            # Get customer info
            customer = db.get_customer(order['customer_id'])
            if not customer:
                return {
                    "customer_unique_id": None,
                    "related_order_ids": []
                }
            
            customer_unique_id = customer['customer_unique_id']
            
            # Get related orders (exclude current order)
            related_orders = db.get_customer_orders(
                customer_unique_id, 
                exclude_order_id=order_id
            )
            
            # Limit to MAX_RELATED_ORDER_IDS
            related_orders = related_orders[:MAX_RELATED_ORDER_IDS]
            
            return {
                "customer_unique_id": customer_unique_id,
                "related_order_ids": related_orders
            }


if __name__ == "__main__":
    # Test customer agent
    agent = CustomerAgent()
    result = agent.investigate("9b75cdaf2d85857ef023980e15d01546")
    print("Customer Agent Result:")
    print(f"  customer_unique_id: {result['customer_unique_id']}")
    print(f"  related_order_ids: {len(result['related_order_ids'])} orders")
