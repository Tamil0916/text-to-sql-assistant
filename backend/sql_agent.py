import os
import re
import sqlite3

from dotenv import load_dotenv
from groq import Groq

from safety import UnsafeSQL, run_query
from schema import AS_OF, DB_PATH, get_schema

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM = """You are a careful data analyst who writes SQLite SQL.
Rules:
- Output ONLY one SQL SELECT query. No explanation, no markdown.
- Use only the tables and columns in the schema below.
- Never modify data (no INSERT, UPDATE, DELETE, DROP, CREATE, ALTER).
- Dates are ISO text (YYYY-MM-DD). Treat today's date as {as_of}. Do not use date('now').
- An invoice is overdue when paid_date IS NULL and due_date < today.
- Cancelled orders have no invoice.
- invoices.amount is the total for a WHOLE order. Never SUM(invoices.amount) in a query that also joins order_items or products, because the amount repeats for every item.
- Revenue by customer, country or month: SUM(invoices.amount), without joining order_items.
- Revenue by product or category: SUM(order_items.quantity * products.unit_price), joined through orders with orders.status != 'Cancelled'.
- If the question cannot be answered from the schema, output exactly: CANNOT_ANSWER

Schema:
{schema}
"""


def extract_sql(text):
    text = (text or "").strip()
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


def _chat(messages):
    # reasoning models need a large token budget and low reasoning effort for a simple task
    for extra in ({"reasoning_effort": "low"}, {}):
        try:
            resp = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0, max_tokens=2000, **extra)
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as e:
            print("LLM call failed:", type(e).__name__, e)
    return ""


def generate_sql(question, prev_sql=None, error=None):
    messages = [
        {"role": "system", "content": SYSTEM.format(as_of=AS_OF, schema=get_schema())},
        {"role": "user", "content": question},
    ]
    if prev_sql and error:
        messages += [
            {"role": "assistant", "content": prev_sql},
            {"role": "user", "content": f"That query failed with: {error}\nReturn a corrected SQL query only."},
        ]
    return extract_sql(_chat(messages))


def _execute(sql):
    try:
        df, truncated, clean = run_query(sql, DB_PATH)
        return {"sql": clean, "df": df, "truncated": truncated, "error": None}
    except UnsafeSQL as e:
        return {"sql": sql, "df": None, "truncated": False, "error": f"Blocked for safety: {e}", "fatal": True}
    except sqlite3.Error as e:
        return {"sql": sql, "df": None, "truncated": False, "error": str(e), "fatal": False}


def ask(question):
    sql = generate_sql(question)
    if sql.upper().startswith("CANNOT_ANSWER"):
        return {"sql": None, "df": None, "truncated": False, "attempts": 1,
                "error": "This question can't be answered from the database."}
    res = _execute(sql)
    res["attempts"] = 1
    if res["error"] and not res.get("fatal"):  # retry once on database errors, never on blocked SQL
        res = _execute(generate_sql(question, prev_sql=sql, error=res["error"]))
        res["attempts"] = 2
    return res