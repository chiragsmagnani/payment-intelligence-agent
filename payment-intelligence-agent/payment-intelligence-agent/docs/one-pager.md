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

## v1 scope (what's built here)

- Natural-language Q&A over a fixed schema (transactions, decline reasons,
  markets).
- Agent writes and executes its own read-only SQL.
- Answers are grounded in a domain glossary so metric definitions and the
  issuer/network/risk decline framing are consistent every time.
- Session memory so follow-up questions ("break that down by market")
  work without restating context.
- A small eval suite as a starting regression check.

## Explicit non-goals for v1

- **Not** a write/action agent — it cannot modify data, trigger workflows,
  or take actions on a user's behalf. Read-only by design.
- **Not** connected to live production data — this is a synthetic dataset
  for demonstration; a real version would need data governance, PII
  review, and access controls before touching real transaction data.
- **Not** a fraud-detection or decisioning system — it explains historical
  performance, it doesn't score or block transactions.
- No multi-turn tool orchestration beyond SQL + glossary lookup (no
  external API calls, no chart generation) in this version.

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
- **Observability**: v1 only logs to stdout via the eval script. A real
  version needs per-query logging (question → generated SQL → result →
  final answer) so a PM can audit *why* the agent said what it said.

## v2 ideas (not built, but this is where I'd take it next)

- Chart/visualization tool so answers can include a trend line, not just
  markdown tables.
- A confidence/citation layer that shows the exact SQL run alongside the
  answer, so an analyst can verify without re-deriving it.
- Multi-turn "investigate this dip" workflow: agent proactively segments
  by market/category/channel/decline-code without being asked each cut.
- A proper eval framework (LLM-as-judge + golden dataset) instead of
  keyword matching, once there's a large enough set of real questions to
  build one from.
