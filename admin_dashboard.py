"""
Infinite Solutions - Admin Dashboard
Local GUI for managing buyback rates, viewing inventory, and deploying updates.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import subprocess
import os
import sys
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Predefined market item flags (shown as badges on the site)
ITEM_FLAGS = [
    ('out_of_stock', 'Out of Stock',   '#ff3333'),
    ('low_stock',    'Low Stock',      '#ff8844'),
    ('hot_item',     'Hot Item',       '#ff4444'),
    ('new_arrival',  'New Arrival',    '#44aaff'),
    ('limited',      'Limited Supply', '#cc66ff'),
    ('popular',      'Popular',        '#44cc88'),
]

# Map DB category names to display names (must match generate_buyback_data.py)
CATEGORY_DISPLAY = {
    'minerals': 'Minerals',
    'ice_products': 'Ice Products',
    'moon_materials': 'Reaction Materials',
    'gas_cloud_materials': 'Gas Cloud Materials',
    'research_equipment': 'Research Equipment',
    'pi_materials': 'Planetary Materials',
    'salvaged_materials': 'Salvaged Materials',
    'standard_ore': 'Standard Ore',
    'ice_ore': 'Ice Ore',
    'moon_ore': 'Moon Ore',
}
# Reverse lookup: display name -> DB category key
CATEGORY_DB_KEY = {v: k for k, v in CATEGORY_DISPLAY.items()}

# TEST Alliance Buyback competitor intel — Google Sheet source
_COMP_SHEET_ID = '1UGdb9mQIrdNprFN9_9g4WDYMh-C8fX5CTlhFBCV6bI4'
COMP_TABS = [
    ('Minerals, Gas',        '604363953'),
    ('Moon Goo, Composites', '498403852'),
    ('Ore, Ice',             '1641474510'),
    ('PI',                   '684077699'),
]
# DB categories covered by the competitor sheet (for tree tag colouring)
COMP_INTEL_CATEGORIES = {
    'minerals', 'ice_products', 'moon_materials', 'gas_cloud_materials', 'research_equipment', 'pi_materials',
    'standard_ore', 'ice_ore', 'moon_ore',
}

# Market tab visibility
MARKET_TAB_KEYS = ['minerals', 'ice_products', 'moon_materials', 'gas_cloud_materials', 'research_equipment', 'pi_materials', 'salvaged_materials']
MARKET_TAB_LABELS = {
    'minerals':            'Minerals',
    'ice_products':        'Ice Products',
    'moon_materials':      'Moon Materials',
    'gas_cloud_materials': 'Gas Cloud Materials',
    'research_equipment':  'Research Equipment',
    'pi_materials':        'Planetary Materials',
    'salvaged_materials':  'Salvaged Materials',
}

# Market subcategory definitions: (tab_key, sub_key, display_label)
MARKET_SUBTAB_DEFS = [
    ('ice_products',        'fuel_blocks',           'Fuel Blocks'),
    ('ice_products',        'refined_ice',           'Refined Ice'),
    ('ice_products',        'isotopes',              'Isotopes'),
    ('moon_materials',      'raw',                   'Raw'),
    ('moon_materials',      'processed',             'Processed'),
    ('moon_materials',      'advanced',              'Advanced'),
    ('gas_cloud_materials', 'compressed_fullerene',  'Compressed Fullerenes'),
    ('gas_cloud_materials', 'compressed_booster',    'Compressed Booster Gas'),
    ('gas_cloud_materials', 'uncompressed_fullerene','Uncompressed Fullerenes'),
    ('gas_cloud_materials', 'uncompressed_booster',  'Uncompressed Booster Gas'),
    ('research_equipment',  'datacores',             'Datacores'),
    ('research_equipment',  'decryptors',            'Decryptors'),
    ('pi_materials',        'p1',                    'P1'),
    ('pi_materials',        'p2',                    'P2'),
    ('pi_materials',        'p3',                    'P3'),
    ('pi_materials',        'p4',                    'P4'),
]


def _get_ice_subcat(display_order):
    if display_order is None: return ''
    if display_order <= 4:  return 'Fuel Blocks'
    if display_order <= 11: return 'Refined Ice'
    return 'Isotopes'


def _get_moon_subcat(display_order):
    if display_order is None: return ''
    if display_order <= 35:  return 'Raw'
    if display_order <= 124: return 'Processed'
    return 'Advanced'


def _get_gas_subcat(display_order):
    if display_order is None: return ''
    if display_order < 100:  return 'compressed_fullerene'
    if display_order < 200:  return 'compressed_booster'
    if display_order < 300:  return 'uncompressed_fullerene'
    return 'uncompressed_booster'


def _get_research_subcat(display_order):
    if display_order is None: return ''
    if display_order < 100:  return 'datacores'
    return 'decryptors'


PI_GROUP_MAP = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}


class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Infinite Solutions - Admin Dashboard")
        self.root.geometry("1100x750")
        self.root.configure(bg='#0a1520')
        self.root.minsize(900, 600)

        # Ore Import tab constants — defined here so they survive tab rebuilds
        self._ORE_MINERALS = [
            (34,    'Tritanium',  '95'), (35,    'Pyerite',   '95'),
            (36,    'Mexallon',   '98'), (37,    'Isogen',   '100'),
            (38,    'Nocxium',   '105'), (39,    'Zydrine',  '110'),
            (40,    'Megacyte',  '115'), (11399, 'Morphite', '120'),
        ]
        self._ORE_ICE_PRODUCTS = [
            (16272, 'Heavy Water',         '90'),
            (16273, 'Liquid Ozone',        '95'),
            (16274, 'Helium Isotopes',    '100'),
            (16275, 'Strontium Clath.',   '100'),
            (17887, 'Oxygen Isotopes',    '100'),
            (17888, 'Nitrogen Isotopes',  '100'),
            (17889, 'Hydrogen Isotopes',  '100'),
        ]
        self._ORE_MOON_MATERIALS = [
            # R4 processed moon materials
            (16633, 'Hydrocarbons',  '95', 'R4'),
            (16634, 'Atmo. Gases',   '95', 'R4'),
            (16635, 'Evaporate Dep.','95', 'R4'),
            (16636, 'Silicates',     '95', 'R4'),
            # R8 processed moon materials
            (16637, 'Tungsten',      '95', 'R8'),
            (16638, 'Titanium',      '95', 'R8'),
            (16639, 'Scandium',      '95', 'R8'),
            (16640, 'Cobalt',        '95', 'R8'),
            # R16 processed moon materials
            (16641, 'Chromium',      '95', 'R16'),
            (16642, 'Vanadium',      '95', 'R16'),
            (16643, 'Cadmium',       '95', 'R16'),
            (16644, 'Platinum',      '95', 'R16'),
            # R32 processed moon materials
            (16646, 'Mercury',       '95', 'R32'),
            (16647, 'Caesium',       '95', 'R32'),
            (16648, 'Hafnium',       '95', 'R32'),
            (16649, 'Technetium',    '95', 'R32'),
            # R64 processed moon materials
            (16650, 'Dysprosium',    '95', 'R64'),
            (16651, 'Neodymium',     '95', 'R64'),
            (16652, 'Promethium',    '95', 'R64'),
            (16653, 'Thulium',       '95', 'R64'),
        ]

        # Track unsaved changes
        self.unsaved_changes = {}

        # Competitor intel state (TEST Buyback stock — all sheet tabs)
        self._test_comp_stock = {}   # {tab_label: {item_name: qty}}
        self._test_pi_last_fetch = None

        # Item flags state
        self._item_flags_db = {}   # type_id -> set of active flag_keys
        self._pending_flags = set()  # flags for currently selected item(s) (unsaved)
        self._flags_selected_type_id = None  # type_id of single selected item
        self._flags_active_iids = []  # treeview iids of all selected items for bulk apply

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()

        # Build UI
        self.build_header()
        self.build_notebook()
        self._ensure_flags_table()
        self.load_data()

    def configure_styles(self):
        """Configure ttk styles to match the EVE Online theme."""
        s = self.style
        s.configure('Header.TLabel', background='#0a1520', foreground='#00ffff',
                     font=('Segoe UI', 20, 'bold'))
        s.configure('SubHeader.TLabel', background='#0a1520', foreground='#66d9ff',
                     font=('Segoe UI', 11))
        s.configure('TNotebook', background='#0d1117', borderwidth=0)
        s.configure('TNotebook.Tab', background='#1a2332', foreground='#66d9ff',
                     font=('Segoe UI', 11, 'bold'), padding=[20, 10])
        s.map('TNotebook.Tab',
              background=[('selected', '#0a3040')],
              foreground=[('selected', '#00ffff')])
        s.configure('TFrame', background='#0d1117')
        s.configure('Card.TFrame', background='#0a2030', relief='solid', borderwidth=1)
        s.configure('TLabel', background='#0d1117', foreground='#88d0e8',
                     font=('Segoe UI', 11))
        s.configure('Value.TLabel', background='#0d1117', foreground='#00ff88',
                     font=('Segoe UI', 11, 'bold'))
        s.configure('Warning.TLabel', background='#0d1117', foreground='#ff6666',
                     font=('Segoe UI', 11, 'bold'))
        s.configure('Action.TButton', background='#0a3040', foreground='#00ffff',
                     font=('Segoe UI', 11, 'bold'), padding=[20, 10])
        s.map('Action.TButton',
              background=[('active', '#0a4050'), ('pressed', '#0a5060')])
        s.configure('Deploy.TButton', background='#0a4020', foreground='#00ff88',
                     font=('Segoe UI', 12, 'bold'), padding=[25, 12])
        s.map('Deploy.TButton',
              background=[('active', '#0a5030'), ('pressed', '#0a6040')])
        s.configure('Save.TButton', background='#2a4060', foreground='#00d9ff',
                     font=('Segoe UI', 11, 'bold'), padding=[20, 10])
        s.map('Save.TButton',
              background=[('active', '#3a5070'), ('pressed', '#4a6080')])

        # Treeview styling
        s.configure('Treeview', background='#0d1a25', foreground='#c0e0f0',
                     fieldbackground='#0d1a25', font=('Segoe UI', 11), rowheight=32)
        s.configure('Treeview.Heading', background='#0a3040', foreground='#00d9ff',
                     font=('Segoe UI', 11, 'bold'))
        s.map('Treeview',
              background=[('selected', '#0a3050')],
              foreground=[('selected', '#00ffff')])

    def build_header(self):
        """Build the top header bar."""
        header_frame = ttk.Frame(self.root, style='TFrame')
        header_frame.pack(fill='x', padx=20, pady=(15, 5))

        ttk.Label(header_frame, text="INFINITE SOLUTIONS",
                  style='Header.TLabel').pack(side='left')

        # Status indicator
        self.status_label = ttk.Label(header_frame, text="All saved",
                                       style='SubHeader.TLabel')
        self.status_label.pack(side='right', padx=10)

    def build_notebook(self):
        """Build the tabbed interface."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=15, pady=10)

        # Tab 1: Market Rates
        self.rates_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.rates_frame, text='  Market Rates  ')
        self.build_rates_tab()

        # Tab 2: Buyback Program
        self.buyback_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.buyback_frame, text='  Buyback Program  ')
        self.build_buyback_tab()

        # Tab 3: Blueprint Library
        self.bp_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.bp_frame, text='  Blueprint Library  ', state='hidden')
        self.build_blueprint_tab()

        # Tab 4: Inventory Overview
        self.inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inventory_frame, text='  Inventory  ')
        self.build_inventory_tab()

        # Tab 5: Export Analysis
        self.export_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.export_frame, text='  Export Analysis  ')
        self.build_export_tab()


        # Tab 7: Ore Import Analysis
        self.ore_import_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ore_import_frame, text='  Ore Import  ')
        self.build_ore_import_tab()

        # Tab 8: Reaction Analysis
        self.reaction_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reaction_frame, text='  Reactions  ')
        self.build_reaction_tab()

        # Tab 9: Consignments
        self.consign_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.consign_frame, text='  Consignments  ')
        self._build_consignment_tab()

        # Tab 9: Slot Pricing
        self.slot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.slot_frame, text='  Slot Pricing  ')
        self._build_slot_pricing_tab()

        # Tab 10: Slot Manager
        self.slotmgr_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.slotmgr_frame, text='  Slot Manager  ')
        self._build_slot_manager_tab()

        # Tab 11: Quick Actions
        self.actions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.actions_frame, text='  Quick Actions  ')
        self.build_actions_tab()

        # Tab 12: Build Requests
        self.build_req_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.build_req_frame, text='  Build Requests  ')
        self._build_build_requests_tab()

    def build_rates_tab(self):
        """Build the Market Rates management tab."""
        # Top controls
        controls = ttk.Frame(self.rates_frame)
        controls.pack(fill='x', padx=15, pady=(15, 10))

        ttk.Label(controls, text="Adjust buyback rates for each item. Changes are highlighted until saved.",
                  style='SubHeader.TLabel').pack(side='left')

        btn_frame = ttk.Frame(controls)
        btn_frame.pack(side='right')

        self.save_btn = ttk.Button(btn_frame, text="Save Changes",
                                    style='Save.TButton', command=self.save_rates)
        self.save_btn.pack(side='left', padx=5)

        ttk.Button(btn_frame, text="Reset", style='Action.TButton',
                   command=self.load_data).pack(side='left', padx=5)

        # ── Market Visibility Panel ──────────────────────────────────────────
        self.market_tab_vars = {}
        self.market_subtab_vars = {}
        self.market_tab_btns = {}
        self.market_subtab_btns = {}

        vis_frame = ttk.Frame(self.rates_frame, style='Card.TFrame')
        vis_frame.pack(fill='x', padx=15, pady=(0, 8))

        # Title row: label left, Save button right
        hdr = ttk.Frame(vis_frame)
        hdr.pack(fill='x', padx=15, pady=(8, 6))
        ttk.Label(hdr, text="Market Visibility",
                  font=('Segoe UI', 10, 'bold'),
                  foreground='#00d9ff').pack(side='left')
        ttk.Button(hdr, text="Save Visibility", style='Save.TButton',
                   command=self.save_market_visibility).pack(side='right')

        # Per-tab section cards in an equal-width grid
        sections_row = ttk.Frame(vis_frame)
        sections_row.pack(fill='x', padx=15, pady=(0, 10))

        for col_i, tab_key in enumerate(MARKET_TAB_KEYS):
            sections_row.columnconfigure(col_i, weight=1)
            padx = (0, 8) if col_i < len(MARKET_TAB_KEYS) - 1 else 0

            sec = tk.Frame(sections_row, bg='#0a1525',
                           highlightbackground='#1e3a4a', highlightthickness=1)
            sec.grid(row=0, column=col_i, padx=padx, sticky='nsew')

            # Tab toggle button (full-width header)
            var = tk.BooleanVar(value=True)
            self.market_tab_vars[tab_key] = var
            btn = tk.Checkbutton(
                sec, text=MARKET_TAB_LABELS[tab_key], variable=var,
                font=('Segoe UI', 9, 'bold'),
                bg='#0a1525', fg='#00ff88', selectcolor='#0a1525',
                activebackground='#0a1525', activeforeground='#00ffff',
                indicatoron=False, relief='flat', bd=0,
                command=lambda k=tab_key: self._on_market_tab_toggle(k))
            btn.pack(fill='x', padx=6, pady=(6, 4))
            self.market_tab_btns[tab_key] = btn

            # Thin separator
            tk.Frame(sec, bg='#1e3a4a', height=1).pack(fill='x')

            # Subcategory toggles
            sub_frame = tk.Frame(sec, bg='#0a1525')
            sub_frame.pack(fill='x', padx=4, pady=(4, 6))
            subcats = [(sk, lbl) for (tk_, sk, lbl) in MARKET_SUBTAB_DEFS if tk_ == tab_key]
            for sub_key, label in subcats:
                var2 = tk.BooleanVar(value=True)
                self.market_subtab_vars[(tab_key, sub_key)] = var2
                btn2 = tk.Checkbutton(
                    sub_frame, text=label, variable=var2,
                    font=('Segoe UI', 8),
                    bg='#0a1525', fg='#00ff88', selectcolor='#0a1525',
                    activebackground='#0a1525', activeforeground='#00ffff',
                    indicatoron=False, relief='flat', bd=0,
                    command=lambda tk_=tab_key, sk=sub_key: self._on_market_subtab_toggle(tk_, sk))
                btn2.pack(side='left', padx=2)
                self.market_subtab_btns[(tab_key, sub_key)] = btn2

        # ── Competitor Intel Panel ──────────────────────────────────────────
        self._intel_expanded = False
        intel_card = tk.Frame(self.rates_frame, bg='#0d1e10',
                              highlightbackground='#2a3a1a', highlightthickness=1)
        intel_card.pack(fill='x', padx=15, pady=(0, 6))

        intel_hdr = tk.Frame(intel_card, bg='#0d1e10')
        intel_hdr.pack(fill='x', padx=8, pady=(4, 4))

        # Collapse/expand toggle
        self._intel_toggle_btn = tk.Button(
            intel_hdr, text='\u25b6', bg='#0d1e10', fg='#ffaa44',
            font=('Segoe UI', 8), relief='flat', padx=4, pady=0,
            activebackground='#0d1e10', activeforeground='#ffcc88',
            command=self._toggle_intel_panel)
        self._intel_toggle_btn.pack(side='left', padx=(0, 4))

        tk.Label(intel_hdr, text='TEST Buyback — Competitor Stock Intel',
                 bg='#0d1e10', fg='#ffaa44',
                 font=('Segoe UI', 9, 'bold')).pack(side='left')

        # Summary badge (shows alert counts when collapsed)
        self._intel_summary_lbl = tk.Label(intel_hdr, text='',
                                           bg='#0d1e10', fg='#ffcc66',
                                           font=('Segoe UI', 8))
        self._intel_summary_lbl.pack(side='left', padx=(8, 0))

        self._intel_last_lbl = tk.Label(intel_hdr, text='not fetched',
                                        bg='#0d1e10', fg='#445566',
                                        font=('Segoe UI', 8))
        self._intel_last_lbl.pack(side='left', padx=(10, 0))

        ctrl = tk.Frame(intel_hdr, bg='#0d1e10')
        ctrl.pack(side='right')
        tk.Label(ctrl, text='Flag \u2264', bg='#0d1e10', fg='#aabbcc',
                 font=('Segoe UI', 8)).pack(side='left', padx=(0, 3))
        self._intel_threshold_var = tk.IntVar(value=1000)
        tk.Spinbox(ctrl, from_=0, to=500000, increment=1000,
                   textvariable=self._intel_threshold_var,
                   width=7, font=('Segoe UI', 8),
                   bg='#0a1a0a', fg='#ffaa44', buttonbackground='#1a3020',
                   insertbackground='#ffaa44', justify='center').pack(side='left', padx=(0, 8))
        self._intel_threshold_var.trace_add('write', lambda *_: self._test_comp_apply_tree_tags())
        self._intel_refresh_btn = tk.Button(
            ctrl, text='\u21bb Refresh', bg='#1a3020', fg='#00ff88',
            font=('Segoe UI', 8), relief='flat', padx=8, pady=2,
            activebackground='#2a4030', activeforeground='#00ffaa',
            command=self._test_comp_refresh)
        self._intel_refresh_btn.pack(side='left')

        tk.Button(
            ctrl, text='\U0001f4ca Charts', bg='#1a2030', fg='#00d9ff',
            font=('Segoe UI', 8), relief='flat', padx=8, pady=2,
            activebackground='#2a3040', activeforeground='#44eeff',
            command=self._open_intel_charts).pack(side='left', padx=(6, 0))

        # Content area — hidden by default, shown when toggled
        self._intel_content = tk.Frame(intel_card, bg='#0d1e10')
        tk.Label(self._intel_content,
                 text='Click \u21bb Refresh to load competitor stock data',
                 bg='#0d1e10', fg='#334455',
                 font=('Segoe UI', 8, 'italic')).pack(pady=(2, 4))

        # Rates treeview
        tree_frame = ttk.Frame(self.rates_frame)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))

        columns = ('category', 'subcategory', 'item', 'current_rate', 'new_rate', 'corp_discount', 'flags')
        self.rates_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        selectmode='extended')

        self.rates_tree.heading('category',     text='Category')
        self.rates_tree.heading('subcategory',  text='Subcategory')
        self.rates_tree.heading('item',         text='Item Name')
        self.rates_tree.heading('current_rate', text='Alliance %')
        self.rates_tree.heading('new_rate',     text='New Alliance %')
        self.rates_tree.heading('corp_discount',text='Corp Discount  →  Corp Rate')
        self.rates_tree.heading('flags',        text='Flags')

        self.rates_tree.column('category',      width=120, anchor='center')
        self.rates_tree.column('subcategory',   width=110, anchor='center')
        self.rates_tree.column('item',          width=200)
        self.rates_tree.column('current_rate',  width=100, anchor='center')
        self.rates_tree.column('new_rate',      width=120, anchor='center')
        self.rates_tree.column('corp_discount', width=185, anchor='center')
        self.rates_tree.column('flags',         width=165)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.rates_tree.yview)
        self.rates_tree.configure(yscrollcommand=scrollbar.set)

        self.rates_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Rate editor panel (bottom) — two rows
        editor = ttk.Frame(self.rates_frame, style='Card.TFrame')
        editor.pack(fill='x', padx=15, pady=(0, 15))

        # ── Row 1: item label + Alliance Rate controls ─────────────────────
        row1 = ttk.Frame(editor)
        row1.pack(fill='x', padx=20, pady=(12, 4))

        ttk.Label(row1, text="Selected Item:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 8))

        self.selected_item_label = ttk.Label(row1, text="(click a row above)",
                                              style='Value.TLabel')
        self.selected_item_label.pack(side='left', padx=(0, 28))

        ttk.Label(row1, text="Alliance %:",
                  font=('Segoe UI', 11, 'bold')).pack(side='left', padx=(0, 5))

        self.rate_var = tk.IntVar(value=98)
        self.rate_spinbox = tk.Spinbox(row1, from_=80, to=110,
                                        textvariable=self.rate_var,
                                        width=5, font=('Segoe UI', 14, 'bold'),
                                        bg='#0a2030', fg='#00ffff',
                                        buttonbackground='#1a3040',
                                        insertbackground='#00ffff',
                                        justify='center')
        self.rate_spinbox.pack(side='left', padx=(0, 8))

        ttk.Button(row1, text="Apply", style='Action.TButton',
                   command=self.apply_rate_change).pack(side='left', padx=5)

        ttk.Label(row1, text="Quick:",
                  font=('Segoe UI', 10)).pack(side='left', padx=(18, 4))
        for pct in [95, 96, 97, 98, 99, 100, 101]:
            btn = tk.Button(row1, text=f"{pct}%", width=4,
                           font=('Segoe UI', 10, 'bold'),
                           bg='#1a3040', fg='#00d9ff', relief='flat',
                           activebackground='#2a4050', activeforeground='#00ffff',
                           command=lambda p=pct: self.quick_set_rate(p))
            btn.pack(side='left', padx=2)

        # ── Row 2: Corp Discount controls + live Corp Rate readout ─────────
        row2 = ttk.Frame(editor)
        row2.pack(fill='x', padx=20, pady=(0, 12))

        ttk.Label(row2, text="Corp Discount %:",
                  font=('Segoe UI', 11, 'bold')).pack(side='left', padx=(0, 5))

        self.discount_var = tk.IntVar(value=2)
        self.discount_spinbox = tk.Spinbox(row2, from_=0, to=20,
                                            textvariable=self.discount_var,
                                            width=5, font=('Segoe UI', 14, 'bold'),
                                            bg='#0a2030', fg='#ffd700',
                                            buttonbackground='#1a3040',
                                            insertbackground='#ffd700',
                                            justify='center')
        self.discount_spinbox.pack(side='left', padx=(0, 8))

        ttk.Button(row2, text="Apply", style='Action.TButton',
                   command=self.apply_discount_change).pack(side='left', padx=5)

        ttk.Label(row2, text="Quick:",
                  font=('Segoe UI', 10)).pack(side='left', padx=(18, 4))
        for d in [0, 1, 2, 3, 4, 5]:
            btn = tk.Button(row2, text=f"{d}%", width=4,
                           font=('Segoe UI', 10, 'bold'),
                           bg='#1a3040', fg='#ffd700', relief='flat',
                           activebackground='#2a4050', activeforeground='#ffee88',
                           command=lambda dd=d: self.quick_set_discount(dd))
            btn.pack(side='left', padx=2)

        # Live corp rate readout
        ttk.Label(row2, text="→  Corp Rate:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(22, 5))
        self.corp_rate_label = ttk.Label(row2, text="—",
                                          font=('Segoe UI', 13, 'bold'),
                                          foreground='#ffd700')
        self.corp_rate_label.pack(side='left')

        # Update corp rate label whenever either spinbox changes
        self.rate_var.trace_add('write', lambda *_: self._refresh_corp_rate_label())
        self.discount_var.trace_add('write', lambda *_: self._refresh_corp_rate_label())

        # ── Row 3: Item flags ──────────────────────────────────────────────
        row3 = ttk.Frame(editor)
        row3.pack(fill='x', padx=20, pady=(0, 12))

        self._flags_label = ttk.Label(row3, text="Flags:",
                                       font=('Segoe UI', 10, 'bold'))
        self._flags_label.pack(side='left', padx=(0, 8))

        self._flag_btns = {}
        for flag_key, flag_label, flag_color in ITEM_FLAGS:
            btn = tk.Button(row3, text=flag_label,
                            font=('Segoe UI', 9), width=13,
                            bg='#1a2030', fg='#445566', relief='flat', padx=4,
                            activebackground='#2a3040', activeforeground=flag_color,
                            command=lambda k=flag_key: self._toggle_flag_btn(k))
            btn.pack(side='left', padx=2)
            self._flag_btns[flag_key] = btn

        ttk.Button(row3, text="Apply Flags", style='Action.TButton',
                   command=self._apply_item_flags).pack(side='left', padx=(14, 0))

        # Bind selection
        self.rates_tree.bind('<<TreeviewSelect>>', self.on_rate_select)

    def build_buyback_tab(self):
        """Build the Buyback Program management tab."""
        # Track unsaved buyback changes separately
        self.unsaved_buyback_changes = {}

        # Buyback category names (must match what the website uses)
        self.buyback_categories = [
            'Minerals', 'Ice Products', 'Reaction Materials',
            'Salvaged Materials', 'Gas Cloud Materials', 'Research Equipment', 'Planetary Materials',
            'Standard Ore', 'Ice Ore', 'Moon Ore',
        ]
        self._ore_categories = {'Standard Ore', 'Ice Ore', 'Moon Ore'}
        self.buyback_category_vars = {}  # BooleanVar per category (True = visible)

        # Top controls
        controls = ttk.Frame(self.buyback_frame)
        controls.pack(fill='x', padx=15, pady=(15, 10))

        ttk.Label(controls, text="Manage buyback rates and accepted items. These rates appear on the Buyback tab.",
                  style='SubHeader.TLabel').pack(side='left')

        btn_frame = ttk.Frame(controls)
        btn_frame.pack(side='right')

        self.bb_save_btn = ttk.Button(btn_frame, text="Save Changes",
                                       style='Save.TButton', command=self.save_buyback_rates)
        self.bb_save_btn.pack(side='left', padx=5)

        ttk.Button(btn_frame, text="Reset", style='Action.TButton',
                   command=self.load_buyback_data).pack(side='left', padx=5)

        # Program info bar
        info_frame = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        info_frame.pack(fill='x', padx=15, pady=(0, 10))

        info_inner = ttk.Frame(info_frame)
        info_inner.pack(fill='x', padx=20, pady=12)

        ttk.Label(info_inner, text="Payout Location:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 5))
        ttk.Label(info_inner, text="LX-ZOJ Tatara  |  Contract to Rax Hakaari  |  Payouts within 24 hours",
                  style='Value.TLabel').pack(side='left', padx=(0, 30))

        self.bb_accepted_label = ttk.Label(info_inner, text="Accepted: --/-- items",
                                            font=('Segoe UI', 11, 'bold'),
                                            foreground='#00d9ff')
        self.bb_accepted_label.pack(side='right')

        # Category visibility toggles (two rows: materials + ores)
        cat_frame = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        cat_frame.pack(fill='x', padx=15, pady=(0, 10))

        self.category_toggle_btns = {}
        for row_cats, label_text, pady_args in [
            ([c for c in self.buyback_categories if c not in self._ore_categories],
             "Category Visibility:", (10, 4)),
            ([c for c in self.buyback_categories if c in self._ore_categories],
             "Ore Visibility:", (4, 10)),
        ]:
            cat_inner = ttk.Frame(cat_frame)
            cat_inner.pack(fill='x', padx=15, pady=pady_args)
            ttk.Label(cat_inner, text=label_text,
                      font=('Segoe UI', 11, 'bold'),
                      foreground='#00d9ff').pack(side='left', padx=(0, 15))
            for cat_name in row_cats:
                var = tk.BooleanVar(value=True)
                self.buyback_category_vars[cat_name] = var
                btn = tk.Checkbutton(cat_inner, text=cat_name,
                                      variable=var,
                                      font=('Segoe UI', 10, 'bold'),
                                      bg='#0d1117', fg='#00ff88',
                                      selectcolor='#0a2030',
                                      activebackground='#0d1117',
                                      activeforeground='#00ffff',
                                      indicatoron=False,
                                      width=16, height=1,
                                      relief='flat', bd=1,
                                      command=lambda c=cat_name: self._on_category_toggle(c))
                btn.pack(side='left', padx=3)
                self.category_toggle_btns[cat_name] = btn

        # Pricing method per category
        price_frame = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        price_frame.pack(fill='x', padx=15, pady=(0, 10))

        self.pricing_method_vars = {}
        self.pricing_method_combos = {}
        pricing_methods = ['Jita Buy', 'Jita Sell', 'Jita Split']

        non_ore_cats = [c for c in self.buyback_categories if c not in self._ore_categories]
        ore_cats = [c for c in self.buyback_categories if c in self._ore_categories]

        # Row 1: non-ore pricing methods
        price_inner1 = ttk.Frame(price_frame)
        price_inner1.pack(fill='x', padx=15, pady=(10, 4))
        ttk.Label(price_inner1, text="Pricing Method:",
                  font=('Segoe UI', 11, 'bold'),
                  foreground='#00d9ff').pack(side='left', padx=(0, 15))
        for cat_name in non_ore_cats:
            frame = ttk.Frame(price_inner1)
            frame.pack(side='left', padx=5)
            ttk.Label(frame, text=cat_name + ":",
                      font=('Segoe UI', 9),
                      foreground='#6fb3d0').pack(side='left', padx=(0, 3))
            var = tk.StringVar(value='Jita Buy')
            self.pricing_method_vars[cat_name] = var
            combo = ttk.Combobox(frame, textvariable=var,
                                  values=pricing_methods, state='readonly',
                                  width=9, font=('Segoe UI', 9))
            combo.pack(side='left')
            combo.bind('<<ComboboxSelected>>',
                       lambda e, c=cat_name: self._on_pricing_method_change(c))
            self.pricing_method_combos[cat_name] = combo

        # Row 2: ore pricing methods + refining efficiency
        price_inner2 = ttk.Frame(price_frame)
        price_inner2.pack(fill='x', padx=15, pady=(4, 10))
        ttk.Label(price_inner2, text="Ore Pricing:",
                  font=('Segoe UI', 11, 'bold'),
                  foreground='#00d9ff').pack(side='left', padx=(0, 15))
        for cat_name in ore_cats:
            frame = ttk.Frame(price_inner2)
            frame.pack(side='left', padx=5)
            ttk.Label(frame, text=cat_name + ":",
                      font=('Segoe UI', 9),
                      foreground='#6fb3d0').pack(side='left', padx=(0, 3))
            var = tk.StringVar(value='Jita Buy')
            self.pricing_method_vars[cat_name] = var
            combo = ttk.Combobox(frame, textvariable=var,
                                  values=pricing_methods, state='readonly',
                                  width=9, font=('Segoe UI', 9))
            combo.pack(side='left')
            combo.bind('<<ComboboxSelected>>',
                       lambda e, c=cat_name: self._on_pricing_method_change(c))
            self.pricing_method_combos[cat_name] = combo

        # Refining efficiency (ore mineral value calculation)
        eff_frame = ttk.Frame(price_inner2)
        eff_frame.pack(side='right', padx=(20, 0))
        ttk.Label(eff_frame, text="Refining Efficiency %:",
                  font=('Segoe UI', 9),
                  foreground='#6fb3d0').pack(side='left', padx=(0, 5))
        self.bb_refining_eff_var = tk.DoubleVar(value=90.63)
        eff_spin = tk.Spinbox(eff_frame, from_=50.0, to=100.0, increment=0.01,
                              textvariable=self.bb_refining_eff_var,
                              width=6, font=('Segoe UI', 9, 'bold'),
                              bg='#0a2030', fg='#00ff88',
                              buttonbackground='#1a3040',
                              insertbackground='#00ff88',
                              justify='center',
                              format='%.2f')
        eff_spin.pack(side='left')
        eff_spin.bind('<FocusOut>', lambda e: self._check_bb_category_unsaved())
        eff_spin.bind('<Return>', lambda e: self._check_bb_category_unsaved())

        # Buyback items treeview
        tree_frame = ttk.Frame(self.buyback_frame)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))

        columns = ('category', 'item', 'buyback_rate', 'new_rate', 'quota', 'accepted')
        self.bb_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                     selectmode='extended')

        self.bb_tree.heading('category', text='Category')
        self.bb_tree.heading('item', text='Item Name')
        self.bb_tree.heading('buyback_rate', text='Current Rate')
        self.bb_tree.heading('new_rate', text='New Rate (%)')
        self.bb_tree.heading('quota', text='Quota')
        self.bb_tree.heading('accepted', text='Accepted')

        self.bb_tree.column('category', width=120, anchor='center')
        self.bb_tree.column('item', width=240)
        self.bb_tree.column('buyback_rate', width=100, anchor='center')
        self.bb_tree.column('new_rate', width=100, anchor='center')
        self.bb_tree.column('quota', width=110, anchor='center')
        self.bb_tree.column('accepted', width=90, anchor='center')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.bb_tree.yview)
        self.bb_tree.configure(yscrollcommand=scrollbar.set)

        self.bb_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Editor panel (bottom)
        editor = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        editor.pack(fill='x', padx=15, pady=(0, 15))

        inner = ttk.Frame(editor)
        inner.pack(padx=20, pady=15)

        ttk.Label(inner, text="Selected:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 10))

        self.bb_selected_label = ttk.Label(inner, text="(click a row above)",
                                            style='Value.TLabel')
        self.bb_selected_label.pack(side='left', padx=(0, 20))

        ttk.Label(inner, text="Buyback Rate %:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 5))

        self.bb_rate_var = tk.IntVar(value=98)
        self.bb_rate_spinbox = tk.Spinbox(inner, from_=80, to=100,
                                           textvariable=self.bb_rate_var,
                                           width=5, font=('Segoe UI', 14, 'bold'),
                                           bg='#0a2030', fg='#00ffff',
                                           buttonbackground='#1a3040',
                                           insertbackground='#00ffff',
                                           justify='center')
        self.bb_rate_spinbox.pack(side='left', padx=(0, 10))

        ttk.Button(inner, text="Apply", style='Action.TButton',
                   command=self.apply_bb_rate_change).pack(side='left', padx=5)

        # Quota
        ttk.Label(inner, text="Quota:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(20, 5))

        self.bb_quota_var = tk.StringVar(value="0")
        self.bb_quota_spinbox = tk.Spinbox(inner, from_=0, to=999999999,
                                            textvariable=self.bb_quota_var,
                                            increment=10000,
                                            width=10, font=('Segoe UI', 12, 'bold'),
                                            bg='#0a2030', fg='#00ffff',
                                            buttonbackground='#1a3040',
                                            insertbackground='#00ffff',
                                            justify='center')
        self.bb_quota_spinbox.pack(side='left', padx=(0, 5))

        ttk.Button(inner, text="Set Quota", style='Action.TButton',
                   command=self.apply_bb_quota_change).pack(side='left', padx=5)

        # Presets
        ttk.Label(inner, text="Presets:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(15, 5))

        for pct in [95, 96, 97, 98]:
            btn = tk.Button(inner, text=f"{pct}%", width=4,
                           font=('Segoe UI', 10, 'bold'),
                           bg='#1a3040', fg='#00d9ff', relief='flat',
                           activebackground='#2a4050', activeforeground='#00ffff',
                           command=lambda p=pct: self.quick_set_bb_rate(p))
            btn.pack(side='left', padx=2)

        # Toggle accepted button
        self.bb_toggle_btn = tk.Button(inner, text="Toggle Accepted", width=14,
                                        font=('Segoe UI', 10, 'bold'),
                                        bg='#2a4020', fg='#00ff88', relief='flat',
                                        activebackground='#3a5030', activeforeground='#00ffaa',
                                        command=self.toggle_bb_accepted)
        self.bb_toggle_btn.pack(side='left', padx=(20, 0))

        # Bind selection
        self.bb_tree.bind('<<TreeviewSelect>>', self.on_bb_select)

    def build_blueprint_tab(self):
        """Build the Blueprint Library management tab."""
        self.unsaved_bp_changes = {}

        # Use a PanedWindow to split pricing params (top) and blueprint list (bottom)
        paned = ttk.PanedWindow(self.bp_frame, orient='vertical')
        paned.pack(fill='both', expand=True, padx=15, pady=(15, 15))

        # === TOP SECTION: Calculator Settings ===
        params_frame = ttk.Frame(paned)
        paned.add(params_frame, weight=0)

        params_header = ttk.Frame(params_frame)
        params_header.pack(fill='x', pady=(0, 10))

        ttk.Label(params_header, text="Calculator Settings",
                  font=('Segoe UI', 13, 'bold'),
                  foreground='#00d9ff').pack(side='left')

        ttk.Label(params_header, text="Controls the BPC Cost Calculator popup on the Blueprint Library page",
                  style='SubHeader.TLabel').pack(side='left', padx=(15, 0))

        self.bp_save_btn = ttk.Button(params_header, text="Save All",
                                       style='Save.TButton', command=self.save_blueprint_settings)
        self.bp_save_btn.pack(side='right', padx=5)

        # Settings row
        param_grid = ttk.Frame(params_frame)
        param_grid.pack(fill='x')

        row1 = ttk.Frame(param_grid)
        row1.pack(fill='x', pady=3)

        self.calc_default_runs_var = tk.IntVar(value=10)
        self._bp_param_field(row1, "Default Runs:", self.calc_default_runs_var, 1, 300)

        self.calc_max_runs_var = tk.IntVar(value=300)
        self._bp_param_field(row1, "Max Runs:", self.calc_max_runs_var, 1, 1000)

        self.calc_default_copies_var = tk.IntVar(value=1)
        self._bp_param_field(row1, "Default Copies:", self.calc_default_copies_var, 1, 100)

        self.calc_max_copies_var = tk.IntVar(value=100)
        self._bp_param_field(row1, "Max Copies:", self.calc_max_copies_var, 1, 500)

        row2 = ttk.Frame(param_grid)
        row2.pack(fill='x', pady=3)

        ttk.Label(row2, text="Facility Name:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(15, 5))

        self.calc_facility_var = tk.StringVar(value="Azbel in LX-ZOJ")
        facility_entry = tk.Entry(row2, textvariable=self.calc_facility_var,
                                   font=('Segoe UI', 12), width=25,
                                   bg='#0a2030', fg='#00ffff',
                                   insertbackground='#00ffff')
        facility_entry.pack(side='left', padx=(0, 20))

        self.calc_lock_bpc_runs_var = tk.BooleanVar(value=True)
        lock_cb = tk.Checkbutton(row2, text="Lock runs for BPCs",
                                  variable=self.calc_lock_bpc_runs_var,
                                  font=('Segoe UI', 11),
                                  bg='#0d1117', fg='#88d0e8',
                                  selectcolor='#0a2030',
                                  activebackground='#0d1117',
                                  activeforeground='#00ffff')
        lock_cb.pack(side='left', padx=(0, 15))

        self.calc_lock_bpc_copies_var = tk.BooleanVar(value=True)
        lock_copies_cb = tk.Checkbutton(row2, text="Lock copies for BPCs",
                                         variable=self.calc_lock_bpc_copies_var,
                                         font=('Segoe UI', 11),
                                         bg='#0d1117', fg='#88d0e8',
                                         selectcolor='#0a2030',
                                         activebackground='#0d1117',
                                         activeforeground='#00ffff')
        lock_copies_cb.pack(side='left')

        # Separator
        ttk.Separator(params_frame, orient='horizontal').pack(fill='x', pady=8)

        # === BOTTOM SECTION: Blueprint Visibility ===
        bp_list_frame = ttk.Frame(paned)
        paned.add(bp_list_frame, weight=1)

        list_header = ttk.Frame(bp_list_frame)
        list_header.pack(fill='x', pady=(0, 8))

        ttk.Label(list_header, text="Blueprint Visibility",
                  font=('Segoe UI', 13, 'bold'),
                  foreground='#00d9ff').pack(side='left')

        self.bp_count_label = ttk.Label(list_header, text="Showing: --/--",
                                         font=('Segoe UI', 11, 'bold'),
                                         foreground='#00ff88')
        self.bp_count_label.pack(side='right', padx=10)

        # Search bar
        search_frame = ttk.Frame(bp_list_frame)
        search_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(search_frame, text="Search:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 5))

        self.bp_search_var = tk.StringVar()
        self.bp_search_var.trace_add('write', lambda *_: self.filter_blueprint_list())
        search_entry = tk.Entry(search_frame, textvariable=self.bp_search_var,
                                font=('Segoe UI', 12), width=30,
                                bg='#0a2030', fg='#00ffff',
                                insertbackground='#00ffff')
        search_entry.pack(side='left', padx=(0, 15))

        # Filter by type
        ttk.Label(search_frame, text="Type:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 5))

        self.bp_type_var = tk.StringVar(value='All')
        type_combo = ttk.Combobox(search_frame, textvariable=self.bp_type_var,
                                   values=['All', 'BPO', 'BPC'], state='readonly', width=6)
        type_combo.pack(side='left', padx=(0, 15))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_blueprint_list())

        # Toggle button
        tk.Button(search_frame, text="Toggle Selected", width=14,
                 font=('Segoe UI', 10, 'bold'),
                 bg='#2a4020', fg='#00ff88', relief='flat',
                 activebackground='#3a5030', activeforeground='#00ffaa',
                 command=self.toggle_bp_visibility).pack(side='left', padx=5)

        tk.Button(search_frame, text="Hide Selected", width=12,
                 font=('Segoe UI', 10, 'bold'),
                 bg='#402020', fg='#ff6666', relief='flat',
                 activebackground='#503030', activeforeground='#ff8888',
                 command=lambda: self.set_bp_visibility(False)).pack(side='left', padx=2)

        tk.Button(search_frame, text="Show Selected", width=12,
                 font=('Segoe UI', 10, 'bold'),
                 bg='#1a3040', fg='#00d9ff', relief='flat',
                 activebackground='#2a4050', activeforeground='#00ffff',
                 command=lambda: self.set_bp_visibility(True)).pack(side='left', padx=2)

        # Treeview
        tree_frame = ttk.Frame(bp_list_frame)
        tree_frame.pack(fill='both', expand=True)

        columns = ('name', 'type', 'category', 'me', 'te', 'visible')
        self.bp_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                     selectmode='extended')

        self.bp_tree.heading('name', text='Blueprint Name')
        self.bp_tree.heading('type', text='Type')
        self.bp_tree.heading('category', text='Category')
        self.bp_tree.heading('me', text='ME')
        self.bp_tree.heading('te', text='TE')
        self.bp_tree.heading('visible', text='Visible')

        self.bp_tree.column('name', width=300)
        self.bp_tree.column('type', width=60, anchor='center')
        self.bp_tree.column('category', width=150, anchor='center')
        self.bp_tree.column('me', width=50, anchor='center')
        self.bp_tree.column('te', width=50, anchor='center')
        self.bp_tree.column('visible', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.bp_tree.yview)
        self.bp_tree.configure(yscrollcommand=scrollbar.set)

        self.bp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.bp_tree.tag_configure('hidden', foreground='#555555')

    def _bp_param_field(self, parent, label, var, min_val, max_val, width=5, increment=1.0):
        """Create a labeled spinbox for a calculator parameter."""
        ttk.Label(parent, text=label,
                  font=('Segoe UI', 11)).pack(side='left', padx=(15, 3))
        spinbox = tk.Spinbox(parent, from_=min_val, to=max_val,
                              textvariable=var, increment=increment,
                              width=width, font=('Segoe UI', 12, 'bold'),
                              bg='#0a2030', fg='#00ffff',
                              buttonbackground='#1a3040',
                              insertbackground='#00ffff',
                              justify='center')
        spinbox.pack(side='left', padx=(0, 10))

    def build_inventory_tab(self):
        """Build the Inventory overview tab."""
        controls = ttk.Frame(self.inventory_frame)
        controls.pack(fill='x', padx=15, pady=(15, 10))

        ttk.Label(controls, text="Current LX-ZOJ Station Inventory",
                  style='SubHeader.TLabel').pack(side='left')

        ttk.Button(controls, text="Refresh", style='Action.TButton',
                   command=self.load_inventory).pack(side='right')

        # Inventory treeview
        tree_frame = ttk.Frame(self.inventory_frame)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        columns = ('category', 'item', 'quantity', 'status')
        self.inv_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                      selectmode='browse')

        self.inv_tree.heading('category', text='Category')
        self.inv_tree.heading('item', text='Item Name')
        self.inv_tree.heading('quantity', text='Quantity')
        self.inv_tree.heading('status', text='Status')

        self.inv_tree.column('category', width=150, anchor='center')
        self.inv_tree.column('item', width=300)
        self.inv_tree.column('quantity', width=200, anchor='e')
        self.inv_tree.column('status', width=120, anchor='center')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=scrollbar.set)

        self.inv_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def build_actions_tab(self):
        """Build the Quick Actions tab."""
        container = ttk.Frame(self.actions_frame)
        container.pack(fill='both', expand=True, padx=30, pady=30)

        ttk.Label(container, text="Quick Actions",
                  style='Header.TLabel').pack(anchor='w', pady=(0, 20))

        actions = [
            ("Update Inventory", "Fetch latest inventory from ESI and update the website",
             self.action_update_inventory),
            ("Generate Stock Image", "Create a Discord-ready PNG of current stock (stock_image.png)",
             self.action_generate_stock_image),
            ("Generate Fuel Image", "Create a Discord-ready PNG of fuel/ice products (fuel_image.png)",
             self.action_generate_fuel_image),
            ("Generate Buyback Image", "Create a Discord-ready PNG of accepted buyback items and quotas (buyback_image.png)",
             self.action_generate_buyback_image),
            ("Generate Catalog Images", "Create per-category Discord PNGs showing prices (catalog_*.png)",
             self.action_generate_catalog_images),
            ("Update Blueprints", "Refresh blueprint data, BPC pricing, and research jobs",
             self.action_update_blueprints),
            ("Deploy to Live", "Push current changes to GitHub (makes them live)",
             self.action_deploy),
        ]

        for title, desc, cmd in actions:
            frame = ttk.Frame(container, style='Card.TFrame')
            frame.pack(fill='x', pady=8)

            inner = ttk.Frame(frame)
            inner.pack(fill='x', padx=20, pady=15)

            text_frame = ttk.Frame(inner)
            text_frame.pack(side='left', fill='x', expand=True)

            ttk.Label(text_frame, text=title,
                      font=('Segoe UI', 13, 'bold'),
                      foreground='#00d9ff').pack(anchor='w')
            ttk.Label(text_frame, text=desc,
                      font=('Segoe UI', 10),
                      foreground='#6fb3d0').pack(anchor='w')

            style = 'Deploy.TButton' if 'Deploy' in title else 'Action.TButton'
            btn = ttk.Button(inner, text="Run", style=style,
                             command=cmd)
            btn.pack(side='right', padx=10)
            if title == "Update Inventory":
                self._inv_action_btn = btn

        # Last updated info
        self.last_updated_label = ttk.Label(container, text="",
                                             style='SubHeader.TLabel')
        self.last_updated_label.pack(anchor='w', pady=(30, 0))

    # ===== CONFIG HELPERS =====

    def _get_config(self, key, default=''):
        """Read a single value from site_config, returning default if missing."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM site_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else default
        except Exception:
            return default

    def _set_config(self, key, value):
        """Persist a single key/value to site_config, silently ignoring errors."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ===== DATA LOADING =====

    def load_data(self):
        """Load all data from database."""
        self.unsaved_changes = {}
        self.unsaved_buyback_changes = {}
        self.unsaved_bp_changes = {}
        self.update_status("All saved")
        self.load_rates()
        self.load_market_visibility()
        self.load_buyback_data()
        self.load_blueprint_settings()
        self.load_inventory()
        self.load_export_data()

    def load_rates(self):
        """Load buyback rates from tracked_market_items."""
        self.rates_tree.delete(*self.rates_tree.get_children())

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tmi.id, tmi.type_id, tmi.type_name, tmi.category,
                   tmi.price_percentage, tmi.alliance_discount,
                   tmi.display_order, it.market_group_id
            FROM tracked_market_items tmi
            LEFT JOIN inv_types it ON tmi.type_id = it.type_id
            ORDER BY tmi.category, tmi.display_order, tmi.type_name
        """)
        rows = cursor.fetchall()

        # Load flags cache
        try:
            flag_rows = cursor.execute(
                "SELECT type_id, flag_key FROM item_flags"
            ).fetchall()
            self._item_flags_db = {}
            for tid, fk in flag_rows:
                self._item_flags_db.setdefault(tid, set()).add(fk)
        except Exception:
            self._item_flags_db = {}

        conn.close()

        flag_labels = {key: label for key, label, _ in ITEM_FLAGS}

        self.rate_items = {}
        for row_id, type_id, name, category, pct, discount, display_order, mkt_group_id in rows:
            cat_display = CATEGORY_DISPLAY.get(category, category.replace('_', ' ').title())

            if category == 'ice_products':
                subcat = _get_ice_subcat(display_order)
            elif category == 'moon_materials':
                subcat = _get_moon_subcat(display_order)
            elif category == 'gas_cloud_materials':
                subcat = _get_gas_subcat(display_order)
            elif category == 'research_equipment':
                subcat = _get_research_subcat(display_order)
            elif category == 'pi_materials':
                subcat = PI_GROUP_MAP.get(mkt_group_id, '')
            else:
                subcat = ''

            corp_rate = (pct or 0) - (discount or 0)
            active_flags = self._item_flags_db.get(type_id, set())
            flags_str = ', '.join(
                flag_labels[k] for k, _, _ in ITEM_FLAGS if k in active_flags
            )
            iid = self.rates_tree.insert('', 'end', values=(
                cat_display, subcat, name, f"{pct}%", f"{pct}%",
                f"-{discount}%  →  {corp_rate}%", flags_str
            ))
            self.rate_items[iid] = {
                'id': row_id, 'type_id': type_id, 'name': name,
                'category': category, 'rate': pct, 'discount': discount
            }

        self._test_comp_apply_tree_tags()

    def load_market_visibility(self):
        """Load market tab/subtab visibility settings from site_config."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value FROM site_config
                WHERE key LIKE 'market_tab_%' OR key LIKE 'market_sub_%'
            """)
            rows = {k: v for k, v in cursor.fetchall()}
            conn.close()
        except Exception:
            rows = {}

        for tab_key in MARKET_TAB_KEYS:
            visible = rows.get(f'market_tab_{tab_key}', '1') == '1'
            self.market_tab_vars[tab_key].set(visible)
            self._on_market_tab_toggle(tab_key)

        for tab_key, sub_key, _ in MARKET_SUBTAB_DEFS:
            visible = rows.get(f'market_sub_{tab_key}_{sub_key}', '1') == '1'
            self.market_subtab_vars[(tab_key, sub_key)].set(visible)
            self._on_market_subtab_toggle(tab_key, sub_key)

    def _on_market_tab_toggle(self, tab_key):
        """Update button colour when a market tab visibility toggle changes."""
        visible = self.market_tab_vars[tab_key].get()
        self.market_tab_btns[tab_key].configure(
            fg='#00ff88' if visible else '#ff6666')

    def _on_market_subtab_toggle(self, tab_key, sub_key):
        """Update button colour when a subcategory visibility toggle changes."""
        visible = self.market_subtab_vars[(tab_key, sub_key)].get()
        self.market_subtab_btns[(tab_key, sub_key)].configure(
            fg='#00ff88' if visible else '#ff6666')

    def save_market_visibility(self):
        """Persist market tab/subtab visibility to site_config and regenerate data."""
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()
            for tab_key in MARKET_TAB_KEYS:
                value = '1' if self.market_tab_vars[tab_key].get() else '0'
                cursor.execute(
                    "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                    (f'market_tab_{tab_key}', value))
            for tab_key, sub_key, _ in MARKET_SUBTAB_DEFS:
                value = '1' if self.market_subtab_vars[(tab_key, sub_key)].get() else '0'
                cursor.execute(
                    "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                    (f'market_sub_{tab_key}_{sub_key}', value))
            conn.commit()
            conn.close()
            self.update_status("Market visibility saved")
        except Exception as e:
            self.update_status(f"Error saving visibility: {e}")
            return

        # Regenerate buyback_data.js in background thread
        import threading
        def _regen():
            try:
                subprocess.run(
                    ['python', os.path.join(PROJECT_DIR, 'generate_buyback_data.py')],
                    capture_output=True)
            except Exception:
                pass
        threading.Thread(target=_regen, daemon=True).start()

    # ── TEST Buyback competitor intel (Minerals, Moon Goo, Ore/Ice, PI) ────

    def _toggle_intel_panel(self):
        """Collapse or expand the competitor stock detail grid."""
        self._intel_expanded = not self._intel_expanded
        if self._intel_expanded:
            tk.Frame(self._intel_content.master, bg='#1a3a1a',
                     height=1).pack(fill='x', before=self._intel_content)
            self._intel_content.pack(fill='x', padx=8, pady=(4, 6))
            self._intel_toggle_btn.configure(text='\u25bc')
        else:
            # Remove the separator line and hide content
            for w in self._intel_content.master.pack_slaves():
                if isinstance(w, tk.Frame) and w is not self._intel_content and \
                        w.cget('height') == 1:
                    w.pack_forget()
                    w.destroy()
            self._intel_content.pack_forget()
            self._intel_toggle_btn.configure(text='\u25b6')

    def _merge_comp_stock(self):
        """Return a flat {name_lower: qty} dict merged from all fetched sheet tabs."""
        merged = {}
        for tab_data in self._test_comp_stock.values():
            for name, qty in tab_data.items():
                merged[name.lower()] = qty
        return merged

    def _test_comp_refresh(self):
        """Fetch competitor stock data from all TEST Buyback Google Sheet tabs."""
        import threading, requests, csv, io as _io
        self._intel_refresh_btn.configure(state='disabled', text='Fetching\u2026')
        self._intel_last_lbl.configure(text='Fetching\u2026', fg='#ffcc44')
        result = {}
        error_holder = [None]

        def _fetch():
            try:
                for tab_label, gid in COMP_TABS:
                    url = (f'https://docs.google.com/spreadsheets/d/'
                           f'{_COMP_SHEET_ID}/export?format=csv&gid={gid}')
                    resp = requests.get(url, timeout=20, allow_redirects=True)
                    resp.raise_for_status()
                    reader = csv.DictReader(_io.StringIO(resp.text))
                    tab_data = {}
                    for row in reader:
                        name = row.get('Type', '').strip()
                        qty_str = row.get('Quantity', '0').strip().replace(',', '')
                        try:
                            qty = int(float(qty_str))
                        except ValueError:
                            qty = 0
                        if name:
                            tab_data[name] = qty
                    result[tab_label] = tab_data
            except Exception as exc:
                error_holder[0] = str(exc)
            self.root.after(0, lambda: self._test_comp_refresh_done(result, error_holder[0]))

        threading.Thread(target=_fetch, daemon=True).start()

    def _test_comp_refresh_done(self, result, error):
        """Called on the main thread when the multi-tab fetch completes."""
        self._intel_refresh_btn.configure(state='normal', text='\u21bb Refresh')
        if error:
            self._intel_last_lbl.configure(
                text=f'Error: {error[:60]}', fg='#ff6666')
            return
        self._test_comp_stock = result
        self._test_pi_last_fetch = datetime.now()
        ts = self._test_pi_last_fetch.strftime('%H:%M:%S')
        total = sum(len(d) for d in result.values())
        self._intel_last_lbl.configure(text=f'Updated {ts}  ({total} items)', fg='#556677')
        self._test_comp_update_intel()
        self._test_comp_apply_tree_tags()

    def _open_intel_charts(self):
        """Generate and open the competitor intel HTML chart report."""
        import subprocess
        script = os.path.join(PROJECT_DIR, 'generate_intel_charts.py')
        try:
            subprocess.Popen([sys.executable, script],
                             creationflags=subprocess.CREATE_NO_WINDOW
                             if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
            self.update_status('Intel charts report opened in browser.')
        except Exception as e:
            self.update_status(f'Could not open charts: {e}')

    def _test_comp_update_intel(self):
        """Rebuild the competitor stock grid, grouped by sheet tab."""
        for w in self._intel_content.winfo_children():
            w.destroy()

        threshold = self._intel_threshold_var.get()
        self._update_intel_summary(threshold)

        if not self._test_comp_stock:
            tk.Label(self._intel_content, text='No data loaded.',
                     bg='#0d1e10', fg='#334455',
                     font=('Segoe UI', 8, 'italic')).pack(pady=2)
            return

        COLS = 5
        for tab_label, tab_data in self._test_comp_stock.items():
            if not tab_data:
                continue
            # Section header
            tk.Label(self._intel_content, text=tab_label,
                     bg='#0d1e10', fg='#ffcc44',
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=6, pady=(5, 1))
            tk.Frame(self._intel_content, bg='#2a3a1a', height=1).pack(fill='x', padx=6, pady=(0, 2))

            # Sort ascending by qty so lowest-stock items appear first
            items = sorted(tab_data.items(), key=lambda x: x[1])

            grid = tk.Frame(self._intel_content, bg='#0d1e10')
            grid.pack(fill='x', padx=2, pady=(0, 2))
            for c in range(COLS):
                grid.columnconfigure(c, weight=1)

            for i, (name, qty) in enumerate(items):
                row_i, col_i = divmod(i, COLS)
                if qty == 0:
                    qty_color = '#ff5555'
                elif qty <= threshold:
                    qty_color = '#ffaa44'
                else:
                    qty_color = '#448844'

                cell = tk.Frame(grid, bg='#0d1e10')
                cell.grid(row=row_i, column=col_i, sticky='ew', padx=4, pady=1)

                short = name if len(name) <= 20 else name[:19] + '\u2026'
                tk.Label(cell, text=short, bg='#0d1e10', fg='#8899aa',
                         font=('Segoe UI', 8), anchor='w').pack(side='left')
                tk.Label(cell, text=f' {qty:,}', bg='#0d1e10', fg=qty_color,
                         font=('Segoe UI', 8, 'bold'), anchor='e').pack(side='right')

    def _update_intel_summary(self, threshold):
        """Update the collapsed-view summary badge with current alert counts."""
        if not self._test_comp_stock:
            self._intel_summary_lbl.configure(text='')
            return
        merged = self._merge_comp_stock()
        n_out  = sum(1 for q in merged.values() if q == 0)
        n_low  = sum(1 for q in merged.values() if 0 < q <= threshold)
        n_none = sum(
            1 for d in self.rate_items.values()
            if d.get('category') in COMP_INTEL_CATEGORIES
            and d.get('name', '').lower() not in merged
        )
        parts = []
        if n_out:
            parts.append(f'{n_out} out')
        if n_low:
            parts.append(f'{n_low} low')
        if n_none:
            parts.append(f'{n_none} not carried')
        summary = ' · '.join(parts) if parts else 'all stocked'
        color = '#ff8888' if n_out else '#ffcc66' if n_low else '#6688bb' if n_none else '#448844'
        self._intel_summary_lbl.configure(text=f'({summary})', fg=color)

    def _test_comp_apply_tree_tags(self):
        """Colour-code rows in the rates treeview based on TEST competitor stock."""
        if not hasattr(self, '_test_comp_stock') or not self._test_comp_stock:
            return
        try:
            threshold = self._intel_threshold_var.get()
        except Exception:
            return
        self._update_intel_summary(threshold)

        self.rates_tree.tag_configure('pi_intel_out',
            background='#2a0a0a', foreground='#ff8888')
        self.rates_tree.tag_configure('pi_intel_low',
            background='#1e1200', foreground='#ffcc66')
        self.rates_tree.tag_configure('pi_intel_none',
            background='#0a0d1e', foreground='#6688bb')

        stock_lower = self._merge_comp_stock()

        for iid in self.rates_tree.get_children():
            data = self.rate_items.get(iid, {})
            category = data.get('category', '')
            if category not in COMP_INTEL_CATEGORIES:
                continue
            name_lower = data.get('name', '').lower()
            if name_lower not in stock_lower:
                # Competitor does not carry this item at all
                self.rates_tree.item(iid, tags=('pi_intel_none',))
                continue
            qty = stock_lower[name_lower]
            if qty == 0:
                self.rates_tree.item(iid, tags=('pi_intel_out',))
            elif qty <= threshold:
                self.rates_tree.item(iid, tags=('pi_intel_low',))
            else:
                self.rates_tree.item(iid, tags=())

    def load_inventory(self):
        """Load current inventory from database."""
        self.inv_tree.delete(*self.inv_tree.get_children())

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get latest inventory via the view
        cursor.execute("""
            SELECT t.type_name, i.quantity,
                   COALESCE(tm.category, 'other') as category
            FROM lx_zoj_current_inventory i
            LEFT JOIN tracked_market_items tm ON i.type_id = tm.type_id
            LEFT JOIN inv_types t ON i.type_id = t.type_id
            ORDER BY tm.category, tm.display_order, t.type_name
        """)
        rows = cursor.fetchall()

        # Also get timestamp
        cursor.execute("SELECT MAX(snapshot_timestamp) FROM lx_zoj_inventory")
        ts = cursor.fetchone()
        conn.close()

        for name, qty, category in rows:
            cat_display = category.replace('_', ' ').title()
            status = "OUT OF STOCK" if qty == 0 else ("LOW" if qty < 1000 else "OK")
            self.inv_tree.insert('', 'end', values=(
                cat_display,
                name or 'Unknown',
                f"{qty:,}",
                status
            ))

        if ts and ts[0]:
            self.last_updated_label.configure(
                text=f"Last inventory update: {ts[0]}"
            )

    # ===== BUYBACK PROGRAM =====

    def _on_category_toggle(self, cat_name):
        """Handle a category visibility checkbox toggle."""
        visible = self.buyback_category_vars[cat_name].get()
        btn = self.category_toggle_btns[cat_name]
        if visible:
            btn.configure(fg='#00ff88', bg='#0d1117')
        else:
            btn.configure(fg='#ff6666', bg='#1a1520')
        # Mark that we have unsaved category changes
        self._check_bb_category_unsaved()

    def _on_pricing_method_change(self, cat_name):
        """Handle a pricing method combo change."""
        self._check_bb_category_unsaved()

    def _check_bb_category_unsaved(self):
        """Check if category visibility or pricing method has unsaved changes."""
        total_unsaved = len(self.unsaved_changes) + len(self.unsaved_buyback_changes)
        # Check category changes (visibility + pricing method)
        has_cat_changes = False
        for cat_name, var in self.buyback_category_vars.items():
            original = self._original_category_visibility.get(cat_name, True)
            if var.get() != original:
                has_cat_changes = True
                break
        if not has_cat_changes:
            for cat_name, var in self.pricing_method_vars.items():
                original = self._original_pricing_methods.get(cat_name, 'Jita Buy')
                if var.get() != original:
                    has_cat_changes = True
                    break
        if not has_cat_changes:
            try:
                orig_eff = getattr(self, '_original_refining_eff', 90.63)
                cur_eff = float(self.bb_refining_eff_var.get())
                if abs(cur_eff - orig_eff) > 0.001:
                    has_cat_changes = True
            except (ValueError, AttributeError, tk.TclError):
                pass
        if has_cat_changes:
            total_unsaved += 1
        if total_unsaved > 0:
            self.update_status(f"{total_unsaved} unsaved change{'s' if total_unsaved > 1 else ''}")
        else:
            self.update_status("All saved")

    def load_buyback_data(self):
        """Load buyback items from tracked_market_items."""
        self.bb_tree.delete(*self.bb_tree.get_children())
        self.unsaved_buyback_changes = {}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Ensure site_config table exists for category visibility
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()

        # Load category visibility settings
        self._original_category_visibility = {}
        for cat_name in self.buyback_categories:
            config_key = f"buyback_category_{cat_name.lower().replace(' ', '_')}"
            cursor.execute("SELECT value FROM site_config WHERE key = ?", (config_key,))
            row = cursor.fetchone()
            visible = True if not row else (row[0] == '1')
            self._original_category_visibility[cat_name] = visible
            self.buyback_category_vars[cat_name].set(visible)
            btn = self.category_toggle_btns[cat_name]
            if visible:
                btn.configure(fg='#00ff88', bg='#0d1117')
            else:
                btn.configure(fg='#ff6666', bg='#1a1520')

        # Load pricing method settings
        self._original_pricing_methods = {}
        for cat_name in self.buyback_categories:
            config_key = f"buyback_pricing_{cat_name.lower().replace(' ', '_')}"
            cursor.execute("SELECT value FROM site_config WHERE key = ?", (config_key,))
            row = cursor.fetchone()
            method = row[0] if row else 'Jita Buy'
            self._original_pricing_methods[cat_name] = method
            self.pricing_method_vars[cat_name].set(method)

        # Load refining efficiency
        cursor.execute("SELECT value FROM site_config WHERE key = 'buyback_ore_refining_efficiency'")
        row = cursor.fetchone()
        self._original_refining_eff = float(row[0]) if row else 90.63
        self.bb_refining_eff_var.set(self._original_refining_eff)

        # Check if buyback_accepted column exists, create if not
        cursor.execute("PRAGMA table_info(tracked_market_items)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'buyback_accepted' not in columns:
            cursor.execute("ALTER TABLE tracked_market_items ADD COLUMN buyback_accepted INTEGER DEFAULT 1")
            conn.commit()
        if 'buyback_rate' not in columns:
            cursor.execute("ALTER TABLE tracked_market_items ADD COLUMN buyback_rate INTEGER DEFAULT NULL")
            conn.commit()
        if 'buyback_quota' not in columns:
            cursor.execute("ALTER TABLE tracked_market_items ADD COLUMN buyback_quota INTEGER DEFAULT 0")
            conn.commit()

        cursor.execute("""
            SELECT id, type_id, type_name, category, price_percentage,
                   COALESCE(buyback_rate, price_percentage) as bb_rate,
                   COALESCE(buyback_accepted, 1) as accepted,
                   COALESCE(buyback_quota, 0) as quota
            FROM tracked_market_items
            ORDER BY category, display_order, type_name
        """)
        rows = cursor.fetchall()
        conn.close()

        self.bb_items = {}
        accepted_count = 0
        total_count = 0
        for row_id, type_id, name, category, market_rate, bb_rate, accepted, quota in rows:
            cat_display = CATEGORY_DISPLAY.get(category, category.replace('_', ' ').title())
            accepted_text = "YES" if accepted else "NO"
            quota_display = f"{quota:,}" if quota > 0 else "No limit"
            iid = self.bb_tree.insert('', 'end', values=(
                cat_display, name, f"{bb_rate}%", f"{bb_rate}%", quota_display, accepted_text
            ))
            # Color the accepted column
            if not accepted:
                self.bb_tree.item(iid, tags=('not_accepted',))

            self.bb_items[iid] = {
                'id': row_id, 'type_id': type_id, 'name': name,
                'category': category, 'bb_rate': bb_rate, 'accepted': accepted,
                'quota': quota
            }
            total_count += 1
            if accepted:
                accepted_count += 1

        # Style tags for accepted/not
        self.bb_tree.tag_configure('not_accepted', foreground='#666688')

        self.bb_accepted_label.configure(
            text=f"Accepted: {accepted_count}/{total_count} items"
        )

        # Count active items per category for auto-hide indicators
        cat_active_counts = {}
        cat_total_counts = {}
        for item in self.bb_items.values():
            cat_display = CATEGORY_DISPLAY.get(item['category'], item['category'].replace('_', ' ').title())
            cat_active_counts[cat_display] = cat_active_counts.get(cat_display, 0) + (1 if item['accepted'] else 0)
            cat_total_counts[cat_display] = cat_total_counts.get(cat_display, 0) + 1

        # Update category toggle buttons with active count
        for cat_name in self.buyback_categories:
            btn = self.category_toggle_btns[cat_name]
            active = cat_active_counts.get(cat_name, 0)
            total = cat_total_counts.get(cat_name, 0)
            visible = self.buyback_category_vars[cat_name].get()
            if active == 0 and total > 0:
                btn.configure(text=f"{cat_name} (0/{total})",
                              fg='#666666', bg='#151520')
            elif active == 0 and total == 0:
                btn.configure(text=f"{cat_name} (empty)",
                              fg='#666666', bg='#151520')
            else:
                label = f"{cat_name} ({active}/{total})"
                if visible:
                    btn.configure(text=label, fg='#00ff88', bg='#0d1117')
                else:
                    btn.configure(text=label, fg='#ff6666', bg='#1a1520')

    def on_bb_select(self, event):
        """Handle buyback row selection (single or multi)."""
        selection = self.bb_tree.selection()
        if not selection:
            return
        if len(selection) == 1:
            item = self.bb_items.get(selection[0])
            if item:
                self.bb_selected_label.configure(text=item['name'])
                self.bb_rate_var.set(item['bb_rate'])
                self.bb_quota_var.set(str(item['quota']))
        else:
            self.bb_selected_label.configure(text=f"{len(selection)} items selected")

    def quick_set_bb_rate(self, pct):
        """Set the buyback rate spinbox to a preset and apply."""
        self.bb_rate_var.set(pct)
        self.apply_bb_rate_change()

    def _get_bb_change(self, iid, item):
        """Get or create a buyback change entry."""
        return self.unsaved_buyback_changes.get(iid, {
            'id': item['id'], 'name': item['name'],
            'old_rate': item['bb_rate'], 'new_rate': item['bb_rate'],
            'old_accepted': item['accepted'], 'new_accepted': item['accepted'],
            'old_quota': item['quota'], 'new_quota': item['quota']
        })

    def _update_bb_tree_display(self, iid, item, change):
        """Update the buyback treeview row with current change state."""
        accepted_text = "YES" if change['new_accepted'] else "NO"
        if change['new_accepted'] != item['accepted']:
            accepted_text += " *"

        rate_display = f"{change['new_rate']}%"
        if change['new_rate'] != item['bb_rate']:
            rate_display += " *"

        new_quota = change.get('new_quota', item['quota'])
        quota_display = f"{new_quota:,}" if new_quota > 0 else "No limit"
        if new_quota != item['quota']:
            quota_display += " *"

        tags = () if change['new_accepted'] else ('not_accepted',)
        cat_display = CATEGORY_DISPLAY.get(item['category'], item['category'].replace('_', ' ').title())
        self.bb_tree.item(iid, values=(
            cat_display,
            item['name'], f"{item['bb_rate']}%", rate_display, quota_display, accepted_text
        ), tags=tags)

    def apply_bb_rate_change(self):
        """Apply a buyback rate change to all selected items."""
        selection = self.bb_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        new_rate = self.bb_rate_var.get()

        for iid in selection:
            item = self.bb_items[iid]
            change = self._get_bb_change(iid, item)
            change['new_rate'] = new_rate
            self.unsaved_buyback_changes[iid] = change
            self._update_bb_tree_display(iid, item, change)
            self._check_bb_unsaved(iid, change, item)

    def apply_bb_quota_change(self):
        """Apply a quota change to all selected items."""
        selection = self.bb_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        try:
            new_quota = int(self.bb_quota_var.get())
        except ValueError:
            messagebox.showerror("Invalid Value", "Quota must be a number.")
            return

        if new_quota < 0:
            new_quota = 0

        for iid in selection:
            item = self.bb_items[iid]
            change = self._get_bb_change(iid, item)
            change['new_quota'] = new_quota
            self.unsaved_buyback_changes[iid] = change
            self._update_bb_tree_display(iid, item, change)
            self._check_bb_unsaved(iid, change, item)

    def toggle_bb_accepted(self):
        """Toggle accepted status for all selected items."""
        selection = self.bb_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        for iid in selection:
            item = self.bb_items[iid]
            change = self._get_bb_change(iid, item)
            change['new_accepted'] = 0 if change['new_accepted'] else 1
            self.unsaved_buyback_changes[iid] = change
            self._update_bb_tree_display(iid, item, change)
            self._check_bb_unsaved(iid, change, item)

    def _check_bb_unsaved(self, iid, change, item):
        """Check if a buyback change is actually different from the original."""
        new_quota = change.get('new_quota', item['quota'])
        if (change['new_rate'] == item['bb_rate']
                and change['new_accepted'] == item['accepted']
                and new_quota == item['quota']):
            if iid in self.unsaved_buyback_changes:
                del self.unsaved_buyback_changes[iid]

        total_unsaved = len(self.unsaved_changes) + len(self.unsaved_buyback_changes)
        if total_unsaved > 0:
            self.update_status(f"{total_unsaved} unsaved change{'s' if total_unsaved > 1 else ''}")
        else:
            self.update_status("All saved")

    def save_buyback_rates(self):
        """Save all buyback changes to the database."""
        # Check for category visibility changes
        cat_changes = {}
        for cat_name, var in self.buyback_category_vars.items():
            original = self._original_category_visibility.get(cat_name, True)
            if var.get() != original:
                cat_changes[cat_name] = var.get()

        # Check for pricing method changes
        pricing_changes = {}
        for cat_name, var in self.pricing_method_vars.items():
            original = self._original_pricing_methods.get(cat_name, 'Jita Buy')
            if var.get() != original:
                pricing_changes[cat_name] = var.get()

        # Check for refining efficiency change
        try:
            new_eff = round(float(self.bb_refining_eff_var.get()), 2)
        except (ValueError, tk.TclError):
            new_eff = self._original_refining_eff
        eff_changed = abs(new_eff - self._original_refining_eff) > 0.001

        if not self.unsaved_buyback_changes and not cat_changes and not pricing_changes and not eff_changed:
            messagebox.showinfo("No Changes", "Nothing to save.")
            return

        # Build confirmation text
        lines = []
        for c in self.unsaved_buyback_changes.values():
            parts = []
            if c['new_rate'] != c['old_rate']:
                parts.append(f"rate {c['old_rate']}% -> {c['new_rate']}%")
            if c.get('new_quota') is not None and c['new_quota'] != c.get('old_quota', 0):
                old_q = f"{c.get('old_quota', 0):,}" if c.get('old_quota', 0) > 0 else "none"
                new_q = f"{c['new_quota']:,}" if c['new_quota'] > 0 else "none"
                parts.append(f"quota {old_q} -> {new_q}")
            if c['new_accepted'] != c['old_accepted']:
                old_a = "YES" if c['old_accepted'] else "NO"
                new_a = "YES" if c['new_accepted'] else "NO"
                parts.append(f"accepted {old_a} -> {new_a}")
            lines.append(f"  {c['name']}: {', '.join(parts)}")

        for cat_name, visible in cat_changes.items():
            old_state = "Visible" if self._original_category_visibility.get(cat_name, True) else "Hidden"
            new_state = "Visible" if visible else "Hidden"
            lines.append(f"  Category '{cat_name}': {old_state} -> {new_state}")

        for cat_name, method in pricing_changes.items():
            old_method = self._original_pricing_methods.get(cat_name, 'Jita Buy')
            lines.append(f"  Category '{cat_name}' pricing: {old_method} -> {method}")

        if eff_changed:
            lines.append(f"  Ore refining efficiency: {self._original_refining_eff}% -> {new_eff}%")

        changes_text = "\n".join(lines)
        if not messagebox.askyesno("Confirm Changes",
                                    f"Save these buyback changes?\n\n{changes_text}"):
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for change in self.unsaved_buyback_changes.values():
            new_quota = change.get('new_quota', change.get('old_quota', 0))
            cursor.execute(
                "UPDATE tracked_market_items SET buyback_rate = ?, buyback_accepted = ?, buyback_quota = ? WHERE id = ?",
                (change['new_rate'], change['new_accepted'], new_quota, change['id'])
            )

        # Save category visibility to site_config
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        for cat_name in self.buyback_categories:
            config_key = f"buyback_category_{cat_name.lower().replace(' ', '_')}"
            visible = '1' if self.buyback_category_vars[cat_name].get() else '0'
            cursor.execute(
                "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                (config_key, visible)
            )

        # Save pricing method per category
        for cat_name in self.buyback_categories:
            config_key = f"buyback_pricing_{cat_name.lower().replace(' ', '_')}"
            method = self.pricing_method_vars[cat_name].get()
            cursor.execute(
                "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                (config_key, method)
            )

        # Save refining efficiency
        cursor.execute(
            "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
            ('buyback_ore_refining_efficiency', str(new_eff))
        )

        conn.commit()
        conn.close()

        self.unsaved_buyback_changes = {}
        self.load_buyback_data()

        total_unsaved = len(self.unsaved_changes)
        if total_unsaved > 0:
            self.update_status(f"{total_unsaved} unsaved change{'s' if total_unsaved > 1 else ''}")
        else:
            self.update_status("All saved")

        cat_count = len(cat_changes)
        pricing_count = len(pricing_changes)
        item_count = len(lines) - cat_count - pricing_count
        msg_parts = []
        if item_count > 0:
            msg_parts.append(f"{item_count} item change(s)")
        if cat_count > 0:
            msg_parts.append(f"{cat_count} visibility change(s)")
        if pricing_count > 0:
            msg_parts.append(f"{pricing_count} pricing method change(s)")
        messagebox.showinfo("Saved", f"Buyback settings updated.\n{', '.join(msg_parts)}.")

    # ===== BLUEPRINT LIBRARY =====

    def _ensure_bp_tables(self, cursor, conn):
        """Ensure blueprint admin tables exist."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hidden_blueprints (
                type_id INTEGER NOT NULL,
                me INTEGER NOT NULL DEFAULT 0,
                te INTEGER NOT NULL DEFAULT 0,
                runs INTEGER NOT NULL DEFAULT -1,
                PRIMARY KEY (type_id, me, te, runs)
            )
        """)
        conn.commit()

    def load_blueprint_settings(self):
        """Load calculator params and blueprint list."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        self._ensure_bp_tables(cursor, conn)

        # Load calculator settings from site_config
        defaults = {
            'calc_default_runs': ('10', 'int'),
            'calc_max_runs': ('300', 'int'),
            'calc_default_copies': ('1', 'int'),
            'calc_max_copies': ('100', 'int'),
            'calc_facility': ('Azbel in LX-ZOJ', 'str'),
            'calc_lock_bpc_runs': ('1', 'bool'),
            'calc_lock_bpc_copies': ('1', 'bool'),
        }
        var_map = {
            'calc_default_runs': self.calc_default_runs_var,
            'calc_max_runs': self.calc_max_runs_var,
            'calc_default_copies': self.calc_default_copies_var,
            'calc_max_copies': self.calc_max_copies_var,
            'calc_facility': self.calc_facility_var,
            'calc_lock_bpc_runs': self.calc_lock_bpc_runs_var,
            'calc_lock_bpc_copies': self.calc_lock_bpc_copies_var,
        }
        for key, (default, typ) in defaults.items():
            cursor.execute("SELECT value FROM site_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            raw = row[0] if row else default
            if typ == 'int':
                var_map[key].set(int(raw))
            elif typ == 'bool':
                var_map[key].set(raw == '1' or raw == 'True')
            else:
                var_map[key].set(raw)

        # Load hidden blueprints set
        cursor.execute("SELECT type_id, me, te, runs FROM hidden_blueprints")
        self.hidden_bps = set()
        for row in cursor.fetchall():
            self.hidden_bps.add((row[0], row[1], row[2], row[3]))

        # Load all blueprints
        cursor.execute("""
            SELECT cb.type_id, cb.type_name,
                   cb.material_efficiency, cb.time_efficiency, cb.runs,
                   COALESCE(g.group_name, 'Unknown') as group_name
            FROM character_blueprints cb
            LEFT JOIN inv_types t ON cb.type_id = t.type_id
            LEFT JOIN inv_groups g ON t.group_id = g.group_id
            ORDER BY cb.type_name
        """)
        self.all_blueprints = []
        for type_id, name, me, te, runs, group in cursor.fetchall():
            bp_type = 'BPO' if runs == -1 else 'BPC'
            hidden = (type_id, me, te, runs) in self.hidden_bps
            self.all_blueprints.append({
                'type_id': type_id, 'name': name,
                'me': me, 'te': te, 'runs': runs,
                'type': bp_type, 'group': group, 'hidden': hidden
            })

        conn.close()
        self.unsaved_bp_changes = {}
        self.filter_blueprint_list()

    def filter_blueprint_list(self):
        """Filter and redisplay the blueprint list."""
        self.bp_tree.delete(*self.bp_tree.get_children())

        search = self.bp_search_var.get().lower()
        type_filter = self.bp_type_var.get()

        shown = 0
        total = len(self.all_blueprints)

        for bp in self.all_blueprints:
            # Search filter
            if search and search not in bp['name'].lower():
                continue
            # Type filter
            if type_filter != 'All' and bp['type'] != type_filter:
                continue

            # Check for unsaved change
            bp_key = (bp['type_id'], bp['me'], bp['te'], bp['runs'])
            if bp_key in self.unsaved_bp_changes:
                is_hidden = self.unsaved_bp_changes[bp_key]
            else:
                is_hidden = bp['hidden']

            visible_text = "HIDDEN *" if (is_hidden and bp_key in self.unsaved_bp_changes) else \
                           "HIDDEN" if is_hidden else \
                           "YES *" if (not is_hidden and bp_key in self.unsaved_bp_changes) else "YES"

            runs_display = str(bp['runs']) if bp['runs'] > 0 else '-'
            tags = ('hidden',) if is_hidden else ()
            self.bp_tree.insert('', 'end', values=(
                bp['name'], bp['type'], bp['group'],
                bp['me'], bp['te'], visible_text
            ), tags=tags)

            shown += 1

        visible_count = sum(1 for bp in self.all_blueprints if not bp['hidden'])
        self.bp_count_label.configure(text=f"Visible: {visible_count}/{total}  |  Showing: {shown}")

    def toggle_bp_visibility(self):
        """Toggle visibility of selected blueprints."""
        selection = self.bp_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select one or more blueprints first.")
            return

        for iid in selection:
            values = self.bp_tree.item(iid, 'values')
            bp_name = values[0]
            bp = next((b for b in self.all_blueprints if b['name'] == bp_name
                       and b['type'] == values[1]
                       and str(b['me']) == str(values[3])
                       and str(b['te']) == str(values[4])), None)
            if not bp:
                continue

            bp_key = (bp['type_id'], bp['me'], bp['te'], bp['runs'])
            current = self.unsaved_bp_changes.get(bp_key, bp['hidden'])
            self.unsaved_bp_changes[bp_key] = not current

        self.filter_blueprint_list()
        self._update_bp_status()

    def set_bp_visibility(self, visible):
        """Set visibility for selected blueprints."""
        selection = self.bp_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select one or more blueprints first.")
            return

        for iid in selection:
            values = self.bp_tree.item(iid, 'values')
            bp_name = values[0]
            bp = next((b for b in self.all_blueprints if b['name'] == bp_name
                       and b['type'] == values[1]
                       and str(b['me']) == str(values[3])
                       and str(b['te']) == str(values[4])), None)
            if not bp:
                continue

            bp_key = (bp['type_id'], bp['me'], bp['te'], bp['runs'])
            new_hidden = not visible
            if new_hidden != bp['hidden']:
                self.unsaved_bp_changes[bp_key] = new_hidden
            elif bp_key in self.unsaved_bp_changes:
                del self.unsaved_bp_changes[bp_key]

        self.filter_blueprint_list()
        self._update_bp_status()

    def _update_bp_status(self):
        """Update status bar with unsaved blueprint changes."""
        total_unsaved = len(self.unsaved_changes) + len(self.unsaved_buyback_changes) + len(self.unsaved_bp_changes)
        if total_unsaved > 0:
            self.update_status(f"{total_unsaved} unsaved change{'s' if total_unsaved > 1 else ''}")
        else:
            self.update_status("All saved")

    def save_blueprint_settings(self):
        """Save calculator params and visibility changes."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        self._ensure_bp_tables(cursor, conn)

        # Save calculator settings
        params = {
            'calc_default_runs': str(self.calc_default_runs_var.get()),
            'calc_max_runs': str(self.calc_max_runs_var.get()),
            'calc_default_copies': str(self.calc_default_copies_var.get()),
            'calc_max_copies': str(self.calc_max_copies_var.get()),
            'calc_facility': self.calc_facility_var.get(),
            'calc_lock_bpc_runs': '1' if self.calc_lock_bpc_runs_var.get() else '0',
            'calc_lock_bpc_copies': '1' if self.calc_lock_bpc_copies_var.get() else '0',
        }
        for key, value in params.items():
            cursor.execute(
                "INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)",
                (key, value)
            )

        # Save visibility changes
        changes_made = 0
        for bp_key, is_hidden in self.unsaved_bp_changes.items():
            type_id, me, te, runs = bp_key
            if is_hidden:
                cursor.execute(
                    "INSERT OR IGNORE INTO hidden_blueprints (type_id, me, te, runs) VALUES (?, ?, ?, ?)",
                    (type_id, me, te, runs)
                )
            else:
                cursor.execute(
                    "DELETE FROM hidden_blueprints WHERE type_id = ? AND me = ? AND te = ? AND runs = ?",
                    (type_id, me, te, runs)
                )
            changes_made += 1

            # Update in-memory state
            for bp in self.all_blueprints:
                if (bp['type_id'], bp['me'], bp['te'], bp['runs']) == bp_key:
                    bp['hidden'] = is_hidden

        conn.commit()
        conn.close()

        # Rebuild hidden set
        self.hidden_bps = set(
            (bp['type_id'], bp['me'], bp['te'], bp['runs'])
            for bp in self.all_blueprints if bp['hidden']
        )
        self.unsaved_bp_changes = {}
        self.filter_blueprint_list()
        self._update_bp_status()

        messagebox.showinfo("Saved", f"Blueprint settings saved.\n"
                           f"Calculator parameters updated.\n"
                           f"{changes_made} visibility change(s) applied.")

    # ===== RATE EDITING =====

    def on_rate_select(self, event):
        """Handle rate row selection (single or multi)."""
        selection = self.rates_tree.selection()
        if not selection:
            self._refresh_flag_buttons([])
            return
        if len(selection) == 1:
            item = self.rate_items.get(selection[0])
            if item:
                self.selected_item_label.configure(text=item['name'])
                self.rate_var.set(item['rate'])
                self.discount_var.set(item['discount'])
        else:
            self.selected_item_label.configure(text=f"{len(selection)} items selected")
        self._refresh_flag_buttons(list(selection))
        # corp_rate_label is updated by trace on rate_var/discount_var

    # ── Item flags helpers ──────────────────────────────────────────────────

    def _ensure_flags_table(self):
        """Create item_flags table if it doesn't exist."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""CREATE TABLE IF NOT EXISTS item_flags (
                type_id INTEGER NOT NULL,
                flag_key TEXT NOT NULL,
                PRIMARY KEY (type_id, flag_key)
            )""")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _refresh_flag_buttons(self, iids):
        """Update flag button colours to reflect current flags.

        iids — list of selected treeview iids.
        Single-select: loads that item's current flags.
        Multi-select:  neutral state (blank); Apply Flags writes to all selected.
        """
        self._flags_active_iids = iids
        if len(iids) == 1:
            item = self.rate_items.get(iids[0])
            type_id = item['type_id'] if item else None
            self._flags_selected_type_id = type_id
            active = self._item_flags_db.get(type_id, set()) if type_id else set()
            self._flags_label.configure(text="Flags:")
        else:
            self._flags_selected_type_id = None
            active = set()
            if iids:
                self._flags_label.configure(text=f"Flags ({len(iids)} items):")
            else:
                self._flags_label.configure(text="Flags:")
        self._pending_flags = set(active)
        for flag_key, _, flag_color in ITEM_FLAGS:
            btn = self._flag_btns.get(flag_key)
            if btn is None:
                continue
            if flag_key in active:
                btn.configure(bg='#2a2030', fg=flag_color,
                              relief='groove')
            else:
                btn.configure(bg='#1a2030', fg='#445566',
                              relief='flat')

    def _toggle_flag_btn(self, flag_key):
        """Toggle a flag in the pending set and update button appearance."""
        if not self._flags_active_iids:
            return
        flag_color = next((c for k, _, c in ITEM_FLAGS if k == flag_key), '#ffffff')
        if flag_key in self._pending_flags:
            self._pending_flags.discard(flag_key)
            self._flag_btns[flag_key].configure(bg='#1a2030', fg='#445566',
                                                 relief='flat')
        else:
            self._pending_flags.add(flag_key)
            self._flag_btns[flag_key].configure(bg='#2a2030', fg=flag_color,
                                                 relief='groove')

    def _apply_item_flags(self):
        """Save pending flags to DB for all currently selected items."""
        if not self._flags_active_iids:
            return

        # Gather (iid, type_id) pairs for all selected rows
        targets = []
        for iid in self._flags_active_iids:
            item = self.rate_items.get(iid)
            if item:
                targets.append((iid, item['type_id']))
        if not targets:
            return

        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()
            for _, type_id in targets:
                cursor.execute("DELETE FROM item_flags WHERE type_id = ?", (type_id,))
                for fk in self._pending_flags:
                    cursor.execute(
                        "INSERT OR IGNORE INTO item_flags (type_id, flag_key) VALUES (?, ?)",
                        (type_id, fk))
            conn.commit()
            conn.close()
        except Exception as e:
            self.update_status(f"Error saving flags: {e}")
            return

        # Update in-memory cache and treeview for all targets
        flag_labels = {key: label for key, label, _ in ITEM_FLAGS}
        flags_str = ', '.join(
            flag_labels[k] for k, _, _ in ITEM_FLAGS if k in self._pending_flags
        )
        for iid, type_id in targets:
            self._item_flags_db[type_id] = set(self._pending_flags)
            vals = list(self.rates_tree.item(iid, 'values'))
            vals[6] = flags_str
            self.rates_tree.item(iid, values=vals)

        count = len(targets)
        self.update_status(f"Flags saved for {count} item{'s' if count != 1 else ''}")

    def _refresh_corp_rate_label(self):
        """Update the live Corp Rate readout label."""
        try:
            alliance = int(self.rate_var.get())
            discount = int(self.discount_var.get())
            corp = alliance - discount
            self.corp_rate_label.configure(text=f"{corp}% JBV")
        except (ValueError, AttributeError):
            pass

    def quick_set_rate(self, pct):
        """Set the alliance rate spinbox to a preset and apply."""
        self.rate_var.set(pct)
        self.apply_rate_change()

    def quick_set_discount(self, d):
        """Set the corp discount spinbox to a preset and apply."""
        self.discount_var.set(d)
        self.apply_discount_change()

    def apply_rate_change(self):
        """Apply the rate change to all selected items."""
        selection = self.rates_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        new_rate = self.rate_var.get()

        for iid in selection:
            item = self.rate_items[iid]
            existing = self.unsaved_changes.get(iid, {})

            # Determine current effective discount (pending or saved)
            cur_discount = existing.get('new_discount', item['discount'])
            corp_rate = new_rate - cur_discount
            changed = new_rate != item['rate']

            # Update tree display
            values = list(self.rates_tree.item(iid, 'values'))
            values[3] = f"{new_rate}% *" if changed else f"{new_rate}%"
            disc_star = ' *' if (changed or 'new_discount' in existing) else ''
            values[4] = f"-{cur_discount}%  →  {corp_rate}%{disc_star}"
            self.rates_tree.item(iid, values=values)

            # Track change (merge with existing discount change if any)
            if changed or 'new_discount' in existing:
                self.unsaved_changes[iid] = {'id': item['id'], 'name': item['name'],
                                              'old': item['rate'], 'new': new_rate}
                if 'new_discount' in existing:
                    self.unsaved_changes[iid]['old_discount'] = existing.get('old_discount', item['discount'])
                    self.unsaved_changes[iid]['new_discount'] = existing['new_discount']
            elif iid in self.unsaved_changes:
                del self.unsaved_changes[iid]

        count = len(self.unsaved_changes)
        if count > 0:
            self.update_status(f"{count} unsaved change{'s' if count > 1 else ''}")
        else:
            self.update_status("All saved")

    def apply_discount_change(self):
        """Apply the discount change to all selected items."""
        selection = self.rates_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        new_discount = self.discount_var.get()

        for iid in selection:
            item = self.rate_items[iid]
            existing = self.unsaved_changes.get(iid, {})

            # Determine current effective alliance rate (pending or saved)
            cur_alliance = existing.get('new', item['rate'])
            corp_rate = cur_alliance - new_discount
            changed = new_discount != item['discount']

            # Update tree display
            values = list(self.rates_tree.item(iid, 'values'))
            disc_star = ' *' if (changed or existing.get('new', item['rate']) != item['rate']) else ''
            values[4] = f"-{new_discount}%  →  {corp_rate}%{disc_star}"
            self.rates_tree.item(iid, values=values)

            # Track change (merge with existing rate change if any)
            if iid in self.unsaved_changes:
                self.unsaved_changes[iid]['new_discount'] = new_discount
                self.unsaved_changes[iid]['old_discount'] = self.unsaved_changes[iid].get('old_discount', item['discount'])
            elif changed:
                self.unsaved_changes[iid] = {'id': item['id'], 'name': item['name'],
                                              'old': item['rate'], 'new': item['rate'],
                                              'old_discount': item['discount'],
                                              'new_discount': new_discount}
            # Clean up if back to original with no rate change
            elif iid in self.unsaved_changes and self.unsaved_changes[iid].get('new') == item['rate']:
                del self.unsaved_changes[iid]

        count = len(self.unsaved_changes)
        if count > 0:
            self.update_status(f"{count} unsaved change{'s' if count > 1 else ''}")
        else:
            self.update_status("All saved")

    def save_rates(self):
        """Save all rate changes to the database."""
        if not self.unsaved_changes:
            messagebox.showinfo("No Changes", "Nothing to save.")
            return

        # Confirm
        lines = []
        for c in self.unsaved_changes.values():
            parts = []
            if c['new'] != c['old']:
                parts.append(f"rate {c['old']}% -> {c['new']}%")
            if 'new_discount' in c and c['new_discount'] != c.get('old_discount', c.get('old_discount')):
                parts.append(f"discount {c.get('old_discount', '?')}% -> {c['new_discount']}%")
            if not parts:
                parts.append("no change")
            lines.append(f"  {c['name']}: {', '.join(parts)}")
        changes_text = "\n".join(lines)

        if not messagebox.askyesno("Confirm Changes",
                                    f"Save these changes?\n\n{changes_text}"):
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for change in self.unsaved_changes.values():
            if 'new_discount' in change:
                cursor.execute(
                    "UPDATE tracked_market_items SET price_percentage = ?, alliance_discount = ? WHERE id = ?",
                    (change['new'], change['new_discount'], change['id'])
                )
            else:
                cursor.execute(
                    "UPDATE tracked_market_items SET price_percentage = ? WHERE id = ?",
                    (change['new'], change['id'])
                )

        conn.commit()
        conn.close()

        self.unsaved_changes = {}
        self.update_status("All saved")
        self.load_rates()
        messagebox.showinfo("Saved", "Rates updated in database.\n\n"
                           "Run 'Update Inventory' or 'Deploy to Live' to push changes to the website.")

    # ===== ACTIONS =====

    def action_update_inventory(self):
        """Run the inventory update script in a background thread."""
        import threading, sys as _sys

        script_path = os.path.join(PROJECT_DIR, 'update_lx_zoj_inventory.py')
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return

        self._inv_action_btn.configure(state='disabled', text='Running...')
        self.update_status('Updating inventory...')
        error_holder = [None]

        def _worker():
            try:
                result = subprocess.run(
                    [_sys.executable, script_path],
                    cwd=PROJECT_DIR,
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    error_holder[0] = (result.stderr or result.stdout or 'Unknown error').strip()[-300:]
            except Exception as e:
                error_holder[0] = str(e)
            self.root.after(0, _done)

        def _done():
            self._inv_action_btn.configure(state='normal', text='Run')
            if error_holder[0]:
                self.update_status('Inventory update failed')
                messagebox.showerror("Update Failed", f"Inventory update failed:\n\n{error_holder[0]}")
            else:
                self.update_status('Inventory updated successfully')
                self.load_inventory()
                messagebox.showinfo("Done", "Inventory updated and site pushed to GitHub.\n"
                                            "Live site will reflect changes in 1-2 minutes.")

        threading.Thread(target=_worker, daemon=True).start()

    def action_generate_stock_image(self):
        """Generate Discord stock image in a background thread."""
        import threading, sys as _sys
        script_path = os.path.join(PROJECT_DIR, 'generate_stock_image.py')
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return
        self.update_status('Generating stock image...')
        error_holder = [None]

        def _worker():
            try:
                result = subprocess.run(
                    [_sys.executable, script_path],
                    cwd=PROJECT_DIR,
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    error_holder[0] = (result.stderr or result.stdout or 'Unknown error').strip()[-300:]
            except Exception as e:
                error_holder[0] = str(e)
            self.root.after(0, _done)

        def _done():
            if error_holder[0]:
                self.update_status('Stock image generation failed')
                messagebox.showerror("Failed", f"Image generation failed:\n\n{error_holder[0]}")
            else:
                self.update_status('Stock image saved to stock_image.png')
                messagebox.showinfo("Done", "stock_image.png has been saved.\n"
                                            "Ready to drag into Discord.")

        threading.Thread(target=_worker, daemon=True).start()

    def action_generate_fuel_image(self):
        """Generate Discord fuel image in a background thread."""
        import threading, sys as _sys
        script_path = os.path.join(PROJECT_DIR, 'generate_fuel_image.py')
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return
        self.update_status('Generating fuel image...')
        error_holder = [None]

        def _worker():
            try:
                result = subprocess.run(
                    [_sys.executable, script_path],
                    cwd=PROJECT_DIR,
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    error_holder[0] = (result.stderr or result.stdout or 'Unknown error').strip()[-300:]
            except Exception as e:
                error_holder[0] = str(e)
            self.root.after(0, _done)

        def _done():
            if error_holder[0]:
                self.update_status('Fuel image generation failed')
                messagebox.showerror("Failed", f"Image generation failed:\n\n{error_holder[0]}")
            else:
                self.update_status('Fuel image saved to fuel_image.png')
                messagebox.showinfo("Done", "fuel_image.png has been saved.\nReady to drag into Discord.")

        threading.Thread(target=_worker, daemon=True).start()

    def action_generate_catalog_images(self):
        """Generate per-category Discord catalog images in a background thread."""
        import threading, sys as _sys
        script_path = os.path.join(PROJECT_DIR, 'generate_catalog_image.py')
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return
        self.update_status('Generating catalog images...')
        error_holder = [None]

        def _worker():
            try:
                result = subprocess.run(
                    [_sys.executable, script_path],
                    cwd=PROJECT_DIR,
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    error_holder[0] = (result.stderr or result.stdout or 'Unknown error').strip()[-300:]
            except Exception as e:
                error_holder[0] = str(e)
            self.root.after(0, _done)

        def _done():
            if error_holder[0]:
                self.update_status('Catalog image generation failed')
                messagebox.showerror("Failed", f"Image generation failed:\n\n{error_holder[0]}")
            else:
                self.update_status('Catalog images saved (catalog_*.png)')
                messagebox.showinfo("Done", "catalog_minerals.png\ncatalog_ice_products.png\n"
                                            "catalog_moon_materials.png\ncatalog_pi_materials.png\n"
                                            "catalog_gas_cloud_materials.png\ncatalog_research_equipment.png\n"
                                            "catalog_salvaged_materials.png\n\n"
                                            "Ready to drag into Discord.")

        threading.Thread(target=_worker, daemon=True).start()

    def action_generate_buyback_image(self):
        """Generate Discord buyback image in a background thread."""
        import threading, sys as _sys
        script_path = os.path.join(PROJECT_DIR, 'generate_buyback_image.py')
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return
        self.update_status('Generating buyback image...')
        error_holder = [None]

        def _worker():
            try:
                result = subprocess.run(
                    [_sys.executable, script_path],
                    cwd=PROJECT_DIR,
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    error_holder[0] = (result.stderr or result.stdout or 'Unknown error').strip()[-300:]
            except Exception as e:
                error_holder[0] = str(e)
            self.root.after(0, _done)

        def _done():
            if error_holder[0]:
                self.update_status('Buyback image generation failed')
                messagebox.showerror("Failed", f"Image generation failed:\n\n{error_holder[0]}")
            else:
                self.update_status('Buyback images saved (buyback_miners.png, buyback_salvage.png)')
                messagebox.showinfo("Done", "buyback_miners.png  —  Minerals, Ice, Moon, Gas\n"
                                            "buyback_salvage.png  —  Salvage & Research\n\n"
                                            "Ready to drag into Discord.")

        threading.Thread(target=_worker, daemon=True).start()

    def action_update_blueprints(self):
        """Run the blueprint update script."""
        self.run_script('update_all_blueprint_data.py', 'Blueprint Update')

    def action_deploy(self):
        """Push changes to GitHub."""
        if self.unsaved_changes or self.unsaved_buyback_changes or self.unsaved_bp_changes:
            messagebox.showwarning("Unsaved Changes",
                                   "Save your changes first before deploying.")
            return

        if messagebox.askyesno("Deploy to Live",
                               "This will push the current site to GitHub.\n"
                               "The live site will update in 1-2 minutes.\n\n"
                               "Continue?"):
            self.run_script('update_page.bat', 'Deploy')

    def run_script(self, script_name, label):
        """Run a script in the project directory."""
        script_path = os.path.join(PROJECT_DIR, script_name)
        if not os.path.exists(script_path):
            messagebox.showerror("Not Found", f"Script not found:\n{script_path}")
            return

        self.update_status(f"Running {label}...")
        self.root.update()

        try:
            if script_name.endswith('.bat'):
                subprocess.Popen(['cmd', '/c', script_path], cwd=PROJECT_DIR)
            else:
                python_exe = r'C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe'
                subprocess.Popen([python_exe, script_path], cwd=PROJECT_DIR)

            self.update_status(f"{label} started")
            messagebox.showinfo("Started", f"{label} is running.\n"
                               "Check the console for progress.")
        except Exception as e:
            self.update_status("Error")
            messagebox.showerror("Error", f"Failed to start {label}:\n{str(e)}")

    # ===== EXPORT ANALYSIS =====

    def build_export_tab(self):
        """Build the Export Analysis tab."""
        outer = ttk.Frame(self.export_frame)
        outer.pack(fill='both', expand=True, padx=15, pady=(15, 10))

        ttk.Label(outer,
                  text="Calculate profit on items exported from local station → sold at Jita, after shipping and collateral.",
                  style='SubHeader.TLabel').pack(anchor='w', pady=(0, 10))

        # ── Parameter panel ──────────────────────────────────────────────────
        param_card = ttk.Frame(outer, style='Card.TFrame')
        param_card.pack(fill='x', pady=(0, 10))
        param_inner = ttk.Frame(param_card, style='Card.TFrame')
        param_inner.pack(fill='x', padx=12, pady=10)

        ttk.Label(param_inner, text="CALCULATION PARAMETERS",
                  background='#0a2030', foreground='#00d9ff',
                  font=('Segoe UI', 9, 'bold')).grid(
                  row=0, column=0, columnspan=8, sticky='w', pady=(0, 8))

        lbl_cfg = dict(background='#0a2030', foreground='#88d0e8', font=('Segoe UI', 10))

        # Buy basis
        tk.Label(param_inner, text="Buy Basis", **lbl_cfg).grid(row=1, column=0, sticky='w', padx=(0, 4))
        self.export_buy_var = tk.StringVar(value=self._get_config('export_param_buy_basis', 'JBV'))
        self.export_buy_var.trace_add('write', lambda *_: self._set_config('export_param_buy_basis', self.export_buy_var.get()))
        buy_menu = ttk.Combobox(param_inner, textvariable=self.export_buy_var, width=18,
                                values=['JBV', 'Jita Split', 'JSV'], state='readonly')
        buy_menu.grid(row=2, column=0, sticky='w', padx=(0, 12))

        # Buy %
        tk.Label(param_inner, text="Buy % of Basis", **lbl_cfg).grid(row=1, column=1, sticky='w', padx=(0, 4))
        self.export_buy_pct_var = tk.StringVar(value=self._get_config('export_param_buy_pct', '100'))
        self.export_buy_pct_var.trace_add('write', lambda *_: self._set_config('export_param_buy_pct', self.export_buy_pct_var.get()))
        ttk.Entry(param_inner, textvariable=self.export_buy_pct_var, width=8).grid(
            row=2, column=1, sticky='w', padx=(0, 12))

        # Sell basis
        tk.Label(param_inner, text="Sell Basis (at Jita)", **lbl_cfg).grid(row=1, column=2, sticky='w', padx=(0, 4))
        self.export_sell_var = tk.StringVar(value=self._get_config('export_param_sell_basis', 'JSV'))
        self.export_sell_var.trace_add('write', lambda *_: self._set_config('export_param_sell_basis', self.export_sell_var.get()))
        sell_menu = ttk.Combobox(param_inner, textvariable=self.export_sell_var, width=18,
                                 values=['JSV', 'Jita Split', 'JBV'], state='readonly')
        sell_menu.grid(row=2, column=2, sticky='w', padx=(0, 12))

        # Shipping rate
        tk.Label(param_inner, text="Shipping (ISK/m³)", **lbl_cfg).grid(row=1, column=3, sticky='w', padx=(0, 4))
        self.export_ship_var = tk.StringVar(value=self._get_config('export_param_ship_rate', '125'))
        self.export_ship_var.trace_add('write', lambda *_: self._set_config('export_param_ship_rate', self.export_ship_var.get()))
        ttk.Entry(param_inner, textvariable=self.export_ship_var, width=10).grid(
            row=2, column=3, sticky='w', padx=(0, 12))

        # Collateral
        tk.Label(param_inner, text="Collateral %", **lbl_cfg).grid(row=1, column=4, sticky='w', padx=(0, 4))
        self.export_collat_var = tk.StringVar(value=self._get_config('export_param_collat_pct', '1.0'))
        self.export_collat_var.trace_add('write', lambda *_: self._set_config('export_param_collat_pct', self.export_collat_var.get()))
        ttk.Entry(param_inner, textvariable=self.export_collat_var, width=8).grid(
            row=2, column=4, sticky='w', padx=(0, 12))

        # Sales tax
        tk.Label(param_inner, text="Sales Tax %", **lbl_cfg).grid(row=1, column=5, sticky='w', padx=(0, 4))
        self.export_tax_var = tk.StringVar(value=self._get_config('export_param_tax_pct', '3.6'))
        self.export_tax_var.trace_add('write', lambda *_: self._set_config('export_param_tax_pct', self.export_tax_var.get()))
        ttk.Entry(param_inner, textvariable=self.export_tax_var, width=8).grid(
            row=2, column=5, sticky='w', padx=(0, 12))

        # Broker fee
        tk.Label(param_inner, text="Broker Fee %", **lbl_cfg).grid(row=1, column=6, sticky='w', padx=(0, 4))
        self.export_broker_var = tk.StringVar(value=self._get_config('export_param_broker_pct', '3.0'))
        self.export_broker_var.trace_add('write', lambda *_: self._set_config('export_param_broker_pct', self.export_broker_var.get()))
        ttk.Entry(param_inner, textvariable=self.export_broker_var, width=8).grid(
            row=2, column=6, sticky='w', padx=(0, 12))

        # Recalculate button
        ttk.Button(param_inner, text='⟳  Recalculate', style='Action.TButton',
                   command=self.load_export_data).grid(row=2, column=7, sticky='w', padx=(4, 0))

        # ── Quick-scenario pills ─────────────────────────────────────────────
        scenario_frame = ttk.Frame(param_card, style='Card.TFrame')
        scenario_frame.pack(fill='x', padx=12, pady=(0, 10))
        tk.Label(scenario_frame, text="Quick:", **lbl_cfg).pack(side='left', padx=(0, 8))

        scenarios = [
            ('JBV → JSV  (best case)',   'JBV', '100', 'JSV'),
            ('JBV → JBV  (safe/instant)', 'JBV', '100', 'JBV'),
            ('Split → JSV  (conservative)', 'Jita Split', '100', 'JSV'),
            ('Split → JBV  (worst case)', 'Jita Split', '100', 'JBV'),
        ]
        for label, buy, pct, sell in scenarios:
            ttk.Button(scenario_frame, text=label, style='Action.TButton',
                       command=lambda b=buy, p=pct, s=sell: self._apply_export_scenario(b, p, s)
                       ).pack(side='left', padx=3)

        # ── Summary cards ────────────────────────────────────────────────────
        self.export_summary_frame = ttk.Frame(outer)
        self.export_summary_frame.pack(fill='x', pady=(0, 8))
        self._export_summary_labels = {}
        for key, title in [('scenario', 'SCENARIO'), ('total', 'ITEMS ANALYSED'),
                            ('worth', 'WORTH EXPORTING'), ('marginal', 'MARGINAL'),
                            ('avoid', 'AVOID'), ('best', 'BEST OPPORTUNITY')]:
            card = ttk.Frame(self.export_summary_frame, style='Card.TFrame')
            card.pack(side='left', fill='both', expand=True, padx=3)
            tk.Label(card, text=title, background='#0a2030', foreground='#66d9ff',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=8, pady=(6, 0))
            val_lbl = tk.Label(card, text='—', background='#0a2030', foreground='#00ffff',
                               font=('Segoe UI', 12, 'bold'))
            val_lbl.pack(anchor='w', padx=8, pady=(0, 6))
            self._export_summary_labels[key] = val_lbl

        # ── Filter row ───────────────────────────────────────────────────────
        filter_frame = ttk.Frame(outer)
        filter_frame.pack(fill='x', pady=(0, 6))

        ttk.Label(filter_frame, text="Search:").pack(side='left', padx=(0, 4))
        self.export_search_var = tk.StringVar()
        self.export_search_var.trace_add('write', lambda *_: self._filter_export_tree())
        ttk.Entry(filter_frame, textvariable=self.export_search_var, width=18).pack(side='left', padx=(0, 12))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 4))
        self.export_cat_var = tk.StringVar(value='All')
        self.export_cat_menu = ttk.Combobox(filter_frame, textvariable=self.export_cat_var,
                                            width=20, state='readonly',
                                            values=['All', 'Minerals', 'Ice Products',
                                                    'PI Materials', 'Moon Materials',
                                                    'Salvaged Materials'])
        self.export_cat_menu.pack(side='left', padx=(0, 12))
        self.export_cat_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_export_tree())

        ttk.Label(filter_frame, text="Show:").pack(side='left', padx=(0, 4))
        self.export_show_var = tk.StringVar(value='Profitable')
        show_menu = ttk.Combobox(filter_frame, textvariable=self.export_show_var,
                                 width=16, state='readonly',
                                 values=['All', 'Profitable', 'Marginal', 'Avoid'])
        show_menu.pack(side='left', padx=(0, 4))
        show_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_export_tree())

        # ── Treeview ─────────────────────────────────────────────────────────
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill='both', expand=True)

        cols = ('category', 'item', 'volume', 'buy_price', 'sell_price',
                'ship_collat', 'profit', 'margin', 'verdict')
        self.export_tree = ttk.Treeview(tree_frame, columns=cols,
                                        show='headings', selectmode='browse')

        headings = {
            'category':   ('Category',      120, 'w'),
            'item':        ('Item',          200, 'w'),
            'volume':      ('Vol (m³)',       75, 'e'),
            'buy_price':   ('Buy Price',     110, 'e'),
            'sell_price':  ('Sell Price',    110, 'e'),
            'ship_collat': ('Ship+Tax+Fees',  115, 'e'),
            'profit':      ('Profit/unit',   105, 'e'),
            'margin':      ('Margin',         75, 'e'),
            'verdict':     ('Verdict',        90, 'center'),
        }
        for col, (heading, width, anchor) in headings.items():
            self.export_tree.heading(col, text=heading,
                                     command=lambda c=col: self._sort_export_tree(c))
            self.export_tree.column(col, width=width, anchor=anchor, stretch=(col == 'item'))

        # Tag colours
        self.export_tree.tag_configure('great',    foreground='#00ff88')
        self.export_tree.tag_configure('good',     foreground='#88ff66')
        self.export_tree.tag_configure('marginal', foreground='#ffcc44')
        self.export_tree.tag_configure('avoid',    foreground='#ff6666')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.export_tree.yview)
        self.export_tree.configure(yscrollcommand=vsb.set)
        self.export_tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # Footer
        ttk.Label(outer,
                  text="JBV = best buy order · JSV = best sell order · Split = midpoint  |  "
                       "Margin = (Sell − Buy − Ship − Collat) ÷ Sell  |  "
                       "Prices from market_price_snapshots (Jita)",
                  foreground='#2a5070', background='#0d1117',
                  font=('Segoe UI', 9)).pack(anchor='w', pady=(4, 0))

        # Internal data store for filtering/sorting
        self._export_all_rows = []
        self._export_sort_col = 'margin'
        self._export_sort_asc = False

    def _apply_export_scenario(self, buy, pct, sell):
        self.export_buy_var.set(buy)
        self.export_buy_pct_var.set(pct)
        self.export_sell_var.set(sell)
        self.load_export_data()

    def _price_for_basis(self, basis, best_buy, best_sell):
        if basis == 'JBV':
            return best_buy or best_sell   # fall back to sell when no buy orders exist
        elif basis == 'JSV':
            return best_sell
        else:  # Jita Split
            return ((best_buy or best_sell) + best_sell) / 2

    def load_export_data(self):
        """Query DB and populate the export treeview."""
        try:
            ship_rate  = float(self.export_ship_var.get())
            collat_pct = float(self.export_collat_var.get()) / 100.0
            buy_pct    = float(self.export_buy_pct_var.get()) / 100.0
            tax_pct    = float(self.export_tax_var.get()) / 100.0
            broker_pct = float(self.export_broker_var.get()) / 100.0
        except ValueError:
            messagebox.showerror("Invalid Input", "All parameters must be numeric.")
            return

        buy_basis  = self.export_buy_var.get()
        sell_basis = self.export_sell_var.get()
        # Broker fee only applies when placing an order (JSV or Split), not instant sell (JBV)
        effective_broker = 0.0 if sell_basis == 'JBV' else broker_pct

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT it.type_name,
                   tmi.category,
                   it.volume,
                   mps.best_buy,
                   mps.best_sell
            FROM tracked_market_items tmi
            JOIN inv_types it            ON tmi.type_id = it.type_id
            JOIN market_price_snapshots mps ON tmi.type_id = mps.type_id
            WHERE mps.timestamp = (
                SELECT MAX(timestamp) FROM market_price_snapshots
                WHERE type_id = tmi.type_id
            )
              AND mps.best_sell > 0
            ORDER BY tmi.category, it.type_name
        """)
        rows = cursor.fetchall()

        # Timestamp of newest snapshot
        cursor.execute("SELECT MAX(timestamp) FROM market_price_snapshots")
        snap_ts = cursor.fetchone()[0] or '—'
        conn.close()

        self._export_all_rows = []
        counts = {'great': 0, 'good': 0, 'marginal': 0, 'avoid': 0}
        best_name, best_margin = '—', -999

        for name, category, volume, best_buy, best_sell in rows:
            buy_price    = self._price_for_basis(buy_basis,  best_buy, best_sell) * buy_pct
            gross_sell   = self._price_for_basis(sell_basis, best_buy, best_sell)
            ship_cost    = volume * ship_rate
            collat       = buy_price * collat_pct
            sales_tax    = gross_sell * tax_pct
            broker_fee   = gross_sell * effective_broker
            net_sell     = gross_sell - sales_tax - broker_fee
            total_cost   = buy_price + ship_cost + collat
            profit       = net_sell - total_cost
            margin       = (profit / net_sell * 100) if net_sell > 0 else 0

            if margin >= 5:
                tag, verdict = 'great', '✓ Export'
                counts['great'] += 1
            elif margin >= 1:
                tag, verdict = 'good', '✓ Export'
                counts['good'] += 1
            elif margin >= 0:
                tag, verdict = 'marginal', '~ Marginal'
                counts['marginal'] += 1
            else:
                tag, verdict = 'avoid', '✕ Avoid'
                counts['avoid'] += 1

            if margin > best_margin:
                best_margin, best_name = margin, name

            cat_display = {
                'minerals': 'Minerals', 'ice_products': 'Ice Products',
                'moon_materials': 'Moon Materials', 'pi_materials': 'PI Materials',
                'salvaged_materials': 'Salvaged Materials',
            }.get(category, category.replace('_', ' ').title())

            self._export_all_rows.append({
                'category':    cat_display,
                'item':        name,
                'volume':      volume,
                'buy_price':   buy_price,
                'sell_price':  net_sell,
                'ship_collat': ship_cost + collat + sales_tax + broker_fee,
                'profit':      profit,
                'margin':      margin,
                'verdict':     verdict,
                'tag':         tag,
            })

        # Update summary cards
        total = len(self._export_all_rows)
        worth = counts['great'] + counts['good']
        broker_note = f"  (tax {tax_pct*100:.1f}%  broker {effective_broker*100:.1f}%)"
        self._export_summary_labels['scenario'].configure(
            text=f"{buy_basis} → {sell_basis}{broker_note}", foreground='#66d9ff')
        self._export_summary_labels['total'].configure(
            text=str(total), foreground='#00ffff')
        self._export_summary_labels['worth'].configure(
            text=str(worth), foreground='#00ff88')
        self._export_summary_labels['marginal'].configure(
            text=str(counts['marginal']), foreground='#ffcc44')
        self._export_summary_labels['avoid'].configure(
            text=str(counts['avoid']), foreground='#ff6666')
        self._export_summary_labels['best'].configure(
            text=f"{best_name}  {best_margin:.1f}%", foreground='#00ff88')

        self._filter_export_tree()
        self.update_status(f"Export analysis updated — {snap_ts[:16] if len(snap_ts) > 16 else snap_ts}")

    def _filter_export_tree(self):
        """Apply search/category/show filters and repopulate treeview."""
        search = self.export_search_var.get().lower()
        cat_filter = self.export_cat_var.get()
        show = self.export_show_var.get()

        filtered = []
        for row in self._export_all_rows:
            if search and search not in row['item'].lower():
                continue
            if cat_filter != 'All' and row['category'] != cat_filter:
                continue
            if show == 'Profitable' and row['tag'] not in ('great', 'good'):
                continue
            if show == 'Marginal' and row['tag'] != 'marginal':
                continue
            if show == 'Avoid' and row['tag'] != 'avoid':
                continue
            filtered.append(row)

        # Sort
        reverse = not self._export_sort_asc
        col = self._export_sort_col
        filtered.sort(key=lambda r: r[col] if isinstance(r[col], (int, float))
                      else r[col].lower(), reverse=reverse)

        self.export_tree.delete(*self.export_tree.get_children())
        for row in filtered:
            self.export_tree.insert('', 'end', tags=(row['tag'],), values=(
                row['category'],
                row['item'],
                f"{row['volume']:.2f}",
                f"{row['buy_price']:,.0f}",
                f"{row['sell_price']:,.0f}",
                f"{row['ship_collat']:,.0f}",
                f"{row['profit']:,.0f}",
                f"{row['margin']:.1f}%",
                row['verdict'],
            ))

    def _sort_export_tree(self, col):
        """Toggle sort on column click."""
        if self._export_sort_col == col:
            self._export_sort_asc = not self._export_sort_asc
        else:
            self._export_sort_col = col
            self._export_sort_asc = col in ('category', 'item')
        self._filter_export_tree()

    # ===== IMPORT ANALYSIS =====

    def build_ore_import_tab(self):
        """Build the Ore Import Analysis tab."""
        import threading as _threading
        self._ore_threading = _threading

        outer = ttk.Frame(self.ore_import_frame)
        outer.pack(fill='both', expand=True, padx=15, pady=(15, 10))

        ttk.Label(outer,
                  text="Buy raw ore / ice / moon ore at Jita 4-4  \u2192  Ship to null-sec  \u2192  Refine at 100%  \u2192  Sell products locally.",
                  style='SubHeader.TLabel').pack(anchor='w', pady=(0, 8))

        # ── Fetch + params card ──────────────────────────────────────────
        fetch_card = ttk.Frame(outer, style='Card.TFrame')
        fetch_card.pack(fill='x', pady=(0, 8))
        fetch_inner = ttk.Frame(fetch_card, style='Card.TFrame')
        fetch_inner.pack(fill='x', padx=12, pady=10)

        param_inner = ttk.Frame(fetch_inner, style='Card.TFrame')
        param_inner.pack(side='left', fill='x', expand=True)

        lbl_cfg = dict(background='#0a2030', foreground='#88d0e8', font=('Segoe UI', 10))
        hdr_cfg = dict(background='#0a2030', font=('Segoe UI', 8, 'bold'))

        tk.Label(param_inner, text="BUY SIDE", foreground='#66d9ff', **hdr_cfg).grid(
                 row=0, column=0, columnspan=3, sticky='w', pady=(0, 4))
        tk.Label(param_inner, text="LOGISTICS", foreground='#ffcc44', **hdr_cfg).grid(
                 row=0, column=4, columnspan=2, sticky='w', padx=(12, 0), pady=(0, 4))

        tk.Frame(param_inner, background='#1a3040', height=1).grid(
                 row=1, column=0, columnspan=7, sticky='ew', pady=(0, 6))

        # Buy From
        tk.Label(param_inner, text="Buy From", **lbl_cfg).grid(row=2, column=0, sticky='w', padx=(0, 4))
        self.ore_buy_var = tk.StringVar(value=self._get_config('ore_param_buy_basis', 'JSV  (instant)'))
        self.ore_buy_var.trace_add('write', lambda *_: self._set_config('ore_param_buy_basis', self.ore_buy_var.get()))
        self.ore_buy_var.trace_add('write', lambda *_: self._update_ore_jbv_columns())
        ttk.Combobox(param_inner, textvariable=self.ore_buy_var, width=18,
                     values=['JSV  (instant)', 'JBV  (place order)'],
                     state='readonly').grid(row=3, column=0, sticky='w', padx=(0, 10))

        # Buy %
        tk.Label(param_inner, text="Buy %", **lbl_cfg).grid(row=2, column=1, sticky='w', padx=(0, 4))
        self.ore_buy_pct_var = tk.StringVar(value=self._get_config('ore_param_buy_pct', '100'))
        self.ore_buy_pct_var.trace_add('write', lambda *_: self._set_config('ore_param_buy_pct', self.ore_buy_pct_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_buy_pct_var, width=8).grid(
                  row=3, column=1, sticky='w', padx=(0, 10))

        # Broker fee
        tk.Label(param_inner, text="Broker Fee %", **lbl_cfg).grid(row=2, column=2, sticky='w', padx=(0, 4))
        self.ore_broker_var = tk.StringVar(value=self._get_config('ore_param_broker_pct', '0.0'))
        self.ore_broker_var.trace_add('write', lambda *_: self._set_config('ore_param_broker_pct', self.ore_broker_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_broker_var, width=8).grid(
                  row=3, column=2, sticky='w', padx=(0, 16))

        # Divider
        tk.Frame(param_inner, background='#1a3040', width=1).grid(
                 row=2, column=3, rowspan=2, sticky='ns', padx=(0, 12))

        # Shipping
        tk.Label(param_inner, text="Shipping (ISK/m\u00b3)", **lbl_cfg).grid(row=2, column=4, sticky='w', padx=(0, 4))
        self.ore_ship_var = tk.StringVar(value=self._get_config('ore_param_ship_rate', '125'))
        self.ore_ship_var.trace_add('write', lambda *_: self._set_config('ore_param_ship_rate', self.ore_ship_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_ship_var, width=10).grid(
                  row=3, column=4, sticky='w', padx=(0, 10))

        # Collateral
        tk.Label(param_inner, text="Collateral %", **lbl_cfg).grid(row=2, column=5, sticky='w', padx=(0, 4))
        self.ore_collat_var = tk.StringVar(value=self._get_config('ore_param_collat_pct', '1.0'))
        self.ore_collat_var.trace_add('write', lambda *_: self._set_config('ore_param_collat_pct', self.ore_collat_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_collat_var, width=8).grid(
                  row=3, column=5, sticky='w', padx=(0, 10))

        # Refining Efficiency
        tk.Label(param_inner, text="Refine Eff %", **lbl_cfg).grid(row=2, column=6, sticky='w', padx=(0, 4))
        self.ore_refine_var = tk.StringVar(value=self._get_config('ore_param_refine_eff', '87.5'))
        self.ore_refine_var.trace_add('write', lambda *_: self._set_config('ore_param_refine_eff', self.ore_refine_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_refine_var, width=8).grid(
                  row=3, column=6, sticky='w', padx=(0, 10))

        # Deviation window
        tk.Label(param_inner, text="Dev Window (days)", **lbl_cfg).grid(row=2, column=7, sticky='w', padx=(0, 4))
        self.ore_dev_days_var = tk.StringVar(value=self._get_config('ore_param_dev_days', '7'))
        self.ore_dev_days_var.trace_add('write', lambda *_: self._set_config('ore_param_dev_days', self.ore_dev_days_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_dev_days_var, width=6).grid(
                  row=3, column=7, sticky='w', padx=(0, 10))

        # Target Margin % (buy order analysis)
        tk.Label(param_inner, text="Target Margin %", **lbl_cfg).grid(row=2, column=9, sticky='w', padx=(8, 4))
        self.ore_target_margin_var = tk.StringVar(value=self._get_config('ore_param_target_margin', '5.0'))
        self.ore_target_margin_var.trace_add('write', lambda *_: self._set_config('ore_param_target_margin', self.ore_target_margin_var.get()))
        ttk.Entry(param_inner, textvariable=self.ore_target_margin_var, width=6).grid(
                  row=3, column=9, sticky='w', padx=(8, 10))

        # Recalculate
        ttk.Button(param_inner, text='\u27f3  Recalculate', style='Action.TButton',
                   command=self.load_ore_import_data).grid(row=3, column=8, sticky='w', padx=(8, 0))

        # Fetch buttons + status (right side)
        fetch_right = ttk.Frame(fetch_inner, style='Card.TFrame')
        fetch_right.pack(side='right', anchor='ne', padx=(20, 0))

        btn_row = ttk.Frame(fetch_right, style='Card.TFrame')
        btn_row.pack(anchor='e')
        tk.Label(btn_row, text='Fetch:', background='#0a2030',
                 foreground='#88d0e8', font=('Segoe UI', 9)).pack(side='left', padx=(0, 6))
        self._ore_fetch_btns = {}
        for label, cat in [('All', 'all'), ('Standard', 'standard'),
                            ('Ice', 'ice'), ('Moon', 'moon')]:
            btn = ttk.Button(btn_row, text=f'\u27f3 {label}',
                             style='Action.TButton',
                             command=lambda c=cat: self._run_ore_fetch(c))
            btn.pack(side='left', padx=(0, 4))
            self._ore_fetch_btns[cat] = btn

        self.ore_price_age_lbl = tk.Label(fetch_right,
            text='\u26a0 Not loaded \u2014 click Fetch to begin',
            background='#0a2030', foreground='#ffcc44',
            font=('Segoe UI', 8))
        self.ore_price_age_lbl.pack(anchor='e', pady=(4, 0))

        # ── Product sell prices card (collapsible sections) ─────────────
        prices_card = ttk.Frame(outer, style='Card.TFrame')
        prices_card.pack(fill='x', pady=(0, 8))

        tk.Label(prices_card,
                 text="PRODUCT SELL PRICES  (% of Jita JBV \u2014 adjust each product to match your local buyback rates)",
                 background='#0a2030', foreground='#00d9ff',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=12, pady=(8, 4))

        self.ore_product_pct = {}  # type_id (int) -> StringVar

        self._build_mineral_price_section(prices_card, expanded=True)
        self._build_ice_product_price_section(prices_card, expanded=True)
        self._build_moon_material_price_section(prices_card, expanded=False)

        tk.Frame(prices_card, background='#1a3040', height=1).pack(fill='x', padx=12, pady=(2, 6))

        # ── Ore type filter ──────────────────────────────────────────────
        type_row = ttk.Frame(outer)
        type_row.pack(fill='x', pady=(0, 6))

        tk.Label(type_row, text="Filter:", background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 10)).pack(side='left', padx=(0, 8))

        self._ore_type_filter_val = 'all'
        self._ore_type_btns = {}
        for label, val in [('All', 'all'), ('Standard', 'standard'),
                            ('Ice', 'ice'), ('Moon', 'moon')]:
            btn = ttk.Button(type_row, text=label,
                             command=lambda v=val: self._set_ore_type_filter(v))
            btn.pack(side='left', padx=3)
            self._ore_type_btns[val] = btn

        self._ore_type_lbl = tk.Label(type_row, text='Showing: All',
            background='#0a1520', foreground='#00ff88', font=('Segoe UI', 9))
        self._ore_type_lbl.pack(side='left', padx=(12, 0))

        # Compression toggle (right side of same row)
        tk.Frame(type_row, background='#1a3040', width=1).pack(side='left', fill='y', padx=(16, 8))
        tk.Label(type_row, text="Form:", background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 10)).pack(side='left', padx=(0, 6))
        self._ore_comp_filter = tk.StringVar(value='compressed')
        for label, val in [('Compressed', 'compressed'), ('Uncompressed', 'uncompressed'), ('Both', 'both')]:
            ttk.Button(type_row, text=label,
                       command=lambda v=val: self._set_ore_comp_filter(v)
                       ).pack(side='left', padx=3)
        self._ore_comp_lbl = tk.Label(type_row, text='',
            background='#0a1520', foreground='#66d9ff', font=('Segoe UI', 9))
        self._ore_comp_lbl.pack(side='left', padx=(8, 0))

        # ── Summary cards ────────────────────────────────────────────────
        self.ore_summary_frame = ttk.Frame(outer)
        self.ore_summary_frame.pack(fill='x', pady=(0, 6))
        self._ore_summary_labels = {}
        for key, title in [('total', 'ORES ANALYSED'), ('profitable', 'PROFITABLE'),
                            ('best', 'BEST MARGIN'), ('best_isk', 'BEST ISK/BATCH'),
                            ('worst', 'WORST MARGIN')]:
            card = ttk.Frame(self.ore_summary_frame, style='Card.TFrame')
            card.pack(side='left', fill='both', expand=True, padx=3)
            tk.Label(card, text=title, background='#0a2030', foreground='#66d9ff',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=8, pady=(6, 0))
            val_lbl = tk.Label(card, text='\u2014', background='#0a2030',
                               foreground='#c8e8f0', font=('Segoe UI', 12, 'bold'))
            val_lbl.pack(anchor='w', padx=8, pady=(0, 6))
            self._ore_summary_labels[key] = val_lbl

        # ── Filter/sort row ──────────────────────────────────────────────
        frow = ttk.Frame(outer)
        frow.pack(fill='x', pady=(0, 4))

        # View toggle
        tk.Label(frow, text="View:", background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 10)).pack(side='left', padx=(0, 4))
        self._ore_view_btn_ore = ttk.Button(frow, text='By Ore',
                                            command=lambda: self._set_ore_view('ore'))
        self._ore_view_btn_ore.pack(side='left', padx=(0, 3))
        self._ore_view_btn_product = ttk.Button(frow, text='By Product',
                                                command=lambda: self._set_ore_view('product'))
        self._ore_view_btn_product.pack(side='left', padx=(0, 12))
        tk.Frame(frow, background='#1a3040', width=1).pack(side='left', fill='y', padx=(0, 10))

        ttk.Label(frow, text="Search:").pack(side='left', padx=(0, 4))
        self.ore_search_var = tk.StringVar()
        self.ore_search_var.trace_add('write', lambda *_: self._filter_active_ore_view())
        ttk.Entry(frow, textvariable=self.ore_search_var, width=20).pack(side='left', padx=(0, 12))

        ttk.Label(frow, text="Show:").pack(side='left', padx=(0, 4))
        self.ore_show_var = tk.StringVar(value='All')
        ttk.Combobox(frow, textvariable=self.ore_show_var, width=14,
                     values=['All', 'Profitable', 'Loss Only'], state='readonly').pack(side='left', padx=(0, 12))
        self.ore_show_var.trace_add('write', lambda *_: self._filter_active_ore_view())

        ttk.Label(frow, text="Sort:").pack(side='left', padx=(0, 4))
        self.ore_sort_display_var = tk.StringVar(value='Margin %')
        self.ore_sort_cb = ttk.Combobox(frow, textvariable=self.ore_sort_display_var, width=16,
                     values=['Margin %', 'Profit/Unit', 'Landed/Unit', 'Value/Unit', 'Deviation %',
                             'Max Bid', 'Sug Bid', 'Bid Headroom', 'Volatility %'],
                     state='readonly')
        self.ore_sort_cb.pack(side='left')
        self.ore_sort_display_var.trace_add('write', lambda *_: self._filter_active_ore_view())

        # ── Treeview container ───────────────────────────────────────────
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill='both', expand=True)

        # ── Ore view sub-frame ───────────────────────────────────────────
        self.ore_tree_frame = ttk.Frame(tree_frame)
        self.ore_tree_frame.pack(fill='both', expand=True)

        cols = ('name', 'jita_buy', 'logistics', 'landed', 'value', 'profit', 'margin', 'dev',
                'max_bid', 'sug_bid', 'bid_room', 'volatility')
        self.ore_tree = ttk.Treeview(self.ore_tree_frame, columns=cols, show='headings', selectmode='browse')

        col_defs = [
            ('name',       'Ore Name',             200, 'w'),
            ('jita_buy',   'Jita/Unit (ISK)',       120, 'e'),
            ('logistics',  'Logistics/Unit',        110, 'e'),
            ('landed',     'Landed/Unit (ISK)',     115, 'e'),
            ('value',      'Value/Unit (ISK)',      115, 'e'),
            ('profit',     'Profit/Unit (ISK)',     110, 'e'),
            ('margin',     'Margin %',               80, 'e'),
            ('dev',        'vs N-Day Avg %',        100, 'e'),
            # ── Buy order analysis ──────────────────────────
            ('max_bid',    'Max Bid/Unit',          115, 'e'),
            ('sug_bid',    'Sug Bid/Unit',          110, 'e'),
            ('bid_room',   'Bid Headroom %',         95, 'e'),
            ('volatility', '7d Volatility %',        90, 'e'),
        ]
        for cid, heading, width, anchor in col_defs:
            self.ore_tree.heading(cid, text=heading,
                                  command=lambda c=cid: self._sort_ore_tree(c))
            self.ore_tree.column(cid, width=width, minwidth=50, anchor=anchor)

        self.ore_tree.tag_configure('profitable', foreground='#00ff88')
        self.ore_tree.tag_configure('marginal',   foreground='#ffcc44')
        self.ore_tree.tag_configure('loss',       foreground='#ff4444')
        self.ore_tree.tag_configure('group_hdr',  background='#070e18',
                                                  foreground='#446688',
                                                  font=('Segoe UI', 8, 'italic'))
        self.ore_tree.tag_configure('row_a', background='#0a2030')
        self.ore_tree.tag_configure('row_b', background='#0d2535')
        self.ore_tree.tag_configure('dev_high', foreground='#ff7744')
        self.ore_tree.tag_configure('dev_low',  foreground='#44ddaa')

        vsb = ttk.Scrollbar(self.ore_tree_frame, orient='vertical',   command=self.ore_tree.yview)
        hsb = ttk.Scrollbar(self.ore_tree_frame, orient='horizontal', command=self.ore_tree.xview)
        self.ore_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right',  fill='y')
        hsb.pack(side='bottom', fill='x')
        self.ore_tree.pack(fill='both', expand=True)

        # ── Product view sub-frame (hidden by default) ───────────────────
        self.product_tree_frame = ttk.Frame(tree_frame)

        prod_cols = ('product', 'category', 'source', 'cost_unit',
                     'sell_price', 'jita_jbv', 'profit_unit', 'margin')
        self.product_tree = ttk.Treeview(self.product_tree_frame, columns=prod_cols,
                                         show='headings', selectmode='browse')
        prod_col_defs = [
            ('product',     'Product',          200, 'w'),
            ('category',    'Category',         115, 'w'),
            ('source',      'Best Source Ore',  210, 'w'),
            ('cost_unit',   'Cost / Unit',      120, 'e'),
            ('sell_price',  'Your Sell Price',  120, 'e'),
            ('jita_jbv',    'Jita JBV',         110, 'e'),
            ('profit_unit', 'Profit / Unit',    115, 'e'),
            ('margin',      'Margin %',          90, 'e'),
        ]
        for cid, heading, width, anchor in prod_col_defs:
            self.product_tree.heading(cid, text=heading,
                                      command=lambda c=cid: self._sort_product_tree(c))
            self.product_tree.column(cid, width=width, minwidth=50, anchor=anchor)

        self.product_tree.tag_configure('profitable', foreground='#00ff88')
        self.product_tree.tag_configure('marginal',   foreground='#ffcc44')
        self.product_tree.tag_configure('loss',       foreground='#ff4444')
        self.product_tree.tag_configure('group_hdr',  background='#070e18',
                                                      foreground='#446688',
                                                      font=('Segoe UI', 8, 'italic'))
        self.product_tree.tag_configure('row_a',    background='#0a2030')
        self.product_tree.tag_configure('row_b',    background='#0d2535')
        self.product_tree.tag_configure('row_ice',  background='#0a1828')
        self.product_tree.tag_configure('row_moon', background='#110a20')

        prod_vsb = ttk.Scrollbar(self.product_tree_frame, orient='vertical',
                                  command=self.product_tree.yview)
        prod_hsb = ttk.Scrollbar(self.product_tree_frame, orient='horizontal',
                                  command=self.product_tree.xview)
        self.product_tree.configure(yscrollcommand=prod_vsb.set, xscrollcommand=prod_hsb.set)
        prod_vsb.pack(side='right',  fill='y')
        prod_hsb.pack(side='bottom', fill='x')
        self.product_tree.pack(fill='both', expand=True)

        self._ore_all_rows     = []
        self._product_all_rows = []
        self._ore_sort_col     = 'margin'
        self._ore_sort_asc     = False
        self._product_sort_col = 'margin'
        self._product_sort_asc = False
        self._ore_view         = 'ore'
        self._ore_prices_snap  = {}
        self._ore_refine_eff   = 1.0
        self.root.after(0, self._update_ore_jbv_columns)

    # ── Reaction Analysis tab ────────────────────────────────────────────────

    def build_reaction_tab(self):
        """Build the Reaction Analysis tab (import vs react cost comparison)."""
        self._reaction_formulas = {}   # product_type_id -> formula dict (loaded lazily)
        self._reaction_rows     = []   # computed row dicts for sorting/filtering

        outer = ttk.Frame(self.reaction_frame, style='Card.TFrame')
        outer.pack(fill='both', expand=True)

        # ── Parameters card ──────────────────────────────────────────────────
        pcf = ttk.Frame(outer, style='Card.TFrame')
        pcf.pack(fill='x', padx=12, pady=(8, 4))
        tk.Label(pcf, text='REACTION PARAMETERS',
                 background='#0a2030', foreground='#ffcc44',
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=8, pady=(6, 4))

        prow = ttk.Frame(pcf, style='Card.TFrame')
        prow.pack(fill='x', padx=8, pady=(0, 8))

        lbl_cfg = dict(background='#0a2030', foreground='#aabbcc', font=('Segoe UI', 8))
        ent_w   = 9

        def _param(parent, label, default, config_key, col):
            tk.Label(parent, text=label, **lbl_cfg).grid(row=0, column=col*2,   sticky='w', padx=(0 if col==0 else 12, 4))
            var = tk.StringVar(value=self._get_config(config_key, default))
            var.trace_add('write', lambda *_: self._set_config(config_key, var.get()))
            ttk.Entry(parent, textvariable=var, width=ent_w).grid(row=0, column=col*2+1, sticky='w')
            return var

        self._rxn_ship_var    = _param(prow, 'Shipping (ISK/m³)', '125',  'rxn_ship_rate',  0)
        self._rxn_collat_var  = _param(prow, 'Collateral %',       '1.0',  'rxn_collat_pct', 1)
        self._rxn_sci_var     = _param(prow, 'Sys Cost Index %',   '6.14', 'rxn_sci',        2)
        self._rxn_scc_var     = _param(prow, 'SCC Surcharge %',    '4.00', 'rxn_scc',        3)
        self._rxn_tax_var     = _param(prow, 'Facility Tax %',     '0.5',  'rxn_tax',        4)
        self._rxn_me_var      = _param(prow, 'Tatara ME %',        '1.0',  'rxn_me',         5)

        ttk.Button(prow, text='\u27f3  Calculate',
                   style='Action.TButton',
                   command=self._calc_reactions).grid(row=0, column=12, padx=(18, 0))

        # Price age label
        self._rxn_price_lbl = tk.Label(prow,
            text='\u26a0 Click Calculate to load',
            background='#0a2030', foreground='#ffcc44', font=('Segoe UI', 8))
        self._rxn_price_lbl.grid(row=0, column=13, padx=(10, 0))

        # Row 2: sell target + input basis
        tk.Label(prow, text='Local Sell % of JBV', **lbl_cfg).grid(
            row=1, column=0, sticky='w', pady=(6, 0))
        self._rxn_sell_pct_var = tk.StringVar(value=self._get_config('rxn_sell_pct', '95.0'))
        self._rxn_sell_pct_var.trace_add('write',
            lambda *_: self._set_config('rxn_sell_pct', self._rxn_sell_pct_var.get()))
        ttk.Entry(prow, textvariable=self._rxn_sell_pct_var, width=ent_w).grid(
            row=1, column=1, sticky='w', pady=(6, 0))

        tk.Label(prow, text='Input Basis', **lbl_cfg).grid(
            row=1, column=2, sticky='w', padx=(12, 4), pady=(6, 0))
        self._rxn_input_basis_var = tk.StringVar(value=self._get_config('rxn_input_basis', 'JSV'))
        self._rxn_input_basis_var.trace_add('write',
            lambda *_: self._set_config('rxn_input_basis', self._rxn_input_basis_var.get()))
        ttk.Combobox(prow, textvariable=self._rxn_input_basis_var, width=7,
                     values=['JSV', 'JBV'], state='readonly').grid(
            row=1, column=3, sticky='w', pady=(6, 0))

        # ── Sort row ──────────────────────────────────────────────────────────
        frow = ttk.Frame(outer, style='Card.TFrame')
        frow.pack(fill='x', padx=12, pady=(0, 4))

        tk.Label(frow, text='Sort:', background='#0a2030',
                 foreground='#aabbcc', font=('Segoe UI', 8)).pack(side='left', padx=(4, 4))
        self._rxn_sort_var = tk.StringVar(value='React Margin %')
        ttk.Combobox(frow, textvariable=self._rxn_sort_var, width=16,
                     values=['Item', 'React Margin %'], state='readonly').pack(side='left')
        self._rxn_sort_var.trace_add('write', lambda *_: self._rxn_populate_trees())

        # ── Two side-by-side treeviews ────────────────────────────────────────
        tables_frame = ttk.Frame(outer, style='Card.TFrame')
        tables_frame.pack(fill='both', expand=True, padx=12, pady=(0, 8))

        cols = ('item', 'jita_sell', 'react_margin', 'inputs')
        col_defs = [
            ('item',         'Item',           180, 'w'),
            ('jita_sell',    'JSV/u',           90, 'e'),
            ('react_margin', 'React Margin %', 100, 'e'),
            ('inputs',       'Key Inputs',     220, 'w'),
        ]
        tag_cfg = [
            ('win',      {'foreground': '#00ff88'}),
            ('marginal', {'foreground': '#ffcc44'}),
            ('loss',     {'foreground': '#ff4444'}),
            ('row_a',    {'background': '#0a2030'}),
            ('row_b',    {'background': '#0d2535'}),
        ]

        def _make_tree(parent, title):
            tk.Label(parent, text=title, background='#0a2030', foreground='#7799bb',
                     font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=6, pady=(4, 2))
            tf = ttk.Frame(parent)
            tf.pack(fill='both', expand=True)
            tree = ttk.Treeview(tf, columns=cols, show='headings', selectmode='browse')
            for cid, heading, width, anchor in col_defs:
                tree.heading(cid, text=heading,
                             command=lambda c=cid: self._rxn_sort_col(c))
                tree.column(cid, width=width, minwidth=40, anchor=anchor)
            for tag, cfg in tag_cfg:
                tree.tag_configure(tag, **cfg)
            vsb = ttk.Scrollbar(tf, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            vsb.pack(side='right', fill='y')
            tree.pack(fill='both', expand=True)
            return tree

        lf = ttk.Frame(tables_frame, style='Card.TFrame')
        lf.pack(side='left', fill='both', expand=True, padx=(0, 4))
        self._rxn_proc_tree = _make_tree(lf, '── Processed Moon Materials ──')

        rf = ttk.Frame(tables_frame, style='Card.TFrame')
        rf.pack(side='left', fill='both', expand=True, padx=(4, 0))
        self._rxn_adv_tree = _make_tree(rf, '── Advanced (Composite) Materials ──')

    def _load_reaction_formulas(self):
        """Parse blueprints.jsonl and extract Processed + Advanced moon reaction formulas."""
        import json, math, sqlite3

        # Blueprint typeIDs for Processed (Intermediate) moon reactions bp 46166-46186
        # and Advanced (Composite) moon reactions bp 46204-46218.
        # Unrefined variants (46187-46203) and old Simple/Complex Reactions (17941+) excluded.
        PROCESSED_BP_RANGE = range(46166, 46187)
        ADVANCED_BP_RANGE  = range(46204, 46219)

        bp_data = {}
        with open(os.path.join(PROJECT_DIR, 'sde', 'blueprints.jsonl'), 'r', encoding='utf-8') as f:
            for line in f:
                obj = json.loads(line)
                bp_id = obj['blueprintTypeID']
                if bp_id in PROCESSED_BP_RANGE or bp_id in ADVANCED_BP_RANGE:
                    if 'reaction' in obj.get('activities', {}):
                        bp_data[bp_id] = obj['activities']['reaction']

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()

        # Collect all type_ids we need to name
        all_ids = set()
        for data in bp_data.values():
            for m in data.get('materials', []): all_ids.add(m['typeID'])
            for p in data.get('products',  []): all_ids.add(p['typeID'])

        ph = ','.join('?'*len(all_ids))
        c.execute(f'SELECT type_id, type_name, volume FROM inv_types WHERE type_id IN ({ph})',
                  list(all_ids))
        type_info = {r[0]: {'name': r[1], 'vol': r[2] or 0.0} for r in c.fetchall()}
        conn.close()

        # Fuel block type IDs
        FUEL_IDS = {4051, 4246, 4247, 4312}

        self._reaction_formulas = {}
        for bp_id, data in bp_data.items():
            products = data.get('products', [])
            if not products:
                continue
            p         = products[0]
            prod_id   = p['typeID']
            out_qty   = p['quantity']
            tier      = 'Processed' if bp_id in PROCESSED_BP_RANGE else 'Advanced'

            inputs     = []
            fuel_entry = None
            for m in data.get('materials', []):
                if m['typeID'] in FUEL_IDS:
                    fuel_entry = (m['typeID'], m['quantity'])
                else:
                    inputs.append((m['typeID'], m['quantity']))

            prod_info = type_info.get(prod_id, {})
            self._reaction_formulas[prod_id] = {
                'bp_id':    bp_id,
                'tier':     tier,
                'name':     prod_info.get('name', str(prod_id)),
                'vol':      prod_info.get('vol', 0.0),
                'out_qty':  out_qty,
                'inputs':   inputs,   # [(type_id, base_qty), ...]
                'fuel':     fuel_entry,
                'type_info': type_info,
            }

    def _calc_reactions(self):
        """Fetch Jita prices, compute import vs react cost, populate treeview."""
        import math, sqlite3

        if not self._reaction_formulas:
            self._load_reaction_formulas()

        try:
            ship_rate  = float(self._rxn_ship_var.get())
            collat_pct = float(self._rxn_collat_var.get()) / 100.0
            sci        = float(self._rxn_sci_var.get())    / 100.0
            scc        = float(self._rxn_scc_var.get())    / 100.0
            tax        = float(self._rxn_tax_var.get())    / 100.0
            me_pct     = float(self._rxn_me_var.get())     / 100.0
            sell_pct   = float(self._rxn_sell_pct_var.get()) / 100.0
        except ValueError:
            messagebox.showerror('Invalid Input', 'All parameters must be numeric.')
            return

        use_jsv   = self._rxn_input_basis_var.get().upper() == 'JSV'
        # me_factor: ratio of inputs consumed after structure ME bonus
        me_factor = 1.0 - me_pct   # e.g. 0.99 for 1% ME

        # Collect all type_ids we need prices for
        all_ids = set()
        for f in self._reaction_formulas.values():
            for tid, _ in f['inputs']:
                all_ids.add(tid)
            if f['fuel']:
                all_ids.add(f['fuel'][0])
        all_ids.update(self._reaction_formulas.keys())

        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        ph = ','.join('?'*len(all_ids))
        cursor.execute(f"""
            SELECT type_id, best_buy, best_sell
            FROM market_price_snapshots mps
            WHERE type_id IN ({ph})
              AND timestamp = (SELECT MAX(timestamp) FROM market_price_snapshots
                               WHERE type_id = mps.type_id)
        """, list(all_ids))
        prices = {r[0]: (r[1] or 0.0, r[2] or 0.0) for r in cursor.fetchall()}

        cursor.execute('SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id IN (%s)' % ph,
                       list(all_ids))
        snap_ts = cursor.fetchone()[0]
        conn.close()

        if snap_ts:
            self._rxn_price_lbl.configure(
                text=f'Prices: {snap_ts[:19].replace("T", " ")} UTC', foreground='#00ff88')
        else:
            self._rxn_price_lbl.configure(
                text='\u26a0 No price data — fetch market prices first', foreground='#ffaa44')

        type_info = {}
        for f in self._reaction_formulas.values():
            type_info.update(f['type_info'])

        self._reaction_rows = []

        for prod_id, f in self._reaction_formulas.items():
            out_qty   = f['out_qty']
            prod_sell = prices.get(prod_id, (0.0, 0.0))[1]   # Jita JSV (what we pay to import)
            prod_jbv  = prices.get(prod_id, (0.0, 0.0))[0]   # Jita JBV (basis for local sell price)
            prod_vol  = f['vol']

            # ── Local sell price (our revenue per unit) ───────────────────
            your_sell = prod_jbv * sell_pct if prod_jbv > 0 else None

            # ── Import cost (buy at JSV + ship finished product) ──────────
            if prod_sell <= 0:
                import_cost = None
            else:
                prod_jita_split = (prod_jbv + prod_sell) / 2.0 if prod_jbv > 0 else prod_sell
                ship_per_unit   = prod_vol * ship_rate
                collat_per_unit = prod_jita_split * collat_pct
                import_cost     = prod_sell + ship_per_unit + collat_per_unit

            # ── React cost ───────────────────────────────────────────────
            # Buy inputs at JSV (or JBV), ship inputs to Tatara, pay job cost
            input_mat_cost  = 0.0   # ISK for all material inputs (per run)
            input_ship_cost = 0.0   # shipping + collateral for inputs (per run)
            input_eiv       = 0.0   # estimated item value for job cost calc
            input_names     = []
            missing_price   = False

            for tid, base_qty in f['inputs']:
                adj_qty = math.ceil(base_qty * me_factor)
                jbv, jsl = prices.get(tid, (0.0, 0.0))
                in_price = jsl if use_jsv else jbv
                if in_price <= 0:
                    missing_price = True
                    break
                jita_split = (jbv + jsl) / 2.0 if (jbv > 0 and jsl > 0) else (jbv or jsl)
                vol = type_info.get(tid, {}).get('vol', 0.0)

                input_mat_cost  += in_price * adj_qty
                input_ship_cost += (vol * adj_qty * ship_rate +
                                    jita_split * adj_qty * collat_pct)
                input_eiv       += in_price * adj_qty
                input_names.append(type_info.get(tid, {}).get('name', str(tid)))

            # Fuel blocks (ME applies but typically stays the same: ceil(5×0.99)=5)
            fuel_cost = 0.0
            if f['fuel'] and not missing_price:
                ftid, fqty = f['fuel']
                adj_fqty  = math.ceil(fqty * me_factor)
                fjbv, fjsl = prices.get(ftid, (0.0, 0.0))
                fuel_price = fjsl if use_jsv else fjbv
                fjita_split = (fjbv + fjsl) / 2.0 if (fjbv > 0 and fjsl > 0) else (fjbv or fjsl)
                fuel_vol   = type_info.get(ftid, {}).get('vol', 0.0)
                fuel_cost  = fuel_price * adj_fqty
                fuel_ship  = (fuel_vol * adj_fqty * ship_rate +
                              fjita_split * adj_fqty * collat_pct)
                input_eiv += fuel_price * adj_fqty
                input_ship_cost += fuel_ship

            if missing_price or input_mat_cost <= 0:
                react_cost = None
            else:
                job_cost   = input_eiv * sci * (1.0 + scc) * (1.0 + tax)
                total_run  = input_mat_cost + fuel_cost + input_ship_cost + job_cost
                react_cost = total_run / out_qty

            # ── Margins ───────────────────────────────────────────────────
            if your_sell and your_sell > 0:
                react_margin  = (your_sell - react_cost)  / your_sell * 100.0 if react_cost  else None
                import_margin = (your_sell - import_cost) / your_sell * 100.0 if import_cost else None
            else:
                react_margin  = None
                import_margin = None

            margin_adv = (react_margin - import_margin) \
                if (react_margin is not None and import_margin is not None) else None

            self._reaction_rows.append({
                'prod_id':      prod_id,
                'name':         f['name'],
                'tier':         f['tier'],
                'jita_sell':    prod_sell,
                'react_cost':   react_cost,
                'react_margin': react_margin,
                'inputs':       ', '.join(input_names),
            })

        self._rxn_populate_trees()

    def _rxn_populate_trees(self):
        """Sort rows and populate both Processed and Advanced treeviews."""
        if not self._reaction_rows:
            return

        srt = self._rxn_sort_var.get()
        sort_key_map = {
            'Item':           ('name',         False),
            'React Margin %': ('react_margin', True),
        }
        sk, rev = sort_key_map.get(srt, ('react_margin', True))

        def sorted_rows(tier):
            rows = [r for r in self._reaction_rows if r['tier'] == tier]
            return sorted(rows,
                          key=lambda r: (r[sk] is None,
                                         -(r[sk] or 0) if rev else (r[sk] or '')))

        def populate(tree, tier):
            tree.delete(*tree.get_children())
            for idx, r in enumerate(sorted_rows(tier)):
                rm = r['react_margin']
                if rm is None:
                    color_tag = 'marginal'
                elif rm >= 5.0:
                    color_tag = 'win'
                elif rm > 0.0:
                    color_tag = 'marginal'
                else:
                    color_tag = 'loss'
                jsv = r['jita_sell']
                alt = 'row_a' if idx % 2 == 0 else 'row_b'
                tree.insert('', 'end', tags=(color_tag, alt), values=(
                    r['name'],
                    f'{jsv:,.2f}' if jsv else '\u2014',
                    f'{rm:+.1f}%'  if rm  is not None else '\u2014',
                    r['inputs'],
                ))

        populate(self._rxn_proc_tree, 'Processed')
        populate(self._rxn_adv_tree,  'Advanced')

    def _rxn_sort_col(self, col):
        """Map treeview column click to sort dropdown."""
        col_sort_map = {
            'item':         'Item',
            'react_margin': 'React Margin %',
        }
        if col in col_sort_map:
            self._rxn_sort_var.set(col_sort_map[col])

    def _make_collapsible_section(self, parent, title, fg_color, expanded=True):
        """Create a collapsible section header + content frame. Returns content frame."""
        section = ttk.Frame(parent, style='Card.TFrame')
        section.pack(fill='x', padx=12, pady=(0, 2))

        content = ttk.Frame(section, style='Card.TFrame')

        def toggle(btn=None, c=content, state={'open': expanded}):
            if state['open']:
                c.pack_forget()
                state['open'] = False
                hdr_btn.configure(text=f'\u25b6  {title}')
            else:
                c.pack(fill='x', pady=(0, 4))
                state['open'] = True
                hdr_btn.configure(text=f'\u25bc  {title}')

        arrow = '\u25bc' if expanded else '\u25b6'
        hdr_btn = tk.Button(section, text=f'{arrow}  {title}',
                            background='#0a2030', foreground=fg_color,
                            activebackground='#0d2535', activeforeground=fg_color,
                            font=('Segoe UI', 9, 'bold'), relief='flat',
                            cursor='hand2', anchor='w', command=toggle)
        hdr_btn.pack(fill='x', pady=(2, 0))

        if expanded:
            content.pack(fill='x', pady=(0, 4))

        return content

    def _build_mineral_price_section(self, parent, expanded=True):
        """Collapsible: Standard Minerals (8 inputs)."""
        content = self._make_collapsible_section(
            parent, 'Standard Minerals', '#00d9ff', expanded)
        inner = ttk.Frame(content, style='Card.TFrame')
        inner.pack(padx=16, pady=(4, 6))
        lbl_cfg = dict(background='#0a2030', foreground='#00d9ff', font=('Segoe UI', 9))
        for col, (tid, name, default) in enumerate(self._ORE_MINERALS):
            key = f'ore_pct_{tid}'
            var = tk.StringVar(value=self._get_config(key, default))
            var.trace_add('write', lambda *_, k=key, v=var: self._set_config(k, v.get()))
            self.ore_product_pct[tid] = var
            lbl_text = name if tid != 11399 else f'{name} (Mercoxit)'
            tk.Label(inner, text=lbl_text, **lbl_cfg).grid(
                     row=0, column=col, padx=6, sticky='s')
            ttk.Entry(inner, textvariable=var, width=7).grid(row=1, column=col, padx=6)

    def _build_ice_product_price_section(self, parent, expanded=True):
        """Collapsible: Ice Products (7 inputs)."""
        content = self._make_collapsible_section(
            parent, 'Ice Products', '#aaddff', expanded)
        inner = ttk.Frame(content, style='Card.TFrame')
        inner.pack(padx=16, pady=(4, 6))
        lbl_cfg = dict(background='#0a2030', foreground='#aaddff', font=('Segoe UI', 9))
        for col, (tid, name, default) in enumerate(self._ORE_ICE_PRODUCTS):
            key = f'ore_pct_{tid}'
            var = tk.StringVar(value=self._get_config(key, default))
            var.trace_add('write', lambda *_, k=key, v=var: self._set_config(k, v.get()))
            self.ore_product_pct[tid] = var
            tk.Label(inner, text=name, **lbl_cfg).grid(row=0, column=col, padx=6, sticky='s')
            ttk.Entry(inner, textvariable=var, width=7).grid(row=1, column=col, padx=6)

    def _build_moon_material_price_section(self, parent, expanded=False):
        """Collapsible: Moon Materials (20 inputs, R4-R64 tiers)."""
        content = self._make_collapsible_section(
            parent, 'Moon Materials', '#cc88ff', expanded)
        inner = ttk.Frame(content, style='Card.TFrame')
        inner.pack(padx=16, pady=(4, 6))

        tier_colors = {'R4': '#888888', 'R8': '#00ff88', 'R16': '#44aaff',
                       'R32': '#cc88ff', 'R64': '#ffcc44'}
        tier_labels = {'R4': 'R4 \u2014 Ubiquitous', 'R8': 'R8 \u2014 Common',
                       'R16': 'R16 \u2014 Uncommon', 'R32': 'R32 \u2014 Rare',
                       'R64': 'R64 \u2014 Exceptional'}

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
                grid_row += 1

    def _set_ore_type_filter(self, val):
        """Switch the ore type filter and refresh the active view."""
        self._ore_type_filter_val = val
        labels = {'all': 'All', 'standard': 'Standard Ores', 'ice': 'Ice', 'moon': 'Moon Ores'}
        self._ore_type_lbl.configure(text=f'Showing: {labels.get(val, val)}')
        self._filter_active_ore_view()

    def _set_ore_comp_filter(self, val):
        """Switch compressed/uncompressed/both filter and refresh the ore view."""
        self._ore_comp_filter.set(val)
        labels = {'compressed': 'Compressed only', 'uncompressed': 'Uncompressed only', 'both': 'Both forms'}
        self._ore_comp_lbl.configure(text=labels[val])
        self._filter_active_ore_view()

    def _run_ore_fetch(self, category='all'):
        """Run fetch_ore_prices.py for the given category in a background thread."""
        import threading
        label_map = {'all': 'All', 'standard': 'Standard', 'ice': 'Ice', 'moon': 'Moon'}
        for cat, btn in self._ore_fetch_btns.items():
            btn.configure(state='disabled')
        self.ore_price_age_lbl.configure(
            text=f'Fetching {label_map[category]} prices from Jita 4-4...',
            foreground='#ffcc44')
        self.root.update()

        python_exe = r'C:\Users\lsant\AppData\Local\Python\pythoncore-3.14-64\python.exe'
        fetch_script = os.path.join(PROJECT_DIR, 'scripts', 'fetch_ore_prices.py')

        fetch_error = [None]

        def _worker():
            try:
                import subprocess
                result = subprocess.run([python_exe, fetch_script, category],
                                        cwd=PROJECT_DIR,
                                        capture_output=True, timeout=300, text=True)
                if result.returncode != 0:
                    fetch_error[0] = (result.stderr or result.stdout or 'unknown error').strip()[-200:]
            except Exception as e:
                fetch_error[0] = str(e)
            self.root.after(0, _done)

        def _done():
            for btn in self._ore_fetch_btns.values():
                btn.configure(state='normal')
            if fetch_error[0]:
                self.ore_price_age_lbl.configure(
                    text=f'\u26a0 Fetch failed: {fetch_error[0]}', foreground='#ff4444')
            else:
                self.load_ore_import_data()

        threading.Thread(target=_worker, daemon=True).start()

    def load_ore_import_data(self):
        """Query DB, calculate ore import margins, and populate the treeview."""
        try:
            buy_pct    = float(self.ore_buy_pct_var.get()) / 100.0
            broker_pct = float(self.ore_broker_var.get()) / 100.0
            ship_rate  = float(self.ore_ship_var.get())
            collat_pct = float(self.ore_collat_var.get()) / 100.0
            refine_eff = float(self.ore_refine_var.get()) / 100.0
            dev_days   = int(float(self.ore_dev_days_var.get() or '7'))
        except ValueError:
            messagebox.showerror("Invalid Input", "All parameters must be numeric.")
            return

        buy_basis = self.ore_buy_var.get()
        # Broker only applies when placing buy orders (JBV)
        effective_broker = broker_pct if 'JBV' in buy_basis else 0.0

        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Collect all type IDs we need prices for
        _std_raw = [1230,17470,17471,46689, 1228,17463,17464,46687, 1224,17459,17460,46686,
                    18,17455,17456,46685, 1227,17867,17868,46684, 20,17452,17453,46683,
                    21,17440,17441,46680, 1231,17444,17445,46681, 1226,17448,17449,46682,
                    1229,17865,17866,46679, 1232,17436,17437,46675, 1225,17432,17433,46677,
                    19,17466,17467,46688, 1223,17428,17429,46676, 22,17425,17426,46678,
                    11396,17869,17870]
        _std_comp = [62516,62517,62518,62519, 62520,62521,62522,62523,
                     62524,62525,62526,62527, 62528,62529,62530,62531,
                     62532,62533,62534,62535, 62536,62537,62538,62539,
                     62540,62541,62542,62543, 62544,62545,62546,62547,
                     62548,62549,62550,62551, 62552,62553,62554,62555,
                     62556,62557,62558,62559, 62560,62561,62562,62563,
                     62564,62565,62566,62567, 62568,62569,62570,62571,
                     62572,62573,62574,62575, 62586,62587,62588]
        _ice_raw  = [16262,16263,16264,16265,16266,16267,16268,16269,17975,17976,17977,17978]
        _ice_comp = [28433,28443,28434,28436,28435,28437,28438,28442,28439,28440,28444,28441]
        _moon_raw = [45490,45491,45492,45493, 46280,46282,46284,46286, 46281,46283,46285,46287,
                     45494,45495,45496,45497, 46288,46290,46292,46294, 46289,46291,46293,46295,
                     45498,45499,45500,45501, 46296,46298,46300,46302, 46297,46299,46301,46303,
                     45502,45503,45504,45506, 46304,46306,46308,46310, 46305,46307,46309,46311,
                     45510,45511,45512,45513, 46312,46314,46316,46318, 46313,46315,46317,46319]
        _moon_comp = [62454,62457,62455,62458,62461,62464, 62456,62459,62466,62467,62460,62463,
                      62474,62471,62468,62477, 62475,62472,62469,62478, 62476,62473,62470,62479,
                      62480,62483,62486,62489, 62481,62484,62487,62490, 62482,62485,62488,62491,
                      62492,62501,62498,62495, 62493,62502,62499,62496, 62494,62503,62500,62497,
                      62504,62510,62507,62513, 62505,62511,62508,62514, 62506,62512,62509,62515]
        _anomaly_raw  = [81900,81901,81902,81903, 82016,82017,82018,82019,
                         82205,82206,82207,82208, 82163,82164,82165,82166,
                         81975,81976,81977,81978]
        _anomaly_comp = [82300,82301,82302,82303, 82304,82305,82306,82307,
                         82308,82309,82310,82311, 82312,82313,82314,82315,
                         82316,82317,82318,82319]
        _a0rare_raw   = [74521,74522,74523,74524, 74525,74526,74527,74528,
                         74529,74530,74531,74532, 74533,74534,74535,74536]
        _a0rare_comp  = [75275,75276,75277,75278, 75279,75280,75281,75282,
                         75283,75284,75285,75286, 75287,75288,75289,75290]

        compressed_set = set(_std_comp + _ice_comp + _moon_comp +
                              _anomaly_comp + _a0rare_comp)
        all_ore_ids = (_std_raw + _std_comp + _ice_raw + _ice_comp +
                       _moon_raw + _moon_comp + _anomaly_raw + _anomaly_comp +
                       _a0rare_raw + _a0rare_comp)
        all_product_ids = [t for t in self.ore_product_pct]

        all_ids = list(set(all_ore_ids + all_product_ids))
        placeholders = ','.join('?' * len(all_ids))

        # Latest price per type_id
        cursor.execute(f"""
            SELECT type_id, best_buy, best_sell
            FROM market_price_snapshots mps
            WHERE type_id IN ({placeholders})
              AND timestamp = (
                  SELECT MAX(timestamp) FROM market_price_snapshots
                  WHERE type_id = mps.type_id
              )
        """, all_ids)
        prices = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

        # Latest overall snapshot timestamp
        cursor.execute("SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id IN (%s)" % placeholders, all_ids)
        snap_ts = cursor.fetchone()[0]

        # N-day average for ore AND product type_ids (minerals, ice products, moon mats)
        # Used to compute avg refine value per unit for dev % calculation
        cursor.execute(f"""
            SELECT type_id, AVG(best_buy)
            FROM market_price_snapshots
            WHERE type_id IN ({placeholders})
              AND best_buy IS NOT NULL
              AND timestamp >= datetime('now', '-{dev_days} days')
            GROUP BY type_id
        """, all_ids)
        avg_prices = {r[0]: r[1] for r in cursor.fetchall()}

        # 7-day price range (high/low) for volatility column — same basis as avg
        if 'JSV' in buy_basis:
            rng_col    = 'best_sell'
            rng_filter = 'AND best_sell IS NOT NULL'
        elif 'Split' in buy_basis:
            rng_col    = '(best_buy + best_sell) / 2.0'
            rng_filter = 'AND best_buy IS NOT NULL AND best_sell IS NOT NULL'
        else:
            rng_col    = 'best_buy'
            rng_filter = 'AND best_buy IS NOT NULL'
        cursor.execute(f"""
            SELECT type_id, MIN({rng_col}), MAX({rng_col})
            FROM market_price_snapshots
            WHERE type_id IN ({ore_ph})
              {rng_filter}
              AND timestamp >= datetime('now', '-{dev_days} days')
            GROUP BY type_id
        """, all_ore_ids)
        price_ranges = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

        # Volume + portion size for all ore type IDs
        cursor.execute(f"SELECT type_id, type_name, volume, portion_size FROM inv_types WHERE type_id IN ({ore_ph})",
                       all_ore_ids)
        ore_meta = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

        # Refining yields from type_materials
        import json as _json
        cursor.execute(f"SELECT type_id, materials_json FROM type_materials WHERE type_id IN ({ore_ph})",
                       all_ore_ids)
        yields = {r[0]: _json.loads(r[1]) for r in cursor.fetchall()}

        conn.close()

        # Update price age label
        if snap_ts:
            self.ore_price_age_lbl.configure(
                text=f'Price data: {snap_ts[:19].replace("T", " ")} UTC',
                foreground='#00ff88')
        else:
            self.ore_price_age_lbl.configure(
                text='\u26a0 No price data \u2014 click Fetch first',
                foreground='#ffaa44')

        # Ore category classification
        ice_ids  = set(_ice_raw  + _ice_comp)
        moon_ids = set(_moon_raw + _moon_comp)
        # everything else (std, anomaly, A0 rare) is 'standard'

        def _ore_buy_price(type_id):
            bb, bs = prices.get(type_id, (None, None))
            if bb is None and bs is None:
                return None
            if 'JBV' in buy_basis:
                return bb
            return bs  # JSV

        self._ore_all_rows = []

        for type_id in all_ore_ids:
            if type_id not in ore_meta:
                continue
            name, volume, portion = ore_meta[type_id]
            ore_yields = yields.get(type_id, [])
            if not ore_yields:
                continue

            raw_price = _ore_buy_price(type_id)
            if raw_price is None or raw_price <= 0:
                continue

            # Per-batch costs
            ore_cost   = raw_price * buy_pct * portion
            broker     = ore_cost * effective_broker
            ship_cost  = volume * portion * ship_rate
            collat     = ore_cost * collat_pct
            total_cost = ore_cost + broker + ship_cost + collat

            # Per-batch product value
            prod_value = 0.0
            raw_value  = 0.0   # unweighted by sell% — used for cost allocation in product view
            for mat in ore_yields:
                mat_id = mat['materialTypeID']
                qty    = mat['quantity']
                if mat_id not in self.ore_product_pct:
                    continue
                try:
                    pct = float(self.ore_product_pct[mat_id].get()) / 100.0
                except ValueError:
                    pct = 1.0
                mat_bb = prices.get(mat_id, (None, None))[0]  # JBV for sell side
                if mat_bb and mat_bb > 0:
                    raw_value  += qty * refine_eff * mat_bb
                    prod_value += qty * refine_eff * mat_bb * pct

            if prod_value <= 0:
                continue

            profit  = prod_value - total_cost
            margin  = (profit / total_cost * 100) if total_cost > 0 else 0

            avg_bb = avg_prices.get(type_id)   # N-day avg ore price (used for sug_bid/volatility)

            # ── Buy order analysis metrics ────────────────────────────────
            try:
                target_margin_rate = float(self.ore_target_margin_var.get()) / 100.0
            except (ValueError, AttributeError):
                target_margin_rate = 0.05

            value_pu = prod_value / portion          # refine value per unit

            # Deviation vs N-day average — compare current refine value to avg refine value
            # (matches Import Analysis tool: use avg mineral prices to recompute avg refine value)
            _avg_rv = 0.0
            _all_mats_avg = bool(ore_yields)
            for _mat in ore_yields:
                _mid = _mat['materialTypeID']
                _qty = _mat['quantity']
                if _mid not in self.ore_product_pct:
                    continue
                try:    _mpct = float(self.ore_product_pct[_mid].get()) / 100.0
                except: _mpct = 1.0
                _avg_mat = avg_prices.get(_mid)
                if not _avg_mat:
                    _all_mats_avg = False
                    break
                _avg_rv += _qty * refine_eff * _avg_mat * _mpct
            _avg_refine_pu = (_avg_rv / portion) if (_all_mats_avg and _avg_rv > 0) else None
            dev_pct = ((value_pu - _avg_refine_pu) / _avg_refine_pu * 100) if _avg_refine_pu else None
            ship_pu  = volume * ship_rate            # fixed shipping per unit (doesn't scale with price)

            # max_bid: max ISK/unit to place on buy order to hit target_margin
            #   value_pu = (bid * (1+broker+collat) + ship_pu) * (1+target_margin)
            #   where bid = price_ref * buy_pct  =>  price_ref = bid / buy_pct
            #   => bid = (value_pu/(1+target_margin) - ship_pu) / (1+broker+collat)
            cost_factor = 1.0 + effective_broker + collat_pct
            if cost_factor > 0:
                _mb_isk = (value_pu / (1.0 + target_margin_rate) - ship_pu) / cost_factor
                max_bid = round(_mb_isk, 2) if _mb_isk > 0 else None
                # reference Jita price threshold (for OVER check and bid_room)
                max_bid_ref = round(_mb_isk / buy_pct, 2) if (buy_pct > 0 and _mb_isk > 0) else None
            else:
                max_bid     = None
                max_bid_ref = None

            # sug_bid: conservative entry ISK — stay at or slightly below N-day avg bid, capped at max_bid
            if max_bid is not None and avg_bb is not None and avg_bb > 0:
                sug_bid = round(min(max_bid, avg_bb * buy_pct * 0.99), 2)
            elif max_bid is not None:
                sug_bid = max_bid
            else:
                sug_bid = None

            # bid_room: how far max_bid_ref is above current Jita price (positive = room to bid more)
            if max_bid_ref is not None and raw_price > 0:
                bid_room = round((max_bid_ref - raw_price) / raw_price * 100, 2)
            else:
                bid_room = None

            # volatility: 7-day price swing as % of N-day avg
            rng = price_ranges.get(type_id)
            if rng and rng[0] is not None and rng[1] is not None and avg_bb and avg_bb > 0:
                volatility = round((rng[1] - rng[0]) / avg_bb * 100, 2)
            else:
                volatility = None

            if type_id in ice_ids:
                ore_cat = 'ice'
            elif type_id in moon_ids:
                ore_cat = 'moon'
            else:
                ore_cat = 'standard'  # std, anomaly, and A0 rare all under standard
            is_compressed = type_id in compressed_set

            self._ore_all_rows.append({
                'type_id':    type_id,
                'name':       name,
                'jita_buy':   raw_price,                              # already per-unit
                'logistics':  (ship_cost + collat + broker) / portion, # per-unit, includes broker
                'landed':     total_cost / portion,                    # per-unit
                'value':      prod_value / portion,                    # per-unit
                'raw_value':  raw_value / portion,                     # per-unit (ratio preserved)
                'ore_yields': ore_yields,
                'profit':     profit / portion,                        # per-unit
                'margin':     margin,                                   # % unchanged
                'dev':        dev_pct,                                  # % unchanged
                'ore_cat':    ore_cat,
                'compressed': is_compressed,
                # Buy order analysis
                'max_bid':     max_bid,      # actual max ISK/unit to bid
                'max_bid_ref': max_bid_ref,  # Jita price threshold (for OVER check)
                'sug_bid':     sug_bid,
                'bid_room':    bid_room,
                'volatility':  volatility,
            })

        self._ore_prices_snap = prices
        self._ore_refine_eff  = refine_eff
        self._filter_active_ore_view()

    def _filter_active_ore_view(self):
        """Route to the correct filter function based on current view."""
        if getattr(self, '_ore_view', 'ore') == 'product':
            self._compute_product_rows()   # recompute best sources with current comp filter
            self._filter_product_tree()
        else:
            self._filter_ore_tree()

    def _update_ore_jbv_columns(self):
        """Show/hide JBV-only columns and sort options based on selected buy basis."""
        is_jbv = 'JBV' in self.ore_buy_var.get()
        all_cols  = ('name', 'jita_buy', 'logistics', 'landed', 'value', 'profit', 'margin', 'dev',
                     'max_bid', 'sug_bid', 'bid_room', 'volatility')
        base_cols = ('name', 'jita_buy', 'logistics', 'landed', 'value', 'profit', 'margin', 'dev')
        self.ore_tree['displaycolumns'] = all_cols if is_jbv else base_cols

        all_sort  = ['Margin %', 'Profit/Unit', 'Landed/Unit', 'Value/Unit', 'Deviation %',
                     'Max Bid', 'Sug Bid', 'Bid Headroom', 'Volatility %']
        base_sort = ['Margin %', 'Profit/Unit', 'Landed/Unit', 'Value/Unit', 'Deviation %']
        self.ore_sort_cb['values'] = all_sort if is_jbv else base_sort
        if not is_jbv and self.ore_sort_display_var.get() in ('Max Bid', 'Sug Bid', 'Bid Headroom', 'Volatility %'):
            self.ore_sort_display_var.set('Margin %')

    def _filter_ore_tree(self):
        """Apply search/show/sort/type filters and repopulate the treeview."""
        search   = self.ore_search_var.get().lower()
        show     = self.ore_show_var.get()
        sort_map = {'Margin %': 'margin', 'Profit/Unit': 'profit',
                    'Landed/Unit': 'landed', 'Value/Unit': 'value', 'Deviation %': 'dev',
                    'Max Bid': 'max_bid', 'Sug Bid': 'sug_bid',
                    'Bid Headroom': 'bid_room', 'Volatility %': 'volatility'}
        sort_key = sort_map.get(self.ore_sort_display_var.get(), 'margin')
        type_filter = self._ore_type_filter_val

        rows = self._ore_all_rows
        if type_filter != 'all':
            rows = [r for r in rows if r['ore_cat'] == type_filter]
        comp_filter = self._ore_comp_filter.get()
        if comp_filter == 'compressed':
            rows = [r for r in rows if r['compressed']]
        elif comp_filter == 'uncompressed':
            rows = [r for r in rows if not r['compressed']]
        if search:
            rows = [r for r in rows if search in r['name'].lower()]
        if show == 'Profitable':
            rows = [r for r in rows if r['profit'] > 0]
        elif show == 'Loss Only':
            rows = [r for r in rows if r['profit'] <= 0]

        rows = sorted(rows, key=lambda r: (r[sort_key] is None, r[sort_key] or 0.0), reverse=True)

        self.ore_tree.delete(*self.ore_tree.get_children())

        def fmt_isk(v):
            if v is None:
                return '—'
            return f'{v:,.2f}'

        profitable = sum(1 for r in rows if r['profit'] > 0)
        best_r  = max(rows, key=lambda r: r['margin'],  default=None)
        best_i  = max(rows, key=lambda r: r['profit'],  default=None)
        worst_r = min(rows, key=lambda r: r['margin'],  default=None)

        self._ore_summary_labels['total'].configure(text=str(len(rows)))
        self._ore_summary_labels['profitable'].configure(
            text=f'{profitable}  ({profitable/len(rows)*100:.0f}%)' if rows else '—')
        self._ore_summary_labels['best'].configure(
            text=f'+{best_r["margin"]:.1f}%  {best_r["name"]}' if best_r else '—',
            foreground='#00ff88' if best_r and best_r['margin'] > 0 else '#ff4444')
        self._ore_summary_labels['best_isk'].configure(
            text=f'+{fmt_isk(best_i["profit"])} ISK  {best_i["name"]}' if best_i else '—')
        self._ore_summary_labels['worst'].configure(
            text=f'{worst_r["margin"]:.1f}%  {worst_r["name"]}' if worst_r else '—',
            foreground='#ff4444' if worst_r and worst_r['margin'] < 0 else '#00ff88')

        # Insert rows with group headers when not searching/filtering
        show_groups = not search and type_filter in ('all', 'standard', 'ice', 'moon')
        current_cat = None
        row_idx = 0

        for r in rows:
            cat = r['ore_cat']
            if show_groups and cat != current_cat:
                current_cat = cat
                cat_label = {'standard': '── Standard Ores ──',
                             'ice':      '── Ice ──',
                             'moon':     '── Moon Ores ──'}.get(cat, cat)
                self.ore_tree.insert('', 'end',
                    values=(cat_label, '', '', '', '', '', '', '', '', '', '', ''),
                    tags=('group_hdr',))

            m = r['margin']
            if m >= 5:
                tag = 'profitable'
            elif m >= 0:
                tag = 'marginal'
            else:
                tag = 'loss'

            alt = 'row_a' if row_idx % 2 == 0 else 'row_b'

            dev = r.get('dev')
            if dev is not None:
                dev_str = f"{dev:+.1f}%"
                dev_tag = 'dev_high' if dev > 5 else ('dev_low' if dev < -5 else '')
            else:
                dev_str = '—'
                dev_tag = ''

            # Buy order column formatting
            max_bid    = r.get('max_bid')
            sug_bid    = r.get('sug_bid')
            bid_room   = r.get('bid_room')
            volatility = r.get('volatility')

            max_bid_str  = f"{max_bid:,.2f}"    if max_bid    is not None else '—'
            sug_bid_str  = f"{sug_bid:,.2f}"    if sug_bid    is not None else '—'
            bid_room_str = f"{bid_room:+.1f}%"  if bid_room   is not None else '—'
            volat_str    = f"{volatility:.1f}%" if volatility is not None else '—'

            # Flag if current Jita price is above the max_bid_ref threshold (can't hit target margin)
            max_bid_ref = r.get('max_bid_ref')
            if max_bid is not None and max_bid_ref is not None and r['jita_buy'] > max_bid_ref:
                max_bid_str = f'OVER ({max_bid:,.2f})'

            tags = tuple(t for t in (tag, alt, dev_tag) if t)
            self.ore_tree.insert('', 'end', tags=tags, values=(
                r['name'],
                f"{r['jita_buy']:,.2f}",
                f"{r['logistics']:,.2f}",
                f"{r['landed']:,.2f}",
                f"{r['value']:,.2f}",
                f"{r['profit']:+,.2f}",
                f"{r['margin']:+.1f}%",
                dev_str,
                max_bid_str,
                sug_bid_str,
                bid_room_str,
                volat_str,
            ))
            row_idx += 1

    def _sort_ore_tree(self, col):
        sort_map = {'margin': 'Margin %', 'profit': 'Profit/Unit', 'landed': 'Landed/Unit',
                    'value': 'Value/Unit', 'dev': 'Deviation %',
                    'max_bid': 'Max Bid', 'sug_bid': 'Sug Bid',
                    'bid_room': 'Bid Headroom', 'volatility': 'Volatility %'}
        if col in sort_map:
            self.ore_sort_display_var.set(sort_map[col])
        self._filter_ore_tree()

    def _set_ore_view(self, view):
        """Switch between By Ore and By Product views."""
        self._ore_view = view
        if view == 'product':
            self.ore_tree_frame.pack_forget()
            self.product_tree_frame.pack(fill='both', expand=True)
            if self._ore_all_rows:
                self._compute_product_rows()
            self._filter_product_tree()
        else:
            self.product_tree_frame.pack_forget()
            self.ore_tree_frame.pack(fill='both', expand=True)
            self._filter_ore_tree()

    def _compute_product_rows(self):
        """Build per-product cost/margin rows from current ore row data."""
        prices     = self._ore_prices_snap
        refine_eff = self._ore_refine_eff

        # Build product metadata lookup: type_id -> (display_name, category, tier)
        product_meta = {}
        for tid, name, _ in self._ORE_MINERALS:
            product_meta[tid] = (name, 'Mineral', None)
        for tid, name, _ in self._ORE_ICE_PRODUCTS:
            product_meta[tid] = (name, 'Ice Product', None)
        for tid, name, _, tier in self._ORE_MOON_MATERIALS:
            product_meta[tid] = (name, f'Moon Mat ({tier})', tier)

        # For each product, find the ore that yields it at the lowest cost per unit.
        # Value-weighted allocation: cost_per_unit = landed × jbv_P / raw_total
        # (The qty terms cancel in the value-weighted formula.)
        best = {}  # type_id -> {cost_unit, source_name}

        # Apply comp filter and ore type filter to source rows
        comp_filter = getattr(self, '_ore_comp_filter', None)
        comp_val    = comp_filter.get() if comp_filter else 'both'
        type_val    = getattr(self, '_ore_type_filter_val', 'all')

        def _source_passes(row):
            if comp_val == 'compressed'   and not row.get('compressed'):
                return False
            if comp_val == 'uncompressed' and     row.get('compressed'):
                return False
            cat = row.get('ore_cat', 'standard')
            if type_val == 'standard' and cat != 'standard':
                return False
            if type_val == 'ice'      and cat != 'ice':
                return False
            if type_val == 'moon'     and cat != 'moon':
                return False
            return True

        for ore_row in (r for r in self._ore_all_rows if _source_passes(r)):
            landed    = ore_row['landed']
            raw_value = ore_row.get('raw_value', 0)
            if raw_value <= 0:
                continue
            for mat in ore_row.get('ore_yields', []):
                mat_id = mat['materialTypeID']
                if mat_id not in product_meta:
                    continue
                mat_bb = prices.get(mat_id, (None, None))[0]
                if not mat_bb or mat_bb <= 0:
                    continue
                cost_unit = landed * mat_bb / raw_value
                if mat_id not in best or cost_unit < best[mat_id]['cost_unit']:
                    best[mat_id] = {'cost_unit': cost_unit, 'source': ore_row['name']}

        self._product_all_rows = []
        for mat_id, b in best.items():
            name, category, tier = product_meta[mat_id]
            mat_bb = prices.get(mat_id, (None, None))[0]
            if not mat_bb or mat_bb <= 0:
                continue
            try:
                pct = float(self.ore_product_pct[mat_id].get()) / 100.0
            except (ValueError, KeyError):
                pct = 1.0

            sell_price  = mat_bb * pct
            cost_unit   = b['cost_unit']
            profit_unit = sell_price - cost_unit
            margin      = (profit_unit / cost_unit * 100) if cost_unit > 0 else 0

            prod_cat = 'mineral' if category == 'Mineral' else (
                       'ice'     if category == 'Ice Product' else 'moon')

            self._product_all_rows.append({
                'type_id':    mat_id,
                'product':    name,
                'category':   category,
                'tier':       tier,
                'source':     b['source'],
                'cost_unit':  cost_unit,
                'sell_price': sell_price,
                'jita_jbv':   mat_bb,
                'profit_unit': profit_unit,
                'margin':     margin,
                'prod_cat':   prod_cat,
            })

    def _filter_product_tree(self):
        """Filter/sort product rows and populate the product treeview."""
        if not self._product_all_rows:
            self.product_tree.delete(*self.product_tree.get_children())
            return

        search      = self.ore_search_var.get().lower()
        show        = self.ore_show_var.get()
        type_filter = self._ore_type_filter_val
        cat_map     = {'all': None, 'standard': 'mineral', 'ice': 'ice', 'moon': 'moon'}
        cat_filter  = cat_map.get(type_filter)

        rows = list(self._product_all_rows)
        if cat_filter:
            rows = [r for r in rows if r['prod_cat'] == cat_filter]
        if search:
            rows = [r for r in rows if search in r['product'].lower()
                                    or search in r['source'].lower()]
        if show == 'Profitable':
            rows = [r for r in rows if r['profit_unit'] > 0]
        elif show == 'Loss Only':
            rows = [r for r in rows if r['profit_unit'] <= 0]

        sort_key = self._product_sort_col
        sort_asc = self._product_sort_asc
        rows.sort(key=lambda r: r.get(sort_key) or 0, reverse=not sort_asc)

        # Update summary cards
        profitable = sum(1 for r in rows if r['profit_unit'] > 0)
        best_r  = max(rows, key=lambda r: r['margin'],      default=None)
        best_i  = max(rows, key=lambda r: r['profit_unit'], default=None)
        worst_r = min(rows, key=lambda r: r['margin'],      default=None)

        self._ore_summary_labels['total'].configure(text=str(len(rows)))
        self._ore_summary_labels['profitable'].configure(
            text=f'{profitable}  ({profitable/len(rows)*100:.0f}%)' if rows else '—')
        self._ore_summary_labels['best'].configure(
            text=f'+{best_r["margin"]:.1f}%  {best_r["product"]}' if best_r else '—',
            foreground='#00ff88' if best_r and best_r['margin'] > 0 else '#ff4444')
        self._ore_summary_labels['best_isk'].configure(
            text=f'+{best_i["profit_unit"]:,.2f} ISK  {best_i["product"]}' if best_i else '—')
        self._ore_summary_labels['worst'].configure(
            text=f'{worst_r["margin"]:.1f}%  {worst_r["product"]}' if worst_r else '—',
            foreground='#ff4444' if worst_r and worst_r['margin'] < 0 else '#00ff88')

        self.product_tree.delete(*self.product_tree.get_children())

        show_groups = not search and not cat_filter
        cat_order   = {'mineral': 0, 'ice': 1, 'moon': 2}
        if show_groups:
            rows.sort(key=lambda r: (
                cat_order.get(r['prod_cat'], 3),
                -(r.get(sort_key) or 0) if not sort_asc else (r.get(sort_key) or 0)
            ))

        current_cat = None
        row_idx     = 0
        for r in rows:
            cat = r['prod_cat']
            if show_groups and cat != current_cat:
                current_cat = cat
                label = {'mineral': '── Minerals ──',
                         'ice':     '── Ice Products ──',
                         'moon':    '── Moon Materials ──'}.get(cat, cat)
                self.product_tree.insert('', 'end',
                    values=(label, '', '', '', '', '', '', ''),
                    tags=('group_hdr',))

            m   = r['margin']
            tag = 'profitable' if m >= 5 else ('marginal' if m >= 0 else 'loss')
            bg  = ('row_ice' if cat == 'ice' else
                   'row_moon' if cat == 'moon' else
                   ('row_a' if row_idx % 2 == 0 else 'row_b'))

            tier_str     = f' ({r["tier"]})' if r.get('tier') else ''
            cat_display  = r['category'] + tier_str

            self.product_tree.insert('', 'end', tags=(tag, bg), values=(
                r['product'],
                cat_display,
                r['source'],
                f"{r['cost_unit']:,.2f}",
                f"{r['sell_price']:,.2f}",
                f"{r['jita_jbv']:,.2f}",
                f"{r['profit_unit']:+,.2f}",
                f"{r['margin']:+.1f}%",
            ))
            row_idx += 1

    def _sort_product_tree(self, col):
        """Toggle sort on a product tree column header click."""
        if self._product_sort_col == col:
            self._product_sort_asc = not self._product_sort_asc
        else:
            self._product_sort_col = col
            self._product_sort_asc = col in ('product', 'source', 'category')
        self._filter_product_tree()

    # ──────────────────────────────────────────────────────────────────────
    #  CONSIGNMENT TAB
    # ──────────────────────────────────────────────────────────────────────

    def _consign_init_db(self):
        """Create consignment tables if they don't exist, and migrate existing ones."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consignors (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT    NOT NULL,
                item_name      TEXT    NOT NULL,
                item_type_id   INTEGER,
                list_price     REAL,
                consignor_pct  REAL    NOT NULL,
                start_date     TEXT    NOT NULL,
                active         INTEGER DEFAULT 1,
                notes          TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consignment_sales (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                consignor_id       INTEGER NOT NULL REFERENCES consignors(id),
                sale_date          TEXT    NOT NULL,
                quantity           INTEGER NOT NULL,
                price_per_unit     REAL    NOT NULL,
                total_isk          REAL    NOT NULL,
                consignor_isk      REAL    NOT NULL,
                broker_isk         REAL    NOT NULL,
                paid               INTEGER DEFAULT 0,
                paid_date          TEXT,
                notes              TEXT,
                source_contract_id INTEGER,
                auto_logged        INTEGER DEFAULT 0
            )
        """)
        # Container → consignor assignment
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consignor_containers (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                consignor_id       INTEGER NOT NULL REFERENCES consignors(id),
                container_item_id  INTEGER NOT NULL UNIQUE,
                container_name     TEXT,
                notes              TEXT
            )
        """)
        # All known hangar containers discovered via ESI
        conn.execute("""
            CREATE TABLE IF NOT EXISTS known_containers (
                item_id    INTEGER PRIMARY KEY,
                name       TEXT,
                ignored    INTEGER NOT NULL DEFAULT 0,
                last_seen  TEXT
            )
        """)
        # Shared-slot sales pending manual attribution
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consignment_pending_sales (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id       INTEGER NOT NULL,
                type_id           INTEGER NOT NULL,
                item_name         TEXT,
                total_qty         INTEGER NOT NULL,
                total_isk         REAL    NOT NULL,
                sale_date         TEXT,
                created_at        TEXT    NOT NULL,
                notes             TEXT
            )
        """)
        # Per-container inventory history (parallel to lx_zoj_inventory)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lx_zoj_container_snapshot (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_timestamp TEXT   NOT NULL,
                container_item_id  INTEGER NOT NULL,
                type_id            INTEGER NOT NULL,
                type_name          TEXT    NOT NULL,
                quantity           INTEGER NOT NULL
            )
        """)
        # Safe migrations for existing installs
        for sql in [
            "ALTER TABLE consignors ADD COLUMN item_type_id   INTEGER",
            "ALTER TABLE consignors ADD COLUMN slot_type      TEXT    DEFAULT 'shared'",
            "ALTER TABLE consignors ADD COLUMN slot_priority  INTEGER DEFAULT 1",
            "ALTER TABLE consignors ADD COLUMN max_units      INTEGER",
            "ALTER TABLE consignors ADD COLUMN demand_tier    TEXT    DEFAULT 'medium'",
            "ALTER TABLE consignors ADD COLUMN current_qty    INTEGER DEFAULT 0",
            "ALTER TABLE consignment_sales ADD COLUMN source_contract_id INTEGER",
            "ALTER TABLE consignment_sales ADD COLUMN auto_logged INTEGER DEFAULT 0",
            "ALTER TABLE lx_zoj_inventory   ADD COLUMN container_item_id INTEGER",
            "ALTER TABLE consignors ADD COLUMN corp_donation_opted INTEGER DEFAULT 0",
            "ALTER TABLE consignors ADD COLUMN corp_donation_pct REAL DEFAULT 0",
            "ALTER TABLE consignment_sales ADD COLUMN corp_donation_isk REAL DEFAULT 0",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass  # Column already exists
        conn.commit()
        conn.close()

    def _build_consignment_tab(self):
        """Build the Consignment tracking tab."""
        self._consign_init_db()

        outer = tk.Frame(self.consign_frame, background='#0a1520')
        outer.pack(fill='both', expand=True, padx=15, pady=10)

        tk.Label(outer, text='Consignment Program', background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 8))

        # Paned layout — consignors top, sales log bottom
        pane = tk.PanedWindow(outer, orient='vertical', background='#1a3040',
                              sashrelief='flat', sashwidth=6, sashpad=2)
        pane.pack(fill='both', expand=True)

        # ── TOP: Consignors ───────────────────────────────────────────────
        top_card = ttk.Frame(pane, style='Card.TFrame')
        pane.add(top_card, minsize=160)

        top_inner = ttk.Frame(top_card, style='Card.TFrame')
        top_inner.pack(fill='both', expand=True, padx=10, pady=8)

        ctb = ttk.Frame(top_inner, style='Card.TFrame')
        ctb.pack(fill='x', pady=(0, 6))
        tk.Label(ctb, text='Consignors', background='#0a2030',
                 foreground='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 12))
        ttk.Button(ctb, text='+ Add Consignor',
                   command=self._consign_add_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(ctb, text='Edit',
                   command=self._consign_edit_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(ctb, text='Toggle Active',
                   command=self._consign_toggle_active).pack(side='left', padx=(0, 4))
        ttk.Button(ctb, text='Containers\u2026',
                   command=self._consign_open_containers_dialog).pack(side='left', padx=(12, 4))
        ttk.Button(ctb, text='Pending\u2026',
                   command=self._consign_open_pending_dialog).pack(side='left', padx=(0, 4))

        c_cols = ('slot_type', 'name', 'item', 'current_qty', 'max_units',
                  'list_price', 'demand', 'status', 'owed')
        self.consign_tree = ttk.Treeview(top_inner, columns=c_cols, show='headings',
                                         selectmode='browse', height=6)
        for cid, hd, w, a in [
            ('slot_type',  'Type',             90, 'c'),
            ('name',       'Consignor',        150, 'w'),
            ('item',       'Item',             180, 'w'),
            ('current_qty','In Slot',           75, 'e'),
            ('max_units',  'Max Units',         80, 'e'),
            ('list_price', 'Price/Unit',       120, 'e'),
            ('demand',     'Demand',            75, 'c'),
            ('status',     'Status',            75, 'c'),
            ('owed',       'ISK Owed',         130, 'e'),
        ]:
            self.consign_tree.heading(cid, text=hd)
            self.consign_tree.column(cid, width=w, minwidth=40, anchor=a)
        self.consign_tree.tag_configure('active',    foreground='#00ff88')
        self.consign_tree.tag_configure('inactive',  foreground='#888888')
        self.consign_tree.tag_configure('exclusive', foreground='#ffcc44')
        self.consign_tree.tag_configure('combined',  foreground='#00d9ff', font=('Segoe UI', 9, 'bold'))
        self.consign_tree.tag_configure('d_high',    foreground='#ff6666')
        self.consign_tree.tag_configure('d_medium',  foreground='#ffcc44')
        self.consign_tree.tag_configure('d_low',     foreground='#66d9ff')
        self.consign_tree.bind('<<TreeviewSelect>>', lambda _: self._consign_load_sales())

        c_vsb = ttk.Scrollbar(top_inner, orient='vertical', command=self.consign_tree.yview)
        self.consign_tree.configure(yscrollcommand=c_vsb.set)
        c_vsb.pack(side='right', fill='y')
        self.consign_tree.pack(fill='both', expand=True)

        # ── BOTTOM: Sales Log ─────────────────────────────────────────────
        bot_card = ttk.Frame(pane, style='Card.TFrame')
        pane.add(bot_card, minsize=200)

        bot_inner = ttk.Frame(bot_card, style='Card.TFrame')
        bot_inner.pack(fill='both', expand=True, padx=10, pady=8)

        stb = ttk.Frame(bot_inner, style='Card.TFrame')
        stb.pack(fill='x', pady=(0, 6))
        self._consign_log_title = tk.Label(stb, text='Sales Log', background='#0a2030',
                                           foreground='#66d9ff', font=('Segoe UI', 10, 'bold'))
        self._consign_log_title.pack(side='left', padx=(0, 12))
        ttk.Button(stb, text='Log Sale', style='Action.TButton',
                   command=self._consign_log_sale_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(stb, text='Mark Selected Paid',
                   command=self._consign_mark_paid).pack(side='left', padx=(0, 4))
        ttk.Button(stb, text='Delete Selected',
                   command=self._consign_delete_sales).pack(side='left', padx=(0, 4))
        ttk.Button(stb, text='\u21ba Sync Contracts',
                   command=self._consign_sync_contracts).pack(side='left', padx=(0, 8))
        self._consign_owed_lbl = tk.Label(stb, text='Owed: —', background='#0a2030',
                                          foreground='#ffcc44', font=('Segoe UI', 9, 'bold'))
        self._consign_owed_lbl.pack(side='left', padx=(0, 16))
        self._consign_paid_lbl = tk.Label(stb, text='Total Paid Out: —', background='#0a2030',
                                          foreground='#66d9ff', font=('Segoe UI', 9))
        self._consign_paid_lbl.pack(side='left', padx=(0, 16))
        self._consign_corp_lbl = tk.Label(stb, text='Corp Donation Owed: —', background='#0a2030',
                                          foreground='#ff9944', font=('Segoe UI', 9))
        self._consign_corp_lbl.pack(side='left')

        s_cols = ('date', 'qty', 'price_unit', 'total', 'their_isk', 'corp_don', 'my_isk', 'paid', 'notes')
        self.sales_tree = ttk.Treeview(bot_inner, columns=s_cols, show='headings',
                                        selectmode='extended', height=10)
        for cid, hd, w, a in [
            ('date',       'Sale Date',      110, 'c'),
            ('qty',        'Qty',             55, 'e'),
            ('price_unit', 'Price/Unit',     125, 'e'),
            ('total',      'Total ISK',      135, 'e'),
            ('their_isk',  'Their Share',    135, 'e'),
            ('corp_don',   'Corp Don.',      110, 'e'),
            ('my_isk',     'My Share',       120, 'e'),
            ('paid',       'Paid',            90, 'c'),
            ('notes',      'Notes',          220, 'w'),
        ]:
            self.sales_tree.heading(cid, text=hd)
            self.sales_tree.column(cid, width=w, minwidth=40, anchor=a)
        self.sales_tree.tag_configure('paid',   foreground='#00ff88')
        self.sales_tree.tag_configure('unpaid', foreground='#ffcc44')
        self.sales_tree.tag_configure('row_a',  background='#0a2030')
        self.sales_tree.tag_configure('row_b',  background='#0d2535')

        s_vsb = ttk.Scrollbar(bot_inner, orient='vertical',   command=self.sales_tree.yview)
        s_hsb = ttk.Scrollbar(bot_inner, orient='horizontal', command=self.sales_tree.xview)
        self.sales_tree.configure(yscrollcommand=s_vsb.set, xscrollcommand=s_hsb.set)
        s_vsb.pack(side='right',  fill='y')
        s_hsb.pack(side='bottom', fill='x')
        self.sales_tree.pack(fill='both', expand=True)

        self.container_tree = None  # created on demand in _consign_open_containers_dialog
        self.pending_tree   = None  # created on demand in _consign_open_pending_dialog

        self._consign_load_consignors()

    def _consign_load_consignors(self):
        """Load consignors into the treeview, with combined-stock rows for shared items."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT c.id, c.character_name, c.item_name, c.list_price,
                   c.consignor_pct, c.start_date, c.active,
                   COALESCE(SUM(CASE WHEN s.paid=0 THEN s.consignor_isk ELSE 0 END), 0),
                   c.slot_type, c.slot_priority, c.max_units, c.demand_tier,
                   COALESCE(c.current_qty, 0),
                   COALESCE(c.corp_donation_opted, 0), COALESCE(c.corp_donation_pct, 0)
            FROM consignors c
            LEFT JOIN consignment_sales s ON s.consignor_id = c.id
            GROUP BY c.id
            ORDER BY c.active DESC, c.item_name, c.slot_priority, c.character_name
        """).fetchall()
        conn.close()

        # Build a map of item_name -> list of shared+active rows to generate combined rows
        from collections import defaultdict
        shared_groups = defaultdict(list)
        for row in rows:
            cid, name, item, price, their_pct, start, active, owed, \
                slot_type, priority, max_units, demand, cur_qty, \
                don_opted, don_pct = row
            if (slot_type or 'shared') == 'shared' and active:
                shared_groups[item].append(row)

        _demand_label = {'high': '▲ High', 'medium': '◆ Med', 'low': '▼ Low'}
        _demand_tag   = {'high': 'd_high', 'medium': 'd_medium', 'low': 'd_low'}
        _slot_label   = {'exclusive': '★ Exclusive', 'shared': '◈ Shared'}

        sel = self.consign_tree.selection()
        self.consign_tree.delete(*self.consign_tree.get_children())

        # Track which shared items already have a combined row inserted
        combined_inserted = set()

        for row in rows:
            cid, name, item, price, their_pct, start, active, owed, \
                slot_type, priority, max_units, demand, cur_qty, \
                don_opted, don_pct = row
            slot_type  = slot_type  or 'shared'
            demand     = demand     or 'medium'
            my_pct     = round(100.0 - their_pct, 1)
            price_str  = f"{price:,.2f}" if price is not None else '—'
            owed_str   = f"{owed:,.2f}" if owed else '—'
            max_str    = f"{max_units:,}" if max_units else '—'
            cur_str    = f"{cur_qty:,}" if cur_qty else '—'
            d_label    = _demand_label.get(demand, demand)
            d_tag      = _demand_tag.get(demand, 'd_medium')
            type_label = _slot_label.get(slot_type, slot_type)
            donate_str = f"{don_pct:.1f}%" if don_opted else '—'

            # Insert combined-stock summary row for shared items with 2+ active suppliers
            if slot_type == 'shared' and item not in combined_inserted:
                group = shared_groups.get(item, [])
                if len(group) >= 2:
                    combined_qty   = sum(r[12] for r in group)
                    combined_owed  = sum(r[7]  for r in group)
                    combined_inserted.add(item)
                    self.consign_tree.insert('', 'end',
                        iid=f'combined_{item}', tags=('combined',), values=(
                        '◈ Shared',
                        f'({len(group)} suppliers)',
                        item,
                        f"{combined_qty:,}" if combined_qty else '—',
                        '—', price_str, d_label,
                        '▶ Combined',
                        f"{combined_owed:,.2f}" if combined_owed else '—',
                    ))

            status_tag = 'active' if active else 'inactive'
            type_tag   = 'exclusive' if slot_type == 'exclusive' else status_tag
            tags       = (type_tag, d_tag)
            self.consign_tree.insert('', 'end', iid=str(cid), tags=tags, values=(
                type_label, name, item,
                cur_str, max_str, price_str,
                d_label,
                'Active' if active else 'Inactive',
                owed_str,
            ))

        if sel and self.consign_tree.exists(sel[0]):
            self.consign_tree.selection_set(sel[0])

    def _consign_load_sales(self):
        """Load the sales log for the selected consignor."""
        sel = self.consign_tree.selection()
        if not sel or not sel[0].isdigit():
            return  # ignore combined summary rows
        cid  = int(sel[0])
        name = self.consign_tree.set(sel[0], 'name')
        self._consign_log_title.configure(text=f'Sales Log \u2014 {name}')

        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT id, sale_date, quantity, price_per_unit,
                   total_isk, consignor_isk, broker_isk, paid, paid_date, notes,
                   COALESCE(corp_donation_isk, 0)
            FROM consignment_sales
            WHERE consignor_id = ?
            ORDER BY sale_date DESC, id DESC
        """, (cid,)).fetchall()
        owed = conn.execute(
            "SELECT COALESCE(SUM(consignor_isk),0) FROM consignment_sales WHERE consignor_id=? AND paid=0",
            (cid,)).fetchone()[0]
        paid_total = conn.execute(
            "SELECT COALESCE(SUM(consignor_isk),0) FROM consignment_sales WHERE consignor_id=? AND paid=1",
            (cid,)).fetchone()[0]
        corp_owed = conn.execute(
            "SELECT COALESCE(SUM(corp_donation_isk),0) FROM consignment_sales WHERE consignor_id=? AND paid=0",
            (cid,)).fetchone()[0]
        conn.close()

        self.sales_tree.delete(*self.sales_tree.get_children())
        for idx, (sid, date, qty, ppu, total, their_isk, my_isk, paid, paid_date, notes, corp_don) in enumerate(rows):
            alt      = 'row_a' if idx % 2 == 0 else 'row_b'
            paid_tag = 'paid' if paid else 'unpaid'
            paid_str = f"\u2713 {paid_date[:10] if paid_date else ''}" if paid else '\u2014'
            corp_don_str = f"{corp_don:,.2f}" if corp_don else '—'
            self.sales_tree.insert('', 'end', iid=str(sid), tags=(paid_tag, alt), values=(
                date[:10], qty,
                f"{ppu:,.2f}", f"{total:,.2f}",
                f"{their_isk:,.2f}", corp_don_str, f"{my_isk:,.2f}",
                paid_str, notes or '',
            ))

        self._consign_owed_lbl.configure(
            text=f"Owed: {owed:,.2f} ISK" if owed else "Owed: 0 ISK")
        self._consign_paid_lbl.configure(
            text=f"Total Paid Out: {paid_total:,.2f} ISK" if paid_total else "Total Paid Out: 0 ISK")
        self._consign_corp_lbl.configure(
            text=f"Corp Donation Owed: {corp_owed:,.2f} ISK" if corp_owed else "Corp Donation Owed: 0 ISK")

    def _consign_add_dialog(self, consignor_id=None):
        """Add or edit a consignor record."""
        existing = None
        if consignor_id:
            conn = sqlite3.connect(DB_PATH)
            existing = conn.execute(
                "SELECT character_name, item_name, item_type_id, list_price, "
                "consignor_pct, start_date, notes, slot_type, slot_priority, "
                "max_units, demand_tier, current_qty, "
                "COALESCE(corp_donation_opted,0), COALESCE(corp_donation_pct,0) "
                "FROM consignors WHERE id=?",
                (consignor_id,)).fetchone()
            conn.close()

        dlg = tk.Toplevel(self.root)
        dlg.title('Edit Consignor' if existing else 'Add Consignor')
        dlg.geometry('480x620')
        dlg.configure(background='#0a1520')
        dlg.resizable(True, True)
        dlg.minsize(420, 380)
        dlg.grab_set()

        # ── Scrollable content area ────────────────────────────────────────
        vsb    = ttk.Scrollbar(dlg, orient='vertical')
        canvas = tk.Canvas(dlg, background='#0a1520', highlightthickness=0,
                           yscrollcommand=vsb.set)
        vsb.configure(command=canvas.yview)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, background='#0a1520')
        _cw   = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_inner_cfg(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas_cfg(e):
            canvas.itemconfig(_cw, width=e.width)
        def _on_wheel(e):
            canvas.yview_scroll(-1 * (e.delta // 120), 'units')

        inner.bind('<Configure>', _on_inner_cfg)
        canvas.bind('<Configure>', _on_canvas_cfg)
        canvas.bind_all('<MouseWheel>', _on_wheel)
        dlg.bind('<Destroy>', lambda e: canvas.unbind_all('<MouseWheel>'))
        # ──────────────────────────────────────────────────────────────────

        lbl_cfg = dict(background='#0a1520', foreground='#88d0e8', font=('Segoe UI', 10))
        sub_cfg = dict(background='#0a1520', foreground='#3a7090', font=('Segoe UI', 8, 'italic'))

        def labeled_entry(label, default='', width=32):
            tk.Label(inner, text=label, **lbl_cfg).pack(anchor='w', padx=16, pady=(6, 2))
            var = tk.StringVar(value=default)
            ttk.Entry(inner, textvariable=var, width=width).pack(anchor='w', padx=16)
            return var

        name_var = labeled_entry('Character Name',       existing[0] if existing else '')
        item_var = labeled_entry('Item Being Consigned', existing[1] if existing else '')

        # Type ID row with live name preview
        tk.Label(inner, text='Item Type ID  (for contract sync)', **lbl_cfg).pack(
            anchor='w', padx=16, pady=(6, 2))
        tid_row = tk.Frame(inner, background='#0a1520')
        tid_row.pack(anchor='w', padx=16)
        tid_var = tk.StringVar(value=str(existing[2]) if existing and existing[2] else '')
        ttk.Entry(tid_row, textvariable=tid_var, width=12).pack(side='left', padx=(0, 8))
        tid_name_lbl = tk.Label(tid_row, text='', background='#0a1520',
                                foreground='#44ddaa', font=('Segoe UI', 9, 'italic'))
        tid_name_lbl.pack(side='left')

        def _lookup_type_name(*_):
            raw = tid_var.get().strip()
            if not raw.isdigit():
                tid_name_lbl.configure(text='')
                return
            conn2 = sqlite3.connect(DB_PATH)
            row = conn2.execute(
                "SELECT type_name FROM inv_types WHERE type_id=?", (int(raw),)).fetchone()
            conn2.close()
            tid_name_lbl.configure(text=row[0] if row else '(not found)')
        tid_var.trace_add('write', _lookup_type_name)
        _lookup_type_name()

        price_var = labeled_entry('Agreed List Price / Unit',
                                  f"{existing[3]:.2f}" if existing and existing[3] is not None else '')
        pct_var   = labeled_entry('Consignor % (their share)',
                                  f"{existing[4]:.1f}" if existing else '85.0')
        date_var  = labeled_entry('Start Date (YYYY-MM-DD)',
                                  existing[5] if existing else datetime.now().strftime('%Y-%m-%d'))

        # ── Slot type ─────────────────────────────────────────────────────
        tk.Frame(inner, background='#1a3040', height=1).pack(fill='x', padx=16, pady=(10, 0))
        tk.Label(inner, text='Slot Configuration', background='#0a1520',
                 foreground='#00d9ff', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=16, pady=(6, 2))

        slot_var = tk.StringVar(value=existing[7] if existing and existing[7] else 'shared')
        slot_row = tk.Frame(inner, background='#0a1520')
        slot_row.pack(anchor='w', padx=16)
        tk.Radiobutton(slot_row, text='◈ Shared  (multiple suppliers)',
                       variable=slot_var, value='shared',
                       background='#0a1520', foreground='#66d9ff',
                       selectcolor='#0a1520', activebackground='#0a1520',
                       font=('Segoe UI', 10)).pack(side='left', padx=(0, 16))
        tk.Radiobutton(slot_row, text='★ Exclusive  (single supplier)',
                       variable=slot_var, value='exclusive',
                       background='#0a1520', foreground='#ffcc44',
                       selectcolor='#0a1520', activebackground='#0a1520',
                       font=('Segoe UI', 10)).pack(side='left')

        # Priority + Max units row
        pm_row = tk.Frame(inner, background='#0a1520')
        pm_row.pack(anchor='w', padx=16, pady=(6, 0))
        tk.Label(pm_row, text='Priority (1=primary):', **lbl_cfg).pack(side='left', padx=(0, 6))
        pri_var = tk.StringVar(value=str(existing[8]) if existing and existing[8] else '1')
        ttk.Entry(pm_row, textvariable=pri_var, width=4).pack(side='left', padx=(0, 16))
        tk.Label(pm_row, text='Max Units in Slot:', **lbl_cfg).pack(side='left', padx=(0, 6))
        max_var = tk.StringVar(value=str(existing[9]) if existing and existing[9] else '')
        ttk.Entry(pm_row, textvariable=max_var, width=10).pack(side='left')
        tk.Label(inner, text='For shared slots: lower priority number = listed first. '
                 'Leave Max Units blank for unlimited.',
                 **sub_cfg).pack(anchor='w', padx=16)

        # Current qty + demand tier row
        tk.Label(inner, text='Current Qty in Slot', **lbl_cfg).pack(anchor='w', padx=16, pady=(6, 2))
        qty_var = tk.StringVar(value=str(existing[11]) if existing and existing[11] else '0')
        ttk.Entry(inner, textvariable=qty_var, width=12).pack(anchor='w', padx=16)
        tk.Label(inner, text='Update when you restock or confirm contract qty.',
                 **sub_cfg).pack(anchor='w', padx=16)

        tk.Label(inner, text='Demand Tier', **lbl_cfg).pack(anchor='w', padx=16, pady=(6, 2))
        dem_var = tk.StringVar(value=existing[10] if existing and existing[10] else 'medium')
        dem_row = tk.Frame(inner, background='#0a1520')
        dem_row.pack(anchor='w', padx=16)
        for val, lbl, fg in [('low', '▼ Low', '#66d9ff'), ('medium', '◆ Medium', '#ffcc44'),
                              ('high', '▲ High', '#ff6666')]:
            tk.Radiobutton(dem_row, text=lbl, variable=dem_var, value=val,
                           background='#0a1520', foreground=fg,
                           selectcolor='#0a1520', activebackground='#0a1520',
                           font=('Segoe UI', 10)).pack(side='left', padx=(0, 12))

        # ── Corp Donation ──────────────────────────────────────────────────
        tk.Frame(inner, background='#1a3040', height=1).pack(fill='x', padx=16, pady=(10, 0))
        tk.Label(inner, text='Corp Donation (Optional)', background='#0a1520',
                 foreground='#ff9944', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=16, pady=(6, 2))

        don_opted_var = tk.IntVar(value=int(existing[12]) if existing else 0)
        don_pct_var   = tk.StringVar(value=f"{existing[13]:.1f}" if existing and existing[13] else '0.0')

        don_row = tk.Frame(inner, background='#0a1520')
        don_row.pack(anchor='w', padx=16)
        tk.Radiobutton(don_row, text='No donation', variable=don_opted_var, value=0,
                       background='#0a1520', foreground='#88d0e8',
                       selectcolor='#0a1520', activebackground='#0a1520',
                       font=('Segoe UI', 10)).pack(side='left', padx=(0, 16))
        tk.Radiobutton(don_row, text='Donate to corp', variable=don_opted_var, value=1,
                       background='#0a1520', foreground='#ff9944',
                       selectcolor='#0a1520', activebackground='#0a1520',
                       font=('Segoe UI', 10)).pack(side='left')

        don_pct_row = tk.Frame(inner, background='#0a1520')
        don_pct_row.pack(anchor='w', padx=16, pady=(4, 0))
        tk.Label(don_pct_row, text='Donation %:', **lbl_cfg).pack(side='left', padx=(0, 6))
        don_pct_entry = ttk.Entry(don_pct_row, textvariable=don_pct_var, width=8)
        don_pct_entry.pack(side='left')
        tk.Label(don_pct_row, text='of consignor\'s share', **sub_cfg).pack(side='left', padx=(6, 0))
        tk.Label(inner, text='Donation is deducted from the consignor\'s share per sale.',
                 **sub_cfg).pack(anchor='w', padx=16)

        # ── Notes ─────────────────────────────────────────────────────────
        tk.Frame(inner, background='#1a3040', height=1).pack(fill='x', padx=16, pady=(10, 0))
        tk.Label(inner, text='Notes', **lbl_cfg).pack(anchor='w', padx=16, pady=(6, 2))
        notes_txt = tk.Text(inner, width=46, height=3, background='#0d2535',
                            foreground='#ccddee', insertbackground='white',
                            font=('Segoe UI', 9), relief='flat')
        notes_txt.pack(anchor='w', padx=16, pady=(0, 12))
        if existing and existing[6]:
            notes_txt.insert('1.0', existing[6])

        def save():
            try:
                name      = name_var.get().strip()
                item      = item_var.get().strip()
                tid_raw   = tid_var.get().strip()
                type_id   = int(tid_raw) if tid_raw.isdigit() else None
                price     = float(price_var.get()) if price_var.get().strip() else None
                pct       = float(pct_var.get())
                date      = date_var.get().strip()
                notes     = notes_txt.get('1.0', 'end').strip()
                slot_type = slot_var.get()
                priority  = int(pri_var.get()) if pri_var.get().strip().isdigit() else 1
                max_units = int(max_var.get()) if max_var.get().strip().isdigit() else None
                cur_qty   = int(qty_var.get()) if qty_var.get().strip().isdigit() else 0
                demand    = dem_var.get()
                don_opted = don_opted_var.get()
                don_pct   = float(don_pct_var.get()) if don_opted else 0.0
                if not name or not item:
                    messagebox.showerror('Error', 'Character Name and Item are required.', parent=dlg)
                    return
                conn = sqlite3.connect(DB_PATH)
                if consignor_id:
                    conn.execute(
                        "UPDATE consignors SET character_name=?, item_name=?, item_type_id=?, "
                        "list_price=?, consignor_pct=?, start_date=?, notes=?, "
                        "slot_type=?, slot_priority=?, max_units=?, demand_tier=?, current_qty=?, "
                        "corp_donation_opted=?, corp_donation_pct=? "
                        "WHERE id=?",
                        (name, item, type_id, price, pct, date, notes,
                         slot_type, priority, max_units, demand, cur_qty,
                         don_opted, don_pct, consignor_id))
                else:
                    conn.execute(
                        "INSERT INTO consignors (character_name, item_name, item_type_id, "
                        "list_price, consignor_pct, start_date, notes, "
                        "slot_type, slot_priority, max_units, demand_tier, current_qty, "
                        "corp_donation_opted, corp_donation_pct) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (name, item, type_id, price, pct, date, notes,
                         slot_type, priority, max_units, demand, cur_qty,
                         don_opted, don_pct))
                conn.commit()
                conn.close()
                dlg.destroy()
                self._consign_load_consignors()
            except ValueError as e:
                messagebox.showerror('Error', f'Invalid value: {e}', parent=dlg)

        # Fixed Save/Cancel bar — packed into dlg (outside scroll canvas)
        btn_bar = tk.Frame(dlg, background='#0a1520')
        btn_bar.pack(side='bottom', fill='x')
        tk.Frame(btn_bar, background='#1a3040', height=1).pack(fill='x')
        btn_row = tk.Frame(btn_bar, background='#0a1520')
        btn_row.pack(pady=8)
        ttk.Button(btn_row, text='Save', style='Action.TButton', command=save).pack(side='left', padx=6)
        ttk.Button(btn_row, text='Cancel', command=dlg.destroy).pack(side='left', padx=6)

    def _consign_edit_dialog(self):
        """Open the edit dialog for the selected consignor."""
        sel = self.consign_tree.selection()
        if not sel or not sel[0].isdigit():
            return  # ignore combined summary rows
        self._consign_add_dialog(consignor_id=int(sel[0]))

    def _consign_toggle_active(self):
        """Toggle the active/inactive status of the selected consignor."""
        sel = self.consign_tree.selection()
        if not sel or not sel[0].isdigit():
            return
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE consignors SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (int(sel[0]),))
        conn.commit()
        conn.close()
        self._consign_load_consignors()

    def _consign_log_sale_dialog(self):
        """Dialog to log a new sale for the selected consignor."""
        sel = self.consign_tree.selection()
        if not sel or not sel[0].isdigit():
            messagebox.showinfo('Select Consignor', 'Select an individual consignor row first.')
            return
        cid       = int(sel[0])
        vals      = self.consign_tree.item(sel[0])['values']
        name      = vals[1]
        item      = vals[2]
        their_pct = str(vals[6]).replace('%', '').strip()
        raw_price = str(vals[5]).replace(',', '').strip()

        # Fetch donation settings for this consignor
        _dconn = sqlite3.connect(DB_PATH)
        _drow  = _dconn.execute(
            "SELECT COALESCE(corp_donation_opted,0), COALESCE(corp_donation_pct,0) "
            "FROM consignors WHERE id=?", (cid,)).fetchone()
        _dconn.close()
        don_opted, don_pct = _drow if _drow else (0, 0.0)

        dlg = tk.Toplevel(self.root)
        dlg.title(f'Log Sale \u2014 {name}')
        dlg.geometry('400x330' if don_opted else '400x310')
        dlg.configure(background='#0a1520')
        dlg.resizable(False, False)
        dlg.grab_set()

        lbl_cfg = dict(background='#0a1520', foreground='#88d0e8', font=('Segoe UI', 10))
        tk.Label(dlg, text=f'Item: {item}', background='#0a1520',
                 foreground='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=16, pady=(12, 6))
        if don_opted:
            tk.Label(dlg, text=f'Corp donation: {don_pct:.1f}% of consignor share', background='#0a1520',
                     foreground='#ff9944', font=('Segoe UI', 8, 'italic')).pack(anchor='w', padx=16, pady=(0, 4))

        def labeled_entry(label, default='', width=24):
            tk.Label(dlg, text=label, **lbl_cfg).pack(anchor='w', padx=16, pady=(4, 2))
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=width).pack(anchor='w', padx=16)
            return var

        qty_var   = labeled_entry('Quantity Sold')
        price_var = labeled_entry('Sale Price / Unit (ISK)', raw_price if raw_price != '\u2014' else '')
        date_var  = labeled_entry('Sale Date (YYYY-MM-DD)',  datetime.now().strftime('%Y-%m-%d'))
        notes_var = labeled_entry('Notes (optional)', '', width=40)

        preview = tk.Label(dlg, text='', background='#0a1520',
                           foreground='#ffcc44', font=('Segoe UI', 9))
        preview.pack(padx=16, pady=(6, 0))

        def update_preview(*_):
            try:
                qty          = int(qty_var.get())
                price        = float(price_var.get())
                their_f      = float(their_pct) / 100.0
                total        = qty * price
                gross_their  = total * their_f
                my_isk       = total - gross_their
                donation_isk = gross_their * don_pct / 100.0 if don_opted else 0.0
                their_net    = gross_their - donation_isk
                if don_opted:
                    preview.configure(
                        text=f"Total: {total:,.2f}  \u2192  {name}: {their_net:,.2f}  "
                             f"|  Corp: {donation_isk:,.2f}  |  Me: {my_isk:,.2f}")
                else:
                    preview.configure(
                        text=f"Total: {total:,.2f}  \u2192  {name}: {their_net:,.2f}  |  Me: {my_isk:,.2f}")
            except ValueError:
                preview.configure(text='')

        qty_var.trace_add('write', update_preview)
        price_var.trace_add('write', update_preview)

        def save():
            try:
                qty          = int(qty_var.get())
                price        = float(price_var.get())
                date         = date_var.get().strip()
                notes        = notes_var.get().strip()
                their_f      = float(their_pct) / 100.0
                total        = round(qty * price, 2)
                gross_their  = total * their_f
                my_isk       = round(total - gross_their, 2)
                donation_isk = round(gross_their * don_pct / 100.0, 2) if don_opted else 0.0
                their_isk    = round(gross_their - donation_isk, 2)
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO consignment_sales "
                    "(consignor_id, sale_date, quantity, price_per_unit, total_isk, "
                    "consignor_isk, broker_isk, corp_donation_isk, paid, notes) "
                    "VALUES (?,?,?,?,?,?,?,?,0,?)",
                    (cid, date, qty, price, total, their_isk, my_isk, donation_isk, notes))
                conn.commit()
                conn.close()
                dlg.destroy()
                self._consign_load_sales()
            except ValueError as e:
                messagebox.showerror('Error', f'Invalid value: {e}', parent=dlg)

        btn_row = tk.Frame(dlg, background='#0a1520')
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text='Log Sale', style='Action.TButton', command=save).pack(side='left', padx=6)
        ttk.Button(btn_row, text='Cancel', command=dlg.destroy).pack(side='left', padx=6)

    def _consign_mark_paid(self):
        """Mark all selected sales rows as paid."""
        selected = self.sales_tree.selection()
        if not selected:
            return
        today    = datetime.now().strftime('%Y-%m-%d')
        sale_ids = [int(iid) for iid in selected]
        conn = sqlite3.connect(DB_PATH)
        conn.executemany(
            "UPDATE consignment_sales SET paid=1, paid_date=? WHERE id=? AND paid=0",
            [(today, sid) for sid in sale_ids])
        conn.commit()
        conn.close()
        self._consign_load_sales()

    def _consign_delete_sales(self):
        """Delete selected sales log entries after confirmation."""
        selected = self.sales_tree.selection()
        if not selected:
            return
        n = len(selected)
        if not messagebox.askyesno(
                'Confirm Delete',
                f'Permanently delete {n} sale entr{"y" if n == 1 else "ies"}?\nThis cannot be undone.',
                parent=self.root):
            return
        sale_ids = [int(iid) for iid in selected]
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            f"DELETE FROM consignment_sales WHERE id IN ({','.join('?' * n)})",
            sale_ids)
        conn.commit()
        conn.close()
        self._consign_load_sales()

    def _consign_sync_contracts(self):
        """
        Scan contract_profits table for finished contracts containing consigned items.

        - Exclusive slots (one consignor per type_id): auto-log with value-weighted attribution.
        - Shared slots (multiple active consignors for the same type_id): insert a row in
          consignment_pending_sales for manual split via the Attribution panel.
        """
        conn = sqlite3.connect(DB_PATH)

        # Get active consignors that have a type_id set
        consignors = conn.execute(
            "SELECT id, character_name, item_type_id, consignor_pct, "
            "COALESCE(corp_donation_opted,0), COALESCE(corp_donation_pct,0) "
            "FROM consignors WHERE item_type_id IS NOT NULL AND active=1"
        ).fetchall()
        if not consignors:
            conn.close()
            messagebox.showinfo('Sync Contracts',
                                'No active consignors with Item Type IDs set.\n'
                                'Edit a consignor to add their item\'s Type ID first.',
                                parent=self.root)
            return

        # Build type_id → list of consignors (may be multiple for shared slots)
        from collections import defaultdict
        type_to_consignors = defaultdict(list)
        for c in consignors:
            type_to_consignors[c[2]].append(c)

        # type_ids already present in pending table — don't re-queue them per contract
        already_pending = set(
            r[0] for r in conn.execute(
                "SELECT DISTINCT contract_id FROM consignment_pending_sales"
            ).fetchall()
        )

        # Contracts already fully synced
        synced_ids = set(
            r[0] for r in conn.execute(
                "SELECT DISTINCT source_contract_id FROM consignment_sales "
                "WHERE source_contract_id IS NOT NULL"
            ).fetchall()
        )

        # All finished contracts with item data
        contracts = conn.execute(
            "SELECT contract_id, date_completed, contract_price, items_json "
            "FROM contract_profits WHERE contract_price > 0 AND items_json IS NOT NULL"
        ).fetchall()

        import json as _json
        from datetime import datetime as _dt

        new_entries  = 0
        new_pending  = 0
        skipped      = 0

        for contract_id, date_completed, contract_price, items_json_str in contracts:
            if contract_id in synced_ids:
                continue
            try:
                items = _json.loads(items_json_str)
            except (_json.JSONDecodeError, TypeError):
                continue

            consign_hits = [i for i in items if i.get('type_id') in type_to_consignors]
            if not consign_hits:
                continue

            # Value-weighted attribution proxy
            total_weighted = sum(i.get('qty', 0) * i.get('unit_cost', 0) for i in items)

            for ci in consign_hits:
                type_id = ci['type_id']
                qty     = ci.get('qty', 0)
                if qty <= 0:
                    continue

                consignor_list = type_to_consignors[type_id]
                sale_date      = (date_completed or '')[:10]

                if len(consignor_list) > 1:
                    # Shared slot — route to pending attribution (skip if already queued)
                    if contract_id not in already_pending:
                        item_weighted = qty * ci.get('unit_cost', 0)
                        if total_weighted > 0:
                            attributed = contract_price * (item_weighted / total_weighted)
                        else:
                            attributed = contract_price / max(len(items), 1)

                        item_name = next(
                            (c['item_name'] for c in consignor_list if c), '')
                        conn.execute(
                            "INSERT INTO consignment_pending_sales "
                            "(contract_id, type_id, item_name, total_qty, total_isk, "
                            " sale_date, created_at, notes) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (contract_id, type_id,
                             consignor_list[0][1] if not item_name else item_name,
                             qty, round(attributed, 2), sale_date,
                             _dt.utcnow().isoformat(),
                             f"Shared slot | contract {contract_id}"))
                        already_pending.add(contract_id)
                        new_pending += 1
                else:
                    # Exclusive slot — auto-log directly
                    c_id, c_name, _, c_pct, c_don_opted, c_don_pct = consignor_list[0]
                    item_weighted = qty * ci.get('unit_cost', 0)
                    if total_weighted > 0:
                        attributed = contract_price * (item_weighted / total_weighted)
                    else:
                        attributed = contract_price / max(len(items), 1)
                        skipped += 1

                    per_unit     = round(attributed / qty, 2)
                    total_isk    = round(attributed, 2)
                    gross_their  = total_isk * c_pct / 100.0
                    my_isk       = round(total_isk - gross_their, 2)
                    don_isk      = round(gross_their * c_don_pct / 100.0, 2) if c_don_opted else 0.0
                    their_isk    = round(gross_their - don_isk, 2)

                    conn.execute(
                        "INSERT INTO consignment_sales "
                        "(consignor_id, sale_date, quantity, price_per_unit, total_isk, "
                        "consignor_isk, broker_isk, corp_donation_isk, paid, notes, "
                        "source_contract_id, auto_logged) "
                        "VALUES (?,?,?,?,?,?,?,?,0,?,?,1)",
                        (c_id, sale_date, qty, per_unit, total_isk,
                         their_isk, my_isk, don_isk,
                         f"Auto | contract {contract_id}", contract_id))
                    new_entries += 1

        conn.commit()
        conn.close()

        parts = []
        if new_entries:
            parts.append(f'{new_entries} sale entr{"y" if new_entries == 1 else "ies"} auto-logged.')
        if new_pending:
            parts.append(f'{new_pending} shared-slot sale(s) added to Pending Attribution.')
        if skipped:
            parts.append(f'{skipped} used equal-split fallback (no cost data).')
        if not parts:
            parts = ['No new contracts found to sync.']
        messagebox.showinfo('Sync Contracts', '\n'.join(parts), parent=self.root)
        self._consign_load_sales()
        self._consign_load_pending()

    # ── Container / Pending dialog openers ───────────────────────────────

    def _consign_open_containers_dialog(self):
        """Open a popup window for container assignment management."""
        dlg = tk.Toplevel(self.root)
        dlg.title('Container Assignments')
        dlg.geometry('860x260')
        dlg.configure(background='#0a1520')

        inner = ttk.Frame(dlg, style='Card.TFrame')
        inner.pack(fill='both', expand=True, padx=10, pady=8)

        tb = ttk.Frame(inner, style='Card.TFrame')
        tb.pack(fill='x', pady=(0, 6))
        tk.Label(tb, text='Container Assignments', background='#0a2030',
                 foreground='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 12))

        cc_cols = ('consignor', 'item', 'container_id', 'container_name', 'notes')
        tree = ttk.Treeview(inner, columns=cc_cols, show='headings', selectmode='browse', height=8)
        for col_id, hd, w, a in [
            ('consignor',      'Consignor',    150, 'w'),
            ('item',           'Item',         180, 'w'),
            ('container_id',   'Container ID', 135, 'e'),
            ('container_name', 'ESI Name',     200, 'w'),
            ('notes',          'Notes',        260, 'w'),
        ]:
            tree.heading(col_id, text=hd)
            tree.column(col_id, width=w, minwidth=40, anchor=a)

        vsb = ttk.Scrollbar(inner, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        self.container_tree = tree

        def _reload():
            self._consign_load_containers()

        def _remove():
            sel = tree.selection()
            if not sel:
                return
            if not messagebox.askyesno('Confirm',
                                       'Remove this container assignment?\n'
                                       '(Does not affect the actual in-game container.)',
                                       parent=dlg):
                return
            row_id = int(sel[0])
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM consignor_containers WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
            _reload()
            self._consign_load_consignors()

        def _on_close():
            self.container_tree = None
            dlg.destroy()

        ttk.Button(tb, text='+ Assign Container',
                   command=lambda: self._consign_assign_container_dialog(reload_cb=_reload)
                   ).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Remove', command=_remove).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='\u21ba Refresh Names',
                   command=lambda: self._consign_refresh_container_names(reload_cb=_reload)
                   ).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Manage All',
                   command=self._consign_manage_containers_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Close', command=_on_close).pack(side='right')

        vsb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        dlg.protocol('WM_DELETE_WINDOW', _on_close)
        _reload()

    def _consign_open_pending_dialog(self):
        """Open a popup window for shared-slot pending attribution."""
        dlg = tk.Toplevel(self.root)
        dlg.title('Pending Attribution')
        dlg.geometry('860x300')
        dlg.configure(background='#0a1520')

        inner = ttk.Frame(dlg, style='Card.TFrame')
        inner.pack(fill='both', expand=True, padx=10, pady=8)

        tb = ttk.Frame(inner, style='Card.TFrame')
        tb.pack(fill='x', pady=(0, 6))
        tk.Label(tb, text='Pending Attribution', background='#0a2030',
                 foreground='#ff9944', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 12))

        ps_cols = ('sale_date', 'item_name', 'total_qty', 'total_isk', 'notes')
        tree = ttk.Treeview(inner, columns=ps_cols, show='headings', selectmode='browse', height=10)
        for col_id, hd, w, a in [
            ('sale_date',  'Sale Date',  110, 'c'),
            ('item_name',  'Item',       220, 'w'),
            ('total_qty',  'Total Qty',   90, 'e'),
            ('total_isk',  'Total ISK',  150, 'e'),
            ('notes',      'Notes',      360, 'w'),
        ]:
            tree.heading(col_id, text=hd)
            tree.column(col_id, width=w, minwidth=40, anchor=a)
        tree.tag_configure('pending_row', foreground='#ff9944')

        vsb = ttk.Scrollbar(inner, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        self.pending_tree = tree

        def _on_close():
            self.pending_tree = None
            dlg.destroy()

        ttk.Button(tb, text='Split / Attribute',
                   command=self._consign_split_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Delete Selected',
                   command=self._consign_delete_pending).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Close', command=_on_close).pack(side='right')

        vsb.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        dlg.protocol('WM_DELETE_WINDOW', _on_close)
        self._consign_load_pending()

    # ── Container assignment methods ──────────────────────────────────────

    def _consign_load_containers(self):
        """Populate the Container Assignments treeview."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT cc.id, c.character_name, c.item_name,
                   cc.container_item_id, cc.container_name, cc.notes
            FROM consignor_containers cc
            JOIN consignors c ON c.id = cc.consignor_id
            ORDER BY c.item_name, c.character_name
        """).fetchall()
        conn.close()

        try:
            if self.container_tree is None:
                return
            self.container_tree.delete(*self.container_tree.get_children())
            for row_id, consignor, item, cid, cname, notes in rows:
                self.container_tree.insert('', 'end', iid=str(row_id), values=(
                    consignor,
                    item,
                    cid,
                    cname or '(no name yet)',
                    notes or '',
                ))
        except Exception:
            pass

    def _consign_assign_container_dialog(self, reload_cb=None):
        """Dialog to assign a hangar container to a consignor, picked from known_containers."""
        conn = sqlite3.connect(DB_PATH)
        consignors = conn.execute(
            "SELECT id, character_name, item_name FROM consignors WHERE active=1 ORDER BY item_name, character_name"
        ).fetchall()
        # Available containers: known, not ignored, not already assigned
        available = conn.execute("""
            SELECT kc.item_id, kc.name
            FROM known_containers kc
            WHERE kc.ignored = 0
              AND kc.item_id NOT IN (SELECT container_item_id FROM consignor_containers)
            ORDER BY kc.name, kc.item_id
        """).fetchall()
        conn.close()

        if not consignors:
            messagebox.showinfo('Assign Container',
                                'No active consignors found. Add a consignor first.',
                                parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title('Assign Container to Consignor')
        dlg.geometry('460x310')
        dlg.configure(background='#0a1520')
        dlg.grab_set()

        _lkw = dict(background='#0a1520', foreground='#aaccdd', font=('Segoe UI', 9))
        _ekw = dict(background='#0d1f30', foreground='#e0e8f0', insertbackground='white',
                    relief='flat', font=('Segoe UI', 9))

        tk.Label(dlg, text='Assign Hangar Container', background='#0a1520',
                 foreground='#66d9ff', font=('Segoe UI', 11, 'bold')).pack(pady=(12, 8))

        frm = tk.Frame(dlg, background='#0a1520')
        frm.pack(fill='x', padx=20)

        tk.Label(frm, text='Consignor:', **_lkw).grid(row=0, column=0, sticky='w', pady=4)
        consignor_var = tk.StringVar()
        c_labels = [f"{c[1]} — {c[2]}" for c in consignors]
        consignor_cb = ttk.Combobox(frm, textvariable=consignor_var, values=c_labels,
                                     width=36, state='readonly')
        consignor_cb.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=4)
        if c_labels:
            consignor_cb.current(0)

        tk.Label(frm, text='Container:', **_lkw).grid(row=1, column=0, sticky='w', pady=4)
        container_var = tk.StringVar()
        if available:
            cont_labels = [f"{r[1] or '(unnamed)'} — {r[0]}" for r in available]
            cont_cb = ttk.Combobox(frm, textvariable=container_var, values=cont_labels,
                                   width=36, state='readonly')
            cont_cb.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=4)
            cont_cb.current(0)
            hint = ('Select a container from the list above.\n'
                    'Run \u21ba Refresh Names to update after creating new containers in-game.')
        else:
            # Fallback: manual entry
            cont_cb = None
            tk.Entry(frm, textvariable=container_var, width=24, **_ekw).grid(
                row=1, column=1, sticky='w', padx=(8, 0), pady=4)
            hint = ('No available containers found. Run \u21ba Refresh Names to sync from ESI,\n'
                    'or enter the Container Item ID manually.')

        tk.Label(frm, text=hint, background='#0a1520', foreground='#556677',
                 font=('Segoe UI', 8), justify='left').grid(
            row=2, column=0, columnspan=2, sticky='w', pady=(2, 4))

        tk.Label(frm, text='Notes (optional):', **_lkw).grid(row=3, column=0, sticky='w', pady=4)
        notes_var = tk.StringVar()
        tk.Entry(frm, textvariable=notes_var, width=36, **_ekw).grid(
            row=3, column=1, sticky='ew', padx=(8, 0), pady=4)

        frm.columnconfigure(1, weight=1)

        def _save():
            idx = consignor_cb.current()
            if idx < 0:
                return
            consignor_id = consignors[idx][0]

            if cont_cb is not None:
                sel = cont_cb.current()
                if sel < 0:
                    messagebox.showerror('Invalid', 'Select a container.', parent=dlg)
                    return
                item_id = available[sel][0]
            else:
                cid_txt = container_var.get().strip()
                if not cid_txt.isdigit():
                    messagebox.showerror('Invalid', 'Container Item ID must be a number.', parent=dlg)
                    return
                item_id = int(cid_txt)

            conn2 = sqlite3.connect(DB_PATH)
            try:
                conn2.execute(
                    "INSERT INTO consignor_containers (consignor_id, container_item_id, notes) "
                    "VALUES (?,?,?)",
                    (consignor_id, item_id, notes_var.get().strip() or None))
                conn2.commit()
            except Exception as e:
                messagebox.showerror('Error', f'Could not save: {e}', parent=dlg)
                conn2.close()
                return
            conn2.close()
            dlg.destroy()
            if reload_cb:
                reload_cb()

        bf = tk.Frame(dlg, background='#0a1520')
        bf.pack(pady=12)
        ttk.Button(bf, text='Save', style='Action.TButton', command=_save).pack(side='left', padx=4)
        ttk.Button(bf, text='Cancel', command=dlg.destroy).pack(side='left', padx=4)

    def _consign_manage_containers_dialog(self):
        """Dialog showing all known containers with ignore/unignore and assign actions."""
        dlg = tk.Toplevel(self.root)
        dlg.title('Manage All Containers')
        dlg.geometry('660x380')
        dlg.configure(background='#0a1520')
        dlg.grab_set()

        tk.Label(dlg, text='All Known Containers', background='#0a1520',
                 foreground='#66d9ff', font=('Segoe UI', 11, 'bold')).pack(pady=(12, 4))
        tk.Label(dlg,
                 text='Containers discovered via ESI sync. Ignored containers are hidden from the '
                      'assign picker but kept here so you can reactivate them later.',
                 background='#0a1520', foreground='#556677',
                 font=('Segoe UI', 8), wraplength=620, justify='left').pack(padx=20, pady=(0, 8))

        tree_frame = tk.Frame(dlg, background='#0a1520')
        tree_frame.pack(fill='both', expand=True, padx=12)

        cols = ('name', 'item_id', 'assigned_to', 'status')
        tv = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode='browse', height=10)
        for cid, hd, w, a in [
            ('name',        'ESI Name',   200, 'w'),
            ('item_id',     'Item ID',    130, 'e'),
            ('assigned_to', 'Assigned To',200, 'w'),
            ('status',      'Status',      90, 'w'),
        ]:
            tv.heading(cid, text=hd)
            tv.column(cid, width=w, minwidth=40, anchor=a)

        tv.tag_configure('ignored', foreground='#445566')
        tv.tag_configure('assigned', foreground='#66cc88')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        tv.pack(fill='both', expand=True)

        def _load():
            tv.delete(*tv.get_children())
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("""
                SELECT kc.item_id, kc.name, kc.ignored,
                       c.character_name, c.item_name
                FROM known_containers kc
                LEFT JOIN consignor_containers cc ON cc.container_item_id = kc.item_id
                LEFT JOIN consignors c            ON c.id = cc.consignor_id
                ORDER BY kc.ignored, kc.name, kc.item_id
            """).fetchall()
            conn.close()
            for item_id, name, ignored, char_name, item_name in rows:
                assigned = f"{char_name} — {item_name}" if char_name else ''
                if ignored:
                    status, tag = 'Ignored', 'ignored'
                elif assigned:
                    status, tag = 'Assigned', 'assigned'
                else:
                    status, tag = 'Available', ''
                tv.insert('', 'end', iid=str(item_id),
                          values=(name or '(unnamed)', item_id, assigned, status),
                          tags=(tag,))

        _load()

        bf = tk.Frame(dlg, background='#0a1520')
        bf.pack(pady=8)

        def _toggle_ignore():
            sel = tv.selection()
            if not sel:
                return
            item_id = int(sel[0])
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute("SELECT ignored FROM known_containers WHERE item_id=?",
                               (item_id,)).fetchone()
            if row is None:
                conn.close()
                return
            new_val = 0 if row[0] else 1
            conn.execute("UPDATE known_containers SET ignored=? WHERE item_id=?",
                         (new_val, item_id))
            conn.commit()
            conn.close()
            _load()

        ttk.Button(bf, text='Toggle Ignore', command=_toggle_ignore).pack(side='left', padx=4)
        ttk.Button(bf, text='Close', command=dlg.destroy).pack(side='left', padx=4)

    def _consign_remove_container(self):
        """Remove the selected container assignment."""
        sel = self.container_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno('Confirm', 'Remove this container assignment?\n'
                                   '(Does not affect the actual in-game container.)',
                                   parent=self.root):
            return
        row_id = int(sel[0])
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM consignor_containers WHERE id=?", (row_id,))
        conn.commit()
        conn.close()
        self._consign_load_containers()

    def _consign_refresh_container_names(self, reload_cb=None):
        """Trigger update_lx_zoj_inventory.py in a background thread to refresh ESI names."""
        import threading, subprocess as _sp

        def _run():
            try:
                result = _sp.run(
                    [sys.executable,
                     os.path.join(PROJECT_DIR, 'update_lx_zoj_inventory.py')],
                    cwd=PROJECT_DIR, capture_output=True, text=True, timeout=180
                )
                ok = result.returncode == 0
            except Exception:
                ok = False

            def _after():
                if reload_cb:
                    reload_cb()
                self._consign_load_consignors()
                messagebox.showinfo(
                    'Refresh Names',
                    'Container names refreshed from ESI.' if ok
                    else 'ESI refresh failed — check console output.',
                    parent=self.root)

            self.root.after(0, _after)

        threading.Thread(target=_run, daemon=True).start()
        messagebox.showinfo('Refresh Names',
                            'Inventory sync started in background.\n'
                            'The table will update when complete.',
                            parent=self.root)

    # ── Pending attribution methods ───────────────────────────────────────

    def _consign_load_pending(self):
        """Populate the Pending Attribution treeview."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT id, sale_date, item_name, total_qty, total_isk, notes "
            "FROM consignment_pending_sales ORDER BY sale_date DESC, id DESC"
        ).fetchall()
        conn.close()

        try:
            if self.pending_tree is None:
                return
            self.pending_tree.delete(*self.pending_tree.get_children())
            for row_id, sale_date, item_name, qty, isk, notes in rows:
                self.pending_tree.insert('', 'end', iid=str(row_id),
                                         tags=('pending_row',),
                                         values=(
                                             sale_date or '',
                                             item_name or '',
                                             f'{qty:,}',
                                             f'{isk:,.2f}',
                                             notes or '',
                                         ))
        except Exception:
            pass

    def _consign_delete_pending(self):
        """Delete the selected pending sale."""
        if self.pending_tree is None:
            return
        sel = self.pending_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno('Confirm Delete',
                                   'Delete this pending sale record?\n'
                                   'No sale entries will be logged — use only if the sale '
                                   'should not be attributed to any consignor.',
                                   parent=self.root):
            return
        row_id = int(sel[0])
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM consignment_pending_sales WHERE id=?", (row_id,))
        conn.commit()
        conn.close()
        self._consign_load_pending()

    def _consign_split_dialog(self):
        """
        Manual attribution dialog for a pending shared-slot sale.
        Shows all active consignors for that item type, lets you enter how many
        units to attribute to each, and optionally uses priority-based FIFO auto-fill.
        """
        if self.pending_tree is None:
            return
        sel = self.pending_tree.selection()
        if not sel:
            messagebox.showinfo('Split', 'Select a pending sale first.', parent=self.root)
            return
        row_id = int(sel[0])

        conn = sqlite3.connect(DB_PATH)
        pending = conn.execute(
            "SELECT id, contract_id, type_id, item_name, total_qty, total_isk, sale_date "
            "FROM consignment_pending_sales WHERE id=?", (row_id,)
        ).fetchone()
        if not pending:
            conn.close()
            return

        p_id, contract_id, type_id, item_name, total_qty, total_isk, sale_date = pending

        # All active consignors for this item type, sorted by priority
        consignors = conn.execute("""
            SELECT id, character_name, consignor_pct, slot_priority,
                   COALESCE(current_qty, 0)
            FROM consignors
            WHERE item_type_id=? AND active=1
            ORDER BY slot_priority, character_name
        """, (type_id,)).fetchall()
        conn.close()

        if not consignors:
            messagebox.showinfo('Split',
                                f'No active consignors found for type_id {type_id}.',
                                parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f'Attribute Sale — {item_name}')
        dlg.geometry('520x420')
        dlg.configure(background='#0a1520')
        dlg.grab_set()

        _lkw = dict(background='#0a1520', foreground='#aaccdd', font=('Segoe UI', 9))
        _ekw = dict(background='#0d1f30', foreground='#e0e8f0', insertbackground='white',
                    relief='flat', font=('Segoe UI', 9))

        tk.Label(dlg, text=f'Attribute: {item_name}', background='#0a1520',
                 foreground='#ff9944', font=('Segoe UI', 11, 'bold')).pack(pady=(10, 2))
        tk.Label(dlg,
                 text=f'Total qty: {total_qty:,}  |  Total ISK: {total_isk:,.2f}  |  Date: {sale_date}',
                 **_lkw).pack(pady=(0, 8))

        # Remaining qty tracker
        remaining_var = tk.StringVar(value=f'Remaining: {total_qty:,}')
        remaining_lbl = tk.Label(dlg, textvariable=remaining_var,
                                 background='#0a1520', foreground='#ffcc44',
                                 font=('Segoe UI', 9, 'bold'))
        remaining_lbl.pack()

        frm = tk.Frame(dlg, background='#0a1520')
        frm.pack(fill='x', padx=20, pady=8)

        qty_vars = []
        for i, (c_id, c_name, c_pct, priority, cur_qty) in enumerate(consignors):
            tk.Label(frm, text=f'P{priority} {c_name} (cur:{cur_qty:,}):',
                     **_lkw).grid(row=i, column=0, sticky='w', pady=3)
            v = tk.StringVar(value='0')
            qty_vars.append((c_id, c_pct, v))
            ent = tk.Entry(frm, textvariable=v, width=12, **_ekw)
            ent.grid(row=i, column=1, sticky='w', padx=(8, 0), pady=3)

            def _upd(*_, _v=v):
                try:
                    used = sum(int(float(x.get()) or 0) for _, _, x in qty_vars)
                    remaining_var.set(f'Remaining: {total_qty - used:,}')
                except Exception:
                    pass

            v.trace_add('write', _upd)

        def _fifo_fill():
            """Auto-fill using priority order up to current_qty."""
            left = total_qty
            for (_, _, v), (_, _, _, _, cur_qty) in zip(qty_vars, consignors):
                alloc = min(left, cur_qty)
                v.set(str(alloc))
                left -= alloc
                if left <= 0:
                    break
            # Put any remainder on the last slot
            if left > 0:
                last_v = qty_vars[-1][2]
                try:
                    last_v.set(str(int(float(last_v.get()) or 0) + left))
                except Exception:
                    last_v.set(str(left))

        ttk.Button(dlg, text='Auto-fill (FIFO by priority)',
                   command=_fifo_fill).pack(pady=(4, 8))

        def _save():
            allocations = []
            total_alloc = 0
            for c_id, c_pct, v in qty_vars:
                try:
                    qty = int(float(v.get()) or 0)
                except Exception:
                    qty = 0
                if qty > 0:
                    allocations.append((c_id, c_pct, qty))
                    total_alloc += qty

            if total_alloc == 0:
                messagebox.showerror('Error', 'Enter at least one non-zero quantity.', parent=dlg)
                return
            if total_alloc != total_qty:
                if not messagebox.askyesno(
                        'Mismatch',
                        f'Allocated {total_alloc:,} but sale total is {total_qty:,}.\n'
                        'Save anyway?', parent=dlg):
                    return

            per_unit = total_isk / total_qty if total_qty else 0

            conn2 = sqlite3.connect(DB_PATH)
            for c_id, c_pct, qty in allocations:
                attributed = round(per_unit * qty, 2)
                their_isk  = round(attributed * c_pct / 100.0, 2)
                my_isk     = round(attributed - their_isk, 2)
                conn2.execute(
                    "INSERT INTO consignment_sales "
                    "(consignor_id, sale_date, quantity, price_per_unit, total_isk, "
                    "consignor_isk, broker_isk, paid, notes, source_contract_id, auto_logged) "
                    "VALUES (?,?,?,?,?,?,?,0,?,?,0)",
                    (c_id, sale_date, qty, round(per_unit, 2), attributed,
                     their_isk, my_isk,
                     f'Manual split | contract {contract_id}', contract_id))
                # Reduce current_qty by attributed units
                conn2.execute(
                    "UPDATE consignors SET current_qty = MAX(0, current_qty - ?) WHERE id=?",
                    (qty, c_id))
            conn2.execute("DELETE FROM consignment_pending_sales WHERE id=?", (p_id,))
            conn2.commit()
            conn2.close()
            dlg.destroy()
            self._consign_load_pending()
            self._consign_load_sales()
            self._consign_load_consignors()

        bf = tk.Frame(dlg, background='#0a1520')
        bf.pack(pady=8)
        ttk.Button(bf, text='Save Attribution', style='Action.TButton',
                   command=_save).pack(side='left', padx=4)
        ttk.Button(bf, text='Cancel', command=dlg.destroy).pack(side='left', padx=4)

    # ===== SLOT PRICING CALCULATOR =====

    def _build_slot_pricing_tab(self):
        """Build the PI Slot Pricing Calculator tab."""
        self._slot_volumes = {}     # type_id -> jita_30d_vol (int)
        self._slot_basis = {}       # str(type_id) -> {'mode': 'jbv'|'split', 'pct': float}
        self._slot_items = []       # list of (type_id, name, tier, avg_buy, avg_sell)
        self._slot_loading = False
        self._slot_params_saved = {}
        self._slot_load_config()

        outer = tk.Frame(self.slot_frame, background='#0a1520')
        outer.pack(fill='both', expand=True, padx=15, pady=10)

        tk.Label(outer, text='PI Slot Pricing Calculator', background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 8))

        # ── Parameters bar ───────────────────────────────────────────────────
        param_card = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        param_card.pack(fill='x', pady=(0, 8))
        pf = tk.Frame(param_card, background='#0a2030')
        pf.pack(fill='x', padx=12, pady=8)

        _lkw = dict(bg='#0a2030', fg='#88d0e8', font=('Segoe UI', 10))
        _ekw = dict(bg='#0d2030', fg='#00ff88', insertbackground='#00ff88', font=('Segoe UI', 10))
        _ukw = dict(bg='#0a2030', fg='#66d9ff', font=('Segoe UI', 10))

        tk.Label(pf, text='Shop Scale:', **_lkw).grid(row=0, column=0, padx=(0, 4), sticky='w')
        self._slot_scale_var = tk.StringVar(value=self._slot_params_saved.get('scale', '0.100'))
        self._slot_scale_entry = tk.Entry(pf, textvariable=self._slot_scale_var, width=7, **_ekw)
        self._slot_scale_entry.grid(row=0, column=1, padx=(0, 2))
        tk.Label(pf, text='% of Jita vol', **_ukw).grid(row=0, column=2, padx=(0, 16), sticky='w')

        tk.Label(pf, text='Commission:', **_lkw).grid(row=0, column=3, padx=(0, 4), sticky='w')
        self._slot_comm_var = tk.StringVar(value=self._slot_params_saved.get('commission', '5.00'))
        tk.Entry(pf, textvariable=self._slot_comm_var, width=7, **_ekw).grid(row=0, column=4, padx=(0, 2))
        tk.Label(pf, text='%', **_ukw).grid(row=0, column=5, padx=(0, 16), sticky='w')

        tk.Label(pf, text='Exclusivity:', **_lkw).grid(row=0, column=6, padx=(0, 4), sticky='w')
        self._slot_prem_var = tk.StringVar(value=self._slot_params_saved.get('premium', '1.25'))
        tk.Entry(pf, textvariable=self._slot_prem_var, width=7, **_ekw).grid(row=0, column=7, padx=(0, 2))
        tk.Label(pf, text='× premium', **_ukw).grid(row=0, column=8, padx=(0, 20), sticky='w')

        self._slot_fetch_btn = ttk.Button(pf, text='\u21ba Fetch Jita Volumes',
                                          command=self._slot_fetch_volumes)
        self._slot_fetch_btn.grid(row=0, column=9, padx=(0, 6))
        ttk.Button(pf, text='Recalculate', command=self._slot_recalculate).grid(row=0, column=10, padx=(0, 6))
        ttk.Button(pf, text='Save Config', style='Save.TButton',
                   command=self._slot_save_config).grid(row=0, column=11, padx=(0, 6))

        self._slot_status_lbl = tk.Label(pf, text='', bg='#0a2030', fg='#ffcc44',
                                         font=('Segoe UI', 9))
        self._slot_status_lbl.grid(row=0, column=12, padx=(8, 0), sticky='w')

        # ── Main treeview ────────────────────────────────────────────────────
        tree_frame = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        tree_frame.pack(fill='both', expand=True, pady=(0, 6))

        cols = ('tier', 'item', 'basis', 'price', 'jita_vol', 'shop_vol', 'shop_rev', 'slot_price')
        self._slot_tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                       selectmode='extended')
        for cid, hd, w, anchor in [
            ('tier',       'Tier',           50,  'c'),
            ('item',       'Item',          210,  'w'),
            ('basis',      'Price Basis',   130,  'c'),
            ('price',      'Price Used',    115,  'e'),
            ('jita_vol',   'Jita 30d Vol',  130,  'e'),
            ('shop_vol',   'Shop Vol/mo',   115,  'e'),
            ('shop_rev',   'Shop Rev/mo',   130,  'e'),
            ('slot_price', 'Slot Price/mo', 120,  'e'),
        ]:
            self._slot_tree.heading(cid, text=hd)
            self._slot_tree.column(cid, width=w, minwidth=40, anchor=anchor)

        self._slot_tree.tag_configure('P1',  foreground='#88d0e8')
        self._slot_tree.tag_configure('P2',  foreground='#66cc88')
        self._slot_tree.tag_configure('P3',  foreground='#ffcc44')
        self._slot_tree.tag_configure('P4',  foreground='#ff8866')
        self._slot_tree.tag_configure('sep', foreground='#334455', background='#0a1828')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._slot_tree.yview)
        self._slot_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self._slot_tree.pack(fill='both', expand=True)
        self._slot_tree.bind('<<TreeviewSelect>>', self._slot_on_select)

        # ── Bottom: basis config (left) + math breakdown (right) ─────────────
        bottom = tk.Frame(outer, background='#0a1520')
        bottom.pack(fill='x', pady=(0, 6))

        # Left: per-item basis configuration
        config_card = tk.Frame(bottom, background='#0a2030', relief='solid', bd=1)
        config_card.pack(side='left', fill='y', padx=(0, 8))

        tk.Label(config_card, text='Price Basis — Selected Item', bg='#0a2030',
                 fg='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=10, pady=(8, 2))
        self._slot_selected_lbl = tk.Label(config_card, text='— select an item above —',
                                           bg='#0a2030', fg='#88d0e8',
                                           font=('Segoe UI', 9, 'italic'))
        self._slot_selected_lbl.pack(anchor='w', padx=10, pady=(0, 8))

        self._slot_basis_var = tk.StringVar(value='jbv')
        tk.Radiobutton(config_card, text='JBV  (Jita Buy Value)',
                       variable=self._slot_basis_var, value='jbv',
                       bg='#0a2030', fg='#88d0e8', selectcolor='#0a3040',
                       activebackground='#0a2030', activeforeground='#00ff88',
                       command=self._slot_basis_changed).pack(anchor='w', padx=10)

        jbv_pct_row = tk.Frame(config_card, background='#0a2030')
        jbv_pct_row.pack(anchor='w', padx=10, pady=(4, 0))
        tk.Radiobutton(jbv_pct_row, text='% of JBV:',
                       variable=self._slot_basis_var, value='jbv_pct',
                       bg='#0a2030', fg='#88d0e8', selectcolor='#0a3040',
                       activebackground='#0a2030', activeforeground='#00ff88',
                       command=self._slot_basis_changed).pack(side='left')
        self._slot_jbv_pct_var = tk.StringVar(value='95')
        self._slot_jbv_pct_entry = tk.Entry(jbv_pct_row, textvariable=self._slot_jbv_pct_var,
                                            width=6, bg='#0d2030', fg='#00ff88',
                                            insertbackground='#00ff88',
                                            font=('Segoe UI', 10), state='disabled')
        self._slot_jbv_pct_entry.pack(side='left', padx=(6, 2))
        tk.Label(jbv_pct_row, text='%', bg='#0a2030', fg='#66d9ff',
                 font=('Segoe UI', 10)).pack(side='left')

        split_row = tk.Frame(config_card, background='#0a2030')
        split_row.pack(anchor='w', padx=10, pady=(4, 0))
        tk.Radiobutton(split_row, text='% of Jita Split:',
                       variable=self._slot_basis_var, value='split',
                       bg='#0a2030', fg='#88d0e8', selectcolor='#0a3040',
                       activebackground='#0a2030', activeforeground='#00ff88',
                       command=self._slot_basis_changed).pack(side='left')
        self._slot_split_pct_var = tk.StringVar(value='95')
        self._slot_split_entry = tk.Entry(split_row, textvariable=self._slot_split_pct_var,
                                          width=6, bg='#0d2030', fg='#00ff88',
                                          insertbackground='#00ff88',
                                          font=('Segoe UI', 10), state='disabled')
        self._slot_split_entry.pack(side='left', padx=(6, 2))
        tk.Label(split_row, text='%', bg='#0a2030', fg='#66d9ff',
                 font=('Segoe UI', 10)).pack(side='left')

        ttk.Button(config_card, text='Apply to Selected',
                   command=self._slot_apply_basis).pack(anchor='w', padx=10, pady=(10, 4))

        # Per-item volume mode selection
        tk.Frame(config_card, bg='#1a3040', height=1).pack(fill='x', padx=10, pady=(4, 6))
        tk.Label(config_card, text='Volume Mode (this item):', bg='#0a2030',
                 fg='#66d9ff', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=10)
        self._slot_item_vol_mode_var = tk.StringVar(value='jita')
        tk.Radiobutton(config_card, text='Jita 30d Vol \u00d7 Scale',
                       variable=self._slot_item_vol_mode_var, value='jita',
                       bg='#0a2030', fg='#88d0e8', selectcolor='#0a3040',
                       activebackground='#0a2030', activeforeground='#00ff88',
                       command=self._slot_item_vol_mode_changed).pack(anchor='w', padx=10)
        tk.Radiobutton(config_card, text='Expected Units/mo',
                       variable=self._slot_item_vol_mode_var, value='expected',
                       bg='#0a2030', fg='#88d0e8', selectcolor='#0a3040',
                       activebackground='#0a2030', activeforeground='#00ff88',
                       command=self._slot_item_vol_mode_changed).pack(anchor='w', padx=10)
        self._slot_units_var   = tk.StringVar(value='0')
        self._slot_units_entry = tk.Entry(config_card, textvariable=self._slot_units_var,
                                          width=14, bg='#0d2030', fg='#00ff88',
                                          insertbackground='#00ff88',
                                          font=('Segoe UI', 10), state='disabled')
        self._slot_units_entry.pack(anchor='w', padx=24, pady=(3, 0))
        tk.Label(config_card, text='(units lessee produces/month)',
                 bg='#0a2030', fg='#445566', font=('Segoe UI', 9)).pack(anchor='w', padx=24, pady=(0, 10))

        # Right: math breakdown
        math_card = tk.Frame(bottom, background='#0a2030', relief='solid', bd=1)
        math_card.pack(side='left', fill='both', expand=True)

        tk.Label(math_card, text='Formula Breakdown', bg='#0a2030',
                 fg='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
        self._slot_math_text = tk.Text(math_card, height=9, bg='#060f18', fg='#88d0e8',
                                       font=('Consolas', 9), state='disabled', relief='flat',
                                       borderwidth=0, padx=10, pady=6)
        self._slot_math_text.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self._slot_math_text.tag_configure('header',  foreground='#00d9ff')
        self._slot_math_text.tag_configure('result',  foreground='#00ff88', font=('Consolas', 9, 'bold'))
        self._slot_math_text.tag_configure('dim',     foreground='#445566')
        self._slot_math_text.tag_configure('normal',  foreground='#88d0e8')

        # ── Summary footer ────────────────────────────────────────────────────
        summary_card = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        summary_card.pack(fill='x')
        sf = tk.Frame(summary_card, background='#0a2030')
        sf.pack(fill='x', padx=12, pady=6)

        tk.Label(sf, text='Monthly Totals (all slots filled):',
                 bg='#0a2030', fg='#66d9ff', font=('Segoe UI', 10, 'bold')).grid(
                 row=0, column=0, padx=(0, 20), sticky='w')

        self._slot_summary_labels = {}
        tier_colors = {'P1': '#88d0e8', 'P2': '#66cc88', 'P3': '#ffcc44',
                       'P4': '#ff8866', 'TOTAL': '#00ff88'}
        for col_i, tier in enumerate(['P1', 'P2', 'P3', 'P4', 'TOTAL'], start=1):
            color = tier_colors[tier]
            tk.Label(sf, text=f'{tier}:', bg='#0a2030', fg=color,
                     font=('Segoe UI', 9, 'bold')).grid(row=0, column=col_i * 2 - 1,
                                                         padx=(0, 4), sticky='e')
            lbl = tk.Label(sf, text='—', bg='#0a2030', fg=color, font=('Segoe UI', 9))
            lbl.grid(row=0, column=col_i * 2, padx=(0, 24), sticky='w')
            self._slot_summary_labels[tier] = lbl

        # Load items and populate
        self._slot_load_items()

    def _slot_load_config(self):
        """Load saved basis config and global params from site_config."""
        try:
            conn = sqlite3.connect(DB_PATH)
            row_b = conn.execute(
                "SELECT value FROM site_config WHERE key='slot_pricing_basis'").fetchone()
            row_p = conn.execute(
                "SELECT value FROM site_config WHERE key='slot_pricing_params'").fetchone()
            conn.close()
            self._slot_basis = json.loads(row_b[0]) if row_b else {}
            self._slot_params_saved = json.loads(row_p[0]) if row_p else {}
        except Exception:
            self._slot_basis = {}
            self._slot_params_saved = {}

    def _slot_save_config(self):
        """Save per-item basis config and global params to site_config."""
        try:
            params = {
                'scale':      self._slot_scale_var.get(),
                'commission': self._slot_comm_var.get(),
                'premium':    self._slot_prem_var.get(),
            }
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?,?)",
                         ('slot_pricing_basis',  json.dumps(self._slot_basis)))
            conn.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?,?)",
                         ('slot_pricing_params', json.dumps(params)))
            conn.commit()
            conn.close()
            self._slot_status_lbl.configure(text='Config saved \u2713', fg='#00ff88')
            self.root.after(3000, lambda: self._slot_status_lbl.configure(text=''))
        except Exception as e:
            self._slot_status_lbl.configure(text=f'Save error: {e}', fg='#ff6666')

    def _slot_load_items(self):
        """Load PI items and their current prices from the DB."""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("""
                SELECT tmi.type_id, tmi.type_name, it.market_group_id,
                       ROUND(AVG(mps.best_buy),  0) AS avg_buy,
                       ROUND(AVG(mps.best_sell), 0) AS avg_sell
                FROM tracked_market_items tmi
                JOIN inv_types it ON tmi.type_id = it.type_id
                LEFT JOIN market_price_snapshots mps
                    ON tmi.type_id = mps.type_id
                    AND mps.timestamp >= datetime('now', '-7 days')
                WHERE tmi.category = 'pi_materials'
                AND it.market_group_id IN (1334, 1335, 1336, 1337)
                GROUP BY tmi.type_id, tmi.type_name, it.market_group_id
                ORDER BY it.market_group_id, tmi.type_name
            """).fetchall()
            conn.close()
            tier_map = {1334: 'P1', 1335: 'P2', 1336: 'P3', 1337: 'P4'}
            self._slot_items = [
                (r[0], r[1], tier_map[r[2]], r[3] or 0.0, r[4] or 0.0)
                for r in rows
            ]
        except Exception:
            self._slot_items = []
        self._slot_recalculate()

    def _slot_get_params(self):
        """Return (scale_fraction, commission_fraction, premium_multiplier)."""
        try:    scale = float(self._slot_scale_var.get()) / 100.0
        except Exception: scale = 0.001
        try:    comm  = float(self._slot_comm_var.get()) / 100.0
        except Exception: comm  = 0.05
        try:    prem  = float(self._slot_prem_var.get())
        except Exception: prem  = 1.25
        return scale, comm, prem

    def _slot_get_price(self, type_id, avg_buy, avg_sell):
        """Return (price, basis_label) for an item based on its stored config."""
        cfg  = self._slot_basis.get(str(type_id), {'mode': 'jbv', 'pct': 95.0})
        mode = cfg.get('mode', 'jbv')
        if mode == 'jbv':
            return avg_buy, 'JBV'
        pct = cfg.get('pct', 95.0)
        if mode == 'jbv_pct':
            return avg_buy * pct / 100.0, f'{pct:.0f}% JBV'
        split = (avg_buy + avg_sell) / 2.0 if avg_buy and avg_sell else (avg_buy or avg_sell)
        return split * pct / 100.0, f'{pct:.0f}% Split'

    @staticmethod
    def _slot_fmt_vol(v):
        if v <= 0:   return '—'
        if v >= 1e9: return f'{v/1e9:.1f}B'
        if v >= 1e6: return f'{v/1e6:.1f}M'
        return f'{v/1e3:.0f}K'

    @staticmethod
    def _slot_fmt_isk(v):
        if v <= 0:   return '—'
        if v >= 1e9: return f'{v/1e9:.2f}B'
        if v >= 1e6: return f'{v/1e6:.1f}M'
        return f'{v/1e3:.0f}K'

    def _slot_recalculate(self):
        """Rebuild the treeview with current parameters and per-item basis."""
        scale, comm, prem = self._slot_get_params()
        self._slot_tree.delete(*self._slot_tree.get_children())
        tier_totals = {'P1': 0.0, 'P2': 0.0, 'P3': 0.0, 'P4': 0.0}
        cur_tier = None

        for type_id, name, tier, avg_buy, avg_sell in self._slot_items:
            if tier != cur_tier:
                cur_tier = tier
                self._slot_tree.insert('', 'end', iid=f'sep_{tier}', tags=('sep',),
                                       values=(f'  \u2500\u2500 {tier} \u2500\u2500',
                                               '', '', '', '', '', '', ''))

            jita_vol = self._slot_volumes.get(type_id, 0)
            price, basis_lbl = self._slot_get_price(type_id, avg_buy, avg_sell)
            cfg      = self._slot_basis.get(str(type_id), {})
            item_vol_mode = cfg.get('vol_mode', 'jita')
            if item_vol_mode == 'expected':
                shop_vol  = float(cfg.get('units', 0))
                vol_label = f'{basis_lbl} · exp'
            else:
                shop_vol  = jita_vol * scale
                vol_label = basis_lbl
            mo_rev   = shop_vol * price
            slot_p   = mo_rev * comm * prem
            tier_totals[tier] += slot_p

            self._slot_tree.insert('', 'end', iid=str(type_id), tags=(tier,), values=(
                tier, name, vol_label,
                f'{price:,.0f}' if price > 0 else '—',
                self._slot_fmt_vol(jita_vol),
                f'{shop_vol:,.0f}' if shop_vol > 0 else '—',
                self._slot_fmt_isk(mo_rev),
                self._slot_fmt_isk(slot_p),
            ))

        # Update summary labels
        grand = sum(tier_totals.values())
        for tier, lbl in self._slot_summary_labels.items():
            if tier == 'TOTAL':
                val = f'{grand/1e6:.1f}M ISK' if grand >= 1e6 else f'{grand/1e3:.0f}K ISK' if grand > 0 else '—'
            else:
                v = tier_totals.get(tier, 0.0)
                val = f'{v/1e6:.1f}M' if v >= 1e6 else f'{v/1e3:.0f}K' if v > 0 else '—'
            lbl.configure(text=val)

    def _slot_on_select(self, _event=None):
        """Update basis controls and math breakdown for the selected item(s)."""
        sel = self._slot_tree.selection()
        # Filter out separator rows
        item_sel = [s for s in sel if not s.startswith('sep_')]
        if not item_sel:
            return

        # Multiple items selected — show count and load first item's config into controls
        if len(item_sel) > 1:
            self._slot_selected_lbl.configure(text=f'{len(item_sel)} items selected')
            # Load basis config from the first real item so controls are ready to bulk-apply
            try:
                first_id = int(item_sel[0])
                cfg = self._slot_basis.get(str(first_id), {'mode': 'jbv', 'pct': 95.0})
                mode = cfg.get('mode', 'jbv')
                pct  = str(cfg.get('pct', 95.0))
                self._slot_basis_var.set(mode)
                if mode == 'jbv_pct':
                    self._slot_jbv_pct_var.set(pct)
                else:
                    self._slot_split_pct_var.set(pct)
                self._slot_basis_changed()
            except ValueError:
                pass
            # Show a summary in the math panel
            self._slot_math_text.configure(state='normal')
            self._slot_math_text.delete('1.0', 'end')
            self._slot_math_text.insert('end',
                f'{len(item_sel)} items selected\n\n'
                'Set the price basis below and click\n'
                '"Apply to Selected" to update all\n'
                'highlighted items at once.', 'header')
            self._slot_math_text.configure(state='disabled')
            return

        try:
            type_id = int(item_sel[0])
        except ValueError:
            return

        item = next((i for i in self._slot_items if i[0] == type_id), None)
        if not item:
            return
        _, name, tier, avg_buy, avg_sell = item

        # Update basis controls to reflect this item's stored config
        cfg  = self._slot_basis.get(str(type_id), {'mode': 'jbv', 'pct': 95.0})
        mode = cfg.get('mode', 'jbv')
        pct  = str(cfg.get('pct', 95.0))
        self._slot_basis_var.set(mode)
        if mode == 'jbv_pct':
            self._slot_jbv_pct_var.set(pct)
        else:
            self._slot_split_pct_var.set(pct)
        item_vol_mode = cfg.get('vol_mode', 'jita')
        self._slot_item_vol_mode_var.set(item_vol_mode)
        self._slot_units_var.set(str(cfg.get('units', 0)))
        self._slot_basis_changed()
        self._slot_item_vol_mode_changed()
        self._slot_selected_lbl.configure(text=f'{name}  ({tier})')

        # Compute values for breakdown
        scale, comm, prem = self._slot_get_params()
        jita_vol  = self._slot_volumes.get(type_id, 0)
        price, basis_lbl = self._slot_get_price(type_id, avg_buy, avg_sell)
        exp_units = float(cfg.get('units', 0))
        shop_vol  = exp_units if item_vol_mode == 'expected' else jita_vol * scale
        mo_rev    = shop_vol * price
        slot_p    = mo_rev * comm * prem
        split_mid = (avg_buy + avg_sell) / 2.0 if avg_buy and avg_sell else 0.0

        try:    scale_pct = float(self._slot_scale_var.get())
        except Exception: scale_pct = 0.1
        try:    comm_pct  = float(self._slot_comm_var.get())
        except Exception: comm_pct  = 5.0
        try:    prem_val  = float(self._slot_prem_var.get())
        except Exception: prem_val  = 1.25

        sep = '\u2500' * 58
        lines = [
            (f'{name}  \u2014  Slot Price Breakdown\n', 'header'),
            (sep + '\n', 'dim'),
            (f'  JBV (avg 7d):          {avg_buy:>15,.0f} ISK\n', 'normal'),
            (f'  JSV (avg 7d):          {avg_sell:>15,.0f} ISK\n', 'normal'),
            (f'  Jita Split mid-point:  {split_mid:>15,.0f} ISK\n', 'normal'),
            (f'  Price Used ({basis_lbl:<12s}): {price:>15,.0f} ISK\n', 'normal'),
            (sep + '\n', 'dim'),
        ]
        if item_vol_mode == 'expected':
            lines += [
                (f'  Expected Units/mo:     {exp_units:>15,.0f} units\n', 'normal'),
                (f'  \u00d7 Price Used:           {price:>15,.0f} ISK\n', 'normal'),
            ]
        else:
            lines += [
                (f'  Jita 30d Volume:       {jita_vol:>15,.0f} units\n', 'normal'),
                (f'  \u00d7 Shop Scale ({scale_pct:.3f}%):    {shop_vol:>15,.0f} units/mo\n', 'normal'),
                (f'  \u00d7 Price Used:           {price:>15,.0f} ISK\n', 'normal'),
            ]
        lines += [
            (sep + '\n', 'dim'),
            (f'  Monthly Shop Revenue:  {mo_rev:>15,.0f} ISK\n', 'normal'),
            (f'  \u00d7 Commission ({comm_pct:.1f}%):     {mo_rev * comm:>15,.0f} ISK\n', 'normal'),
            (f'  \u00d7 Exclusivity ({prem_val:.2f}\u00d7):   {slot_p:>15,.0f} ISK\n', 'normal'),
            (sep + '\n', 'dim'),
        ]
        if slot_p >= 1e6:
            slot_str = f'{slot_p/1e6:.2f}M ISK/mo'
        elif slot_p > 0:
            slot_str = f'{slot_p/1e3:.0f}K ISK/mo'
        else:
            slot_str = '— (fetch Jita volumes first)'
        lines.append((f'  Suggested Slot Price:  {slot_str:>22}\n', 'result'))

        self._slot_math_text.configure(state='normal')
        self._slot_math_text.delete('1.0', 'end')
        for text, tag in lines:
            self._slot_math_text.insert('end', text, tag)
        self._slot_math_text.configure(state='disabled')

    def _slot_item_vol_mode_changed(self):
        """Enable/disable the Expected Units entry based on the per-item vol mode radio."""
        mode = self._slot_item_vol_mode_var.get()
        self._slot_units_entry.configure(state='normal' if mode == 'expected' else 'disabled')

    def _slot_basis_changed(self):
        """Enable/disable the pct entries based on radio selection."""
        mode = self._slot_basis_var.get()
        self._slot_jbv_pct_entry.configure(state='normal' if mode == 'jbv_pct' else 'disabled')
        self._slot_split_entry.configure(state='normal' if mode == 'split' else 'disabled')

    def _slot_apply_basis(self):
        """Apply basis setting to all selected items and recalculate."""
        sel = self._slot_tree.selection()
        item_sel = [s for s in sel if not s.startswith('sep_')]
        if not item_sel:
            return
        mode = self._slot_basis_var.get()
        try:
            if mode == 'jbv_pct':
                pct = float(self._slot_jbv_pct_var.get())
            else:
                pct = float(self._slot_split_pct_var.get())
        except Exception:
            pct = 95.0

        try:    units = int(float(self._slot_units_var.get()))
        except Exception: units = 0
        item_vol_mode = self._slot_item_vol_mode_var.get()

        for iid in item_sel:
            try:
                self._slot_basis[iid] = {
                    'mode': mode, 'pct': pct,
                    'units': units, 'vol_mode': item_vol_mode,
                }
            except Exception:
                pass

        self._slot_recalculate()
        # Restore selection after tree rebuild
        valid = [iid for iid in item_sel if self._slot_tree.exists(iid)]
        if valid:
            self._slot_tree.selection_set(valid)
            self._slot_on_select()

    def _slot_fetch_volumes(self):
        """Fetch Jita 30-day volumes from ESI in a background thread."""
        if self._slot_loading or not self._slot_items:
            return
        self._slot_loading = True
        self._slot_fetch_btn.configure(state='disabled')
        self._slot_status_lbl.configure(text='Fetching from ESI\u2026', fg='#ffcc44')

        import threading
        import requests
        import time as _time
        from datetime import timedelta

        items_snap = list(self._slot_items)
        FORGE  = 10000002
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date()

        def _fetch():
            volumes = {}
            for i, (type_id, name, tier, _, _) in enumerate(items_snap):
                try:
                    url = (f'https://esi.evetech.net/latest/markets/{FORGE}'
                           f'/history/?type_id={type_id}')
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        volumes[type_id] = sum(
                            d['volume'] for d in r.json()
                            if d['date'] >= str(cutoff)
                        )
                    else:
                        volumes[type_id] = 0
                except Exception:
                    volumes[type_id] = 0
                _time.sleep(0.1)
                self.root.after(0, lambda i=i: self._slot_status_lbl.configure(
                    text=f'Fetching\u2026 {i + 1}/{len(items_snap)}', fg='#ffcc44'))

            def _done():
                self._slot_volumes.update(volumes)
                self._slot_loading = False
                self._slot_fetch_btn.configure(state='normal')
                self._slot_status_lbl.configure(
                    text=f'Fetched {len(volumes)} items \u2713', fg='#00ff88')
                self._slot_recalculate()
            self.root.after(0, _done)

        threading.Thread(target=_fetch, daemon=True).start()

    # ===== SLOT MANAGER =====

    _SLOTMGR_CONFIG_PATH = os.path.join(PROJECT_DIR, 'slots_config.json')

    _SLOTMGR_CAT_ORDER = [
        'minerals', 'ice_products', 'moon_materials',
        'pi_materials', 'salvaged_materials',
    ]
    _SLOTMGR_CAT_LABELS = {
        'minerals':           'Minerals',
        'ice_products':       'Ice Products',
        'moon_materials':     'Moon Materials',
        'pi_materials':       'Planetary Materials',
        'salvaged_materials': 'Salvaged Materials',
    }

    def _build_slot_manager_tab(self):
        """Build the Slot Manager tab."""
        # State: type_id -> {'in_program': bool, 'status': 'open'|'closed', 'lessee': str}
        self._sm_state   = {}   # populated by _sm_load
        self._sm_all_ids = []   # ordered list of type_ids from DB

        outer = tk.Frame(self.slotmgr_frame, background='#0a1520')
        outer.pack(fill='both', expand=True, padx=15, pady=10)

        tk.Label(outer, text='Slot Manager', background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 13, 'bold')).pack(
                 anchor='w', pady=(0, 8))

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        toolbar.pack(fill='x', pady=(0, 8))
        tf = tk.Frame(toolbar, background='#0a2030')
        tf.pack(fill='x', padx=10, pady=6)

        # Filter controls
        tk.Label(tf, text='Category:', bg='#0a2030', fg='#88d0e8',
                 font=('Segoe UI', 10)).pack(side='left', padx=(0, 4))
        self._sm_cat_var = tk.StringVar(value='All')
        cat_options = ['All'] + [self._SLOTMGR_CAT_LABELS[c]
                                  for c in self._SLOTMGR_CAT_ORDER]
        cat_menu = ttk.Combobox(tf, textvariable=self._sm_cat_var,
                                values=cat_options, state='readonly', width=20)
        cat_menu.pack(side='left', padx=(0, 16))
        cat_menu.bind('<<ComboboxSelected>>', lambda _: self._sm_refresh_tree())

        tk.Label(tf, text='Show:', bg='#0a2030', fg='#88d0e8',
                 font=('Segoe UI', 10)).pack(side='left', padx=(0, 4))
        self._sm_show_var = tk.StringVar(value='All')
        show_menu = ttk.Combobox(tf, textvariable=self._sm_show_var,
                                 values=['All', 'In Program', 'Not in Program'],
                                 state='readonly', width=16)
        show_menu.pack(side='left', padx=(0, 20))
        show_menu.bind('<<ComboboxSelected>>', lambda _: self._sm_refresh_tree())

        # Action buttons
        ttk.Button(tf, text='Include Selected',
                   command=lambda: self._sm_set_program(True)).pack(side='left', padx=(0, 4))
        ttk.Button(tf, text='Exclude Selected',
                   command=lambda: self._sm_set_program(False)).pack(side='left', padx=(0, 16))

        ttk.Button(tf, text='Save Config', style='Save.TButton',
                   command=self._sm_save).pack(side='left', padx=(0, 6))
        ttk.Button(tf, text='Generate Image', style='Deploy.TButton',
                   command=self._sm_generate).pack(side='left', padx=(0, 6))

        self._sm_status_lbl = tk.Label(tf, text='', bg='#0a2030', fg='#ffcc44',
                                       font=('Segoe UI', 9))
        self._sm_status_lbl.pack(side='left', padx=(10, 0))

        # Counter labels (right side)
        self._sm_count_lbl = tk.Label(tf, text='', bg='#0a2030', fg='#66d9ff',
                                      font=('Segoe UI', 9))
        self._sm_count_lbl.pack(side='right')

        # ── Treeview ─────────────────────────────────────────────────────────
        tree_frame = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        tree_frame.pack(fill='both', expand=True, pady=(0, 6))

        cols = ('in_prog', 'category', 'sub', 'name', 'status', 'lessee', 'price')
        self._sm_tree = ttk.Treeview(tree_frame, columns=cols, show='headings',
                                     selectmode='extended')
        for cid, hd, w, anchor in [
            ('in_prog',  '\u2713 Slot?',    60,  'c'),
            ('category', 'Category',       145,  'c'),
            ('sub',      'Tier / Grade',   110,  'c'),
            ('name',     'Item Name',      250,  'w'),
            ('status',   'Status',          80,  'c'),
            ('lessee',   'Lessee',         190,  'w'),
            ('price',    'Price / mo',     110,  'e'),
        ]:
            self._sm_tree.heading(cid, text=hd)
            self._sm_tree.column(cid, width=w, minwidth=30, anchor=anchor)

        self._sm_tree.tag_configure('in_open',   foreground='#00ff88')
        self._sm_tree.tag_configure('in_closed', foreground='#ffcc44')
        self._sm_tree.tag_configure('out',       foreground='#445566')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self._sm_tree.yview)
        self._sm_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self._sm_tree.pack(fill='both', expand=True)
        self._sm_tree.bind('<<TreeviewSelect>>', self._sm_on_select)

        # ── Edit panel (bottom) ───────────────────────────────────────────────
        edit_card = tk.Frame(outer, background='#0a2030', relief='solid', bd=1)
        edit_card.pack(fill='x')
        ef = tk.Frame(edit_card, background='#0a2030')
        ef.pack(fill='x', padx=12, pady=8)

        self._sm_sel_lbl = tk.Label(ef, text='— select item(s) above —',
                                    bg='#0a2030', fg='#88d0e8',
                                    font=('Segoe UI', 9, 'italic'))
        self._sm_sel_lbl.grid(row=0, column=0, columnspan=9, sticky='w', pady=(0, 6))

        tk.Label(ef, text='Status:', bg='#0a2030', fg='#88d0e8',
                 font=('Segoe UI', 10)).grid(row=1, column=0, padx=(0, 6), sticky='w')
        self._sm_status_var = tk.StringVar(value='open')
        tk.Radiobutton(ef, text='Open', variable=self._sm_status_var,
                       value='open', bg='#0a2030', fg='#00ff88',
                       selectcolor='#0a3040', activebackground='#0a2030',
                       activeforeground='#00ff88',
                       command=self._sm_status_changed).grid(
                       row=1, column=1, padx=(0, 8), sticky='w')
        tk.Radiobutton(ef, text='Closed', variable=self._sm_status_var,
                       value='closed', bg='#0a2030', fg='#ffcc44',
                       selectcolor='#0a3040', activebackground='#0a2030',
                       activeforeground='#ffcc44',
                       command=self._sm_status_changed).grid(
                       row=1, column=2, padx=(0, 20), sticky='w')

        tk.Label(ef, text='Lessee name:', bg='#0a2030', fg='#88d0e8',
                 font=('Segoe UI', 10)).grid(row=1, column=3, padx=(0, 6), sticky='w')
        self._sm_lessee_var = tk.StringVar()
        self._sm_lessee_entry = tk.Entry(ef, textvariable=self._sm_lessee_var,
                                         width=22, bg='#0d2030', fg='#ffcc44',
                                         insertbackground='#ffcc44',
                                         font=('Segoe UI', 10), state='disabled')
        self._sm_lessee_entry.grid(row=1, column=4, padx=(0, 16), sticky='w')

        tk.Label(ef, text='Price / mo (ISK):', bg='#0a2030', fg='#88d0e8',
                 font=('Segoe UI', 10)).grid(row=1, column=5, padx=(0, 6), sticky='w')
        self._sm_price_var = tk.StringVar()
        tk.Entry(ef, textvariable=self._sm_price_var, width=14,
                 bg='#0d2030', fg='#66d9ff', insertbackground='#66d9ff',
                 font=('Segoe UI', 10)).grid(row=1, column=6, padx=(0, 8), sticky='w')
        ttk.Button(ef, text='Pull from Calculator',
                   command=self._sm_pull_calc_prices).grid(row=1, column=7, padx=(0, 10))

        ttk.Button(ef, text='Apply to Selected',
                   command=self._sm_apply_edit).grid(row=1, column=8, padx=(0, 0))

        # Load data
        self._sm_load_all()

    # ── Slot Manager helpers ──────────────────────────────────────────────────

    def _sm_load_all(self):
        """Load all market items from DB, then overlay slots_config.json."""
        # Fetch every non-ore item + metadata from DB
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute('''
            SELECT tmi.type_id, tmi.category, it.type_name,
                   tmi.display_order, it.market_group_id
            FROM tracked_market_items tmi
            JOIN inv_types it ON tmi.type_id = it.type_id
            WHERE tmi.category NOT IN ("standard_ore","ice_ore","moon_ore")
            ORDER BY tmi.category, tmi.display_order
        ''').fetchall()
        conn.close()

        PI_TIER  = {1334:'P1', 1335:'P2', 1336:'P3', 1337:'P4'}

        def _sal_grade(d):
            if d is None: return ''
            if d <= 9:    return 'Common'
            if d <= 21:   return 'Uncommon'
            if d <= 32:   return 'Rare'
            if d <= 42:   return 'Very Rare'
            return 'Rogue Drone'

        self._sm_meta = {}   # type_id -> (category, name, sub_label)
        self._sm_all_ids = []
        for type_id, cat, name, disp, grp in rows:
            if cat == 'pi_materials':
                sub = PI_TIER.get(grp, 'P2')
            elif cat == 'salvaged_materials':
                sub = _sal_grade(disp)
            else:
                sub = ''
            self._sm_meta[type_id] = (cat, name, sub)
            self._sm_all_ids.append(type_id)
            # Default state: not in program
            self._sm_state.setdefault(type_id, {
                'in_program': False,
                'status':     'open',
                'lessee':     '',
                'price':      '',
            })

        # Overlay saved config
        if os.path.exists(self._SLOTMGR_CONFIG_PATH):
            try:
                with open(self._SLOTMGR_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                # Mark items that are in the config as in_program
                in_config = {e['type_id'] for e in cfg}
                for tid in self._sm_all_ids:
                    self._sm_state[tid]['in_program'] = tid in in_config
                for entry in cfg:
                    tid = entry.get('type_id')
                    if tid in self._sm_state:
                        self._sm_state[tid]['status'] = entry.get('status', 'open')
                        self._sm_state[tid]['lessee'] = entry.get('lessee') or ''
                        self._sm_state[tid]['price']  = entry.get('price')  or ''
            except Exception:
                pass

        self._sm_refresh_tree()

    def _sm_refresh_tree(self):
        """Rebuild the treeview to match current filter settings."""
        cat_filter  = self._sm_cat_var.get()
        show_filter = self._sm_show_var.get()

        # Reverse label -> key
        label_to_key = {v: k for k, v in self._SLOTMGR_CAT_LABELS.items()}

        self._sm_tree.delete(*self._sm_tree.get_children())

        in_prog_count = out_count = 0
        for type_id in self._sm_all_ids:
            cat, name, sub = self._sm_meta[type_id]
            state = self._sm_state[type_id]

            # Category filter
            if cat_filter != 'All':
                if label_to_key.get(cat_filter) != cat:
                    continue

            # Show filter
            if show_filter == 'In Program' and not state['in_program']:
                continue
            if show_filter == 'Not in Program' and state['in_program']:
                continue

            in_prog  = state['in_program']
            status   = state['status']
            lessee   = state['lessee']
            in_prog_count += 1 if in_prog else 0
            out_count     += 0 if in_prog else 1

            tag = ('in_open'   if in_prog and status == 'open'   else
                   'in_closed' if in_prog and status == 'closed' else
                   'out')

            price     = state['price']
            price_disp = self._sm_fmt_price(price) if in_prog and price else ('—' if not in_prog else '')

            self._sm_tree.insert('', 'end', iid=str(type_id), tags=(tag,), values=(
                '\u2713' if in_prog else '',
                self._SLOTMGR_CAT_LABELS.get(cat, cat),
                sub,
                name,
                status.capitalize() if in_prog else '—',
                lessee if in_prog and lessee else ('—' if not in_prog else ''),
                price_disp,
            ))

        total = len(self._sm_all_ids)
        self._sm_count_lbl.configure(
            text=f'{in_prog_count} in program  ·  {out_count} excluded  ·  {total} total items')

    def _sm_on_select(self, _event=None):
        """Update the edit panel when selection changes."""
        sel = self._sm_tree.selection()
        if not sel:
            return
        if len(sel) == 1:
            tid   = int(sel[0])
            state = self._sm_state[tid]
            self._sm_sel_lbl.configure(text=self._sm_meta[tid][1])
            self._sm_status_var.set(state['status'])
            self._sm_lessee_var.set(state['lessee'])
            self._sm_price_var.set(state['price'])
        else:
            self._sm_sel_lbl.configure(text=f'{len(sel)} items selected')
        self._sm_status_changed()

    def _sm_status_changed(self):
        """Enable lessee entry only when status is closed."""
        if self._sm_status_var.get() == 'closed':
            self._sm_lessee_entry.configure(state='normal')
        else:
            self._sm_lessee_entry.configure(state='disabled')

    def _sm_set_program(self, include: bool):
        """Include or exclude all selected items from the slot program."""
        sel = self._sm_tree.selection()
        if not sel:
            return
        for iid in sel:
            self._sm_state[int(iid)]['in_program'] = include
        self._sm_refresh_tree()
        # Restore selection
        valid = [i for i in sel if self._sm_tree.exists(i)]
        if valid:
            self._sm_tree.selection_set(valid)

    def _sm_apply_edit(self):
        """Apply status/lessee to all selected in-program items."""
        sel = self._sm_tree.selection()
        if not sel:
            return
        status = self._sm_status_var.get()
        lessee = self._sm_lessee_var.get().strip() if status == 'closed' else ''
        price  = self._sm_price_var.get().strip()
        for iid in sel:
            tid = int(iid)
            self._sm_state[tid]['status'] = status
            self._sm_state[tid]['lessee'] = lessee
            self._sm_state[tid]['price']  = price
            # Auto-include if not already
            self._sm_state[tid]['in_program'] = True
        self._sm_refresh_tree()
        valid = [i for i in sel if self._sm_tree.exists(i)]
        if valid:
            self._sm_tree.selection_set(valid)

    @staticmethod
    def _sm_fmt_price(raw):
        """Format a raw price value (number or string) for display."""
        try:
            v = float(str(raw).replace(',', '').replace('M', 'e6')
                              .replace('K', 'e3').replace('B', 'e9'))
            if v >= 1e9: return f'{v/1e9:.2f}B/mo'
            if v >= 1e6: return f'{v/1e6:.1f}M/mo'
            if v >= 1e3: return f'{v/1e3:.0f}K/mo'
            return f'{int(v):,}/mo'
        except Exception:
            return str(raw)

    def _sm_pull_calc_prices(self):
        """Populate prices from the Slot Pricing calculator for matching items."""
        if not hasattr(self, '_slot_items') or not self._slot_volumes:
            self._sm_status_lbl.configure(
                text='Run the Slot Pricing tab and fetch Jita volumes first.',
                fg='#ff6666')
            self.root.after(4000, lambda: self._sm_status_lbl.configure(text=''))
            return

        scale, comm, prem = self._slot_get_params()
        updated = 0
        for type_id, name, tier, avg_buy, avg_sell in self._slot_items:
            if type_id not in self._sm_state:
                continue
            cfg           = self._slot_basis.get(str(type_id), {})
            item_vol_mode = cfg.get('vol_mode', 'jita')
            price, _      = self._slot_get_price(type_id, avg_buy, avg_sell)
            if item_vol_mode == 'expected':
                exp_units = float(cfg.get('units', 0))
                if not exp_units:
                    continue
                slot_p = exp_units * price * comm * prem
            else:
                jita_vol = self._slot_volumes.get(type_id, 0)
                if not jita_vol:
                    continue
                slot_p = jita_vol * scale * price * comm * prem
            self._sm_state[type_id]['price'] = f'{slot_p:,.0f}'
            updated += 1

        self._sm_refresh_tree()
        self._sm_status_lbl.configure(
            text=f'Pulled prices for {updated} PI items \u2713', fg='#00ff88')
        self.root.after(3000, lambda: self._sm_status_lbl.configure(text=''))

    def _sm_save(self):
        """Write in-program items to slots_config.json."""
        entries = []
        for type_id in self._sm_all_ids:
            state = self._sm_state[type_id]
            if not state['in_program']:
                continue
            cat, name, _ = self._sm_meta[type_id]
            entries.append({
                'type_id':  type_id,
                'category': cat,
                'name':     name,
                'status':   state['status'],
                'lessee':   state['lessee'] or None,
                'price':    state['price']  or None,
            })
        try:
            with open(self._SLOTMGR_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            n = len(entries)
            self._sm_status_lbl.configure(
                text=f'Saved {n} slot{"s" if n != 1 else ""} \u2713', fg='#00ff88')
            self.root.after(3000, lambda: self._sm_status_lbl.configure(text=''))
        except Exception as e:
            self._sm_status_lbl.configure(text=f'Error: {e}', fg='#ff6666')

    def _sm_generate(self):
        """Save config then run generate_slots_image.py in background."""
        self._sm_save()
        self._sm_status_lbl.configure(text='Generating\u2026', fg='#ffcc44')

        import threading
        def _run():
            try:
                result = subprocess.run(
                    [sys.executable,
                     os.path.join(PROJECT_DIR, 'generate_slots_image.py')],
                    capture_output=True, text=True
                )
                msg = result.stdout.strip().split('\n')[0] if result.stdout else 'Done'
                if result.returncode != 0:
                    msg = result.stderr.strip()[:60]
                self.root.after(0, lambda: self._sm_status_lbl.configure(
                    text=msg, fg='#00ff88' if result.returncode == 0 else '#ff6666'))
            except Exception as e:
                self.root.after(0, lambda: self._sm_status_lbl.configure(
                    text=str(e)[:60], fg='#ff6666'))
        threading.Thread(target=_run, daemon=True).start()

    def update_status(self, text):
        """Update the status indicator."""
        self.status_label.configure(text=text)
        if "unsaved" in text.lower():
            self.status_label.configure(foreground='#ffaa00')
        elif "error" in text.lower():
            self.status_label.configure(foreground='#ff6666')
        else:
            self.status_label.configure(foreground='#00ff88')


    # ══════════════════════════════════════════════════════════════════════
    # BUILD REQUESTS TAB (Tab 12)
    # ══════════════════════════════════════════════════════════════════════

    def _build_build_requests_tab(self):
        """Build the Build Requests management tab."""
        import sys as _sys
        _sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts'))
        from bom_engine import expand_bom, calc_totals
        self._bom_expand   = expand_bom
        self._bom_totals   = calc_totals
        self._bs_bom_data  = None   # current expanded BOM
        self._bs_req_id    = None   # currently loaded request id

        BG = '#0a1520'
        outer = tk.Frame(self.build_req_frame, background=BG)
        outer.pack(fill='both', expand=True, padx=15, pady=10)

        tk.Label(outer, text='Build Requests', background=BG,
                 foreground='#88d0e8', font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 8))

        pane = tk.PanedWindow(outer, orient='vertical', background='#1a3040',
                              sashrelief='flat', sashwidth=6, sashpad=2)
        pane.pack(fill='both', expand=True)

        # ── TOP: Request Queue ────────────────────────────────────────────
        top_card = ttk.Frame(pane, style='Card.TFrame')
        pane.add(top_card, minsize=180)

        top_inner = ttk.Frame(top_card, style='Card.TFrame')
        top_inner.pack(fill='both', expand=True, padx=10, pady=8)

        # Toolbar
        tb = ttk.Frame(top_inner, style='Card.TFrame')
        tb.pack(fill='x', pady=(0, 6))

        tk.Label(tb, text='Request Queue', background='#0a2030',
                 foreground='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 12))

        # Status filter
        tk.Label(tb, text='Filter:', background='#0a2030',
                 foreground='#88d0e8', font=('Segoe UI', 9)).pack(side='left')
        self._bs_filter_var = tk.StringVar(value='active')
        filter_cb = ttk.Combobox(tb, textvariable=self._bs_filter_var, width=12,
                                  state='readonly',
                                  values=['active', 'all', 'pending', 'quoted', 'accepted',
                                          'assigned', 'in_progress', 'delivered', 'complete', 'cancelled'])
        filter_cb.pack(side='left', padx=(2, 8))
        filter_cb.bind('<<ComboboxSelected>>', lambda _: self._bs_load_requests())

        ttk.Button(tb, text='⟳ Refresh', command=self._bs_load_requests).pack(side='left', padx=(0, 16))

        # Action buttons
        ttk.Button(tb, text='Quote',
                   command=self._bs_open_quote).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Assign Builder',
                   command=self._bs_assign_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Mark Delivered',
                   command=self._bs_mark_delivered).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Cancel',
                   command=self._bs_cancel_request).pack(side='left', padx=(0, 16))
        ttk.Button(tb, text='View Details',
                   command=self._bs_view_details).pack(side='left', padx=(0, 4))

        # Request treeview
        req_cols = ('req_id', 'customer', 'item', 'qty', 'status', 'quote', 'builder', 'deadline', 'submitted')
        self._bs_tree = ttk.Treeview(top_inner, columns=req_cols, show='headings',
                                      selectmode='browse', height=7)
        for cid, hd, w, a in [
            ('req_id',    'REQ#',      60,  'c'),
            ('customer',  'Customer',  130, 'w'),
            ('item',      'Item',      180, 'w'),
            ('qty',       'Qty',        45, 'e'),
            ('status',    'Status',     90, 'c'),
            ('quote',     'Quote ISK', 130, 'e'),
            ('builder',   'Builder',   110, 'w'),
            ('deadline',  'Deadline',   90, 'c'),
            ('submitted', 'Submitted',  90, 'c'),
        ]:
            self._bs_tree.heading(cid, text=hd,
                                  command=lambda c=cid: self._bs_sort(c))
            self._bs_tree.column(cid, width=w, minwidth=30, anchor=a)

        # Row colours by status
        self._bs_tree.tag_configure('pending',     foreground='#8899bb')
        self._bs_tree.tag_configure('quoted',      foreground='#ffcc44')
        self._bs_tree.tag_configure('accepted',    foreground='#00d9ff')
        self._bs_tree.tag_configure('assigned',    foreground='#aaddff')
        self._bs_tree.tag_configure('in_progress', foreground='#bb88ff')
        self._bs_tree.tag_configure('delivered',   foreground='#88ffbb')
        self._bs_tree.tag_configure('complete',    foreground='#00ff88')
        self._bs_tree.tag_configure('cancelled',   foreground='#666666')
        self._bs_tree.tag_configure('row_a',       background='#0a1e2e')
        self._bs_tree.tag_configure('row_b',       background='#0d2535')

        req_vsb = ttk.Scrollbar(top_inner, orient='vertical', command=self._bs_tree.yview)
        self._bs_tree.configure(yscrollcommand=req_vsb.set)
        req_vsb.pack(side='right', fill='y')
        self._bs_tree.pack(fill='both', expand=True)
        self._bs_tree.bind('<Double-1>', lambda _: self._bs_open_quote())

        # ── BOTTOM: sub-notebook (Quote Tool | Builder Pool) ──────────────
        bot_card = ttk.Frame(pane, style='Card.TFrame')
        pane.add(bot_card, minsize=260)

        self._bs_subnb = ttk.Notebook(bot_card)
        self._bs_subnb.pack(fill='both', expand=True, padx=6, pady=6)

        # ── Quote Tool tab ────────────────────────────────────────────────
        qt_frame = ttk.Frame(self._bs_subnb, style='Card.TFrame')
        self._bs_subnb.add(qt_frame, text='  Quote Tool  ')
        self._bs_build_quote_panel(qt_frame)

        # ── Builder Pool tab ──────────────────────────────────────────────
        bp_frame = ttk.Frame(self._bs_subnb, style='Card.TFrame')
        self._bs_subnb.add(bp_frame, text='  Builder Pool  ')
        self._bs_build_builder_panel(bp_frame)

        # Initial load
        self._bs_load_requests()

    # ── Quote Tool panel ──────────────────────────────────────────────────

    def _bs_build_quote_panel(self, parent):
        BG = '#0a2030'
        inner = tk.Frame(parent, background=BG)
        inner.pack(fill='both', expand=True, padx=8, pady=6)

        # Context label
        self._bs_qt_ctx = tk.Label(inner, text='Select a pending request and click Quote',
                                    background=BG, foreground='#446688',
                                    font=('Segoe UI', 10, 'italic'))
        self._bs_qt_ctx.pack(anchor='w', pady=(0, 6))

        # Split: materials left, summary right
        split = tk.Frame(inner, background=BG)
        split.pack(fill='both', expand=True)

        # ── Left: BOM treeview ────────────────────────────────────────────
        left = tk.Frame(split, background=BG)
        left.pack(side='left', fill='both', expand=True)

        # Basis controls
        basis_bar = tk.Frame(left, background=BG)
        basis_bar.pack(fill='x', pady=(0, 4))
        tk.Label(basis_bar, text='Set all:', background=BG,
                 foreground='#668899', font=('Segoe UI', 9)).pack(side='left')
        ttk.Button(basis_bar, text='JBV',
                   command=lambda: self._bs_set_all_basis('JBV')).pack(side='left', padx=2)
        ttk.Button(basis_bar, text='JSV',
                   command=lambda: self._bs_set_all_basis('JSV')).pack(side='left', padx=2)
        ttk.Button(basis_bar, text='Reset',
                   command=self._bs_reset_basis).pack(side='left', padx=(2, 12))
        ttk.Button(basis_bar, text='Toggle Selected',
                   command=self._bs_toggle_selected_basis).pack(side='left', padx=2)
        self._bs_basis_summary = tk.Label(basis_bar, text='', background=BG,
                                           foreground='#446688', font=('Segoe UI', 9))
        self._bs_basis_summary.pack(side='right')

        # Materials treeview
        mat_cols = ('name', 'qty', 'basis', 'unit_price', 'total')
        self._bs_mat_tree = ttk.Treeview(left, columns=mat_cols, show='headings',
                                          selectmode='browse', height=8)
        for cid, hd, w, a in [
            ('name',       'Material',   220, 'w'),
            ('qty',        'Qty',         90, 'e'),
            ('basis',      'Basis',       55, 'c'),
            ('unit_price', 'Unit Price', 130, 'e'),
            ('total',      'Total ISK',  140, 'e'),
        ]:
            self._bs_mat_tree.heading(cid, text=hd)
            self._bs_mat_tree.column(cid, width=w, minwidth=30, anchor=a)

        self._bs_mat_tree.tag_configure('jbv',      foreground='#00ff88')
        self._bs_mat_tree.tag_configure('jsv',      foreground='#00d9ff')
        self._bs_mat_tree.tag_configure('no_price', foreground='#ff6666')
        self._bs_mat_tree.tag_configure('row_a',    background='#0a1e2e')
        self._bs_mat_tree.tag_configure('row_b',    background='#0d2535')

        mat_vsb = ttk.Scrollbar(left, orient='vertical', command=self._bs_mat_tree.yview)
        self._bs_mat_tree.configure(yscrollcommand=mat_vsb.set)
        mat_vsb.pack(side='right', fill='y')
        self._bs_mat_tree.pack(fill='both', expand=True)

        # Job costs summary below treeview
        jobs_frame = tk.Frame(left, background=BG)
        jobs_frame.pack(fill='x', pady=(4, 0))
        self._bs_jobs_lbl = tk.Label(jobs_frame, text='', background=BG,
                                      foreground='#bb88ff', font=('Segoe UI', 9),
                                      justify='left', anchor='w')
        self._bs_jobs_lbl.pack(side='left')

        # ── Right: Quote summary ──────────────────────────────────────────
        right = tk.Frame(split, background='#0a1828', width=220)
        right.pack(side='right', fill='y', padx=(10, 0))
        right.pack_propagate(False)

        def _lrow(label, var_attr, color='#cce6ff'):
            row = tk.Frame(right, background='#0a1828')
            row.pack(fill='x', padx=10, pady=2)
            tk.Label(row, text=label, background='#0a1828',
                     foreground='#668899', font=('Segoe UI', 9), anchor='w').pack(side='left')
            lbl = tk.Label(row, text='—', background='#0a1828',
                           foreground=color, font=('Segoe UI', 9, 'bold'), anchor='e')
            lbl.pack(side='right')
            setattr(self, var_attr, lbl)

        tk.Label(right, text='Quote Builder', background='#0a1828',
                 foreground='#00d9ff', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=10, pady=(8, 6))

        _lrow('JBV Materials',  '_bs_lbl_jbv',  '#00ff88')
        _lrow('JSV Materials',  '_bs_lbl_jsv',  '#00d9ff')
        _lrow('Job Costs',      '_bs_lbl_jobs', '#bb88ff')

        sep = tk.Frame(right, background='#1a3040', height=1)
        sep.pack(fill='x', padx=10, pady=4)

        _lrow('Subtotal',  '_bs_lbl_sub')

        # Markup row
        mu_row = tk.Frame(right, background='#0a1828')
        mu_row.pack(fill='x', padx=10, pady=4)
        tk.Label(mu_row, text='Markup %', background='#0a1828',
                 foreground='#668899', font=('Segoe UI', 9)).pack(side='left')
        self._bs_markup_var = tk.DoubleVar(value=15.0)
        mu_spin = tk.Spinbox(mu_row, from_=0, to=100, increment=1,
                             textvariable=self._bs_markup_var, width=5,
                             background='#0a2030', foreground='#cce6ff',
                             font=('Segoe UI', 9),
                             command=self._bs_recalc)
        mu_spin.pack(side='right')
        self._bs_markup_var.trace_add('write', lambda *_: self._bs_recalc())

        sep2 = tk.Frame(right, background='#1a3040', height=1)
        sep2.pack(fill='x', padx=10, pady=4)

        _lrow('Final Quote',   '_bs_lbl_quote', '#ffcc44')
        _lrow('Corp Margin',   '_bs_lbl_margin', '#00ff88')
        _lrow('Builder (~70%)', '_bs_lbl_builder', '#bb88ff')

        sep3 = tk.Frame(right, background='#1a3040', height=1)
        sep3.pack(fill='x', padx=10, pady=6)

        self._bs_save_btn = ttk.Button(right, text='Save Quote',
                                        style='Save.TButton',
                                        command=self._bs_save_quote,
                                        state='disabled')
        self._bs_save_btn.pack(fill='x', padx=10, pady=2)

        ttk.Button(right, text='Send Discord Notification',
                   command=self._bs_send_discord).pack(fill='x', padx=10, pady=2)

    # ── Builder Pool panel ────────────────────────────────────────────────

    def _bs_build_builder_panel(self, parent):
        BG = '#0a2030'
        inner = tk.Frame(parent, background=BG)
        inner.pack(fill='both', expand=True, padx=8, pady=6)

        # Toolbar
        tb = tk.Frame(inner, background=BG)
        tb.pack(fill='x', pady=(0, 6))
        tk.Label(tb, text='Builder Pool', background=BG,
                 foreground='#66d9ff', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 12))
        ttk.Button(tb, text='+ Add Builder',
                   command=self._bs_add_builder_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Edit',
                   command=self._bs_edit_builder_dialog).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Toggle Active',
                   command=self._bs_toggle_builder_active).pack(side='left', padx=(0, 4))
        ttk.Button(tb, text='Log Payment',
                   command=self._bs_log_payment_dialog).pack(side='left', padx=(0, 16))
        ttk.Button(tb, text='⟳ Refresh',
                   command=self._bs_load_builders).pack(side='left')

        # Builder treeview
        b_cols = ('name', 'active', 'specs', 'cut_pct', 'owed', 'total_earned')
        self._bs_builder_tree = ttk.Treeview(inner, columns=b_cols, show='headings',
                                              selectmode='browse', height=8)
        for cid, hd, w, a in [
            ('name',         'Character',    160, 'w'),
            ('active',       'Active',        55, 'c'),
            ('specs',        'Specialisations', 200, 'w'),
            ('cut_pct',      'Cut %',          55, 'e'),
            ('owed',         'ISK Owed',      140, 'e'),
            ('total_earned', 'Total Earned',  140, 'e'),
        ]:
            self._bs_builder_tree.heading(cid, text=hd)
            self._bs_builder_tree.column(cid, width=w, minwidth=30, anchor=a)

        self._bs_builder_tree.tag_configure('active',   foreground='#00ff88')
        self._bs_builder_tree.tag_configure('inactive', foreground='#666666')

        b_vsb = ttk.Scrollbar(inner, orient='vertical', command=self._bs_builder_tree.yview)
        self._bs_builder_tree.configure(yscrollcommand=b_vsb.set)
        b_vsb.pack(side='right', fill='y')
        self._bs_builder_tree.pack(fill='both', expand=True)

        self._bs_load_builders()

    # ── Data loading ──────────────────────────────────────────────────────

    def _bs_load_requests(self):
        """Reload the request queue treeview from DB."""
        filt = self._bs_filter_var.get()
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()

        if filt == 'all':
            cur.execute('''SELECT r.id, r.customer_name, r.item_name, r.quantity,
                                  r.status, r.quote_price, r.deadline, r.created_at,
                                  b.character_name AS builder_name
                           FROM build_requests r
                           LEFT JOIN build_builders b ON r.builder_id = b.id
                           ORDER BY r.created_at DESC''')
        elif filt == 'active':
            cur.execute('''SELECT r.id, r.customer_name, r.item_name, r.quantity,
                                  r.status, r.quote_price, r.deadline, r.created_at,
                                  b.character_name AS builder_name
                           FROM build_requests r
                           LEFT JOIN build_builders b ON r.builder_id = b.id
                           WHERE r.status NOT IN ('complete', 'cancelled')
                           ORDER BY r.created_at DESC''')
        else:
            cur.execute('''SELECT r.id, r.customer_name, r.item_name, r.quantity,
                                  r.status, r.quote_price, r.deadline, r.created_at,
                                  b.character_name AS builder_name
                           FROM build_requests r
                           LEFT JOIN build_builders b ON r.builder_id = b.id
                           WHERE r.status = ?
                           ORDER BY r.created_at DESC''', (filt,))
        rows = cur.fetchall()
        conn.close()

        self._bs_tree.delete(*self._bs_tree.get_children())
        for i, r in enumerate(rows):
            rid, cust, item, qty, status, quote, deadline, created, builder = r
            quote_str   = f'{quote:,.0f}' if quote else '—'
            deadline_str = deadline[:10] if deadline else '—'
            created_str  = created[:10] if created else '—'
            builder_str  = builder or '—'
            tags = (status, 'row_a' if i % 2 == 0 else 'row_b')
            self._bs_tree.insert('', 'end', iid=str(rid), tags=tags,
                                 values=(f'REQ-{rid:04d}', cust, item, qty, status,
                                         quote_str, builder_str, deadline_str, created_str))

    def _bs_load_builders(self):
        """Reload the builder pool treeview."""
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('''SELECT b.id, b.character_name, b.active,
                              b.specializations, b.default_builder_pct,
                              COALESCE(SUM(CASE WHEN p.paid=0 THEN p.isk_owed ELSE 0 END), 0) AS owed,
                              COALESCE(SUM(p.isk_owed), 0) AS total_earned
                       FROM build_builders b
                       LEFT JOIN build_payouts p ON p.builder_id = b.id
                       GROUP BY b.id
                       ORDER BY b.active DESC, b.character_name''')
        rows = cur.fetchall()
        conn.close()

        self._bs_builder_tree.delete(*self._bs_builder_tree.get_children())
        for r in rows:
            bid, name, active, specs_json, cut, owed, earned = r
            try:
                specs = ', '.join(json.loads(specs_json or '[]'))
            except Exception:
                specs = specs_json or ''
            tag = 'active' if active else 'inactive'
            self._bs_builder_tree.insert('', 'end', iid=str(bid), tags=(tag,),
                                         values=(name, '✓' if active else '—',
                                                 specs, f'{cut:.0f}%',
                                                 f'{owed:,.0f}',
                                                 f'{earned:,.0f}'))

    # ── Quote Tool logic ──────────────────────────────────────────────────

    def _bs_selected_req_id(self):
        sel = self._bs_tree.selection()
        if not sel:
            messagebox.showinfo('Build Requests', 'Select a request first.')
            return None
        return int(sel[0])

    def _bs_open_quote(self):
        """Expand BOM and populate the quote tool for the selected request."""
        rid = self._bs_selected_req_id()
        if rid is None:
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req = conn.execute('SELECT * FROM build_requests WHERE id = ?', (rid,)).fetchone()
        conn.close()

        if not req:
            return

        self._bs_req_id = rid
        self._bs_subnb.select(0)  # switch to Quote Tool tab

        self._bs_qt_ctx.configure(
            text=f'REQ-{rid:04d}  ·  {req["item_name"]} ×{req["quantity"]}  '
                 f'|  ME10  ·  SCI {self._get_cfg("mfg_sci", "?")}%  ·  Tax {self._get_cfg("mfg_facility_tax", "?")}%',
            foreground='#88d0e8'
        )

        if req['markup_pct']:
            self._bs_markup_var.set(req['markup_pct'])

        if not req['item_type_id']:
            messagebox.showwarning('Quote Tool',
                                   f'No type_id stored for "{req["item_name"]}" — '
                                   f'cannot auto-expand BOM.\nEnter quote manually.')
            return

        result = self._bom_expand(req['item_type_id'], req['quantity'], DB_PATH)
        if not result['ok']:
            messagebox.showerror('BOM Error', result['error'])
            return

        self._bs_bom_data = result
        self._bs_render_bom()
        self._bs_recalc()
        self._bs_save_btn.configure(state='normal')

    def _bs_render_bom(self):
        """Populate the materials treeview from current BOM data."""
        if not self._bs_bom_data:
            return
        mats = self._bs_bom_data['materials']
        self._bs_mat_tree.delete(*self._bs_mat_tree.get_children())

        jbv_count = jsv_count = no_price = 0
        for i, m in enumerate(mats):
            price = m['jbv'] if m['basis'] == 'JBV' else m['jsv']
            eff   = price * (m['pct'] / 100)
            total = m['qty'] * eff

            if not m['has_price']:
                tag   = 'no_price'
                p_str = 'NO PRICE'
                t_str = '—'
                no_price += 1
            elif m['basis'] == 'JBV':
                tag   = 'jbv'
                p_str = f'{eff:,.2f}'
                t_str = f'{total:,.0f}'
                jbv_count += 1
            else:
                tag   = 'jsv'
                p_str = f'{eff:,.2f}'
                t_str = f'{total:,.0f}'
                jsv_count += 1

            row_tag = 'row_a' if i % 2 == 0 else 'row_b'
            self._bs_mat_tree.insert('', 'end', iid=str(i), tags=(tag, row_tag),
                                     values=(m['name'], f'{m["qty"]:,}',
                                             m['basis'], p_str, t_str))

        # Job costs summary
        jobs = self._bs_bom_data['jobs']
        job_lines = [f'{j["name"]} ×{j["runs"]}  →  {j["job_cost"]/1e6:.2f}M ISK'
                     for j in sorted(jobs, key=lambda x: x['depth'])]
        self._bs_jobs_lbl.configure(
            text='Jobs: ' + '   |   '.join(job_lines[:4]) +
                 (f'  (+{len(job_lines)-4} more)' if len(job_lines) > 4 else '')
        )
        self._bs_basis_summary.configure(
            text=f'{jbv_count} JBV · {jsv_count} JSV' +
                 (f' · {no_price} ⚠ no price' if no_price else '')
        )

    def _bs_recalc(self):
        """Recalculate totals and update the summary panel."""
        if not self._bs_bom_data:
            return
        t = self._bom_totals(self._bs_bom_data['materials'], self._bs_bom_data['jobs'])

        try:
            markup = float(self._bs_markup_var.get())
        except Exception:
            markup = 15.0

        quote  = t['subtotal'] * (1 + markup / 100)
        margin = quote - t['subtotal']
        conn   = sqlite3.connect(DB_PATH)
        build_pct = float(conn.execute(
            "SELECT value FROM site_config WHERE key='build_default_builder_pct'"
        ).fetchone()[0] or 70)
        conn.close()
        builder_cut = quote * (build_pct / 100)

        def fmt(n): return f'{n:,.0f} ISK'
        self._bs_lbl_jbv.configure(text=fmt(t['jbv_mat']))
        self._bs_lbl_jsv.configure(text=fmt(t['jsv_mat']))
        self._bs_lbl_jobs.configure(text=fmt(t['job_cost']))
        self._bs_lbl_sub.configure(text=fmt(t['subtotal']))
        self._bs_lbl_quote.configure(text=fmt(quote))
        self._bs_lbl_margin.configure(text=fmt(margin))
        self._bs_lbl_builder.configure(text=fmt(builder_cut))

    def _bs_set_all_basis(self, basis):
        if not self._bs_bom_data:
            return
        for m in self._bs_bom_data['materials']:
            m['basis'] = basis
        self._bs_render_bom()
        self._bs_recalc()

    def _bs_reset_basis(self):
        if not self._bs_bom_data:
            return
        for m in self._bs_bom_data['materials']:
            m['basis'] = 'JBV' if m['has_local_price'] else 'JSV'
        self._bs_render_bom()
        self._bs_recalc()

    def _bs_toggle_selected_basis(self):
        if not self._bs_bom_data:
            return
        sel = self._bs_mat_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        m = self._bs_bom_data['materials'][idx]
        m['basis'] = 'JSV' if m['basis'] == 'JBV' else 'JBV'
        self._bs_render_bom()
        self._bs_recalc()

    # ── Save / actions ────────────────────────────────────────────────────

    def _bs_save_quote(self):
        if not self._bs_bom_data or not self._bs_req_id:
            return
        t = self._bom_totals(self._bs_bom_data['materials'], self._bs_bom_data['jobs'])
        try:
            markup = float(self._bs_markup_var.get())
        except Exception:
            markup = 15.0
        quote = t['subtotal'] * (1 + markup / 100)

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            '''UPDATE build_requests
               SET status='quoted', materials_cost_est=?, job_cost_est=?,
                   markup_pct=?, quote_price=?, updated_at=datetime('now')
               WHERE id=?''',
            (t['jbv_mat'] + t['jsv_mat'], t['job_cost'], markup, quote, self._bs_req_id)
        )
        conn.commit()
        conn.close()
        self._bs_load_requests()
        self.update_status(f'Quote saved for REQ-{self._bs_req_id:04d}: {quote:,.0f} ISK')
        messagebox.showinfo('Quote Saved',
                            f'REQ-{self._bs_req_id:04d} → quoted\n'
                            f'Quote: {quote:,.0f} ISK\n\n'
                            f'Use "Send Discord Notification" to notify the customer.')

    def _bs_send_discord(self):
        if not self._bs_req_id:
            return
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req = conn.execute('SELECT * FROM build_requests WHERE id=?', (self._bs_req_id,)).fetchone()
        webhook = conn.execute(
            "SELECT value FROM site_config WHERE key='build_discord_webhook'"
        ).fetchone()
        conn.close()

        if not webhook or not webhook[0]:
            messagebox.showwarning('Discord',
                                   'No webhook configured.\n'
                                   'Set build_discord_webhook in site_config.')
            return

        import urllib.request
        msg = (f'**Build Quote — REQ-{req["id"]:04d}**\n'
               f'Customer: {req["customer_name"]}\n'
               f'Item: **{req["item_name"]}** ×{req["quantity"]}\n'
               f'Quote: **{req["quote_price"]:,.0f} ISK**\n'
               f'Delivery: {req["delivery_location"]}\n'
               f'Lookup token: `{req["lookup_token"]}`\n'
               f'Reply Accept to confirm. Quote valid 48h.')
        try:
            data = json.dumps({'content': msg}).encode()
            req2 = urllib.request.Request(webhook[0], data=data,
                                          headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req2, timeout=8)
            self.update_status('Discord notification sent.')
        except Exception as e:
            messagebox.showerror('Discord Error', str(e))

    def _bs_assign_dialog(self):
        rid = self._bs_selected_req_id()
        if rid is None:
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req      = conn.execute('SELECT * FROM build_requests WHERE id=?', (rid,)).fetchone()
        builders = conn.execute(
            'SELECT id, character_name, default_builder_pct FROM build_builders WHERE active=1 ORDER BY character_name'
        ).fetchall()
        conn.close()

        if not builders:
            messagebox.showinfo('Assign Builder',
                                'No active builders in the pool.\nAdd builders in the Builder Pool tab first.')
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f'Assign Builder — REQ-{rid:04d}')
        dlg.geometry('380x260')
        dlg.configure(bg='#0a1520')
        dlg.grab_set()

        tk.Label(dlg, text=f'REQ-{rid:04d}: {req["item_name"]} ×{req["quantity"]}',
                 background='#0a1520', foreground='#cce6ff',
                 font=('Segoe UI', 11, 'bold')).pack(pady=(14, 4), padx=16, anchor='w')

        tk.Label(dlg, text='Select builder:', background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 10)).pack(padx=16, anchor='w')

        builder_names = [b['character_name'] for b in builders]
        builder_ids   = [b['id'] for b in builders]
        builder_pcts  = [b['default_builder_pct'] for b in builders]

        sel_var = tk.StringVar(value=builder_names[0])
        cb = ttk.Combobox(dlg, textvariable=sel_var, values=builder_names,
                           state='readonly', width=28)
        cb.pack(padx=16, pady=6, anchor='w')

        pct_frame = tk.Frame(dlg, background='#0a1520')
        pct_frame.pack(fill='x', padx=16, pady=4)
        tk.Label(pct_frame, text='Builder cut %:', background='#0a1520',
                 foreground='#88d0e8', font=('Segoe UI', 10)).pack(side='left')
        pct_var = tk.DoubleVar(value=builder_pcts[0])
        pct_spin = tk.Spinbox(pct_frame, from_=0, to=100, increment=5,
                              textvariable=pct_var, width=6,
                              background='#0a2030', foreground='#cce6ff', font=('Segoe UI', 10))
        pct_spin.pack(side='left', padx=6)

        def on_builder_change(*_):
            idx = builder_names.index(sel_var.get())
            pct_var.set(builder_pcts[idx])
        sel_var.trace_add('write', on_builder_change)

        def do_assign():
            idx = builder_names.index(sel_var.get())
            bid = builder_ids[idx]
            pct = float(pct_var.get())
            conn2 = sqlite3.connect(DB_PATH)
            conn2.execute(
                '''UPDATE build_requests
                   SET builder_id=?, builder_pct=?, status='assigned',
                       assigned_at=datetime('now'), updated_at=datetime('now')
                   WHERE id=?''',
                (bid, pct, rid)
            )
            conn2.commit()
            conn2.close()
            dlg.destroy()
            self._bs_load_requests()
            self.update_status(f'REQ-{rid:04d} assigned to {sel_var.get()}')

        btn_row = tk.Frame(dlg, background='#0a1520')
        btn_row.pack(pady=14)
        ttk.Button(btn_row, text='Assign', style='Save.TButton',
                   command=do_assign).pack(side='left', padx=6)
        ttk.Button(btn_row, text='Cancel',
                   command=dlg.destroy).pack(side='left', padx=6)

    def _bs_mark_delivered(self):
        rid = self._bs_selected_req_id()
        if rid is None:
            return
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req = conn.execute('SELECT * FROM build_requests WHERE id=?', (rid,)).fetchone()

        price_str = f'{req["quote_price"]:,.0f}' if req['quote_price'] else '?'
        if not messagebox.askyesno('Mark Delivered',
                                   f'Mark REQ-{rid:04d} as delivered?\n'
                                   f'Item: {req["item_name"]} ×{req["quantity"]}\n'
                                   f'Quote: {price_str} ISK\n\n'
                                   f'This will create a payout record for the builder.'):
            conn.close()
            return

        # Update request
        conn.execute(
            '''UPDATE build_requests
               SET status='delivered', contract_price_actual=quote_price,
                   completed_at=datetime('now'), updated_at=datetime('now')
               WHERE id=?''', (rid,)
        )
        # Create payout record if builder assigned
        if req['builder_id'] and req['quote_price'] and req['builder_pct']:
            isk_owed = req['quote_price'] * (req['builder_pct'] / 100)
            conn.execute(
                'INSERT INTO build_payouts (builder_id, request_id, isk_owed, paid) VALUES (?,?,?,0)',
                (req['builder_id'], rid, isk_owed)
            )
        conn.commit()
        conn.close()
        self._bs_load_requests()
        self._bs_load_builders()
        self.update_status(f'REQ-{rid:04d} marked delivered.')

    def _bs_cancel_request(self):
        rid = self._bs_selected_req_id()
        if rid is None:
            return
        if messagebox.askyesno('Cancel Request', f'Cancel REQ-{rid:04d}?'):
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE build_requests SET status='cancelled', updated_at=datetime('now') WHERE id=?",
                (rid,)
            )
            conn.commit()
            conn.close()
            self._bs_load_requests()
            self.update_status(f'REQ-{rid:04d} cancelled.')

    def _bs_view_details(self):
        rid = self._bs_selected_req_id()
        if rid is None:
            return
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        req = conn.execute('SELECT * FROM build_requests WHERE id=?', (rid,)).fetchone()
        conn.close()

        dlg = tk.Toplevel(self.root)
        dlg.title(f'REQ-{rid:04d} Details')
        dlg.geometry('460x340')
        dlg.configure(bg='#0a1520')
        dlg.grab_set()

        def row(label, value, color='#cce6ff'):
            f = tk.Frame(dlg, background='#0a1520')
            f.pack(fill='x', padx=18, pady=2)
            tk.Label(f, text=label, background='#0a1520', foreground='#668899',
                     font=('Segoe UI', 9), width=18, anchor='w').pack(side='left')
            tk.Label(f, text=str(value or '—'), background='#0a1520', foreground=color,
                     font=('Segoe UI', 10)).pack(side='left')

        tk.Label(dlg, text=f'REQ-{rid:04d}  ·  {req["item_name"]}',
                 background='#0a1520', foreground='#00d9ff',
                 font=('Segoe UI', 13, 'bold')).pack(pady=(14, 10), padx=18, anchor='w')

        row('Customer',   req['customer_name'])
        row('Quantity',   req['quantity'])
        row('Status',     req['status'], '#ffcc44')
        row('Delivery',   req['delivery_location'])
        row('Deadline',   req['deadline'])
        row('Lookup Token', req['lookup_token'], '#00d9ff')
        row('Quote Price', f'{req["quote_price"]:,.0f} ISK' if req['quote_price'] else '—', '#ffcc44')
        row('Submitted',  req['created_at'][:16] if req['created_at'] else '—')
        if req['notes']:
            tk.Label(dlg, text='Notes:', background='#0a1520', foreground='#668899',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=(8, 2))
            tk.Label(dlg, text=req['notes'], background='#0a1520', foreground='#aabbcc',
                     font=('Segoe UI', 10), wraplength=400, justify='left').pack(anchor='w', padx=18)

        ttk.Button(dlg, text='Close', command=dlg.destroy).pack(pady=12)

    def _bs_sort(self, col):
        """Sort the request treeview by column."""
        items = [(self._bs_tree.set(k, col), k) for k in self._bs_tree.get_children('')]
        items.sort(key=lambda x: x[0])
        for idx, (_, k) in enumerate(items):
            self._bs_tree.move(k, '', idx)

    # ── Builder pool actions ──────────────────────────────────────────────

    def _bs_add_builder_dialog(self):
        self._bs_builder_form_dialog(None)

    def _bs_edit_builder_dialog(self):
        sel = self._bs_builder_tree.selection()
        if not sel:
            messagebox.showinfo('Builder Pool', 'Select a builder to edit.')
            return
        self._bs_builder_form_dialog(int(sel[0]))

    def _bs_builder_form_dialog(self, builder_id):
        existing = None
        if builder_id:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            existing = conn.execute('SELECT * FROM build_builders WHERE id=?', (builder_id,)).fetchone()
            conn.close()

        dlg = tk.Toplevel(self.root)
        dlg.title('Add Builder' if not existing else f'Edit — {existing["character_name"]}')
        dlg.geometry('380x320')
        dlg.configure(bg='#0a1520')
        dlg.grab_set()

        fields = {}
        def field(label, default=''):
            f = tk.Frame(dlg, background='#0a1520')
            f.pack(fill='x', padx=16, pady=4)
            tk.Label(f, text=label, background='#0a1520', foreground='#88d0e8',
                     font=('Segoe UI', 10), width=18, anchor='w').pack(side='left')
            e = tk.Entry(f, background='#0a2030', foreground='#cce6ff',
                         insertbackground='#cce6ff', font=('Segoe UI', 10), width=22)
            e.insert(0, str(default))
            e.pack(side='left')
            return e

        fields['name'] = field('Character Name', existing['character_name'] if existing else '')
        fields['char_id'] = field('Character ID', existing['character_id'] if existing else '')
        fields['cut']  = field('Default Cut %',  existing['default_builder_pct'] if existing else '70')
        fields['specs'] = field('Specialisations',
                                ', '.join(json.loads(existing['specializations'] or '[]')) if existing else '')

        notes_frame = tk.Frame(dlg, background='#0a1520')
        notes_frame.pack(fill='x', padx=16, pady=4)
        tk.Label(notes_frame, text='Notes', background='#0a1520', foreground='#88d0e8',
                 font=('Segoe UI', 10), width=18, anchor='w').pack(side='left')
        notes_e = tk.Text(notes_frame, background='#0a2030', foreground='#cce6ff',
                          font=('Segoe UI', 10), width=22, height=3)
        if existing and existing['notes']:
            notes_e.insert('1.0', existing['notes'])
        notes_e.pack(side='left')

        def save():
            name  = fields['name'].get().strip()
            cid   = fields['char_id'].get().strip() or None
            cut   = float(fields['cut'].get() or 70)
            specs_raw = [s.strip() for s in fields['specs'].get().split(',') if s.strip()]
            specs = json.dumps(specs_raw)
            notes = notes_e.get('1.0', 'end').strip()
            if not name:
                messagebox.showerror('Validation', 'Character name is required.')
                return
            conn2 = sqlite3.connect(DB_PATH)
            if existing:
                conn2.execute(
                    '''UPDATE build_builders SET character_name=?, character_id=?,
                       default_builder_pct=?, specializations=?, notes=? WHERE id=?''',
                    (name, cid, cut, specs, notes, builder_id)
                )
            else:
                conn2.execute(
                    '''INSERT INTO build_builders
                       (character_name, character_id, default_builder_pct, specializations, notes, active)
                       VALUES (?,?,?,?,?,1)''',
                    (name, cid, cut, specs, notes)
                )
            conn2.commit()
            conn2.close()
            dlg.destroy()
            self._bs_load_builders()

        btn_row = tk.Frame(dlg, background='#0a1520')
        btn_row.pack(pady=12)
        ttk.Button(btn_row, text='Save', style='Save.TButton', command=save).pack(side='left', padx=6)
        ttk.Button(btn_row, text='Cancel', command=dlg.destroy).pack(side='left', padx=6)

    def _bs_toggle_builder_active(self):
        sel = self._bs_builder_tree.selection()
        if not sel:
            messagebox.showinfo('Builder Pool', 'Select a builder first.')
            return
        bid = int(sel[0])
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('SELECT active FROM build_builders WHERE id=?', (bid,))
        current = cur.fetchone()[0]
        conn.execute('UPDATE build_builders SET active=? WHERE id=?', (0 if current else 1, bid))
        conn.commit()
        conn.close()
        self._bs_load_builders()

    def _bs_log_payment_dialog(self):
        sel = self._bs_builder_tree.selection()
        if not sel:
            messagebox.showinfo('Log Payment', 'Select a builder first.')
            return
        bid  = int(sel[0])
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        builder = conn.execute('SELECT * FROM build_builders WHERE id=?', (bid,)).fetchone()
        owed_rows = conn.execute(
            '''SELECT p.id, r.item_name, r.quantity, p.isk_owed
               FROM build_payouts p
               JOIN build_requests r ON r.id = p.request_id
               WHERE p.builder_id=? AND p.paid=0''', (bid,)
        ).fetchall()
        conn.close()

        if not owed_rows:
            messagebox.showinfo('Log Payment', f'{builder["character_name"]} has no unpaid payouts.')
            return

        total_owed = sum(r['isk_owed'] for r in owed_rows)
        if messagebox.askyesno('Log Payment',
                               f'Mark ALL unpaid for {builder["character_name"]} as paid?\n'
                               f'Total: {total_owed:,.0f} ISK\n'
                               f'({len(owed_rows)} payout(s))'):
            conn2 = sqlite3.connect(DB_PATH)
            conn2.execute(
                "UPDATE build_payouts SET paid=1, paid_date=date('now') WHERE builder_id=? AND paid=0",
                (bid,)
            )
            conn2.commit()
            conn2.close()
            self._bs_load_builders()
            self.update_status(f'Payment logged for {builder["character_name"]}: {total_owed:,.0f} ISK')

    def _get_cfg(self, key, default=''):
        conn = sqlite3.connect(DB_PATH)
        row  = conn.execute('SELECT value FROM site_config WHERE key=?', (key,)).fetchone()
        conn.close()
        return row[0] if row else default


def main():
    root = tk.Tk()
    app = AdminDashboard(root)
    # Force window to front
    root.lift()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))
    root.focus_force()
    root.mainloop()


if __name__ == '__main__':
    main()
