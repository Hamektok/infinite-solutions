"""
Split compressed ore inventory across N loads by refined mineral value.
Usage: python split_loads.py [N]   (default N=6)

Uses type_materials table for per-batch yields, 90.63% efficiency, 100% Jita sell prices.
"""
import sqlite3, json, math, heapq, os, sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mydatabase.db')

N_LOADS = int(sys.argv[1]) if len(sys.argv) > 1 else 6

# Inventory: name -> quantity
INVENTORY = {
    'Compressed Veldspar':             34721548,
    'Compressed Veldspar II-Grade':    93068812,
    'Compressed Veldspar III-Grade':   30256755,
    'Compressed Scordite':              2326744,
    'Compressed Scordite II-Grade':    15559810,
    'Compressed Scordite III-Grade':     187642,
    'Compressed Scordite IV-Grade':     3935946,
    'Compressed Plagioclase':           3031572,
    'Compressed Plagioclase II-Grade':  3362215,
    'Compressed Plagioclase III-Grade':  631864,
    'Compressed Pyroxeres II-Grade':     191115,
    'Compressed Pyroxeres III-Grade':    229587,
    'Compressed Kernite':                461020,
    'Compressed Kernite II-Grade':       200486,
    'Compressed Kernite III-Grade':      286472,
    'Compressed Kernite IV-Grade':           92,
    'Compressed Omber':                  118017,
    'Compressed Omber II-Grade':         439669,
    'Compressed Omber III-Grade':         13791,
    'Compressed Omber IV-Grade':         289427,
    'Compressed Jaspet III-Grade':         2175,
    'Compressed Hedbergite III-Grade':    16226,
    'Compressed Dark Ochre III-Grade':    11331,
    'Compressed Crokite III-Grade':       20927,
    'Compressed Crokite IV-Grade':          857,
    'Compressed Gneiss IV-Grade':            20,
    'Compressed Kylixium III-Grade':      74310,
    'Compressed Griemeer III-Grade':         39,
    'Compressed Loparite':                  677,
    'Compressed Zeolites':                92897,
    'Compressed Brimful Zeolites':        330389,
    'Compressed Coesite':                    70,
    'Compressed Glistening Coesite':      42076,
    'Compressed Sylvite':                326804,
    'Compressed Brimful Sylvite':           6715,
    'Compressed Glistening Bitumens':      5545,
    'Compressed Clear Icicle':             2475,
    'Compressed Glacial Mass':              817,
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
target = grand_total / N_LOADS

# Greedy bin-packing with min-heap; split items that exceed per-load target
# heap entries: [current_val, load_index, contents_list]
heap = [[0.0, i, []] for i in range(N_LOADS)]
heapq.heapify(heap)

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

print(f"Grand total: {grand_total/1e6:.2f}M ISK  |  {N_LOADS} loads  |  Target: {target/1e6:.2f}M each")
print()

vals = []
for load_val, load_idx, contents in heap:
    vals.append(load_val)
    print(f"Load {load_idx+1}  —  {load_val/1e6:.2f}M ISK")
    # Consolidate duplicate entries for same item
    consolidated = {}
    for name, qty in contents:
        consolidated[name] = consolidated.get(name, 0) + qty
    for name, qty in consolidated.items():
        if qty > 0:
            print(f"  {name:<45}  {qty:>14,}")
    print()

print(f"Spread: {(max(vals)-min(vals))/1e6:.2f}M ISK  ({(max(vals)-min(vals))/target*100:.2f}%)")
