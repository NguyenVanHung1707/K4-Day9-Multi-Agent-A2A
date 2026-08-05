"""
Database Helper
Provides easy-to-use functions for querying SQLite database.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any


class DatabaseHelper:
    """Helper class for querying Olist SQLite database"""
    
    def __init__(self, db_path="olist.db"):
        self.db_path = Path(db_path)
        self.conn = None
        
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        
    def connect(self):
        """Connect to database"""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {self.db_path}\n"
                "Run 'python src/data_processing/csv_to_sqlite.py' first!"
            )
        self.conn = sqlite3.connect(self.db_path)
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame"""
        if params:
            return pd.read_sql_query(sql, self.conn, params=params)
        return pd.read_sql_query(sql, self.conn)
    
    # ==================== Order Queries ====================
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order details by order_id"""
        sql = "SELECT * FROM orders WHERE order_id = ?"
        df = self.query(sql, (order_id,))
        return df.to_dict('records')[0] if not df.empty else None
    
    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        """Get all items for an order"""
        sql = "SELECT * FROM order_items WHERE order_id = ? ORDER BY order_item_id"
        df = self.query(sql, (order_id,))
        return df.to_dict('records')
    
    def get_order_payments(self, order_id: str) -> List[Dict[str, Any]]:
        """Get all payments for an order"""
        sql = "SELECT * FROM order_payments WHERE order_id = ? ORDER BY payment_sequential"
        df = self.query(sql, (order_id,))
        return df.to_dict('records')
    
    def get_order_reviews(self, order_id: str) -> List[Dict[str, Any]]:
        """Get reviews for an order"""
        sql = "SELECT * FROM order_reviews WHERE order_id = ?"
        df = self.query(sql, (order_id,))
        return df.to_dict('records')
    
    # ==================== Customer Queries ====================
    
    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer details by customer_id"""
        sql = "SELECT * FROM customers WHERE customer_id = ?"
        df = self.query(sql, (customer_id,))
        return df.to_dict('records')[0] if not df.empty else None
    
    def get_customer_orders(self, customer_unique_id: str, exclude_order_id: Optional[str] = None) -> List[str]:
        """Get all order IDs for a customer (by customer_unique_id)"""
        if exclude_order_id:
            sql = """
                SELECT o.order_id 
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE c.customer_unique_id = ? AND o.order_id != ?
                ORDER BY o.order_purchase_timestamp DESC
            """
            df = self.query(sql, (customer_unique_id, exclude_order_id))
        else:
            sql = """
                SELECT o.order_id 
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE c.customer_unique_id = ?
                ORDER BY o.order_purchase_timestamp DESC
            """
            df = self.query(sql, (customer_unique_id,))
        
        return df['order_id'].tolist()
    
    # ==================== Product Queries ====================
    
    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details"""
        sql = "SELECT * FROM products WHERE product_id = ?"
        df = self.query(sql, (product_id,))
        return df.to_dict('records')[0] if not df.empty else None
    
    def get_category_translation(self, category_name: str) -> Optional[str]:
        """Translate category name to English"""
        sql = "SELECT product_category_name_english FROM category_translation WHERE product_category_name = ?"
        df = self.query(sql, (category_name,))
        return df['product_category_name_english'].iloc[0] if not df.empty else None
    
    # ==================== Seller Queries ====================
    
    def get_seller(self, seller_id: str) -> Optional[Dict[str, Any]]:
        """Get seller details"""
        sql = "SELECT * FROM sellers WHERE seller_id = ?"
        df = self.query(sql, (seller_id,))
        return df.to_dict('records')[0] if not df.empty else None
    
    # ==================== Complex Queries ====================
    
    def get_full_order_details(self, order_id: str) -> Dict[str, Any]:
        """Get complete order information with all related data"""
        return {
            "order": self.get_order(order_id),
            "customer": self.get_customer(self.get_order(order_id)['customer_id']) if self.get_order(order_id) else None,
            "items": self.get_order_items(order_id),
            "payments": self.get_order_payments(order_id),
            "reviews": self.get_order_reviews(order_id),
        }
    
    def get_order_with_products(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order items with product details"""
        sql = """
            SELECT 
                oi.*,
                p.product_category_name,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                ct.product_category_name_english
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
            WHERE oi.order_id = ?
            ORDER BY oi.order_item_id
        """
        df = self.query(sql, (order_id,))
        return df.to_dict('records')


# ==================== Convenience Functions ====================

def get_db() -> DatabaseHelper:
    """Get a database helper instance (use with context manager)"""
    return DatabaseHelper()


def test_connection():
    """Test database connection and show sample data"""
    print("Testing database connection...")
    
    with get_db() as db:
        # Test order query
        print("\n✅ Testing order query:")
        order = db.get_order("9b75cdaf2d85857ef023980e15d01546")
        if order:
            print(f"   Order ID: {order['order_id']}")
            print(f"   Status: {order['order_status']}")
            print(f"   Customer ID: {order['customer_id']}")
        
        # Test items query
        print("\n✅ Testing items query:")
        items = db.get_order_items("9b75cdaf2d85857ef023980e15d01546")
        print(f"   Found {len(items)} items")
        
        # Test payments query
        print("\n✅ Testing payments query:")
        payments = db.get_order_payments("9b75cdaf2d85857ef023980e15d01546")
        print(f"   Found {len(payments)} payments")
        
        print("\n✅ Database connection successful!")


if __name__ == "__main__":
    test_connection()
