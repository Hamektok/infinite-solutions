"""
Patch: Phase 2 — Add Minerals, Ice Products, Moon Materials to Import Analysis tab.

Changes:
1. Extend SQL WHERE clause to include the 3 new categories.
2. Extend cat_map with display labels for new categories.
3. Add PRODUCT_CATS branch in the per-row loop (before ore refine-yield block)
   so minerals/ice products/moon materials use hub_imp_basis/pct sell value instead.
4. Extend category filter combobox with new options.
"""
import sys, os

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'admin_dashboard.py')

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1: SQL WHERE clause + comment
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = """\
        # Phase 1: ore/ice/moon ore items only
        cursor.execute(\"\"\"
            WITH latest AS (
                SELECT station_id, type_id, best_buy, best_sell,
                       ROW_NUMBER() OVER (
                           PARTITION BY station_id, type_id
                           ORDER BY fetched_at DESC) AS rn
                FROM market_snapshots
            )
            SELECT tmi.type_id, it.type_name, tmi.category, it.volume,
                   tmi.display_order,
                   j.best_buy, j.best_sell,
                   a.best_sell,
                   d.best_sell,
                   r.best_sell,
                   h.best_sell
            FROM tracked_market_items tmi
            JOIN inv_types it ON tmi.type_id = it.type_id
            LEFT JOIN latest j ON j.type_id=tmi.type_id AND j.station_id=60003760 AND j.rn=1
            LEFT JOIN latest a ON a.type_id=tmi.type_id AND a.station_id=60008494 AND a.rn=1
            LEFT JOIN latest d ON d.type_id=tmi.type_id AND d.station_id=60011866 AND d.rn=1
            LEFT JOIN latest r ON r.type_id=tmi.type_id AND r.station_id=60004588 AND r.rn=1
            LEFT JOIN latest h ON h.type_id=tmi.type_id AND h.station_id=60005686 AND h.rn=1
            WHERE tmi.category IN ('standard_ore', 'ice_ore', 'moon_ore')
            ORDER BY tmi.category, tmi.display_order, it.type_name
        \"\"\")"""

NEW1 = """\
        # Ore + finished products (minerals, ice products, moon materials)
        cursor.execute(\"\"\"
            WITH latest AS (
                SELECT station_id, type_id, best_buy, best_sell,
                       ROW_NUMBER() OVER (
                           PARTITION BY station_id, type_id
                           ORDER BY fetched_at DESC) AS rn
                FROM market_snapshots
            )
            SELECT tmi.type_id, it.type_name, tmi.category, it.volume,
                   tmi.display_order,
                   j.best_buy, j.best_sell,
                   a.best_sell,
                   d.best_sell,
                   r.best_sell,
                   h.best_sell
            FROM tracked_market_items tmi
            JOIN inv_types it ON tmi.type_id = it.type_id
            LEFT JOIN latest j ON j.type_id=tmi.type_id AND j.station_id=60003760 AND j.rn=1
            LEFT JOIN latest a ON a.type_id=tmi.type_id AND a.station_id=60008494 AND a.rn=1
            LEFT JOIN latest d ON d.type_id=tmi.type_id AND d.station_id=60011866 AND d.rn=1
            LEFT JOIN latest r ON r.type_id=tmi.type_id AND r.station_id=60004588 AND r.rn=1
            LEFT JOIN latest h ON h.type_id=tmi.type_id AND h.station_id=60005686 AND h.rn=1
            WHERE tmi.category IN (
                'standard_ore', 'ice_ore', 'moon_ore',
                'minerals', 'ice_products', 'moon_materials'
            )
            ORDER BY tmi.category, tmi.display_order, it.type_name
        \"\"\")"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2: cat_map — add new category labels
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = """\
        cat_map = {
            'standard_ore': 'Standard Ore',
            'ice_ore':      'Ice Ore',
            'moon_ore':     'Moon Ore',
        }"""

NEW2 = """\
        cat_map = {
            'standard_ore':   'Standard Ore',
            'ice_ore':        'Ice Ore',
            'moon_ore':       'Moon Ore',
            'minerals':       'Minerals',
            'ice_products':   'Ice Products',
            'moon_materials': 'Moon Materials',
        }
        PRODUCT_CATS = {'minerals', 'ice_products', 'moon_materials'}"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3: Replace the ore-refine-yield block with a branched version.
# For PRODUCT_CATS: use hub_imp_basis/pct sell price.
# For ore: existing refine-yield logic unchanged.
# ─────────────────────────────────────────────────────────────────────────────
OLD3 = """\
            # Refine value: sum of (yield_qty × refine_eff × mineral_jbv × sell_pct)
            ylds    = ore_yields.get(tid, [])
            portion = ore_portion.get(tid, 1) or 1
            ref_val = 0.0
            for mat in ylds:
                mat_id  = mat['materialTypeID']
                mat_jbv = mineral_jbv.get(mat_id)
                if mat_jbv:
                    try:
                        sell_pct = (
                            float(self.ore_product_pct[mat_id].get()) / 100.0
                            if hasattr(self, 'ore_product_pct')
                            and mat_id in self.ore_product_pct
                            else 1.0)
                    except (ValueError, AttributeError):
                        sell_pct = 1.0
                    ref_val += mat['quantity'] * refine_eff * mat_jbv * sell_pct

            if ref_val <= 0:
                # Mineral prices not yet fetched — show as nodata with hub prices
                self._import_all_rows.append({
                    'type_id':    tid,
                    'category':   cat_label,
                    'item':       name,
                    'jita':    jita_price,    'amarr':   amarr_price,
                    'dodixie': dodixie_price, 'rens':    rens_price,
                    'hek':     hek_price,
                    'best_hub':   best_hub.title(),
                    'best_lc':    best_lc,
                    'margin':     None,
                    'dev':        None,
                    'tag':        'nodata',
                    'ref_val':    None,
                    'vol':        volume,
                    'best_fixed': bc.get('fixed'),
                    'best_var':   bc.get('var'),
                    'best_dep':   bc.get('dep'),
                })
                continue

            contract = ref_val / portion  # per-unit refine value

            # Margin: ROI = (contract \u2212 landed) / landed \u00d7 100
            margin = ((contract - best_lc) / best_lc * 100) if best_lc > 0 else 0.0

            # Dev vs N-day avg at best hub
            best_station = HUB_STATION[best_hub]
            best_sell    = row[HUB_SELL_COL[best_hub]]
            avg_at_best  = avg_prices.get((tid, best_station))
            dev_pct      = ((best_sell - avg_at_best) / avg_at_best * 100
                            if best_sell and avg_at_best and avg_at_best > 0 else None)

            # Tag
            if margin >= 5:
                tag = 'profitable'
                profitable_n += 1
            elif margin >= 0:
                tag = 'marginal'
            else:
                tag = 'loss'

            if best_margin is None or margin > best_margin:
                best_margin = margin
            if worst_margin is None or margin < worst_margin:
                worst_margin = margin

            self._import_all_rows.append({
                'type_id':    tid,
                'category':   cat_label,
                'item':       name,
                'jita':    jita_price,    'amarr':   amarr_price,
                'dodixie': dodixie_price, 'rens':    rens_price,
                'hek':     hek_price,
                'best_hub':   best_hub.title(),
                'best_lc':    best_lc,
                'margin':     margin,
                'dev':        dev_pct,
                'tag':        tag,
                'ref_val':    contract,
                'vol':        volume,
                'best_fixed': bc.get('fixed'),
                'best_var':   bc.get('var'),
                'best_dep':   bc.get('dep'),
            })"""

NEW3 = """\
            if category in PRODUCT_CATS:
                # Finished product — sell value = price_basis(tid) \u00d7 sell_pct(tid)
                basis_var = self._hub_sell_basis.get(tid)
                pct_var   = self._hub_sell_pct.get(tid)
                basis_str = (basis_var.get() if basis_var
                             else self._get_config('hub_import_sell_ref', 'JSV'))
                try:
                    pct_val = float(pct_var.get() if pct_var
                                    else self._get_config('hub_import_markup_pct', '115')) / 100.0
                except (ValueError, AttributeError):
                    pct_val = 1.15
                jita_buy_p  = row[5]
                jita_sell_p = row[6]
                if basis_str == 'JBV':
                    base_price = jita_buy_p
                elif basis_str == 'Jita Split':
                    base_price = ((jita_buy_p + jita_sell_p) / 2
                                  if jita_buy_p and jita_sell_p
                                  else (jita_buy_p or jita_sell_p))
                else:  # JSV
                    base_price = jita_sell_p
                if not base_price:
                    self._import_all_rows.append({
                        'type_id':    tid,   'category':   cat_label,
                        'item':       name,
                        'jita':    jita_price,    'amarr':   amarr_price,
                        'dodixie': dodixie_price, 'rens':    rens_price,
                        'hek':     hek_price,
                        'best_hub':   best_hub.title(), 'best_lc': best_lc,
                        'margin':     None,  'dev':   None,  'tag': 'nodata',
                        'ref_val':    None,  'vol':   volume,
                        'best_fixed': bc.get('fixed'), 'best_var': bc.get('var'),
                        'best_dep':   bc.get('dep'),
                    })
                    continue
                contract = base_price * pct_val
            else:
                # Ore — refine value: sum of (yield_qty \u00d7 refine_eff \u00d7 mineral_jbv \u00d7 sell_pct)
                ylds    = ore_yields.get(tid, [])
                portion = ore_portion.get(tid, 1) or 1
                ref_val = 0.0
                for mat in ylds:
                    mat_id  = mat['materialTypeID']
                    mat_jbv = mineral_jbv.get(mat_id)
                    if mat_jbv:
                        try:
                            sell_pct = (
                                float(self.ore_product_pct[mat_id].get()) / 100.0
                                if hasattr(self, 'ore_product_pct')
                                and mat_id in self.ore_product_pct
                                else 1.0)
                        except (ValueError, AttributeError):
                            sell_pct = 1.0
                        ref_val += mat['quantity'] * refine_eff * mat_jbv * sell_pct

                if ref_val <= 0:
                    self._import_all_rows.append({
                        'type_id':    tid,   'category':   cat_label,
                        'item':       name,
                        'jita':    jita_price,    'amarr':   amarr_price,
                        'dodixie': dodixie_price, 'rens':    rens_price,
                        'hek':     hek_price,
                        'best_hub':   best_hub.title(), 'best_lc': best_lc,
                        'margin':     None,  'dev':   None,  'tag': 'nodata',
                        'ref_val':    None,  'vol':   volume,
                        'best_fixed': bc.get('fixed'), 'best_var': bc.get('var'),
                        'best_dep':   bc.get('dep'),
                    })
                    continue
                contract = ref_val / portion  # per-unit refine value

            # Margin: ROI = (contract \u2212 landed) / landed \u00d7 100
            margin = ((contract - best_lc) / best_lc * 100) if best_lc > 0 else 0.0

            # Dev vs N-day avg at best hub
            best_station = HUB_STATION[best_hub]
            best_sell    = row[HUB_SELL_COL[best_hub]]
            avg_at_best  = avg_prices.get((tid, best_station))
            dev_pct      = ((best_sell - avg_at_best) / avg_at_best * 100
                            if best_sell and avg_at_best and avg_at_best > 0 else None)

            # Tag
            if margin >= 5:
                tag = 'profitable'
                profitable_n += 1
            elif margin >= 0:
                tag = 'marginal'
            else:
                tag = 'loss'

            if best_margin is None or margin > best_margin:
                best_margin = margin
            if worst_margin is None or margin < worst_margin:
                worst_margin = margin

            self._import_all_rows.append({
                'type_id':    tid,
                'category':   cat_label,
                'item':       name,
                'jita':    jita_price,    'amarr':   amarr_price,
                'dodixie': dodixie_price, 'rens':    rens_price,
                'hek':     hek_price,
                'best_hub':   best_hub.title(),
                'best_lc':    best_lc,
                'margin':     margin,
                'dev':        dev_pct,
                'tag':        tag,
                'ref_val':    contract,
                'vol':        volume,
                'best_fixed': bc.get('fixed'),
                'best_var':   bc.get('var'),
                'best_dep':   bc.get('dep'),
            })"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 4: Category filter combobox values
# ─────────────────────────────────────────────────────────────────────────────
OLD4 = """\
            values=['All', 'Standard Ore', 'Ice Ore', 'Moon Ore'])"""

NEW4 = """\
            values=['All', 'Standard Ore', 'Ice Ore', 'Moon Ore',
                    'Minerals', 'Ice Products', 'Moon Materials'])"""

# ─────────────────────────────────────────────────────────────────────────────
# Apply
# ─────────────────────────────────────────────────────────────────────────────
def apply(src, old, new, label):
    src_lf = src.replace('\r\n', '\n')
    old_lf = old.replace('\r\n', '\n')
    new_lf = new.replace('\r\n', '\n')
    if old_lf not in src_lf:
        print(f'FAIL [{label}]: anchor not found')
        sys.exit(1)
    count = src_lf.count(old_lf)
    if count > 1:
        print(f'FAIL [{label}]: anchor found {count} times')
        sys.exit(1)
    result = src_lf.replace(old_lf, new_lf, 1)
    if '\r\n' in src:
        result = result.replace('\n', '\r\n')
    print(f'OK   [{label}]')
    return result

src = apply(src, OLD1, NEW1, 'SQL WHERE clause extended')
src = apply(src, OLD2, NEW2, 'cat_map + PRODUCT_CATS')
src = apply(src, OLD3, NEW3, 'product branch in per-row loop')
src = apply(src, OLD4, NEW4, 'category filter combobox')

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print(f'\nPatched: {TARGET}')
