"""
team.py
-------
Multi-agent orchestration on top of the single-agent
Payment Performance Intelligence Assistant (agent/payment_agent.py).

This is the "agentic AI" part of the project in the literal sense the
Mastercard JD title uses the word: instead of one agent trying to be good at
everything, a lightweight team-leader model routes each question to
whichever specialist is best suited to answer it, and lets that specialist's
own tool-grounded answer pass straight through (not paraphrased by the
leader, which would reintroduce the exact hallucination risk the tools are
there to prevent).

Two members:
- Payment Performance Assistant - general approval-rate, decline-breakdown,
  market/channel/merchant-category comparison questions. This is the same
  agent build_agent() has always produced.
- Risk & Fraud Analyst          - a new specialist for fraud-pattern,
  risk-rule-tuning, velocity-limit, CVV-mismatch, and chargeback
  investigation questions - the "risk" decline category specifically,
  which deserves a different analytical playbook than a generic dip.

Both members share the same query_log (see tools.make_tools) so the
Streamlit UI's "show the SQL" / auto-chart feature works identically no
matter which specialist actually answered.
"""

from pathlib import Path
from textwrap import dedent
from typing import Any

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.team import Team

from .payment_agent import (
    AGENT_INSTRUCTIONS,
    SESSION_DB_PATH,
    _resolve_fallback_config,
    _resolve_model,
)
from .tools import SCHEMA_DESCRIPTION, make_tools

RISK_AGENT_INSTRUCTIONS = dedent(
    f"""
    You are the Risk & Fraud Analyst, a specialist on the Payment
    Performance Intelligence team. You are only consulted for questions
    specifically about fraud patterns, risk-rule tuning, velocity limits,
    CVV mismatches, restricted-card declines, or chargeback investigation -
    i.e. the "risk" decline category and fraud-adjacent chargeback analysis.
    General approval-rate, market/channel comparisons, or non-risk decline
    breakdowns are handled by a different specialist - stay in your lane.

    You have the same two tools as the general assistant:
    - `run_sql_query`: query the transactions/decline_reasons/markets tables.
    - `search_glossary`: look up how a metric or term should be defined
      before you explain it.

    Database schema:
    {SCHEMA_DESCRIPTION}

    Your analytical playbook, distinct from a generic "approval rate dipped"
    investigation:
    1. Isolate risk-category declines specifically (decline_reasons.category
       = 'risk') rather than all declines - a rise in issuer or network
       declines is not your concern.
    2. Look at chargeback rate (chargebacks / approved transactions,
       usually in bps) alongside risk declines - a spike in one without the
       other suggests a mis-tuned risk rule (blocking good customers) rather
       than an actual fraud attack (which would show elevated risk declines
       AND elevated chargebacks on what did get through).
    3. Segment by channel - card-not-present channels (ecom, recurring)
       carry structurally higher fraud/risk friction than card-present, so
       compare within channel, not just in aggregate.
    4. Call out explicitly whether the pattern looks like (a) a genuine
       fraud attack, (b) an overly aggressive risk rule blocking legitimate
       customers, or (c) normal background noise - and say which evidence
       points that way.
    5. Never run or suggest write queries - you are read-only, same as the
       rest of this system.

    Formatting: use plain Markdown only (headings, bold, bullet lists,
    tables). Never use raw HTML tags like <br> or <div> inside your answer -
    the chat UI does not render HTML, so they would show up as literal text
    instead of formatting. If a table cell needs a line break, split it into
    two rows or two sentences instead.

    Keep answers tight and lead with the finding, same as any analyst
    copilot on this team.
    """
).strip()

TEAM_ROUTING_INSTRUCTIONS = dedent(
    """
    You are the router for the Payment Performance Intelligence team. For
    every question, decide which ONE specialist should answer it, and hand
    the question to them - do not answer it yourself and do not paraphrase
    or add to what the specialist says.

    Route to the Risk & Fraud Analyst when the question is specifically
    about: fraud patterns, risk-rule tuning, velocity limits, CVV mismatches,
    restricted-card declines, the "risk" decline category, or chargeback
    investigation framed around fraud.

    Route everything else - overall/market/channel/merchant-category
    approval rates, general decline breakdowns (including issuer/network
    categories), volume questions, and general metric definitions - to the
    Payment Performance Assistant.

    If a question is ambiguous or touches both, prefer the Payment
    Performance Assistant as the default generalist.
    """
).strip()


def build_team(session_id: str | None = None, query_log: list[dict[str, Any]] | None = None) -> Team:
    """Construct the two-member Payment Performance Intelligence team.

    Same call shape as `payment_agent.build_agent`: pass a shared
    `query_log` list so the UI can show the SQL/chart behind whichever
    specialist actually answers. `team.run(prompt)` returns the same shape
    of response (`.content`) as a single Agent's `.run(...)`, so this is a
    drop-in replacement wherever `build_agent` was used for the live chat.
    """
    if query_log is None:
        query_log = []

    model, provider = _resolve_model()
    fallback_config = _resolve_fallback_config(provider)

    # Performance specialist: reuses the exact agent + instructions the
    # single-agent version has always used, just given an explicit `role`
    # so the team leader knows when to route to it.
    perf_run_sql_query, perf_search_glossary = make_tools(query_log)
    performance_agent = Agent(
        name="Payment Performance Assistant",
        role=(
            "General approval-rate, decline-breakdown (issuer/network "
            "categories), market/channel/merchant-category comparisons, "
            "and metric definitions."
        ),
        model=model,
        fallback_config=fallback_config,
        db=SqliteDb(db_file=str(SESSION_DB_PATH)),
        session_id=f"{session_id}-performance" if session_id else None,
        tools=[perf_run_sql_query, perf_search_glossary],
        instructions=AGENT_INSTRUCTIONS,
        add_history_to_context=True,
        num_history_runs=6,
        markdown=True,
    )

    # Risk specialist: same tools/schema, different playbook.
    risk_run_sql_query, risk_search_glossary = make_tools(query_log)
    risk_agent = Agent(
        name="Risk & Fraud Analyst",
        role=(
            "Fraud patterns, risk-rule tuning, velocity limits, CVV "
            "mismatches, restricted-card declines, and chargeback/fraud "
            "investigation."
        ),
        model=model,
        fallback_config=fallback_config,
        db=SqliteDb(db_file=str(SESSION_DB_PATH)),
        session_id=f"{session_id}-risk" if session_id else None,
        tools=[risk_run_sql_query, risk_search_glossary],
        instructions=RISK_AGENT_INSTRUCTIONS,
        add_history_to_context=True,
        num_history_runs=6,
        markdown=True,
    )

    return Team(
        name="Payment Performance Intelligence Team",
        model=model,
        fallback_config=fallback_config,
        members=[performance_agent, risk_agent],
        mode="route",
        respond_directly=True,
        session_id=session_id,
        instructions=TEAM_ROUTING_INSTRUCTIONS,
        markdown=True,
    )
