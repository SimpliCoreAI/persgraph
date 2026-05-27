-- PersGraph SQLite Schema
-- transactions: core ledger
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,           -- ISO format YYYY-MM-DD
    account     TEXT NOT NULL,
    description TEXT NOT NULL,
    category    TEXT,
    tags        TEXT,
    amount      REAL NOT NULL,
    year        INTEGER NOT NULL,
    source_file TEXT,
    hash        TEXT UNIQUE             -- dedup key: md5(date+account+description+amount)
);
CREATE INDEX IF NOT EXISTS idx_date     ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_account  ON transactions(account);
CREATE INDEX IF NOT EXISTS idx_year     ON transactions(year);

-- accounts: parsed from transaction data
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    type        TEXT,                   -- checking, savings, credit, investment
    institution TEXT,
    last4       TEXT
);

-- fee_rules: pattern-based fee classification
CREATE TABLE IF NOT EXISTS fee_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern     TEXT NOT NULL,          -- LIKE pattern, e.g. '%fee%'
    fee_type    TEXT NOT NULL           -- e.g. 'late_fee', 'annual_fee', 'interest'
);

-- Default fee rules
INSERT OR IGNORE INTO fee_rules (pattern, fee_type) VALUES
    ('%interest charge%', 'interest'),
    ('%late fee%', 'late_fee'),
    ('%annual fee%', 'annual_fee'),
    ('%annual membership%', 'annual_fee'),
    ('%plan fee%', 'plan_fee'),
    ('%maintenance fee%', 'maintenance_fee'),
    ('%foreign transaction%', 'foreign_transaction_fee'),
    ('%cash advance fee%', 'cash_advance_fee');
