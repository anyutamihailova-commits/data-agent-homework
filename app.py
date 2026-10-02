"""Streamlit dashboard: payments & refunds KPIs, monthly net revenue, and the agent."""

import altair as alt
import streamlit as st

from agent import GeminiUnavailableError, ask
from db import run_query

st.set_page_config(page_title="Payments & Refunds", layout="wide")
st.title("Payments & Refunds")
st.caption(
    "Duplicates (payment_id ending in “_X”) excluded. "
    "Net revenue excludes refunded payments. Data: 2021-01-01 – 2023-02-26."
)


@st.cache_data(ttl=600)
def load(name):
    return run_query(name)


kpis = load("kpis").iloc[0]
col1, col2, col3 = st.columns(3)
col1.metric("Net revenue", f"${kpis['net_revenue_usd']:,.0f}",
            help=f"Gross revenue: ${kpis['gross_revenue_usd']:,.0f}")
col2.metric("Refund rate", f"{kpis['refund_rate_pct']:.2f}%",
            help=f"{int(kpis['refunded_payments']):,} of {int(kpis['payments']):,} payments refunded "
                 f"(${kpis['refunded_amount_usd']:,.0f}, "
                 f"{kpis['refund_rate_by_amount_pct']:.2f}% by amount)")
col3.metric("Paying users", f"{int(kpis['paying_users']):,}",
            help="Users with at least one non-refunded payment")

st.subheader("Net revenue by month")
monthly = load("revenue_by_month")
monthly["status"] = monthly["is_complete"].map({True: "Complete month", False: "Incomplete month"})
chart = (
    alt.Chart(monthly)
    .mark_bar()
    .encode(
        x=alt.X("month:N", title=None),
        y=alt.Y("net_revenue_usd:Q", title="Net revenue (USD)"),
        color=alt.Color(
            "status:N",
            scale=alt.Scale(domain=["Complete month", "Incomplete month"],
                            range=["#4c78a8", "#c7c7c7"]),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            "month",
            alt.Tooltip("net_revenue_usd:Q", format="$,.0f", title="Net revenue"),
            alt.Tooltip("gross_revenue_usd:Q", format="$,.0f", title="Gross revenue"),
            alt.Tooltip("annual_plan_share_pct:Q", title="Annual plan share, %"),
            "status",
        ],
    )
)
st.altair_chart(chart, width="stretch")
st.caption(
    "February 2023 is incomplete (data ends 2023-02-26) and should not be compared with full months. "
    "Every January the number of annual payments roughly doubles (399, 462, 505), "
    "a yearly pattern, probably renewals of annual plans (hypothesis). "
    "January 2021 has an especially high annual share (31.9% vs ~11%) "
    "because there were few monthly payments at the start of the data."
)

st.subheader("Ask the agent")
question = st.text_input(
    "Your question",
    placeholder="e.g. Which plan brings the most revenue? Which countries have the highest refund rate?",
)
if question:
    with st.spinner("Thinking..."):
        try:
            answer, model = ask(question)
            # Escape $ so Streamlit does not render text between two $ as LaTeX.
            # Un-escape first, in case the model already wrote \$.
            st.markdown(answer.replace("\\$", "$").replace("$", "\\$"))
            st.caption(f"Model: {model}")
        except GeminiUnavailableError as e:
            st.warning(str(e))
        except Exception as e:
            st.error(f"The agent could not answer: {e}")
