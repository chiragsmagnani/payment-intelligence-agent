"""
generate_data.py
-----------------
Creates a synthetic "Payment Performance Intelligence" dataset and loads it
into a local SQLite database (data/payment_performance.db).

The schema is deliberately shaped like the kind of data a card-network
performance-analytics product (think: Mastercard's Payment Performance
Intelligence) would expose to an issuer/acquirer:

    transactions        one row per authorization attempt
    decline_reasons     lookup table of ISO 8583-style decline codes
    markets             lookup table of markets/currencies

This is 100% synthetic data generated with a fixed random seed - no real
cardholder, merchant, or transaction data is used anywhere in this project.
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "payment_performance.db"

random.seed(42)

MARKETS = [
    ("UK", "GBP", "United Kingdom"),
    ("SG", "SGD", "Singapore"),
    ("PL", "PLN", "Poland"),
]

MERCHANT_CATEGORIES = [
    "Grocery", "Travel", "E-commerce", "Fuel", "Dining",
    "Utilities", "Subscriptions", "Electronics", "Healthcare", "Entertainment",
]

# Simplified ISO 8583-style decline reason codes
DECLINE_REASONS = [
    ("05", "Do not honor", "issuer"),
    ("14", "Invalid card number", "network"),
    ("51", "Insufficient funds", "issuer"),
    ("54", "Expired card", "issuer"),
    ("57", "Transaction not permitted to cardholder", "issuer"),
    ("61", "Exceeds withdrawal amount limit", "issuer"),
    ("62", "Restricted card", "issuer"),
    ("65", "Activity count limit exceeded", "risk"),
    ("91", "Issuer or switch inoperative", "network"),
    ("N7", "CVV2 mismatch", "risk"),
]

CHANNELS = ["card_present", "ecom", "recurring", "wallet"]


def build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS decline_reasons;
        DROP TABLE IF EXISTS markets;

        CREATE TABLE markets (
            market_code TEXT PRIMARY KEY,
            currency TEXT NOT NULL,
            market_name TEXT NOT NULL
        );

        CREATE TABLE decline_reasons (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            category TEXT NOT NULL
        );

        CREATE TABLE transactions (
            txn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_date TEXT NOT NULL,
            market_code TEXT NOT NULL,
            merchant_category TEXT NOT NULL,
            channel TEXT NOT NULL,
            amount REAL NOT NULL,
            is_approved INTEGER NOT NULL,
            decline_code TEXT,
            is_chargeback INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (market_code) REFERENCES markets(market_code),
            FOREIGN KEY (decline_code) REFERENCES decline_reasons(code)
        );
        """
    )


def seed_lookups(conn: sqlite3.Connection) -> None:
    conn.executemany("INSERT INTO markets VALUES (?, ?, ?)", MARKETS)
    conn.executemany("INSERT INTO decline_reasons VALUES (?, ?, ?)", DECLINE_REASONS)


def generate_transactions(conn: sqlite3.Connection, days: int = 180, per_day: int = 250) -> None:
    start = date.today() - timedelta(days=days)
    rows = []

    for d in range(days):
        txn_date = (start + timedelta(days=d)).isoformat()

        # Simulate a deliberate approval-rate dip in "March" of the window
        # (roughly day 60-75) tied to a specific decline reason spiking -
        # this gives the agent something meaningful to discover and explain.
        dip = 60 <= d <= 75

        for _ in range(per_day):
            market_code = random.choices(
                ["UK", "SG", "PL"], weights=[0.5, 0.3, 0.2]
            )[0]
            merchant_category = random.choice(MERCHANT_CATEGORIES)
            channel = random.choices(CHANNELS, weights=[0.35, 0.4, 0.15, 0.1])[0]
            amount = round(random.lognormvariate(3.2, 0.9), 2)

            base_approval_rate = 0.93
            if dip:
                base_approval_rate = 0.80  # simulated incident window

            is_approved = random.random() < base_approval_rate
            decline_code = None
            if not is_approved:
                if dip and random.random() < 0.7:
                    # During the dip, most declines are issuer-side "insufficient funds"
                    # style misconfiguration - a realistic root cause an analyst would dig into
                    decline_code = "51"
                else:
                    decline_code = random.choice(DECLINE_REASONS)[0]

            is_chargeback = 1 if (is_approved and random.random() < 0.003) else 0

            rows.append(
                (
                    txn_date,
                    market_code,
                    merchant_category,
                    channel,
                    amount,
                    int(is_approved),
                    decline_code,
                    is_chargeback,
                )
            )

    conn.executemany(
        """
        INSERT INTO transactions
            (txn_date, market_code, merchant_category, channel, amount,
             is_approved, decline_code, is_chargeback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        build_schema(conn)
        seed_lookups(conn)
        generate_transactions(conn)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        print(f"Generated {count:,} synthetic transactions -> {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
