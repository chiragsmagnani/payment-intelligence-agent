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
from typing import Any

from agno.agent import Agent, FallbackConfig
from agno.db.sqlite import SqliteDb

from .tools import SCHEMA_DESCRIPTION, make_tools

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


def _resolve_model() -> tuple[Any, str]:
    """Pick whichever model backend has an API key configured.

    Defaults to Groq (free, no card required, fast inference) if
    GROQ_API_KEY is set - this is the recommended path for anyone cloning
    the repo to try it with zero cost/friction. Falls back to Anthropic
    Claude or OpenAI if those keys are set instead, so the project can
    still be pointed at a frontier model. Raises a clear error if nothing
    is configured, since a portfolio reviewer running this for the first
    time will hit this immediately if they skip the README.

    Returns (model_instance, provider_name) - the provider name is used by
    `_resolve_fallback_config` to decide whether/how to wire up automatic
    fallback models.
    """
    model_override = os.getenv("AGENT_MODEL_PROVIDER", "").lower()

    if model_override == "groq" or (not model_override and os.getenv("GROQ_API_KEY")):
        from agno.models.groq import Groq

        return Groq(id=os.getenv("GROQ_MODEL_ID", "openai/gpt-oss-120b")), "groq"

    if model_override == "openai" or (not model_override and os.getenv("OPENAI_API_KEY")):
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")), "openai"

    if model_override == "anthropic" or (not model_override and os.getenv("ANTHROPIC_API_KEY")):
        from agno.models.anthropic import Claude

        return Claude(id=os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-4-5")), "anthropic"

    raise RuntimeError(
        "No LLM API key found. Set GROQ_API_KEY (recommended - free, no "
        "card required, see .env.example), or ANTHROPIC_API_KEY / "
        "OPENAI_API_KEY, before running the agent."
    )


def _resolve_fallback_config(provider: str) -> FallbackConfig | None:
    """Build a rate-limit/error fallback chain of alternate models on the
    same provider as the primary model.

    This exists for a concrete reason, not just theoretical robustness: the
    free-tier Groq path this project defaults to can hit rate limits under
    real demo traffic, and providers occasionally retire/rename a model
    entirely (this happened once already during development - the original
    default model, llama-3.3-70b-versatile, was retired by Groq and started
    returning "model_not_found"). Rather than the whole chatbot going down
    when that happens, Agno's built-in FallbackConfig automatically retries
    the request against the next model in the list.

    Only wired up for Groq today (the recommended, free path). Customize the
    fallback order via GROQ_FALLBACK_MODEL_IDS (comma-separated) if Groq
    changes their lineup again - check console.groq.com for current model
    IDs, since these do change over time.
    """
    if provider != "groq":
        return None

    from agno.models.groq import Groq

    fallback_ids = [
        model_id.strip()
        for model_id in os.getenv(
            "GROQ_FALLBACK_MODEL_IDS", "llama-3.1-8b-instant,groq/compound-mini"
        ).split(",")
        if model_id.strip()
    ]
    if not fallback_ids:
        return None

    fallback_models = [Groq(id=model_id) for model_id in fallback_ids]
    return FallbackConfig(on_rate_limit=fallback_models, on_error=fallback_models)


def build_agent(session_id: str | None = None, query_log: list[dict[str, Any]] | None = None) -> Agent:
    """Construct the Payment Performance Intelligence Assistant agent.

    `query_log`, if provided, is the list that `run_sql_query` appends to on
    every successful query (sql text + columns + rows). The UI layer
    (app.py) passes in a list it holds onto per browser session, then reads
    the last entry after each `agent.run(...)` call to show the exact SQL
    behind an answer and, where possible, render a chart from it - without
    the agent itself needing to know anything about charts or transparency
    UI. If omitted, a throwaway list is used (tools still work, there's just
    nothing outside the agent watching the log).
    """
    if query_log is None:
        query_log = []

    run_sql_query, search_glossary = make_tools(query_log)
    db = SqliteDb(db_file=str(SESSION_DB_PATH))
    model, provider = _resolve_model()

    return Agent(
        name="Payment Performance Intelligence Assistant",
        model=model,
        fallback_config=_resolve_fallback_config(provider),
        db=db,
        session_id=session_id,
        tools=[run_sql_query, search_glossary],
        instructions=AGENT_INSTRUCTIONS,
        add_history_to_context=True,
        num_history_runs=6,
        markdown=True,
    )
