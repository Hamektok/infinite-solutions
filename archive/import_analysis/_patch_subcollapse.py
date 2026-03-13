"""
Patch: Add sub-category collapsibles for Moon Materials and PI Materials.

Changes:
1. build_import_tab() sell price section — Moon Materials (Raw/Processed/Advanced)
   and PI Materials (P1/P2/P3/P4) tiers get their own collapsible sub-sections.
2. _build_moon_material_price_section() in the Ore Import tab — R4–R64 tiers each
   become a collapsible sub-section.
"""
import re, sys, os

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'admin_dashboard.py')

with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1: build_import_tab() — pi_materials and moon_materials sub-collapsibles
# ─────────────────────────────────────────────────────────────────────────────
OLD1 = '''\
            if cat == 'pi_materials':
                tg = _OD()
                for tid, name, disp, mg in items:
                    tg.setdefault(_pi_sub.get(mg, 'Other'), []).append((tid, name))
                for tier in ['P1', 'P2', 'P3', 'P4', 'Other']:
                    if tier not in tg:
                        continue
                    tk.Label(inner, text=f'{tier}:', background='#0a2030',
                             foreground='#ffa01e',
                             font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(4, 0))
                    tf = ttk.Frame(inner, style='Card.TFrame')
                    tf.pack(fill='x')
                    for ci, (t2, n2) in enumerate(tg[tier]):
                        self._hub_sell_item_widget(
                            tf, ci % ITEMS_PER_ROW,
                            (ci // ITEMS_PER_ROW) * 3, t2, n2, ilbl)
            elif cat == 'moon_materials':
                tg = _OD()
                for tid, name, disp, mg in items:
                    tg.setdefault('Raw' if disp < 100 else
                                  'Processed' if disp < 200 else 'Advanced',
                                  []).append((tid, name))
                for tier in ['Raw', 'Processed', 'Advanced']:
                    if tier not in tg:
                        continue
                    tk.Label(inner, text=f'{tier}:', background='#0a2030',
                             foreground='#c850dc',
                             font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(4, 0))
                    tf = ttk.Frame(inner, style='Card.TFrame')
                    tf.pack(fill='x')
                    for ci, (t2, n2) in enumerate(tg[tier]):
                        self._hub_sell_item_widget(
                            tf, ci % ITEMS_PER_ROW,
                            (ci // ITEMS_PER_ROW) * 3, t2, n2, ilbl)'''

NEW1 = '''\
            if cat == 'pi_materials':
                tg = _OD()
                for tid, name, disp, mg in items:
                    tg.setdefault(_pi_sub.get(mg, 'Other'), []).append((tid, name))
                for tier in ['P1', 'P2', 'P3', 'P4', 'Other']:
                    if tier not in tg:
                        continue
                    sub_content = self._make_collapsible_section(
                        inner, tier, '#ffa01e', expanded=False)
                    tf = ttk.Frame(sub_content, style='Card.TFrame')
                    tf.pack(fill='x', pady=(2, 4))
                    for ci, (t2, n2) in enumerate(tg[tier]):
                        self._hub_sell_item_widget(
                            tf, ci % ITEMS_PER_ROW,
                            (ci // ITEMS_PER_ROW) * 3, t2, n2, ilbl)
            elif cat == 'moon_materials':
                tg = _OD()
                for tid, name, disp, mg in items:
                    tg.setdefault('Raw' if disp < 100 else
                                  'Processed' if disp < 200 else 'Advanced',
                                  []).append((tid, name))
                for tier in ['Raw', 'Processed', 'Advanced']:
                    if tier not in tg:
                        continue
                    sub_content = self._make_collapsible_section(
                        inner, tier, '#c850dc', expanded=False)
                    tf = ttk.Frame(sub_content, style='Card.TFrame')
                    tf.pack(fill='x', pady=(2, 4))
                    for ci, (t2, n2) in enumerate(tg[tier]):
                        self._hub_sell_item_widget(
                            tf, ci % ITEMS_PER_ROW,
                            (ci // ITEMS_PER_ROW) * 3, t2, n2, ilbl)'''

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2: _build_moon_material_price_section() — Ore Import tab sub-collapsibles
# ─────────────────────────────────────────────────────────────────────────────
OLD2 = '''\
    def _build_moon_material_price_section(self, parent, expanded=False):
        """Collapsible: Moon Materials (20 inputs, R4-R64 tiers)."""
        content = self._make_collapsible_section(
            parent, 'Moon Materials', '#cc88ff', expanded)
        inner = ttk.Frame(content, style='Card.TFrame')
        inner.pack(padx=16, pady=(4, 6))

        tier_colors = {'R4': '#888888', 'R8': '#00ff88', 'R16': '#44aaff',
                       'R32': '#cc88ff', 'R64': '#ffcc44'}
        tier_labels = {'R4': 'R4 \\u2014 Ubiquitous', 'R8': 'R8 \\u2014 Common',
                       'R16': 'R16 \\u2014 Uncommon', 'R32': 'R32 \\u2014 Rare',
                       'R64': 'R64 \\u2014 Exceptional'}

        grid_row = 0
        current_tier = None
        items_in_row = 0
        for tid, name, default, tier in self._ORE_MOON_MATERIALS:
            if tier != current_tier:
                current_tier = tier
                if items_in_row > 0:
                    grid_row += 1
                    items_in_row = 0
                tk.Label(inner, text=tier_labels[tier],
                         background='#0a2030', foreground=tier_colors[tier],
                         font=('Segoe UI', 8, 'bold')).grid(
                         row=grid_row, column=0, columnspan=8, sticky='w', pady=(6, 2))
                grid_row += 1

            key = f'ore_pct_{tid}'
            var = tk.StringVar(value=self._get_config(key, default))
            var.trace_add('write', lambda *_, k=key, v=var: self._set_config(k, v.get()))
            self.ore_product_pct[tid] = var

            gc = items_in_row * 2
            tk.Label(inner, text=name,
                     background='#0a2030', foreground='#88d0e8',
                     font=('Segoe UI', 9)).grid(row=grid_row, column=gc, padx=(6, 2), sticky='e')
            ttk.Entry(inner, textvariable=var, width=6).grid(
                      row=grid_row, column=gc + 1, padx=(0, 10), sticky='w')

            items_in_row += 1
            if items_in_row >= 4:
                items_in_row = 0
                grid_row += 1'''

NEW2 = '''\
    def _build_moon_material_price_section(self, parent, expanded=False):
        """Collapsible: Moon Materials (20 inputs, R4-R64 tiers, each tier collapsible)."""
        content = self._make_collapsible_section(
            parent, 'Moon Materials', '#cc88ff', expanded)

        tier_colors = {'R4': '#888888', 'R8': '#00ff88', 'R16': '#44aaff',
                       'R32': '#cc88ff', 'R64': '#ffcc44'}
        tier_labels = {'R4': 'R4 \\u2014 Ubiquitous', 'R8': 'R8 \\u2014 Common',
                       'R16': 'R16 \\u2014 Uncommon', 'R32': 'R32 \\u2014 Rare',
                       'R64': 'R64 \\u2014 Exceptional'}

        # Group items by tier (preserving R4/R8/R16/R32/R64 order)
        tier_groups = {}
        tier_order = []
        for tid, name, default, tier in self._ORE_MOON_MATERIALS:
            if tier not in tier_groups:
                tier_groups[tier] = []
                tier_order.append(tier)
            tier_groups[tier].append((tid, name, default))

        for tier in tier_order:
            tier_items = tier_groups[tier]
            sub_content = self._make_collapsible_section(
                content, tier_labels[tier], tier_colors[tier], expanded=False)
            inner = ttk.Frame(sub_content, style='Card.TFrame')
            inner.pack(padx=8, pady=(2, 4))
            lbl_cfg = dict(background='#0a2030', foreground='#88d0e8',
                           font=('Segoe UI', 9))
            for col_i, (tid, name, default) in enumerate(tier_items):
                key = f'ore_pct_{tid}'
                var = tk.StringVar(value=self._get_config(key, default))
                var.trace_add('write', lambda *_, k=key, v=var: self._set_config(k, v.get()))
                self.ore_product_pct[tid] = var
                gc = col_i * 2
                tk.Label(inner, text=name, **lbl_cfg).grid(
                    row=0, column=gc, padx=(6, 2), sticky='e')
                ttk.Entry(inner, textvariable=var, width=6).grid(
                    row=0, column=gc + 1, padx=(0, 10), sticky='w')'''

# ─────────────────────────────────────────────────────────────────────────────
# Apply patches
# ─────────────────────────────────────────────────────────────────────────────
def apply(src, old, new, label):
    # Normalize CRLF → LF for matching, then restore
    src_lf = src.replace('\r\n', '\n')
    old_lf = old.replace('\r\n', '\n')
    new_lf = new.replace('\r\n', '\n')
    if old_lf not in src_lf:
        print(f'FAIL [{label}]: anchor not found')
        sys.exit(1)
    count = src_lf.count(old_lf)
    if count > 1:
        print(f'FAIL [{label}]: anchor found {count} times (not unique)')
        sys.exit(1)
    result = src_lf.replace(old_lf, new_lf, 1)
    # Restore CRLF if original used it
    if '\r\n' in src:
        result = result.replace('\n', '\r\n')
    print(f'OK   [{label}]')
    return result

src = apply(src, OLD1, NEW1, 'build_import_tab pi/moon sub-collapsibles')
src = apply(src, OLD2, NEW2, '_build_moon_material_price_section tier sub-collapsibles')

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print(f'\nPatched: {TARGET}')
