import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(42)
AS_OF = date(2026, 11, 1)  # "today" for the data, so "overdue" is well defined
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sales.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
if os.path.exists(DB):
    os.remove(DB)

con = sqlite3.connect(DB)
cur = con.cursor()
cur.executescript("""
CREATE TABLE customers(customer_id INTEGER PRIMARY KEY, name TEXT, country TEXT, segment TEXT, signup_date TEXT);
CREATE TABLE products(product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, unit_price REAL);
CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(customer_id), order_date TEXT, status TEXT);
CREATE TABLE order_items(item_id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(order_id), product_id INTEGER REFERENCES products(product_id), quantity INTEGER);
CREATE TABLE invoices(invoice_id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(order_id), amount REAL, issued_date TEXT, due_date TEXT, paid_date TEXT);
""")

FIRST = ["Aarav", "Priya", "Karthik", "Meera", "Rahul", "Anita", "John", "Sara", "Liam", "Emma", "Noah", "Olivia", "Hans", "Mei"]
LAST = ["Kumar", "Sharma", "Iyer", "Reddy", "Smith", "Brown", "Miller", "Tan", "Wong", "Schmidt", "Patel", "Nair"]


def rand_date(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))


for i in range(1, 201):
    cur.execute("INSERT INTO customers VALUES (?,?,?,?,?)", (
        i, f"{random.choice(FIRST)} {random.choice(LAST)}",
        random.choice(["India", "USA", "UK", "Germany", "Singapore"]),
        random.choice(["Retail", "SMB", "Enterprise"]),
        rand_date(date(2022, 1, 1), date(2024, 12, 31)).isoformat()))

cats = ["Laptops", "Phones", "Accessories", "Software", "Audio"]
for i in range(1, 31):
    c = cats[(i - 1) % 5]
    cur.execute("INSERT INTO products VALUES (?,?,?,?)", (i, f"{c} Model {i}", c, round(random.uniform(10, 1500), 2)))
price = dict(cur.execute("SELECT product_id, unit_price FROM products").fetchall())

item_id = inv_id = 0
for oid in range(1, 1501):
    odate = rand_date(date(2025, 1, 1), date(2026, 10, 31))
    status = random.choices(["Completed", "Cancelled", "Pending"], [80, 10, 10])[0]
    cur.execute("INSERT INTO orders VALUES (?,?,?,?)", (oid, random.randint(1, 200), odate.isoformat(), status))
    total = 0.0
    for _ in range(random.randint(1, 4)):
        item_id += 1
        pid, qty = random.randint(1, 30), random.randint(1, 5)
        total += price[pid] * qty
        cur.execute("INSERT INTO order_items VALUES (?,?,?,?)", (item_id, oid, pid, qty))
    if status != "Cancelled":
        inv_id += 1
        due = odate + timedelta(days=30)
        pay = odate + timedelta(days=random.randint(0, 50)) if random.random() < 0.75 else None
        paid = pay.isoformat() if pay and pay <= AS_OF else None
        cur.execute("INSERT INTO invoices VALUES (?,?,?,?,?,?)",
                    (inv_id, oid, round(total, 2), odate.isoformat(), due.isoformat(), paid))

con.commit()
for t in ["customers", "products", "orders", "order_items", "invoices"]:
    print(t, cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("overdue invoices:", cur.execute(
    "SELECT COUNT(*) FROM invoices WHERE paid_date IS NULL AND due_date < ?", (AS_OF.isoformat(),)).fetchone()[0])
con.close()