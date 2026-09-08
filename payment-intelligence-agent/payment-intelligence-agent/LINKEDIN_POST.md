# LinkedIn post draft

*(punchy/confident tone, per your style — trim or soften as you like)*

---

Built a Gen AI chatbot that answers payment performance questions instead
of an analyst having to write the SQL.

Ask it "why did our approval rate dip in March" and it queries transaction
data, breaks declines down by issuer/network/risk, and root-causes it — in
plain language, not a raw table.

Stack: Agno (agent framework), Groq (free, fastest inference out there), SQLite, Streamlit.

Why I built this: the "Payment Performance Intelligence" style products
being built across the payments industry right now are exactly this —
agentic Gen AI chatbots that sit on top of transaction/performance data for
issuers and acquirers. I wanted to actually build one, not just talk about
the concept in an interview.

A few product decisions I made on purpose, not by default:
→ Read-only by design — the agent can query data, it can never write to it
→ A domain glossary so it explains "chargeback rate" or "decline reason"
   the way a payments analyst would, not generically
→ A small eval suite (correctness + a safety refusal test) — because a
   chatbot demo with no way to catch regressions isn't a product, it's a
   toy

Code + a PRD-style write-up (scope, non-goals, what v2 would need) in the
repo: [link]

#GenAI #AgenticAI #Payments #ProductManagement #Fintech

---

## Portfolio blurb (shorter, for a portfolio site card)

**Payment Performance Intelligence Assistant** — a Gen AI agent (built on
Agno) that answers natural-language questions over card transaction
performance data: approval rates, decline breakdowns, chargeback trends.
Read-only by design, grounded in a payments glossary, with a built-in eval
harness. Built to mirror how card networks are shipping agentic chatbots on
top of payment performance data today.
