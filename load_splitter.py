"""
load_splitter.py
----------------
Split a cargo list into N value-balanced loads using refine value.
Reads Jita buy prices and volumes from mydatabase.db.

Paste items as copied from EVE inventory: Name [TAB] Quantity
"""

import tkinter as tk
from tkinter import ttk
import sqlite3, os, math, re, json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')

BG     = '#0d1117'
PANEL  = '#111a25'
PANEL2 = '#0a1828'
BORDER = '#1e2535'
FG     = '#d8e0f0'
DIM    = '#5a6880'
ACCENT = '#00d9ff'
GOLD   = '#ffd700'
FONT   = ('Segoe UI', 10)
FONT_B = ('Segoe UI', 10, 'bold')
MONO   = ('Consolas', 10)

LOAD_COLORS = ['#e05050', '#5588e0', '#44cc88', '#e0a030', '#aa44ff', '#00aaff']


class LoadSplitter:
    def __init__(self, root):
        self.root = root
        root.title('Cargo Load Splitter  ·  LX-ZOJ')
        root.geometry('1200x760')
        root.configure(bg=BG)
        root.resizable(True, True)
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Vertical.TScrollbar', background=PANEL, troughcolor=BG,
                        bordercolor=BG, arrowcolor=DIM, relief='flat')
        style.configure('TSeparator', background=BORDER)

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg='#060e18', pady=10)
        hdr.pack(fill='x')
        tk.Frame(hdr, bg=ACCENT, width=3).pack(side='left', fill='y', padx=(14, 0))
        tk.Label(hdr, text='CARGO LOAD SPLITTER', bg='#060e18', fg=GOLD,
                 font=('Segoe UI', 13, 'bold')).pack(side='left', padx=12)
        tk.Label(hdr, text='Split cargo into value-balanced loads using Jita refine value',
                 bg='#060e18', fg=DIM, font=FONT).pack(side='left')

        # ── Body (left + right) ─────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill='both', expand=True)

        # Left panel
        left = tk.Frame(body, bg=PANEL, width=360)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)

        tk.Label(left, text='CARGO LIST', bg=PANEL, fg=ACCENT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=14, pady=(14, 2))
        tk.Label(left, text='Paste items from EVE  (Name [Tab] Quantity)',
                 bg=PANEL, fg=DIM, font=('Segoe UI', 8)).pack(anchor='w', padx=14)

        txt_frame = tk.Frame(left, bg=PANEL)
        txt_frame.pack(fill='both', expand=True, padx=12, pady=(6, 0))
        self.input_text = tk.Text(
            txt_frame, bg=PANEL2, fg=FG, insertbackground=FG,
            font=MONO, relief='flat', wrap='none',
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, bd=0)
        txt_sb = ttk.Scrollbar(txt_frame, orient='vertical',
                               command=self.input_text.yview)
        txt_sb.pack(side='right', fill='y')
        self.input_text.pack(side='left', fill='both', expand=True)
        self.input_text.configure(yscrollcommand=txt_sb.set)

        # Parameters
        sep = tk.Frame(left, bg=BORDER, height=1)
        sep.pack(fill='x', padx=12, pady=(12, 0))
        tk.Label(left, text='PARAMETERS', bg=PANEL, fg=ACCENT,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=14, pady=(10, 4))

        params = tk.Frame(left, bg=PANEL)
        params.pack(fill='x', padx=12)

        self.n_loads_var    = tk.IntVar(value=6)
        self.refine_eff_var = tk.DoubleVar(value=90.63)
        self.refine_fee_var = tk.DoubleVar(value=1.0)

        def param_row(label, var, from_, to, inc, fmt=''):
            row = tk.Frame(params, bg=PANEL)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, bg=PANEL, fg=DIM, font=FONT,
                     width=22, anchor='w').pack(side='left')
            sp = tk.Spinbox(row, from_=from_, to=to, increment=inc,
                            textvariable=var, width=7,
                            bg=PANEL2, fg=ACCENT, buttonbackground=PANEL2,
                            insertbackground=ACCENT, relief='flat', font=FONT)
            sp.pack(side='left', padx=(4, 0))

        param_row('Number of loads:',    self.n_loads_var,    1,   20,  1)
        param_row('Refine efficiency %:', self.refine_eff_var, 0,  100, 0.01)
        param_row('Refine fee %:',        self.refine_fee_var, 0,   10, 0.1)

        sep2 = tk.Frame(left, bg=BORDER, height=1)
        sep2.pack(fill='x', padx=12, pady=(12, 8))

        self.calc_btn = tk.Button(
            left, text='⟳  Calculate Loads',
            bg='#0d2a40', fg=ACCENT, font=FONT_B,
            relief='flat', padx=14, pady=8,
            activebackground='#1a3a50', activeforeground='#44eeff',
            command=self._calculate)
        self.calc_btn.pack(fill='x', padx=12)

        self.status_var = tk.StringVar(value='Paste cargo and click Calculate.')
        tk.Label(left, textvariable=self.status_var, bg=PANEL, fg=DIM,
                 font=('Segoe UI', 8), anchor='w', wraplength=330,
                 justify='left').pack(fill='x', padx=14, pady=(6, 14))

        # Right panel
        right = tk.Frame(body, bg=BG)
        right.pack(side='left', fill='both', expand=True)

        # Summary bar
        self.summary_var = tk.StringVar(value='')
        tk.Label(right, textvariable=self.summary_var,
                 bg='#060e18', fg=DIM, font=('Segoe UI', 9),
                 anchor='w', pady=6, padx=14).pack(fill='x')

        # Scrollable results canvas
        canvas_wrap = tk.Frame(right, bg=BG)
        canvas_wrap.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(canvas_wrap, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_wrap, orient='vertical', command=self.canvas.yview)
        vsb.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self._cwin = self.canvas.create_window((0, 0), window=self.inner,
                                               anchor='nw', tags='inner')
        self.inner.bind('<Configure>',
                        lambda e: self.canvas.configure(
                            scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',
                         lambda e: self.canvas.itemconfig('inner', width=e.width))
        self.canvas.bind_all('<MouseWheel>',
                             lambda e: self.canvas.yview_scroll(
                                 int(-1 * (e.delta / 120)), 'units'))

    # ── DB helpers ─────────────────────────────────────────────────────────────

    def _lookup_db(self, names):
        """Return {name: dict} with volume, jbv, portion_size, materials, mat_prices."""
        conn = sqlite3.connect(DB_PATH)
        ph   = ','.join('?' * len(names))

        rows = conn.execute(
            f'SELECT type_name, type_id, volume, portion_size FROM inv_types WHERE type_name IN ({ph})',
            names).fetchall()
        info = {r[0]: {'type_id': r[1], 'volume': r[2], 'jbv': None,
                       'portion_size': r[3] or 1, 'materials': [], 'mat_prices': {}}
                for r in rows}

        type_ids = [v['type_id'] for v in info.values()]
        if not type_ids:
            conn.close()
            return info

        id_ph    = ','.join('?' * len(type_ids))
        jita_sid = 60003760

        def _fetch_jbv(ids):
            """Return {type_id: best_buy} from market_snapshots then market_price_snapshots."""
            iph = ','.join('?' * len(ids))
            snap = conn.execute(f'''
                SELECT ms.type_id, ms.best_buy
                FROM market_snapshots ms
                INNER JOIN (
                    SELECT type_id, MAX(fetched_at) fa
                    FROM market_snapshots WHERE station_id=?
                    GROUP BY type_id
                ) l ON ms.type_id=l.type_id AND ms.fetched_at=l.fa
                WHERE ms.station_id=? AND ms.type_id IN ({iph})
            ''', [jita_sid, jita_sid] + ids).fetchall()
            m = {r[0]: r[1] for r in snap}
            fall = conn.execute(f'''
                SELECT mps.type_id, mps.best_buy
                FROM market_price_snapshots mps
                INNER JOIN (
                    SELECT type_id, MAX(timestamp) mt
                    FROM market_price_snapshots GROUP BY type_id
                ) l ON mps.type_id=l.type_id AND mps.timestamp=l.mt
                WHERE mps.type_id IN ({iph})
            ''', ids).fetchall()
            for r in fall:
                if r[0] not in m:
                    m[r[0]] = r[1]
            return m

        # Ore JBV (used as fallback if refine data is missing)
        ore_jbv = _fetch_jbv(type_ids)
        for name, d in info.items():
            d['jbv'] = ore_jbv.get(d['type_id'])

        # Refine materials from type_materials table
        tm_rows = conn.execute(
            f'SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({id_ph})',
            type_ids).fetchall()

        # tid → dict lookup
        tid_to_name = {d['type_id']: name for name, d in info.items()}
        mat_id_set = set()
        for tid, mj in tm_rows:
            try:
                mats = [(m['materialTypeID'], m['quantity']) for m in json.loads(mj)]
            except Exception:
                mats = []
            name = tid_to_name.get(tid)
            if name and mats:
                info[name]['materials'] = mats
                mat_id_set.update(mid for mid, _ in mats)

        # Material JBVs
        if mat_id_set:
            mat_prices = _fetch_jbv(list(mat_id_set))
            for d in info.values():
                if d['materials']:
                    d['mat_prices'] = {mid: mat_prices.get(mid) for mid, _ in d['materials']}

        conn.close()
        return info

    # ── Core calculation ───────────────────────────────────────────────────────

    def _parse_input(self):
        raw = self.input_text.get('1.0', 'end').strip()
        if not raw:
            raise ValueError('No items pasted.')
        items = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'\t| {2,}', line, maxsplit=1)
            if len(parts) != 2:
                raise ValueError(f'Cannot parse: {line!r}\n(Expected Name [Tab] Quantity)')
            name = parts[0].strip()
            qty_str = re.sub(r'[,\s]', '', parts[1])
            try:
                qty = int(float(qty_str))
            except ValueError:
                raise ValueError(f'Bad quantity on line: {line!r}')
            if qty <= 0:
                raise ValueError(f'Quantity must be > 0: {line!r}')
            items.append((name, qty))
        if not items:
            raise ValueError('No valid items found.')
        return items

    def _split_loads(self, pool, n_loads):
        total_rv = sum(i['remaining'] * i['rv'] for i in pool)
        total_vol = sum(i['qty'] * i['vol'] for i in pool)
        target   = total_rv / n_loads
        loads = []
        for load_num in range(1, n_loads + 1):
            # Last load gets whatever remains
            if load_num == n_loads:
                rem_target = sum(i['remaining'] * i['rv'] for i in pool)
            else:
                rem_target = target

            load_items = []
            load_rv = load_vol = 0.0
            for item in pool:
                if item['remaining'] <= 0 or rem_target <= 1e-6:
                    continue
                units_needed = rem_target / item['rv']
                take = min(item['remaining'], math.ceil(units_needed))
                # Don't overshoot by more than 1 unit's worth
                if take > 1 and take * item['rv'] > rem_target + item['rv']:
                    take = math.floor(units_needed)
                take = max(0, min(take, item['remaining']))
                if take == 0:
                    continue
                rv_taken  = take * item['rv']
                vol_taken = take * item['vol']
                load_items.append((item['name'], take, rv_taken, vol_taken))
                item['remaining'] -= take
                rem_target        -= rv_taken
                load_rv           += rv_taken
                load_vol          += vol_taken

            loads.append((load_rv, load_vol, load_items))
        return loads, total_rv, total_vol, target

    def _calculate(self):
        try:
            items = self._parse_input()
        except ValueError as e:
            self.status_var.set(f'Error: {e}')
            return

        names  = list({n for n, _ in items})
        db_map = self._lookup_db(names)

        eff = self.refine_eff_var.get() / 100.0
        fee = self.refine_fee_var.get() / 100.0
        n   = self.n_loads_var.get()

        pool     = []
        warnings = []
        for name, qty in items:
            if name not in db_map:
                warnings.append(f'Not in DB: {name}')
                continue
            d = db_map[name]
            vol     = d['volume']
            jbv     = d['jbv']
            mats    = d['materials']
            mprices = d['mat_prices']
            portion = d['portion_size']

            # Actual refine value: sum mineral outputs × mineral JBV / portionSize
            rv = None
            if mats:
                total = 0.0
                all_ok = True
                for mat_id, mat_qty in mats:
                    mat_jbv = mprices.get(mat_id)
                    if not mat_jbv:
                        all_ok = False
                        break
                    total += mat_qty * eff * (1 - fee) * mat_jbv
                if all_ok and portion > 0:
                    rv = total / portion

            # Fallback: ore JBV × eff × (1−fee)
            if rv is None:
                if jbv is None:
                    warnings.append(f'No price data: {name}')
                    continue
                rv = jbv * eff * (1 - fee)

            pool.append({'name': name, 'qty': qty, 'remaining': qty,
                         'rv': rv, 'vol': vol, 'jbv': jbv})

        if not pool:
            self.status_var.set('No items with Jita prices found. Fetch prices first.')
            return

        pool.sort(key=lambda x: -x['rv'])
        loads, total_rv, total_vol, target = self._split_loads(pool, n)
        self._render_results(loads, total_rv, total_vol, target)

        warn = ('  ⚠ ' + ' | '.join(warnings)) if warnings else ''
        self.status_var.set(f'Done — {n} loads calculated.{warn}')

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _render_results(self, loads, total_rv, total_vol, target):
        self.summary_var.set(
            f'  Total refine value: {total_rv:,.0f} ISK  ·  '
            f'Total volume: {total_vol:,.0f} m³  ·  '
            f'Target per load: {target:,.0f} ISK')

        for w in self.inner.winfo_children():
            w.destroy()

        for i, (rv, vol, items) in enumerate(loads):
            color = LOAD_COLORS[i % len(LOAD_COLORS)]

            box = tk.Frame(self.inner, bg=PANEL,
                           highlightthickness=1, highlightbackground=color)
            box.pack(fill='x', padx=14, pady=(10, 0))

            # Load header row
            hdr = tk.Frame(box, bg=PANEL)
            hdr.pack(fill='x', padx=12, pady=(8, 6))

            tk.Label(hdr, text=f'LOAD {i+1}', bg=PANEL, fg=color,
                     font=('Segoe UI', 10, 'bold')).pack(side='left')
            tk.Label(hdr, text=f'{rv:,.0f} ISK', bg=PANEL, fg=FG,
                     font=MONO).pack(side='left', padx=(16, 0))
            tk.Label(hdr, text=f'·  {vol:,.1f} m³', bg=PANEL, fg=DIM,
                     font=MONO).pack(side='left', padx=(8, 0))

            # Copy button
            def _copy(load_items=items):
                text = '\n'.join(f'{n}\t{q:,}' for n, q, _, _ in load_items)
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
            tk.Button(hdr, text='Copy', bg=PANEL2, fg=DIM,
                      font=('Segoe UI', 8), relief='flat', padx=10, pady=1,
                      activebackground=PANEL, activeforeground=FG,
                      command=_copy).pack(side='right')

            # Divider
            tk.Frame(box, bg=BORDER, height=1).pack(fill='x')

            # Item rows
            for j, (name, qty, item_rv, item_vol) in enumerate(items):
                row_bg = PANEL2 if j % 2 == 0 else PANEL
                row = tk.Frame(box, bg=row_bg)
                row.pack(fill='x')
                tk.Label(row, text=name, bg=row_bg, fg=FG,
                         font=FONT, anchor='w').pack(side='left', padx=(14, 0), pady=4)
                tk.Label(row, text=f'{item_rv:,.0f} ISK',
                         bg=row_bg, fg=DIM, font=MONO).pack(side='right', padx=(0, 14))
                tk.Label(row, text=f'{qty:,}', bg=row_bg, fg=ACCENT,
                         font=MONO).pack(side='right', padx=(0, 6))

            tk.Frame(box, height=4, bg=PANEL).pack()

        tk.Frame(self.inner, height=20, bg=BG).pack()


def main():
    root = tk.Tk()
    LoadSplitter(root)
    root.mainloop()


if __name__ == '__main__':
    main()
