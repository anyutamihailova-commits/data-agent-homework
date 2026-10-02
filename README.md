# data-agent-homework

A simple Data Analyst Agent for payments and refunds (`payments` and `users` tables),
with a Streamlit dashboard.

- Net revenue, refund rate, paying users, and monthly net revenue chart.
- Ask questions in plain language. The agent runs only predefined read-only SQL
  (`queries.py`), and Gemini writes an answer from the results. Gemini never writes SQL.

## Data rules
- 40 duplicate payments (`payment_id` ending in `_X`, user `U9999999`) are excluded.
- Gross revenue = all valid payments; net revenue = non-refunded payments.
  Refund rate = share of refunded payments (by count).
- Paying users = distinct users with at least one non-refunded payment.
- February 2023 is incomplete (data ends 2023-02-26) and marked as such.
- Every January the number of annual payments roughly doubles (399, 462, 505 in
  2021–2023). This is a yearly pattern, probably renewals of annual plans (a hypothesis,
  not an established fact). January 2021 has an especially high annual share
  (31.9% vs ~11%) because there were few monthly payments at the start of the data.
- Two payments by the same user on the same day are kept.
- Country spellings are merged (DE → Germany, USA → United States, UK → United Kingdom);
  users without a country form a "(not specified)" group and stay in all totals.
- Refund-rate ranking by country includes only countries with at least 100 payments;
  "(not specified)" and "Other" are not countries and are excluded from the ranking
  (but stay in all totals and in the data the agent receives).

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY and DATABASE_URL
streamlit run app.py
```

## Files
- `queries.py` – predefined SQL queries
- `db.py` – read-only database connection
- `agent.py` – Gemini agent (answers only from query results)
- `app.py` – Streamlit dashboard
