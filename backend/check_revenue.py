import sqlite3

from schema import DB_PATH

con = sqlite3.connect(DB_PATH)
total_inv = con.execute("SELECT SUM(amount) FROM invoices").fetchone()[0]
print("Total invoiced:", round(total_inv, 2))
print("Revenue by category, computed correctly from items:")
rows = con.execute("""
    SELECT p.category, ROUND(SUM(oi.quantity * p.unit_price), 2)
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.status != 'Cancelled'
    GROUP BY p.category ORDER BY 1
""").fetchall()
for r in rows:
    print(" ", r)
print("Sum of those:", round(sum(r[1] for r in rows), 2))