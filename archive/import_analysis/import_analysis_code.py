# ARCHIVED: Import Analysis tab code from admin_dashboard.py
# Tab registration was at lines 214-217
# Methods were at lines 2968-3435

# --- TAB REGISTRATION ---
        # Tab 6: Import Analysis
        self.import_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.import_frame, text='  Import Analysis  ')
        self.build_import_tab()

# --- METHODS ---
    def build_import_tab(self):
        """Build the Import Analysis tab (Jita -> null-sec staging, sold via contract)."""
        outer = ttk.Frame(self.import_frame)
        outer.pack(fill='both', expand=True, padx=15, pady=(15, 10))

        ttk.Label(outer,
                  text="Model profitability of importing items from Jita to null-sec staging, purchased via market and sold via contract.",
                  style='SubHeader.TLabel').pack(anchor='w', pady=(0, 8))

        # ── Flow indicator ───────────────────────────────────────────────────
        flow_frame = ttk.Frame(outer)
        flow_frame.pack(fill='x', pady=(0, 10))
        for widget_type, text, fg, bg in [
            ('node',  'JITA\nBuy from market',                  '#00ffff', '#0a2030'),
            ('arrow', '  >  ',                                   '#1a5060', '#0d1117'),
            ('cost',  'SHIPPING + COLLATERAL\nHauler contract',  '#ffcc44', '#0d1a00'),
            ('arrow', '  >  ',                                   '#1a5060', '#0d1117'),
            ('node',  'NULL-SEC STAGING\nSell via contract',     '#00ff88', '#0a2030'),
        ]:
            tk.Label(flow_frame, text=text, background=bg, foreground=fg,
                     font=('Segoe UI', 10, 'bold' if widget_type != 'arrow' else 'normal'),
                     relief=('solid' if widget_type != 'arrow' else 'flat'),
                     borderwidth=(1 if widget_type != 'arrow' else 0),
                     padx=(10 if widget_type != 'arrow' else 0),
                     pady=(5 if widget_type != 'arrow' else 0)).pack(side='left')

        # ── Parameter panel ──────────────────────────────────────────────────
        param_card = ttk.Frame(outer, style='Card.TFrame')
        param_card.pack(fill='x', pady=(0, 10))
        param_inner = ttk.Frame(param_card, style='Card.TFrame')
        param_inner.pack(fill='x', padx=12, pady=10)

        lbl_cfg = dict(background='#0a2030', foreground='#88d0e8', font=('Segoe UI', 10))
        hdr_cfg = dict(background='#0a2030', font=('Segoe UI', 9, 'bold'))

        tk.Label(param_inner, text="BUY SIDE  (Jita market, fees may apply)",
                 foreground='#66d9ff', **hdr_cfg).grid(
                 row=0, column=0, columnspan=3, sticky='w', padx=(0, 20), pady=(0, 6))
        tk.Label(param_inner, text="LOGISTICS",
                 foreground='#ffcc44', **hdr_cfg).grid(
                 row=0, column=3, columnspan=3, sticky='w', padx=(16, 20), pady=(0, 6))
        tk.Label(param_inner, text="SELL SIDE  (contract, no tax/broker)",
                 foreground='#00ff88', **hdr_cfg).grid(
                 row=0, column=6, columnspan=3, sticky='w', padx=(16, 0), pady=(0, 6))

        tk.Frame(param_inner, background='#1a3040', height=1).grid(
            row=1, column=0, columnspan=9, sticky='ew', pady=(0, 8))

        # Buy side
        tk.Label(param_inner, text="Buy From", **lbl_cfg).grid(
            row=2, column=0, sticky='w', padx=(0, 4))
        self.import_buy_var = tk.StringVar(value=self._get_config('import_param_buy_basis', 'JSV  (instant, from sell orders)'))
        self.import_buy_var.trace_add('write', lambda *_: self._set_config('import_param_buy_basis', self.import_buy_var.get()))
        ttk.Combobox(param_inner, textvariable=self.import_buy_var, width=22,
                     values=['JSV  (instant, from sell orders)', 'JBV  (place buy order)'],
                     state='readonly').grid(row=3, column=0, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Buy % of Basis", **lbl_cfg).grid(
            row=2, column=1, sticky='w', padx=(0, 4))
        self.import_buy_pct_var = tk.StringVar(value=self._get_config('import_param_buy_pct', '100'))
        self.import_buy_pct_var.trace_add('write', lambda *_: self._set_config('import_param_buy_pct', self.import_buy_pct_var.get()))
        ttk.Entry(param_inner, textvariable=self.import_buy_pct_var, width=8).grid(
            row=3, column=1, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Broker Fee %", **lbl_cfg).grid(
            row=2, column=2, sticky='w', padx=(0, 4))
        self.import_broker_var = tk.StringVar(value=self._get_config('import_param_broker_pct', '0.0'))
        self.import_broker_var.trace_add('write', lambda *_: self._set_config('import_param_broker_pct', self.import_broker_var.get()))
        ttk.Entry(param_inner, textvariable=self.import_broker_var, width=8).grid(
            row=3, column=2, sticky='w', padx=(0, 20))

        # Logistics
        tk.Frame(param_inner, background='#1a3040', width=1).grid(
            row=2, column=3, rowspan=2, sticky='ns', padx=(0, 12))
        tk.Label(param_inner, text="Shipping (ISK/m\u00b3)", **lbl_cfg).grid(
            row=2, column=4, sticky='w', padx=(0, 4))
        self.import_ship_var = tk.StringVar(value=self._get_config('import_param_ship_rate', '125'))
        self.import_ship_var.trace_add('write', lambda *_: self._set_config('import_param_ship_rate', self.import_ship_var.get()))
        ttk.Entry(param_inner, textvariable=self.import_ship_var, width=10).grid(
            row=3, column=4, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Collateral %", **lbl_cfg).grid(
            row=2, column=5, sticky='w', padx=(0, 4))
        self.import_collat_var = tk.StringVar(value=self._get_config('import_param_collat_pct', '1.0'))
        self.import_collat_var.trace_add('write', lambda *_: self._set_config('import_param_collat_pct', self.import_collat_var.get()))
        ttk.Entry(param_inner, textvariable=self.import_collat_var, width=8).grid(
            row=3, column=5, sticky='w', padx=(0, 20))

        # Sell side
        tk.Frame(param_inner, background='#1a3040', width=1).grid(
            row=2, column=6, rowspan=2, sticky='ns', padx=(0, 12))
        tk.Label(param_inner, text="Price Reference", **lbl_cfg).grid(
            row=2, column=7, sticky='w', padx=(0, 4))
        self.import_sell_ref_var = tk.StringVar(value=self._get_config('import_param_sell_ref', 'JSV'))
        self.import_sell_ref_var.trace_add('write', lambda *_: self._set_config('import_param_sell_ref', self.import_sell_ref_var.get()))
        ttk.Combobox(param_inner, textvariable=self.import_sell_ref_var,
                     width=14, values=['JSV', 'Jita Split', 'JBV'],
                     state='readonly').grid(row=3, column=7, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Sell Markup %", **lbl_cfg).grid(
            row=2, column=8, sticky='w', padx=(0, 4))
        self.import_markup_var = tk.StringVar(value=self._get_config('import_param_markup_pct', '115'))
        self.import_markup_var.trace_add('write', lambda *_: self._set_config('import_param_markup_pct', self.import_markup_var.get()))
        ttk.Entry(param_inner, textvariable=self.import_markup_var, width=8).grid(
            row=3, column=8, sticky='w', padx=(0, 12))

        ttk.Button(param_inner, text='\u27f3  Recalculate', style='Action.TButton',
                   command=self.load_import_data).grid(
                   row=3, column=9, sticky='w', padx=(4, 0))

        # Quick scenarios
        scenario_frame = ttk.Frame(param_card, style='Card.TFrame')
        scenario_frame.pack(fill='x', padx=12, pady=(0, 10))
        tk.Label(scenario_frame, text="Quick:", **lbl_cfg).pack(side='left', padx=(0, 8))
        for label, buy, pct, broker, ref, markup in [
            ('JSV + 15%  (baseline)',    'JSV  (instant, from sell orders)', '100', '0.0', 'JSV', '115'),
            ('JSV + 20%  (premium)',     'JSV  (instant, from sell orders)', '100', '0.0', 'JSV', '120'),
            ('JSV + 10%  (competitive)', 'JSV  (instant, from sell orders)', '100', '0.0', 'JSV', '110'),
            ('JBV order + 15%',          'JBV  (place buy order)',           '100', '3.0', 'JSV', '115'),
        ]:
            ttk.Button(scenario_frame, text=label, style='Action.TButton',
                       command=lambda b=buy, p=pct, br=broker, r=ref, m=markup:
                           self._apply_import_scenario(b, p, br, r, m)
                       ).pack(side='left', padx=3)

        # Summary cards
        self.import_summary_frame = ttk.Frame(outer)
        self.import_summary_frame.pack(fill='x', pady=(0, 8))
        self._import_summary_labels = {}
        for key, title in [('scenario', 'SCENARIO'), ('total', 'ITEMS ANALYSED'),
                            ('worth', 'WORTH IMPORTING'), ('marginal', 'MARGINAL'),
                            ('avoid', 'AVOID'), ('avg_margin', 'AVG MARGIN')]:
            card = ttk.Frame(self.import_summary_frame, style='Card.TFrame')
            card.pack(side='left', fill='both', expand=True, padx=3)
            tk.Label(card, text=title, background='#0a2030', foreground='#66d9ff',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=8, pady=(6, 0))
            val_lbl = tk.Label(card, text='\u2014', background='#0a2030',
                               foreground='#00ffff', font=('Segoe UI', 12, 'bold'))
            val_lbl.pack(anchor='w', padx=8, pady=(0, 6))
            self._import_summary_labels[key] = val_lbl

        # Filter row
        filter_frame = ttk.Frame(outer)
        filter_frame.pack(fill='x', pady=(0, 6))
        ttk.Label(filter_frame, text="Search:").pack(side='left', padx=(0, 4))
        self.import_search_var = tk.StringVar()
        self.import_search_var.trace_add('write', lambda *_: self._filter_import_tree())
        ttk.Entry(filter_frame, textvariable=self.import_search_var, width=18).pack(
            side='left', padx=(0, 12))
        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 4))
        self.import_cat_var = tk.StringVar(value='All')
        import_cat_menu = ttk.Combobox(filter_frame, textvariable=self.import_cat_var,
                                       width=20, state='readonly',
                                       values=['All', 'Minerals', 'Ice Products',
                                               'PI Materials', 'Moon Materials',
                                               'Salvaged Materials'])
        import_cat_menu.pack(side='left', padx=(0, 12))
        import_cat_menu.bind('<<ComboboxSelected>>', lambda _: self._import_cat_changed())
        ttk.Label(filter_frame, text="Subcategory:").pack(side='left', padx=(0, 4))
        self.import_sub_var = tk.StringVar(value='All Subcategories')
        self.import_sub_menu = ttk.Combobox(filter_frame, textvariable=self.import_sub_var,
                                            width=18, state='readonly',
                                            values=['All Subcategories'])
        self.import_sub_menu.pack(side='left', padx=(0, 12))
        self.import_sub_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())
        ttk.Label(filter_frame, text="Show:").pack(side='left', padx=(0, 4))
        self.import_show_var = tk.StringVar(value='Profitable')
        show_menu = ttk.Combobox(filter_frame, textvariable=self.import_show_var,
                                 width=16, state='readonly',
                                 values=['All', 'Profitable', 'Marginal', 'Avoid'])
        show_menu.pack(side='left', padx=(0, 4))
        show_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())

        # Treeview
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill='both', expand=True)
        cols = ('category', 'item', 'volume', 'buy_cost', 'ship_collat',
                'total_cost', 'contract_price', 'profit', 'margin', 'verdict')
        self.import_tree = ttk.Treeview(tree_frame, columns=cols,
                                        show='headings', selectmode='browse')
        for col, heading, width, anchor in [
            ('category',       'Category',       120, 'w'),
            ('item',           'Item',            195, 'w'),
            ('volume',         'Vol (m\u00b3)',    70, 'e'),
            ('buy_cost',       'Buy Cost',        110, 'e'),
            ('ship_collat',    'Ship+Collat',     105, 'e'),
            ('total_cost',     'Total Landed',    110, 'e'),
            ('contract_price', 'Contract Price',  115, 'e'),
            ('profit',         'Profit / unit',   105, 'e'),
            ('margin',         'Margin',           75, 'e'),
            ('verdict',        'Verdict',          90, 'center'),
        ]:
            self.import_tree.heading(col, text=heading,
                                     command=lambda c=col: self._sort_import_tree(c))
            self.import_tree.column(col, width=width, anchor=anchor,
                                    stretch=(col == 'item'))
        self.import_tree.tag_configure('great',    foreground='#00ff88')
        self.import_tree.tag_configure('good',     foreground='#88ff66')
        self.import_tree.tag_configure('marginal', foreground='#ffcc44')
        self.import_tree.tag_configure('avoid',    foreground='#ff6666')
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.import_tree.yview)
        self.import_tree.configure(yscrollcommand=vsb.set)
        self.import_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        ttk.Label(outer,
                  text="Buy cost = Jita price x buy %.  Broker fee only if placing buy orders.  "
                       "No buyer-side sales tax (paid by seller).  "
                       "Contract price = reference x markup %.  No tax/broker on contract sales.  "
                       "Margin = (Contract - Landed) / Contract.",
                  foreground='#2a5070', background='#0d1117',
                  font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 0))

        self._import_all_rows = []
        self._import_sort_col = 'margin'
        self._import_sort_asc = False

    def _apply_import_scenario(self, buy, pct, broker, ref, markup):
        self.import_buy_var.set(buy)
        self.import_buy_pct_var.set(pct)
        self.import_broker_var.set(broker)
        self.import_sell_ref_var.set(ref)
        self.import_markup_var.set(markup)
        self.load_import_data()

    def _import_price_for_basis(self, basis, best_buy, best_sell):
        key = basis.split()[0]
        if key == 'JSV':
            return best_sell
        elif key == 'JBV':
            return best_buy or best_sell   # fall back to sell when no buy orders exist
        return ((best_buy or best_sell) + best_sell) / 2

    def load_import_data(self):
        """Query DB and populate the import analysis treeview."""
        try:
            ship_rate  = float(self.import_ship_var.get())
            collat_pct = float(self.import_collat_var.get()) / 100.0
            buy_pct    = float(self.import_buy_pct_var.get()) / 100.0
            broker_pct = float(self.import_broker_var.get()) / 100.0
            markup_pct = float(self.import_markup_var.get()) / 100.0
        except ValueError:
            messagebox.showerror("Invalid Input", "All parameters must be numeric.")
            return

        buy_basis        = self.import_buy_var.get()
        sell_ref         = self.import_sell_ref_var.get()
        effective_broker = broker_pct if 'JBV' in buy_basis else 0.0

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT it.type_name, tmi.category, it.volume, mps.best_buy, mps.best_sell,
                   tmi.display_order, it.market_group_id
            FROM tracked_market_items tmi
            JOIN inv_types it               ON tmi.type_id = it.type_id
            JOIN market_price_snapshots mps ON tmi.type_id = mps.type_id
            WHERE mps.timestamp = (
                SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id = tmi.type_id
            )
              AND mps.best_sell > 0
            ORDER BY tmi.category, it.type_name
        """)
        rows = cursor.fetchall()
        cursor.execute("SELECT MAX(timestamp) FROM market_price_snapshots")
        snap_ts = cursor.fetchone()[0] or '\u2014'
        conn.close()

        cat_map = {
            'minerals': 'Minerals', 'ice_products': 'Ice Products',
            'moon_materials': 'Moon Materials', 'pi_materials': 'PI Materials',
            'salvaged_materials': 'Salvaged Materials',
        }
        _pi_sub  = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}
        def _sub(cat, disp, mg):
            if cat == 'ice_products':
                if disp <= 8:  return 'Fuel Blocks'
                if disp <= 11: return 'Refined Ice'
                return 'Isotopes'
            if cat == 'moon_materials':
                if disp < 100:  return 'Raw'
                if disp < 200:  return 'Processed'
                return 'Advanced'
            if cat == 'pi_materials':
                return _pi_sub.get(mg, '')
            if cat == 'salvaged_materials':
                if disp <= 9:  return 'Common'
                if disp <= 21: return 'Uncommon'
                if disp <= 32: return 'Rare'
                if disp <= 42: return 'Very Rare'
                return 'Rogue Drone'
            return ''

        self._import_all_rows = []
        counts = {'great': 0, 'good': 0, 'marginal': 0, 'avoid': 0}
        margin_sum, margin_n = 0.0, 0

        for name, category, volume, best_buy, best_sell, disp_ord, mgroup in rows:
            subcategory = _sub(category, disp_ord or 0, mgroup or 0)
            raw_buy        = self._import_price_for_basis(buy_basis, best_buy, best_sell)
            buy_cost       = raw_buy * buy_pct + raw_buy * effective_broker
            ship_cost      = volume * ship_rate
            collat         = buy_cost * collat_pct
            total_cost     = buy_cost + ship_cost + collat
            ref_price      = self._import_price_for_basis(sell_ref, best_buy, best_sell)
            contract_price = ref_price * markup_pct
            profit         = contract_price - total_cost
            margin         = (profit / contract_price * 100) if contract_price > 0 else 0

            if margin >= 5:
                tag, verdict = 'great',    '\u2713 Import'
                counts['great'] += 1
            elif margin >= 1:
                tag, verdict = 'good',     '\u2713 Import'
                counts['good'] += 1
            elif margin >= 0:
                tag, verdict = 'marginal', '~ Marginal'
                counts['marginal'] += 1
            else:
                tag, verdict = 'avoid',    '\u2717 Avoid'
                counts['avoid'] += 1

            margin_sum += margin
            margin_n   += 1

            self._import_all_rows.append({
                'category':       cat_map.get(category, category.replace('_', ' ').title()),
                'subcategory':    subcategory,
                'item':           name,
                'volume':         volume,
                'buy_cost':       buy_cost,
                'ship_collat':    ship_cost + collat,
                'total_cost':     total_cost,
                'contract_price': contract_price,
                'profit':         profit,
                'margin':         margin,
                'verdict':        verdict,
                'tag':            tag,
            })

        total = len(self._import_all_rows)
        worth = counts['great'] + counts['good']
        avg   = (margin_sum / margin_n) if margin_n else 0
        buy_label = 'JSV' if 'JSV' in buy_basis else 'JBV'
        self._import_summary_labels['scenario'].configure(
            text=f"Buy {buy_label} \u2192 Sell {markup_pct*100:.0f}% {sell_ref}",
            foreground='#66d9ff')
        self._import_summary_labels['total'].configure(
            text=str(total), foreground='#00ffff')
        self._import_summary_labels['worth'].configure(
            text=str(worth), foreground='#00ff88')
        self._import_summary_labels['marginal'].configure(
            text=str(counts['marginal']), foreground='#ffcc44')
        self._import_summary_labels['avoid'].configure(
            text=str(counts['avoid']), foreground='#ff6666')
        self._import_summary_labels['avg_margin'].configure(
            text=f"{avg:.1f}%",
            foreground='#00ff88' if avg >= 5 else '#ffcc44')

        self._filter_import_tree()
        self.update_status(
            f"Import analysis updated \u2014 {snap_ts[:16] if len(snap_ts) > 16 else snap_ts}")

    def _import_cat_changed(self):
        cat = self.import_cat_var.get()
        sub_opts = {
            'All':                ['All Subcategories'],
            'Minerals':           ['All Subcategories'],
            'Ice Products':       ['All Subcategories', 'Fuel Blocks', 'Refined Ice', 'Isotopes'],
            'PI Materials':       ['All Subcategories', 'P1', 'P2', 'P3', 'P4'],
            'Moon Materials':     ['All Subcategories', 'Raw', 'Processed', 'Advanced'],
            'Salvaged Materials': ['All Subcategories', 'Common', 'Uncommon', 'Rare', 'Very Rare', 'Rogue Drone'],
        }.get(cat, ['All Subcategories'])
        self.import_sub_menu['values'] = sub_opts
        self.import_sub_var.set('All Subcategories')
        self._filter_import_tree()

    def _filter_import_tree(self):
        search     = self.import_search_var.get().lower()
        cat_filter = self.import_cat_var.get()
        sub_filter = self.import_sub_var.get()
        show       = self.import_show_var.get()
        filtered   = [r for r in self._import_all_rows
                      if (not search or search in r['item'].lower())
                      and (cat_filter == 'All' or r['category'] == cat_filter)
                      and (sub_filter == 'All Subcategories' or r['subcategory'] == sub_filter)
                      and (show == 'All'
                           or (show == 'Profitable' and r['tag'] in ('great', 'good'))
                           or (show == 'Marginal'   and r['tag'] == 'marginal')
                           or (show == 'Avoid'      and r['tag'] == 'avoid'))]

        col     = self._import_sort_col
        reverse = not self._import_sort_asc
        filtered.sort(key=lambda r: r[col] if isinstance(r[col], (int, float))
                      else r[col].lower(), reverse=reverse)

        self.import_tree.delete(*self.import_tree.get_children())
        for row in filtered:
            self.import_tree.insert('', 'end', tags=(row['tag'],), values=(
                row['category'], row['item'],
                f"{row['volume']:.2f}",
                f"{row['buy_cost']:,.0f}",
                f"{row['ship_collat']:,.0f}",
                f"{row['total_cost']:,.0f}",
                f"{row['contract_price']:,.0f}",
                f"{row['profit']:,.0f}",
                f"{row['margin']:.1f}%",
                row['verdict'],
            ))

    def _sort_import_tree(self, col):
        if self._import_sort_col == col:
            self._import_sort_asc = not self._import_sort_asc
        else:
            self._import_sort_col = col
            self._import_sort_asc = col in ('category', 'item')
        self._filter_import_tree()

    # ===== ORE IMPORT ANALYSIS =====

    # Product definitions: (type_id, display_name, config_default)
    _ORE_MINERALS = [
        (34,    'Tritanium',  '95'),
        (35,    'Pyerite',   '95'),
        (36,    'Mexallon',  '98'),
        (37,    'Isogen',   '100'),
        (38,    'Nocxium',  '105'),
        (39,    'Zydrine',  '110'),
        (40,    'Megacyte', '115'),
        (11399, 'Morphite', '120'),
    ]
    _ORE_ICE_PRODUCTS = [
        (16272, 'Heavy Water',        '90'),
        (16273, 'Liquid Ozone',       '95'),
        (16274, 'Helium Isotopes',   '100'),
        (16275, 'Strontium Clath.', '100'),
        (17887, 'Oxygen Isotopes',   '100'),
        (17888, 'Nitrogen Isotopes', '100'),
        (17889, 'Hydrogen Isotopes', '100'),
    ]
    _ORE_MOON_MATERIALS = [
        # R4
        (16633, 'Hydrocarbons',      '95',  'R4'),
        (16634, 'Atmo. Gases',       '95',  'R4'),
        (16635, 'Evaporite Dep.',    '95',  'R4'),
        (16636, 'Silicates',         '95',  'R4'),
        # R8
        (16637, 'Tungsten',         '100',  'R8'),
        (16638, 'Titanium',         '100',  'R8'),
        (16639, 'Scandium',         '100',  'R8'),
        (16640, 'Cobalt',           '100',  'R8'),
        # R16
        (16641, 'Chromium',         '105', 'R16'),
        (16642, 'Vanadium',         '105', 'R16'),
        (16643, 'Cadmium',          '105', 'R16'),
        (16644, 'Platinum',         '105', 'R16'),
        # R32
        (16646, 'Mercury',          '110', 'R32'),
        (16647, 'Caesium',          '110', 'R32'),
        (16648, 'Hafnium',          '110', 'R32'),
        (16649, 'Technetium',       '115', 'R32'),
        # R64
        (16650, 'Dysprosium',       '120', 'R64'),
        (16651, 'Neodymium',        '120', 'R64'),
        (16652, 'Promethium',       '125', 'R64'),
        (16653, 'Thulium',          '125', 'R64'),
    ]

