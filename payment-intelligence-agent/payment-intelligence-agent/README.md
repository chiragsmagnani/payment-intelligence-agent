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

The agent writes its own SQL against the dataset, grounds its explanation of
metrics in an internal payments glossary, and answers in plain business
language — it doesn't just dump a table.

```
┌──────────────┐      ┌─────────────────────────────┐      ┌──────────────────────┐
│  Streamlit   │─────▶│   Agno Agent                 │─────▶│  Claude / OpenAI     │
│  chat UI     │◀─────│   (payment_agent.py)          │◀─────│  (LLM reasoning)     │
└──────────────┘      │                               │      └──────────────────────┘
                       │  Tools:                       │
                       │  • run_sql_query  ───────────┼─────▶ SQLite (synthetic
                       │  • search_glossary            │       payment performance
                       │                               │       data, 45k rows)
                       │  Session memory (SqliteDb)    │
                       └───────────────────────────────┘
```

## Why this project

This was built to directly mirror the responsibilities in Mastercard's
**Lead Product Manager – Technical, Agentic AI** role on the Payment
Performance Intelligence team, which calls for:

| JD responsibility | How this project demonstrates it |
|---|---|
| "Support development of Gen AI chatbot use cases & agentic services" | A working agentic chatbot, not a slide deck — with real tool-calling, not a scripted demo |
| "Partner with engineering/data science to ensure architecture quality, safety, evaluation, and observability" | Read-only SQL enforcement (`tools.py`), a keyword-eval harness (`eval/eval_agent.py`), structured tool-call visibility (`show_result=True`) |
| "Translate a deep understanding of customers into products that drive value" | Sample questions and answer style are written for a PM/analyst audience, not engineers |
| "Own PRDs, backlog prioritization..." | See [`docs/one-pager.md`](docs/one-pager.md) for a PRD-style write-up of scope, non-goals, and what a v2 would add |
| Payments domain fluency (approval rates, decline codes, chargebacks, ISO 8583-style reason codes) | Schema, glossary, and simulated "incident" (a realistic approval-rate dip with a root cause) all reflect real payments analyst workflows |

## Architecture decisions worth calling out

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
├── app.py                     # Streamlit chat UI
├── agent/
│   ├── payment_agent.py       # Agno Agent definition + instructions
│   ├── tools.py                # run_sql_query, search_glossary tools
│   └── knowledge/glossary.md  # payments domain reference (decline codes, metrics)
├── data/
│   ├── generate_data.py       # synthetic dataset generator (45k transactions)
│   └── payment_performance.db
├── eval/
│   └── eval_agent.py          # lightweight eval harness
├── docs/
│   └── one-pager.md           # PRD-style write-up (scope, non-goals, v2 ideas)
├── requirements.txt
└── .env.example
```

## Data disclaimer

All data in this project is **synthetically generated** (`data/generate_data.py`,
fixed random seed) for demonstration purposes only. No real cardholder,
merchant, issuer, or transaction data is used or referenced anywhere in this
repository.

## Tech stack

Agno · Groq (Llama 3.3 70B) — with Claude / GPT-4o-mini as drop-in
alternatives · SQLite · Streamlit · Python 3.11
