"""
Create Build Service DB tables and site_config defaults.
Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
"""
import sqlite3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

DDL = """
-- ── Build Requests ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS build_requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now')),
    status              TEXT    DEFAULT 'pending',
    lookup_token        TEXT    UNIQUE,

    -- Customer
    customer_name       TEXT    NOT NULL,
    character_id        INTEGER,
    character_name      TEXT,

    -- What to build
    item_type_id        INTEGER,
    item_name           TEXT    NOT NULL,
    quantity            INTEGER DEFAULT 1,
    is_doctrine_fit     INTEGER DEFAULT 0,
    doctrine_fit_id     INTEGER,

    -- Delivery
    delivery_location   TEXT    DEFAULT 'LX-ZOJ Sotiyo',
    deadline            TEXT,
    notes               TEXT,

    -- Pricing (set by admin)
    materials_cost_est  REAL,
    job_cost_est        REAL,
    markup_pct          REAL    DEFAULT 15.0,
    quote_price         REAL,

    -- Assignment
    builder_id          INTEGER,
    assigned_at         TEXT,

    -- Completion
    contract_id         INTEGER,
    contract_price_actual REAL,
    builder_pct         REAL,
    builder_isk         REAL,
    corp_isk            REAL,
    completed_at        TEXT
);

-- ── Build Request Line Items (doctrine fits / multi-item orders) ──────────
CREATE TABLE IF NOT EXISTS build_request_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id          INTEGER NOT NULL REFERENCES build_requests(id),
    type_id             INTEGER,
    item_name           TEXT,
    quantity            INTEGER,
    unit_material_cost  REAL
);

-- ── Builder Pool ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS build_builders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id        INTEGER UNIQUE,
    character_name      TEXT    NOT NULL,
    active              INTEGER DEFAULT 1,
    specializations     TEXT    DEFAULT '[]',
    default_builder_pct REAL    DEFAULT 70.0,
    notes               TEXT,
    created_at          TEXT    DEFAULT (datetime('now'))
);

-- ── Payout Ledger ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS build_payouts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    builder_id          INTEGER NOT NULL REFERENCES build_builders(id),
    request_id          INTEGER NOT NULL REFERENCES build_requests(id),
    isk_owed            REAL,
    paid                INTEGER DEFAULT 0,
    paid_date           TEXT,
    notes               TEXT
);

-- ── ESI Adjusted Prices (for EIV / job cost calc) ────────────────────────
CREATE TABLE IF NOT EXISTS adjusted_prices (
    type_id             INTEGER PRIMARY KEY,
    adjusted_price      REAL,
    average_price       REAL,
    fetched_at          TEXT    DEFAULT (datetime('now'))
);
"""

SITE_CONFIG_DEFAULTS = [
    ('build_discord_webhook',       ''),        # set this to your webhook URL
    ('build_default_markup_pct',    '15'),
    ('build_default_builder_pct',   '70'),
    ('build_alliance_id',           '498125261'),  # TEST Alliance Please Ignore
    ('build_delivery_default',      'LX-ZOJ Sotiyo'),
    ('build_redirect_uri',          'http://localhost:5000/auth/callback'),
]


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create tables
    cur.executescript(DDL)
    print('Tables created (or already exist).')

    # Insert site_config defaults (skip if key already present)
    for key, val in SITE_CONFIG_DEFAULTS:
        cur.execute(
            'INSERT OR IGNORE INTO site_config (key, value) VALUES (?, ?)',
            (key, val)
        )
    conn.commit()
    print('site_config defaults inserted.')

    # Verify
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'build_%' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f'\nBuild service tables: {tables}')

    cur.execute("SELECT key, value FROM site_config WHERE key LIKE 'build_%' ORDER BY key")
    print('\nsite_config (build_*):')
    for k, v in cur.fetchall():
        print(f'  {k} = {v!r}')

    conn.close()


if __name__ == '__main__':
    run()
