import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from safety import MalformedSQL, UnsafeSQL, run_query, validate


@pytest.mark.parametrize("sql", [
    "SELECT * FROM customers",
    "SELECT 1 UNION SELECT 2",
    "WITH t AS (SELECT 1 AS a) SELECT a FROM t",
    "SELECT * FROM customers;",
])
def test_select_queries_are_allowed(sql):
    assert validate(sql)


@pytest.mark.parametrize("sql", [
    "DROP TABLE customers",
    "DELETE FROM invoices",
    "UPDATE invoices SET amount = 0",
    "INSERT INTO customers VALUES (1, 'x', 'y', 'z', '2020-01-01')",
    "PRAGMA table_info(customers)",
    "SELECT 1; DROP TABLE customers",
    "",
])
def test_dangerous_or_invalid_sql_is_blocked(sql):
    with pytest.raises(UnsafeSQL):
        validate(sql)


def test_row_limit_truncates_results(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t(a INTEGER)")
    con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(10)])
    con.commit()
    con.close()
    df, truncated, _ = run_query("SELECT * FROM t", str(db), max_rows=5)
    assert len(df) == 5 and truncated

BAD_SQL = """SELECT i.customer_id
FROM (
    SELECT o.customer_id, SUM(i.amount) AS total_overdue
    FROM invoices i
    JOIN orders o ON i.order_id = o.order_id
    WHERE i.paid_date IS NULL
      AND i.due_date < '2026-11-01'
    GROUP BY o.customer_id
    ORDER BY total_overdue DESC
    LIMIT 5
) AS sub
JOIN customers c ON c.customer_id = sub.customer_id
SELECT sub.customer_id FROM sub;"""


def test_malformed_sql_is_reported_as_malformed():
    with pytest.raises(MalformedSQL):
        validate(BAD_SQL)