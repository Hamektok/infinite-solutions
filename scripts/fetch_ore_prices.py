"""
fetch_ore_prices.py
-------------------
Fetch Jita 4-4 best-buy / best-sell prices for all raw mined materials
(standard ores, ice, moon ores) and their refined products (minerals,
ice products, moon materials) using parallel ESI requests.

Stores results in market_price_snapshots.  Run on-demand from the
Ore Import Analysis tab in admin_dashboard.py.

Typical runtime: 10-20 seconds with 20 worker threads.
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
MAX_WORKERS        = 20
REQUEST_TIMEOUT    = 12  # seconds per call

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

ALL_TYPE_IDS = (
    STD_ORE_IDS + ICE_IDS + MOON_ORE_IDS +
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

def main():
    total   = len(ALL_TYPE_IDS)
    ts      = datetime.now(timezone.utc).isoformat()
    results = []
    errors  = []

    print(f'Fetching Jita 4-4 prices for {total} type IDs '
          f'({MAX_WORKERS} parallel workers)...')
    print(f'  Ores: {len(STD_ORE_IDS)} std + {len(ICE_IDS)} ice + '
          f'{len(MOON_ORE_IDS)} moon')
    print(f'  Products: {len(MINERAL_IDS)} minerals + '
          f'{len(ICE_PRODUCT_IDS)} ice + {len(MOON_MATERIAL_IDS)} moon mats')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futures = {exe.submit(fetch_jita_price, tid): tid for tid in ALL_TYPE_IDS}
        done = 0
        for future in as_completed(futures):
            tid, bb, bs, bv, sv = future.result()
            done += 1
            if bb is not None or bs is not None:
                spread = ((bs - bb) / bb * 100) if (bb and bs and bb > 0) else None
                results.append((ts, tid, bb, bs, spread, bv or 0, sv or 0))
            else:
                errors.append(tid)
            print(f'\r  {done}/{total} fetched — {len(results)} priced, '
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
