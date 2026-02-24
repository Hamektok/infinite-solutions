"""
Infinite Solutions - Admin Dashboard
Local GUI for managing buyback rates, viewing inventory, and deploying updates.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import subprocess
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mydatabase.db')
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Map DB category names to display names (must match generate_buyback_data.py)
CATEGORY_DISPLAY = {
    'minerals': 'Minerals',
    'ice_products': 'Ice Products',
    'moon_materials': 'Reaction Materials',
    'salvaged_materials': 'Salvaged Materials',
}
# Reverse lookup: display name -> DB category key
CATEGORY_DB_KEY = {v: k for k, v in CATEGORY_DISPLAY.items()}


class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Infinite Solutions - Admin Dashboard")
        self.root.geometry("1100x750")
        self.root.configure(bg='#0a1520')
        self.root.minsize(900, 600)

        # Track unsaved changes
        self.unsaved_changes = {}

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()

        # Build UI
        self.build_header()
        self.build_notebook()
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
        self.notebook.add(self.bp_frame, text='  Blueprint Library  ')
        self.build_blueprint_tab()

        # Tab 4: Inventory Overview
        self.inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inventory_frame, text='  Inventory  ')
        self.build_inventory_tab()

        # Tab 5: Export Analysis
        self.export_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.export_frame, text='  Export Analysis  ')
        self.build_export_tab()

        # Tab 6: Import Analysis
        self.import_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.import_frame, text='  Import Analysis  ')
        self.build_import_tab()

        # Tab 7: Quick Actions
        self.actions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.actions_frame, text='  Quick Actions  ')
        self.build_actions_tab()

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

        # Rates treeview
        tree_frame = ttk.Frame(self.rates_frame)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))

        columns = ('category', 'item', 'current_rate', 'new_rate', 'alliance_discount')
        self.rates_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                        selectmode='extended')

        self.rates_tree.heading('category', text='Category')
        self.rates_tree.heading('item', text='Item Name')
        self.rates_tree.heading('current_rate', text='Current Rate')
        self.rates_tree.heading('new_rate', text='New Rate (%)')
        self.rates_tree.heading('alliance_discount', text='Discount %')

        self.rates_tree.column('category', width=130, anchor='center')
        self.rates_tree.column('item', width=250)
        self.rates_tree.column('current_rate', width=120, anchor='center')
        self.rates_tree.column('new_rate', width=120, anchor='center')
        self.rates_tree.column('alliance_discount', width=150, anchor='center')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                   command=self.rates_tree.yview)
        self.rates_tree.configure(yscrollcommand=scrollbar.set)

        self.rates_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Rate editor panel (bottom)
        editor = ttk.Frame(self.rates_frame, style='Card.TFrame')
        editor.pack(fill='x', padx=15, pady=(0, 15))

        inner = ttk.Frame(editor)
        inner.pack(padx=20, pady=15)

        ttk.Label(inner, text="Selected Item:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 10))

        self.selected_item_label = ttk.Label(inner, text="(click a row above)",
                                              style='Value.TLabel')
        self.selected_item_label.pack(side='left', padx=(0, 30))

        ttk.Label(inner, text="Set Rate %:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(0, 5))

        self.rate_var = tk.IntVar(value=98)
        self.rate_spinbox = tk.Spinbox(inner, from_=80, to=100,
                                        textvariable=self.rate_var,
                                        width=5, font=('Segoe UI', 14, 'bold'),
                                        bg='#0a2030', fg='#00ffff',
                                        buttonbackground='#1a3040',
                                        insertbackground='#00ffff',
                                        justify='center')
        self.rate_spinbox.pack(side='left', padx=(0, 10))

        ttk.Button(inner, text="Apply", style='Action.TButton',
                   command=self.apply_rate_change).pack(side='left', padx=5)

        # Preset buttons
        ttk.Label(inner, text="Presets:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(20, 5))

        for pct in [95, 96, 97, 98, 99]:
            btn = tk.Button(inner, text=f"{pct}%", width=4,
                           font=('Segoe UI', 10, 'bold'),
                           bg='#1a3040', fg='#00d9ff', relief='flat',
                           activebackground='#2a4050', activeforeground='#00ffff',
                           command=lambda p=pct: self.quick_set_rate(p))
            btn.pack(side='left', padx=2)

        # Discount adjustment
        ttk.Label(inner, text="Discount %:",
                  font=('Segoe UI', 11)).pack(side='left', padx=(25, 5))

        self.discount_var = tk.IntVar(value=2)
        self.discount_spinbox = tk.Spinbox(inner, from_=0, to=20,
                                            textvariable=self.discount_var,
                                            width=5, font=('Segoe UI', 14, 'bold'),
                                            bg='#0a2030', fg='#00ff88',
                                            buttonbackground='#1a3040',
                                            insertbackground='#00ff88',
                                            justify='center')
        self.discount_spinbox.pack(side='left', padx=(0, 10))

        ttk.Button(inner, text="Apply Discount", style='Action.TButton',
                   command=self.apply_discount_change).pack(side='left', padx=5)

        # Bind selection
        self.rates_tree.bind('<<TreeviewSelect>>', self.on_rate_select)

    def build_buyback_tab(self):
        """Build the Buyback Program management tab."""
        # Track unsaved buyback changes separately
        self.unsaved_buyback_changes = {}

        # Buyback category names (must match what the website uses)
        self.buyback_categories = [
            'Minerals', 'Ice Products', 'Reaction Materials',
            'Salvaged Materials', 'Gas Clouds Materials', 'Planetary Materials'
        ]
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

        # Category visibility toggles
        cat_frame = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        cat_frame.pack(fill='x', padx=15, pady=(0, 10))

        cat_inner = ttk.Frame(cat_frame)
        cat_inner.pack(fill='x', padx=15, pady=10)

        ttk.Label(cat_inner, text="Category Visibility:",
                  font=('Segoe UI', 11, 'bold'),
                  foreground='#00d9ff').pack(side='left', padx=(0, 15))

        self.category_toggle_btns = {}
        for cat_name in self.buyback_categories:
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
                                  width=18, height=1,
                                  relief='flat', bd=1,
                                  command=lambda c=cat_name: self._on_category_toggle(c))
            btn.pack(side='left', padx=3)
            self.category_toggle_btns[cat_name] = btn

        # Pricing method per category
        price_frame = ttk.Frame(self.buyback_frame, style='Card.TFrame')
        price_frame.pack(fill='x', padx=15, pady=(0, 10))

        price_inner = ttk.Frame(price_frame)
        price_inner.pack(fill='x', padx=15, pady=10)

        ttk.Label(price_inner, text="Pricing Method:",
                  font=('Segoe UI', 11, 'bold'),
                  foreground='#00d9ff').pack(side='left', padx=(0, 15))

        self.pricing_method_vars = {}
        self.pricing_method_combos = {}
        pricing_methods = ['Jita Buy', 'Jita Sell', 'Jita Split']
        for cat_name in self.buyback_categories:
            frame = ttk.Frame(price_inner)
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
            ttk.Button(inner, text="Run", style=style,
                      command=cmd).pack(side='right', padx=10)

        # Last updated info
        self.last_updated_label = ttk.Label(container, text="",
                                             style='SubHeader.TLabel')
        self.last_updated_label.pack(anchor='w', pady=(30, 0))

    # ===== DATA LOADING =====

    def load_data(self):
        """Load all data from database."""
        self.unsaved_changes = {}
        self.unsaved_buyback_changes = {}
        self.unsaved_bp_changes = {}
        self.update_status("All saved")
        self.load_rates()
        self.load_buyback_data()
        self.load_blueprint_settings()
        self.load_inventory()
        self.load_export_data()
        self.load_import_data()

    def load_rates(self):
        """Load buyback rates from tracked_market_items."""
        self.rates_tree.delete(*self.rates_tree.get_children())

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, type_id, type_name, category, price_percentage, alliance_discount
            FROM tracked_market_items
            ORDER BY category, display_order, type_name
        """)
        rows = cursor.fetchall()
        conn.close()

        self.rate_items = {}
        for row_id, type_id, name, category, pct, discount in rows:
            cat_display = category.replace('_', ' ').title()
            iid = self.rates_tree.insert('', 'end', values=(
                cat_display, name, f"{pct}%", f"{pct}%", f"{discount}%"
            ))
            self.rate_items[iid] = {
                'id': row_id, 'type_id': type_id, 'name': name,
                'category': category, 'rate': pct, 'discount': discount
            }

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

        if not self.unsaved_buyback_changes and not cat_changes and not pricing_changes:
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
            return
        if len(selection) == 1:
            item = self.rate_items.get(selection[0])
            if item:
                self.selected_item_label.configure(text=item['name'])
                self.rate_var.set(item['rate'])
                self.discount_var.set(item['discount'])
        else:
            self.selected_item_label.configure(text=f"{len(selection)} items selected")

    def quick_set_rate(self, pct):
        """Set the spinbox to a preset value."""
        self.rate_var.set(pct)
        self.apply_rate_change()

    def apply_rate_change(self):
        """Apply the rate change to all selected items."""
        selection = self.rates_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Click on an item first.")
            return

        new_rate = self.rate_var.get()

        for iid in selection:
            item = self.rate_items[iid]

            # Update tree display
            values = list(self.rates_tree.item(iid, 'values'))
            values[3] = f"{new_rate}% *" if new_rate != item['rate'] else f"{new_rate}%"
            self.rates_tree.item(iid, values=values)

            # Track change (merge with existing discount change if any)
            existing = self.unsaved_changes.get(iid, {})
            if new_rate != item['rate'] or 'new_discount' in existing:
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

            # Update tree display
            values = list(self.rates_tree.item(iid, 'values'))
            values[4] = f"{new_discount}% *" if new_discount != item['discount'] else f"{new_discount}%"
            self.rates_tree.item(iid, values=values)

            # Track change (merge with existing rate change if any)
            if iid in self.unsaved_changes:
                self.unsaved_changes[iid]['new_discount'] = new_discount
                self.unsaved_changes[iid]['old_discount'] = self.unsaved_changes[iid].get('old_discount', item['discount'])
            elif new_discount != item['discount']:
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
        """Run the inventory update script."""
        self.run_script('update_lx_zoj_inventory.py', 'Inventory Update')

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
        self.export_buy_var = tk.StringVar(value='JBV')
        buy_menu = ttk.Combobox(param_inner, textvariable=self.export_buy_var, width=18,
                                values=['JBV', 'Jita Split', 'JSV'], state='readonly')
        buy_menu.grid(row=2, column=0, sticky='w', padx=(0, 12))

        # Buy %
        tk.Label(param_inner, text="Buy % of Basis", **lbl_cfg).grid(row=1, column=1, sticky='w', padx=(0, 4))
        self.export_buy_pct_var = tk.StringVar(value='100')
        ttk.Entry(param_inner, textvariable=self.export_buy_pct_var, width=8).grid(
            row=2, column=1, sticky='w', padx=(0, 12))

        # Sell basis
        tk.Label(param_inner, text="Sell Basis (at Jita)", **lbl_cfg).grid(row=1, column=2, sticky='w', padx=(0, 4))
        self.export_sell_var = tk.StringVar(value='JSV')
        sell_menu = ttk.Combobox(param_inner, textvariable=self.export_sell_var, width=18,
                                 values=['JSV', 'Jita Split', 'JBV'], state='readonly')
        sell_menu.grid(row=2, column=2, sticky='w', padx=(0, 12))

        # Shipping rate
        tk.Label(param_inner, text="Shipping (ISK/m³)", **lbl_cfg).grid(row=1, column=3, sticky='w', padx=(0, 4))
        self.export_ship_var = tk.StringVar(value='125')
        ttk.Entry(param_inner, textvariable=self.export_ship_var, width=10).grid(
            row=2, column=3, sticky='w', padx=(0, 12))

        # Collateral
        tk.Label(param_inner, text="Collateral %", **lbl_cfg).grid(row=1, column=4, sticky='w', padx=(0, 4))
        self.export_collat_var = tk.StringVar(value='1.0')
        ttk.Entry(param_inner, textvariable=self.export_collat_var, width=8).grid(
            row=2, column=4, sticky='w', padx=(0, 12))

        # Sales tax
        tk.Label(param_inner, text="Sales Tax %", **lbl_cfg).grid(row=1, column=5, sticky='w', padx=(0, 4))
        self.export_tax_var = tk.StringVar(value='3.6')
        ttk.Entry(param_inner, textvariable=self.export_tax_var, width=8).grid(
            row=2, column=5, sticky='w', padx=(0, 12))

        # Broker fee
        tk.Label(param_inner, text="Broker Fee %", **lbl_cfg).grid(row=1, column=6, sticky='w', padx=(0, 4))
        self.export_broker_var = tk.StringVar(value='3.0')
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
            return best_buy
        elif basis == 'JSV':
            return best_sell
        else:  # Jita Split
            return (best_buy + best_sell) / 2

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
              AND mps.best_buy  > 0
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
        self.import_buy_var = tk.StringVar(value='JSV  (instant, from sell orders)')
        ttk.Combobox(param_inner, textvariable=self.import_buy_var, width=22,
                     values=['JSV  (instant, from sell orders)', 'JBV  (place buy order)'],
                     state='readonly').grid(row=3, column=0, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Buy % of Basis", **lbl_cfg).grid(
            row=2, column=1, sticky='w', padx=(0, 4))
        self.import_buy_pct_var = tk.StringVar(value='100')
        ttk.Entry(param_inner, textvariable=self.import_buy_pct_var, width=8).grid(
            row=3, column=1, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Broker Fee %", **lbl_cfg).grid(
            row=2, column=2, sticky='w', padx=(0, 4))
        self.import_broker_var = tk.StringVar(value='0.0')
        ttk.Entry(param_inner, textvariable=self.import_broker_var, width=8).grid(
            row=3, column=2, sticky='w', padx=(0, 20))

        # Logistics
        tk.Frame(param_inner, background='#1a3040', width=1).grid(
            row=2, column=3, rowspan=2, sticky='ns', padx=(0, 12))
        tk.Label(param_inner, text="Shipping (ISK/m\u00b3)", **lbl_cfg).grid(
            row=2, column=4, sticky='w', padx=(0, 4))
        self.import_ship_var = tk.StringVar(value='125')
        ttk.Entry(param_inner, textvariable=self.import_ship_var, width=10).grid(
            row=3, column=4, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Collateral %", **lbl_cfg).grid(
            row=2, column=5, sticky='w', padx=(0, 4))
        self.import_collat_var = tk.StringVar(value='1.0')
        ttk.Entry(param_inner, textvariable=self.import_collat_var, width=8).grid(
            row=3, column=5, sticky='w', padx=(0, 20))

        # Sell side
        tk.Frame(param_inner, background='#1a3040', width=1).grid(
            row=2, column=6, rowspan=2, sticky='ns', padx=(0, 12))
        tk.Label(param_inner, text="Price Reference", **lbl_cfg).grid(
            row=2, column=7, sticky='w', padx=(0, 4))
        self.import_sell_ref_var = tk.StringVar(value='JSV')
        ttk.Combobox(param_inner, textvariable=self.import_sell_ref_var,
                     width=14, values=['JSV', 'Jita Split', 'JBV'],
                     state='readonly').grid(row=3, column=7, sticky='w', padx=(0, 12))

        tk.Label(param_inner, text="Sell Markup %", **lbl_cfg).grid(
            row=2, column=8, sticky='w', padx=(0, 4))
        self.import_markup_var = tk.StringVar(value='115')
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
        import_cat_menu.bind('<<ComboboxSelected>>', lambda _: self._filter_import_tree())
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
            return best_buy
        return (best_buy + best_sell) / 2

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
            SELECT it.type_name, tmi.category, it.volume, mps.best_buy, mps.best_sell
            FROM tracked_market_items tmi
            JOIN inv_types it               ON tmi.type_id = it.type_id
            JOIN market_price_snapshots mps ON tmi.type_id = mps.type_id
            WHERE mps.timestamp = (
                SELECT MAX(timestamp) FROM market_price_snapshots WHERE type_id = tmi.type_id
            )
              AND mps.best_buy > 0 AND mps.best_sell > 0
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
        self._import_all_rows = []
        counts = {'great': 0, 'good': 0, 'marginal': 0, 'avoid': 0}
        margin_sum, margin_n = 0.0, 0

        for name, category, volume, best_buy, best_sell in rows:
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

    def _filter_import_tree(self):
        search     = self.import_search_var.get().lower()
        cat_filter = self.import_cat_var.get()
        show       = self.import_show_var.get()
        filtered   = [r for r in self._import_all_rows
                      if (not search or search in r['item'].lower())
                      and (cat_filter == 'All' or r['category'] == cat_filter)
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

    def update_status(self, text):
        """Update the status indicator."""
        self.status_label.configure(text=text)
        if "unsaved" in text.lower():
            self.status_label.configure(foreground='#ffaa00')
        elif "error" in text.lower():
            self.status_label.configure(foreground='#ff6666')
        else:
            self.status_label.configure(foreground='#00ff88')


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
