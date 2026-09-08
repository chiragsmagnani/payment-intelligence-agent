# Payment Performance Glossary

This is reference knowledge the agent can pull into its answers so it explains
metrics the way a payments analyst actually talks, not like a generic chatbot.

## Core metrics

- **Approval rate**: approved authorizations / total authorization attempts.
  Industry-healthy card-present approval rates are typically 90-97%; e-com
  and recurring channels normally run a few points lower due to higher risk
  friction (CVV/3DS checks, subscription card-on-file expiry, etc).
- **Decline rate**: 1 - approval rate. Always decompose by *reason code*
  before drawing conclusions - "declines went up" is not an insight,
  "issuer-side insufficient-funds declines went up" is.
- **Chargeback rate**: chargebacks / approved transactions. Usually expressed
  in basis points (bps). A rate above ~10-15 bps in card-not-present channels
  is generally considered elevated and worth investigating.

## Decline reason categories (simplified ISO 8583-style)

- **issuer**: the cardholder's bank declined the transaction (insufficient
  funds, restricted card, not permitted). Usually not a merchant/network
  problem - but a *cluster* of issuer declines from one issuer/BIN range can
  indicate an issuer-side outage or misconfiguration.
- **network**: routing/connectivity issue between acquirer, network, and
  issuer (e.g. "issuer or switch inoperative"). A spike here usually points
  to infrastructure, not customer behavior.
- **risk**: declines driven by fraud/risk rules (velocity limits, CVV
  mismatch). A spike can mean either a genuine fraud attack, or a risk rule
  that has become mis-tuned and is now blocking good customers.

## Markets in this dataset

- **UK** - GBP, Faster Payments / Bacs rails in the real world.
- **SG** - SGD.
- **PL** - PLN.

## How to read a "dip"

When approval rate drops for a specific window of dates, the analyst
playbook is:
1. Is the dip isolated to one market / merchant category / channel, or
   system-wide?
2. Which decline reason code(s) grew the most in absolute terms during the
   window?
3. Is the dominant reason "issuer" (likely an issuer-side event),
   "network" (likely an infra/routing event), or "risk" (likely a fraud
   rule tuning issue)?
4. Quantify the business impact: incremental declined volume/value versus
   the pre-dip baseline.
