"""Multi-Mouse Settings Panel — GUI configuration editor."""
import json
import os
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


class SettingsPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Mouse Settings")
        self.root.resizable(False, False)
        self.cfg = load_config()
        self._color_swatches = {}
        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill="both", expand=True)

        row = 0

        # ---- Cursor Size ----
        ttk.Label(frame, text="Cursor Size (px)").grid(row=row, column=0, sticky="w", pady=3)
        self._size_var = tk.IntVar(value=self.cfg.get("cursor_size", 14))
        ttk.Spinbox(frame, from_=6, to=64, textvariable=self._size_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Overlay Border ----
        ttk.Label(frame, text="Border Width (px)").grid(row=row, column=0, sticky="w", pady=3)
        self._border_var = tk.IntVar(value=self.cfg.get("overlay_border_px", 2))
        ttk.Spinbox(frame, from_=0, to=10, textvariable=self._border_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Interior Alpha ----
        ttk.Label(frame, text="Interior Alpha (0-255)").grid(row=row, column=0, sticky="w", pady=3)
        self._alpha_var = tk.IntVar(value=self.cfg.get("overlay_interior_alpha", 180))
        ttk.Spinbox(frame, from_=0, to=255, textvariable=self._alpha_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Move Throttle ----
        ttk.Label(frame, text="Move Throttle (px)").grid(row=row, column=0, sticky="w", pady=3)
        self._throttle_var = tk.IntVar(value=self.cfg.get("move_throttle_px", 3))
        ttk.Spinbox(frame, from_=0, to=20, textvariable=self._throttle_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Hover Threshold ----
        ttk.Label(frame, text="Hover Threshold (sec)").grid(row=row, column=0, sticky="w", pady=3)
        self._hover_var = tk.DoubleVar(value=self.cfg.get("hover_threshold", 0.2))
        ttk.Spinbox(frame, from_=0.05, to=2.0, increment=0.05, textvariable=self._hover_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Stationary Timeout ----
        ttk.Label(frame, text="Stationary Timeout (sec)").grid(row=row, column=0, sticky="w", pady=3)
        self._stationary_var = tk.DoubleVar(value=self.cfg.get("overlay_stationary_timeout", 0.25))
        ttk.Spinbox(frame, from_=0.05, to=2.0, increment=0.05, textvariable=self._stationary_var, width=6).grid(
            row=row, column=1, sticky="w", pady=3
        )
        row += 1

        # ---- Secondary Hover ----
        self._hover_enabled = tk.BooleanVar(value=self.cfg.get("secondary_hover_enabled", True))
        ttk.Checkbutton(frame, text="Secondary Mouse Hover", variable=self._hover_enabled).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=5
        )
        row += 1

        # ---- Separator ----
        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # ---- Colors ----
        ttk.Label(frame, text="Colors", font=("", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        # Primary color
        self._add_color_row(frame, row, "Primary Mouse", "primary_color")
        row += 1

        # Secondary colors
        for i, color in enumerate(self.cfg.get("secondary_colors", [])):
            self._add_color_row(frame, row, f"Secondary Mouse {i+1}", f"secondary_{i}", i=0)
            row += 1

        # ---- Buttons ----
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Apply", command=self._apply).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Reset Defaults", command=self._reset).pack(side="left", padx=5)

    def _add_color_row(self, frame, row, label, key, secondary_idx=None):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)

        if secondary_idx is not None:
            rgb = self.cfg["secondary_colors"][secondary_idx]
        else:
            rgb = self.cfg.get("primary_color", [160, 160, 160])

        swatch = tk.Label(frame, text="   ", bg=rgb_to_hex(*rgb), relief="ridge", width=4)
        swatch.grid(row=row, column=1, sticky="w", pady=2)

        btn = ttk.Button(frame, text="Pick...", command=lambda k=key, idx=secondary_idx: self._pick_color(k, idx))
        btn.grid(row=row, column=2, sticky="w", padx=5)
        self._color_swatches[key] = (swatch, rgb)

    def _pick_color(self, key, idx):
        if idx is not None:
            current = self.cfg["secondary_colors"][idx]
            result = self._change_color(key, current)
            if result:
                self.cfg["secondary_colors"][idx] = list(result)
        else:
            current = self.cfg.get("primary_color", [160, 160, 160])
            result = self._change_color(key, current)
            if result:
                self.cfg[key] = list(result)

    @staticmethod
    def _change_color(key, current):
        hex_color = rgb_to_hex(*current)
        result = colorchooser.askcolor(initialcolor=hex_color, title=f"Pick {key}")
        if result and result[0]:
            return tuple(int(c) for c in result[0])
        return None

    def _apply(self):
        self.cfg["cursor_size"] = self._size_var.get()
        self.cfg["overlay_border_px"] = self._border_var.get()
        self.cfg["overlay_interior_alpha"] = self._alpha_var.get()
        self.cfg["move_throttle_px"] = self._throttle_var.get()
        self.cfg["hover_threshold"] = self._hover_var.get()
        self.cfg["overlay_stationary_timeout"] = self._stationary_var.get()
        self.cfg["secondary_hover_enabled"] = self._hover_enabled.get()
        save_config(self.cfg)
        messagebox.showinfo("Settings", "Saved! Restart the multi-mouse program to apply changes.")

    def _reset(self):
        self._size_var.set(14)
        self._border_var.set(2)
        self._alpha_var.set(180)
        self._throttle_var.set(3)
        self._hover_var.set(0.2)
        self._stationary_var.set(0.25)
        self._hover_enabled.set(True)
        messagebox.showinfo("Settings", "Defaults restored. Click Apply to save.")


def main():
    root = tk.Tk()
    SettingsPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
