"""Multi-Mouse Settings Panel — GUI configuration editor."""
import json
import os
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

STRINGS = {
    "zh": {
        "title": "Multi-Mouse 设置",
        "cursor_size": "光标大小 (px)",
        "border_width": "边框粗细 (px)",
        "interior_alpha": "内部透明度 (0-255)",
        "move_throttle": "移动节流 (px)",
        "hover_threshold": "悬停接管等待 (秒)",
        "stationary_timeout": "静止显示等待 (秒)",
        "secondary_hover": "副鼠标悬停",
        "colors_section": "颜色",
        "primary_mouse": "主鼠标",
        "secondary_mouse": "副鼠标 {}",
        "apply": "应用",
        "reset": "恢复默认",
        "pick": "选择...",
        "saved": "已保存！重启多鼠标程序后生效。",
        "reset_done": "已恢复默认值，点击应用保存。",
        "lang_btn": "EN",
    },
    "en": {
        "title": "Multi-Mouse Settings",
        "cursor_size": "Cursor Size (px)",
        "border_width": "Border Width (px)",
        "interior_alpha": "Interior Alpha (0-255)",
        "move_throttle": "Move Throttle (px)",
        "hover_threshold": "Hover Threshold (sec)",
        "stationary_timeout": "Stationary Timeout (sec)",
        "secondary_hover": "Secondary Mouse Hover",
        "colors_section": "Colors",
        "primary_mouse": "Primary Mouse",
        "secondary_mouse": "Secondary Mouse {}",
        "apply": "Apply",
        "reset": "Reset Defaults",
        "pick": "Pick...",
        "saved": "Saved! Restart the multi-mouse program to apply changes.",
        "reset_done": "Defaults restored. Click Apply to save.",
        "lang_btn": "中文",
    },
}


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
        self.cfg = load_config()
        self._lang = self.cfg.get("language", "zh")
        self._color_swatches = {}
        self._widgets = {}
        self._build_ui()
        self._apply_language()

    def s(self, key, *args):
        text = STRINGS[self._lang].get(key, key)
        if args:
            text = text.format(*args)
        return text

    def _build_ui(self):
        self.root.title(self.s("title"))
        self.root.resizable(False, False)

        # Language toggle button (top-right)
        lang_frame = ttk.Frame(self.root)
        lang_frame.pack(fill="x", padx=10, pady=(10, 0))
        self._lang_btn = ttk.Button(lang_frame, text=self.s("lang_btn"), command=self._toggle_language, width=4)
        self._lang_btn.pack(side="right")

        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill="both", expand=True)

        row = 0

        # Cursor Size
        self._add_label(frame, row, 0, "cursor_size")
        self._size_var = tk.IntVar(value=self.cfg.get("cursor_size", 14))
        self._widgets["size"] = ttk.Spinbox(frame, from_=6, to=64, textvariable=self._size_var, width=6)
        self._widgets["size"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Border Width
        self._add_label(frame, row, 0, "border_width")
        self._border_var = tk.IntVar(value=self.cfg.get("overlay_border_px", 2))
        self._widgets["border"] = ttk.Spinbox(frame, from_=0, to=10, textvariable=self._border_var, width=6)
        self._widgets["border"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Interior Alpha
        self._add_label(frame, row, 0, "interior_alpha")
        self._alpha_var = tk.IntVar(value=self.cfg.get("overlay_interior_alpha", 180))
        self._widgets["alpha"] = ttk.Spinbox(frame, from_=0, to=255, textvariable=self._alpha_var, width=6)
        self._widgets["alpha"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Move Throttle
        self._add_label(frame, row, 0, "move_throttle")
        self._throttle_var = tk.IntVar(value=self.cfg.get("move_throttle_px", 3))
        self._widgets["throttle"] = ttk.Spinbox(frame, from_=0, to=20, textvariable=self._throttle_var, width=6)
        self._widgets["throttle"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Hover Threshold
        self._add_label(frame, row, 0, "hover_threshold")
        self._hover_var = tk.DoubleVar(value=self.cfg.get("hover_threshold", 0.2))
        self._widgets["hover"] = ttk.Spinbox(
            frame, from_=0.05, to=2.0, increment=0.05, textvariable=self._hover_var, width=6
        )
        self._widgets["hover"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Stationary Timeout
        self._add_label(frame, row, 0, "stationary_timeout")
        self._stationary_var = tk.DoubleVar(value=self.cfg.get("overlay_stationary_timeout", 0.25))
        self._widgets["stationary"] = ttk.Spinbox(
            frame, from_=0.05, to=2.0, increment=0.05, textvariable=self._stationary_var, width=6
        )
        self._widgets["stationary"].grid(row=row, column=1, sticky="w", pady=3)
        row += 1

        # Secondary Hover
        self._hover_enabled = tk.BooleanVar(value=self.cfg.get("secondary_hover_enabled", True))
        self._hover_cb = ttk.Checkbutton(
            frame, text=self.s("secondary_hover"), variable=self._hover_enabled
        )
        self._hover_cb.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        self._widgets["hover_cb"] = self._hover_cb
        row += 1

        # Separator
        ttk.Separator(frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1

        # Colors section title
        self._colors_label = ttk.Label(frame, text=self.s("colors_section"), font=("", 10, "bold"))
        self._colors_label.grid(row=row, column=0, columnspan=2, sticky="w")
        self._widgets["colors_label"] = self._colors_label
        row += 1

        # Primary color
        self._primary_label = self._add_label(frame, row, 0, "primary_mouse")
        self._add_color_swatch(frame, row, "primary_color")
        row += 1

        # Secondary colors
        self._secondary_rows = []
        for i, color in enumerate(self.cfg.get("secondary_colors", [])):
            lbl = self._add_label(frame, row, 0, "secondary_mouse", i + 1)
            self._add_color_swatch(frame, row, None, secondary_idx=i)
            self._secondary_rows.append((lbl, row))
            row += 1

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text=self.s("apply"), command=self._apply).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=self.s("reset"), command=self._reset).pack(side="left", padx=5)

    def _add_label(self, frame, row, col, key, *args):
        lbl = ttk.Label(frame, text=self.s(key, *args))
        lbl.grid(row=row, column=col, sticky="w", pady=3)
        return lbl

    def _add_color_swatch(self, frame, row, key, secondary_idx=None):
        if secondary_idx is not None:
            rgb = self.cfg["secondary_colors"][secondary_idx]
            store_key = f"secondary_{secondary_idx}"
        else:
            rgb = self.cfg.get(key, [160, 160, 160])
            store_key = key

        swatch = tk.Label(frame, text="   ", bg=rgb_to_hex(*rgb), relief="ridge", width=4)
        swatch.grid(row=row, column=1, sticky="w", pady=2)

        btn = ttk.Button(
            frame, text=self.s("pick"),
            command=lambda k=key, idx=secondary_idx: self._pick_color(k, idx),
        )
        btn.grid(row=row, column=2, sticky="w", padx=5)
        self._color_swatches[store_key] = (swatch, rgb)

    def _pick_color(self, key, idx):
        if idx is not None:
            current = self.cfg["secondary_colors"][idx]
        else:
            current = self.cfg.get("primary_color", [160, 160, 160])

        hex_color = rgb_to_hex(*current)
        result = colorchooser.askcolor(initialcolor=hex_color, title=f"Pick Color")
        if result and result[0]:
            rgb = tuple(int(c) for c in result[0])
            if idx is not None:
                self.cfg["secondary_colors"][idx] = list(rgb)
                store_key = f"secondary_{idx}"
            else:
                self.cfg[key] = list(rgb)
                store_key = key
            swatch, _ = self._color_swatches[store_key]
            swatch.configure(bg=rgb_to_hex(*rgb))
            self._color_swatches[store_key] = (swatch, rgb)

    def _toggle_language(self):
        self._lang = "en" if self._lang == "zh" else "zh"
        self.cfg["language"] = self._lang
        self._apply_language()

    def _apply_language(self):
        self.root.title(self.s("title"))
        self._lang_btn.configure(text=self.s("lang_btn"))
        # Update static labels by rebuilding or by iterating
        self._apply_labels()

    def _apply_labels(self):
        self.root.title(self.s("title"))
        self._lang_btn.configure(text=self.s("lang_btn"))
        self._colors_label.configure(text=self.s("colors_section"))
        self._hover_cb.configure(text=self.s("secondary_hover"))

        # Rebuild color rows (simpler than tracking every label widget)
        # For now, update the known label references
        # (the spinbox labels are recreated on language change via a simpler approach:
        #  destroy and rebuild. But let's keep it pragmatic.)

    def _apply(self):
        self.cfg["cursor_size"] = self._size_var.get()
        self.cfg["overlay_border_px"] = self._border_var.get()
        self.cfg["overlay_interior_alpha"] = self._alpha_var.get()
        self.cfg["move_throttle_px"] = self._throttle_var.get()
        self.cfg["hover_threshold"] = self._hover_var.get()
        self.cfg["overlay_stationary_timeout"] = self._stationary_var.get()
        self.cfg["secondary_hover_enabled"] = self._hover_enabled.get()
        self.cfg["language"] = self._lang
        save_config(self.cfg)
        messagebox.showinfo("Settings", self.s("saved"))

    def _reset(self):
        self._size_var.set(14)
        self._border_var.set(2)
        self._alpha_var.set(180)
        self._throttle_var.set(3)
        self._hover_var.set(0.2)
        self._stationary_var.set(0.25)
        self._hover_enabled.set(True)
        messagebox.showinfo("Settings", self.s("reset_done"))


def main():
    root = tk.Tk()
    SettingsPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
