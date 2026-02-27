"""
fetch_ore_prices.py
-------------------
Fetch Jita 4-4 best-buy / best-sell prices for all raw mined materials
(standard ores, ice, moon ores) and their refined products (minerals,
ice products, moon materials) using parallel ESI requests.

Stores results in market_price_snapshots.  Run on-demand from the
Ore Import Analysis tab in admin_dashboard.py.

Typical runtime: 5-15 seconds with 50 worker threads.
"""

import os
import sys
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

# ── ESI constants ──────────────────────────────────────────────────────────
ESI_BASE           = 'https://esi.evetech.net/latest'
THE_FORGE_REGION   = 10000002
JITA_STATION_ID    = 60003760   # Jita IV - Moon 4 - Caldari Navy Assembly Plant
MAX_WORKERS        = 50         # more parallel → fewer rounds → faster total
REQUEST_TIMEOUT    = 8          # seconds per call; fail fast rather than hang

# ── Type IDs to fetch ──────────────────────────────────────────────────────

# Standard ores — base + II/III/IV grades (uncompressed only)
STD_ORE_IDS = [
    # Veldspar
    1230, 17470, 17471, 46689,
    # Scordite
    1228, 17463, 17464, 46687,
    # Pyroxeres
    1224, 17459, 17460, 46686,
    # Plagioclase
    18, 17455, 17456, 46685,
    # Omber
    1227, 17867, 17868, 46684,
    # Kernite
    20, 17452, 17453, 46683,
    # Hedbergite
    21, 17440, 17441, 46680,
    # Hemorphite
    1231, 17444, 17445, 46681,
    # Jaspet
    1226, 17448, 17449, 46682,
    # Gneiss
    1229, 17865, 17866, 46679,
    # Dark Ochre
    1232, 17436, 17437, 46675,
    # Crokite
    1225, 17432, 17433, 46677,
    # Spodumain
    19, 17466, 17467, 46688,
    # Bistot
    1223, 17428, 17429, 46676,
    # Arkonor
    22, 17425, 17426, 46678,
    # Mercoxit (no IV grade)
    11396, 17869, 17870,
]

# Standard ores — compressed (same yields as uncompressed, ~100x smaller volume)
COMPRESSED_STD_ORE_IDS = [
    # Veldspar
    62516, 62517, 62518, 62519,
    # Scordite
    62520, 62521, 62522, 62523,
    # Pyroxeres
    62524, 62525, 62526, 62527,
    # Plagioclase
    62528, 62529, 62530, 62531,
    # Omber
    62532, 62533, 62534, 62535,
    # Kernite
    62536, 62537, 62538, 62539,
    # Jaspet
    62540, 62541, 62542, 62543,
    # Hemorphite
    62544, 62545, 62546, 62547,
    # Hedbergite
    62548, 62549, 62550, 62551,
    # Gneiss
    62552, 62553, 62554, 62555,
    # Dark Ochre
    62556, 62557, 62558, 62559,
    # Crokite
    62560, 62561, 62562, 62563,
    # Bistot
    62564, 62565, 62566, 62567,
    # Arkonor
    62568, 62569, 62570, 62571,
    # Spodumain
    62572, 62573, 62574, 62575,
    # Mercoxit (no IV grade)
    62586, 62587, 62588,
]

# Ice — base types + IV-grade variants
ICE_IDS = [
    16262,  # Clear Icicle
    16263,  # Glacial Mass
    16264,  # Blue Ice
    16265,  # White Glaze
    16266,  # Glare Crust
    16267,  # Dark Glitter
    16268,  # Gelidus
    16269,  # Krystallos
    17975,  # Blue Ice IV-Grade
    17976,  # White Glaze IV-Grade
    17977,  # Glacial Mass IV-Grade
    17978,  # Clear Icicle IV-Grade
]

# Ice — compressed variants
COMPRESSED_ICE_IDS = [
    28433,  # Compressed Blue Ice
    28443,  # Compressed Blue Ice IV-Grade
    28434,  # Compressed Clear Icicle
    28436,  # Compressed Clear Icicle IV-Grade
    28435,  # Compressed Dark Glitter
    28437,  # Compressed Gelidus
    28438,  # Compressed Glacial Mass
    28442,  # Compressed Glacial Mass IV-Grade
    28439,  # Compressed Glare Crust
    28440,  # Compressed Krystallos
    28444,  # Compressed White Glaze
    28441,  # Compressed White Glaze IV-Grade
]

# Moon ores — base + grade variants (Brimful/Glistening, Copious/Twinkling, etc.)
MOON_ORE_IDS = [
    # Ubiquitous — base
    45490, 45491, 45492, 45493,
    # Ubiquitous — Brimful (+15%)
    46280, 46282, 46284, 46286,
    # Ubiquitous — Glistening (+100%)
    46281, 46283, 46285, 46287,
    # Common — base
    45494, 45495, 45496, 45497,
    # Common — Copious (+15%)
    46288, 46290, 46292, 46294,
    # Common — Twinkling (+100%)
    46289, 46291, 46293, 46295,
    # Uncommon — base
    45498, 45499, 45500, 45501,
    # Uncommon — Lavish (+15%)
    46296, 46298, 46300, 46302,
    # Uncommon — Shimmering (+100%)
    46297, 46299, 46301, 46303,
    # Rare — base
    45502, 45503, 45504, 45506,
    # Rare — Replete (+15%)
    46304, 46306, 46308, 46310,
    # Rare — Glowing (+100%)
    46305, 46307, 46309, 46311,
    # Exceptional — base
    45510, 45511, 45512, 45513,
    # Exceptional — Bountiful (+15%)
    46312, 46314, 46316, 46318,
    # Exceptional — Shining (+100%)
    46313, 46315, 46317, 46319,
]

# Moon ores — compressed variants
COMPRESSED_MOON_ORE_IDS = [
    # Ubiquitous
    62454, 62457, 62455, 62458, 62461, 62464,  # Bitumens/Coesite/Sylvite/Zeolites + grades
    62456, 62459, 62466, 62467,                 # Glistening variants
    62460, 62463,                               # Sylvite/Zeolites base compressed
    # Common
    62474, 62471, 62468, 62477,                 # Cobaltite/Euxenite/Scheelite/Titanite
    62475, 62472, 62469, 62478,                 # Copious variants
    62476, 62473, 62470, 62479,                 # Twinkling variants
    # Uncommon
    62480, 62483, 62486, 62489,                 # Chromite/Otavite/Sperrylite/Vanadinite
    62481, 62484, 62487, 62490,                 # Lavish variants
    62482, 62485, 62488, 62491,                 # Shimmering variants
    # Rare
    62492, 62501, 62498, 62495,                 # Carnotite/Zircon/Pollucite/Cinnabar
    62493, 62502, 62499, 62496,                 # Replete variants
    62494, 62503, 62500, 62497,                 # Glowing variants
    # Exceptional
    62504, 62510, 62507, 62513,                 # Loparite/Xenotime/Monazite/Ytterbite
    62505, 62511, 62508, 62514,                 # Bountiful variants
    62506, 62512, 62509, 62515,                 # Shining variants
]

# Refined products — standard minerals
MINERAL_IDS = [
    34,     # Tritanium
    35,     # Pyerite
    36,     # Mexallon
    37,     # Isogen
    38,     # Nocxium
    39,     # Zydrine
    40,     # Megacyte
    11399,  # Morphite
]

# Refined products — ice products
ICE_PRODUCT_IDS = [
    16272,  # Heavy Water
    16273,  # Liquid Ozone
    16274,  # Helium Isotopes
    16275,  # Strontium Clathrates
    17887,  # Oxygen Isotopes
    17888,  # Nitrogen Isotopes
    17889,  # Hydrogen Isotopes
]

# Refined products — moon materials (R4 through R64)
MOON_MATERIAL_IDS = [
    # R4 Ubiquitous
    16633,  # Hydrocarbons
    16634,  # Atmospheric Gases
    16635,  # Evaporite Deposits
    16636,  # Silicates
    # R8 Common
    16637,  # Tungsten
    16638,  # Titanium
    16639,  # Scandium
    16640,  # Cobalt
    # R16 Uncommon
    16641,  # Chromium
    16642,  # Vanadium
    16643,  # Cadmium
    16644,  # Platinum
    # R32 Rare
    16646,  # Mercury
    16647,  # Caesium
    16648,  # Hafnium
    16649,  # Technetium
    # R64 Exceptional
    16650,  # Dysprosium
    16651,  # Neodymium
    16652,  # Promethium
    16653,  # Thulium
]

# ── Anomaly ores (found in ore anomalies) ─────────────────────────────────
ANOMALY_ORE_IDS = [
    # Kylixium
    81900, 81901, 81902, 81903,
    # Nocxite
    82016, 82017, 82018, 82019,
    # Ueganite
    82205, 82206, 82207, 82208,
    # Hezorime
    82163, 82164, 82165, 82166,
    # Griemeer
    81975, 81976, 81977, 81978,
]

COMPRESSED_ANOMALY_ORE_IDS = [
    # Compressed Kylixium
    82300, 82301, 82302, 82303,
    # Compressed Nocxite
    82304, 82305, 82306, 82307,
    # Compressed Ueganite
    82308, 82309, 82310, 82311,
    # Compressed Hezorime
    82312, 82313, 82314, 82315,
    # Compressed Griemeer
    82316, 82317, 82318, 82319,
]

# ── A0 rare ores (rare asteroid belt / anomaly ores) ──────────────────────
A0_RARE_ORE_IDS = [
    # Mordunium — yields Pyerite
    74521, 74522, 74523, 74524,
    # Ytirium — yields Isogen
    74525, 74526, 74527, 74528,
    # Eifyrium — yields Zydrine
    74529, 74530, 74531, 74532,
    # Ducinium — yields Megacyte
    74533, 74534, 74535, 74536,
]

COMPRESSED_A0_RARE_ORE_IDS = [
    # Compressed Mordunium
    75275, 75276, 75277, 75278,
    # Compressed Ytirium
    75279, 75280, 75281, 75282,
    # Compressed Eifyrium
    75283, 75284, 75285, 75286,
    # Compressed Ducinium
    75287, 75288, 75289, 75290,
]

ALL_TYPE_IDS = (
    STD_ORE_IDS + COMPRESSED_STD_ORE_IDS +
    ICE_IDS + COMPRESSED_ICE_IDS +
    MOON_ORE_IDS + COMPRESSED_MOON_ORE_IDS +
    ANOMALY_ORE_IDS + COMPRESSED_ANOMALY_ORE_IDS +
    A0_RARE_ORE_IDS + COMPRESSED_A0_RARE_ORE_IDS +
    MINERAL_IDS + ICE_PRODUCT_IDS + MOON_MATERIAL_IDS
)


# ── ESI fetch (one type_id) ────────────────────────────────────────────────

def fetch_jita_price(type_id):
    """
    Fetch orders for type_id in The Forge, filter to Jita 4-4, and
    return (type_id, best_buy, best_sell, buy_volume, sell_volume).
    Returns Nones on error or no Jita orders found.
    """
    url = f'{ESI_BASE}/markets/{THE_FORGE_REGION}/orders/'
    try:
        resp = requests.get(
            url,
            params={'type_id': type_id, 'order_type': 'all'},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return type_id, None, None, None, None

        jita = [o for o in resp.json() if o['location_id'] == JITA_STATION_ID]
        buys  = [(o['price'], o.get('volume_remain', 0)) for o in jita if     o['is_buy_order']]
        sells = [(o['price'], o.get('volume_remain', 0)) for o in jita if not o['is_buy_order']]

        best_buy   = max(p for p, _ in buys)  if buys  else None
        best_sell  = min(p for p, _ in sells) if sells else None
        buy_vol    = sum(v for _, v in buys)
        sell_vol   = sum(v for _, v in sells)

        return type_id, best_buy, best_sell, buy_vol, sell_vol

    except Exception:
        return type_id, None, None, None, None


# ── Main ───────────────────────────────────────────────────────────────────

CATEGORY_IDS = {
    'standard': STD_ORE_IDS + COMPRESSED_STD_ORE_IDS + MINERAL_IDS,
    'ice':      ICE_IDS + COMPRESSED_ICE_IDS + ICE_PRODUCT_IDS,
    'moon':     MOON_ORE_IDS + COMPRESSED_MOON_ORE_IDS + MOON_MATERIAL_IDS,
    'anomaly':  ANOMALY_ORE_IDS + COMPRESSED_ANOMALY_ORE_IDS + MINERAL_IDS,
    'a0rare':   A0_RARE_ORE_IDS + COMPRESSED_A0_RARE_ORE_IDS + MINERAL_IDS,
    'all':      list(ALL_TYPE_IDS),
}


def main():
    category = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
    if category not in CATEGORY_IDS:
        print(f'Unknown category "{category}". Use: standard | ice | moon | anomaly | a0rare | all')
        sys.exit(1)

    type_ids = CATEGORY_IDS[category]
    total   = len(type_ids)
    ts      = datetime.now(timezone.utc).isoformat()
    results = []
    errors  = []

    print(f'Fetching Jita 4-4 prices — category: {category} ({total} type IDs, '
          f'{MAX_WORKERS} workers)...')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(fetch_jita_price, tid): tid for tid in type_ids}
        done = 0
        for future in as_completed(futures):
            tid, bb, bs, bv, sv = future.result()
            done += 1
            # Always insert a row, even with NULL prices.  This stamps the current
            # fetch timestamp on every type_id so that stale prices from previous
            # runs are never served up for items that have no orders right now.
            if bb is not None or bs is not None:
                spread = ((bs - bb) / bb * 100) if (bb and bs and bb > 0) else None
            else:
                spread = None
                errors.append(tid)
            results.append((ts, tid, bb, bs, spread, bv or 0, sv or 0))
            print(f'\r  {done}/{total} fetched — {done - len(errors)} priced, '
                  f'{len(errors)} no orders', end='', flush=True)

    print(f'\n\nInserting {len(results)} records into market_price_snapshots...')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c    = conn.cursor()
    c.executemany(
        '''INSERT INTO market_price_snapshots
           (timestamp, type_id, best_buy, best_sell, spread_pct, buy_volume, sell_volume)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        results,
    )
    conn.commit()
    conn.close()

    print(f'Done. {len(results)} prices stored, {len(errors)} items had no Jita orders.')
    if errors:
        print(f'  No-order type IDs: {errors}')


if __name__ == '__main__':
    main()
