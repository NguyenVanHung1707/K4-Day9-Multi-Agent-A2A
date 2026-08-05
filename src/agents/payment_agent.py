"""
Payment Agent: Payment reconciliation and validation
"""

from typing import Dict, Any, List
from src.data_processing.db_helper import DatabaseHelper
from src.utils.config import (
    MAX_PAYMENT_IDS, 
    PAYMENT_RECONCILIATION_TOLERANCE,
    DECIMAL_PLACES
)


class PaymentAgent:
    """Agent for payment reconciliation"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
    
    def investigate(self, order_id: str, items_raw: List[Dict]) -> Dict[str, Any]:
        """
        Investigate payment reconciliation
        
        Args:
            order_id: Order ID to investigate
            items_raw: Raw items data from OrderAgent
            
        Returns:
            Dict with payment_reconciliation and payment_ids
        """
        with DatabaseHelper(self.db_path) as db:
            # Get all payments
            payments = db.get_order_payments(order_id)
            
            # Build payment_ids
            payment_ids = [
                f"{order_id}:{payment['payment_sequential']}" 
                for payment in payments
            ][:MAX_PAYMENT_IDS]
            
            # Get payment types
            payment_types = list(set(p['payment_type'] for p in payments))
            
            # Calculate totals
            payment_total_brl = sum(p['payment_value'] for p in payments)
            payment_total_brl = round(payment_total_brl, DECIMAL_PLACES)
            
            # Calculate expected total from items
            if items_raw:
                item_total_brl = sum(item['price'] for item in items_raw)
                freight_total_brl = sum(item['freight_value'] for item in items_raw)
                expected_total_brl = item_total_brl + freight_total_brl
                
                item_total_brl = round(item_total_brl, DECIMAL_PLACES)
                freight_total_brl = round(freight_total_brl, DECIMAL_PLACES)
                expected_total_brl = round(expected_total_brl, DECIMAL_PLACES)
                
                difference_brl = payment_total_brl - expected_total_brl
                difference_brl = round(difference_brl, DECIMAL_PLACES)
                
                reconciled = abs(difference_brl) <= PAYMENT_RECONCILIATION_TOLERANCE
            else:
                # No items -> set to null
                item_total_brl = None
                freight_total_brl = None
                expected_total_brl = None
                difference_brl = None
                reconciled = None
            
            return {
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
                "payment_ids": payment_ids,
                "payments_raw": payments  # Keep raw data for policy engine
            }


if __name__ == "__main__":
    # Test payment agent
    from src.agents.order_agent import OrderAgent
    
    order_agent = OrderAgent()
    order_result = order_agent.investigate("9b75cdaf2d85857ef023980e15d01546")
    
    payment_agent = PaymentAgent()
    result = payment_agent.investigate(
        "9b75cdaf2d85857ef023980e15d01546",
        order_result['items_raw']
    )
    
    print("Payment Agent Result:")
    recon = result['payment_reconciliation']
    print(f"  item_total: {recon['item_total_brl']} BRL")
    print(f"  freight_total: {recon['freight_total_brl']} BRL")
    print(f"  expected_total: {recon['expected_total_brl']} BRL")
    print(f"  payment_total: {recon['payment_total_brl']} BRL")
    print(f"  difference: {recon['difference_brl']} BRL")
    print(f"  reconciled: {recon['reconciled']}")
    print(f"  payment_ids: {len(result['payment_ids'])} payments")
