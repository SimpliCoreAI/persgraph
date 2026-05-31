#!/usr/bin/env python3
"""
PersGraph SQLite Query Helpers
Reusable functions for financial data analysis.
"""

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "persgraph.db"

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Return a WAL-mode connection with Row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_transactions_df(
    year: Optional[int] = None,
    category: Optional[str] = None,
    account: Optional[str] = None,
    db_path: Path = DB_PATH,
):
    """Return transactions as a DataFrame, optionally filtered."""
    assert HAS_PANDAS, "pandas required"
    conditions, params = [], []
    if year:
        conditions.append("year = ?"); params.append(year)
    if category:
        conditions.append("category LIKE ?"); params.append(f"%{category}%")
    if account:
        conditions.append("account LIKE ?"); params.append(f"%{account}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"SELECT * FROM transactions {where} ORDER BY date DESC"

    conn = get_connection(db_path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df


def get_fees_df(db_path: Path = DB_PATH):
    """Return all fee transactions joined with fee_rules classification."""
    assert HAS_PANDAS, "pandas required"
    query = """
        SELECT t.date, t.account, t.description, t.category, t.amount, t.year,
               fr.fee_type
        FROM transactions t
        JOIN fee_rules fr ON LOWER(t.description) LIKE LOWER(fr.pattern)
        ORDER BY t.date DESC
    """
    conn = get_connection(db_path)
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df


def get_monthly_summary(year: Optional[int] = None, db_path: Path = DB_PATH):
    """Return monthly income vs expense summary."""
    assert HAS_PANDAS, "pandas required"
    where = "WHERE year = ?" if year else ""
    params = [year] if year else []
    query = f"""
        SELECT
            strftime('%Y-%m', date) AS month,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) AS expenses,
            SUM(amount) AS net,
            COUNT(*) AS tx_count
        FROM transactions
        {where}
        GROUP BY month
        ORDER BY month
    """
    conn = get_connection(db_path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_category_summary(year: Optional[int] = None, db_path: Path = DB_PATH):
    """Return spend totals by category."""
    assert HAS_PANDAS, "pandas required"
    where = "WHERE year = ?" if year else ""
    params = [year] if year else []
    query = f"""
        SELECT
            COALESCE(category, 'Uncategorized') AS category,
            COUNT(*) AS tx_count,
            SUM(amount) AS total,
            AVG(amount) AS avg_amount
        FROM transactions
        {where}
        GROUP BY category
        ORDER BY total ASC
    """
    conn = get_connection(db_path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_accounts(db_path: Path = DB_PATH) -> list:
    """Return all accounts as a list of dicts."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_merchants(year: Optional[int] = None, limit: int = 20, db_path: Path = DB_PATH):
    """Return top merchants by total spend (expenses only)."""
    assert HAS_PANDAS, "pandas required"
    where = "WHERE amount < 0" + (" AND year = ?" if year else "")
    params = [year] if year else []
    query = f"""
        SELECT description, COUNT(*) AS tx_count, SUM(ABS(amount)) AS total_spent
        FROM transactions
        {where}
        GROUP BY description
        ORDER BY total_spent DESC
        LIMIT {limit}
    """
    conn = get_connection(db_path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


if __name__ == "__main__":
    # Quick test
    print("Accounts:", get_accounts())
    if HAS_PANDAS:
        fees = get_fees_df()
        print(f"\nFees found: {len(fees)} transactions")
        if not fees.empty:
            print(fees[['date','description','amount','fee_type']].head(10).to_string())

        monthly = get_monthly_summary()
        print(f"\nMonthly summary ({len(monthly)} months):")
        print(monthly.to_string())
