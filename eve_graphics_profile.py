"""
EVE Online Graphics Profile Switcher
-------------------------------------
Saves and restores graphics settings profiles by swapping core_user_*.dat files.
EVE must be CLOSED when switching profiles.

Usage: python eve_graphics_profile.py
"""

import os
import shutil
import glob
import tkinter as tk
from tkinter import ttk, messagebox

SETTINGS_DIR = os.path.expandvars(
    r"%LOCALAPPDATA%\CCP\EVE\d_eve_tq_tranquility\settings_Default"
)
PROFILES_DIR = os.path.join(os.path.dirname(__file__), "eve_graphics_profiles")


def get_user_dat_files():
    return glob.glob(os.path.join(SETTINGS_DIR, "core_user_*.dat"))


def list_profiles():
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        d for d in os.listdir(PROFILES_DIR)
        if os.path.isdir(os.path.join(PROFILES_DIR, d))
    )


def save_profile(name):
    if not name.strip():
        return False, "Profile name cannot be empty."
    files = get_user_dat_files()
    if not files:
        return False, "No core_user_*.dat files found. Is the settings path correct?"
    dest = os.path.join(PROFILES_DIR, name.strip())
    os.makedirs(dest, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest)
    return True, f"Saved {len(files)} file(s) to profile '{name}'."


def load_profile(name):
    src = os.path.join(PROFILES_DIR, name)
    if not os.path.isdir(src):
        return False, f"Profile '{name}' not found."
    files = glob.glob(os.path.join(src, "core_user_*.dat"))
    if not files:
        return False, "Profile has no core_user_*.dat files."
    for f in files:
        dest = os.path.join(SETTINGS_DIR, os.path.basename(f))
        shutil.copy2(f, dest)
    return True, f"Loaded profile '{name}' ({len(files)} file(s)). Start EVE now."


def delete_profile(name):
    path = os.path.join(PROFILES_DIR, name)
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True, f"Deleted profile '{name}'."
    return False, "Profile not found."


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EVE Graphics Profile Switcher")
        self.resizable(False, False)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        pad = dict(padx=10, pady=6)

        # Header
        tk.Label(self, text="EVE Graphics Profile Switcher",
                 font=("Segoe UI", 12, "bold")).grid(row=0, column=0,
                 columnspan=3, **pad)
        tk.Label(self, text="EVE must be CLOSED when switching profiles.",
                 fg="red", font=("Segoe UI", 9)).grid(row=1, column=0,
                 columnspan=3, padx=10, pady=(0, 8))

        # Profile list
        tk.Label(self, text="Saved Profiles:", font=("Segoe UI", 9, "bold")).grid(
            row=2, column=0, sticky="w", padx=10)
        self.listbox = tk.Listbox(self, height=6, width=28,
                                  font=("Segoe UI", 10), selectmode=tk.SINGLE)
        self.listbox.grid(row=3, column=0, rowspan=4, padx=(10, 4), pady=2,
                          sticky="ns")

        # Buttons
        btn_w = 18
        tk.Button(self, text="Load Selected", width=btn_w, bg="#2a7a2a", fg="white",
                  font=("Segoe UI", 9, "bold"),
                  command=self._load).grid(row=3, column=1, columnspan=2,
                  padx=(4, 10), pady=3, sticky="ew")
        tk.Button(self, text="Delete Selected", width=btn_w,
                  font=("Segoe UI", 9),
                  command=self._delete).grid(row=4, column=1, columnspan=2,
                  padx=(4, 10), pady=3, sticky="ew")

        # Quick-save buttons
        tk.Button(self, text="Quick Save: Quality", width=btn_w,
                  bg="#1a4a8a", fg="white", font=("Segoe UI", 9, "bold"),
                  command=lambda: self._quick_save("Quality")).grid(
                  row=5, column=1, columnspan=2, padx=(4, 10), pady=3, sticky="ew")
        tk.Button(self, text="Quick Save: Potato", width=btn_w,
                  bg="#6a3a1a", fg="white", font=("Segoe UI", 9, "bold"),
                  command=lambda: self._quick_save("Potato")).grid(
                  row=6, column=1, columnspan=2, padx=(4, 10), pady=3, sticky="ew")

        # Custom save
        sep = ttk.Separator(self, orient="horizontal")
        sep.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=6)

        tk.Label(self, text="Save current settings as:",
                 font=("Segoe UI", 9)).grid(row=8, column=0, sticky="e", padx=10)
        self.name_var = tk.StringVar()
        tk.Entry(self, textvariable=self.name_var, width=16,
                 font=("Segoe UI", 10)).grid(row=8, column=1, padx=4, pady=3)
        tk.Button(self, text="Save", width=6,
                  command=self._save_custom).grid(row=8, column=2, padx=(0, 10))

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_var, fg="#444",
                 font=("Segoe UI", 8), anchor="w").grid(
                 row=9, column=0, columnspan=3, sticky="ew", padx=10, pady=(4, 8))

    def _refresh(self):
        self.listbox.delete(0, tk.END)
        for p in list_profiles():
            self.listbox.insert(tk.END, p)

    def _status(self, msg, ok=True):
        self.status_var.set(msg)
        self.status_var.set(msg)

    def _selected(self):
        sel = self.listbox.curselection()
        return self.listbox.get(sel[0]) if sel else None

    def _load(self):
        name = self._selected()
        if not name:
            messagebox.showwarning("No Selection", "Select a profile to load.")
            return
        ok, msg = load_profile(name)
        if ok:
            messagebox.showinfo("Loaded", msg)
        else:
            messagebox.showerror("Error", msg)
        self._status(msg, ok)

    def _delete(self):
        name = self._selected()
        if not name:
            messagebox.showwarning("No Selection", "Select a profile to delete.")
            return
        if messagebox.askyesno("Confirm", f"Delete profile '{name}'?"):
            ok, msg = delete_profile(name)
            self._status(msg, ok)
            self._refresh()

    def _quick_save(self, name):
        ok, msg = save_profile(name)
        if ok:
            self._status(msg)
            self._refresh()
        else:
            messagebox.showerror("Error", msg)

    def _save_custom(self):
        name = self.name_var.get().strip()
        ok, msg = save_profile(name)
        if ok:
            self.name_var.set("")
            self._status(msg)
            self._refresh()
        else:
            messagebox.showerror("Error", msg)


if __name__ == "__main__":
    app = App()
    app.mainloop()
