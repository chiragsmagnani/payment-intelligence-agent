# One-pager: Payment Performance Intelligence Assistant

*A PRD-style summary — written the way I'd frame this if I were pitching it
as a v1 scope, not just describing code.*

## Problem

Analysts and relationship managers spend a meaningful chunk of their time
answering routine questions about payment performance — approval rates,
decline breakdowns, chargeback trends — by writing SQL or waiting on someone
who can. That's slow, and it means non-technical stakeholders (issuer
relationship managers, junior PMs) are bottlenecked on data-team bandwidth
for questions that don't need a human analyst's judgment, just the right
query and the right framing of the answer.

## Target user

Internal: product managers, relationship managers, and analysts on a card
network's payment performance program who need fast, self-serve answers
without writing SQL themselves.

## Success metrics (how I'd know this is working, in production)

- **Containment rate** — % of questions the agent resolves without a human
  analyst getting pulled in. This is the core productivity metric; everything
  else here is a supporting signal for it.
- **Router accuracy** — % of questions handed to the correct specialist,
  sampled and audited on a rolling basis, not just spot-checked at launch.
- **Time-to-answer** — median seconds from question to answer, benchmarked
  against the "wait on a data-team query" baseline it's meant to replace.
- **Groundedness** — % of numeric claims in a response that trace back to an
  actual tool call. v1 gets this close to 100% by architecture (every figure
  has to go through `run_sql_query`), but a production version needs this as
  a monitored metric, not just an assumed guarantee.
- **Cost per resolved question** — LLM spend per question actually answered
  (not per API call), tracked against a budget ceiling.
- **Guardrail trigger rate** — how often the session rate limiter fires, as
  an early signal for capacity/cost planning before it becomes a user
  complaint.

**Illustrative impact, not a measured claim:** if this contained even 20% of
the routine approval-rate/decline/chargeback questions a payment performance
team currently routes to an analyst, that's a meaningful chunk of analyst
time returned to work that actually needs human judgment — the real pitch
isn't "a chatbot," it's fewer people waiting on a query for a question the
data already answers.

## v1 scope (what's built here)

- **Multi-agent orchestration**: a router hands each question to whichever
  of two specialists is best suited — a general Payment Performance
  Assistant, or a Risk & Fraud Analyst with its own playbook for
  distinguishing a genuine fraud attack from an overly aggressive risk rule.
  The router passes the specialist's answer straight through rather than
  paraphrasing it, so adding a second agent doesn't add a second point of
  hallucination risk.
- Natural-language Q&A over a fixed schema (transactions, decline reasons,
  markets).
- Each specialist writes and executes its own read-only SQL.
- Answers are grounded in a domain glossary so metric definitions and the
  issuer/network/risk decline framing are consistent every time.
- Session memory so follow-up questions ("break that down by market")
  work without restating context.
- **Query transparency**: every answer ships with the exact SQL behind it
  in an expandable panel, plus an auto-generated chart where the result
  shape supports one — an analyst can verify the answer without
  re-deriving it themselves.
- **Automatic model fallback** on rate limits or provider errors, so a
  free-tier rate limit or a retired model doesn't take the whole chatbot
  down.
- A session-based message-count rate limiter as a basic abuse/cost
  guardrail on the public demo.
- A small eval suite as a starting regression check.

## Explicit non-goals for v1

- **Not** a write/action agent — it cannot modify data, trigger workflows,
  or take actions on a user's behalf. Read-only by design.
- **Not** connected to live production data — this is a synthetic dataset
  for demonstration; a real version would need data governance, PII
  review, and access controls before touching real transaction data.
- **Not** a fraud-detection or decisioning system — it explains historical
  performance, it doesn't score or block transactions.
- No tool orchestration beyond SQL + glossary lookup — no external API
  calls, no write-back actions, no direct database mutation from either
  specialist.

## Risks / what I'd want engineering + data science input on before this
went further than a demo

- **Hallucinated numbers**: mitigated in v1 by forcing all figures through
  the SQL tool rather than free-generation, but a production version needs
  automated checks that every numeric claim in a response traces back to a
  tool call, not just eyeballing eval output.
- **SQL correctness at scale**: the schema here is 3 tables; a real
  performance-intelligence schema is much wider. Query correctness and
  cost (query plans against a large warehouse) would need real evaluation,
  not a 4-case harness.
- **Access control**: a real deployment needs row/column-level permissions
  so, e.g., one issuer can't query another issuer's data through a clever
  prompt.
- **Observability**: v1 surfaces the SQL behind each answer in the UI and
  the eval script logs to stdout, but there's still no persistent,
  queryable log of question → routed specialist → generated SQL → result →
  final answer. A real version needs that trail stored somewhere a PM can
  audit later, not just visible in the moment.
- **Router misclassification**: a two-specialist router is simple enough to
  reason about today, but as more specialists get added, ambiguous
  questions getting routed to the wrong (or a default) specialist becomes a
  real failure mode that needs its own eval cases, not just spot-checking.
- **No auth on the public demo**: the deployed instance is unauthenticated
  by design (it's a portfolio demo), rate-limited only by a simple
  per-session message cap — a production version needs real auth and a
  hard cost ceiling, not just a soft guardrail.

## Roadmap (not built, but this is where I'd take it next, and why in this order)

**Now** — closes the biggest gaps already called out above, and has to come
before anything else on this list is trustworthy:

- Persistent, queryable observability logging (question → routed specialist
  → SQL → result → answer). This is the cheapest, highest-leverage item
  here — it reuses the transparency mechanism that already exists, just
  writes it somewhere durable instead of only showing it in-session. Without
  it, none of the metrics above can actually be measured.
- Eval cases that specifically test routing accuracy between specialists,
  added to the existing harness. Directly derisks "router misclassification"
  before more specialists make that failure mode worse.

**Next** — natural extensions of the pattern, but only once the above is in
place so they're not built on an unmeasured foundation:

- Additional specialists (e.g. a Chargeback/Dispute Analyst, a
  Volume/Forecasting Analyst), each narrow and well-instructed rather than
  one agent doing everything passably.
- A multi-turn "investigate this dip" workflow: the agent proactively
  segments by market/category/channel/decline-code without being asked each
  cut, rather than answering one query at a time.

**Later** — worth doing, but only once there's either real usage data or a
real need to go beyond a portfolio demo:

- A proper eval framework (LLM-as-judge + golden dataset) instead of
  keyword matching, once there's a large enough set of real questions to
  build one from.
- Basic auth + a hard per-key cost ceiling, if this ever needed to be shared
  more broadly than a portfolio demo.
