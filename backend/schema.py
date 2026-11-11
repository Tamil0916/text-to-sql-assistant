import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sales.db")
AS_OF = "2026-11-01"  # "today" for this dataset


def get_schema(db_path=DB_PATH):
    con = sqlite3.connect(db_path)
    parts = []
    tables = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for (name,) in tables:
        cols = con.execute(f"PRAGMA table_info({name})").fetchall()
        col_txt = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        sample = con.execute(f"SELECT * FROM {name} LIMIT 2").fetchall()
        parts.append(f"TABLE {name}({col_txt})\n  example rows: {sample}")
    con.close()
    return "\n".join(parts)