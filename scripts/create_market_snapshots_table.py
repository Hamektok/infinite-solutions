"""
create_market_snapshots_table.py
---------------------------------
One-time migration: creates the market_snapshots table for multi-hub
price history tracking.

Existing tables (market_price_snapshots, etc.) are NOT modified.

Run once:  python scripts/create_market_snapshots_table.py

Safe to re-run — CREATE TABLE IF NOT EXISTS is used throughout.
"""

import os
import sqlite3

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

# Known hub stations for reference (stored here, not in DB — no FK needed)
HUBS = {
    'Jita':    {'region_id': 10000002, 'station_id': 60003760},
    'Amarr':   {'region_id': 10000043, 'station_id': 60008494},
    'Dodixie': {'region_id': 10000032, 'station_id': 60011866},
    'Rens':    {'region_id': 10000030, 'station_id': 60004588},
    'Hek':     {'region_id': 10000042, 'station_id': 60005686},
}


def main():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    # ── market_snapshots ──────────────────────────────────────────────────────
    # Multi-hub price history.  One row per (station, type_id, fetch).
    # Replaces the implicit "Jita-only" assumption in market_price_snapshots.
    # The existing market_price_snapshots table is left intact.
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at   TEXT    NOT NULL,       -- ISO8601 UTC timestamp of fetch
            region_id    INTEGER NOT NULL,        -- ESI region (10000002=The Forge, etc.)
            station_id   INTEGER NOT NULL,        -- Hub station (60003760=Jita 4-4, etc.)
            type_id      INTEGER NOT NULL,
            best_buy     REAL,                    -- highest buy order at station
            best_sell    REAL,                    -- lowest sell order at station
            spread_pct   REAL,                    -- (best_sell-best_buy)/best_buy*100
            buy_volume   INTEGER DEFAULT 0,       -- total volume_remain on buy orders
            sell_volume  INTEGER DEFAULT 0        -- total volume_remain on sell orders
        )
    """)

    # Primary lookup: latest price for a (station, type) pair
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_msnap_station_type_time
        ON market_snapshots(station_id, type_id, fetched_at DESC)
    """)

    # Cross-hub price comparison: latest price for a type across all stations
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_msnap_type_time
        ON market_snapshots(type_id, fetched_at DESC)
    """)

    # History query: all snapshots for a (station, type) ordered by time
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_msnap_station_type_history
        ON market_snapshots(station_id, type_id, fetched_at)
    """)

    conn.commit()
    conn.close()

    print("market_snapshots table and indexes created (or already exist).")
    print()
    print("Hub reference:")
    for name, info in HUBS.items():
        print(f"  {name:<8}  region_id={info['region_id']}  station_id={info['station_id']}")
    print()
    print("Retention: fetch_hub_prices.py prunes rows older than the configured")
    print("  retention window (site_config key: market_snapshot_retention_days,")
    print("  default 90 days).")


if __name__ == '__main__':
    main()
