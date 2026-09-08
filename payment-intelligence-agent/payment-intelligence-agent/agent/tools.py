"""
tools.py
--------
The two tools the agent has access to:

1. `run_sql_query`     - lets the agent query the synthetic payment
                          performance database directly with SQL, so it can
                          answer open-ended analytical questions instead of
                          relying on a handful of hard-coded functions.
2. `search_glossary`    - a lightweight (keyword-based, no vector DB / no
                          embedding API needed) retrieval tool over the
                          payments glossary in agent/knowledge/glossary.md,
                          so the agent explains metrics using the right
                          domain vocabulary instead of generic phrasing.

Keeping this dependency-light (sqlite3 + stdlib, no vector store) is a
deliberate product decision for a portfolio project: anyone cloning the repo
can run it with just an LLM API key, no extra infra to stand up.
"""

import re
import sqlite3
from pathlib import Path
from textwrap import dedent

from agno.tools import tool

DB_PATH = Path(__file__).parent.parent / "data" / "payment_performance.db"
GLOSSARY_PATH = Path(__file__).parent / "knowledge" / "glossary.md"

# Only allow read-only queries - this is a demo analytics assistant, not a
# database admin tool. A real product would enforce this at the DB-user
# permission level too, not just in the prompt/tool layer.
_DISALLOWED = re.compile(r"\b(insert|update|delete|drop|alter|attach|pragma)\b", re.IGNORECASE)

SCHEMA_DESCRIPTION = dedent(
    """
    Tables available in the payment_performance.db SQLite database:

    transactions(
        txn_id INTEGER,
        txn_date TEXT,            -- ISO date, e.g. '2026-03-14'
        market_code TEXT,         -- 'UK' | 'SG' | 'PL'
        merchant_category TEXT,   -- e.g. 'Grocery', 'Travel', 'E-commerce', ...
        channel TEXT,             -- 'card_present' | 'ecom' | 'recurring' | 'wallet'
        amount REAL,
        is_approved INTEGER,      -- 1 = approved, 0 = declined
        decline_code TEXT,        -- NULL if approved, else FK to decline_reasons.code
        is_chargeback INTEGER     -- 1 if this approved txn was later charged back
    )

    decline_reasons(
        code TEXT,                -- e.g. '51'
        description TEXT,         -- e.g. 'Insufficient funds'
        category TEXT             -- 'issuer' | 'network' | 'risk'
    )

    markets(
        market_code TEXT,
        currency TEXT,
        market_name TEXT
    )
    """
).strip()


@tool(show_result=True)
def run_sql_query(sql_query: str) -> str:
    """Run a read-only SQL SELECT query against the payment performance
    database and return the results as a markdown table.

    Use this to compute approval rates, decline breakdowns, volumes,
    trends over time, comparisons across markets/merchant categories/
    channels, chargeback rates, etc. Always GROUP BY / ORDER BY / LIMIT
    sensibly so results stay small and readable.

    Args:
        sql_query: A single read-only SQL SELECT statement.

    Returns:
        The query result as a markdown table, or an error message.
    """
    if not sql_query.strip().lower().startswith("select"):
        return "Error: only SELECT queries are allowed."
    if _DISALLOWED.search(sql_query):
        return "Error: query contains a disallowed keyword. Read-only SELECT queries only."

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql_query)
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()
    except sqlite3.Error as e:
        return f"SQL error: {e}"

    if not rows:
        return "Query ran successfully but returned no rows."

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = "\n".join("| " + " | ".join(str(row[c]) for c in columns) + " |" for row in rows[:50])
    truncated_note = "\n\n_(truncated to first 50 rows)_" if len(rows) > 50 else ""

    return f"{header}\n{separator}\n{body}{truncated_note}"


@tool(show_result=True)
def search_glossary(keyword: str) -> str:
    """Search the internal payments glossary for a keyword and return the
    matching section(s). Use this before explaining a metric (approval
    rate, chargeback rate, decline categories, etc.) so the explanation
    uses the correct domain definition rather than a guess.

    Args:
        keyword: A term to look up, e.g. "chargeback", "decline reason",
            "approval rate", "dip".

    Returns:
        The matching glossary section(s), or a not-found message.
    """
    text = GLOSSARY_PATH.read_text()
    sections = re.split(r"\n(?=##? )", text)

    matches = [s for s in sections if keyword.lower() in s.lower()]
    if not matches:
        return f"No glossary section matched '{keyword}'. Try a broader term."
    return "\n\n---\n\n".join(matches[:3])
