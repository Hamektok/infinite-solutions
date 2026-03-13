"""
Full rewrite of 5 Import Analysis functions in admin_dashboard.py.
Run once then delete.
"""
import re

PATH = r'e:\Python Project\admin_dashboard.py'

with open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.splitlines(keepends=True)

# ── Locate function start/end positions ────────────────────────────────────────

def find_def_line(lines, method_name):
    """Return 0-indexed line index of '    def method_name('."""
    pat = f'    def {method_name}('
    for i, ln in enumerate(lines):
        if ln.startswith(pat):
            return i
    raise ValueError(f'def {method_name} not found')

pos_build   = find_def_line(lines, 'build_import_tab')
pos_broker  = find_def_line(lines, '_hub_import_broker_toggle')  # first method after build_import_tab
pos_load    = find_def_line(lines, 'load_import_data')
pos_cat     = find_def_line(lines, '_import_cat_changed')
pos_filter  = find_def_line(lines, '_filter_import_tree')
pos_sort    = find_def_line(lines, '_sort_import_tree')

# End of _sort_import_tree: first non-blank line at 4-space class level after the body
sort_end = None
for i in range(pos_sort + 1, len(lines)):
    ln = lines[i].rstrip()
    if ln and not ln.startswith('        '):  # non-blank, not 8-space indented
        sort_end = i
        break
if sort_end is None:
    sort_end = len(lines)

print(f'build_import_tab       : line {pos_build+1}')
print(f'_hub_import_broker_toggle: line {pos_broker+1}  (preserved section start)')
print(f'load_import_data       : line {pos_load+1}')
print(f'_import_cat_changed    : line {pos_cat+1}')
print(f'_filter_import_tree    : line {pos_filter+1}')
print(f'_sort_import_tree      : line {pos_sort+1}  (ends before line {sort_end+1})')

# ── New function bodies ─────────────────────────────────────────────────────────

NEW_BUILD = '''\
    def build_import_tab(self):
        """Build the Multi-Hub Import Analysis tab (Phase 1: ore items)."""
        import threading as _threading
        self._hub_import_threading = _threading

        outer = ttk.Frame(self.import_frame)
        outer.pack(fill='both', expand=True, padx=15, pady=(15, 10))

        ttk.Label(outer,
                  text="Compare landed costs across all 5 EVE trade hubs \u2014 "
                       "buy at cheapest hub, ship to null-sec, refine and sell via contract.",
                  style='SubHeader.TLabel').pack(anchor='w', pady=(0, 8))

        # \u2500\u2500 Fetch card \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        fetch_card = ttk.Frame(outer, style='Card.TFrame')
        fetch_card.pack(fill='x', pady=(0, 8))
        fi = ttk.Frame(fetch_card, style='Card.TFrame')
        fi.pack(fill='x', padx=12, pady=8)
        tk.Label(fi, text='Fetch Hub Prices:', background='#0a2030',
                 foreground='#88d0e8', font=('Segoe UI', 9)).pack(side='left', padx=(0, 8))
        self._hub_fetch_btns = {}
        for label, cat in [('All', 'all'), ('Tracked', 'tracked'),
                            ('Std Ore', 'standard'), ('Ice Ore', 'ice'),
                            ('Moon Ore', 'moon'), ('Gas', 'gas')]:
            btn = ttk.Button(fi, text=f'\u27f3 {label}', style='Action.TButton',
                             command=lambda c=cat: self._run_hub_fetch(c))
            btn.pack(side='left', padx=(0, 4))
            self._hub_fetch_btns[cat] = btn
        self._hub_price_age_lbl = tk.Label(fi,
            text='\u26a0 Not loaded \u2014 click Fetch to begin',
            background='#0a2030', foreground='#ffcc44', font=('Segoe UI', 8))
        self._hub_price_age_lbl.pack(side='right')

        # \u2500\u2500 Parameter card \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        param_card = ttk.Frame(outer, style='Card.TFrame')
        param_card.pack(fill='x', pady=(0, 4))
        pi = ttk.Frame(param_card, style='Card.TFrame')
        pi.pack(fill='x', padx=12, pady=(10, 8))

        lbl_cfg = dict(background='#0a2030', foreground='#88d0e8', font=('Segoe UI', 10))
        hdr_cfg = dict(background='#0a2030', font=('Segoe UI', 9, 'bold'))
        col = 0

        # BUY SIDE
        tk.Label(pi, text="BUY SIDE", foreground='#66d9ff', **hdr_cfg).grid(
                 row=0, column=col, columnspan=3, sticky='w', pady=(0, 4))
        tk.Label(pi, text="Order Type", **lbl_cfg).grid(row=1, column=col, sticky='w', padx=(0, 4))
        self.hub_buy_type_var = tk.StringVar(
            value=self._get_config('hub_import_buy_type', 'Sell Orders'))
        self.hub_buy_type_var.trace_add('write',
            lambda *_: self._set_config('hub_import_buy_type', self.hub_buy_type_var.get()))
        self.hub_buy_type_var.trace_add('write', lambda *_: self._hub_import_broker_toggle())
        ttk.Combobox(pi, textvariable=self.hub_buy_type_var, width=12,
                     values=['Sell Orders', 'Buy Orders'],
                     state='readonly').grid(row=2, column=col, sticky='w', padx=(0, 8))
        col += 1
        tk.Label(pi, text="Buy %", **lbl_cfg).grid(row=1, column=col, sticky='w', padx=(0, 4))
        self.hub_buy_pct_var = tk.StringVar(
            value=self._get_config('hub_import_buy_pct', '100'))
        self.hub_buy_pct_var.trace_add('write',
            lambda *_: self._set_config('hub_import_buy_pct', self.hub_buy_pct_var.get()))
        ttk.Entry(pi, textvariable=self.hub_buy_pct_var, width=6).grid(
            row=2, column=col, sticky='w', padx=(0, 8))
        col += 1
        tk.Label(pi, text="Broker %", **lbl_cfg).grid(row=1, column=col, sticky='w', padx=(0, 4))
        self.hub_broker_var = tk.StringVar(
            value=self._get_config('hub_import_broker_pct', '0.0'))
        self.hub_broker_var.trace_add('write',
            lambda *_: self._set_config('hub_import_broker_pct', self.hub_broker_var.get()))
        self._hub_broker_entry = ttk.Entry(
            pi, textvariable=self.hub_broker_var, width=6, state='disabled')
        self._hub_broker_entry.grid(row=2, column=col, sticky='w', padx=(0, 16))
        col += 1

        tk.Frame(pi, background='#1a3040', width=1).grid(
            row=0, column=col, rowspan=3, sticky='ns', padx=(0, 16))
        col += 1

        # NULL FREIGHT
        tk.Label(pi, text="NULL FREIGHT  (Null-Sec leg)",
                 foreground='#ffcc44', **hdr_cfg).grid(
                 row=0, column=col, columnspan=4, sticky='w', pady=(0, 4))
        for key, label, default, w in [
            ('null_ism3', 'ISK/m\u00b3',  '125', 7),
            ('null_isj',  'ISK/jump', '0',   6),
            ('null_j',    '# Jumps',  '65',  6),
            ('null_coll', 'Collat %', '1.0', 6),
        ]:
            tk.Label(pi, text=label, **lbl_cfg).grid(row=1, column=col, sticky='w', padx=(0, 4))
            var = tk.StringVar(value=self._get_config(f'hub_import_{key}', default))
            var.trace_add('write', lambda *_, k=f'hub_import_{key}', v=var:
                          self._set_config(k, v.get()))
            setattr(self, f'hub_{key}_var', var)
            ttk.Entry(pi, textvariable=var, width=w).grid(
                row=2, column=col, sticky='w', padx=(0, 8))
            col += 1

        tk.Frame(pi, background='#1a3040', width=1).grid(
            row=0, column=col, rowspan=3, sticky='ns', padx=(0, 16))
        col += 1

        # ANALYSIS
        tk.Label(pi, text="ANALYSIS", foreground='#aaddff', **hdr_cfg).grid(
                 row=0, column=col, columnspan=2, sticky='w', pady=(0, 4))
        tk.Label(pi, text="Dev Window", **lbl_cfg).grid(
            row=1, column=col, sticky='w', padx=(0, 4))
        self.hub_dev_days_var = tk.StringVar(
            value=self._get_config('hub_import_dev_days', '7'))
        self.hub_dev_days_var.trace_add('write',
            lambda *_: self._set_config('hub_import_dev_days', self.hub_dev_days_var.get()))
        ttk.Entry(pi, textvariable=self.hub_dev_days_var, width=5).grid(
            row=2, column=col, sticky='w', padx=(0, 4))
        col += 1
        tk.Label(pi, text="days", **lbl_cfg).grid(row=2, column=col, sticky='w', padx=(0, 16))
        col += 1

        tk.Label(pi, text="Refine Eff %", **lbl_cfg).grid(
            row=1, column=col, sticky='w', padx=(0, 4))
        self.hub_refine_var = tk.StringVar(
            value=self._get_config('hub_import_refine_eff', '87.5'))
        self.hub_refine_var.trace_add('write',
            lambda *_: self._set_config('hub_import_refine_eff', self.hub_refine_var.get()))
        ttk.Entry(pi, textvariable=self.hub_refine_var, width=6).grid(
            row=2, column=col, sticky='w', padx=(0, 4))
        col += 1
        tk.Label(pi, text="%", **lbl_cfg).grid(row=2, column=col, sticky='w', padx=(0, 16))
        col += 1

        ttk.Button(pi, text='\u27f3  Recalculate', style='Action.TButton',
                   command=self.load_import_data).grid(row=2, column=col, sticky='w')

        self._hub_import_broker_toggle()

        # \u2500\u2500 HS FREIGHT (collapsible) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

        # Freight rates
        hs_rates = ttk.Frame(hs_body, style='Card.TFrame')
        hs_rates.pack(fill='x', pady=(0, 8))
        for key, label, default, w in [
            ('hs_ism3', 'ISK/m\u00b3',  '150', 7),
            ('hs_isj',  'ISK/jump', '50',  6),
            ('hs_coll', 'Collat %', '1.0', 6),
        ]:
            tk.Label(hs_rates, text=label, **lbl_cfg).pack(side='left', padx=(0, 4))
            var = tk.StringVar(value=self._get_config(f'hub_import_{key}', default))
            var.trace_add('write', lambda *_, k=f'hub_import_{key}', v=var:
                          self._set_config(k, v.get()))
            setattr(self, f'hub_{key}_var', var)
            ttk.Entry(hs_rates, textvariable=var, width=w).pack(side='left', padx=(0, 20))

        # Hub table
        hg = ttk.Frame(hs_body, style='Card.TFrame')
        hg.pack(fill='x')
        for ci, txt in enumerate(['Hub', 'Leg 1 Jumps', '+2nd Leg', 'Leg 2 Jumps', 'Enabled']):
            tk.Label(hg, text=txt, background='#0a2030', foreground='#88d0e8',
                     font=('Segoe UI', 8, 'bold')).grid(
                     row=0, column=ci, sticky='w', padx=(0, 22), pady=(0, 4))
        self._hub_vars = {}
        HUB_DEFAULTS = {
            'jita':    {'j1': '0',  'j2': '0',  'leg2': False, 'en': True},
            'amarr':   {'j1': '9',  'j2': '4',  'leg2': True,  'en': True},
            'dodixie': {'j1': '6',  'j2': '0',  'leg2': False, 'en': True},
            'rens':    {'j1': '13', 'j2': '4',  'leg2': True,  'en': True},
            'hek':     {'j1': '16', 'j2': '4',  'leg2': True,  'en': True},
        }
        HUB_COLORS = {
            'jita': '#00ffff', 'amarr': '#ffaa44', 'dodixie': '#ffcc88',
            'rens': '#88ffcc', 'hek':   '#88ccff',
        }
        for ri, (hub, defs) in enumerate(HUB_DEFAULTS.items(), start=1):
            tk.Label(hg, text=hub.title(), background='#0a2030',
                     foreground=HUB_COLORS[hub],
                     font=('Segoe UI', 9, 'bold')).grid(
                     row=ri, column=0, sticky='w', padx=(0, 22))
            if hub == 'jita':
                tk.Label(hg, text='\u2500\u2500 null only \u2500\u2500',
                         background='#0a2030',
                         foreground='#1a4060', font=('Segoe UI', 9)).grid(
                         row=ri, column=1, columnspan=3, sticky='w')
                en_v = tk.BooleanVar(value=bool(int(
                    self._get_config('hub_import_en_jita', '1'))))
                en_v.trace_add('write', lambda *_, v=en_v:
                    self._set_config('hub_import_en_jita', '1' if v.get() else '0'))
                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')
                self._hub_vars['jita'] = {'en': en_v}
            else:
                j1_v = tk.StringVar(value=self._get_config(
                    f'hub_import_j1_{hub}', defs['j1']))
                j1_v.trace_add('write', lambda *_, k=f'hub_import_j1_{hub}', v=j1_v:
                    self._set_config(k, v.get()))
                ttk.Entry(hg, textvariable=j1_v, width=5).grid(
                    row=ri, column=1, sticky='w', padx=(0, 22))
                l2_v = tk.BooleanVar(value=bool(int(self._get_config(
                    f'hub_import_leg2_{hub}', '1' if defs['leg2'] else '0'))))
                l2_v.trace_add('write', lambda *_, k=f'hub_import_leg2_{hub}', v=l2_v:
                    self._set_config(k, '1' if v.get() else '0'))
                ttk.Checkbutton(hg, variable=l2_v).grid(
                    row=ri, column=2, sticky='w', padx=(4, 22))
                j2_v = tk.StringVar(value=self._get_config(
                    f'hub_import_j2_{hub}', defs['j2']))
                j2_v.trace_add('write', lambda *_, k=f'hub_import_j2_{hub}', v=j2_v:
                    self._set_config(k, v.get()))
                ttk.Entry(hg, textvariable=j2_v, width=5).grid(
                    row=ri, column=3, sticky='w', padx=(0, 22))
                en_v = tk.BooleanVar(value=bool(int(self._get_config(
                    f'hub_import_en_{hub}', '1'))))
                en_v.trace_add('write', lambda *_, k=f'hub_import_en_{hub}', v=en_v:
                    self._set_config(k, '1' if v.get() else '0'))
                ttk.Checkbutton(hg, variable=en_v).grid(row=ri, column=4, sticky='w')
                self._hub_vars[hub] = {
                    'j1': j1_v, 'j2': j2_v, 'leg2': l2_v, 'en': en_v}

        # \u2500\u2500 Sell Price Overrides (collapsible) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        self._hub_sell_basis = {}
        self._hub_sell_pct   = {}
        self._build_hub_sell_overrides(outer)

        # \u2500\u2500 Summary cards \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        self.hub_import_summary_frame = ttk.Frame(outer)
        self.hub_import_summary_frame.pack(fill='x', pady=(0, 8))
        self._hub_import_summary_labels = {}
        for key, title in [
            ('total',        'ITEMS ANALYSED'),
            ('profitable',   'PROFITABLE'),
            ('best_margin',  'BEST MARGIN'),
            ('worst_margin', 'WORST MARGIN'),
        ]:
            card = ttk.Frame(self.hub_import_summary_frame, style='Card.TFrame')
            card.pack(side='left', fill='both', expand=True, padx=3)
            tk.Label(card, text=title, background='#0a2030', foreground='#66d9ff',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=8, pady=(6, 0))
            val_lbl = tk.Label(card, text='\u2014', background='#0a2030',
                               foreground='#00ffff', font=('Segoe UI', 12, 'bold'))
            val_lbl.pack(anchor='w', padx=8, pady=(0, 6))
            self._hub_import_summary_labels[key] = val_lbl

        # \u2500\u2500 Filter row \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        filter_frame = ttk.Frame(outer)
        filter_frame.pack(fill='x', pady=(0, 6))
        ttk.Label(filter_frame, text="Search:").pack(side='left', padx=(0, 4))
        self.hub_import_search_var = tk.StringVar()
        self.hub_import_search_var.trace_add('write', lambda *_: self._filter_import_tree())
        ttk.Entry(filter_frame, textvariable=self.hub_import_search_var, width=18).pack(
            side='left', padx=(0, 12))
        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 4))
        self.import_cat_var = tk.StringVar(value='All')
        import_cat_menu = ttk.Combobox(
            filter_frame, textvariable=self.import_cat_var, width=14, state='readonly',
            values=['All', 'Standard Ore', 'Ice Ore', 'Moon Ore'])
        import_cat_menu.pack(side='left', padx=(0, 12))
        import_cat_menu.bind('<<ComboboxSelected>>', lambda _: self._import_cat_changed())
        ttk.Label(filter_frame, text="Show:").pack(side='left', padx=(0, 4))
        self.import_show_var = tk.StringVar(value='All')
        show_menu = ttk.Combobox(
            filter_frame, textvariable=self.import_show_var, width=14, state='readonly',
            values=['All', 'Profitable', 'Marginal', 'Loss', 'No Data'])
        show_menu.pack(side='left', padx=(0, 4))
        show_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())

        # \u2500\u2500 Treeview \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill='both', expand=True)
        cols = ('category', 'item',
                'jita_lc', 'amarr_lc', 'dodixie_lc', 'rens_lc', 'hek_lc',
                'best_hub', 'contract', 'margin', 'dev')
        self.import_tree = ttk.Treeview(tree_frame, columns=cols,
                                        show='headings', selectmode='browse')
        for col_id, heading, width, anchor in [
            ('category',   'Category',    110, 'w'),
            ('item',       'Item',         200, 'w'),
            ('jita_lc',    'Jita LC',      110, 'e'),
            ('amarr_lc',   'Amarr LC',     110, 'e'),
            ('dodixie_lc', 'Dodixie LC',   110, 'e'),
            ('rens_lc',    'Rens LC',      110, 'e'),
            ('hek_lc',     'Hek LC',       110, 'e'),
            ('best_hub',   'Best Hub',      80, 'center'),
            ('contract',   'Contract',     110, 'e'),
            ('margin',     'Margin %',      75, 'e'),
            ('dev',        'vs 7d Avg %',   90, 'e'),
        ]:
            self.import_tree.heading(col_id, text=heading,
                                     command=lambda c=col_id: self._sort_import_tree(c))
            self.import_tree.column(col_id, width=width, anchor=anchor,
                                    stretch=(col_id == 'item'))
        self.import_tree.tag_configure('profitable', foreground='#00ff88')
        self.import_tree.tag_configure('marginal',   foreground='#ffcc44')
        self.import_tree.tag_configure('loss',       foreground='#ff4444')
        self.import_tree.tag_configure('nodata',     foreground='#446688')
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.import_tree.yview)
        self.import_tree.configure(yscrollcommand=vsb.set)
        self.import_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        ttk.Label(outer,
                  text="Landed = hub price \u00d7 buy% + broker + HS freight + null freight.  "
                       "Contract = refine value per unit at JBV \u00d7 sell%.  "
                       "Margin = (Contract \u2212 Landed) / Landed \u00d7 100.",
                  foreground='#2a5070', background='#0d1117',
                  font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 0))

        self._import_all_rows = []
        self._import_sort_col = 'margin'
        self._import_sort_asc = False

'''

NEW_LOAD = '''\
    def load_import_data(self):
        """Query market_snapshots for ore items and compute multi-hub landed costs."""
        try:
            buy_pct    = float(self.hub_buy_pct_var.get()) / 100.0
            broker_pct = (float(self.hub_broker_var.get()) / 100.0
                          if self.hub_buy_type_var.get() == 'Buy Orders' else 0.0)
            null_ism3  = float(self.hub_null_ism3_var.get())
            null_isj   = float(self.hub_null_isj_var.get())
            null_j     = int(float(self.hub_null_j_var.get()))
            null_coll  = float(self.hub_null_coll_var.get()) / 100.0
            hs_ism3    = float(self.hub_hs_ism3_var.get())
            hs_isj     = float(self.hub_hs_isj_var.get())
            hs_coll    = float(self.hub_hs_coll_var.get()) / 100.0
            refine_eff = float(self.hub_refine_var.get()) / 100.0
        except ValueError:
            messagebox.showerror("Invalid Input", "All parameters must be numeric.")
            return

        buy_type = self.hub_buy_type_var.get()

        HUB_STATION = {
            'jita': 60003760, 'amarr': 60008494, 'dodixie': 60011866,
            'rens': 60004588, 'hek':   60005686,
        }
        hubs_cfg = {}
        for hub in HUB_STATION:
            hv = self._hub_vars.get(hub, {})
            try:
                j1 = int(float(hv['j1'].get())) if 'j1' in hv else 0
                j2 = int(float(hv['j2'].get())) if 'j2' in hv else 0
            except (ValueError, AttributeError):
                j1, j2 = 0, 0
            hubs_cfg[hub] = {
                'j1':   j1,
                'j2':   j2,
                'leg2': hv['leg2'].get() if 'leg2' in hv else False,
                'en':   hv['en'].get()   if 'en'   in hv else True,
            }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Phase 1: ore/ice/moon ore items only
        cursor.execute("""
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
        """)
        rows = cursor.fetchall()

        cursor.execute("SELECT MAX(fetched_at) FROM market_snapshots")
        snap_ts = cursor.fetchone()[0] or '\u2014'

        # Refine data: yields + portion size
        ore_type_ids = [r[0] for r in rows]
        ore_yields   = {}
        ore_portion  = {}
        mineral_jbv  = {}
        if ore_type_ids:
            import json as _json
            ph = ','.join('?' * len(ore_type_ids))
            cursor.execute(
                f'SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({ph})',
                ore_type_ids)
            ore_yields = {r[0]: _json.loads(r[1]) for r in cursor.fetchall()}
            cursor.execute(
                f'SELECT type_id, portion_size FROM inv_types WHERE type_id IN ({ph})',
                ore_type_ids)
            ore_portion = {r[0]: r[1] for r in cursor.fetchall()}
            # Mineral / ice product / moon material JBV at Jita (from market_snapshots)
            mat_ids = list({m['materialTypeID']
                            for ylds in ore_yields.values() for m in ylds})
            if mat_ids:
                mat_ph = ','.join('?' * len(mat_ids))
                cursor.execute("""
                    SELECT type_id, best_buy
                    FROM market_snapshots ms
                    WHERE station_id=60003760 AND type_id IN (%s)
                      AND fetched_at = (
                          SELECT MAX(fetched_at) FROM market_snapshots
                          WHERE station_id=60003760 AND type_id=ms.type_id)
                """ % mat_ph, mat_ids)
                mineral_jbv = {r[0]: r[1] for r in cursor.fetchall()
                               if r[1] and r[1] > 0}

        # N-day avg per hub for vs-avg dev column
        try:
            dev_days = int(float(self.hub_dev_days_var.get()))
        except (ValueError, AttributeError):
            dev_days = 7
        cursor.execute(f"""
            SELECT type_id, station_id, AVG(best_sell)
            FROM market_snapshots
            WHERE fetched_at >= datetime('now', '-{dev_days} days')
              AND station_id IN (60003760,60008494,60011866,60004588,60005686)
              AND best_sell IS NOT NULL
            GROUP BY type_id, station_id
        """)
        avg_prices = {}
        for tid2, sid2, avg2 in cursor.fetchall():
            avg_prices[(tid2, sid2)] = avg2

        conn.close()

        cat_map = {
            'standard_ore': 'Standard Ore',
            'ice_ore':      'Ice Ore',
            'moon_ore':     'Moon Ore',
        }
        # Column positions in query result:
        #  0=tid, 1=name, 2=cat, 3=vol, 4=disp_ord
        #  5=jita_buy, 6=jita_sell, 7=amarr_sell, 8=dodixie_sell, 9=rens_sell, 10=hek_sell
        HUB_NAMES    = ['jita', 'amarr', 'dodixie', 'rens', 'hek']
        HUB_SELL_COL = {'jita': 6, 'amarr': 7, 'dodixie': 8, 'rens': 9, 'hek': 10}

        self._import_all_rows = []
        best_margin  = None
        worst_margin = None
        profitable_n = 0

        for row in rows:
            tid      = row[0]
            name     = row[1]
            category = row[2]
            volume   = row[3]
            cat_label = cat_map.get(category, category.replace('_', ' ').title())

            # Raw price at each hub (buy order price for Jita if buy-order mode)
            hub_raw = {}
            for hub in HUB_NAMES:
                sell = row[HUB_SELL_COL[hub]]
                if hub == 'jita' and buy_type == 'Buy Orders':
                    jbuy = row[5]  # jita best_buy
                    hub_raw[hub] = jbuy if jbuy else sell
                else:
                    hub_raw[hub] = sell

            # Landed cost per enabled hub
            landed = {}
            for hub in HUB_NAMES:
                cfg = hubs_cfg[hub]
                if not cfg['en']:
                    continue
                raw = hub_raw[hub]
                if raw is None:
                    continue
                buy_price = raw * buy_pct
                broker    = buy_price * broker_pct
                null_cost = null_ism3 * volume + null_isj * null_j + null_coll * buy_price
                if hub == 'jita':
                    lc = buy_price + broker + null_cost
                else:
                    hub_jumps = cfg['j1'] + (cfg['j2'] if cfg['leg2'] else 0)
                    hs_cost   = hs_ism3 * volume + hs_isj * hub_jumps + hs_coll * buy_price
                    lc = buy_price + broker + hs_cost + null_cost
                landed[hub] = lc

            jita_lc    = landed.get('jita')
            amarr_lc   = landed.get('amarr')
            dodixie_lc = landed.get('dodixie')
            rens_lc    = landed.get('rens')
            hek_lc     = landed.get('hek')

            if not landed:
                self._import_all_rows.append({
                    'type_id':    tid,
                    'category':   cat_label,
                    'item':       name,
                    'jita_lc':    None, 'amarr_lc':   None, 'dodixie_lc': None,
                    'rens_lc':    None, 'hek_lc':     None,
                    'best_hub':   '\u2014',
                    'best_lc':    None,
                    'contract':   None,
                    'margin':     None,
                    'dev':        None,
                    'tag':        'nodata',
                })
                continue

            best_hub = min(landed, key=lambda h: landed[h])
            best_lc  = landed[best_hub]

            # Refine value: sum of (yield_qty \u00d7 refine_eff \u00d7 mineral_jbv \u00d7 sell_pct)
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
                # Mineral prices not yet fetched \u2014 show as nodata with landed costs
                self._import_all_rows.append({
                    'type_id':    tid,
                    'category':   cat_label,
                    'item':       name,
                    'jita_lc':    jita_lc,   'amarr_lc':   amarr_lc,
                    'dodixie_lc': dodixie_lc, 'rens_lc':   rens_lc,
                    'hek_lc':     hek_lc,
                    'best_hub':   best_hub.title(),
                    'best_lc':    best_lc,
                    'contract':   None,
                    'margin':     None,
                    'dev':        None,
                    'tag':        'nodata',
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
                'jita_lc':    jita_lc,    'amarr_lc':   amarr_lc,
                'dodixie_lc': dodixie_lc, 'rens_lc':    rens_lc,
                'hek_lc':     hek_lc,
                'best_hub':   best_hub.title(),
                'best_lc':    best_lc,
                'contract':   contract,
                'margin':     margin,
                'dev':        dev_pct,
                'tag':        tag,
            })

        total = len(self._import_all_rows)
        self._hub_import_summary_labels['total'].configure(
            text=str(total), foreground='#00ffff')
        self._hub_import_summary_labels['profitable'].configure(
            text=str(profitable_n),
            foreground='#00ff88' if profitable_n > 0 else '#ffcc44')
        self._hub_import_summary_labels['best_margin'].configure(
            text=(f'{best_margin:+.1f}%' if best_margin is not None else '\u2014'),
            foreground='#00ff88' if (best_margin or 0) >= 5 else '#ffcc44')
        self._hub_import_summary_labels['worst_margin'].configure(
            text=(f'{worst_margin:+.1f}%' if worst_margin is not None else '\u2014'),
            foreground='#ff4444' if (worst_margin or 0) < 0 else '#ffcc44')

        self._hub_price_age_lbl.configure(
            text=f'Prices: {snap_ts[:16] if len(snap_ts) > 16 else snap_ts}',
            foreground='#00ff88' if snap_ts != '\u2014' else '#ffcc44')
        self._filter_import_tree()
        self.update_status(
            f"Multi-hub import analysis updated \u2014 "
            f"{snap_ts[:16] if len(snap_ts) > 16 else snap_ts}")

'''

NEW_CAT = '''\
    def _import_cat_changed(self):
        self._filter_import_tree()

'''

NEW_FILTER = '''\
    def _filter_import_tree(self):
        search     = self.hub_import_search_var.get().lower()
        cat_filter = self.import_cat_var.get()
        show       = self.import_show_var.get()

        show_map = {
            'Profitable': {'profitable'},
            'Marginal':   {'marginal'},
            'Loss':       {'loss'},
            'No Data':    {'nodata'},
        }
        show_tags = show_map.get(show)  # None means show All

        filtered = [
            r for r in self._import_all_rows
            if (not search or search in r['item'].lower())
            and (cat_filter == 'All' or r['category'] == cat_filter)
            and (show_tags is None or r['tag'] in show_tags)
        ]

        col     = self._import_sort_col
        reverse = not self._import_sort_asc

        def _key(r):
            v = r.get(col)
            if v is None:
                return (1e18 if not reverse else -1e18)
            if isinstance(v, (int, float)):
                return v
            return (v or '').lower()

        filtered.sort(key=_key, reverse=reverse)

        def _isk(v):
            return f'{v:,.0f}' if v is not None else '\u2014'

        self.import_tree.delete(*self.import_tree.get_children())
        for r in filtered:
            ct  = r.get('contract')
            mg  = r.get('margin')
            dev = r.get('dev')
            self.import_tree.insert('', 'end', tags=(r['tag'],), values=(
                r['category'],
                r['item'],
                _isk(r.get('jita_lc')),
                _isk(r.get('amarr_lc')),
                _isk(r.get('dodixie_lc')),
                _isk(r.get('rens_lc')),
                _isk(r.get('hek_lc')),
                r['best_hub'],
                f'{ct:,.0f}' if ct is not None else '\u2014',
                f'{mg:+.1f}%' if mg is not None else '\u2014',
                f'{dev:+.1f}%' if dev is not None else '\u2014',
            ))

'''

NEW_SORT = '''\
    def _sort_import_tree(self, col):
        if self._import_sort_col == col:
            self._import_sort_asc = not self._import_sort_asc
        else:
            self._import_sort_col = col
            self._import_sort_asc = col in ('category', 'item', 'best_hub')
        self._filter_import_tree()

'''

# ── Assemble new file ───────────────────────────────────────────────────────────

# Section 1: everything before build_import_tab
sec1 = ''.join(lines[:pos_build])

# Section 2: helper methods after build_import_tab, preserved unchanged
# (_hub_import_broker_toggle, _build_hub_sell_overrides, _hub_sell_item_widget,
#  _hub_sell_reset_all, _run_hub_fetch, etc.)
sec2 = ''.join(lines[pos_broker:pos_load])

# Section 3: everything from sort_end (ORE IMPORT ANALYSIS section) to EOF
sec3 = ''.join(lines[sort_end:])

new_content = sec1 + NEW_BUILD + sec2 + NEW_LOAD + NEW_CAT + NEW_FILTER + NEW_SORT + sec3

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Patch applied successfully.")
