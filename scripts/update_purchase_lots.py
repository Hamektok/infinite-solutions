"""
update_purchase_lots.py

For each new BUY wallet_transaction involving a tracked buyback item,
compute the expected revenue (using reprocessing yields for ores/ice/moon ore,
or direct JBV × sell% for final products) at the time of purchase and store
the result in the purchase_lots table.

Run after update_wallet_transactions.py so new transactions are already in DB.
"""
from script_utils import timed_script
import sqlite3
import json
import os
from datetime import datetime, timezone

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

# Categories that require reprocessing before sale
ORE_CATEGORIES    = {'standard_ore', 'ice_ore', 'moon_ore'}
# Categories sold directly (no reprocessing)
DIRECT_CATEGORIES = {'minerals', 'ice_products', 'moon_materials',
                     'pi_materials', 'salvaged_materials'}


def _nearest_jbv(cursor, type_id, before_ts):
    """Return (best_buy, snapshot_timestamp) for the nearest prior snapshot."""
    cursor.execute("""
        SELECT best_buy, timestamp FROM market_price_snapshots
        WHERE type_id = ? AND timestamp <= ?
        ORDER BY timestamp DESC LIMIT 1
    """, (type_id, before_ts))
    row = cursor.fetchone()
    if row and row[0] is not None:
        return row[0], row[1]
    return None, None


@timed_script
def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ── Config ──────────────────────────────────────────────────────────────
    cursor.execute("""
        SELECT key, value FROM site_config
        WHERE key IN ('ore_param_refine_eff')
    """)
    cfg = {r['key']: r['value'] for r in cursor.fetchall()}
    refine_eff = float(cfg.get('ore_param_refine_eff', '90.63')) / 100.0
    print(f"Refine efficiency: {refine_eff * 100:.2f}%")

    # ── Sell % per output product ────────────────────────────────────────────
    cursor.execute("SELECT key, value FROM site_config WHERE key LIKE 'ore_pct_%'")
    sell_pcts = {}
    for r in cursor.fetchall():
        try:
            tid = int(r['key'].replace('ore_pct_', ''))
            sell_pcts[tid] = float(r['value']) / 100.0
        except (ValueError, TypeError):
            pass

    # ── Tracked items ────────────────────────────────────────────────────────
    cursor.execute("SELECT type_id, category FROM tracked_market_items")
    tracked = {r['type_id']: r['category'] for r in cursor.fetchall()}
    tracked_ids = list(tracked.keys())
    print(f"Tracked buyback items: {len(tracked_ids)}")

    # ── Type names ───────────────────────────────────────────────────────────
    ph = ','.join('?' * len(tracked_ids))
    cursor.execute(f"SELECT type_id, type_name FROM inv_types WHERE type_id IN ({ph})",
                   tracked_ids)
    type_names = {r['type_id']: r['type_name'] for r in cursor.fetchall()}

    # ── Reprocessing yields for ore/ice/moon_ore items ───────────────────────
    ore_ids = [tid for tid, cat in tracked.items() if cat in ORE_CATEGORIES]
    yields_data = {}
    if ore_ids:
        ore_ph = ','.join('?' * len(ore_ids))
        cursor.execute(f"""
            SELECT tm.type_id, tm.materials_json, it.portion_size
            FROM type_materials tm
            JOIN inv_types it ON tm.type_id = it.type_id
            WHERE tm.type_id IN ({ore_ph})
        """, ore_ids)
        for r in cursor.fetchall():
            yields_data[r['type_id']] = (json.loads(r['materials_json']),
                                          r['portion_size'])

    # ── New BUY transactions not yet in purchase_lots ────────────────────────
    cursor.execute(f"""
        SELECT wt.transaction_id, wt.date, wt.type_id, wt.quantity, wt.unit_price
        FROM wallet_transactions wt
        LEFT JOIN purchase_lots pl ON wt.transaction_id = pl.transaction_id
        WHERE wt.is_buy = 1
          AND wt.type_id IN ({ph})
          AND pl.transaction_id IS NULL
        ORDER BY wt.date ASC
    """, tracked_ids)
    new_txns = cursor.fetchall()
    print(f"New BUY transactions to process: {len(new_txns)}")

    inserted    = 0
    no_snapshot = 0
    skipped     = 0
    now         = datetime.now(timezone.utc).isoformat()

    for txn in new_txns:
        txn_id   = txn['transaction_id']
        txn_date = txn['date']
        tid      = txn['type_id']
        qty      = txn['quantity']
        paid     = txn['unit_price']
        category = tracked.get(tid, '')
        total_cost = qty * paid

        exp_rev    = None
        exp_profit = None
        margin_pct = None
        snap_ts    = None
        refine_used = None

        if category in ORE_CATEGORIES:
            # ── Reprocessing path ────────────────────────────────────────────
            if tid not in yields_data:
                skipped += 1
                continue  # no yield data, skip

            mats, portion_size = yields_data[tid]
            total_batches = qty / portion_size
            batch_rev  = 0.0
            oldest_snap = None
            missing    = False

            for mat in mats:
                mat_id  = mat['materialTypeID']
                mat_qty = mat['quantity']
                jbv, snap = _nearest_jbv(cursor, mat_id, txn_date)
                if jbv is None:
                    missing = True
                    break
                mat_sell_pct = sell_pcts.get(mat_id, 0.97)
                batch_rev += mat_qty * refine_eff * jbv * mat_sell_pct
                # Track the oldest snapshot used (weakest price reference)
                if oldest_snap is None or snap < oldest_snap:
                    oldest_snap = snap

            if missing:
                no_snapshot += 1
                # Insert with cost tracked but value unknown
            else:
                exp_rev    = batch_rev * total_batches
                exp_profit = exp_rev - total_cost
                margin_pct = (exp_profit / total_cost * 100) if total_cost > 0 else None
                snap_ts    = oldest_snap
                refine_used = refine_eff

        elif category in DIRECT_CATEGORIES:
            # ── Direct sell path ─────────────────────────────────────────────
            jbv, snap = _nearest_jbv(cursor, tid, txn_date)
            if jbv is None:
                no_snapshot += 1
                # Insert with cost tracked but value unknown
            else:
                item_sell_pct = sell_pcts.get(tid, 0.97)
                exp_rev    = qty * jbv * item_sell_pct
                exp_profit = exp_rev - total_cost
                margin_pct = (exp_profit / total_cost * 100) if total_cost > 0 else None
                snap_ts    = snap

        else:
            skipped += 1
            continue  # unknown category

        cursor.execute("""
            INSERT OR REPLACE INTO purchase_lots
                (transaction_id, date, type_id, type_name, category,
                 quantity, price_paid, total_cost, snapshot_ts,
                 expected_revenue, expected_profit, margin_pct,
                 refine_eff, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn_id, txn_date, tid, type_names.get(tid, f'Type {tid}'),
            category, qty, paid, total_cost, snap_ts,
            exp_rev, exp_profit, margin_pct, refine_used, now
        ))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"\nResults:")
    print(f"  Inserted:              {inserted}")
    print(f"  No snapshot (cost only): {no_snapshot}")
    print(f"  Skipped (no yield data): {skipped}")


if __name__ == '__main__':
    main()
