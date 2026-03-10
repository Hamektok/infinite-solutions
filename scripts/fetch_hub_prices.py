"""
fetch_hub_prices.py
-------------------
Fetch best-buy / best-sell prices across all 5 EVE trade hubs,
storing results in market_snapshots for multi-hub import analysis.

Run on-demand from the Multi-Hub Import Analysis tab in admin_dashboard.py.

Usage:
    python scripts/fetch_hub_prices.py [category] [hubs]

    category : standard | ice | moon | gas | tracked | all  (default: all)
    hubs     : all | jita | amarr | dodixie | rens | hek    (default: all)
               Multiple hubs comma-separated: jita,amarr

    'tracked' fetches all type_ids currently in tracked_market_items
    (minerals, ice products, PI materials, moon materials, salvaged materials).

Typical runtime: 15-60 s for all hubs (50 workers per hub, sequential).
"""

import os
import sys
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

# ── ESI ────────────────────────────────────────────────────────────────────
ESI_BASE        = 'https://esi.evetech.net/latest'
MAX_WORKERS     = 50
REQUEST_TIMEOUT = 8

# ── Hub definitions ────────────────────────────────────────────────────────
HUBS = {
    'jita':    {'region_id': 10000002, 'station_id': 60003760},
    'amarr':   {'region_id': 10000043, 'station_id': 60008494},
    'dodixie': {'region_id': 10000032, 'station_id': 60011866},
    'rens':    {'region_id': 10000030, 'station_id': 60004588},
    'hek':     {'region_id': 10000042, 'station_id': 60005686},
}

DEFAULT_RETENTION_DAYS = 90

# ── Type ID lists ──────────────────────────────────────────────────────────

# Standard ores — base + II/III/IV grades (uncompressed)
STD_ORE_IDS = [
    1230, 17470, 17471, 46689,   # Veldspar
    1228, 17463, 17464, 46687,   # Scordite
    1224, 17459, 17460, 46686,   # Pyroxeres
    18,   17455, 17456, 46685,   # Plagioclase
    1227, 17867, 17868, 46684,   # Omber
    20,   17452, 17453, 46683,   # Kernite
    21,   17440, 17441, 46680,   # Hedbergite
    1231, 17444, 17445, 46681,   # Hemorphite
    1226, 17448, 17449, 46682,   # Jaspet
    1229, 17865, 17866, 46679,   # Gneiss
    1232, 17436, 17437, 46675,   # Dark Ochre
    1225, 17432, 17433, 46677,   # Crokite
    19,   17466, 17467, 46688,   # Spodumain
    1223, 17428, 17429, 46676,   # Bistot
    22,   17425, 17426, 46678,   # Arkonor
    11396, 17869, 17870,         # Mercoxit (no IV grade)
]

COMPRESSED_STD_ORE_IDS = [
    62516, 62517, 62518, 62519,  # Veldspar
    62520, 62521, 62522, 62523,  # Scordite
    62524, 62525, 62526, 62527,  # Pyroxeres
    62528, 62529, 62530, 62531,  # Plagioclase
    62532, 62533, 62534, 62535,  # Omber
    62536, 62537, 62538, 62539,  # Kernite
    62540, 62541, 62542, 62543,  # Jaspet
    62544, 62545, 62546, 62547,  # Hemorphite
    62548, 62549, 62550, 62551,  # Hedbergite
    62552, 62553, 62554, 62555,  # Gneiss
    62556, 62557, 62558, 62559,  # Dark Ochre
    62560, 62561, 62562, 62563,  # Crokite
    62564, 62565, 62566, 62567,  # Bistot
    62568, 62569, 62570, 62571,  # Arkonor
    62572, 62573, 62574, 62575,  # Spodumain
    62586, 62587, 62588,         # Mercoxit
]

ANOMALY_ORE_IDS = [
    81900, 81901, 81902, 81903,  # Kylixium
    82016, 82017, 82018, 82019,  # Nocxite
    82205, 82206, 82207, 82208,  # Ueganite
    82163, 82164, 82165, 82166,  # Hezorime
    81975, 81976, 81977, 81978,  # Griemeer
]

COMPRESSED_ANOMALY_ORE_IDS = [
    82300, 82301, 82302, 82303,  # Compressed Kylixium
    82304, 82305, 82306, 82307,  # Compressed Nocxite
    82308, 82309, 82310, 82311,  # Compressed Ueganite
    82312, 82313, 82314, 82315,  # Compressed Hezorime
    82316, 82317, 82318, 82319,  # Compressed Griemeer
]

A0_RARE_ORE_IDS = [
    74521, 74522, 74523, 74524,  # Mordunium
    74525, 74526, 74527, 74528,  # Ytirium
    74529, 74530, 74531, 74532,  # Eifyrium
    74533, 74534, 74535, 74536,  # Ducinium
]

COMPRESSED_A0_RARE_ORE_IDS = [
    75275, 75276, 75277, 75278,  # Compressed Mordunium
    75279, 75280, 75281, 75282,  # Compressed Ytirium
    75283, 75284, 75285, 75286,  # Compressed Eifyrium
    75287, 75288, 75289, 75290,  # Compressed Ducinium
]

ICE_IDS = [
    16262, 16263, 16264, 16265, 16266, 16267, 16268, 16269,
    17975, 17976, 17977, 17978,
]

COMPRESSED_ICE_IDS = [
    28433, 28443, 28434, 28436, 28435, 28437, 28438, 28442,
    28439, 28440, 28444, 28441,
]

MOON_ORE_IDS = [
    45490, 45491, 45492, 45493,  # Ubiquitous base
    46280, 46282, 46284, 46286, 46281, 46283, 46285, 46287,
    45494, 45495, 45496, 45497,  # Common base
    46288, 46290, 46292, 46294, 46289, 46291, 46293, 46295,
    45498, 45499, 45500, 45501,  # Uncommon base
    46296, 46298, 46300, 46302, 46297, 46299, 46301, 46303,
    45502, 45503, 45504, 45506,  # Rare base
    46304, 46306, 46308, 46310, 46305, 46307, 46309, 46311,
    45510, 45511, 45512, 45513,  # Exceptional base
    46312, 46314, 46316, 46318, 46313, 46315, 46317, 46319,
]

COMPRESSED_MOON_ORE_IDS = [
    62454, 62457, 62455, 62458, 62461, 62464,
    62456, 62459, 62466, 62467, 62460, 62463,
    62474, 62471, 62468, 62477, 62475, 62472, 62469, 62478, 62476, 62473, 62470, 62479,
    62480, 62483, 62486, 62489, 62481, 62484, 62487, 62490, 62482, 62485, 62488, 62491,
    62492, 62501, 62498, 62495, 62493, 62502, 62499, 62496, 62494, 62503, 62500, 62497,
    62504, 62510, 62507, 62513, 62505, 62511, 62508, 62514, 62506, 62512, 62509, 62515,
]

# Gas: Fullerites (w-space) + Cytoserocin + Mykoserocin (k-space)
GAS_IDS = [
    # Fullerites
    30370, 30371, 30372, 30373, 30374, 30375, 30376,
    # Cytoserocin (8 variants)
    25264, 25265, 25266, 25267, 25268, 25269, 25270, 25271,
    # Mykoserocin (8 variants)
    25272, 25273, 25274, 25275, 25276, 25277, 25278, 25279,
]

ALL_ORE_IDS = list(set(
    STD_ORE_IDS + COMPRESSED_STD_ORE_IDS +
    ANOMALY_ORE_IDS + COMPRESSED_ANOMALY_ORE_IDS +
    A0_RARE_ORE_IDS + COMPRESSED_A0_RARE_ORE_IDS +
    ICE_IDS + COMPRESSED_ICE_IDS +
    MOON_ORE_IDS + COMPRESSED_MOON_ORE_IDS
))


# ── DB helpers ─────────────────────────────────────────────────────────────

def get_tracked_type_ids(conn):
    """Return all type_ids from tracked_market_items."""
    c = conn.cursor()
    c.execute("SELECT DISTINCT type_id FROM tracked_market_items")
    return [row[0] for row in c.fetchall()]


def get_retention_days(conn):
    c = conn.cursor()
    c.execute("SELECT value FROM site_config WHERE key='market_snapshot_retention_days'")
    row = c.fetchone()
    return int(row[0]) if row else DEFAULT_RETENTION_DAYS


def prune_old_snapshots(conn):
    days   = get_retention_days(conn)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    c      = conn.cursor()
    c.execute("DELETE FROM market_snapshots WHERE fetched_at < ?", (cutoff.isoformat(),))
    conn.commit()
    return c.rowcount


# ── ESI fetch ──────────────────────────────────────────────────────────────

def fetch_hub_price(type_id, region_id, station_id):
    """
    Fetch orders for one type_id in a region, filter to a specific station,
    and return (type_id, best_buy, best_sell, buy_volume, sell_volume).
    Returns Nones on error or no orders at that station.
    """
    url = f'{ESI_BASE}/markets/{region_id}/orders/'
    try:
        resp = requests.get(
            url,
            params={'type_id': type_id, 'order_type': 'all'},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return type_id, None, None, None, None

        orders = [o for o in resp.json() if o['location_id'] == station_id]
        buys   = [(o['price'], o.get('volume_remain', 0)) for o in orders if     o['is_buy_order']]
        sells  = [(o['price'], o.get('volume_remain', 0)) for o in orders if not o['is_buy_order']]

        best_buy  = max(p for p, _ in buys)  if buys  else None
        best_sell = min(p for p, _ in sells) if sells else None
        return type_id, best_buy, best_sell, sum(v for _, v in buys), sum(v for _, v in sells)

    except Exception:
        return type_id, None, None, None, None


def fetch_and_store(type_ids, hub_name, hub_info, conn):
    """Fetch prices for all type_ids at one hub and insert into market_snapshots."""
    region_id  = hub_info['region_id']
    station_id = hub_info['station_id']
    total      = len(type_ids)
    ts         = datetime.now(timezone.utc).isoformat()
    results    = []
    errors     = 0

    print(f'  [{hub_name.upper()}] {total} type IDs  '
          f'(region={region_id}, station={station_id})...')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(fetch_hub_price, tid, region_id, station_id): tid
                   for tid in type_ids}
        done = 0
        for future in as_completed(futures):
            tid, bb, bs, bv, sv = future.result()
            done += 1
            if bb is None and bs is None:
                errors += 1
            spread = ((bs - bb) / bb * 100) if (bb and bs and bb > 0) else None
            results.append((ts, region_id, station_id, tid,
                             bb, bs, spread, bv or 0, sv or 0))
            print(f'\r    {done}/{total} fetched — {done - errors} priced, '
                  f'{errors} no orders', end='', flush=True)

    print(f'\n    Inserting {len(results)} rows...')
    c = conn.cursor()
    c.executemany(
        '''INSERT INTO market_snapshots
               (fetched_at, region_id, station_id, type_id,
                best_buy, best_sell, spread_pct, buy_volume, sell_volume)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        results,
    )
    conn.commit()
    print(f'    Done — {errors} items had no orders at {hub_name.title()}.')


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    category = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    hubs_arg = sys.argv[2].lower() if len(sys.argv) > 2 else 'all'

    # Hub selection
    if hubs_arg == 'all':
        target_hubs = HUBS
    else:
        target_hubs = {}
        for h in hubs_arg.split(','):
            h = h.strip()
            if h not in HUBS:
                print(f'Unknown hub "{h}". Valid: {", ".join(HUBS)}')
                sys.exit(1)
            target_hubs[h] = HUBS[h]

    conn = sqlite3.connect(DB_PATH, timeout=30)

    # Build type ID list
    if category == 'tracked':
        type_ids = get_tracked_type_ids(conn)
        label    = f'tracked_market_items ({len(type_ids)} type IDs from DB)'
    elif category == 'standard':
        type_ids = list(set(
            STD_ORE_IDS + COMPRESSED_STD_ORE_IDS +
            ANOMALY_ORE_IDS + COMPRESSED_ANOMALY_ORE_IDS +
            A0_RARE_ORE_IDS + COMPRESSED_A0_RARE_ORE_IDS
        ))
        label = f'standard ores ({len(type_ids)} type IDs)'
    elif category == 'ice':
        type_ids = list(set(ICE_IDS + COMPRESSED_ICE_IDS))
        label    = f'ice ore ({len(type_ids)} type IDs)'
    elif category == 'moon':
        type_ids = list(set(MOON_ORE_IDS + COMPRESSED_MOON_ORE_IDS))
        label    = f'moon ore ({len(type_ids)} type IDs)'
    elif category == 'gas':
        type_ids = list(set(GAS_IDS))
        label    = f'gas ({len(type_ids)} type IDs)'
    elif category == 'all':
        tracked  = get_tracked_type_ids(conn)
        type_ids = list(set(ALL_ORE_IDS + GAS_IDS + tracked))
        label    = f'all ({len(type_ids)} type IDs)'
    else:
        print(f'Unknown category "{category}". '
              f'Use: standard | ice | moon | gas | tracked | all')
        conn.close()
        sys.exit(1)

    print(f'fetch_hub_prices — {label}')
    print(f'Hubs: {", ".join(target_hubs)}')
    print()

    for hub_name, hub_info in target_hubs.items():
        fetch_and_store(type_ids, hub_name, hub_info, conn)
        print()

    print('Pruning old snapshots...')
    deleted = prune_old_snapshots(conn)
    print(f'Pruned {deleted} rows older than {get_retention_days(conn)}-day retention window.')
    conn.close()
    print('\nAll done.')


if __name__ == '__main__':
    main()
