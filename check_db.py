import sqlite3

conn = sqlite3.connect('olist.db')
cur = conn.cursor()

print("=== EC_001 Order Items ===")
cur.execute('''
    SELECT oi.order_item_id, oi.product_id, p.product_category_name
    FROM order_items oi
    LEFT JOIN products p ON oi.product_id = p.product_id
    WHERE oi.order_id = '9b75cdaf2d85857ef023980e15d01546'
    ORDER BY oi.order_item_id
''')
for row in cur.fetchall():
    print(f"Item {row[0]}: product={row[1]}, category={row[2]}")

print("\n=== Category Translation ===")
cur.execute('''
    SELECT product_category_name, product_category_name_english
    FROM category_translation
    WHERE product_category_name = 'beleza_saude'
''')
for row in cur.fetchall():
    print(f"Portuguese: {row[0]} -> English: {row[1]}")

conn.close()
