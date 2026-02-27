"""
Generate buyback_data.js from the database.
Reads tracked_market_items and market_price_snapshots to produce
a JavaScript data file with item rates, quotas, and 7-day avg Jita buy prices.

For ore categories (ore_standard, ore_compressed, ore_ice, ore_compressed_ice,
ore_moon, ore_compressed_moon), the 'avgJitaBuy' is the MINERAL VALUE per unit
at the configured refining efficiency (default 90.63%), not the raw ore market price.
"""
import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'mydatabase.db')
SDE_DIR = os.path.join(os.path.dirname(__file__), 'sde')

# Map DB category names to display names
CATEGORY_DISPLAY = {
    'minerals': 'Minerals',
    'ice_products': 'Ice Products',
    'moon_materials': 'Reaction Materials',
    'pi_materials': 'Planetary Materials',
    'salvaged_materials': 'Salvaged Materials',
    'standard_ore': 'Standard Ore',
    'ice_ore': 'Ice Ore',
    'moon_ore': 'Moon Ore',
}

# Ore categories that use mineral-value pricing instead of Jita ore spot price
ORE_CATEGORIES = {
    'standard_ore', 'ice_ore', 'moon_ore',
}

# Default refining efficiency (90.63% = typical Tatara with max skills/rigs)
DEFAULT_REFINING_EFFICIENCY = 90.63

# Tier mapping for salvaged_materials based on display_order ranges
SALVAGE_TIERS = {
    range(1, 10): 'Common',
    range(10, 22): 'Uncommon',
    range(22, 33): 'Rare',
    range(33, 43): 'Very Rare',
    range(43, 100): 'Rogue Drone',
}

# Map config slug (from display name) to DB category key
# Admin dashboard stores config as: buyback_category_{display_name_slug}
# e.g. "Reaction Materials" -> buyback_category_reaction_materials
CONFIG_TO_DB_CATEGORY = {
    'reaction_materials': 'moon_materials',
    'planetary_materials': 'pi_materials',
}


def load_sde_ore_data(ore_type_ids):
    """
    Load portionSize and refining materials for given ore type IDs from the SDE.
    Returns:
        portion_sizes: {type_id: portion_size}
        type_materials: {type_id: [(material_type_id, quantity), ...]}
    """
    portion_sizes = {}
    type_materials = {}

    # Load portion sizes from types.jsonl
    types_path = os.path.join(SDE_DIR, 'types.jsonl')
    if os.path.exists(types_path):
        with open(types_path, encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                tid = obj.get('_key')
                if tid in ore_type_ids:
                    portion_sizes[tid] = obj.get('portionSize', 1)

    # Load refining output from typeMaterials.jsonl
    mats_path = os.path.join(SDE_DIR, 'typeMaterials.jsonl')
    if os.path.exists(mats_path):
        with open(mats_path, encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                tid = obj.get('_key')
                if tid in ore_type_ids:
                    materials = obj.get('materials', [])
                    type_materials[tid] = [
                        (m['materialTypeID'], m['quantity'])
                        for m in materials
                    ]

    return portion_sizes, type_materials


def compute_ore_mineral_values(ore_type_ids, avg_prices, efficiency_pct):
    """
    For each ore type_id, compute the mineral value per unit of ore.
    mineral_value_per_unit = sum(mat_qty * efficiency * mat_price) / portion_size

    Returns: {type_id: mineral_value_per_unit}
    """
    efficiency = efficiency_pct / 100.0
    portion_sizes, type_materials = load_sde_ore_data(ore_type_ids)

    ore_values = {}
    for type_id in ore_type_ids:
        mats = type_materials.get(type_id)
        if not mats:
            ore_values[type_id] = 0
            continue

        portion = portion_sizes.get(type_id, 1)
        total_value = 0.0
        for mat_type_id, qty in mats:
            mat_price = avg_prices.get(mat_type_id, 0)
            total_value += qty * efficiency * mat_price

        ore_values[type_id] = round(total_value / portion, 4) if portion > 0 else 0

    return ore_values


def get_buyback_data():
    """Query the database and build the buyback data structure."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get refining efficiency from site_config
    cursor.execute("SELECT value FROM site_config WHERE key = 'buyback_ore_refining_efficiency'")
    row = cursor.fetchone()
    refining_efficiency = float(row[0]) if row else DEFAULT_REFINING_EFFICIENCY

    # Get all tracked items with buyback info
    cursor.execute("""
        SELECT type_id, type_name, category, display_order,
               price_percentage, buyback_accepted, buyback_rate, buyback_quota
        FROM tracked_market_items
        ORDER BY category, display_order
    """)
    items = cursor.fetchall()

    # Get 7-day average Jita buy prices from snapshots
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cursor.execute("""
        SELECT type_id, AVG(best_buy) as avg_buy
        FROM market_price_snapshots
        WHERE timestamp >= ?
        GROUP BY type_id
    """, (seven_days_ago,))
    avg_prices = {row[0]: round(row[1], 2) for row in cursor.fetchall() if row[1] is not None}

    # Get category visibility from site_config
    cursor.execute("""
        SELECT key, value FROM site_config
        WHERE key LIKE 'buyback_category_%'
          AND key NOT LIKE '%_visible'
          AND key NOT LIKE 'buyback_category_%_pricing%'
    """)
    category_visibility = {}
    for key, value in cursor.fetchall():
        slug = key.replace('buyback_category_', '')
        db_cat = CONFIG_TO_DB_CATEGORY.get(slug, slug)
        category_visibility[db_cat] = value == '1'

    # Get pricing method per category
    cursor.execute("""
        SELECT key, value FROM site_config
        WHERE key LIKE 'buyback_pricing_%'
    """)
    category_pricing = {}
    for key, value in cursor.fetchall():
        slug = key.replace('buyback_pricing_', '')
        db_cat = CONFIG_TO_DB_CATEGORY.get(slug, slug)
        category_pricing[db_cat] = value

    conn.close()

    # Identify all ore type_ids that need mineral-value calculation
    ore_type_ids = set(
        row[0] for row in items if row[2] in ORE_CATEGORIES
    )
    ore_mineral_values = compute_ore_mineral_values(ore_type_ids, avg_prices, refining_efficiency)

    # Build output data
    buyback_items = []
    for type_id, type_name, category, display_order, price_pct, accepted, rate, quota in items:
        # Use buyback_rate if set, otherwise fall back to price_percentage
        effective_rate = rate if rate is not None else price_pct

        # For ore categories: use mineral value per unit (at refining efficiency)
        # For everything else: use Jita buy spot price
        if category in ORE_CATEGORIES:
            price = ore_mineral_values.get(type_id, 0)
        else:
            price = avg_prices.get(type_id, 0)

        item = {
            'typeId': type_id,
            'name': type_name,
            'category': category,
            'displayCategory': CATEGORY_DISPLAY.get(category, category),
            'rate': effective_rate,
            'sellRate': price_pct,
            'accepted': bool(accepted),
            'quota': quota or 0,
            'avgJitaBuy': price,
        }

        # Add tier for salvaged materials
        if category == 'salvaged_materials' and display_order is not None:
            for order_range, tier_name in SALVAGE_TIERS.items():
                if display_order in order_range:
                    item['tier'] = tier_name
                    break

        buyback_items.append(item)

    # Build category config
    categories = {}
    for cat_key, display_name in CATEGORY_DISPLAY.items():
        visible = category_visibility.get(cat_key, True)
        categories[cat_key] = {
            'displayName': display_name,
            'visible': visible,
            'pricingMethod': category_pricing.get(cat_key, 'Jita Buy'),
        }

    return {
        'items': buyback_items,
        'categories': categories,
        'refiningEfficiency': refining_efficiency,
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    }


def main():
    print("Generating buyback data from database...")
    data = get_buyback_data()

    # Count stats
    total = len(data['items'])
    accepted = sum(1 for i in data['items'] if i['accepted'])
    with_prices = sum(1 for i in data['items'] if i['avgJitaBuy'] > 0)

    print(f"  Items: {total} total, {accepted} accepting, {with_prices} with price data")
    print(f"  Refining efficiency: {data['refiningEfficiency']}%")

    # Write to buyback_data.js
    output_path = os.path.join(os.path.dirname(__file__), 'buyback_data.js')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('// Auto-generated buyback program data\n')
        f.write(f'// Generated: {data["generated"]}\n')
        f.write('const BUYBACK_DATA = ')
        f.write(json.dumps(data, indent=2))
        f.write(';\n')

    print(f"  Written to: buyback_data.js")
    print("Done!")


if __name__ == '__main__':
    main()
