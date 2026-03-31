"""
import_tool.py
-------------
Standalone Import Analysis tool for LX-ZOJ.

Shows live buy prices at all 5 trade hubs for every tracked item.
Calculates margin = (sell_price − hub_price − broker − shipping − collateral) / hub_price × 100

Sell price:
  - Compressed ore / ice / moon ore  → refine value per unit (product JBV × qty × refine_eff)
    using ore_pct_{type_id} sell rates for each refine product (same as Ore Import tab).
  - All other categories             → Jita JBV × per-item sell% from Product Sell Rates panel.

Uncompressed ore (display_order < 101) are excluded entirely.

Product Sell Rates panel key scheme:
  - minerals / ice_products / moon_materials : ore_pct_{type_id}  (shared with Ore Import tab)
  - all other categories                     : import_pct_{type_id}
  - Defaults to item's price_percentage from tracked_market_items.

Run:  python import_tool.py
"""

import json
import tkinter as tk
from tkinter import ttk
import sqlite3
import os
import sys
import subprocess
import threading
from collections import defaultdict
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(PROJECT_DIR, 'mydatabase.db')
SDE_DIR     = os.path.join(PROJECT_DIR, 'sde')

# Categories whose sell_price is calculated as refine value (same model as Ore Import tab)
ORE_REFINE_CATEGORIES = {'standard_ore', 'ice_ore', 'moon_ore'}
DEFAULT_REFINE_EFF = 90.63

# ── Hub definitions ──────────────────────────────────────────────────────────
HUBS = {
    'Jita':    {'station_id': 60003760, 'region_id': 10000002},
    'Amarr':   {'station_id': 60008494, 'region_id': 10000043},
    'Dodixie': {'station_id': 60011866, 'region_id': 10000032},
    'Rens':    {'station_id': 60004588, 'region_id': 10000030},
    'Hek':     {'station_id': 60005686, 'region_id': 10000042},
}
HUB_ORDER = ['Amarr', 'Rens', 'Hek', 'Dodixie', 'Jita']

# ── Category maps (uncompressed ore excluded — compressed ore included) ──────
CATEGORY_DISPLAY = {
    'minerals':           'Minerals',
    'ice_products':       'Ice Products',
    'moon_materials':     'Reaction Materials',
    'gas_cloud_materials':'Gas Cloud Materials',
    'research_equipment': 'Research Equipment',
    'pi_materials':       'Planetary Materials',
    'salvaged_materials': 'Salvaged Materials',
    'standard_ore':       'Compressed Ore',
    'ice_ore':            'Compressed Ice',
    'moon_ore':           'Compressed Moon Ore',
    'fw_ammo':            'Crucible of the Faithful',
}
DISPLAY_TO_CAT = {v: k for k, v in CATEGORY_DISPLAY.items()}

CATEGORY_FETCH_ARG = {
    'All':                       'import_all',
    'Minerals':                  'minerals',
    'Ice Products':              'ice_products',
    'Reaction Materials':        'moon_materials',
    'Gas Cloud Materials':       'gas_cloud_materials',
    'Research Equipment':        'research_equipment',
    'Planetary Materials':       'pi_materials',
    'Salvaged Materials':        'salvaged_materials',
    'Compressed Ore':            'compressed_standard_ore',
    'Compressed Ice':            'compressed_ice_ore',
    'Compressed Moon Ore':       'compressed_moon_ore',
    'Crucible of the Faithful':  'fw_ammo',
}

PI_GROUP_MAP = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}

SUBCAT_LABELS = {
    'ice_products':        {'fuel_blocks':'Fuel Blocks', 'refined_ice':'Refined Ice',
                            'isotopes':'Isotopes'},
    'moon_materials':      {'raw':'Raw', 'processed':'Processed', 'advanced':'Advanced'},
    'gas_cloud_materials': {
        'compressed_fullerene': 'Compressed Fullerenes',
        'compressed_booster':   'Compressed Booster Gas',
        'uncompressed_fullerene':'Uncompressed Fullerenes',
        'uncompressed_booster': 'Uncompressed Booster Gas',
    },
    'research_equipment':  {'datacores':'Datacores', 'decryptors':'Decryptors'},
    'pi_materials':        {'p1':'P1', 'p2':'P2', 'p3':'P3', 'p4':'P4'},
    'salvaged_materials':  {'common':'Common', 'uncommon':'Uncommon', 'rare':'Rare',
                            'very_rare':'Very Rare', 'rogue_drone':'Rogue Drone'},
}

# Items in these DB categories use ore_pct_ site_config keys (shared with admin dashboard)
ORE_PCT_CATEGORIES = {'minerals', 'ice_products', 'moon_materials'}

# Section header colours per subcat label
SECTION_COLORS = {
    # minerals / ice / moon
    'Minerals':              '#00d9ff',
    'Fuel Blocks':           '#aaddff',
    'Refined Ice':           '#88ccff',
    'Isotopes':              '#66bbff',
    'Raw':                   '#888888',
    'Processed':             '#cc88ff',
    'Advanced':              '#9944ff',
    # gas
    'Compressed Fullerenes': '#00ffcc',
    'Compressed Booster Gas':'#ffd700',
    'Uncompressed Fullerenes':'#88aacc',
    'Uncompressed Booster Gas':'#cc8844',
    # research
    'Datacores':             '#00d9ff',
    'Decryptors':            '#cc88ff',
    # PI
    'P1':                    '#88ff88',
    'P2':                    '#44aaff',
    'P3':                    '#ff8844',
    'P4':                    '#ffcc44',
    # salvage
    'Common':                '#88d0e8',
    'Uncommon':              '#44dd88',
    'Rare':                  '#8888ff',
    'Very Rare':             '#ff8888',
    'Rogue Drone':           '#ffaa44',
}


def _get_subcat_key(category, display_order, market_group_id):
    if category == 'ice_products':
        if display_order is None: return ''
        if display_order <= 4:   return 'fuel_blocks'
        if display_order <= 11:  return 'refined_ice'
        return 'isotopes'
    elif category == 'moon_materials':
        if display_order is None: return ''
        if display_order <= 35:  return 'raw'
        if display_order <= 124: return 'processed'
        return 'advanced'
    elif category == 'gas_cloud_materials':
        if display_order is None: return ''
        if display_order < 100:  return 'compressed_fullerene'
        if display_order < 200:  return 'compressed_booster'
        if display_order < 300:  return 'uncompressed_fullerene'
        return 'uncompressed_booster'
    elif category == 'research_equipment':
        if display_order is None: return ''
        return 'datacores' if display_order < 100 else 'decryptors'
    elif category == 'pi_materials':
        return PI_GROUP_MAP.get(market_group_id, '')
    elif category == 'salvaged_materials':
        if display_order is None: return ''
        if display_order < 10:  return 'common'
        if display_order < 22:  return 'uncommon'
        if display_order < 33:  return 'rare'
        if display_order < 43:  return 'very_rare'
        return 'rogue_drone'
    return ''


# ── Formatting helpers ───────────────────────────────────────────────────────
def fmt_isk(v):
    if v is None: return '—'
    return f'{v:,.2f}'


def load_sde_refine_data(type_ids):
    """
    Load portionSize and refining materials for given ore type IDs from SDE files.
    Returns:
        portion_sizes   : {type_id: portion_size}
        type_materials  : {type_id: [(mat_type_id, quantity), ...]}
    """
    id_set = set(type_ids)
    portion_sizes  = {}
    type_materials = {}

    types_path = os.path.join(SDE_DIR, 'types.jsonl')
    if os.path.exists(types_path):
        with open(types_path, encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                tid = obj.get('_key')
                if tid in id_set:
                    portion_sizes[tid] = obj.get('portionSize', 1)

    mats_path = os.path.join(SDE_DIR, 'typeMaterials.jsonl')
    if os.path.exists(mats_path):
        with open(mats_path, encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                tid = obj.get('_key')
                if tid in id_set:
                    type_materials[tid] = [
                        (m['materialTypeID'], m['quantity'])
                        for m in obj.get('materials', [])
                    ]

    return portion_sizes, type_materials


def ensure_market_snapshots(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at TEXT, region_id INTEGER, station_id INTEGER,
            type_id INTEGER, best_buy REAL, best_sell REAL,
            spread_pct REAL, buy_volume INTEGER, sell_volume INTEGER
        )
    """)
    conn.commit()


# ── Treeview columns (no Sell % — all rates live in the panel) ───────────────
COLS        = ('name', 'amarr', 'rens', 'hek', 'dodixie', 'jita',
               'best_hub', 'margin', 'max_buy', 'dev')
COL_LABELS  = ('Item Name', 'Amarr', 'Rens', 'Hek', 'Dodixie', 'Jita',
               'Best Hub', 'Margin %', 'Max Buy Price', 'vs N-Day Avg %')
COL_WIDTHS  = (260, 120, 120, 120, 120, 120, 80, 80, 120, 100)
COL_ANCHORS = ('w', 'e', 'e', 'e', 'e', 'e', 'center', 'e', 'e', 'e')
HUB_COL_MAP = {'amarr': 'Amarr', 'rens': 'Rens', 'hek': 'Hek',
               'dodixie': 'Dodixie', 'jita': 'Jita'}

# Tab definitions for the product panel notebook
TAB_DEFS = [
    ('Minerals / Ice / Moon', ['minerals', 'ice_products', 'moon_materials']),
    ('Gas Cloud / Research',  ['gas_cloud_materials', 'research_equipment']),
    ('Planetary Materials',   ['pi_materials']),
    ('Salvaged Materials',    ['salvaged_materials']),
    ('Compressed Ore',        ['standard_ore', 'ice_ore', 'moon_ore']),
    ('Crucible of the Faithful', ['fw_ammo']),
]


class ImportTool:
    def __init__(self, root):
        self.root = root
        self.root.title("LX-ZOJ  ·  Import Analysis")
        self.root.geometry("1440x820")
        self.root.configure(bg='#0d1117')

        self.broker_var        = tk.DoubleVar(value=0.0)
        self.ship_var          = tk.DoubleVar(value=500.0)
        self.refine_eff_var    = tk.DoubleVar(value=DEFAULT_REFINE_EFF)
        self.margin_target_var = tk.DoubleVar(value=5.0)
        self.cat_var        = tk.StringVar(value='All')
        self.subcat_var     = tk.StringVar(value='All')
        self.buy_mode_var   = tk.StringVar(value='Sell Orders')
        self.coll_pct_var   = tk.DoubleVar(value=1.0)
        self.coll_basis_var = tk.StringVar(value='JBV')
        self.hub_vars       = {hub: tk.BooleanVar(value=True) for hub in HUB_ORDER}
        self.dev_days_var   = tk.IntVar(value=7)

        self._all_rows        = []
        self._sort_col        = None
        self._sort_rev        = False
        self._all_pcts        = {}   # type_id → StringVar (all items, both key schemes)
        self._pct_after_id    = None
        self._products_visible = False

        # SDE refine data — loaded once on first load_data call
        self._sde_portions   = {}   # type_id → portionSize
        self._sde_materials  = {}   # type_id → [(mat_type_id, qty), ...]
        self._sde_loaded_ids = set()

        # Latest prices — populated in load_data, used by _calc_row for refine value
        self._all_prices    = {}   # (station_id, type_id) → (best_buy, best_sell)
        self._jita_fallback = {}   # type_id → (best_buy, best_sell) from market_price_snapshots
        self._avg_prices    = {}   # type_id → N-day avg best_buy (from market_price_snapshots)

        self._build_ui()
        self._ensure_db()
        self.load_data()

    # ── DB init ──────────────────────────────────────────────────────────────

    def _ensure_db(self):
        conn = sqlite3.connect(DB_PATH)
        ensure_market_snapshots(conn)
        conn.close()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background='#0d1117', foreground='#e8f4ff',
                        fieldbackground='#0d1117')
        style.configure('TFrame', background='#0d1117')
        style.configure('TLabel', background='#0d1117', foreground='#e8f4ff')
        style.configure('TCombobox',
            fieldbackground='#ffffff', background='#ffffff', foreground='#000000',
            selectbackground='#1a3a5a', selectforeground='#ffffff')
        style.map('TCombobox',
            fieldbackground=[('readonly', '#ffffff')],
            foreground=[('readonly', '#000000')])
        style.configure('Treeview',
            background='#0a1520', foreground='#c8dff0',
            fieldbackground='#0a1520', rowheight=22)
        style.configure('Treeview.Heading',
            background='#1a2a3a', foreground='#00d9ff',
            font=('Segoe UI', 9, 'bold'), relief='flat')
        style.map('Treeview',
            background=[('selected', '#1a3a5a')],
            foreground=[('selected', '#ffffff')])
        style.map('Treeview.Heading', background=[('active', '#253a4a')])
        # Notebook tab styling
        style.configure('TNotebook', background='#0a1828', borderwidth=0, tabmargins=0)
        style.configure('TNotebook.Tab', background='#111a25', foreground='#7090a8',
                        font=('Segoe UI', 9), padding=[10, 3])
        style.map('TNotebook.Tab',
                  background=[('selected', '#0a1828')],
                  foreground=[('selected', '#00d9ff')])
        self.root.option_add('*TCombobox*Listbox.background',       '#ffffff')
        self.root.option_add('*TCombobox*Listbox.foreground',       '#000000')
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#1a3a5a')
        self.root.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')

        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg='#060e18', height=50)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='LX-ZOJ  ·  IMPORT ANALYSIS',
                 bg='#060e18', fg='#e8f4ff',
                 font=('Segoe UI', 14, 'bold')).pack(side='left', padx=18, pady=12)
        tk.Frame(hdr, bg='#00aaff', width=2).pack(side='left', fill='y', pady=10)
        tk.Label(hdr, text='Live hub pricing · sell price = Jita JBV × per-item rate (set in Product Sell Rates panel)',
                 bg='#060e18', fg='#507090',
                 font=('Segoe UI', 9)).pack(side='left', padx=14)

        # ── Controls bar ────────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg='#111a25', pady=6)
        ctrl.pack(fill='x')
        inner = tk.Frame(ctrl, bg='#111a25')
        inner.pack(fill='x', padx=14)

        # Row 1 — Category / Sub / Fetch
        row1 = tk.Frame(inner, bg='#111a25')
        row1.pack(fill='x', pady=(0, 4))

        tk.Label(row1, text='Category:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        self.cat_combo = ttk.Combobox(row1, textvariable=self.cat_var,
                                       state='readonly', width=20,
                                       font=('Segoe UI', 10))
        self.cat_combo.pack(side='left', padx=(4, 12))
        self.cat_combo.bind('<<ComboboxSelected>>', self._on_cat_change)

        tk.Label(row1, text='Sub:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        self.subcat_combo = ttk.Combobox(row1, textvariable=self.subcat_var,
                                          state='readonly', width=20,
                                          font=('Segoe UI', 10))
        self.subcat_combo.pack(side='left', padx=(4, 0))
        self.subcat_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())

        self.fetch_btn = tk.Button(
            row1, text='⟳  Fetch Prices',
            bg='#0d2a40', fg='#00d9ff', font=('Segoe UI', 10, 'bold'),
            relief='flat', padx=14, pady=4,
            activebackground='#1a3a50', activeforeground='#44eeff',
            command=self._fetch_prices)
        self.fetch_btn.pack(side='right')

        # Row 1b — Hub toggles
        row1b = tk.Frame(inner, bg='#111a25')
        row1b.pack(fill='x', pady=(0, 4))
        tk.Label(row1b, text='Hubs:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        for hub_name in HUB_ORDER:
            tk.Checkbutton(
                row1b, text=hub_name,
                variable=self.hub_vars[hub_name],
                bg='#111a25', fg='#c8dff0',
                selectcolor='#0d1117',
                activebackground='#111a25', activeforeground='#e8f4ff',
                font=('Segoe UI', 10),
                command=self._apply_filter
            ).pack(side='left', padx=(6, 0))

        # Row 2 — Calculation parameters
        row2 = tk.Frame(inner, bg='#111a25')
        row2.pack(fill='x')

        def sep():
            tk.Frame(row2, bg='#2a3a4a', width=1).pack(side='left', fill='y', padx=10)

        tk.Label(row2, text='Buy from:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        for lbl in ('Sell Orders', 'Buy Orders'):
            tk.Radiobutton(row2, text=lbl, variable=self.buy_mode_var, value=lbl,
                           bg='#111a25', fg='#c8dff0', selectcolor='#0d1117',
                           activebackground='#111a25', activeforeground='#e8f4ff',
                           font=('Segoe UI', 10),
                           command=self._apply_filter).pack(side='left', padx=(4, 6))
        sep()

        tk.Label(row2, text='Broker % (Buy Orders):', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        bspin = tk.Spinbox(row2, from_=0.0, to=10.0, increment=0.1,
                           textvariable=self.broker_var, width=5,
                           font=('Segoe UI', 10), bg='#0a2030', fg='#00ffcc',
                           buttonbackground='#1a3040', insertbackground='#00ffcc',
                           command=self._apply_filter, relief='flat')
        bspin.pack(side='left', padx=(4, 0))
        bspin.bind('<Return>', lambda e: self._apply_filter())
        sep()

        tk.Label(row2, text='Ship ISK/m³:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        ship_e = tk.Entry(row2, textvariable=self.ship_var, width=8,
                          font=('Segoe UI', 10), bg='#0a2030', fg='#00ffcc',
                          insertbackground='#00ffcc', relief='flat')
        ship_e.pack(side='left', padx=(4, 0))
        ship_e.bind('<Return>',   lambda e: self._apply_filter())
        ship_e.bind('<FocusOut>', lambda e: self._apply_filter())
        sep()

        tk.Label(row2, text='Refine %:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        ref_e = tk.Entry(row2, textvariable=self.refine_eff_var, width=7,
                         font=('Segoe UI', 10), bg='#0a2030', fg='#00ffcc',
                         insertbackground='#00ffcc', relief='flat')
        ref_e.pack(side='left', padx=(4, 0))
        ref_e.bind('<Return>',   lambda e: self._apply_filter())
        ref_e.bind('<FocusOut>', lambda e: self._apply_filter())
        tk.Label(row2, text='(ore)', bg='#111a25', fg='#446677',
                 font=('Segoe UI', 8)).pack(side='left', padx=(2, 0))
        sep()

        tk.Label(row2, text='Margin Target %:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        tgt_spin = tk.Spinbox(row2, from_=0.0, to=100.0, increment=0.5,
                              textvariable=self.margin_target_var, width=5,
                              font=('Segoe UI', 10), bg='#0a2030', fg='#ffd700',
                              buttonbackground='#1a3040', insertbackground='#ffd700',
                              command=self._apply_filter, relief='flat')
        tgt_spin.pack(side='left', padx=(4, 0))
        tgt_spin.bind('<Return>', lambda e: self._apply_filter())
        sep()

        tk.Label(row2, text='Dev Days:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        dev_spin = tk.Spinbox(row2, from_=1, to=90, increment=1,
                              textvariable=self.dev_days_var, width=4,
                              font=('Segoe UI', 10), bg='#0a2030', fg='#ffd700',
                              buttonbackground='#1a3040', insertbackground='#ffd700',
                              command=self._on_dev_days_change, relief='flat')
        dev_spin.pack(side='left', padx=(4, 0))
        dev_spin.bind('<Return>', lambda e: self._on_dev_days_change())
        sep()

        tk.Label(row2, text='Collateral %:', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        cspin = tk.Spinbox(row2, from_=0.0, to=10.0, increment=0.1,
                           textvariable=self.coll_pct_var, width=5,
                           font=('Segoe UI', 10), bg='#0a2030', fg='#00ffcc',
                           buttonbackground='#1a3040', insertbackground='#00ffcc',
                           command=self._apply_filter, relief='flat')
        cspin.pack(side='left', padx=(4, 6))
        cspin.bind('<Return>', lambda e: self._apply_filter())
        tk.Label(row2, text='of', bg='#111a25', fg='#7090a8',
                 font=('Segoe UI', 10)).pack(side='left')
        coll_cb = ttk.Combobox(row2, textvariable=self.coll_basis_var,
                                values=['JBV', 'JSV', 'Split'], state='readonly',
                                width=6, font=('Segoe UI', 10))
        coll_cb.pack(side='left', padx=(4, 0))
        coll_cb.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())

        # Row 3 — Toggle for product sell rates panel
        row3 = tk.Frame(inner, bg='#111a25')
        row3.pack(fill='x', pady=(4, 0))
        self._toggle_btn = tk.Button(
            row3,
            text='▶  Product Sell Rates  (click to expand — set per-item sell % for all categories)',
            bg='#0a1828', fg='#7090a8', font=('Segoe UI', 9),
            relief='flat', anchor='w', padx=8, pady=3,
            activebackground='#0d1f30', activeforeground='#aaccdd',
            command=self._toggle_product_panel)
        self._toggle_btn.pack(fill='x')

        # ── Product sell rates panel (hidden by default) ─────────────────────
        self._product_frame = tk.Frame(self.root, bg='#0a1828')
        self._product_nb    = ttk.Notebook(self._product_frame)
        self._product_nb.pack(fill='x', padx=0, pady=0)
        # Create tab frames with scrollable canvas inside each tab
        self._tab_frames       = []   # outer frame added to notebook
        self._tab_canvases     = []   # canvas widget for each tab
        self._tab_inner_frames = []   # inner frame that holds actual content
        for tab_label, _ in TAB_DEFS:
            outer = tk.Frame(self._product_nb, bg='#0a1828')
            self._product_nb.add(outer, text=tab_label)
            self._tab_frames.append(outer)

            canvas = tk.Canvas(outer, bg='#0a1828', highlightthickness=0, height=190)
            vsb    = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)

            inner = tk.Frame(canvas, bg='#0a1828')
            win   = canvas.create_window((0, 0), window=inner, anchor='nw')

            def _on_inner_cfg(event, c=canvas):
                c.configure(scrollregion=c.bbox('all'))
            inner.bind('<Configure>', _on_inner_cfg)

            def _on_canvas_cfg(event, c=canvas, w=win):
                c.itemconfig(w, width=event.width)
            canvas.bind('<Configure>', _on_canvas_cfg)

            # Bind mousewheel while cursor is inside the canvas region
            def _enter(event, c=canvas):
                c.bind_all('<MouseWheel>',
                    lambda e, cv=c: cv.yview_scroll(int(-1 * (e.delta / 120)), 'units'))
            def _leave(event, c=canvas):
                c.unbind_all('<MouseWheel>')
            canvas.bind('<Enter>', _enter)
            canvas.bind('<Leave>', _leave)

            self._tab_canvases.append(canvas)
            self._tab_inner_frames.append(inner)

        # ── Treeview ────────────────────────────────────────────────────────
        self._tree_outer = tk.Frame(self.root, bg='#0d1117')
        self._tree_outer.pack(fill='both', expand=True, padx=14, pady=(8, 0))

        self.tree = ttk.Treeview(self._tree_outer, columns=COLS,
                                  show='headings', selectmode='browse')
        for col, lbl, w, anc in zip(COLS, COL_LABELS, COL_WIDTHS, COL_ANCHORS):
            self.tree.heading(col, text=lbl, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, anchor=anc, minwidth=40)

        vsb = ttk.Scrollbar(self._tree_outer, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(self._tree_outer, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side='bottom', fill='x')
        vsb.pack(side='right',  fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.tree.tag_configure('green',    foreground='#44dd88')
        self.tree.tag_configure('yellow',   foreground='#ffd700')
        self.tree.tag_configure('red',      foreground='#ff6666')
        self.tree.tag_configure('nodata',   foreground='#445566')
        self.tree.tag_configure('alt',      background='#0a1828')
        self.tree.tag_configure('dev_high', foreground='#ff9a00')
        self.tree.tag_configure('dev_low',  foreground='#00d4ff')

        # ── Status bar ──────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value='Loading…')
        tk.Label(self.root, textvariable=self.status_var,
                 bg='#060e18', fg='#507090',
                 font=('Segoe UI', 9), anchor='w', pady=5
                 ).pack(fill='x', side='bottom', padx=14)

    # ── Product panel toggle ─────────────────────────────────────────────────

    def _toggle_product_panel(self):
        if self._products_visible:
            self._product_frame.pack_forget()
            self._products_visible = False
            self._toggle_btn.configure(
                text='▶  Product Sell Rates  (click to expand — set per-item sell % for all categories)')
        else:
            self._product_frame.pack(fill='x', before=self._tree_outer)
            self._products_visible = True
            self._toggle_btn.configure(
                text='▼  Product Sell Rates  (click to collapse)')

    # ── Product panel content builder ────────────────────────────────────────

    def _rebuild_product_tabs(self):
        """Rebuild all notebook tab contents from _all_rows and _all_pcts."""
        bg       = '#0a1828'
        lkw      = dict(bg=bg, font=('Segoe UI', 8))
        ekw      = dict(font=('Segoe UI', 9), bg='#0a2030', fg='#00ffcc',
                        insertbackground='#00ffcc', relief='flat',
                        justify='center', width=5)
        per_row  = 8

        for tab_idx, (_, db_cats) in enumerate(TAB_DEFS):
            inner  = self._tab_inner_frames[tab_idx]
            canvas = self._tab_canvases[tab_idx]
            for w in inner.winfo_children():
                w.destroy()

            # Collect items for this tab, grouped by subcat_label
            groups = defaultdict(list)  # subcat_label → [(tid, name)]
            subcat_order = []           # preserve order of first appearance
            cat_for_subcat = {}
            for row in self._all_rows:
                db_cat = DISPLAY_TO_CAT.get(row['category'])
                if db_cat not in db_cats:
                    continue
                sl = row['subcat_label'] or row['category']
                if sl not in groups:
                    subcat_order.append(sl)
                    cat_for_subcat[sl] = db_cat
                groups[sl].append((row['type_id'], row['name']))

            if not subcat_order:
                tk.Label(inner, text='No items loaded yet',
                         bg=bg, fg='#446688',
                         font=('Segoe UI', 9)).pack(padx=12, pady=8)
                canvas.configure(scrollregion=canvas.bbox('all'))
                continue

            for sl in subcat_order:
                items = groups[sl]
                color = SECTION_COLORS.get(sl, '#88d0e8')

                hdr = tk.Frame(inner, bg=bg)
                hdr.pack(fill='x', padx=12, pady=(6, 2))
                tk.Label(hdr, text=sl.upper(), fg=color,
                         font=('Segoe UI', 8, 'bold'), **{'bg': bg}).pack(side='left')

                for chunk_start in range(0, len(items), per_row):
                    chunk    = items[chunk_start:chunk_start + per_row]
                    row_frm  = tk.Frame(inner, bg=bg)
                    row_frm.pack(fill='x', padx=12, pady=1)
                    for tid, name in chunk:
                        var = self._all_pcts.get(tid)
                        if var is None:
                            continue
                        f = tk.Frame(row_frm, bg=bg)
                        f.pack(side='left', padx=3)
                        tk.Label(f, text=name, fg=color, **lkw).pack()
                        tk.Entry(f, textvariable=var, **ekw).pack()

            # Force geometry update so bbox('all') is accurate
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))

    # ── Sell % var management ────────────────────────────────────────────────

    def _ensure_pct_var(self, type_id, db_cat, default_pct):
        """Create a StringVar for type_id if one doesn't exist yet."""
        if type_id in self._all_pcts:
            return
        var = tk.StringVar(value=str(default_pct))
        var.trace_add('write',
            lambda *_, t=type_id, v=var, c=db_cat:
                self._on_pct_write(t, v, c))
        self._all_pcts[type_id] = var

    def _on_pct_write(self, type_id, var, db_cat):
        try:
            float(var.get())
        except ValueError:
            return
        key = (f'ore_pct_{type_id}' if db_cat in ORE_PCT_CATEGORIES
               else f'import_pct_{type_id}')
        self._save_pct(key, var.get())
        if self._pct_after_id:
            self.root.after_cancel(self._pct_after_id)
        self._pct_after_id = self.root.after(400, self._apply_filter)

    def _save_pct(self, key, value):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute('DELETE FROM site_config WHERE key=?', (key,))
            conn.execute('INSERT INTO site_config (key, value) VALUES (?,?)', (key, value))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Data loading ─────────────────────────────────────────────────────────

    def load_data(self):
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        # Tracked items — uncompressed ore excluded; compressed ore (display_order >= 101) included
        c.execute("""
            SELECT tm.type_id, tm.type_name, tm.category, tm.display_order,
                   tm.price_percentage,
                   COALESCE(it.volume, 0.0)        AS volume,
                   COALESCE(it.market_group_id, 0) AS mkt_grp
            FROM tracked_market_items tm
            LEFT JOIN inv_types it ON tm.type_id = it.type_id
            WHERE NOT (tm.category IN ('standard_ore', 'ice_ore', 'moon_ore')
                       AND (tm.display_order IS NULL OR tm.display_order < 101))
            ORDER BY tm.category, tm.display_order, tm.type_name
        """)
        items = c.fetchall()

        # Hub prices (latest per station/type) from market_snapshots
        c.execute("""
            SELECT ms.station_id, ms.type_id, ms.best_buy, ms.best_sell
            FROM market_snapshots ms
            INNER JOIN (
                SELECT station_id, type_id, MAX(fetched_at) AS max_fa
                FROM market_snapshots GROUP BY station_id, type_id
            ) latest ON ms.station_id = latest.station_id
                    AND ms.type_id    = latest.type_id
                    AND ms.fetched_at = latest.max_fa
        """)
        hub_prices_raw = c.fetchall()

        # Jita fallback (market_price_snapshots — Jita only)
        c.execute("""
            SELECT mps.type_id, mps.best_buy, mps.best_sell
            FROM market_price_snapshots mps
            INNER JOIN (
                SELECT type_id, MAX(timestamp) AS max_ts
                FROM market_price_snapshots GROUP BY type_id
            ) latest ON mps.type_id = latest.type_id
                     AND mps.timestamp = latest.max_ts
        """)
        jita_fallback = {r[0]: (r[1], r[2]) for r in c.fetchall()}

        # Stored sell % values
        c.execute("""
            SELECT key, value FROM site_config
            WHERE key LIKE 'ore_pct_%' OR key LIKE 'import_pct_%'
        """)
        stored_pcts = {}
        for key, val in c.fetchall():
            try:
                if key.startswith('ore_pct_'):
                    stored_pcts[int(key[8:])]  = float(val)
                else:
                    stored_pcts[int(key[11:])] = float(val)
            except (ValueError, IndexError):
                pass

        c.execute("SELECT MAX(fetched_at) FROM market_snapshots")
        last_fa = c.fetchone()[0]

        # N-day average buy prices (Jita only, from market_price_snapshots)
        n_days = self.dev_days_var.get()
        c.execute("""
            SELECT type_id, AVG(best_buy)
            FROM market_price_snapshots
            WHERE timestamp >= datetime('now', ?)
            GROUP BY type_id
        """, (f'-{n_days} days',))
        self._avg_prices = {r[0]: r[1] for r in c.fetchall() if r[1] is not None}

        conn.close()

        # Hub price lookup: (station_id, type_id) → (best_buy, best_sell)
        prices = {}
        for sid, tid, bb, bs in hub_prices_raw:
            prices[(sid, tid)] = (bb, bs)

        # Save to instance so _calc_row can access for refine value calculation
        self._all_prices    = prices
        self._jita_fallback = jita_fallback

        jita_sid = HUBS['Jita']['station_id']
        all_rows = []
        for type_id, name, category, display_order, price_pct, volume, mkt_grp in items:
            subcat_key   = _get_subcat_key(category, display_order, mkt_grp)
            subcat_label = SUBCAT_LABELS.get(category, {}).get(subcat_key, '')
            cat_display  = CATEGORY_DISPLAY.get(category, category)

            hub_sell, hub_buy = {}, {}
            for hub_name in HUB_ORDER:
                pair = prices.get((HUBS[hub_name]['station_id'], type_id))
                hub_sell[hub_name] = pair[1] if pair else None
                hub_buy[hub_name]  = pair[0] if pair else None

            jita_pair = prices.get((jita_sid, type_id))
            jita_jbv, jita_jsv = (jita_pair if jita_pair
                                  else jita_fallback.get(type_id, (None, None)))

            # Ensure a sell % var exists for this item
            default = stored_pcts.get(type_id, price_pct or 95.0)
            self._ensure_pct_var(type_id, category, default)
            # Apply stored value (don't overwrite an in-session edit in progress)
            if type_id in stored_pcts and type_id in self._all_pcts:
                self._all_pcts[type_id].set(str(stored_pcts[type_id]))

            all_rows.append({
                'type_id':      type_id,
                'name':         name,
                'category':     cat_display,
                'db_cat':       category,
                'subcat_key':   subcat_key,
                'subcat_label': subcat_label,
                'volume':       volume,
                'price_pct':    price_pct,
                'hub_sell':     hub_sell,
                'hub_buy':      hub_buy,
                'jita_jbv':     jita_jbv,
                'jita_jsv':     jita_jsv,
            })

        self._all_rows = all_rows

        # Load SDE refine data for any new ore type_ids not yet loaded
        ore_ids = {r['type_id'] for r in all_rows if r['db_cat'] in ORE_REFINE_CATEGORIES}
        new_ids = ore_ids - self._sde_loaded_ids
        if new_ids:
            portions, mats = load_sde_refine_data(ore_ids)
            self._sde_portions.update(portions)
            self._sde_materials.update(mats)
            self._sde_loaded_ids.update(ore_ids)

        # Rebuild product panel tab contents
        self._rebuild_product_tabs()

        # Populate category dropdown
        cats     = sorted(set(r['category'] for r in all_rows))
        cat_opts = ['All'] + cats
        self.cat_combo['values'] = cat_opts
        if self.cat_var.get() not in cat_opts:
            self.cat_var.set('All')

        self._update_subcat_combo()
        self._apply_filter()

        ts_str = ''
        if last_fa:
            try:
                dt     = datetime.fromisoformat(last_fa)
                ts_str = f'  ·  Last fetched: {dt.strftime("%d %b %Y  %H:%M UTC")}'
            except Exception:
                ts_str = f'  ·  Last fetched: {last_fa[:16]}'
        self._set_status(f'{len(all_rows)} items loaded{ts_str}')

    # ── Filter helpers ───────────────────────────────────────────────────────

    def _update_subcat_combo(self):
        cat_key = DISPLAY_TO_CAT.get(self.cat_var.get())
        subcats = SUBCAT_LABELS.get(cat_key, {})
        opts    = ['All'] + list(subcats.values())
        self.subcat_combo['values'] = opts
        if self.subcat_var.get() not in opts:
            self.subcat_var.set('All')

    def _on_cat_change(self, event=None):
        self._update_subcat_combo()
        self._apply_filter()

    def _on_dev_days_change(self):
        self.load_data()

    def _apply_filter(self):
        try:    broker_pct = self.broker_var.get() / 100.0
        except: broker_pct = 0.0
        try:    isk_per_m3 = float(self.ship_var.get())
        except: isk_per_m3 = 500.0
        try:    coll_pct   = self.coll_pct_var.get() / 100.0
        except: coll_pct   = 0.01

        coll_basis    = self.coll_basis_var.get()
        buy_mode      = self.buy_mode_var.get()
        cat_filter    = self.cat_var.get()
        subcat_filter = self.subcat_var.get()

        try:    refine_eff     = self.refine_eff_var.get()
        except: refine_eff     = DEFAULT_REFINE_EFF
        try:    margin_target  = self.margin_target_var.get()
        except: margin_target  = 5.0

        rows = []
        for row in self._all_rows:
            if cat_filter    != 'All' and row['category']     != cat_filter:    continue
            if subcat_filter != 'All' and row['subcat_label'] != subcat_filter: continue
            rows.append(self._calc_row(row, buy_mode, broker_pct,
                                       isk_per_m3, coll_pct, coll_basis,
                                       refine_eff, margin_target))

        if self._sort_col:
            rows.sort(key=lambda r: self._row_sort_key(r, self._sort_col),
                      reverse=self._sort_rev)
        self._populate_tree(rows)

    def _calc_row(self, row, buy_mode, broker_pct, isk_per_m3, coll_pct, coll_basis,
                  refine_eff=DEFAULT_REFINE_EFF, margin_target=5.0):
        type_id  = row['type_id']
        db_cat   = row['db_cat']
        jita_jbv = row['jita_jbv']
        jita_jsv = row['jita_jsv']
        jita_sid = HUBS['Jita']['station_id']

        if db_cat in ORE_REFINE_CATEGORIES:
            # Sell price = refine value per unit of compressed ore
            # same model as Ore Import tab: sum(mat_qty × refine_eff × mat_JBV × mat_sell_pct)
            # divided by portionSize to get per-unit value
            mats    = self._sde_materials.get(type_id, [])
            portion = self._sde_portions.get(type_id, 1)
            eff     = refine_eff / 100.0
            rv      = 0.0
            for mat_id, qty in mats:
                # Product JBV: from market_snapshots Jita first, then market_price_snapshots
                mat_pair  = self._all_prices.get((jita_sid, mat_id))
                mat_jbv   = mat_pair[0] if mat_pair else None
                if mat_jbv is None:
                    fb = self._jita_fallback.get(mat_id)
                    mat_jbv = fb[0] if fb else None
                if not mat_jbv:
                    continue
                # Product sell %: from _all_pcts (ore_pct_ key, same as Ore Import tab)
                pct_var  = self._all_pcts.get(mat_id)
                try:    mat_pct = float(pct_var.get()) if pct_var else 100.0
                except: mat_pct = 100.0
                rv += qty * eff * mat_jbv * mat_pct / 100.0
            sell_price = (rv / portion) if (portion > 0 and rv > 0) else None
            item_pct   = None   # N/A for ore (refine value used instead)
        else:
            # Sell price: Jita JBV × per-item sell %
            pct_var = self._all_pcts.get(type_id)
            try:
                item_pct = float(pct_var.get()) if pct_var else (row['price_pct'] or 95.0)
            except ValueError:
                item_pct = row['price_pct'] or 95.0
            sell_price = (jita_jbv * item_pct / 100.0) if jita_jbv else None

        # Collateral basis
        if coll_basis == 'JSV':
            coll_val = jita_jsv
        elif coll_basis == 'Split':
            coll_val = ((jita_jbv + jita_jsv) / 2.0
                        if (jita_jbv and jita_jsv) else jita_jbv or jita_jsv)
        else:
            coll_val = jita_jbv
        collateral = (coll_val * coll_pct) if coll_val else 0.0
        ship_isk   = row['volume'] * isk_per_m3

        best_hub    = None
        best_margin = None
        for hub_name in HUB_ORDER:
            if not self.hub_vars[hub_name].get():
                continue
            if buy_mode == 'Buy Orders':
                bp          = row['hub_buy'].get(hub_name)
                broker_cost = (bp * broker_pct) if bp else 0.0
            else:
                bp          = row['hub_sell'].get(hub_name)
                broker_cost = 0.0

            if bp and bp > 0 and sell_price:
                m = (sell_price - bp - broker_cost - ship_isk - collateral) / bp * 100.0
                if best_margin is None or m > best_margin:
                    best_margin = m
                    best_hub    = hub_name

        # Max Buy Price: highest price you can pay per unit to still hit target_margin.
        # Derivation (solve for bp):
        #   (sell - bp - bp*broker_pct - ship - coll) / bp = target/100
        #   sell - ship - coll = bp * (1 + broker_pct + target/100)
        #   bp_max = (sell - ship - coll) / (1 + broker_pct + target/100)
        if sell_price and sell_price > 0:
            denominator = 1.0 + broker_pct + margin_target / 100.0
            max_buy = (sell_price - ship_isk - collateral) / denominator if denominator > 0 else None
            if max_buy and max_buy <= 0:
                max_buy = None
        else:
            max_buy = None

        # N-day deviation: compare current value to N-day average
        if db_cat in ORE_REFINE_CATEGORIES:
            # For ore: compare current refine value to avg refine value
            # (recompute refine value using N-day avg mineral prices)
            mats_d    = self._sde_materials.get(type_id, [])
            portion_d = self._sde_portions.get(type_id, 1)
            eff_d     = refine_eff / 100.0
            avg_rv    = 0.0
            all_mats_have_avg = bool(mats_d)
            for mat_id, qty in mats_d:
                avg_mat = self._avg_prices.get(mat_id)
                if not avg_mat:
                    all_mats_have_avg = False
                    break
                pv = self._all_pcts.get(mat_id)
                try:    mp = float(pv.get()) if pv else 100.0
                except: mp = 100.0
                avg_rv += qty * eff_d * avg_mat * mp / 100.0
            avg_value     = (avg_rv / portion_d) if (all_mats_have_avg and portion_d > 0 and avg_rv > 0) else None
            current_value = sell_price
        else:
            current_value = jita_jbv
            avg_value     = self._avg_prices.get(type_id)

        if current_value and avg_value and avg_value > 0:
            dev_pct = (current_value - avg_value) / avg_value * 100.0
        else:
            dev_pct = None

        return {**row,
                'item_pct':    item_pct,
                'sell_price':  sell_price,
                'ship_isk':    ship_isk,
                'collateral':  collateral,
                'best_hub':    best_hub,
                'best_margin': best_margin,
                'max_buy':     max_buy,
                'dev_pct':     dev_pct}

    def _row_sort_key(self, row, col):
        if col == 'name':     return (row['name'].lower(),)
        if col in HUB_COL_MAP:
            v = row['hub_sell'].get(HUB_COL_MAP[col])
            return (1 if v is None else 0, v or 0)
        if col == 'best_hub':  return (row['best_hub'] or '',)
        if col == 'margin':
            v = row['best_margin']
            return (1 if v is None else 0, -(v or 0))
        if col == 'max_buy':
            v = row['max_buy']
            return (1 if v is None else 0, -(v or 0))
        if col == 'dev':
            v = row.get('dev_pct')
            return (1 if v is None else 0, v or 0)
        return ('',)

    # ── Tree population ──────────────────────────────────────────────────────

    def _populate_tree(self, rows):
        self.tree.delete(*self.tree.get_children())

        for i, row in enumerate(rows):
            hs      = row['hub_sell']
            margin  = row['best_margin']
            dev_pct = row.get('dev_pct')

            vals = (
                row['name'],
                fmt_isk(hs.get('Amarr')),
                fmt_isk(hs.get('Rens')),
                fmt_isk(hs.get('Hek')),
                fmt_isk(hs.get('Dodixie')),
                fmt_isk(hs.get('Jita')),
                row['best_hub'] or '—',
                f'{margin:.1f}%' if margin is not None else '—',
                fmt_isk(row['max_buy']) if row['max_buy'] else '—',
                f'{dev_pct:+.1f}%' if dev_pct is not None else '—',
            )

            if margin is None:   colour = 'nodata'
            elif margin >= 10.0: colour = 'green'
            elif margin >= 0.0:  colour = 'yellow'
            else:                colour = 'red'

            tag_list = [colour]
            if dev_pct is not None and dev_pct > 5:
                tag_list.append('dev_high')
            elif dev_pct is not None and dev_pct < -5:
                tag_list.append('dev_low')
            if i % 2 == 1:
                tag_list.append('alt')
            self.tree.insert('', 'end', values=vals, tags=tuple(tag_list))

        n = len(rows)
        self._set_status(f'{n} item{"s" if n != 1 else ""} displayed')

    # ── Column sort ──────────────────────────────────────────────────────────

    def _sort_by(self, col):
        self._sort_rev = not self._sort_rev if self._sort_col == col else False
        self._sort_col = col
        self._apply_filter()

    # ── Fetch prices ─────────────────────────────────────────────────────────

    def _fetch_prices(self):
        script = os.path.join(PROJECT_DIR, 'scripts', 'fetch_hub_prices.py')
        if not os.path.exists(script):
            self._set_status('ERROR: scripts/fetch_hub_prices.py not found')
            return

        cat_display = self.cat_var.get()
        fetch_arg   = CATEGORY_FETCH_ARG.get(cat_display, 'import_all')
        label       = cat_display if cat_display != 'All' else 'All Categories'

        # Only fetch checked hubs; fall back to 'all' if everything is checked
        checked_hubs = [h.lower() for h in HUB_ORDER if self.hub_vars[h].get()]
        hubs_arg     = ','.join(checked_hubs) if checked_hubs else 'all'
        hubs_label   = ', '.join(h for h in HUB_ORDER if self.hub_vars[h].get()) or 'none'

        self.fetch_btn.configure(state='disabled', text='Fetching…')
        self._set_status(f'Fetching {label} [{hubs_label}] from ESI — this may take a few minutes…')

        def run():
            try:
                proc = subprocess.Popen(
                    [sys.executable, script, fetch_arg, hubs_arg],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, cwd=PROJECT_DIR)
                for line in proc.stdout:
                    msg = line.strip()
                    if msg:
                        self.root.after(0, lambda m=msg: self._set_status(m))
                proc.wait()
                if proc.returncode == 0:
                    self.root.after(0, self._on_fetch_done)
                else:
                    self.root.after(0, lambda: self._set_status('Fetch failed'))
                    self.root.after(0, lambda: self.fetch_btn.configure(
                        state='normal', text='⟳  Fetch Prices'))
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f'Error: {e}'))
                self.root.after(0, lambda: self.fetch_btn.configure(
                    state='normal', text='⟳  Fetch Prices'))

        threading.Thread(target=run, daemon=True).start()

    def _on_fetch_done(self):
        self.fetch_btn.configure(state='normal', text='⟳  Fetch Prices')
        self.load_data()

    def _set_status(self, msg):
        self.status_var.set(f'  {msg}')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    ImportTool(root)
    root.mainloop()


if __name__ == '__main__':
    main()
