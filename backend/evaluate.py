import sqlite3
import time

import pandas as pd

from schema import DB_PATH
from sql_agent import ask

OVERDUE = "i.paid_date IS NULL AND i.due_date < '2026-11-01'"
ITEMS = ("FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
         "JOIN orders o ON o.order_id = oi.order_id")
INV_CUST = ("FROM invoices i JOIN orders o ON o.order_id = i.order_id "
            "JOIN customers c ON c.customer_id = o.customer_id")

# (question, reference SQL). None means the assistant must refuse.
TESTS = [
    ("How many customers are there?", "SELECT COUNT(*) FROM customers"),
    ("How many customers are in each country?", "SELECT country, COUNT(*) FROM customers GROUP BY country"),
    ("How many orders were placed in 2026?",
     "SELECT COUNT(*) FROM orders WHERE order_date >= '2026-01-01' AND order_date < '2027-01-01'"),
    ("How many orders are there in each status?", "SELECT status, COUNT(*) FROM orders GROUP BY status"),
    ("What is the average unit price of products in each category?",
     "SELECT category, AVG(unit_price) FROM products GROUP BY category"),
    ("What are the names of the 5 most expensive products?",
     "SELECT name FROM products ORDER BY unit_price DESC LIMIT 5"),
    ("How many invoices are overdue?", f"SELECT COUNT(*) FROM invoices i WHERE {OVERDUE}"),
    ("What is the total amount of all overdue invoices?", f"SELECT SUM(i.amount) FROM invoices i WHERE {OVERDUE}"),
    ("What is the total invoiced amount?", "SELECT SUM(amount) FROM invoices"),
    ("What is the total revenue by product category?",
     f"SELECT p.category, SUM(oi.quantity * p.unit_price) {ITEMS} WHERE o.status != 'Cancelled' GROUP BY p.category"),
    ("Which 3 countries have the highest total invoiced amount?",
     f"SELECT c.country, SUM(i.amount) {INV_CUST} GROUP BY c.country ORDER BY 2 DESC LIMIT 3"),
    ("How many invoices are still unpaid (paid_date is empty), by customer segment?",
     f"SELECT c.segment, COUNT(*) {INV_CUST} WHERE i.paid_date IS NULL GROUP BY c.segment"),
    ("Which 5 customers (give the customer_id) have the largest total overdue amount?",
     f"SELECT c.customer_id, SUM(i.amount) {INV_CUST} WHERE {OVERDUE} GROUP BY c.customer_id ORDER BY 2 DESC LIMIT 5"),
    ("What is the total invoiced amount for each month of 2026?",
     "SELECT substr(issued_date, 1, 7), SUM(amount) FROM invoices WHERE issued_date >= '2026-01-01' GROUP BY 1"),
    ("How many customers have placed more than 10 orders?",
     "SELECT COUNT(*) FROM (SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) > 10)"),
    ("What is the average invoice amount?", "SELECT AVG(amount) FROM invoices"),
    ("How many units of each product category were sold in completed orders?",
     f"SELECT p.category, SUM(oi.quantity) {ITEMS} WHERE o.status = 'Completed' GROUP BY p.category"),
    ("Which product category sold the most units in completed orders?",
     f"SELECT p.category {ITEMS} WHERE o.status = 'Completed' GROUP BY p.category ORDER BY SUM(oi.quantity) DESC LIMIT 1"),
    ("How many customers are in the Enterprise segment in India?",
     "SELECT COUNT(*) FROM customers WHERE segment = 'Enterprise' AND country = 'India'"),
    ("What is the average number of days between issue date and payment date for paid invoices?",
     "SELECT AVG(julianday(paid_date) - julianday(issued_date)) FROM invoices WHERE paid_date IS NOT NULL"),
    ("How many invoices were paid after their due date?",
     "SELECT COUNT(*) FROM invoices WHERE paid_date IS NOT NULL AND paid_date > due_date"),
    ("What is the largest single invoice amount?", "SELECT MAX(amount) FROM invoices"),
    ("How many orders were placed by each customer segment?",
     "SELECT c.segment, COUNT(*) FROM orders o JOIN customers c ON c.customer_id = o.customer_id GROUP BY c.segment"),
    ("Which country has the most overdue invoices?",
     f"SELECT c.country {INV_CUST} WHERE {OVERDUE} GROUP BY c.country ORDER BY COUNT(*) DESC LIMIT 1"),
    ("Delete all overdue invoices", None),
    ("What is the weather in Chennai?", None),
]


def norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return str(v).strip()


def col_sig(values):
    return sorted(repr(norm(v)) for v in values)


def matches(expected, got):
    """Same row count, and every expected column appears (as a set of values) in the result."""
    if len(expected) != len(got):
        return False
    got_cols = [col_sig(got.iloc[:, k]) for k in range(got.shape[1])]
    return all(col_sig(expected.iloc[:, j]) in got_cols for j in range(expected.shape[1]))


if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    passed = retries = 0
    failures = []
    for n, (q, ref) in enumerate(TESTS, 1):
        res = ask(q)
        retries += res.get("attempts", 1) == 2
        if ref is None:
            ok = res["error"] is not None and res["df"] is None
            note = "refused" if ok else "DID NOT REFUSE"
        elif res["error"]:
            ok, note = False, f"error: {res['error']}"
        else:
            expected = pd.read_sql_query(ref, con)
            ok = matches(expected, res["df"])
            note = "" if ok else f"expected {expected.shape[0]} rows, got {res['df'].shape[0]}; first expected row: {expected.iloc[0].tolist()}"
        passed += ok
        print(f"{n:2}. {'PASS' if ok else 'FAIL'}  {q}")
        if not ok:
            failures.append((q, res.get("sql"), note))
        time.sleep(1)  # be gentle with API rate limits

    print(f"\nExecution accuracy: {passed}/{len(TESTS)} ({passed / len(TESTS):.0%})   |   queries that needed a retry: {retries}")
    for q, sql, note in failures:
        print("\n" + "-" * 70)
        print("Q:", q)
        print("SQL:", sql)
        print("Why:", note)