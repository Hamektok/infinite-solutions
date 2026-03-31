"""
generate_sig_store_data.py

Reads Chapter Store items + current FW inventory from the database and embeds
SIG_STORE_DATA as a JS constant into sig_store.html.

Run any time after inventory is updated:
  python generate_sig_store_data.py
"""
import os, sqlite3, re
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
OUT_PATH    = os.path.join(PROJECT_DIR, 'sig_store.html')

# EVE group_id → display group label within Ammunition & Charges sub-tab
AMMO_GROUP_LABELS = {
    376: 'Projectile Ammo',   # Projectile Ammo (S/M/L/XL)
    85:  'Projectile Ammo',
    377: 'Hybrid Charges',    # Hybrid Charges
    83:  'Hybrid Charges',
    384: 'Missiles',          # Light Missiles
    385: 'Missiles',          # Heavy Missiles
    386: 'Missiles',          # Heavy Assault Missiles
    387: 'Missiles',          # Torpedoes
    648: 'Missiles',          # Rockets
    82:  'Laser Charges',     # Frequency Crystals
    916: 'Misc',              # Nanite Repair Paste
}

# Ordered group labels within a sub-tab (defines divider order)
AMMO_GROUP_ORDER = [
    'Projectile Ammo',
    'Missiles',
    'Hybrid Charges',
    'Laser Charges',
    'Misc',
]


def _js_str(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    if not os.path.exists(OUT_PATH):
        print(f'[ERROR] {OUT_PATH} not found — create sig_store.html first')
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Site config ───────────────────────────────────────────────────────────
    cfg_rows = c.execute('SELECT key, value FROM site_config').fetchall()
    cfg = {r[0]: r[1] for r in cfg_rows}

    cof_visible = cfg.get('sig_cof_visible', '1') == '1'
    rbd_visible = cfg.get('sig_rbd_visible', '0') == '1'
    ammo_visible = cfg.get('sig_fw_sub_ammo_charges', '1') == '1'

    # ── FW tracked items + inventory ─────────────────────────────────────────
    c.execute('''
        SELECT t.type_id, t.type_name, t.price_percentage,
               COALESCE(i.quantity, 0),
               COALESCE(it.group_id, 0)
        FROM tracked_market_items t
        LEFT JOIN fw_current_inventory i ON i.type_id = t.type_id
        LEFT JOIN inv_types it ON it.type_id = t.type_id
        WHERE t.site = 'fw'
        ORDER BY t.display_order, t.type_name
    ''')
    rows = c.fetchall()

    # ── Item flags ────────────────────────────────────────────────────────────
    flag_rows = c.execute(
        'SELECT type_id, flag_key FROM item_flags'
    ).fetchall()
    flags_by_type = {}
    for type_id, flag_key in flag_rows:
        flags_by_type.setdefault(type_id, []).append(flag_key)

    snap_ts = c.execute(
        'SELECT MAX(snapshot_timestamp) FROM fw_current_inventory'
    ).fetchone()[0] or ''
    conn.close()

    # Timestamp string
    try:
        ts_str = datetime.fromisoformat(snap_ts).strftime('%d %b %Y  %H:%M EVE')
    except Exception:
        ts_str = datetime.now(timezone.utc).strftime('%d %b %Y  %H:%M UTC')

    # ── Bucket items into ammo groups ─────────────────────────────────────────
    buckets = {g: [] for g in AMMO_GROUP_ORDER}
    for type_id, name, pct, qty, group_id in rows:
        group_label = AMMO_GROUP_LABELS.get(group_id, 'Misc')
        if group_label not in buckets:
            buckets[group_label] = []
        item_flags = flags_by_type.get(type_id, [])
        buckets[group_label].append({
            'name': name, 'qty': qty, 'pricePct': pct,
            'typeId': type_id, 'flags': item_flags
        })

    # ── Build groups JS array ─────────────────────────────────────────────────
    def js_item(it):
        flags_js = '[' + ','.join(f'"{f}"' for f in it['flags']) + ']'
        return (f'{{name:{_js_str(it["name"])},qty:{it["qty"]},'
                f'pricePct:{it["pricePct"]},typeId:{it["typeId"]},'
                f'flags:{flags_js}}}')

    groups_parts = []
    for label in AMMO_GROUP_ORDER:
        items = buckets.get(label, [])
        if not items:
            continue
        items_js = ', '.join(js_item(it) for it in items)
        groups_parts.append(
            f'          {{label:{_js_str(label)}, items:[{items_js}]}}'
        )

    groups_js = '[\n' + ',\n'.join(groups_parts) + '\n        ]' if groups_parts else '[]'

    total_items = sum(len(v) for v in buckets.values())

    js_block = f'''const SIG_STORE_DATA = {{
  snapshotTime: {_js_str(ts_str)},
  chapters: {{
    cof: {{
      label: "Crucible of the Faithful",
      visible: {"true" if cof_visible else "false"},
      subtabs: {{
        ammo_charges: {{
          label: "Ammunition & Charges",
          visible: {"true" if ammo_visible else "false"},
          groups: {groups_js}
        }}
      }}
    }},
    rbd: {{
      label: "Rockbound Disciples",
      visible: {"true" if rbd_visible else "false"},
      subtabs: {{}}
    }}
  }}
}};
// {total_items} items in Crucible of the Faithful'''

    # ── Inject into sig_store.html ────────────────────────────────────────────
    with open(OUT_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    marker_start = '<!-- SIG_STORE_DATA_START -->'
    marker_end   = '<!-- SIG_STORE_DATA_END -->'

    if marker_start not in html or marker_end not in html:
        print(f'[ERROR] Markers not found in {OUT_PATH}')
        return

    new_block = f'{marker_start}\n<script>\n{js_block}\n</script>\n{marker_end}'
    html = re.sub(
        re.escape(marker_start) + r'.*?' + re.escape(marker_end),
        new_block, html, flags=re.DOTALL
    )

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'[OK] Embedded SIG_STORE_DATA into {OUT_PATH}')
    print(f'     {total_items} items  |  CoF visible: {cof_visible}  |  RBD visible: {rbd_visible}')
    print(f'     snapshot: {ts_str}')


if __name__ == '__main__':
    main()
