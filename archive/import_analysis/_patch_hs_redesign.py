#!/usr/bin/env python3
"""Patch script: Replace HS FREIGHT section with 3-leg route design.

Three replacements in admin_dashboard.py:
  1. UI block in build_import_tab()  (lines ~3101-3201)
  2. hs_ism3/isj/coll var removals + hubs_cfg loop (lines ~3511-3538)
  3. HS cost calculation (lines ~3677-3683)
"""

import sys, os

FILE = r'e:\Python Project\admin_dashboard.py'

with open(FILE, 'r', encoding='utf-8') as f:
    src = f.read()

original_src = src

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 1 — HS FREIGHT UI block
# ─────────────────────────────────────────────────────────────────────────────

OLD_UI = (
    "        # ── HS FREIGHT (collapsible) ──────────────────────────────────────────────────────────────────────────────────\n"
    "        hs_card = ttk.Frame(outer, style='Card.TFrame')\n"
    "        hs_card.pack(fill='x', pady=(0, 4))\n"
    "        hs_body = ttk.Frame(hs_card, style='Card.TFrame')\n"
    "        hs_state = {'open': True}\n"
    "\n"
    "        def _toggle_hs():\n"
    "            if hs_state['open']:\n"
    "                hs_body.pack_forget()\n"
    "                hs_state['open'] = False\n"
    "                hs_btn.configure(text='▶  HS FREIGHT  (High-Sec legs)')\n"
    "            else:\n"
    "                hs_body.pack(fill='x', padx=12, pady=(0, 10))\n"
    "                hs_state['open'] = True\n"
    "                hs_btn.configure(text='▼  HS FREIGHT  (High-Sec legs)')\n"
    "\n"
    "        hs_btn = tk.Button(hs_card, text='▼  HS FREIGHT  (High-Sec legs)',\n"
    "                           background='#0a2030', foreground='#ff9944',\n"
    "                           activebackground='#0d2535', activeforeground='#ff9944',\n"
    "                           font=('Segoe UI', 9, 'bold'), relief='flat',\n"
    "                           cursor='hand2', anchor='w', command=_toggle_hs)\n"
    "        hs_btn.pack(fill='x', padx=12, pady=(8, 2))\n"
    "        hs_body.pack(fill='x', padx=12, pady=(0, 10))\n"
    "\n"
    "        # Freight rates\n"
    "        hs_rates = ttk.Frame(hs_body, style='Card.TFrame')\n"
    "        hs_rates.pack(fill='x', pady=(0, 8))\n"
    "        for key, label, default, w in [\n"
    "            ('hs_ism3', 'ISK/m³',  '150', 7),\n"
    "            ('hs_isj',  'ISK/jump', '50',  6),\n"
    "            ('hs_coll', 'Collat %', '1.0', 6),\n"
    "        ]:\n"
    "            tk.Label(hs_rates, text=label, **lbl_cfg).pack(side='left', padx=(0, 4))\n"
    "            var = tk.StringVar(value=self._get_config(f'hub_import_{key}', default))\n"
    "            var.trace_add('write', lambda *_, k=f'hub_import_{key}', v=var:\n"
    "                          self._set_config(k, v.get()))\n"
    "            setattr(self, f'hub_{key}_var', var)\n"
    "            ttk.Entry(hs_rates, textvariable=var, width=w).pack(side='left', padx=(0, 20))\n"
    "\n"
    "        # Hub table\n"
    "        hg = ttk.Frame(hs_body, style='Card.TFrame')\n"
    "        hg.pack(fill='x')\n"
    "        for ci, txt in enumerate(['Hub', 'Leg 1 Jumps', '+2nd Leg', 'Leg 2 Jumps', 'Enabled']):\n"
    "            tk.Label(hg, text=txt, background='#0a2030', foreground='#88d0e8',\n"
    "                     font=('Segoe UI', 8, 'bold')).grid(\n"
    "                     row=0, column=ci, sticky='w', padx=(0, 22), pady=(0, 4))\n"
    "        self._hub_vars = {}\n"
    "        HUB_DEFAULTS = {\n"
    "            'jita':    {'j1': '0',  'j2': '0',  'leg2': False, 'en': True},\n"
    "            'amarr':   {'j1': '9',  'j2': '4',  'leg2': True,  'en': True},\n"
    "            'dodixie': {'j1': '6',  'j2': '0',  'leg2': False, 'en': True},\n"
    "            'rens':    {'j1': '13', 'j2': '4',  'leg2': True,  'en': True},\n"
    "            'hek':     {'j1': '16', 'j2': '4',  'leg2': True,  'en': True},\n"
    "        }\n"
    "        HUB_COLORS = {\n"
    "            'jita': '#00ffff', 'amarr': '#ffaa44', 'dodixie': '#ffcc88',\n"
    "            'rens': '#88ffcc', 'hek':   '#88ccff',\n"
    "        }\n"
    "        for ri, (hub, defs) in enumerate(HUB_DEFAULTS.items(), start=1):\n"
    "            tk.Label(hg, text=hub.title(), background='#0a2030',\n"
    "                     foreground=HUB_COLORS[hub],\n"
    "                     font=('Segoe UI', 9, 'bold')).grid(\n"
    "                     row=ri, column=0, sticky='w', padx=(0, 22))\n"
    "            if hub == 'jita':\n"
    "                tk.Label(hg, text='── null only ──',\n"
    "                         background='#0a2030',\n"
    "                         foreground='#1a4060', font=('Segoe UI', 9)).grid(\n"
    "                         row=ri, column=1, columnspan=3, sticky='w')\n"
    "                en_v = tk.BooleanVar(value=bool(int(\n"
    "                    self._get_config('hub_import_en_jita', '1'))))\n"
    "                en_v.trace_add('write', lambda *_, v=en_v:\n"
    "                    self._set_config('hub_import_en_jita', '1' if v.get() else '0'))\n"
    "                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')\n"
    "                self._hub_vars['jita'] = {'en': en_v}\n"
    "            else:\n"
    "                j1_v = tk.StringVar(value=self._get_config(\n"
    "                    f'hub_import_j1_{hub}', defs['j1']))\n"
    "                j1_v.trace_add('write', lambda *_, k=f'hub_import_j1_{hub}', v=j1_v:\n"
    "                    self._set_config(k, v.get()))\n"
    "                ttk.Entry(hg, textvariable=j1_v, width=5).grid(\n"
    "                    row=ri, column=1, sticky='w', padx=(0, 22))\n"
    "                l2_v = tk.BooleanVar(value=bool(int(self._get_config(\n"
    "                    f'hub_import_leg2_{hub}', '1' if defs['leg2'] else '0'))))\n"
    "                l2_v.trace_add('write', lambda *_, k=f'hub_import_leg2_{hub}', v=l2_v:\n"
    "                    self._set_config(k, '1' if v.get() else '0'))\n"
    "                ttk.Checkbutton(hg, variable=l2_v).grid(\n"
    "                    row=ri, column=2, sticky='w', padx=(4, 22))\n"
    "                j2_v = tk.StringVar(value=self._get_config(\n"
    "                    f'hub_import_j2_{hub}', defs['j2']))\n"
    "                j2_v.trace_add('write', lambda *_, k=f'hub_import_j2_{hub}', v=j2_v:\n"
    "                    self._set_config(k, v.get()))\n"
    "                ttk.Entry(hg, textvariable=j2_v, width=5).grid(\n"
    "                    row=ri, column=3, sticky='w', padx=(0, 22))\n"
    "                en_v = tk.BooleanVar(value=bool(int(self._get_config(\n"
    "                    f'hub_import_en_{hub}', '1'))))\n"
    "                en_v.trace_add('write', lambda *_, k=f'hub_import_en_{hub}', v=en_v:\n"
    "                    self._set_config(k, '1' if v.get() else '0'))\n"
    "                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')\n"
    "                self._hub_vars[hub] = {\n"
    "                    'j1': j1_v, 'j2': j2_v, 'leg2': l2_v, 'en': en_v}"
)

NEW_UI = """\
        # ── HS FREIGHT (collapsible) ──────────────────────────────────────────────────────────────────────────────────
        hs_card = ttk.Frame(outer, style='Card.TFrame')
        hs_card.pack(fill='x', pady=(0, 4))
        hs_body = ttk.Frame(hs_card, style='Card.TFrame')
        hs_state = {'open': True}

        def _toggle_hs():
            if hs_state['open']:
                hs_body.pack_forget()
                hs_state['open'] = False
                hs_btn.configure(text='\u25b6  HS FREIGHT  (High-Sec legs)')
            else:
                hs_body.pack(fill='x', padx=12, pady=(0, 10))
                hs_state['open'] = True
                hs_btn.configure(text='\u25bc  HS FREIGHT  (High-Sec legs)')

        hs_btn = tk.Button(hs_card, text='\u25bc  HS FREIGHT  (High-Sec legs)',
                           background='#0a2030', foreground='#ff9944',
                           activebackground='#0d2535', activeforeground='#ff9944',
                           font=('Segoe UI', 9, 'bold'), relief='flat',
                           cursor='hand2', anchor='w', command=_toggle_hs)
        hs_btn.pack(fill='x', padx=12, pady=(8, 2))
        hs_body.pack(fill='x', padx=12, pady=(0, 10))

        # Leg rate cards (3 legs)
        self._leg_vars = {}
        LEG_DEFAULTS = {
            1: {'en': '1',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
            2: {'en': '1',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
            3: {'en': '0',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
        }
        for n, defs in LEG_DEFAULTS.items():
            leg_outer = ttk.Frame(hs_body, style='Card.TFrame')
            leg_outer.pack(fill='x', pady=(0, 4))
            hdr = ttk.Frame(leg_outer, style='Card.TFrame')
            hdr.pack(fill='x', padx=4, pady=(2, 0))
            en_v = tk.BooleanVar(value=bool(int(
                self._get_config(f'hub_import_leg{n}_en', defs['en']))))
            _n, _v = n, en_v
            en_v.trace_add('write', lambda *_, k=f'hub_import_leg{n}_en', v=en_v:
                           self._set_config(k, '1' if v.get() else '0'))
            ttk.Checkbutton(hdr, variable=en_v).pack(side='left')
            tk.Label(hdr, text=f'Leg {n}', background='#0a2030', foreground='#ff9944',
                     font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(4, 0))
            rates_row = ttk.Frame(leg_outer, style='Card.TFrame')
            rates_row.pack(fill='x', padx=4, pady=(0, 4))
            leg_vd = {'en': en_v}
            for key, label, w in [
                ('ism3', 'ISK/m\u00b3',       7),
                ('isj',  'ISK/jump',     8),
                ('coll', 'Collat %',     6),
                ('dep',  'Departing m\u00b3', 9),
            ]:
                tk.Label(rates_row, text=label, background='#0a2030', foreground='#aaaaaa',
                         font=('Segoe UI', 8)).pack(side='left', padx=(0, 3))
                var = tk.StringVar(value=self._get_config(
                    f'hub_import_leg{n}_{key}', defs[key]))
                var.trace_add('write', lambda *_, k=f'hub_import_leg{n}_{key}', v=var:
                              self._set_config(k, v.get()))
                ttk.Entry(rates_row, textvariable=var, width=w).pack(
                    side='left', padx=(0, 14))
                leg_vd[key] = var
            self._leg_vars[n] = leg_vd

        # Hub assignment table
        hg = ttk.Frame(hs_body, style='Card.TFrame')
        hg.pack(fill='x', pady=(4, 0))
        for ci, txt in enumerate(['Hub', 'Leg 1 j', 'Leg 2 j', 'Leg 3 j', 'Enabled']):
            tk.Label(hg, text=txt, background='#0a2030', foreground='#88d0e8',
                     font=('Segoe UI', 8, 'bold')).grid(
                     row=0, column=ci, sticky='w', padx=(0, 16), pady=(0, 4))
        self._hub_vars = {}
        HUB_DEFAULTS = {
            'jita':    {'j1': '0',  'j2': '0',  'j3': '0',  'en': True},
            'amarr':   {'j1': '20', 'j2': '6',  'j3': '19', 'en': True},
            'dodixie': {'j1': '15', 'j2': '0',  'j3': '0',  'en': True},
            'rens':    {'j1': '0',  'j2': '6',  'j3': '19', 'en': True},
            'hek':     {'j1': '0',  'j2': '0',  'j3': '19', 'en': True},
        }
        HUB_COLORS = {
            'jita': '#00ffff', 'amarr': '#ffaa44', 'dodixie': '#ffcc88',
            'rens': '#88ffcc', 'hek':   '#88ccff',
        }
        for ri, (hub, defs) in enumerate(HUB_DEFAULTS.items(), start=1):
            tk.Label(hg, text=hub.title(), background='#0a2030',
                     foreground=HUB_COLORS[hub],
                     font=('Segoe UI', 9, 'bold')).grid(
                     row=ri, column=0, sticky='w', padx=(0, 16))
            if hub == 'jita':
                tk.Label(hg, text='\u2500\u2500 null only \u2500\u2500',
                         background='#0a2030', foreground='#1a4060',
                         font=('Segoe UI', 9)).grid(
                         row=ri, column=1, columnspan=3, sticky='w')
                en_v = tk.BooleanVar(value=bool(int(
                    self._get_config('hub_import_en_jita', '1'))))
                en_v.trace_add('write', lambda *_, v=en_v:
                    self._set_config('hub_import_en_jita', '1' if v.get() else '0'))
                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')
                self._hub_vars['jita'] = {'en': en_v}
            else:
                hub_vd = {}
                for ci2, jk in enumerate(('j1', 'j2', 'j3'), start=1):
                    jv = tk.StringVar(value=self._get_config(
                        f'hub_import_{jk}_{hub}', defs[jk]))
                    jv.trace_add('write', lambda *_, k=f'hub_import_{jk}_{hub}', v=jv:
                        self._set_config(k, v.get()))
                    ttk.Entry(hg, textvariable=jv, width=5).grid(
                        row=ri, column=ci2, sticky='w', padx=(0, 16))
                    hub_vd[jk] = jv
                en_v = tk.BooleanVar(value=bool(int(self._get_config(
                    f'hub_import_en_{hub}', '1'))))
                en_v.trace_add('write', lambda *_, k=f'hub_import_en_{hub}', v=en_v:
                    self._set_config(k, '1' if v.get() else '0'))
                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')
                hub_vd['en'] = en_v
                self._hub_vars[hub] = hub_vd

        # Jump Reference (editable, informational)
        jr_sep = ttk.Frame(hs_body, style='Card.TFrame')
        jr_sep.pack(fill='x', pady=(6, 0))
        tk.Label(jr_sep, text='Jump Reference:', background='#0a2030',
                 foreground='#88d0e8',
                 font=('Segoe UI', 8, 'bold')).pack(side='left', padx=(0, 8))
        JUMP_REF_PAIRS = [
            ('jita',  'amarr',   '45'), ('jita',  'rens',    '25'),
            ('jita',  'hek',     '19'), ('jita',  'dodixie', '15'),
            ('amarr', 'rens',    '20'), ('amarr', 'hek',     '26'),
            ('rens',  'hek',     '6'),
        ]
        self._jump_ref = {}
        for h1, h2, default in JUMP_REF_PAIRS:
            cfg_key = f'hub_import_ref_{h1}_{h2}'
            tk.Label(jr_sep, text=f'{h1.title()}\u2194{h2.title()}',
                     background='#0a2030', foreground='#556677',
                     font=('Segoe UI', 8)).pack(side='left', padx=(0, 2))
            rvar = tk.StringVar(value=self._get_config(cfg_key, default))
            rvar.trace_add('write', lambda *_, k=cfg_key, v=rvar:
                           self._set_config(k, v.get()))
            ttk.Entry(jr_sep, textvariable=rvar, width=4).pack(side='left', padx=(0, 8))
            self._jump_ref[(h1, h2)] = rvar"""

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 2 — Remove hs_ism3/isj/coll vars from load_import_data()
# ─────────────────────────────────────────────────────────────────────────────

OLD_HS_VARS = (
    "            hs_ism3    = float(self.hub_hs_ism3_var.get())\n"
    "            hs_isj     = float(self.hub_hs_isj_var.get())\n"
    "            hs_coll    = float(self.hub_hs_coll_var.get()) / 100.0\n"
)
NEW_HS_VARS = ""  # removed — values now come from self._leg_vars

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 3 — Replace hubs_cfg build with legs_cfg + hubs_cfg
# ─────────────────────────────────────────────────────────────────────────────

OLD_HUBS_CFG = (
    "        hubs_cfg = {}\n"
    "        for hub in HUB_STATION:\n"
    "            hv = self._hub_vars.get(hub, {})\n"
    "            try:\n"
    "                j1 = int(float(hv['j1'].get())) if 'j1' in hv else 0\n"
    "                j2 = int(float(hv['j2'].get())) if 'j2' in hv else 0\n"
    "            except (ValueError, AttributeError):\n"
    "                j1, j2 = 0, 0\n"
    "            hubs_cfg[hub] = {\n"
    "                'j1':   j1,\n"
    "                'j2':   j2,\n"
    "                'leg2': hv['leg2'].get() if 'leg2' in hv else False,\n"
    "                'en':   hv['en'].get()   if 'en'   in hv else True,\n"
    "            }"
)

NEW_HUBS_CFG = """\
        legs_cfg = {}
        for _n in (1, 2, 3):
            lv = self._leg_vars[_n]
            try:
                legs_cfg[_n] = {
                    'en':   lv['en'].get(),
                    'ism3': float(lv['ism3'].get()),
                    'isj':  float(lv['isj'].get()),
                    'coll': float(lv['coll'].get()) / 100,
                    'dep':  max(float(lv['dep'].get()), 1.0),
                }
            except (ValueError, AttributeError):
                legs_cfg[_n] = {'en': False, 'ism3': 0, 'isj': 0, 'coll': 0, 'dep': 1}
        hubs_cfg = {}
        for hub in HUB_STATION:
            hv = self._hub_vars.get(hub, {})
            jumps = {}
            for jk in ('j1', 'j2', 'j3'):
                try:    jumps[jk] = int(float(hv[jk].get())) if jk in hv else 0
                except: jumps[jk] = 0
            hubs_cfg[hub] = {**jumps, 'en': hv['en'].get() if 'en' in hv else True}"""

# ─────────────────────────────────────────────────────────────────────────────
# REPLACEMENT 4 — Replace HS cost calculation
# ─────────────────────────────────────────────────────────────────────────────

OLD_HS_CALC = (
    "                if hub == 'jita':\n"
    "                    lc = buy_price + broker + null_cost\n"
    "                else:\n"
    "                    hub_jumps = cfg['j1'] + (cfg['j2'] if cfg['leg2'] else 0)\n"
    "                    hs_cost   = hs_ism3 * volume + hs_isj * hub_jumps + hs_coll * buy_price\n"
    "                    lc = buy_price + broker + hs_cost + null_cost"
)

NEW_HS_CALC = """\
                if hub == 'jita':
                    lc = buy_price + broker + null_cost
                else:
                    hs_cost = 0.0
                    for _n, jkey in ((1, 'j1'), (2, 'j2'), (3, 'j3')):
                        leg   = legs_cfg[_n]
                        jumps = hubs_cfg[hub][jkey]
                        if not leg['en'] or jumps <= 0:
                            continue
                        hs_cost += (
                            leg['ism3'] * volume
                            + leg['isj'] * jumps * (volume / leg['dep'])
                            + leg['coll'] * buy_price
                        )
                    lc = buy_price + broker + hs_cost + null_cost"""

# ─────────────────────────────────────────────────────────────────────────────
# Apply replacements
# ─────────────────────────────────────────────────────────────────────────────

errors = []

def apply(src, old, new, label):
    if old not in src:
        errors.append(f'NOT FOUND: {label}')
        return src
    count = src.count(old)
    if count > 1:
        errors.append(f'AMBIGUOUS ({count} matches): {label}')
        return src
    print(f'  OK: {label}')
    return src.replace(old, new)

src = apply(src, OLD_UI,       NEW_UI,       'UI block (build_import_tab)')
src = apply(src, OLD_HS_VARS,  NEW_HS_VARS,  'hs_ism3/isj/coll var removal')
src = apply(src, OLD_HUBS_CFG, NEW_HUBS_CFG, 'hubs_cfg build replacement')
src = apply(src, OLD_HS_CALC,  NEW_HS_CALC,  'HS cost calculation replacement')

if errors:
    print('\nERRORS — file NOT written:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)

# Syntax check
import ast
try:
    ast.parse(src)
    print('\nSyntax check: OK')
except SyntaxError as e:
    print(f'\nSyntax error: {e}')
    sys.exit(1)

# Write
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(src)
print(f'Written: {FILE}')
