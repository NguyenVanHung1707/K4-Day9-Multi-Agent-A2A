# Data Processing Module

## 📦 Overview

This module handles CSV to SQLite conversion and provides helper functions for querying the Olist database.

## 🚀 Quick Start

### 1. Setup Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Convert CSV to SQLite

```bash
python src/data_processing/csv_to_sqlite.py
```

**Output:**
- Creates `olist.db` (144 MB)
- 9 tables with 1.5M+ rows
- 11 indexes for fast querying

### 3. Test Database Connection

```bash
python src/data_processing/db_helper.py
```

## 📊 Database Schema

| Table | Rows | Description |
|---|---:|---|
| `orders` | 99,441 | Order information |
| `customers` | 99,441 | Customer details |
| `order_items` | 112,650 | Items in each order |
| `order_payments` | 103,886 | Payment transactions |
| `order_reviews` | 99,224 | Customer reviews |
| `products` | 32,951 | Product catalog |
| `sellers` | 3,095 | Seller information |
| `geolocation` | 1,000,163 | Geographic data |
| `category_translation` | 71 | Category name translations |

## 🔍 Indexes Created

- `orders`: order_id, customer_id
- `order_items`: order_id, product_id, seller_id
- `order_payments`: order_id
- `order_reviews`: order_id
- `customers`: customer_id, customer_unique_id
- `products`: product_id
- `sellers`: seller_id

## 💻 Usage Examples

### Basic Query

```python
from src.data_processing.db_helper import get_db

with get_db() as db:
    # Get order details
    order = db.get_order("9b75cdaf2d85857ef023980e15d01546")
    print(order)
    
    # Get order items
    items = db.get_order_items("9b75cdaf2d85857ef023980e15d01546")
    print(f"Found {len(items)} items")
    
    # Get payments
    payments = db.get_order_payments("9b75cdaf2d85857ef023980e15d01546")
    print(f"Total payment: {sum(p['payment_value'] for p in payments)}")
```

### Get Customer History

```python
with get_db() as db:
    # Get customer info
    customer = db.get_customer("1790ea7644578180c232ae2249ee4486")
    
    # Get customer's other orders
    customer_unique_id = customer['customer_unique_id']
    related_orders = db.get_customer_orders(
        customer_unique_id, 
        exclude_order_id="9b75cdaf2d85857ef023980e15d01546"
    )
    print(f"Customer has {len(related_orders)} other orders")
```

### Get Full Order Details

```python
with get_db() as db:
    full_details = db.get_full_order_details("9b75cdaf2d85857ef023980e15d01546")
    
    print("Order:", full_details['order']['order_status'])
    print("Customer:", full_details['customer']['customer_city'])
    print("Items:", len(full_details['items']))
    print("Payments:", len(full_details['payments']))
```

### Custom SQL Query

```python
with get_db() as db:
    # Raw SQL query
    df = db.query("""
        SELECT o.order_id, o.order_status, COUNT(oi.order_item_id) as item_count
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY o.order_id
        LIMIT 10
    """)
    print(df)
```

## ⚡ Performance

- **CSV approach:** ~5 seconds per case (loading CSVs each time)
- **SQLite approach:** ~0.1 seconds per case (indexed queries)
- **50 cases:** SQLite saves ~4 minutes!

## 🛠️ Files

- `csv_to_sqlite.py` - Converts CSV files to SQLite
- `db_helper.py` - Helper class for querying database
- `README.md` - This file
