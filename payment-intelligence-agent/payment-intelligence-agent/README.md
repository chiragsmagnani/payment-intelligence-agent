# Payment Performance Intelligence Assistant

A Gen AI chatbot that lets a product manager or analyst ask natural-language
questions over card transaction performance data — approval rates, decline
reasons, chargebacks, market/channel comparisons — and get grounded,
tool-verified answers back, instead of waiting on an analyst to pull a query.

Built with **[Agno](https://github.com/agno-agi/agno)** (the actively
maintained successor to Phidata), **Groq** (free, no credit card required,
fastest inference available) as the default model backend — with Claude and
OpenAI supported as drop-in alternatives — and a synthetic SQLite dataset
shaped like real card-network performance data.

Under the hood it's a **two-specialist agent team**, not a single
do-everything agent: a router hands each question to whichever specialist
is best suited to answer it — see [Architecture](#architecture) below.

> Portfolio project by Chirag Magnani — built to demonstrate hands-on
> understanding of the kind of Gen AI chatbot / agentic product this
> [Mastercard Lead Product Manager – Technical, Agentic AI](#why-this-project)
> role is responsible for shipping.

---

## What it does

Ask it things like:

- *"What's our overall approval rate, and how does it vary by market?"*
- *"Was there a dip in approval rate in the last 6 months? When, and why?"*
- *"Break down declines by reason category — issuer vs network vs risk."*
- *"Which merchant category has the highest chargeback rate?"*
- *"Do our risk-category declines look like a fraud attack or an overly
  aggressive risk rule?"*

The agent writes its own SQL against the dataset, grounds its explanation of
metrics in an internal payments glossary, and answers in plain business
language — it doesn't just dump a table. Every answer comes with the exact
SQL behind it (and an auto-generated chart, where the shape of the result
supports one) in a "show your work" expander in the UI.

## Architecture

Instead of one agent trying to be good at every kind of question, a
lightweight **router** (an Agno `Team` in `route` mode) reads each question
and hands it to whichever specialist is actually suited to answer it. The
specialist's own tool-grounded answer passes straight back to the user
unedited — the router never paraphrases or adds to it, which would
reintroduce the exact hallucination risk the tools exist to prevent.
```
                    ┌──────────────────────────────┐
                    │  Payment Performance         │
                    │  Intelligence Team            │
                    │  (agent/team.py) — router     │
                    └───────────────┬───────────────┘
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                             ▼
┌───────────────────────────┐                 ┌───────────────────────────┐
│ Payment Performance        │                 │ Risk & Fraud Analyst       │
│ Assistant                  │                 │                            │
│ approval rates, decline    │                 │ fraud patterns, risk-rule  │
│ breakdowns, market/channel │                 │ tuning, chargeback vs.     │
│ comparisons                │                 │ fraud investigation        │
└──────────────┬──────────────┘                 └──────────────┬─────────────┘
              │                                                 │
              └───────────────────┬─────────────────────────────┘
                                  ▼
                  Tools: run_sql_query, search_glossary
                                  │
                                  ▼
                    SQLite (synthetic payment
                    performance data, 45k rows)
```
Streamlit chat UI sends the question to the router above; the router
returns whichever specialist's answer came back, unedited.

Both specialists share the same two tools (`run_sql_query`, `search_glossary`)
and the same underlying schema, but each has its own instructions and
analytical playbook — the Risk & Fraud Analyst, for example, is told to
cross-check risk-category declines against chargeback rate and channel to
distinguish a genuine fraud attack from an overly aggressive risk rule,
which is a materially different investigation than a general approval-rate
dip.

## Why this project

This was built to directly mirror the responsibilities in Mastercard's
**Lead Product Manager – Technical, Agentic AI** role on the Payment
Performance Intelligence team, which calls for:

| JD responsibility | How this project demonstrates it |
|---|---|
| "Support development of Gen AI chatbot use cases & agentic services" | A working **multi-agent** chatbot (`agent/team.py`), not a slide deck — a router hands each question to the right specialist, with real tool-calling, not a scripted demo |
| "Partner with engineering/data science to ensure architecture quality, safety, evaluation, and observability" | Read-only SQL enforcement (`tools.py`), a keyword-eval harness (`eval/eval_agent.py`), structured tool-call visibility (`show_result=True`), an in-UI "show the SQL" transparency panel, and automatic model fallback on rate limits/outages |
| "Translate a deep understanding of customers into products that drive value" | Sample questions and answer style are written for a PM/analyst audience, not engineers |
| "Own PRDs, backlog prioritization..." | See [`docs/one-pager.md`](docs/one-pager.md) for a PRD-style write-up of scope, non-goals, and what a v2 would add |
| Payments domain fluency (approval rates, decline codes, chargebacks, ISO 8583-style reason codes) | Schema, glossary, and simulated "incident" (a realistic approval-rate dip with a root cause) all reflect real payments analyst workflows |

## Architecture decisions worth calling out

- **A router, not a single generalist agent.** Splitting the Risk & Fraud
  Analyst out from the general Payment Performance Assistant isn't just for
  show — a "was this a fraud attack?" question genuinely needs a different
  analytical playbook (chargeback rate cross-checked against risk declines,
  channel segmentation) than a "how's approval rate trending?" question
  does. `respond_directly=True` on the team means the router's own model
  never touches or paraphrases the specialist's answer, so adding a second
  agent doesn't add a second point of hallucination risk.
- **Groq as the default model, not the biggest name.** This project
  intentionally defaults to Groq's free tier (no card required) instead of
  a paid Claude/OpenAI key. The point isn't "cheapest option" — it's that
  anyone can clone this repo and have it running in two minutes with zero
  billing friction, and it also happens to be the fastest inference
  available. Claude and OpenAI are still supported as one-line swaps
  (`AGENT_MODEL_PROVIDER` in `.env`) for anyone who wants a frontier model.
- **Read-only SQL, enforced in the tool, not just the prompt.** The
  `run_sql_query` tool rejects anything that isn't a `SELECT` and blocks
  write/DDL keywords outright — a small but deliberate safety control, the
  kind of thing this JD's "architecture quality, safety" line is about.
- **No vector database.** The glossary lookup is a simple keyword search
  over a markdown file, not a RAG pipeline with an embedding model. For a
  small, fixed reference doc, that's a better product decision than adding
  infrastructure (and API cost) a demo doesn't need — knowing when *not* to
  add complexity is itself a product judgment call.
- **Automatic model fallback, not a single point of failure.** Groq's free
  tier can hit rate limits under real traffic, and providers occasionally
  retire a model outright (this happened once during development). Agno's
  `FallbackConfig` means a rate limit or model error on the primary model
  automatically retries against a backup model instead of the whole
  chatbot going down.
- **A built-in eval harness**, not just manual testing. Four cases check
  correctness (SQL grounding), domain-groundedness (glossary usage), and a
  safety refusal (declining a write-action request). This is meant to be
  the seed of a regression suite, not a finished one.
- **Simulated incident in the data.** The generator injects a real
  approval-rate dip (days 60–75) driven by a spike in "insufficient funds"
  declines, so the agent's root-cause reasoning is actually being tested
  against ground truth, not just "does it return a number."

## Getting started

```bash
git clone <your-repo-url>
cd payment-intelligence-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add GROQ_API_KEY (free, no card required: console.groq.com/keys)
# — or ANTHROPIC_API_KEY / OPENAI_API_KEY if you'd rather use those

python data/generate_data.py   # regenerate the synthetic dataset (optional — a pre-built one is included)
streamlit run app.py
```

Then open the local URL Streamlit prints and start asking questions.

### Running the eval suite

```bash
python -m eval.eval_agent
```

Prints a pass/fail report with latency per case.

## Project structure
```
payment-intelligence-agent/
├── app.py # Streamlit chat UI
├── agent/
│ ├── team.py # Two-specialist Agno Team (router + agents)
│ ├── payment_agent.py # Payment Performance Assistant (Agno Agent)
│ ├── tools.py # run_sql_query, search_glossary tools
│ └── knowledge/glossary.md # payments domain reference (decline codes, metrics)
├── data/
│ ├── generate_data.py # synthetic dataset generator (45k transactions)
│ └── payment_performance.db
├── eval/
│ └── eval_agent.py # lightweight eval harness
├── docs/
│ └── one-pager.md # PRD-style write-up (scope, non-goals, v2 ideas)
├── requirements.txt
└── .env.example
```

## Data disclaimer

All data in this project is **synthetically generated** (`data/generate_data.py`,
fixed random seed) for demonstration purposes only. No real cardholder,
merchant, issuer, or transaction data is used or referenced anywhere in this
repository.

## Tech stack

Agno (multi-agent `Team` + `Agent`) · Groq (with automatic model fallback) —
with Claude / GPT-4o-mini as drop-in alternatives · SQLite · Streamlit ·
Python 3.11
