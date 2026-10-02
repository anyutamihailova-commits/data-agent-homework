"""Predefined read-only SQL queries. Gemini never writes or changes these.

Data rules applied in every query:
- 40 duplicate rows (payment_id ending in "_X", user_id U9999999) are excluded.
- Refunded payments keep their amount: gross = all valid payments,
  net = valid payments with is_refunded = 0.
- Two payments by the same user on the same day are kept as is.
"""

# Countries need at least this many payments to be included in the refund-rate ranking.
MIN_PAYMENTS_FOR_REFUND_RANKING = 100

# Country names as stored in users.country, with alternative spellings merged.
# Empty values form a separate "(not specified)" group and stay in all totals.
COUNTRY = """CASE upper(trim(u.country))
        WHEN 'DE'  THEN 'Germany'
        WHEN 'USA' THEN 'United States'
        WHEN 'UK'  THEN 'United Kingdom'
        ELSE coalesce(nullif(trim(u.country), ''), '(not specified)')
    END"""

# Groups that are not single countries: kept in all totals, but never ranked by refund rate.
NON_COUNTRY_GROUPS = ("(not specified)", "Other")

# Common base: all valid payments (duplicates excluded).
VALID_PAYMENTS = r"""
WITH valid AS (
    SELECT * FROM payments WHERE payment_id NOT LIKE '%\_X'
)
"""

QUERIES = {
    "kpis": {
        "description": "Overall totals: gross and net revenue, refunds, refund rate, paying users, date range.",
        "sql": VALID_PAYMENTS + """
SELECT
    count(*)                                              AS payments,
    sum(amount_usd)                                       AS gross_revenue_usd,
    sum(amount_usd) FILTER (WHERE is_refunded = 0)        AS net_revenue_usd,
    count(*) FILTER (WHERE is_refunded = 1)               AS refunded_payments,
    sum(amount_usd) FILTER (WHERE is_refunded = 1)        AS refunded_amount_usd,
    round(100.0 * count(*) FILTER (WHERE is_refunded = 1) / count(*), 2)
                                                          AS refund_rate_pct,
    round(100.0 * sum(amount_usd) FILTER (WHERE is_refunded = 1) / sum(amount_usd), 2)
                                                          AS refund_rate_by_amount_pct,
    count(DISTINCT user_id) FILTER (WHERE is_refunded = 0) AS paying_users,
    min(paid_at)                                          AS first_payment_date,
    max(paid_at)                                          AS last_payment_date
FROM valid
""",
    },
    "revenue_by_plan": {
        "description": "Revenue, refunds and paying users per plan (monthly / annual).",
        "sql": VALID_PAYMENTS + """
SELECT
    plan,
    count(*)                                              AS payments,
    sum(amount_usd)                                       AS gross_revenue_usd,
    sum(amount_usd) FILTER (WHERE is_refunded = 0)        AS net_revenue_usd,
    count(*) FILTER (WHERE is_refunded = 1)               AS refunded_payments,
    round(100.0 * count(*) FILTER (WHERE is_refunded = 1) / count(*), 2)
                                                          AS refund_rate_pct,
    count(DISTINCT user_id) FILTER (WHERE is_refunded = 0) AS paying_users
FROM valid
GROUP BY plan
ORDER BY net_revenue_usd DESC
""",
    },
    "refunds_by_country": {
        "description": (
            "Payments, refunds, refund rate and revenue per country (spellings merged). "
            "All groups are listed and included in totals. Only rows with "
            "included_in_refund_ranking = true may be ranked by refund rate; "
            "ranking_exclusion_reason explains why a row is excluded."
        ),
        "sql": VALID_PAYMENTS + f"""
, by_country AS (
    SELECT
        {COUNTRY}                                             AS country,
        count(*)                                              AS payments,
        count(*) FILTER (WHERE p.is_refunded = 1)             AS refunded_payments,
        round(100.0 * count(*) FILTER (WHERE p.is_refunded = 1) / count(*), 2)
                                                              AS refund_rate_pct,
        sum(p.amount_usd)                                     AS gross_revenue_usd,
        sum(p.amount_usd) FILTER (WHERE p.is_refunded = 0)    AS net_revenue_usd,
        count(DISTINCT p.user_id) FILTER (WHERE p.is_refunded = 0) AS paying_users
    FROM valid p
    JOIN users u USING (user_id)
    GROUP BY 1
), with_reason AS (
    SELECT *,
        CASE
            WHEN country IN ({', '.join(f"'{g}'" for g in NON_COUNTRY_GROUPS)}) THEN 'not a country'
            WHEN payments < {MIN_PAYMENTS_FOR_REFUND_RANKING}
                THEN 'fewer than {MIN_PAYMENTS_FOR_REFUND_RANKING} payments'
        END                                                   AS ranking_exclusion_reason
    FROM by_country
)
SELECT *, ranking_exclusion_reason IS NULL AS included_in_refund_ranking
FROM with_reason
ORDER BY included_in_refund_ranking DESC, refund_rate_pct DESC
""",
    },
    "revenue_by_month": {
        "description": "Monthly payments, gross/net revenue, refunds, share of annual plans, and whether the month is complete.",
        "sql": VALID_PAYMENTS + """
SELECT
    to_char(date_trunc('month', paid_at), 'YYYY-MM')      AS month,
    count(*)                                              AS payments,
    sum(amount_usd)                                       AS gross_revenue_usd,
    sum(amount_usd) FILTER (WHERE is_refunded = 0)        AS net_revenue_usd,
    count(*) FILTER (WHERE is_refunded = 1)               AS refunded_payments,
    round(100.0 * count(*) FILTER (WHERE plan = 'annual') / count(*), 1)
                                                          AS annual_plan_share_pct,
    -- A month is complete only if the data reaches its last day.
    (date_trunc('month', paid_at) + interval '1 month - 1 day')::date
        <= (SELECT max(paid_at) FROM valid)               AS is_complete
FROM valid
GROUP BY date_trunc('month', paid_at)
ORDER BY month
""",
    },
}
