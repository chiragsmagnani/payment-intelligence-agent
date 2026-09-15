"""Streamlit chat interface for the Payment Performance Intelligence Assistant."""

import re
import uuid

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agent.team import build_team


load_dotenv()

MAX_MESSAGES_PER_SESSION = 20  # simple abuse/cost guardrail for a public demo

SAMPLE_QUESTIONS = [
    "What's our overall approval rate, and how does it vary by market?",
    "Was there a dip in approval rate in the last 6 months? When, and why?",
    "Break down declines by reason category (issuer vs network vs risk).",
    "Which merchant category has the highest chargeback rate?",
    "Compare approval rates across channels (card present, ecom, recurring, wallet).",
    "Do our risk-category declines look like a fraud attack or an overly aggressive risk rule?",
]

st.set_page_config(
    page_title="Payment Performance Intelligence Assistant",
    page_icon="💳",
    layout="centered",
)

st.title("Payment Performance Intelligence Assistant")
st.caption(
    "Ask questions about approval rates, declines, chargebacks, markets, "
    "channels, and merchant categories."
)


def _looks_like_provider_error(text: str) -> bool:
    """Detect when the model provider's raw error JSON leaked into the
    answer text instead of being raised as a normal exception.

    Groq (and other OpenAI-compatible providers) sometimes return an error
    payload like {"error": {"message": "...", "code": "rate_limit_exceeded"}}
    as the response *content* rather than raising - this happens when a
    rate limit or transient provider error occurs mid-response. Agno's
    FallbackConfig doesn't always catch this shape, so without this check
    the raw JSON would be shown to the user verbatim as if it were the
    agent's actual answer.
    """
    lowered = text.lower()
    return '"error"' in lowered and ("rate_limit" in lowered or '"code"' in lowered)


def _strip_leaked_query_dumps(text: str) -> str:
    """Strip any leaked raw-tool-output lines from the model's answer
    before displaying it.

    Despite explicit instructions not to, the free-tier model this project
    defaults to occasionally prefixes its answer with a run-on line that
    mashes together the SQL tool's rejection error and/or several raw query
    results - visible as a wall of "|"-separated values with no real line
    breaks, using raw SQL column names instead of the polished headers the
    model uses in its actual answer further down. Prompt instructions alone
    don't reliably stop a smaller model from doing this, so this is a
    code-level safety net: any line that reads like a leaked dump (an
    abnormal number of "|" characters, or the literal SQL rejection text)
    is dropped before the answer is shown. A legitimate markdown table row
    never comes close to this many columns, so the threshold is safe.
    """
    cleaned_lines = [
        line
        for line in text.split("\n")
        if "only select queries are allowed" not in line.lower() and line.count("|") <= 15
    ]
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or text  # never return an empty answer - fall back to the original


_TABLE_SEPARATOR_LINE = re.compile(r"^[\s\-|]+$")


def _strip_leaked_table_dumps(text: str) -> str:
    """Strip a leading block of concatenated raw query-result tables from
    the model's answer.

    This catches a second, sneakier shape of the same leak
    `_strip_leaked_query_dumps` targets: instead of one overloaded line,
    the model sometimes pastes several *properly formatted* mini-tables
    from different `run_sql_query` calls back to back, using raw SQL
    column names (total_txns, approved_chargebacks, ...) instead of the
    clean labels it uses in its real answer further down. A single
    legitimate markdown table only ever has one "---" separator row; two
    or more separator-looking rows in a row means multiple raw results got
    stitched together. When that's detected, everything up through the
    last such separator is dropped, keeping only the well-formed answer
    that follows (which always starts with a heading or a plain sentence,
    not another raw table row).
    """
    lines = text.split("\n")

    # Find the leading block: starting from the very top, lines that are
    # blank or "table-like" (contain a "|"). The block ends at the first
    # line with real content but no "|" - that's where actual prose or a
    # heading begins, i.e. the real answer.
    end_of_block = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and "|" not in stripped:
            end_of_block = i
            break

    leading_block = lines[:end_of_block]
    separator_count = sum(
        1 for line in leading_block if line.strip() and _TABLE_SEPARATOR_LINE.match(line.strip())
    )
    if separator_count < 2:
        return text  # a normal single table has exactly one separator row

    cleaned = "\n".join(lines[end_of_block:]).strip()
    return cleaned or text  # never return an empty answer - fall back to the original


def _get_agent():
    """Create one team (and one shared query log) per browser session, and
    retain each specialist's conversation memory across turns within that
    session. Named `_get_agent` (singular) for historical reasons - it
    actually returns a two-specialist Team now (see agent/team.py), but the
    call site below just does `.run(prompt)` either way, so nothing else
    had to change."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    if "query_log" not in st.session_state:
        st.session_state.query_log = []
    if "agent" not in st.session_state:
        st.session_state.agent = build_team(
            st.session_state.session_id, query_log=st.session_state.query_log
        )
    return st.session_state.agent


def _dataframe_from_log_entry(entry: dict) -> pd.DataFrame | None:
    """Turn a captured {sql, columns, rows} log entry into a DataFrame, or
    None if there's nothing chartable (no rows, or only one column)."""
    if not entry.get("rows") or not entry.get("columns") or len(entry["columns"]) < 2:
        return None
    return pd.DataFrame(entry["rows"], columns=entry["columns"])


def _render_chart_if_useful(df: pd.DataFrame) -> None:
    """Best-effort auto-chart: a date-like column becomes a line chart's
    x-axis; otherwise, one categorical column plus at least one numeric
    column becomes a bar chart. Silently does nothing if the shape doesn't
    fit either pattern - this is a bonus visualization, not a guarantee."""
    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    if date_col and numeric_cols:
        chart_df = df.copy()
        chart_df[date_col] = pd.to_datetime(chart_df[date_col], errors="coerce")
        chart_df = chart_df.dropna(subset=[date_col]).set_index(date_col)
        st.line_chart(chart_df[numeric_cols])
        return

    categorical_cols = [c for c in df.columns if c not in numeric_cols]
    if len(categorical_cols) == 1 and numeric_cols and 1 < len(df) <= 30:
        chart_df = df.set_index(categorical_cols[0])
        st.bar_chart(chart_df[numeric_cols])


def _render_query_transparency(query_log: list[dict], before_count: int) -> None:
    """Show the SQL the agent ran (and a chart, where useful) for this turn.
    `before_count` is the log length before this turn's agent.run() call, so
    only queries from *this* turn are shown, not the whole session's history."""
    new_entries = query_log[before_count:]
    if not new_entries:
        return

    with st.expander(f"🔍 See the {len(new_entries)} SQL quer{'y' if len(new_entries) == 1 else 'ies'} behind this answer"):
        for i, entry in enumerate(new_entries, start=1):
            st.code(entry["sql"], language="sql")
            df = _dataframe_from_log_entry(entry)
            if df is not None:
                _render_chart_if_useful(df)


with st.sidebar:
    st.header("About this demo")
    st.markdown(
        "This agent answers questions over a **synthetic** payment "
        "performance dataset (45,000 simulated transactions across "
        "UK / SG / PL markets) using:\n\n"
        "- a **two-specialist agent team**: a router hands each question to "
        "either the *Payment Performance Assistant* (approval rates, "
        "market/channel/decline breakdowns) or the *Risk & Fraud Analyst* "
        "(fraud patterns, risk-rule tuning, chargeback investigation)\n"
        "- a **SQL tool** each specialist writes queries with itself\n"
        "- a **glossary lookup tool** so answers use the right definitions\n"
        "- session memory for follow-up questions\n\n"
        "No real cardholder or transaction data is used anywhere."
    )
    st.header("Try asking")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, key=f"sample_{hash(q)}", use_container_width=True):
            st.session_state.queued_prompt = q
    if st.button("🔄 Reset conversation"):
        st.session_state.clear()
        st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi — I can analyze the payment-performance dataset. "
                "Try asking, “What is our overall approval rate by market?”"
            ),
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("query_log_slice"):
            with st.expander(
                f"🔍 See the SQL {'query' if len(message['query_log_slice']) == 1 else 'queries'} behind this answer"
            ):
                for entry in message["query_log_slice"]:
                    st.code(entry["sql"], language="sql")
                    df = _dataframe_from_log_entry(entry)
                    if df is not None:
                        _render_chart_if_useful(df)

prompt = st.chat_input("Ask a payment performance question") or st.session_state.pop(
    "queued_prompt", None
)

if prompt:
    if len(st.session_state.messages) >= MAX_MESSAGES_PER_SESSION:
        st.warning(
            "This demo session has hit its message limit (a safeguard against "
            "free-tier API abuse on a public demo). Refresh the page to start "
            "a new session."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing payment performance…"):
            agent = _get_agent()
            log_before = len(st.session_state.query_log)
            try:
                response = agent.run(prompt)
                answer = response.content or "I could not produce an answer for that question."
                answer = _strip_leaked_query_dumps(answer)
                answer = _strip_leaked_table_dumps(answer)
                if _looks_like_provider_error(answer):
                    answer = (
                        "This demo just hit a temporary rate limit on the "
                        "free-tier model (a lot of tool calls in one answer can "
                        "briefly exceed it). Please ask again — it almost "
                        "always clears within a few seconds."
                    )
            except Exception as exc:
                answer = (
                    "I couldn't answer that right now. "
                    f"Please check the app configuration and try again. ({exc})"
                )
        st.markdown(answer)
        query_log_slice = st.session_state.query_log[log_before:]
        _render_query_transparency(st.session_state.query_log, log_before)

        st.session_state.messages.append(
        {"role": "assistant", "content": answer, "query_log_slice": query_log_slice}
    )
