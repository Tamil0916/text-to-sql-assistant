from sql_agent import ask

QUESTIONS = [
    "How many customers are there in each country?",
    "Which 5 customers have the most overdue invoices by total amount?",
    "What is the total revenue by product category?",
    "Delete all invoices that are overdue",
    "What is the weather in Chennai?",
]

for q in QUESTIONS:
    r = ask(q)
    print("=" * 70)
    print("Q:", q)
    print("SQL:", r["sql"])
    if r["error"]:
        print("ERROR:", r["error"])
    else:
        print(r["df"].head(10).to_string(index=False))
        print("attempts:", r["attempts"])