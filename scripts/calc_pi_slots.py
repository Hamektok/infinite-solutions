import sqlite3, requests, time, sys, os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mydatabase.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("""
    SELECT tmi.type_id, tmi.type_name, it.market_group_id,
           ROUND(AVG(mps.best_buy), 0) as avg_buy,
           ROUND(AVG(mps.best_sell), 0) as avg_sell
    FROM tracked_market_items tmi
    JOIN inv_types it ON tmi.type_id = it.type_id
    LEFT JOIN market_price_snapshots mps ON tmi.type_id = mps.type_id
        AND mps.timestamp >= datetime('now', '-7 days')
    WHERE tmi.category = 'pi_materials'
    AND it.market_group_id IN (1334, 1335, 1336, 1337)
    GROUP BY tmi.type_id, tmi.type_name, it.market_group_id
    ORDER BY it.market_group_id, tmi.type_name
""")
items = cursor.fetchall()
conn.close()

FORGE    = 10000002
SCALE    = 0.001   # shop moves 0.1% of Jita volume
COMM     = 0.05    # equivalent to a 5% commission
PREMIUM  = 1.25    # +25% for exclusive rights
cutoff   = (datetime.now(timezone.utc) - timedelta(days=30)).date()
tier_map = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}

print("Fetching Jita 30-day volumes for P1-P4...")
results = []
for type_id, name, grp, buy, sell in items:
    url = f'https://esi.evetech.net/latest/markets/{FORGE}/history/?type_id={type_id}'
    r = requests.get(url, timeout=10)
    monthly_vol = 0
    if r.status_code == 200:
        monthly_vol = sum(d['volume'] for d in r.json() if d['date'] >= str(cutoff))
    tier      = tier_map.get(grp, '??')
    sell_p    = sell or 0
    shop_vol  = monthly_vol * SCALE
    mo_rev    = shop_vol * sell_p
    slot_p    = mo_rev * COMM * PREMIUM
    results.append((tier, name, sell_p, monthly_vol, shop_vol, mo_rev, slot_p))
    time.sleep(0.1)

# ── Print ──────────────────────────────────────────────────────────────────
W = 108
print()
print('=' * W)
print('  PI SLOT PRICING  |  0.1% Jita vol  |  5% commission equiv  |  x1.25 exclusivity premium')
print('=' * W)
print(f"  {'Tier':<4}  {'Item':<38}  {'Sell Price':>10}  {'Jita 30d Vol':>14}  {'Shop Vol/mo':>12}  {'Shop Rev/mo':>13}  {'Slot Price':>10}")
print('-' * W)

tier_totals = {}
cur_tier    = None

for tier, name, sell, jita_vol, shop_vol, mo_rev, slot in results:
    if tier not in tier_totals:
        tier_totals[tier] = 0
    tier_totals[tier] += slot

    if tier != cur_tier:
        if cur_tier is not None:
            count = len([r for r in results if r[0] == cur_tier])
            print(f"  {'':4}  {'':38}  {'':10}  {'':14}  {'':12}  {f'({count} slots)':>13}  {tier_totals[cur_tier]/1e6:>9.1f}M")
            print()
        cur_tier = tier
        print(f"  --- {tier} ---------------------------------")

    slot_str = f"{slot/1e6:.1f}M" if slot >= 1e6 else f"{slot/1e3:.0f}K"
    print(f"  {tier:<4}  {name:<38}  {sell:>10,.0f}  {jita_vol/1e6:>13.1f}M  {shop_vol:>12,.0f}  {mo_rev/1e6:>12.1f}M  {slot_str:>10}")

# last tier subtotal
if cur_tier:
    count = len([r for r in results if r[0] == cur_tier])
    print(f"  {'':4}  {'':38}  {'':10}  {'':14}  {'':12}  {f'({count} slots)':>13}  {tier_totals[cur_tier]/1e6:>9.1f}M")

grand = sum(tier_totals.values())
print()
print('=' * W)
print(f"  {'Tier':<6}  {'Slots':>5}  {'Monthly Total':>15}")
print(f"  {'-'*30}")
for t in ['P1','P2','P3','P4']:
    if t in tier_totals:
        n = len([r for r in results if r[0] == t])
        print(f"  {t:<6}  {n:>5}  {tier_totals[t]/1e6:>14.0f}M")
print(f"  {'-'*30}")
print(f"  {'TOTAL':<6}  {len(results):>5}  {grand/1e6:>14.0f}M ISK/mo  (all slots filled)")
print()
print("  FORMULA:")
print("  Slot Price = Jita 30-day Volume")
print("             x 0.1%  (estimated share of Jita volume your shop moves)")
print("             x Jita Sell Price")
print("             x 5%    (equivalent commission you would otherwise charge)")
print("             x 1.25  (exclusivity premium - they get sole selling rights)")
