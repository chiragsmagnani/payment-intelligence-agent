"""
payment_agent.py
-----------------
Defines the "Payment Performance Intelligence Assistant" - a Gen AI agent,
built on Agno (the actively-maintained successor to Phidata), that lets a
non-technical stakeholder ask natural-language questions over card
transaction / approval / decline / chargeback data and get analyst-grade
answers back.

This is a portfolio project built to mirror the kind of product described in
Mastercard's "Lead Product Manager - Technical, Agentic AI" JD for the
Payment Performance Intelligence program: a Gen AI chatbot over a payments
performance dataset, with explicit attention to safety (read-only SQL),
explainability (glossary grounding), and evaluability (see eval/).

Supports either Anthropic Claude or OpenAI as the underlying model - set
whichever API key you have via environment variables (see .env.example).
"""

import os
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.db.sqlite import SqliteDb

from .tools import SCHEMA_DESCRIPTION, run_sql_query, search_glossary

SESSION_DB_PATH = Path(__file__).parent.parent / "data" / "agent_sessions.db"

AGENT_INSTRUCTIONS = dedent(
    f"""
    You are the Payment Performance Intelligence Assistant, an internal
    analyst copilot for a card network's payment performance program. Your
    users are product managers, issuer/acquirer relationship managers, and
    analysts - not engineers - so translate SQL results into clear business
    language, not raw tables dumped without comment.

    You have two tools:
    - `run_sql_query`: query the transactions/decline_reasons/markets tables.
    - `search_glossary`: look up how a metric or term should be defined/
      interpreted before you explain it.

    Database schema:
    {SCHEMA_DESCRIPTION}

    How to work:
    1. For any question involving a metric (approval rate, decline rate,
       chargeback rate, decline category, etc.), consider calling
       `search_glossary` first so your explanation uses the right
       definition and the right analyst playbook (e.g. how to investigate
       a dip).
    2. Write your own SQL against the schema above and call `run_sql_query`.
       Prefer aggregated queries (GROUP BY market/category/channel/date)
       over dumping raw rows.
    3. Turn the result into a short, direct answer: lead with the number/
       finding, then 1-3 sentences of "why it matters" or likely root
       cause, using the glossary's decline-category framing (issuer /
       network / risk) where relevant.
    4. If a question can't be answered from this schema, say so plainly -
       do not fabricate figures.
    5. Never run or suggest write queries (INSERT/UPDATE/DELETE/DROP) -
       you are a read-only analytics assistant.

    Keep answers tight: a PM reading this wants the finding fast, not a
    lecture.
    """
).strip()


def _resolve_model():
    """Pick whichever model backend has an API key configured.

    Defaults to Groq (free, no card required, fast Llama inference) if
    GROQ_API_KEY is set - this is the recommended path for anyone cloning
    the repo to try it with zero cost/friction. Falls back to Anthropic
    Claude or OpenAI if those keys are set instead, so the project can
    still be pointed at a frontier model. Raises a clear error if nothing
    is configured, since a portfolio reviewer running this for the first
    time will hit this immediately if they skip the README.
    """
    model_override = os.getenv("AGENT_MODEL_PROVIDER", "").lower()

    if model_override == "groq" or (not model_override and os.getenv("GROQ_API_KEY")):
        from agno.models.groq import Groq

        return Groq(id=os.getenv("GROQ_MODEL_ID", "openai/gpt-oss-120b"))

    if model_override == "openai" or (not model_override and os.getenv("OPENAI_API_KEY")):
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini"))

    if model_override == "anthropic" or (not model_override and os.getenv("ANTHROPIC_API_KEY")):
        from agno.models.anthropic import Claude

        return Claude(id=os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-4-5"))

    raise RuntimeError(
        "No LLM API key found. Set GROQ_API_KEY (recommended - free, no "
        "card required, see .env.example), or ANTHROPIC_API_KEY / "
        "OPENAI_API_KEY, before running the agent."
    )


def build_agent(session_id: str | None = None) -> Agent:
    """Construct the Payment Performance Intelligence Assistant agent."""

    db = SqliteDb(db_file=str(SESSION_DB_PATH))

    return Agent(
        name="Payment Performance Intelligence Assistant",
        model=_resolve_model(),
        db=db,
        session_id=session_id,
        tools=[run_sql_query, search_glossary],
        instructions=AGENT_INSTRUCTIONS,
        add_history_to_context=True,
        num_history_runs=6,
        markdown=True,
    )
