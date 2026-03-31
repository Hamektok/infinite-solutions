"""
pyerite_scrape_report.py
------------------------
Finds modules that are worth more scrapped for minerals than purchased outright,
with a focus on pyerite yield. Uses 55% reprocessing efficiency (null sec max).

Data sources:
  - item_reprocessing_yields       : per-module mineral yields (DB)
  - market_snapshots               : current Jita mineral prices (DB)
  - ESI /markets/10000002/orders/  : live Jita sell orders per type_id (threaded)

Output: pyerite_scrape_report.html
"""

import sqlite3
import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'pyerite_scrape_report.html')

EFFICIENCY = 0.55   # null sec max scrapmetal reprocessing rate

MINERAL_MAP = {
    'tritanium_yield': 34,
    'pyerite_yield':   35,
    'mexallon_yield':  36,
    'isogen_yield':    37,
    'nocxium_yield':   38,
    'zydrine_yield':   39,
    'megacyte_yield':  40,
    'morphite_yield':  11399,
}
MINERAL_NAMES = {34:'Tritanium', 35:'Pyerite', 36:'Mexallon', 37:'Isogen',
                 38:'Nocxium', 39:'Zydrine', 40:'Megacyte', 11399:'Morphite'}

JITA_STATION = 60003760


def fmt(v):
    if v is None: return '—'
    if abs(v) >= 1e9: return f'{v/1e9:,.2f}B'
    if abs(v) >= 1e6: return f'{v/1e6:,.2f}M'
    if abs(v) >= 1e3: return f'{v/1e3:,.2f}K'
    return f'{v:,.2f}'


def get_mineral_prices(conn):
    c = conn.cursor()
    c.execute("""
        SELECT ms.type_id, ms.best_buy
        FROM market_snapshots ms
        INNER JOIN (
            SELECT type_id, MAX(fetched_at) AS max_fa
            FROM market_snapshots
            WHERE station_id = ? AND type_id IN (34,35,36,37,38,39,40,11399)
            GROUP BY type_id
        ) latest ON ms.type_id = latest.type_id AND ms.fetched_at = latest.max_fa
        WHERE ms.station_id = ?
    """, (JITA_STATION, JITA_STATION))
    return {r[0]: r[1] for r in c.fetchall()}


def get_module_yields(conn):
    c = conn.cursor()
    c.execute("""
        SELECT
            iry.type_id,
            iry.type_name,
            iry.tritanium_yield,
            iry.pyerite_yield,
            iry.mexallon_yield,
            iry.isogen_yield,
            iry.nocxium_yield,
            iry.zydrine_yield,
            iry.megacyte_yield,
            iry.morphite_yield,
            iry.portion_size,
            COALESCE(it.volume, 0) AS volume,
            ig.group_name,
            ic.category_name,
            ic.category_id
        FROM item_reprocessing_yields iry
        JOIN inv_types it      ON iry.type_id  = it.type_id
        JOIN inv_groups ig     ON it.group_id  = ig.group_id
        JOIN inv_categories ic ON ig.category_id = ic.category_id
        WHERE iry.pyerite_yield > 0
          AND iry.can_reprocess = 1
          AND ic.category_id NOT IN (25)  -- exclude raw ore/ice/moon (handled separately)
    """)
    cols = [d[0] for d in c.description]
    return [dict(zip(cols, row)) for row in c.fetchall()]


JITA_REGION   = 10000002
ESI_BASE      = 'https://esi.evetech.net/latest'
FETCH_WORKERS = 20   # concurrent ESI requests


def _fetch_cheapest_sell(type_id):
    """Return (type_id, cheapest_sell_price) from live Jita sell orders, or None."""
    url = (f'{ESI_BASE}/markets/{JITA_REGION}/orders/'
           f'?datasource=tranquility&order_type=sell&type_id={type_id}')
    req = urllib.request.Request(url, headers={'User-Agent': 'LX-ZOJ pyerite_scrape_report/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            orders = json.loads(resp.read().decode())
        # Filter to Jita station only, take cheapest sell
        jita_orders = [o['price'] for o in orders
                       if o.get('location_id') == JITA_STATION]
        if jita_orders:
            return type_id, min(jita_orders)
        # Fall back to any sell order in Jita region if no station orders
        if orders:
            return type_id, min(o['price'] for o in orders)
        return type_id, None
    except Exception:
        return type_id, None


def fetch_jita_sell_prices(type_ids):
    """Fetch cheapest Jita sell order price for each type_id, threaded."""
    total  = len(type_ids)
    done   = 0
    prices = {}
    print(f"  Fetching live Jita sell orders for {total:,} modules "
          f"({FETCH_WORKERS} concurrent)...")
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        futures = {ex.submit(_fetch_cheapest_sell, tid): tid for tid in type_ids}
        for fut in as_completed(futures):
            tid, price = fut.result()
            if price:
                prices[tid] = price
            done += 1
            if done % 200 == 0 or done == total:
                print(f"    {done:,} / {total:,} fetched, {len(prices):,} with orders")
    return prices


def analyse(modules, mineral_prices, esi_prices):
    results = []
    yield_cols = list(MINERAL_MAP.keys())

    for m in modules:
        type_id   = m['type_id']
        buy_price = esi_prices.get(type_id)
        if not buy_price or buy_price <= 0:
            continue

        mineral_value = 0.0
        breakdown     = {}
        for col, mid in MINERAL_MAP.items():
            qty = m[col] * EFFICIENCY
            mp  = mineral_prices.get(mid, 0)
            val = qty * mp
            mineral_value  += val
            breakdown[mid]  = {'qty': qty, 'value': val}

        profit = mineral_value - buy_price
        if profit <= 0:
            continue

        margin       = profit / buy_price * 100.0
        pyerite_qty  = breakdown[35]['qty']
        pyerite_val  = breakdown[35]['value']
        pyerite_pct  = (pyerite_val / mineral_value * 100.0) if mineral_value > 0 else 0.0

        results.append({
            'type_id':      type_id,
            'name':         m['type_name'],
            'category':     m['category_name'],
            'group':        m['group_name'],
            'volume':       m['volume'],
            'portion_size': m['portion_size'],
            'buy_price':    buy_price,
            'mineral_value':mineral_value,
            'profit':       profit,
            'margin':       margin,
            'pyerite_qty':  pyerite_qty,
            'pyerite_value':pyerite_val,
            'pyerite_pct':  pyerite_pct,
            'breakdown':    breakdown,
        })

    results.sort(key=lambda r: r['margin'], reverse=True)
    return results


def write_html(results, mineral_prices, total_checked):
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    pye_price  = mineral_prices.get(35, 0)
    total_pye_units = sum(r['pyerite_qty'] for r in results)
    best_margin     = results[0]['margin'] if results else 0

    # Group results by category, preserving margin sort within each group
    from collections import defaultdict
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r['category']].append(r)
    # Order categories by best margin in each group
    cat_order = sorted(by_cat.keys(), key=lambda c: -by_cat[c][0]['margin'])

    rows_html = ''
    rank = 0
    for cat in cat_order:
        cat_results = by_cat[cat]
        rows_html += f"""
        <tr class="cat-header">
          <td colspan="12">{cat} &nbsp;·&nbsp; {len(cat_results)} profitable item{'s' if len(cat_results)!=1 else ''}</td>
        </tr>"""
        for i, r in enumerate(cat_results):
            rank += 1
            margin_class = ('margin-high' if r['margin'] >= 20
                            else 'margin-mid' if r['margin'] >= 5
                            else 'margin-low')
            pye_class = 'pye-high' if r['pyerite_pct'] >= 50 else ''
            alt = ' alt' if i % 2 == 1 else ''

            rows_html += f"""
        <tr class="{alt}">
          <td class="num">{rank}</td>
          <td class="name">{r['name']}</td>
          <td class="grp">{r['group']}</td>
          <td class="num">{r['volume']:,.2f}</td>
          <td class="num">{fmt(r['buy_price'])}</td>
          <td class="num">{fmt(r['mineral_value'])}</td>
          <td class="num pos">{fmt(r['profit'])}</td>
          <td class="num {margin_class}">{r['margin']:.1f}%</td>
          <td class="num">{r['pyerite_qty']:,.0f}</td>
          <td class="num">{fmt(r['pyerite_value'])}</td>
          <td class="num {pye_class}">{r['pyerite_pct']:.1f}%</td>
        </tr>"""

    mineral_row = ''.join(
        f'<td class="num">{MINERAL_NAMES[mid]}: {fmt(mineral_prices.get(mid))} ISK</td>'
        for mid in [34,35,36,37,38,39,40,11399]
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pyerite Scrape Report — LX-ZOJ</title>

<style>
  body      {{ background:#0d1117; color:#c8dff0; font-family:'Segoe UI',sans-serif; margin:0; padding:20px; }}
  h1        {{ color:#e8f4ff; font-size:1.4em; margin-bottom:4px; }}
  .subtitle {{ color:#507090; font-size:.85em; margin-bottom:18px; }}
  .summary  {{ background:#111a25; border:1px solid #1a2a3a; border-radius:6px;
               padding:14px 18px; margin-bottom:18px; display:flex; flex-wrap:wrap; gap:18px; }}
  .stat     {{ display:flex; flex-direction:column; }}
  .stat-val {{ color:#00d9ff; font-size:1.3em; font-weight:bold; }}
  .stat-lbl {{ color:#507090; font-size:.78em; }}
  .mineral-prices {{ background:#0a1828; border:1px solid #1a2a3a; border-radius:4px;
                     padding:8px 14px; margin-bottom:18px; font-size:.8em; color:#507090; }}
  .mineral-prices td {{ padding:0 12px 0 0; }}
  table     {{ width:100%; border-collapse:collapse; font-size:.85em; }}
  th        {{ background:#1a2a3a; color:#00d9ff; padding:8px 10px; text-align:right;
               font-weight:600; border-bottom:2px solid #253a4a; position:sticky; top:0; }}
  th.left   {{ text-align:left; }}
  td        {{ padding:6px 10px; border-bottom:1px solid #0a1828; }}
  td.num    {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.name   {{ color:#e8f4ff; }}
  td.grp    {{ color:#7090a8; font-size:.82em; }}
  tr.alt td {{ background:#080f18; }}
  .pos      {{ color:#44dd88; }}
  .margin-high {{ color:#44dd88; font-weight:bold; }}
  .margin-mid  {{ color:#ffd700; }}
  .margin-low  {{ color:#7090a8; }}
  .pye-high    {{ color:#ff9a00; font-weight:bold; }}
  .note     {{ color:#446677; font-size:.8em; margin-top:14px; }}
  .cat-header td {{ background:#0d2035; color:#00d9ff; font-weight:600;
                    font-size:.8em; letter-spacing:.06em; text-transform:uppercase;
                    padding:10px 10px 6px; border-top:2px solid #1a3a5a; }}
</style>
</head>
<body>
<h1>Pyerite Scrape Arbitrage — LX-ZOJ</h1>
<div class="subtitle">
  Modules where 55% null-sec reprocessing yield &gt; cheapest Jita sell order &nbsp;·&nbsp;
  Generated: {generated}
</div>

<div class="summary">
  <div class="stat"><span class="stat-val">{len(results):,}</span><span class="stat-lbl">Profitable modules</span></div>
  <div class="stat"><span class="stat-val">{total_checked:,}</span><span class="stat-lbl">Modules checked</span></div>
  <div class="stat"><span class="stat-val">{best_margin:.1f}%</span><span class="stat-lbl">Best margin</span></div>
  <div class="stat"><span class="stat-val">{total_pye_units:,.0f}</span><span class="stat-lbl">Total pyerite units (if all bought)</span></div>
  <div class="stat"><span class="stat-val">{fmt(total_pye_units * pye_price)}</span><span class="stat-lbl">Pyerite ISK value (if all bought)</span></div>
</div>

<div class="mineral-prices">
  <b style="color:#7090a8">Jita Mineral Buy Prices:</b>&nbsp;
  <table><tr>{mineral_row}</tr></table>
</div>

<table>
  <thead>
    <tr>
      <th>#</th>
      <th class="left">Item Name</th>
      <th class="left">Group</th>
      <th>Vol m³</th>
      <th>Jita Sell Price</th>
      <th>Mineral Value</th>
      <th>Profit</th>
      <th>Margin %</th>
      <th>Pyerite Units</th>
      <th>Pyerite Value</th>
      <th>Pyerite %</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>

<p class="note">
  Buy prices: live Jita sell orders (cheapest available at time of run).
  Efficiency: {EFFICIENCY*100:.0f}% scrapmetal reprocessing. Mineral prices: Jita best buy from market_snapshots ({generated}).
</p>
</body>
</html>"""

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    print("Pyerite Scrape Arbitrage Report")
    print(f"  Efficiency: {EFFICIENCY*100:.0f}%")

    conn = sqlite3.connect(DB_PATH)

    print("  Loading mineral prices from market_snapshots...")
    mineral_prices = get_mineral_prices(conn)
    print(f"  Mineral prices loaded: {mineral_prices}")

    if 35 not in mineral_prices:
        print("ERROR: Pyerite price not found in market_snapshots. Run a price fetch first.")
        conn.close()
        return

    print("  Loading module yields from item_reprocessing_yields...")
    modules = get_module_yields(conn)
    print(f"  Modules with pyerite yield: {len(modules):,}")
    conn.close()

    type_ids   = [m['type_id'] for m in modules]
    esi_prices = fetch_jita_sell_prices(type_ids)

    print("  Calculating arbitrage...")
    results = analyse(modules, mineral_prices, esi_prices)

    print(f"  Profitable modules: {len(results):,} / {len(modules):,}")
    if results:
        print(f"  Best margin: {results[0]['margin']:.1f}%  ({results[0]['name']})")

    print(f"  Writing report to pyerite_scrape_report.html...")
    write_html(results, mineral_prices, len(modules))
    print("Done!")


if __name__ == '__main__':
    main()
