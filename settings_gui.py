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
        "cursor_size_desc": "覆盖层三角光标的边长。太小看不清，太大遮挡内容。",
        "border_width": "边框粗细 (px)",
        "border_width_desc": "三角光标深色边框的宽度。0 = 无边框。",
        "interior_alpha": "内部透明度 (0-255)",
        "interior_alpha_desc": "光标内部填充的透明度。0 = 全透明，255 = 完全不透明。",
        "move_throttle": "移动节流 (px)",
        "move_throttle_desc": "副鼠标移动时，距上次位置小于此像素数则跳过 SendInput。增大可降低 CPU 占用，但光标可能不够跟手。",
        "hover_threshold": "悬停接管等待 (秒)",
        "hover_threshold_desc": "副鼠标要移动系统光标（触发悬停提示），需等待主鼠标静止的时长。避免两手同时移动时光标闪烁。",
        "stationary_timeout": "静止显示等待 (秒)",
        "stationary_timeout_desc": "主鼠标停止移动后，多久重新显示其覆盖层光标。",
        "secondary_hover": "副鼠标悬停 (开关)",
        "secondary_hover_desc": "关闭后副鼠标不再移动系统光标，悬停提示不会出现，但主副光标视觉上完全独立。",
        "colors_section": "颜色",
        "colors_desc": "点击「选择...」为每个鼠标挑选光标颜色。内置光标为三角形，自定义 PNG 图片时此颜色无效。",
        "primary_mouse": "主鼠标",
        "secondary_mouse": "副鼠标 {}",
        "apply": "应用",
        "reset": "恢复默认",
        "pick": "选择...",
        "saved": "已保存！重启多鼠标程序后生效。",
        "reset_done": "已恢复默认值，点击应用保存。",
        "lang_btn": "EN",
        "desc_title": "参数说明",
        "desc_default": "鼠标悬停或点击某个参数查看说明。",
    },
    "en": {
        "title": "Multi-Mouse Settings",
        "cursor_size": "Cursor Size (px)",
        "cursor_size_desc": "Side length of the triangular overlay cursor. Too small = hard to see, too large = obscures content.",
        "border_width": "Border Width (px)",
        "border_width_desc": "Width of the dark border around the triangle. 0 = no border.",
        "interior_alpha": "Interior Alpha (0-255)",
        "interior_alpha_desc": "Transparency of the cursor interior fill. 0 = fully transparent, 255 = fully opaque.",
        "move_throttle": "Move Throttle (px)",
        "move_throttle_desc": "Skip SendInput for secondary mouse moves smaller than this distance. Higher = lower CPU but less responsive cursor.",
        "hover_threshold": "Hover Threshold (sec)",
        "hover_threshold_desc": "How long the primary mouse must be idle before the secondary mouse can move the system cursor for hover effects. Prevents flickering when both mice move.",
        "stationary_timeout": "Stationary Timeout (sec)",
        "stationary_timeout_desc": "How long the primary mouse must be still before its overlay cursor reappears.",
        "secondary_hover": "Secondary Hover (toggle)",
        "secondary_hover_desc": "When off, the secondary mouse never moves the system cursor — hover tooltips won't appear, but both cursors are visually fully independent.",
        "colors_section": "Colors",
        "colors_desc": "Click 'Pick...' to select a cursor color for each mouse. Does not affect custom PNG cursors.",
        "primary_mouse": "Primary Mouse",
        "secondary_mouse": "Secondary Mouse {}",
        "apply": "Apply",
        "reset": "Reset Defaults",
        "pick": "Pick...",
        "saved": "Saved! Restart the multi-mouse program to apply changes.",
        "reset_done": "Defaults restored. Click Apply to save.",
        "lang_btn": "中文",
        "desc_title": "Description",
        "desc_default": "Hover or click a parameter to see its description.",
    },
}

PARAM_DESC_KEYS = {
    "cursor_size": "cursor_size_desc",
    "border_width": "border_width_desc",
    "interior_alpha": "interior_alpha_desc",
    "move_throttle": "move_throttle_desc",
    "hover_threshold": "hover_threshold_desc",
    "stationary_timeout": "stationary_timeout_desc",
    "secondary_hover": "secondary_hover_desc",
    "colors": "colors_desc",
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
        self._param_rows = []
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

        # Language toggle
        lang_frame = ttk.Frame(self.root)
        lang_frame.pack(fill="x", padx=10, pady=(10, 0))
        self._lang_btn = ttk.Button(lang_frame, text=self.s("lang_btn"), command=self._toggle_language, width=4)
        self._lang_btn.pack(side="right")

        # Main content: left=parameters, right=description
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Left panel — parameters
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        row = 0
        # Cursor Size
        self._add_param_row(left_frame, row, "cursor_size", "size_var", tk.IntVar(value=self.cfg.get("cursor_size", 14)),
                            tk.Spinbox, dict(from_=6, to=64))
        row += 1

        # Border
        self._add_param_row(left_frame, row, "border_width", "border_var", tk.IntVar(value=self.cfg.get("overlay_border_px", 2)),
                            tk.Spinbox, dict(from_=0, to=10))
        row += 1

        # Alpha
        self._add_param_row(left_frame, row, "interior_alpha", "alpha_var", tk.IntVar(value=self.cfg.get("overlay_interior_alpha", 180)),
                            tk.Spinbox, dict(from_=0, to=255))
        row += 1

        # Throttle
        self._add_param_row(left_frame, row, "move_throttle", "throttle_var", tk.IntVar(value=self.cfg.get("move_throttle_px", 3)),
                            tk.Spinbox, dict(from_=0, to=20))
        row += 1

        # Hover threshold
        self._add_param_row(left_frame, row, "hover_threshold", "hover_var", tk.DoubleVar(value=self.cfg.get("hover_threshold", 0.2)),
                            tk.Spinbox, dict(from_=0.05, to=2.0, increment=0.05))
        row += 1

        # Stationary timeout
        self._add_param_row(left_frame, row, "stationary_timeout", "stationary_var", tk.DoubleVar(value=self.cfg.get("overlay_stationary_timeout", 0.25)),
                            tk.Spinbox, dict(from_=0.05, to=2.0, increment=0.05))
        row += 1

        # Hover toggle
        hover_frame = ttk.Frame(left_frame)
        hover_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        self._hover_enabled = tk.BooleanVar(value=self.cfg.get("secondary_hover_enabled", True))
        self._hover_cb = ttk.Checkbutton(hover_frame, text=self.s("secondary_hover"), variable=self._hover_enabled)
        self._hover_cb.pack(side="left")
        self._hover_cb.bind("<Enter>", lambda e: self._show_desc("secondary_hover"))
        self._param_rows.append((hover_frame, "secondary_hover"))
        row += 1

        # Colors
        ttk.Separator(left_frame, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=8)
        row += 1
        colors_label = ttk.Label(left_frame, text=self.s("colors_section"), font=("", 10, "bold"))
        colors_label.grid(row=row, column=0, columnspan=2, sticky="w")
        colors_label.bind("<Enter>", lambda e: self._show_desc("colors"))
        row += 1

        # Primary
        fr = ttk.Frame(left_frame)
        fr.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(fr, text=self.s("primary_mouse"), width=18).pack(side="left")
        self._add_color_swatch(fr, "primary_color", None)
        fr.bind("<Enter>", lambda e: self._show_desc("colors"))
        row += 1

        # Secondary
        for i in range(len(self.cfg.get("secondary_colors", []))):
            fr = ttk.Frame(left_frame)
            fr.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            ttk.Label(fr, text=self.s("secondary_mouse", i + 1), width=18).pack(side="left")
            self._add_color_swatch(fr, None, secondary_idx=i)
            fr.bind("<Enter>", lambda e: self._show_desc("colors"))
            row += 1

        # Buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text=self.s("apply"), command=self._apply).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=self.s("reset"), command=self._reset).pack(side="left", padx=5)

        # Right panel — description
        right_frame = ttk.LabelFrame(main_frame, text=self.s("desc_title"), padding=10, width=280, height=300)
        right_frame.pack(side="right", fill="both", expand=True)
        right_frame.pack_propagate(False)
        self._desc_label = tk.Label(right_frame, text=self.s("desc_default"), wraplength=250, justify="left",
                                    anchor="nw", font=("", 9))
        self._desc_label.pack(fill="both", expand=True)

    def _add_param_row(self, parent, row, key, var_name, var, widget_cls, widget_kw):
        lbl = ttk.Label(parent, text=self.s(key), width=22)
        lbl.grid(row=row, column=0, sticky="w", pady=3)
        w = widget_cls(parent, textvariable=var, width=5, **widget_kw)
        w.grid(row=row, column=1, sticky="w", pady=3)
        setattr(self, f"_{var_name}", var)
        lbl.bind("<Enter>", lambda e: self._show_desc(key))
        w.bind("<Enter>", lambda e: self._show_desc(key))
        self._param_rows.append((lbl, key))

    def _add_color_swatch(self, parent, key, secondary_idx=None):
        if secondary_idx is not None:
            rgb = self.cfg["secondary_colors"][secondary_idx]
            store_key = f"secondary_{secondary_idx}"
        else:
            rgb = self.cfg.get(key, [160, 160, 160])
            store_key = key

        swatch = tk.Label(parent, text="   ", bg=rgb_to_hex(*rgb), relief="ridge", width=4)
        swatch.pack(side="left", padx=5)

        btn = ttk.Button(parent, text=self.s("pick"),
                         command=lambda k=key, idx=secondary_idx: self._pick_color(k, idx))
        btn.pack(side="left", padx=5)
        self._color_swatches[store_key] = (swatch, rgb)

    def _show_desc(self, key):
        desc_key = PARAM_DESC_KEYS.get(key)
        if desc_key:
            self._desc_label.configure(text=self.s(desc_key))
        else:
            self._desc_label.configure(text=self.s("desc_default"))

    def _pick_color(self, key, idx):
        if idx is not None:
            current = self.cfg["secondary_colors"][idx]
        else:
            current = self.cfg.get("primary_color", [160, 160, 160])

        hex_color = rgb_to_hex(*current)
        result = colorchooser.askcolor(initialcolor=hex_color, title="Pick Color")
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
        self._hover_cb.configure(text=self.s("secondary_hover"))
        self._desc_label.configure(text=self.s("desc_default"))

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
