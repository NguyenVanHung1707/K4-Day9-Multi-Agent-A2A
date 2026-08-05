"""
CSV to SQLite Converter
Converts all CSV files in data/ folder to SQLite database with proper indexing.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import time


class CSVToSQLiteConverter:
    """Convert CSV files to SQLite database with optimized indexing"""
    
    def __init__(self, data_folder="data", db_path="olist.db"):
        self.data_folder = Path(data_folder)
        self.db_path = Path(db_path)
        self.conn = None
        
    def connect(self):
        """Connect to SQLite database"""
        self.conn = sqlite3.connect(self.db_path)
        print(f"✅ Connected to SQLite: {self.db_path}")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print(f"✅ Database connection closed")
    
    def import_csv(self, csv_file: Path, table_name: str):
        """Import a single CSV file to SQLite table"""
        print(f"\n📂 Importing: {csv_file.name}")
        
        # Read CSV
        start = time.time()
        df = pd.read_csv(csv_file)
        rows = len(df)
        cols = len(df.columns)
        
        print(f"   - Rows: {rows:,} | Columns: {cols}")
        
        # Import to SQLite
        df.to_sql(table_name, self.conn, if_exists='replace', index=False)
        
        elapsed = time.time() - start
        print(f"   ✅ Imported in {elapsed:.2f}s")
        
        return rows
    
    def create_indexes(self):
        """Create indexes on key columns for fast querying"""
        print("\n🔍 Creating indexes...")
        
        indexes = [
            # Orders table - most queried
            ("idx_orders_order_id", "orders", "order_id"),
            ("idx_orders_customer_id", "orders", "customer_id"),
            
            # Order items - join with orders
            ("idx_items_order_id", "order_items", "order_id"),
            ("idx_items_product_id", "order_items", "product_id"),
            ("idx_items_seller_id", "order_items", "seller_id"),
            
            # Payments - join with orders
            ("idx_payments_order_id", "order_payments", "order_id"),
            
            # Reviews - join with orders
            ("idx_reviews_order_id", "order_reviews", "order_id"),
            
            # Customers - lookup
            ("idx_customers_customer_id", "customers", "customer_id"),
            ("idx_customers_unique_id", "customers", "customer_unique_id"),
            
            # Products - lookup
            ("idx_products_product_id", "products", "product_id"),
            
            # Sellers - lookup
            ("idx_sellers_seller_id", "sellers", "seller_id"),
            
            # Geolocation - optional (skip if not used)
            # ("idx_geo_zip", "geolocation", "geolocation_zip_code_prefix"),
        ]
        
        cursor = self.conn.cursor()
        
        for idx_name, table, column in tqdm(indexes, desc="Creating indexes"):
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                self.conn.commit()
            except Exception as e:
                print(f"   ⚠️ Failed to create index {idx_name}: {e}")
        
        print(f"   ✅ Created {len(indexes)} indexes")
    
    def convert_all(self):
        """Convert all CSV files to SQLite"""
        self.connect()
        
        # Define table mappings (CSV filename -> table name)
        csv_mappings = {
            "olist_orders_dataset.csv": "orders",
            "olist_customers_dataset.csv": "customers",
            "olist_order_items_dataset.csv": "order_items",
            "olist_order_payments_dataset.csv": "order_payments",
            "olist_order_reviews_dataset.csv": "order_reviews",
            "olist_products_dataset.csv": "products",
            "olist_sellers_dataset.csv": "sellers",
            "olist_geolocation_dataset.csv": "geolocation",
            "product_category_name_translation.csv": "category_translation",
        }
        
        total_rows = 0
        
        print("=" * 80)
        print("🚀 Converting CSV files to SQLite")
        print("=" * 80)
        
        # Import each CSV
        for csv_name, table_name in csv_mappings.items():
            csv_path = self.data_folder / csv_name
            if csv_path.exists():
                rows = self.import_csv(csv_path, table_name)
                total_rows += rows
            else:
                print(f"⚠️ File not found: {csv_name}")
        
        # Create indexes
        self.create_indexes()
        
        # Summary
        print("\n" + "=" * 80)
        print(f"✅ Conversion complete!")
        print(f"   - Total rows imported: {total_rows:,}")
        print(f"   - Database size: {self.db_path.stat().st_size / 1024 / 1024:.2f} MB")
        print("=" * 80)
        
        self.close()
    
    def verify_database(self):
        """Verify database integrity and show table stats"""
        self.connect()
        cursor = self.conn.cursor()
        
        print("\n" + "=" * 80)
        print("📊 Database Statistics")
        print("=" * 80)
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"{table_name:<30} {count:>12,} rows")
        
        print("=" * 80)
        
        self.close()


def main():
    """Main entry point"""
    converter = CSVToSQLiteConverter(data_folder="data", db_path="olist.db")
    
    # Convert all CSVs
    converter.convert_all()
    
    # Verify
    converter.verify_database()


if __name__ == "__main__":
    main()
