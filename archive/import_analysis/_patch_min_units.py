#!/usr/bin/env python3
"""Patch: Add Min Units column + Target % to Import Analysis tab."""
import sys

FILE = r'e:\Python Project\admin_dashboard.py'

with open(FILE, 'r', encoding='utf-8') as f:
    src = f.read()

errors = []

def apply(src, old, new, label):
    if old not in src:
        errors.append(f'NOT FOUND: {label}')
        return src
    count = src.count(old)
    if count > 1:
        errors.append(f'AMBIGUOUS ({count}): {label}')
        return src
    print(f'  OK: {label}')
    return src.replace(old, new)

# ─── 1. Add import math ───────────────────────────────────────────────────────
src = apply(src,
    'import json\nfrom datetime import datetime, timezone',
    'import json\nimport math\nfrom datetime import datetime, timezone',
    'import math')

# ─── 2. Treeview cols tuple ──────────────────────────────────────────────────
src = apply(src,
    "        cols = ('category', 'item',\n"
    "                'jita', 'amarr', 'dodixie', 'rens', 'hek',\n"
    "                'best_hub', 'margin', 'dev')",
    "        cols = ('category', 'item',\n"
    "                'jita', 'amarr', 'dodixie', 'rens', 'hek',\n"
    "                'best_hub', 'margin', 'dev', 'min_units')",
    'cols tuple')

# ─── 3. Column headings list ─────────────────────────────────────────────────
src = apply(src,
    "            ('dev',      'vs 7d Avg %',   90, 'e'),\n"
    "        ]:",
    "            ('dev',      'vs 7d Avg %',   90, 'e'),\n"
    "            ('min_units','Min Units',      90, 'e'),\n"
    "        ]:",
    'column headings')

# ─── 4. Filter row: add Target % field ───────────────────────────────────────
src = apply(src,
    "        show_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())\n"
    "\n"
    "        # ── Treeview",
    "        show_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())\n"
    "        tk.Label(filter_frame, text='Target %',\n"
    "                 background='#0d1117', foreground='#88d0e8',\n"
    "                 font=('Segoe UI', 9)).pack(side='left', padx=(16, 4))\n"
    "        self.hub_target_mg_var = tk.StringVar(\n"
    "            value=self._get_config('hub_import_target_mg', '10'))\n"
    "        self.hub_target_mg_var.trace_add('write', lambda *_: (\n"
    "            self._set_config('hub_import_target_mg',\n"
    "                             self.hub_target_mg_var.get()),\n"
    "            self._filter_import_tree()))\n"
    "        ttk.Entry(filter_frame, textvariable=self.hub_target_mg_var,\n"
    "                  width=5).pack(side='left')\n"
    "\n"
    "        # ── Treeview",
    'Target % filter field')

# ─── 5. Landed cost loop: add landed_comps ───────────────────────────────────
src = apply(src,
    "            # Landed cost per enabled hub\n"
    "            landed = {}\n"
    "            for hub in HUB_NAMES:\n"
    "                cfg = hubs_cfg[hub]\n"
    "                if not cfg['en']:\n"
    "                    continue\n"
    "                raw = hub_raw[hub]\n"
    "                if raw is None:\n"
    "                    continue\n"
    "                buy_price = raw * buy_pct\n"
    "                broker    = buy_price * broker_pct\n"
    "                null_cost = null_ism3 * volume + null_isj * null_j + null_coll * buy_price\n"
    "                if hub == 'jita':\n"
    "                    lc = buy_price + broker + null_cost\n"
    "                else:\n"
    "                    hs_cost = 0.0\n"
    "                    for _n, jkey in ((1, 'j1'), (2, 'j2'), (3, 'j3')):\n"
    "                        leg   = legs_cfg[_n]\n"
    "                        jumps = hubs_cfg[hub][jkey]\n"
    "                        if not leg['en'] or jumps <= 0:\n"
    "                            continue\n"
    "                        hs_cost += (\n"
    "                            leg['ism3'] * volume\n"
    "                            + leg['isj'] * jumps * (volume / leg['dep'])\n"
    "                            + leg['coll'] * buy_price\n"
    "                        )\n"
    "                    lc = buy_price + broker + hs_cost + null_cost\n"
    "                landed[hub] = lc",

    "            # Landed cost per enabled hub\n"
    "            landed       = {}\n"
    "            landed_comps = {}\n"
    "            for hub in HUB_NAMES:\n"
    "                cfg = hubs_cfg[hub]\n"
    "                if not cfg['en']:\n"
    "                    continue\n"
    "                raw = hub_raw[hub]\n"
    "                if raw is None:\n"
    "                    continue\n"
    "                buy_price  = raw * buy_pct\n"
    "                broker     = buy_price * broker_pct\n"
    "                null_fixed = null_isj * null_j\n"
    "                null_var   = null_ism3 * volume + null_coll * buy_price\n"
    "                null_cost  = null_fixed + null_var\n"
    "                if hub == 'jita':\n"
    "                    lc = buy_price + broker + null_cost\n"
    "                    landed_comps[hub] = {\n"
    "                        'fixed': null_fixed,\n"
    "                        'var':   buy_price + broker + null_var,\n"
    "                        'dep':   1e12,\n"
    "                    }\n"
    "                else:\n"
    "                    hs_cost    = 0.0\n"
    "                    hs_fixed_h = 0.0\n"
    "                    hs_var_h   = 0.0\n"
    "                    dep_list   = []\n"
    "                    for _n, jkey in ((1, 'j1'), (2, 'j2'), (3, 'j3')):\n"
    "                        leg   = legs_cfg[_n]\n"
    "                        jumps = hubs_cfg[hub][jkey]\n"
    "                        if not leg['en'] or jumps <= 0:\n"
    "                            continue\n"
    "                        hs_fixed_h += leg['isj'] * jumps\n"
    "                        hs_var_h   += leg['ism3'] * volume + leg['coll'] * buy_price\n"
    "                        dep_list.append(leg['dep'])\n"
    "                        hs_cost    += (\n"
    "                            leg['ism3'] * volume\n"
    "                            + leg['isj'] * jumps * (volume / leg['dep'])\n"
    "                            + leg['coll'] * buy_price\n"
    "                        )\n"
    "                    lc = buy_price + broker + hs_cost + null_cost\n"
    "                    landed_comps[hub] = {\n"
    "                        'fixed': hs_fixed_h + null_fixed,\n"
    "                        'var':   buy_price + broker + hs_var_h + null_var,\n"
    "                        'dep':   min(dep_list) if dep_list else 900000.0,\n"
    "                    }\n"
    "                landed[hub] = lc",
    'landed_comps tracking')

# ─── 6. Extract bc after best_hub selection ──────────────────────────────────
src = apply(src,
    "            best_hub = min(landed, key=lambda h: landed[h])\n"
    "            best_lc  = landed[best_hub]\n"
    "\n"
    "            # Refine value",
    "            best_hub = min(landed, key=lambda h: landed[h])\n"
    "            best_lc  = landed[best_hub]\n"
    "            bc       = landed_comps.get(best_hub, {})\n"
    "\n"
    "            # Refine value",
    'bc extraction after best_hub')

# ─── 7. nodata1 row dict (not landed) ────────────────────────────────────────
src = apply(src,
    "                    'best_hub':   '—',\n"
    "                    'best_lc':    None,\n"
    "                    'margin':     None,\n"
    "                    'dev':        None,\n"
    "                    'tag':        'nodata',\n"
    "                })\n"
    "                continue\n"
    "\n"
    "            best_hub = min(landed",
    "                    'best_hub':   '—',\n"
    "                    'best_lc':    None,\n"
    "                    'margin':     None,\n"
    "                    'dev':        None,\n"
    "                    'tag':        'nodata',\n"
    "                    'ref_val':    None,\n"
    "                    'vol':        volume,\n"
    "                    'best_fixed': None,\n"
    "                    'best_var':   None,\n"
    "                    'best_dep':   None,\n"
    "                })\n"
    "                continue\n"
    "\n"
    "            best_hub = min(landed",
    'nodata1 row dict')

# ─── 8. nodata2 row dict (ref_val <= 0) ──────────────────────────────────────
src = apply(src,
    "                    'best_hub':   best_hub.title(),\n"
    "                    'best_lc':    best_lc,\n"
    "                    'margin':     None,\n"
    "                    'dev':        None,\n"
    "                    'tag':        'nodata',\n"
    "                })\n"
    "                continue\n"
    "\n"
    "            contract = ref_val / portion",
    "                    'best_hub':   best_hub.title(),\n"
    "                    'best_lc':    best_lc,\n"
    "                    'margin':     None,\n"
    "                    'dev':        None,\n"
    "                    'tag':        'nodata',\n"
    "                    'ref_val':    None,\n"
    "                    'vol':        volume,\n"
    "                    'best_fixed': bc.get('fixed'),\n"
    "                    'best_var':   bc.get('var'),\n"
    "                    'best_dep':   bc.get('dep'),\n"
    "                })\n"
    "                continue\n"
    "\n"
    "            contract = ref_val / portion",
    'nodata2 row dict')

# ─── 9. Main row dict ────────────────────────────────────────────────────────
src = apply(src,
    "                'best_hub':   best_hub.title(),\n"
    "                'best_lc':    best_lc,\n"
    "                'margin':     margin,\n"
    "                'dev':        dev_pct,\n"
    "                'tag':        tag,\n"
    "            })",
    "                'best_hub':   best_hub.title(),\n"
    "                'best_lc':    best_lc,\n"
    "                'margin':     margin,\n"
    "                'dev':        dev_pct,\n"
    "                'tag':        tag,\n"
    "                'ref_val':    contract,\n"
    "                'vol':        volume,\n"
    "                'best_fixed': bc.get('fixed'),\n"
    "                'best_var':   bc.get('var'),\n"
    "                'best_dep':   bc.get('dep'),\n"
    "            })",
    'main row dict')

# ─── 10. _filter_import_tree: tgt + sort key + min_units display ─────────────
src = apply(src,
    "    def _filter_import_tree(self):\n"
    "        search     = self.hub_import_search_var.get().lower()\n"
    "        cat_filter = self.import_cat_var.get()\n"
    "        show       = self.import_show_var.get()\n"
    "\n"
    "        show_map = {\n"
    "            'Profitable': {'profitable'},\n"
    "            'Marginal':   {'marginal'},\n"
    "            'Loss':       {'loss'},\n"
    "            'No Data':    {'nodata'},\n"
    "        }\n"
    "        show_tags = show_map.get(show)  # None means show All\n"
    "\n"
    "        filtered = [\n"
    "            r for r in self._import_all_rows\n"
    "            if (not search or search in r['item'].lower())\n"
    "            and (cat_filter == 'All' or r['category'] == cat_filter)\n"
    "            and (show_tags is None or r['tag'] in show_tags)\n"
    "        ]\n"
    "\n"
    "        col     = self._import_sort_col\n"
    "        reverse = not self._import_sort_asc\n"
    "\n"
    "        def _key(r):\n"
    "            v = r.get(col)\n"
    "            if v is None:\n"
    "                return (1e18 if not reverse else -1e18)\n"
    "            if isinstance(v, (int, float)):\n"
    "                return v\n"
    "            return (v or '').lower()\n"
    "\n"
    "        filtered.sort(key=_key, reverse=reverse)\n"
    "\n"
    "        def _isk(v):\n"
    "            return f'{v:,.0f}' if v is not None else '—'\n"
    "\n"
    "        self.import_tree.delete(*self.import_tree.get_children())\n"
    "        for r in filtered:\n"
    "            mg  = r.get('margin')\n"
    "            dev = r.get('dev')\n"
    "            self.import_tree.insert('', 'end', tags=(r['tag'],), values=(\n"
    "                r['category'],\n"
    "                r['item'],\n"
    "                _isk(r.get('jita')),\n"
    "                _isk(r.get('amarr')),\n"
    "                _isk(r.get('dodixie')),\n"
    "                _isk(r.get('rens')),\n"
    "                _isk(r.get('hek')),\n"
    "                r['best_hub'],\n"
    "                f'{mg:+.1f}%' if mg is not None else '—',\n"
    "                f'{dev:+.1f}%' if dev is not None else '—',\n"
    "            ))",

    "    def _filter_import_tree(self):\n"
    "        search     = self.hub_import_search_var.get().lower()\n"
    "        cat_filter = self.import_cat_var.get()\n"
    "        show       = self.import_show_var.get()\n"
    "\n"
    "        try:\n"
    "            tgt = float(self.hub_target_mg_var.get()) / 100\n"
    "        except (ValueError, AttributeError):\n"
    "            tgt = 0.10\n"
    "\n"
    "        show_map = {\n"
    "            'Profitable': {'profitable'},\n"
    "            'Marginal':   {'marginal'},\n"
    "            'Loss':       {'loss'},\n"
    "            'No Data':    {'nodata'},\n"
    "        }\n"
    "        show_tags = show_map.get(show)  # None means show All\n"
    "\n"
    "        filtered = [\n"
    "            r for r in self._import_all_rows\n"
    "            if (not search or search in r['item'].lower())\n"
    "            and (cat_filter == 'All' or r['category'] == cat_filter)\n"
    "            and (show_tags is None or r['tag'] in show_tags)\n"
    "        ]\n"
    "\n"
    "        col     = self._import_sort_col\n"
    "        reverse = not self._import_sort_asc\n"
    "\n"
    "        def _min_n(r):\n"
    "            ref_v  = r.get('ref_val')\n"
    "            bfixed = r.get('best_fixed') or 0\n"
    "            bvar   = r.get('best_var')\n"
    "            if ref_v is None or bvar is None:\n"
    "                return None\n"
    "            if bfixed <= 0:\n"
    "                return 1 if ref_v > bvar * (1 + tgt) else None\n"
    "            denom = ref_v / (1 + tgt) - bvar\n"
    "            if denom <= 0:\n"
    "                return None\n"
    "            return bfixed / denom\n"
    "\n"
    "        def _key(r):\n"
    "            if col == 'min_units':\n"
    "                mn = _min_n(r)\n"
    "                if mn is None:\n"
    "                    return 1e18 if not reverse else -1e18\n"
    "                return mn\n"
    "            v = r.get(col)\n"
    "            if v is None:\n"
    "                return (1e18 if not reverse else -1e18)\n"
    "            if isinstance(v, (int, float)):\n"
    "                return v\n"
    "            return (v or '').lower()\n"
    "\n"
    "        filtered.sort(key=_key, reverse=reverse)\n"
    "\n"
    "        def _isk(v):\n"
    "            return f'{v:,.0f}' if v is not None else '\u2014'\n"
    "\n"
    "        self.import_tree.delete(*self.import_tree.get_children())\n"
    "        for r in filtered:\n"
    "            mg  = r.get('margin')\n"
    "            dev = r.get('dev')\n"
    "            mn  = _min_n(r)\n"
    "            bvol = r.get('vol') or 1\n"
    "            bdep = r.get('best_dep') or 900000\n"
    "            if mn is None:\n"
    "                min_u = '\u2014'\n"
    "            else:\n"
    "                min_n_int = math.ceil(mn)\n"
    "                cap = int(bdep / bvol)\n"
    "                min_u = (f'{min_n_int:,}' if min_n_int <= cap\n"
    "                         else f'\u26a0 >{cap:,}')\n"
    "            self.import_tree.insert('', 'end', tags=(r['tag'],), values=(\n"
    "                r['category'],\n"
    "                r['item'],\n"
    "                _isk(r.get('jita')),\n"
    "                _isk(r.get('amarr')),\n"
    "                _isk(r.get('dodixie')),\n"
    "                _isk(r.get('rens')),\n"
    "                _isk(r.get('hek')),\n"
    "                r['best_hub'],\n"
    "                f'{mg:+.1f}%' if mg is not None else '\u2014',\n"
    "                f'{dev:+.1f}%' if dev is not None else '\u2014',\n"
    "                min_u,\n"
    "            ))",
    '_filter_import_tree full replacement')

# ─── 11. _sort_import_tree: add min_units to ascending-first cols ─────────────
src = apply(src,
    "            self._import_sort_asc = col in ('category', 'item', 'best_hub')",
    "            self._import_sort_asc = col in ('category', 'item', 'best_hub', 'min_units')",
    '_sort_import_tree ascending list')

# ─── Check errors & syntax ────────────────────────────────────────────────────
if errors:
    print('\nERRORS — file NOT written:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)

import ast
try:
    ast.parse(src)
    print('\nSyntax: OK')
except SyntaxError as e:
    print(f'\nSyntax error: {e}')
    sys.exit(1)

with open(FILE, 'w', encoding='utf-8') as f:
    f.write(src)
print(f'Written: {FILE}')
