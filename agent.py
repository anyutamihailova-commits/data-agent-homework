"""Data Analyst Agent: runs all predefined queries and lets Gemini explain the results.

Gemini does not see the database and does not write SQL. It only receives
the query results below and turns them into a text answer.
"""

import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from db import run_query
from queries import MIN_PAYMENTS_FOR_REFUND_RANKING, QUERIES

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
# Used once if the main model stays unavailable. Checked with client.models.list().
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash"

# Gemini errors worth retrying: 503 = overloaded, 429 = rate limit.
RETRYABLE_CODES = {429, 503}
# Pause before each next try: 3 tries of the main model, then the fallback model.
RETRY_DELAYS_SECONDS = [2, 4, 8]

OVERLOADED_MESSAGE = "Gemini зараз перевантажений, спробуйте через хвилину."


class GeminiUnavailableError(Exception):
    """Gemini did not answer after all retries and the fallback model."""

SYSTEM_INSTRUCTION = """
You are a data analyst for an online learning platform. You answer questions about
payments, revenue, refunds and paying users.

You receive the results of predefined SQL queries. Use ONLY these results.
- Never invent, guess or extrapolate numbers. Every number in your answer must come
  from the results (or be simple arithmetic on them, such as a difference or a share).
- If the question cannot be answered from these results, say plainly that you do not
  have this data, and list what you can be asked about: overall gross/net revenue,
  refunds and refund rate, paying users, revenue by plan (monthly/annual),
  refunds and revenue by country, revenue by month.

Definitions and data rules (already applied in the results):
- 40 duplicate payments (payment_id ending in "_X", test user U9999999) are excluded.
- Gross revenue = all valid payments. Net revenue = valid payments that were not refunded.
  Refunded payments keep their amount in the data.
- Refund rate = share of refunded payments by count (refund_rate_pct). A rate by amount
  is also provided (refund_rate_by_amount_pct).
- Paying users = distinct users with at least one non-refunded payment.
- Data covers 2021-01-01 to 2023-02-26. February 2023 is incomplete (is_complete = false):
  you may report its numbers, but always say it is incomplete and never compare it with
  full months or use it to claim growth or decline.
- January pattern: every January the number of annual payments roughly doubles
  (399 in Jan 2021, 462 in Jan 2022, 505 in Jan 2023; about 2x the previous December).
  This is a yearly pattern, probably renewals of annual plans. January 2021 has an
  especially high annual share (31.9% vs about 11% in later Januaries) because there
  were few monthly payments at the start of the data. When answering about trends,
  monthly changes or January, mention this, and present the renewal explanation as a
  hypothesis, not as an established fact. Annual payments ($399) raise January revenue.
- Countries: alternative spellings are already merged ("DE" -> Germany, "USA" -> United
  States, "UK" -> United Kingdom). "(not specified)" means users without a country and
  "Other" is a group of countries as stored in the data. Both are included in all totals
  and you may report their numbers.
- Refund rate ranking by country: only rows with included_in_refund_ranking = true may
  be ranked or called highest/lowest. When you answer about refund rates by country,
  always mention that:
  * "(not specified)" and "Other" are not countries, so they are not in the ranking;
  * countries with fewer than {min_payments} payments are excluded from the ranking
    (name any excluded for this reason; if none, say all countries meet the threshold).
  ranking_exclusion_reason shows why each row is excluded.

Answer format:
- Answer in the language of the question.
- At most 120 words. No headings.
- Put the main conclusion in the first sentence.
- Give detailed numbers (tables, full lists, breakdowns) only if the user asks for them;
  otherwise use only the one or two key numbers that support the conclusion.
- Use USD amounts with thousands separators.
""".strip().format(min_payments=MIN_PAYMENTS_FOR_REFUND_RANKING)


def build_context() -> str:
    """Run every predefined query and format the results as text for Gemini."""
    parts = []
    for name, query in QUERIES.items():
        df = run_query(name)
        parts.append(f"### {name}\n{query['description']}\n{df.to_csv(index=False)}")
    return "\n\n".join(parts)


def ask(question: str) -> tuple[str, str]:
    """Answer a user question using only the predefined query results.

    Returns (answer, model that answered). Raises GeminiUnavailableError if Gemini
    stays overloaded (503) or rate-limited (429) after all retries.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")

    client = genai.Client(api_key=api_key)
    contents = f"Query results:\n\n{build_context()}\n\nQuestion: {question}"
    config = types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)

    main_model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL
    # 3 tries with the main model, then 1 try with the fallback model.
    models = [main_model] * 3 + [fallback_model]

    for attempt, model in enumerate(models):
        if attempt > 0:
            time.sleep(RETRY_DELAYS_SECONDS[attempt - 1])
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            return response.text, model
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES:
                raise

    raise GeminiUnavailableError(OVERLOADED_MESSAGE)
