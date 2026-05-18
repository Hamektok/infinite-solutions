"""
insert_ammo_items.py
--------------------
Bulk-insert T1/T2/Faction/Structure ammunition items into tracked_market_items
with category='ammo' so they appear in the Import Tool.

Run once: python scripts/insert_ammo_items.py
"""
import sqlite3
import os
from collections import defaultdict

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

# group_id → subcategory key
GROUP_TO_SUBCAT = {
    # Hybrid Charges
    85:   'hybrid_charges',
    373:  'hybrid_charges',   # Advanced Railgun Charge
    377:  'hybrid_charges',   # Advanced Blaster Charge
    # Projectile Ammo
    83:   'projectile_ammo',
    372:  'projectile_ammo',  # Advanced Autocannon Ammo
    376:  'projectile_ammo',  # Advanced Artillery Ammo
    # Frequency Crystals
    86:   'frequency_crystals',
    374:  'frequency_crystals',  # Advanced Beam Laser Crystal
    375:  'frequency_crystals',  # Advanced Pulse Laser Crystal
    # Missiles (all types)
    88:   'missiles',   # Defender Missiles
    89:   'missiles',   # Torpedo
    384:  'missiles',   # Light Missile
    385:  'missiles',   # Heavy Missile
    386:  'missiles',   # Cruise Missile
    387:  'missiles',   # Rocket
    394:  'missiles',   # Auto-Targeting Light Missile
    395:  'missiles',   # Auto-Targeting Heavy Missile
    396:  'missiles',   # Auto-Targeting Cruise Missile
    476:  'missiles',   # XL Torpedo
    648:  'missiles',   # Advanced Rocket
    653:  'missiles',   # Advanced Light Missile
    654:  'missiles',   # Advanced Heavy Assault Missile
    655:  'missiles',   # Advanced Heavy Missile
    656:  'missiles',   # Advanced Cruise Missile
    657:  'missiles',   # Advanced Torpedo
    772:  'missiles',   # Heavy Assault Missile
    1677: 'missiles',   # Advanced XL Torpedo
    1678: 'missiles',   # Advanced XL Cruise Missile
    # Mining Crystals
    482:  'mining_crystals',
    663:  'mining_crystals',  # Mercoxit Mining Crystal
    # Cap Booster Charges
    87:   'cap_booster_charges',
    # Scripts
    1701: 'scripts',    # Flex Armor Hardener Script
    1702: 'scripts',    # Flex Shield Hardener Script
    # Nanite Repair Paste
    916:  'nanite_repair_paste',
    # Command Burst Charges
    1769: 'command_burst_charges',
    1771: 'command_burst_charges',
    1772: 'command_burst_charges',
    1773: 'command_burst_charges',
    1774: 'command_burst_charges',
    4905: 'command_burst_charges',
    # Bombs
    90:   'bombs',
    # Exotic Plasma Charges
    1987: 'exotic_plasma_charges',
    1989: 'exotic_plasma_charges',
    # Probes
    479:  'probes',
    492:  'probes',
    548:  'probes',
    # Breacher Pods
    4808: 'breacher_pods',
}

# display_order range start per subcategory
SUBCAT_ORDER_START = {
    'hybrid_charges':           0,
    'projectile_ammo':          100,
    'frequency_crystals':       200,
    'missiles':                 300,
    'mining_crystals':          500,
    'cap_booster_charges':      600,
    'scripts':                  700,
    'nanite_repair_paste':      800,
    'command_burst_charges':    900,
    'condenser_packs':          1000,
    'bombs':                    1100,
    'exotic_plasma_charges':    1200,
    'probes':                   1300,
    'breacher_pods':            1400,
    'structure_area_denial':    1500,
    'structure_guided_bombs':   1600,
}

conn = sqlite3.connect(DB_PATH)

# ── Gather items ─────────────────────────────────────────────────────────────
items = {}   # type_id → (type_name, subcat)

# 1. Known group_ids from inv_types
placeholders = ','.join('?' * len(GROUP_TO_SUBCAT))
rows = conn.execute(f"""
    SELECT type_id, type_name, group_id
    FROM inv_types
    WHERE published = 1
      AND group_id IN ({placeholders})
      AND (meta_group_id IS NULL OR meta_group_id IN (1, 2, 4, 54))
      AND type_name NOT LIKE '%Blueprint%'
      AND market_group_id IS NOT NULL
""", list(GROUP_TO_SUBCAT.keys())).fetchall()
for tid, tname, gid in rows:
    items[tid] = (tname, GROUP_TO_SUBCAT[gid])

# 2. Condenser Packs (group_id 4062 not in inv_groups — query by name)
rows2 = conn.execute("""
    SELECT type_id, type_name
    FROM inv_types
    WHERE published = 1
      AND type_name LIKE '%Condenser Pack%'
      AND type_name NOT LIKE '%Blueprint%'
      AND (meta_group_id IS NULL OR meta_group_id IN (1, 2, 4, 54))
""").fetchall()
for tid, tname in rows2:
    items[tid] = (tname, 'condenser_packs')

# 3. Structure Area Denial Ammunition (market_group_id 2820/2821)
rows3 = conn.execute("""
    SELECT type_id, type_name
    FROM inv_types
    WHERE published = 1
      AND market_group_id IN (2820, 2821)
      AND type_name NOT LIKE '%Blueprint%'
      AND (meta_group_id IS NULL OR meta_group_id IN (1, 2, 4, 54))
""").fetchall()
for tid, tname in rows3:
    items[tid] = (tname, 'structure_area_denial')

# 4. Structure Guided Bombs (market_group_id 2198)
rows4 = conn.execute("""
    SELECT type_id, type_name
    FROM inv_types
    WHERE published = 1
      AND market_group_id = 2198
      AND type_name NOT LIKE '%Blueprint%'
      AND (meta_group_id IS NULL OR meta_group_id IN (1, 2, 4, 54))
""").fetchall()
for tid, tname in rows4:
    items[tid] = (tname, 'structure_guided_bombs')

# ── Assign display_order: range_start + alphabetical index within subcat ─────
by_subcat = defaultdict(list)
for tid, (tname, subcat) in items.items():
    by_subcat[subcat].append((tname, tid))

rows_to_insert = []
for subcat, entries in by_subcat.items():
    entries.sort()   # alphabetical by type_name
    start = SUBCAT_ORDER_START.get(subcat, 9000)
    for idx, (tname, tid) in enumerate(entries):
        display_order = start + idx
        rows_to_insert.append((tid, tname, display_order))

# ── Insert ────────────────────────────────────────────────────────────────────
inserted = 0
skipped  = 0
for tid, tname, display_order in rows_to_insert:
    existing = conn.execute(
        "SELECT 1 FROM tracked_market_items WHERE type_id=?", (tid,)
    ).fetchone()
    if existing:
        skipped += 1
        continue
    conn.execute("""
        INSERT INTO tracked_market_items
            (type_id, type_name, category, display_order, price_percentage,
             alliance_discount, buyback_accepted)
        VALUES (?, ?, 'ammo', ?, 100, NULL, 0)
    """, (tid, tname, display_order))
    inserted += 1

conn.commit()
conn.close()

print(f"Done — {inserted} items inserted, {skipped} already existed.")
print(f"Total items found: {len(rows_to_insert)}")

# Print summary by subcategory
print("\nItems per subcategory:")
for subcat, entries in sorted(by_subcat.items(), key=lambda x: SUBCAT_ORDER_START.get(x[0], 9999)):
    print(f"  {subcat:<35}  {len(entries)}")
