"""
Patch: Add Contract Hauler mode toggle to Import Analysis HS FREIGHT section.

Changes:
1. build_import_tab() — adds mode toggle + per-hub rate card UI inside hs_body.
   Existing 3-leg freighter UI is wrapped in a sub-frame and toggled visible/hidden.
2. load_import_data() — branches on mode: 'freighter' uses existing leg logic unchanged;
   'contract' uses per-hub ism3/coll/min_reward rates.
"""
import sys, os

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'admin_dashboard.py')

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1: Wrap freighter content and add mode toggle + contract rate card
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = """\
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

NEW1 = """\
        # ── HS Mode toggle (Freighter / Contract) ────────────────────────────
        mode_row = ttk.Frame(hs_body, style='Card.TFrame')
        mode_row.pack(fill='x', pady=(0, 6))
        tk.Label(mode_row, text='HS Mode:', background='#0a2030', foreground='#ff9944',
                 font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 8))
        self.hub_hs_mode_var = tk.StringVar(
            value=self._get_config('hub_hs_mode', 'freighter'))
        self.hub_hs_mode_var.trace_add('write', lambda *_: (
            self._set_config('hub_hs_mode', self.hub_hs_mode_var.get()),
            self._toggle_hs_mode()))

        # Sub-frames that swap in/out
        self._hs_freighter_frame = ttk.Frame(hs_body, style='Card.TFrame')
        self._hs_contract_frame  = ttk.Frame(hs_body, style='Card.TFrame')

        for val, lbl in [('freighter', 'Freighter (DIY)'), ('contract', 'Contract Hauler')]:
            tk.Radiobutton(mode_row, text=lbl,
                           variable=self.hub_hs_mode_var, value=val,
                           background='#0a2030', foreground='#aaccdd',
                           activebackground='#0a2030', activeforeground='#ff9944',
                           selectcolor='#0a2030', font=('Segoe UI', 9),
                           relief='flat').pack(side='left', padx=(0, 12))

        # ── FREIGHTER sub-frame ───────────────────────────────────────────────
        ff = self._hs_freighter_frame

        # Leg rate cards (3 legs)
        self._leg_vars = {}
        LEG_DEFAULTS = {
            1: {'en': '1',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
            2: {'en': '1',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
            3: {'en': '0',  'ism3': '150', 'isj': '50000', 'coll': '1.0', 'dep': '900000'},
        }
        for n, defs in LEG_DEFAULTS.items():
            leg_outer = ttk.Frame(ff, style='Card.TFrame')
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
        hg = ttk.Frame(ff, style='Card.TFrame')
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
        jr_sep = ttk.Frame(ff, style='Card.TFrame')
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
            self._jump_ref[(h1, h2)] = rvar

        # ── CONTRACT sub-frame ────────────────────────────────────────────────
        cf = self._hs_contract_frame
        tk.Label(cf, text='Per-hub contract rates  (offer to freelance haulers)',
                 background='#0a2030', foreground='#88d0e8',
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 4))

        cg = ttk.Frame(cf, style='Card.TFrame')
        cg.pack(fill='x')
        for ci, hdr_txt in enumerate(['Hub', 'ISK/m\u00b3', 'Coll %', 'Min Reward (ISK)']):
            tk.Label(cg, text=hdr_txt, background='#0a2030', foreground='#88d0e8',
                     font=('Segoe UI', 8, 'bold')).grid(
                     row=0, column=ci, sticky='w', padx=(0, 20), pady=(0, 4))

        CONTRACT_DEFAULTS = {
            'amarr':   {'ism3': '500', 'coll': '0.5', 'min_reward': '2000000'},
            'dodixie': {'ism3': '400', 'coll': '0.5', 'min_reward': '1500000'},
            'rens':    {'ism3': '450', 'coll': '0.5', 'min_reward': '1800000'},
            'hek':     {'ism3': '350', 'coll': '0.5', 'min_reward': '1200000'},
        }
        HUB_COLORS2 = {
            'amarr': '#ffaa44', 'dodixie': '#ffcc88',
            'rens': '#88ffcc', 'hek':   '#88ccff',
        }
        self._hub_contract_vars = {}
        for ri, (hub, defs) in enumerate(CONTRACT_DEFAULTS.items(), start=1):
            tk.Label(cg, text=hub.title(), background='#0a2030',
                     foreground=HUB_COLORS2[hub],
                     font=('Segoe UI', 9, 'bold')).grid(
                     row=ri, column=0, sticky='w', padx=(0, 20))
            cvd = {}
            for ci2, (key, w) in enumerate([('ism3', 7), ('coll', 6), ('min_reward', 12)],
                                            start=1):
                cfg_key = f'hub_import_contract_{key}_{hub}'
                v = tk.StringVar(value=self._get_config(cfg_key, defs[key]))
                v.trace_add('write', lambda *_, k=cfg_key, vv=v:
                            self._set_config(k, vv.get()))
                ttk.Entry(cg, textvariable=v, width=w).grid(
                    row=ri, column=ci2, sticky='w', padx=(0, 20))
                cvd[key] = v
            self._hub_contract_vars[hub] = cvd

        tk.Label(cf, text='Jita: no HS leg (null-sec direct)',
                 background='#0a2030', foreground='#1a4060',
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(6, 0))

        # Pack whichever frame is active at startup
        self._toggle_hs_mode()"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2: Add _toggle_hs_mode() helper method
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = "    def load_import_data(self):"

NEW2 = """\
    def _toggle_hs_mode(self):
        \"\"\"Show/hide freighter vs contract rate card inside HS FREIGHT section.\"\"\"
        mode = self.hub_hs_mode_var.get()
        if mode == 'contract':
            self._hs_freighter_frame.pack_forget()
            self._hs_contract_frame.pack(fill='x')
        else:
            self._hs_contract_frame.pack_forget()
            self._hs_freighter_frame.pack(fill='x')

    def load_import_data(self):"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3: Add hs_mode read + contract_rates build in load_import_data
# ─────────────────────────────────────────────────────────────────────────────
OLD3 = """\
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

NEW3 = """\
        hs_mode = self.hub_hs_mode_var.get()   # 'freighter' or 'contract'

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
            hubs_cfg[hub] = {**jumps, 'en': hv['en'].get() if 'en' in hv else True}

        # Contract mode: build per-hub rate lookup
        contract_rates = {}
        for hub, cvd in self._hub_contract_vars.items():
            try:
                contract_rates[hub] = {
                    'ism3':       float(cvd['ism3'].get()),
                    'coll':       float(cvd['coll'].get()) / 100.0,
                    'min_reward': float(cvd['min_reward'].get()),
                }
            except (ValueError, AttributeError):
                contract_rates[hub] = {'ism3': 0, 'coll': 0, 'min_reward': 0}"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 4: Branch the hs_cost calculation
# ─────────────────────────────────────────────────────────────────────────────
OLD4 = """\
                if hub == 'jita':
                    lc = buy_price + broker + null_cost
                    landed_comps[hub] = {
                        'fixed': null_fixed,
                        'var':   buy_price + broker + null_var,
                        'dep':   1e12,
                    }
                else:
                    hs_cost    = 0.0
                    hs_fixed_h = 0.0
                    hs_var_h   = 0.0
                    dep_list   = []"""

NEW4 = """\
                if hub == 'jita':
                    lc = buy_price + broker + null_cost
                    landed_comps[hub] = {
                        'fixed': null_fixed,
                        'var':   buy_price + broker + null_var,
                        'dep':   1e12,
                    }
                elif hs_mode == 'contract':
                    cr         = contract_rates.get(hub, {'ism3': 0, 'coll': 0, 'min_reward': 0})
                    hs_var_h   = cr['ism3'] * volume + cr['coll'] * buy_price
                    hs_fixed_h = cr['min_reward']
                    lc = buy_price + broker + hs_var_h + null_cost
                    landed_comps[hub] = {
                        'fixed': hs_fixed_h + null_fixed,
                        'var':   buy_price + broker + hs_var_h + null_var,
                        'dep':   860000.0,
                    }
                else:
                    hs_cost    = 0.0
                    hs_fixed_h = 0.0
                    hs_var_h   = 0.0
                    dep_list   = []"""

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

src = apply(src, OLD1, NEW1, 'hs_body UI restructure + contract frame')
src = apply(src, OLD2, NEW2, '_toggle_hs_mode helper method')
src = apply(src, OLD3, NEW3, 'load_import_data contract_rates build')
src = apply(src, OLD4, NEW4, 'landed cost loop contract branch')

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print(f'\nPatched: {TARGET}')
