"""
Split compressed ore inventory across loads by refined mineral value.
Usage:
  python split_loads.py [N]            split into N equal loads (default 6)
  python split_loads.py [N] --no-split keep stacks whole, N equal loads
  python split_loads.py --cap [MAX_B]  fill loads up to MAX_B billion ISK (default 1)

Uses type_materials table for per-batch yields, 90.63% efficiency, 100% Jita sell prices.
"""
import sqlite3, json, math, heapq, os, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mydatabase.db')

NO_SPLIT  = '--no-split' in sys.argv
CAP_MODE  = '--cap' in sys.argv
if CAP_MODE:
    cap_idx = sys.argv.index('--cap')
    _cap_arg = sys.argv[cap_idx + 1] if cap_idx + 1 < len(sys.argv) and sys.argv[cap_idx + 1][0].isdigit() else '1'
    CAP_VAL  = float(_cap_arg) * 1_000_000_000
    N_LOADS  = None
else:
    CAP_VAL  = None
    N_LOADS  = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1][0].isdigit() else 6

# Inventory: name -> quantity
INVENTORY = {
    'Atmospheric Gases':                    940,
    'Compressed Bistot':                   5628,
    'Compressed Bitumens':                 2512,
    'Compressed Blue Ice':                 1000,
    'Compressed Bountiful Monazite':      72479,
    'Compressed Brimful Bitumens':       153397,
    'Compressed Brimful Sylvite':          6715,
    'Compressed Brimful Zeolites':       330389,
    'Compressed Clear Icicle':             2475,
    'Compressed Coesite':                 64169,
    'Compressed Crokite III-Grade':       20927,
    'Compressed Crokite IV-Grade':        15492,
    'Compressed Dark Ochre':              21160,
    'Compressed Dark Ochre III-Grade':    11331,
    'Compressed Dark Ochre IV-Grade':       792,
    'Compressed Ducinium':                 1831,
    'Compressed Eifyrium':                 1532,
    'Compressed Glacial Mass':              817,
    'Compressed Glistening Bitumens':      5545,
    'Compressed Glistening Coesite':      42076,
    'Compressed Gneiss IV-Grade':            20,
    'Compressed Griemeer III-Grade':         39,
    'Compressed Hedbergite II-Grade':     10066,
    'Compressed Hedbergite III-Grade':    16226,
    'Compressed Hemorphite':               4855,
    'Compressed Hemorphite II-Grade':      2944,
    'Compressed Hemorphite III-Grade':      744,
    'Compressed Jaspet III-Grade':        21665,
    'Compressed Kernite':                495510,
    'Compressed Kernite II-Grade':       220856,
    'Compressed Kernite III-Grade':      299873,
    'Compressed Kernite IV-Grade':           92,
    'Compressed Kylixium III-Grade':      74310,
    'Compressed Loparite':                  677,
    'Compressed Omber':                  118017,
    'Compressed Omber II-Grade':         439669,
    'Compressed Omber III-Grade':         38084,
    'Compressed Omber IV-Grade':         289427,
    'Compressed Plagioclase':           3031572,
    'Compressed Plagioclase II-Grade':  3362215,
    'Compressed Plagioclase III-Grade':  631864,
    'Compressed Pyroxeres II-Grade':     298665,
    'Compressed Pyroxeres III-Grade':    229587,
    'Compressed Scordite':             2326744,
    'Compressed Scordite II-Grade':   15921946,
    'Compressed Scordite III-Grade':     187642,
    'Compressed Scordite IV-Grade':    4670418,
    'Compressed Sylvite':               326804,
    'Compressed Twinkling Scheelite':        57,
    'Compressed Vanadinite':                166,
    'Compressed Veldspar':            36931599,
    'Compressed Veldspar II-Grade':  104167748,
    'Compressed Veldspar III-Grade':  40320312,
    'Compressed Ytirium':               169580,
    'Compressed Zeolites':               92897,
}

EFFICIENCY = 0.9063
MOON_PRICE_OVERRIDES = {
    16633: 582.80,
    16634: 269.90,
    16635: 237.00,
    16636: 359.90,
}

def get_portion_size(name):
    ice_keywords = ('Icicle', 'Ice', 'Glacial', 'Gelidus', 'Krystallos',
                    'Gneiss', 'Dark Ochre', 'Crokite', 'Bistot', 'Arkonor',
                    'Spodumain', 'Hemorphite', 'Hedbergite')
    # Only compressed ice ores (not compressed rock ores) have portionSize=1
    # Ice types: Blue Ice, Clear Icicle, Glacial Mass, Glare Crust, Dark Glitter,
    #            Gelidus, Krystallos, White Glaze
    ice_ore_bases = ('Blue Ice', 'Clear Icicle', 'Glacial Mass', 'Glare Crust',
                     'Dark Glitter', 'Gelidus', 'Krystallos', 'White Glaze')
    for base in ice_ore_bases:
        if base in name:
            return 1
    return 100

conn = sqlite3.connect(DB_PATH)

price_rows = conn.execute("""
    SELECT type_id, best_sell
    FROM market_snapshots
    WHERE station_id = 60003760
      AND best_sell > 0
    GROUP BY type_id
    HAVING fetched_at = MAX(fetched_at)
""").fetchall()
jita_sell = {r[0]: r[1] for r in price_rows}
jita_sell.update(MOON_PRICE_OVERRIDES)

name_to_id = {}
for tid, tname in conn.execute("SELECT type_id, type_name FROM tracked_market_items").fetchall():
    name_to_id[tname] = tid
for tid, tname in conn.execute("SELECT type_id, type_name FROM inv_types").fetchall():
    if tname not in name_to_id:
        name_to_id[tname] = tid

id_to_materials = {}
for tid, mats_json in conn.execute("SELECT type_id, materials_json FROM type_materials").fetchall():
    try:
        mats_list = json.loads(mats_json)
        id_to_materials[tid] = {str(m['materialTypeID']): m['quantity'] for m in mats_list}
    except Exception:
        pass
conn.close()

def refined_value_per_unit(name):
    tid = name_to_id.get(name)
    if not tid:
        return 0.0
    mats = id_to_materials.get(tid)
    if not mats:
        return 0.0
    portion = get_portion_size(name)
    total = 0.0
    for mat_id_str, mat_qty in mats.items():
        price = jita_sell.get(int(mat_id_str), 0.0)
        total += (mat_qty / portion) * EFFICIENCY * price
    return total

items = []
for name, qty in INVENTORY.items():
    portion = get_portion_size(name)
    n_batches = qty // portion
    val_per_unit = refined_value_per_unit(name)
    val_per_batch = val_per_unit * portion
    total_val = n_batches * val_per_batch
    items.append({
        'name': name,
        'qty': qty,
        'portion': portion,
        'n_batches': n_batches,
        'remainder': qty % portion,
        'val_per_unit': val_per_unit,
        'val_per_batch': val_per_batch,
        'total_val': total_val,
    })

items.sort(key=lambda x: -x['total_val'])

grand_total = sum(i['total_val'] for i in items)

# ── Packing ───────────────────────────────────────────────────────────────────
if CAP_MODE:
    # Fill loads up to CAP_VAL; keep stacks whole.
    # Items larger than CAP_VAL are force-split (unavoidable).
    loads = []

    def new_load():
        l = [0.0, len(loads), []]
        loads.append(l)
        return l

    for item in items:
        if item['n_batches'] == 0:
            continue
        item_val = item['total_val']
        item_qty = item['n_batches'] * item['portion']

        if item_val <= CAP_VAL:
            # Keep whole — first-fit into an existing load
            placed = False
            for load in loads:
                if load[0] + item_val <= CAP_VAL:
                    load[0] += item_val
                    load[2].append((item['name'], item_qty))
                    placed = True
                    break
            if not placed:
                load = new_load()
                load[0] += item_val
                load[2].append((item['name'], item_qty))
        else:
            # Force-split: item exceeds cap
            remaining = item['n_batches']
            while remaining > 0:
                load = new_load()
                if item['val_per_batch'] > 0:
                    batches = min(remaining, int(CAP_VAL / item['val_per_batch']))
                    batches = max(batches, 1)
                else:
                    batches = remaining
                load[0] += batches * item['val_per_batch']
                load[2].append((item['name'], batches * item['portion']))
                remaining -= batches

    heap = loads
    target = CAP_VAL

else:
    target = grand_total / N_LOADS
    heap = [[0.0, i, []] for i in range(N_LOADS)]
    heapq.heapify(heap)

    if NO_SPLIT:
        for item in items:
            if item['n_batches'] == 0:
                continue
            load = heapq.heappop(heap)
            load[0] += item['total_val']
            load[2].append((item['name'], item['n_batches'] * item['portion']))
            heapq.heappush(heap, load)
    else:
        for item in items:
            remaining = item['n_batches']
            while remaining > 0:
                load = heapq.heappop(heap)
                space_val = target - load[0]
                if item['val_per_batch'] > 0:
                    can_fit = int(space_val / item['val_per_batch'])
                else:
                    can_fit = remaining
                batches = min(remaining, max(can_fit, 1))
                qty = batches * item['portion']
                val = batches * item['val_per_batch']
                load[0] += val
                load[2].append((item['name'], qty))
                remaining -= batches
                heapq.heappush(heap, load)

    heap.sort(key=lambda x: x[1])

n_loads_actual = len(heap)

# ── Output ────────────────────────────────────────────────────────────────────
SEP  = "=" * 52
SEP2 = "-" * 52

print(SEP)
print(f"  TOTAL   {grand_total/1e6:>10.2f} M ISK")
print(f"  LOADS   {n_loads_actual:>10}")
if CAP_MODE:
    print(f"  CAP     {CAP_VAL/1e6:>10.2f} M ISK each")
else:
    print(f"  TARGET  {target/1e6:>10.2f} M ISK each")
print(SEP)

vals = []
for load_val, load_idx, contents in heap:
    vals.append(load_val)
    print()
    print(SEP)
    print(f"  LOAD {load_idx+1}  —  {load_val/1e6:.2f} M ISK")
    print(SEP2)
    consolidated = {}
    for name, qty in contents:
        consolidated[name] = consolidated.get(name, 0) + qty
    for name, qty in consolidated.items():
        if qty > 0:
            short = name.replace('Compressed ', '')
            print(f"  {short:<34}  {qty:>12,}")
    print(SEP)

print()
if CAP_MODE:
    print(f"  Max load: {max(vals)/1e6:.2f} M ISK")
else:
    print(f"  Spread: {(max(vals)-min(vals))/1e6:.2f} M ISK  ({(max(vals)-min(vals))/target*100:.2f}%)")
