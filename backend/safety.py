import sqlite3
import time
from pathlib import Path

import pandas as pd
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError


class UnsafeSQL(Exception):
    pass


class MalformedSQL(UnsafeSQL):
    """SQL that could not be parsed. Not dangerous, so the agent may ask the model to fix it."""


BLOCKED = {"Insert", "Update", "Delete", "Drop", "Create", "Alter", "AlterTable", "Command", "Pragma",
           "Attach", "Detach", "Merge", "Copy", "TruncateTable", "Transaction", "Commit", "Rollback"}


def validate(sql):
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise UnsafeSQL("Empty query")
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except (ParseError, TokenError) as e:
        raise MalformedSQL(f"Could not parse the SQL: {e}")
    if len(statements) != 1:
        raise UnsafeSQL("Only one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise UnsafeSQL("Only SELECT queries are allowed")
    for node in tree.find_all(exp.Expression):
        if type(node).__name__ in BLOCKED:
            raise UnsafeSQL(f"{type(node).__name__} is not allowed")
    return sql


def run_query(sql, db_path, max_rows=200, timeout=5.0):
    sql = validate(sql)
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"  # read-only connection
    con = sqlite3.connect(uri, uri=True)
    deadline = time.time() + timeout
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
        cols = [d[0] for d in cur.description]
    finally:
        con.close()
    truncated = len(rows) > max_rows
    return pd.DataFrame(rows[:max_rows], columns=cols), truncated, sql