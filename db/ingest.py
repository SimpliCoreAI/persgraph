#!/usr/bin/env python3
"""
PersGraph SQLite Ingestion Script
Loads CSV transaction files into persgraph.db with dedup support.
Usage: python db/ingest.py [--csv path/to/file.csv ...]
"""

import csv
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "persgraph.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DEFAULT_CSVS = [
    Path(__file__).parent.parent / "persgraph/data/transactions_2025.csv",
    Path(__file__).parent.parent / "persgraph/data/transactions_2026.csv",
]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection):
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()


def make_hash(date: str, account: str, description: str, amount: str) -> str:
    key = f"{date}|{account}|{description}|{amount}"
    return hashlib.md5(key.encode()).hexdigest()


def parse_account_type(name: str) -> tuple[str, str, str]:
    """Returns (type, institution, last4) from account name string."""
    name_lower = name.lower()
    last4_match = re.search(r'ending in (\d{4})', name_lower)
    last4 = last4_match.group(1) if last4_match else None

    if any(x in name_lower for x in ['credit card', 'visa', 'platinum', 'gold', 'amex']):
        acc_type = 'credit'
    elif any(x in name_lower for x in ['savings', 'saving']):
        acc_type = 'savings'
    elif any(x in name_lower for x in ['checking', 'check']):
        acc_type = 'checking'
    elif any(x in name_lower for x in ['cd ', 'certificate']):
        acc_type = 'cd'
    elif any(x in name_lower for x in ['investment', 'brokerage', '401k', 'ira']):
        acc_type = 'investment'
    else:
        acc_type = 'other'

    # Institution guesses
    institution = None
    if 'citi' in name_lower:
        institution = 'Citi'
    elif 'amex' in name_lower or 'american express' in name_lower:
        institution = 'American Express'
    elif 'chase' in name_lower:
        institution = 'Chase'
    elif 'bofa' in name_lower or 'bank of america' in name_lower:
        institution = 'Bank of America'
    elif 'ally' in name_lower:
        institution = 'Ally'
    elif 'discover' in name_lower:
        institution = 'Discover'

    return acc_type, institution, last4


def ingest_csv(conn: sqlite3.Connection, csv_path: Path) -> dict:
    if not csv_path.exists():
        print(f"  ⚠️  Not found: {csv_path}")
        return {"inserted": 0, "skipped": 0, "errors": 0}

    inserted = skipped = errors = 0
    accounts_seen = set()

    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date = row['Date'].strip()
                account = row['Account'].strip()
                description = row['Description'].strip()
                category = row.get('Category', '').strip() or None
                tags = row.get('Tags', '').strip() or None
                amount = float(row['Amount'].strip())
                year = int(date[:4])
                row_hash = make_hash(date, account, description, str(amount))

                conn.execute(
                    """INSERT OR IGNORE INTO transactions
                       (date, account, description, category, tags, amount, year, source_file, hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (date, account, description, category, tags, amount, year,
                     csv_path.name, row_hash)
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
                else:
                    skipped += 1

                # Upsert account
                if account not in accounts_seen:
                    accounts_seen.add(account)
                    acc_type, institution, last4 = parse_account_type(account)
                    conn.execute(
                        """INSERT OR IGNORE INTO accounts (name, type, institution, last4)
                           VALUES (?, ?, ?, ?)""",
                        (account, acc_type, institution, last4)
                    )

            except Exception as e:
                errors += 1
                print(f"  ❌ Error on row {row}: {e}")

    conn.commit()
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def print_summary(conn: sqlite3.Connection):
    print("\n📊 Database Summary")
    print("=" * 50)

    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    print(f"  Total transactions: {total:,}")

    print("\n  By year:")
    for row in conn.execute("SELECT year, COUNT(*) as n FROM transactions GROUP BY year ORDER BY year"):
        print(f"    {row['year']}: {row['n']:,} rows")

    print("\n  By account:")
    for row in conn.execute("""
        SELECT a.name, a.type, COUNT(t.id) as n
        FROM accounts a
        LEFT JOIN transactions t ON t.account = a.name
        GROUP BY a.name ORDER BY n DESC
    """):
        print(f"    [{row['type']}] {row['name'][:55]}: {row['n']:,}")


def main():
    csv_files = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_CSVS

    print(f"🗄️  PersGraph SQLite Ingestion")
    print(f"   DB: {DB_PATH}")

    conn = get_connection()
    init_db(conn)

    total_inserted = total_skipped = 0
    for csv_path in csv_files:
        print(f"\n📂 {csv_path.name}")
        stats = ingest_csv(conn, csv_path)
        print(f"   ✅ Inserted: {stats['inserted']:,}  |  Skipped (dupes): {stats['skipped']:,}  |  Errors: {stats['errors']}")
        total_inserted += stats['inserted']
        total_skipped += stats['skipped']

    print(f"\n   Total inserted: {total_inserted:,} | Total skipped: {total_skipped:,}")
    print_summary(conn)
    conn.close()
    print(f"\n✅ Done — {DB_PATH}")


if __name__ == "__main__":
    main()
