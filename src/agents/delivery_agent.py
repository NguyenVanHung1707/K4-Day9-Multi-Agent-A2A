"""
Delivery Agent: Delivery timeline analysis
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.data_processing.db_helper import DatabaseHelper
from src.utils.config import DECIMAL_PLACES


class DeliveryAgent:
    """Agent for delivery timeline analysis"""
    
    def __init__(self, db_path: str = "olist.db"):
        self.db_path = db_path
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        if not timestamp_str or timestamp_str == '' or str(timestamp_str).lower() == 'none':
            return None
        try:
            return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None
    
    def _calculate_hours_diff(self, dt1: Optional[datetime], dt2: Optional[datetime]) -> Optional[float]:
        """Calculate hours difference between two datetimes"""
        if dt1 is None or dt2 is None:
            return None
        diff_seconds = (dt1 - dt2).total_seconds()
        hours = diff_seconds / 3600
        return round(hours, DECIMAL_PLACES)
    
    def investigate(self, order_id: str, items_raw: List[Dict]) -> Dict[str, Any]:
        """
        Investigate delivery timeline and seller handoff
        
        Args:
            order_id: Order ID to investigate
            items_raw: Raw items data from OrderAgent
            
        Returns:
            Dict with delivery_analysis
        """
        with DatabaseHelper(self.db_path) as db:
            # Get order delivery info
            order = db.get_order(order_id)
            if not order:
                return self._empty_result()
            
            # Parse timestamps
            delivered_at = self._parse_timestamp(order.get('order_delivered_customer_date'))
            estimated_at = self._parse_timestamp(order.get('order_estimated_delivery_date'))
            carrier_handoff_at = self._parse_timestamp(order.get('order_delivered_carrier_date'))
            
            # Calculate delivery variance
            delivery_variance_hours = self._calculate_hours_diff(delivered_at, estimated_at)
            
            # Analyze seller handoff for each item
            seller_handoff_analysis = []
            late_handoff_seller_ids = []
            
            if carrier_handoff_at and items_raw:
                # Group items by seller
                sellers_seen = {}
                for item in items_raw:
                    seller_id = item['seller_id']
                    if seller_id not in sellers_seen:
                        shipping_limit_at = self._parse_timestamp(item.get('shipping_limit_date'))
                        handoff_variance_hours = self._calculate_hours_diff(
                            carrier_handoff_at, 
                            shipping_limit_at
                        )
                        late_handoff = handoff_variance_hours > 0 if handoff_variance_hours is not None else False
                        
                        seller_handoff_analysis.append({
                            "seller_id": seller_id,
                            "shipping_limit_at": item.get('shipping_limit_date'),
                            "handoff_variance_hours": handoff_variance_hours,
                            "late_handoff": late_handoff
                        })
                        
                        if late_handoff:
                            late_handoff_seller_ids.append(seller_id)
                        
                        sellers_seen[seller_id] = True
            
            return {
                "delivery_analysis": {
                    "delivered_at": order.get('order_delivered_customer_date'),
                    "estimated_delivery_at": order.get('order_estimated_delivery_date'),
                    "carrier_handoff_at": order.get('order_delivered_carrier_date'),
                    "delivery_variance_hours": delivery_variance_hours,
                    "seller_handoff_analysis": seller_handoff_analysis,
                    "late_handoff_seller_ids": late_handoff_seller_ids
                }
            }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when order not found"""
        return {
            "delivery_analysis": {
                "delivered_at": None,
                "estimated_delivery_at": None,
                "carrier_handoff_at": None,
                "delivery_variance_hours": None,
                "seller_handoff_analysis": [],
                "late_handoff_seller_ids": []
            }
        }


if __name__ == "__main__":
    # Test delivery agent
    from src.agents.order_agent import OrderAgent
    
    order_agent = OrderAgent()
    order_result = order_agent.investigate("9b75cdaf2d85857ef023980e15d01546")
    
    delivery_agent = DeliveryAgent()
    result = delivery_agent.investigate(
        "9b75cdaf2d85857ef023980e15d01546",
        order_result['items_raw']
    )
    
    print("Delivery Agent Result:")
    analysis = result['delivery_analysis']
    print(f"  delivered_at: {analysis['delivered_at']}")
    print(f"  estimated_at: {analysis['estimated_delivery_at']}")
    print(f"  delivery_variance: {analysis['delivery_variance_hours']} hours")
    print(f"  late_handoff_sellers: {len(analysis['late_handoff_seller_ids'])} sellers")
    for handoff in analysis['seller_handoff_analysis']:
        print(f"    Seller {handoff['seller_id']}: {handoff['handoff_variance_hours']} hours (late: {handoff['late_handoff']})")
