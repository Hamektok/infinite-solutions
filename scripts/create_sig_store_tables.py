"""
create_sig_store_tables.py

One-time DB migration to support the Alliance SIG Store (sig_store.html).

Run once:  python scripts/create_sig_store_tables.py
Safe to re-run — all operations are idempotent.
"""
import os, sqlite3

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Add 'site' column to tracked_market_items if it doesn't exist
    c.execute("PRAGMA table_info(tracked_market_items)")
    cols = [row[1] for row in c.fetchall()]
    if 'site' not in cols:
        c.execute("ALTER TABLE tracked_market_items ADD COLUMN site TEXT NOT NULL DEFAULT 'lxzoj'")
        print("[OK] Added 'site' column to tracked_market_items (default: lxzoj)")
    else:
        print("[--] 'site' column already exists in tracked_market_items")

    # 2. Create fw_current_inventory table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fw_current_inventory (
            type_id            INTEGER,
            type_name          TEXT,
            quantity           INTEGER,
            snapshot_timestamp DATETIME
        )
    ''')
    print("[OK] fw_current_inventory table ready")

    # 3. Seed site_config keys for FW structure
    for key, value in [
        ('fw_structure_id',   ''),
        ('fw_structure_name', ''),
    ]:
        c.execute("INSERT OR IGNORE INTO site_config (key, value) VALUES (?, ?)", (key, value))
        if c.rowcount:
            print(f"[OK] site_config key '{key}' inserted")
        else:
            print(f"[--] site_config key '{key}' already exists")

    # 4. Seed visibility config keys for FW sub-tabs
    for sub_key in ['hybrid', 'projectile', 'laser', 'missiles', 'consumables']:
        key = f'sig_fw_sub_{sub_key}'
        c.execute("INSERT OR IGNORE INTO site_config (key, value) VALUES (?, ?)", (key, '1'))
        if c.rowcount:
            print(f"[OK] site_config key '{key}' inserted (default: visible)")
        else:
            print(f"[--] site_config key '{key}' already exists")

    conn.commit()
    conn.close()
    print("\nMigration complete.")


if __name__ == '__main__':
    main()
