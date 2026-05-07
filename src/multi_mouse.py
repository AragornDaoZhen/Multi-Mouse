"""
Multi-Mouse Support for Windows
================================
Allows multiple physical mice to work simultaneously with independent cursors.

Uses Windows Raw Input API to distinguish between different physical mice.
Each mouse gets its own cursor: the primary mouse controls the system cursor,
while additional mice show colored overlay indicators and can click independently.

Requires: Windows Vista+ (uses RIDEV_CAPTUREMOUSE for input isolation)
"""

import ctypes
from ctypes import wintypes, POINTER, Structure, Union, sizeof, byref, cast, c_void_p
import ctypes.wintypes as w
import threading
import sys
import time
import math
import os
import json
import atexit

# ============================================================================
# Config loader
# ============================================================================

def load_config():
    """Load config.json from the project directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    config_path = os.path.join(project_dir, "config.json")
    defaults = {
        "cursor_size": 14,
        "primary_color": [160, 160, 160],
        "secondary_colors": [[60, 140, 255], [80, 200, 80], [255, 80, 80], [255, 180, 50]],
        "hover_threshold": 0.2,
        "overlay_stationary_timeout": 0.25,
        "move_throttle_px": 3,
        "overlay_border_px": 2,
        "overlay_interior_alpha": 180,
        "secondary_hover_enabled": True,
    }
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user = json.load(f)
        for k, v in defaults.items():
            if k not in user:
                user[k] = v
        return user
    except Exception:
        return defaults

# ============================================================================
# Win32 API Bindings
# ============================================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

# --- Window Messages ---
WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012

# --- Raw Input ---
RIM_TYPEMOUSE = 0
RID_INPUT = 0x10000003
RID_HEADER = 0x10000005
RIDI_DEVICENAME = 0x20000007
RIDEV_INPUTSINK = 0x00000100
RIDEV_CAPTUREMOUSE = 0x00000200
RIDEV_NOLEGACY = 0x00000030
RIDEV_REMOVE = 0x00000001

# --- Low-level mouse hook ---
WH_MOUSE_LL = 14
LLMHF_INJECTED = 0x00000001

# --- GDI+ for PNG loading ---
class GdiplusStartupInput(Structure):
    _fields_ = [
        ("GdiplusVersion", w.DWORD),
        ("DebugEventCallback", c_void_p),
        ("SuppressBackgroundThread", w.BOOL),
        ("SuppressExternalCodecs", w.BOOL),
    ]

_gdiplus_token = ctypes.c_ulong(0)
_gdiplus_initialized = False

def _init_gdiplus():
    global _gdiplus_initialized, _gdiplus_token
    if _gdiplus_initialized:
        return True
    gdiplus = ctypes.windll.gdiplus
    gdiplus.GdiplusStartup.argtypes = [
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(GdiplusStartupInput),
        c_void_p,
    ]
    gdiplus.GdiplusStartup.restype = w.DWORD
    si = GdiplusStartupInput()
    si.GdiplusVersion = 1
    status = gdiplus.GdiplusStartup(
        byref(_gdiplus_token), byref(si), None
    )
    if status == 0:
        gdiplus.GdipLoadImageFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(c_void_p)]
        gdiplus.GdipLoadImageFromFile.restype = w.DWORD
        gdiplus.GdipGetImageWidth.argtypes = [c_void_p, ctypes.POINTER(w.UINT)]
        gdiplus.GdipGetImageWidth.restype = w.DWORD
        gdiplus.GdipGetImageHeight.argtypes = [c_void_p, ctypes.POINTER(w.UINT)]
        gdiplus.GdipGetImageHeight.restype = w.DWORD
        gdiplus.GdipCreateFromHDC.argtypes = [w.HDC, ctypes.POINTER(c_void_p)]
        gdiplus.GdipCreateFromHDC.restype = w.DWORD
        gdiplus.GdipDrawImageRectI.argtypes = [c_void_p, c_void_p, w.INT, w.INT, w.INT, w.INT]
        gdiplus.GdipDrawImageRectI.restype = w.DWORD
        gdiplus.GdipDeleteGraphics.argtypes = [c_void_p]
        gdiplus.GdipDeleteGraphics.restype = w.DWORD
        gdiplus.GdipDisposeImage.argtypes = [c_void_p]
        gdiplus.GdipDisposeImage.restype = w.DWORD
        _gdiplus_initialized = True
        return True
    return False

def _load_png_to_dib(filepath, target_w, target_h):
    """Load a PNG file and render it into a 32-bit BGRA DIB at target size."""
    if not _init_gdiplus():
        return None, None

    gdiplus = ctypes.windll.gdiplus

    img = c_void_p()
    status = gdiplus.GdipLoadImageFromFile(str(filepath), byref(img))
    if status != 0 or not img:
        return None, None

    # Get original dimensions
    src_w = w.UINT()
    src_h = w.UINT()
    gdiplus.GdipGetImageWidth(img, byref(src_w))
    gdiplus.GdipGetImageHeight(img, byref(src_h))

    if src_w.value == 0 or src_h.value == 0:
        gdiplus.GdipDisposeImage(img)
        return None, None

    # Create target 32-bit DIB
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = target_w
    bmi.bmiHeader.biHeight = -target_h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0

    ppv_bits = c_void_p()
    hbmp = gdi32.CreateDIBSection(mem_dc, byref(bmi), DIB_RGB_COLORS, byref(ppv_bits), None, 0)
    pixels = ctypes.cast(ppv_bits, ctypes.POINTER(ctypes.c_uint32))

    old_bmp = gdi32.SelectObject(mem_dc, hbmp)

    # Draw image onto DIB using GDI+
    graphics = c_void_p()
    gdiplus.GdipCreateFromHDC(mem_dc, byref(graphics))
    gdiplus.GdipDrawImageRectI(
        graphics, img, 0, 0, target_w, target_h
    )

    # GDI+ may not set alpha correctly on some DIB formats.
    # Fix: if a pixel has color but no alpha, make it fully opaque.
    pixel_count = target_w * target_h
    for i in range(pixel_count):
        px = pixels[i]
        if (px & 0x00FFFFFF) != 0 and (px & 0xFF000000) == 0:
            pixels[i] = px | 0xFF000000

    # Cleanup
    gdiplus.GdipDeleteGraphics(graphics)
    gdiplus.GdipDisposeImage(img)
    gdi32.SelectObject(mem_dc, old_bmp)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(None, screen_dc)

    return hbmp, pixels

MOUSE_MOVE_RELATIVE = 0
MOUSE_MOVE_ABSOLUTE = 1

RI_MOUSE_LEFT_BUTTON_DOWN = 0x0001
RI_MOUSE_LEFT_BUTTON_UP = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP = 0x0008
RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010
RI_MOUSE_MIDDLE_BUTTON_UP = 0x0020
RI_MOUSE_WHEEL = 0x0400
RI_MOUSE_HWHEEL = 0x0800

# --- Window Styles ---
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
WS_OVERLAPPED = 0x00000000

# --- Layered Window ---
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

# --- GDI ---
DIB_RGB_COLORS = 0

# --- System Metrics ---
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77

# --- SetWindowPos ---
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# --- SendInput ---
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# ============================================================================
# Structures
# ============================================================================

class POINT(Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]

class SIZE(Structure):
    _fields_ = [("cx", w.LONG), ("cy", w.LONG)]

class MSLLHOOKSTRUCT(Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", w.DWORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", c_void_p),
    ]

class MSG(Structure):
    _fields_ = [
        ("hwnd", w.HWND),
        ("message", w.UINT),
        ("wParam", w.WPARAM),
        ("lParam", w.LPARAM),
        ("time", w.DWORD),
        ("pt", POINT),
    ]

class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", w.USHORT),
        ("usUsage", w.USHORT),
        ("dwFlags", w.DWORD),
        ("hwndTarget", w.HWND),
    ]

class RAWMOUSE(Structure):
    _fields_ = [
        ("usFlags", w.USHORT),
        ("ulButtons", w.ULONG),
        ("ulRawButtons", w.ULONG),
        ("lLastX", w.LONG),
        ("lLastY", w.LONG),
        ("ulExtraInformation", w.ULONG),
    ]

class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType", w.DWORD),
        ("dwSize", w.DWORD),
        ("hDevice", w.HANDLE),
        ("wParam", w.WPARAM),
    ]

class RAWINPUT(Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]

class WNDCLASSEX(Structure):
    _fields_ = [
        ("cbSize", w.UINT),
        ("style", w.UINT),
        ("lpfnWndProc", c_void_p),
        ("cbClsExtra", w.INT),
        ("cbWndExtra", w.INT),
        ("hInstance", w.HINSTANCE),
        ("hIcon", w.HICON),
        ("hCursor", w.HANDLE),
        ("hbrBackground", w.HANDLE),
        ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
        ("hIconSm", w.HICON),
    ]

class BITMAPINFOHEADER(Structure):
    _fields_ = [
        ("biSize", w.DWORD),
        ("biWidth", w.LONG),
        ("biHeight", w.LONG),
        ("biPlanes", w.WORD),
        ("biBitCount", w.WORD),
        ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD),
        ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG),
        ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]

class BITMAPINFO(Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

class BLENDFUNCTION(Structure):
    _fields_ = [
        ("BlendOp", w.BYTE),
        ("BlendFlags", w.BYTE),
        ("SourceConstantAlpha", w.BYTE),
        ("AlphaFormat", w.BYTE),
    ]

class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", w.LONG),
        ("dy", w.LONG),
        ("mouseData", w.DWORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", c_void_p),
    ]

class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", w.WORD),
        ("wScan", w.WORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", c_void_p),
    ]

class HARDWAREINPUT(Structure):
    _fields_ = [
        ("uMsg", w.DWORD),
        ("wParamL", w.WORD),
        ("wParamH", w.WORD),
    ]

class INPUT_UNION(Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT_STRUCT(Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", w.DWORD),
        ("u", INPUT_UNION),
    ]

# ============================================================================
# Function Prototypes
# ============================================================================

def _setup_prototypes():
    user32.RegisterRawInputDevices.argtypes = [c_void_p, w.UINT, w.UINT]
    user32.RegisterRawInputDevices.restype = w.BOOL

    user32.GetRawInputData.argtypes = [w.HANDLE, w.UINT, c_void_p, ctypes.POINTER(w.UINT), w.UINT]
    user32.GetRawInputData.restype = w.UINT

    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
    user32.RegisterClassExW.restype = w.ATOM

    user32.CreateWindowExW.argtypes = [
        w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
        w.INT, w.INT, w.INT, w.INT,
        w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID,
    ]
    user32.CreateWindowExW.restype = w.HWND

    user32.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user32.DefWindowProcW.restype = w.LPARAM

    user32.DestroyWindow.argtypes = [w.HWND]
    user32.DestroyWindow.restype = w.BOOL

    user32.SetWindowPos.argtypes = [w.HWND, w.HWND, w.INT, w.INT, w.INT, w.INT, w.UINT]
    user32.SetWindowPos.restype = w.BOOL

    user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user32.PostMessageW.restype = w.BOOL

    user32.PostQuitMessage.argtypes = [w.INT]
    user32.PostQuitMessage.restype = None

    user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), w.HWND, w.UINT, w.UINT]
    user32.GetMessageW.restype = w.BOOL

    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), w.HWND, w.UINT, w.UINT, w.UINT]
    user32.PeekMessageW.restype = w.BOOL

    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.TranslateMessage.restype = w.BOOL

    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.restype = w.LPARAM

    user32.GetSystemMetrics.argtypes = [w.INT]
    user32.GetSystemMetrics.restype = w.INT

    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = w.BOOL

    user32.SetCursorPos.argtypes = [w.INT, w.INT]
    user32.SetCursorPos.restype = w.BOOL

    user32.ShowWindow.argtypes = [w.HWND, w.INT]
    user32.ShowWindow.restype = w.BOOL

    user32.UpdateLayeredWindow.argtypes = [
        w.HWND, w.HDC,
        ctypes.POINTER(POINT),
        ctypes.POINTER(SIZE),
        w.HDC,
        ctypes.POINTER(POINT),
        w.COLORREF,
        ctypes.POINTER(BLENDFUNCTION),
        w.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = w.BOOL

    user32.GetDC.argtypes = [w.HWND]
    user32.GetDC.restype = w.HDC

    user32.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user32.ReleaseDC.restype = w.INT

    user32.SendInput.argtypes = [w.UINT, c_void_p, w.INT]
    user32.SendInput.restype = w.UINT

    gdi32.CreateCompatibleDC.argtypes = [w.HDC]
    gdi32.CreateCompatibleDC.restype = w.HDC

    gdi32.DeleteDC.argtypes = [w.HDC]
    gdi32.DeleteDC.restype = w.BOOL

    gdi32.CreateDIBSection.argtypes = [
        w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
        ctypes.POINTER(c_void_p), w.HANDLE, w.DWORD,
    ]
    gdi32.CreateDIBSection.restype = w.HBITMAP

    gdi32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
    gdi32.SelectObject.restype = w.HGDIOBJ

    gdi32.DeleteObject.argtypes = [w.HGDIOBJ]
    gdi32.DeleteObject.restype = w.BOOL

    kernel32.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel32.GetModuleHandleW.restype = w.HINSTANCE

    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = w.DWORD

    # Low-level mouse hook
    user32.SetWindowsHookExW.argtypes = [w.INT, c_void_p, w.HINSTANCE, w.DWORD]
    user32.SetWindowsHookExW.restype = w.HHOOK

    user32.CallNextHookEx.argtypes = [w.HHOOK, w.INT, w.WPARAM, w.LPARAM]
    user32.CallNextHookEx.restype = w.LPARAM

    user32.UnhookWindowsHookEx.argtypes = [w.HHOOK]
    user32.UnhookWindowsHookEx.restype = w.BOOL

_setup_prototypes()

# ============================================================================
# Helper: BGRA pixel value
# ============================================================================

def bgra_pixel(r, g, b, a=255):
    """Create a 32-bit BGRA pixel value for DIB section."""
    return (a << 24) | (r << 16) | (g << 8) | b

# ============================================================================
# Cursor Overlay
# ============================================================================

_overlay_wndprocs = {}
_overlay_instances = {}

class CursorOverlay:
    """A transparent, click-through overlay window showing a cursor image."""

    def __init__(self, color_bgra: int, mouse_id: int, config: dict, image_path = None):
        self.color_bgra = color_bgra
        self.mouse_id = mouse_id
        self.image_path = image_path
        self.hwnd = None
        self.x = 0
        self.y = 0
        self.size = config.get("cursor_size", 14)
        self.border_px = config.get("overlay_border_px", 2)
        self.interior_alpha = config.get("overlay_interior_alpha", 180)
        self._create()

    def _create(self):
        instance = kernel32.GetModuleHandleW(None)
        class_name = f"MMOverlay{self.mouse_id}"

        WNDPROC = ctypes.WINFUNCTYPE(w.LPARAM, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        proc = WNDPROC(wnd_proc)
        _overlay_wndprocs[self.mouse_id] = proc

        wc = WNDCLASSEX()
        wc.cbSize = sizeof(WNDCLASSEX)
        wc.lpfnWndProc = cast(proc, c_void_p)
        wc.hInstance = instance
        wc.lpszClassName = class_name
        wc.hCursor = None
        wc.hbrBackground = None
        user32.RegisterClassExW(byref(wc))

        ex_style = (
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST |
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        )

        self.hwnd = user32.CreateWindowExW(
            ex_style, class_name, f"Cursor{self.mouse_id}",
            WS_POPUP,
            0, 0, self.size, self.size,
            None, None, instance, None,
        )

        _overlay_instances[self.hwnd] = self
        self._render()

    def _render(self):
        """Create the cursor bitmap and apply to the layered window."""
        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.size
        bmi.bmiHeader.biHeight = -self.size
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        ppv_bits = c_void_p()
        hbitmap = gdi32.CreateDIBSection(mem_dc, byref(bmi), DIB_RGB_COLORS, byref(ppv_bits), None, 0)
        pixels = ctypes.cast(ppv_bits, ctypes.POINTER(ctypes.c_uint32))

        # Try loading custom image first
        custom_loaded = False
        if self.image_path:
            custom_hbmp, custom_pixels = _load_png_to_dib(self.image_path, self.size, self.size)
            if custom_pixels is not None:
                pixel_count = self.size * self.size
                for i in range(pixel_count):
                    pixels[i] = custom_pixels[i]
                custom_loaded = True
            else:
                print(f"  (Failed to load custom cursor: {self.image_path})")
            if custom_hbmp:
                gdi32.DeleteObject(custom_hbmp)

        if not custom_loaded:
            self._draw_cursor(pixels, self.size, self.color_bgra)

        old_bmp = gdi32.SelectObject(mem_dc, hbitmap)

        blend = BLENDFUNCTION()
        blend.BlendOp = AC_SRC_OVER
        blend.BlendFlags = 0
        blend.SourceConstantAlpha = 255
        blend.AlphaFormat = AC_SRC_ALPHA

        pt_dst = POINT(self.x, self.y)
        sz = SIZE(self.size, self.size)
        pt_src = POINT(0, 0)

        user32.UpdateLayeredWindow(
            self.hwnd, None,
            byref(pt_dst), byref(sz),
            mem_dc, byref(pt_src),
            0, byref(blend), ULW_ALPHA,
        )

        user32.ShowWindow(self.hwnd, 1)

        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)

    def _draw_cursor(self, pixels, size, color):
        """Draw a right-triangle cursor. Right angle at bottom-left, tip at top-left."""
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        dr = max(0, r - 100)
        dg = max(0, g - 100)
        db = max(0, b - 100)
        border = self.border_px
        alpha = self.interior_alpha

        for y in range(size):
            for x in range(size):
                in_triangle = (y >= x)

                if in_triangle:
                    dh = (y - x) / 1.414
                    dl = float(x)
                    db2 = float(size - 1 - y)
                    edge_dist = min(dh, dl, db2)

                    if edge_dist <= border:
                        pixels[y * size + x] = bgra_pixel(dr, dg, db, 255)
                    else:
                        pixels[y * size + x] = bgra_pixel(r, g, b, alpha)
                else:
                    dh_out = (x - y) / 1.414
                    if dh_out < 1.0:
                        a = int(255 * (1.0 - dh_out))
                        pixels[y * size + x] = bgra_pixel(dr, dg, db, a)
                    else:
                        pixels[y * size + x] = 0x00000000

    def move(self, x, y):
        """Move the overlay so the tip (top-left) is at (x, y)."""
        self.x = x
        self.y = y
        if self.hwnd:
            user32.SetWindowPos(
                self.hwnd, w.HWND(-1),
                x, y,
                0, 0,
                SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def hide(self):
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE

    def show(self):
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNOACTIVATE

    def destroy(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

# ============================================================================
# Multi-Mouse Manager
# ============================================================================

class MultiMouseManager:
    """
    Detects and tracks multiple physical mice on Windows.

    - Uses RIDEV_CAPTUREMOUSE to prevent all mice from moving the system cursor.
    - Primary mouse: system cursor tracks its position; clicks forwarded via SendInput.
    - Secondary mice: colored overlay indicators; clicks forwarded via SendInput.
    - All mice can click independently at their own tracked positions.
    """

    def __init__(self, config: dict = None):
        if config is None:
            config = load_config()
        self.config = config

        self.mice = {}
        self.primary_device = None
        self.msg_hwnd = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self._mouse_id_counter = 0
        self.independent_mode = False
        self.cursor_x = 0
        self.cursor_y = 0

        # Config-driven values
        self.colors = [bgra_pixel(*c) for c in config.get("secondary_colors", [[60, 140, 255]])]
        self.primary_color = bgra_pixel(*config.get("primary_color", [160, 160, 160]))
        self.hover_threshold = config.get("hover_threshold", 0.2)
        self.stationary_timeout = config.get("overlay_stationary_timeout", 0.25)
        self.move_throttle_px = config.get("move_throttle_px", 3)
        self.throttle_sq = self.move_throttle_px * self.move_throttle_px
        self.secondary_hover = config.get("secondary_hover_enabled", True)

        # Cache virtual desktop dims
        self._virt_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self._virt_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self._virt_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CXSCREEN)
        self._virt_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CYSCREEN)

        # Throttle state
        self._last_move_x = -1
        self._last_move_y = -1

    def start(self):
        """Start tracking multiple mice."""
        self.running = True
        self.thread = threading.Thread(target=self._message_loop, daemon=False)
        self.thread.start()

        for _ in range(50):
            if self.msg_hwnd is not None:
                break
            time.sleep(0.02)

        if self.msg_hwnd is None:
            raise RuntimeError("Failed to create message window. Try running as administrator?")

        if self.independent_mode:
            mode_desc = "Independent - each mouse has its own cursor"
        else:
            mode_desc = "Shared-cursor - system cursor follows most recent mouse"

        print("=" * 54)
        print(f"  Mode: {mode_desc}")
        print("  Primary mouse:  controls the system cursor")
        print("  Secondary mice: shown as colored dot indicators")
        print("  Press Ctrl+C to exit")
        print("=" * 54)

    def stop(self):
        """Stop tracking, deregister raw input, and clean up resources."""
        self.running = False

        # Remove low-level mouse hook
        if hasattr(self, '_ll_hook') and self._ll_hook:
            user32.UnhookWindowsHookEx(self._ll_hook)
            self._ll_hook = None

        # Deregister raw input to restore normal mouse behavior
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01
        rid.usUsage = 0x02
        rid.dwFlags = RIDEV_REMOVE
        rid.hwndTarget = None
        user32.RegisterRawInputDevices(byref(rid), 1, sizeof(rid))

        if self.msg_hwnd:
            user32.PostMessageW(self.msg_hwnd, WM_CLOSE, 0, 0)

        with self.lock:
            for mouse in self.mice.values():
                if mouse["overlay"]:
                    mouse["overlay"].destroy()
            self.mice.clear()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        print("Multi-Mouse stopped.")

    # ------------------------------------------------------------------
    # Message loop
    # ------------------------------------------------------------------

    def _message_loop(self):
        """Create hidden window, register raw input, and run message loop."""
        instance = kernel32.GetModuleHandleW(None)
        class_name = "MultiMouseMsgWnd"

        WNDPROC = ctypes.WINFUNCTYPE(w.LPARAM, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                self._handle_raw_input(lparam)
                return 0
            elif msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_ref = WNDPROC(wnd_proc)

        wc = WNDCLASSEX()
        wc.cbSize = sizeof(WNDCLASSEX)
        wc.lpfnWndProc = cast(self._wndproc_ref, c_void_p)
        wc.hInstance = instance
        wc.lpszClassName = class_name
        user32.RegisterClassExW(byref(wc))

        self.msg_hwnd = user32.CreateWindowExW(
            0, class_name, "MultiMouseMsg",
            WS_OVERLAPPED,
            0, 0, 1, 1,
            None, None, instance, None,
        )

        if not self.msg_hwnd:
            self.running = False
            return

        # Register for raw mouse input (INPUTSINK only — we use a
        # low-level hook to block physical events, which is more
        # reliable than RIDEV_NOLEGACY).
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = 0x01
        rid.usUsage = 0x02
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = self.msg_hwnd
        user32.RegisterRawInputDevices(byref(rid), 1, sizeof(rid))

        # Install low-level mouse hook to block ALL physical mouse
        # events from reaching applications. Raw input (WM_INPUT)
        # is NOT affected by this hook — we still receive it.
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, w.INT, w.WPARAM, w.LPARAM)

        def ll_mouse_proc(nCode, wParam, lParam):
            if nCode >= 0:
                info = cast(ctypes.c_void_p(lParam), ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                # Let injected events (from our own SendInput) pass through.
                # Block only real physical mouse events.
                if not (info.flags & LLMHF_INJECTED):
                    return 1  # Block physical event
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._hook_proc = HOOKPROC(ll_mouse_proc)
        self._ll_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            cast(self._hook_proc, c_void_p),
            kernel32.GetModuleHandleW(None),
            0,
        )

        if not self._ll_hook:
            print("Warning: Low-level mouse hook failed. Clicks may behave oddly.")

        self.independent_mode = True
        print("Independent mode active - each mouse has its own cursor.")

        msg = MSG()
        while self.running:
            ret = user32.GetMessageW(byref(msg), None, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))

        self.msg_hwnd = None

    # ------------------------------------------------------------------
    # Raw input handling
    # ------------------------------------------------------------------

    def _handle_raw_input(self, lparam):
        """Process WM_INPUT: parse raw mouse data, update state, forward events."""
        # Check if primary overlay should reappear (stationary timeout)
        self._check_stationary()

        size = w.UINT()
        user32.GetRawInputData(
            w.HANDLE(lparam), RID_INPUT, None, byref(size), sizeof(RAWINPUTHEADER)
        )
        if size.value == 0 or size.value > 1024:
            return

        buf = (ctypes.c_byte * size.value)()
        written = user32.GetRawInputData(
            w.HANDLE(lparam), RID_INPUT, buf, byref(size), sizeof(RAWINPUTHEADER)
        )
        if written != size.value:
            return

        raw = cast(buf, ctypes.POINTER(RAWINPUT)).contents
        if raw.header.dwType != RIM_TYPEMOUSE:
            return
        if raw.header.hDevice is None or raw.header.hDevice == 0:
            return

        hdevice = raw.header.hDevice
        mouse = raw.mouse

        usButtonFlags = mouse.ulButtons & 0xFFFF
        usButtonData = (mouse.ulButtons >> 16) & 0xFFFF

        with self.lock:
            # ---- First-time device detection ----
            if hdevice not in self.mice:
                is_primary = (self.primary_device is None)
                overlay = None
                mouse_id = self._mouse_id_counter
                self._mouse_id_counter += 1

                # Resolve custom cursor paths relative to project directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_dir = os.path.dirname(script_dir)  # up one level from src/

                if is_primary:
                    self.primary_device = hdevice
                    custom_path = None
                    candidate = os.path.join(project_dir, "cursor0.png")
                    if os.path.isfile(candidate):
                        custom_path = candidate
                        print(f"[Mouse {mouse_id}] Custom cursor: cursor0.png")
                    overlay = CursorOverlay(self.primary_color, mouse_id, self.config, custom_path)
                    print(f"[Mouse {mouse_id}] PRIMARY   (device: {hdevice}) - system cursor + overlay")
                else:
                    color = self.colors[(mouse_id - 1) % len(self.colors)]
                    custom_path = None
                    candidate = os.path.join(project_dir, f"cursor{mouse_id}.png")
                    if os.path.isfile(candidate):
                        custom_path = candidate
                        print(f"[Mouse {mouse_id}] Custom cursor: cursor{mouse_id}.png")
                    overlay = CursorOverlay(color, mouse_id, self.config, custom_path)
                    color_names = ["Blue", "Green", "Red", "Orange"]
                    cname = color_names[(mouse_id - 1) % len(color_names)]
                    print(f"[Mouse {mouse_id}] SECONDARY (device: {hdevice}) - {cname} indicator")

                pt = POINT()
                user32.GetCursorPos(byref(pt))
                self.cursor_x, self.cursor_y = pt.x, pt.y
                self.mice[hdevice] = {
                    "x": pt.x,
                    "y": pt.y,
                    "overlay": overlay,
                    "left": False,
                    "right": False,
                    "middle": False,
                    "is_primary": is_primary,
                    "last_move_time": time.time(),
                    "overlay_visible": True,
                }

            state = self.mice[hdevice]
            is_primary = state["is_primary"]

            # ---- Button state MUST be updated before cursor decisions ----
            if usButtonFlags & RI_MOUSE_LEFT_BUTTON_DOWN:
                state["left"] = True
            if usButtonFlags & RI_MOUSE_LEFT_BUTTON_UP:
                state["left"] = False
            if usButtonFlags & RI_MOUSE_RIGHT_BUTTON_DOWN:
                state["right"] = True
            if usButtonFlags & RI_MOUSE_RIGHT_BUTTON_UP:
                state["right"] = False
            if usButtonFlags & RI_MOUSE_MIDDLE_BUTTON_DOWN:
                state["middle"] = True
            if usButtonFlags & RI_MOUSE_MIDDLE_BUTTON_UP:
                state["middle"] = False

            # ---- Movement ----
            if mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
                virt_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                virt_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                virt_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                virt_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
                if virt_w > 0 and virt_h > 0:
                    state["x"] = virt_x + int((mouse.lLastX / 65535.0) * virt_w)
                    state["y"] = virt_y + int((mouse.lLastY / 65535.0) * virt_h)
                has_moved = True
            elif mouse.lLastX != 0 or mouse.lLastY != 0:
                state["x"] += mouse.lLastX
                state["y"] += mouse.lLastY
                has_moved = True
            else:
                has_moved = False

            # Clamp to virtual desktop bounds
            sw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CXSCREEN)
            sh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CYSCREEN)
            state["x"] = max(0, min(state["x"], sw - 1))
            state["y"] = max(0, min(state["y"], sh - 1))

            # Track last movement time for overlay logic
            if has_moved:
                state["last_move_time"] = time.time()

            # ---- Update cursor position / overlay ----
            held_dev = self._find_button_held_device()

            # Always move overlay (tracks mouse regardless of button state)
            if state["overlay"]:
                state["overlay"].move(state["x"], state["y"])

            if held_dev is None:
                # No button held — normal movement.
                # Primary always moves cursor. Secondary only moves it
                # when primary is stationary (avoids flickering when both
                # mice move simultaneously).
                primary_still = True
                if self.primary_device and self.primary_device in self.mice and not is_primary:
                    pm = self.mice[self.primary_device]
                    primary_still = (time.time() - pm.get("last_move_time", 0)) > self.hover_threshold

                if is_primary:
                    user32.SetCursorPos(state["x"], state["y"])
                    self.cursor_x, self.cursor_y = state["x"], state["y"]
                elif self.independent_mode and primary_still and self.secondary_hover:
                    # Throttle: skip move if cursor is already near target
                    dx = state["x"] - self._last_move_x
                    dy = state["y"] - self._last_move_y
                    if dx * dx + dy * dy >= self.throttle_sq:
                        abs_x, abs_y = self._get_absolute_coords(state["x"], state["y"])
                        inp = INPUT_STRUCT()
                        inp.type = INPUT_MOUSE
                        inp.mi.dx = abs_x
                        inp.mi.dy = abs_y
                        inp.mi.mouseData = 0
                        inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
                        inp.mi.time = 0
                        inp.mi.dwExtraInfo = c_void_p(0)
                        user32.SendInput(1, byref(inp), sizeof(INPUT_STRUCT))
                        self._last_move_x = state["x"]
                        self._last_move_y = state["y"]
                    self.cursor_x, self.cursor_y = state["x"], state["y"]
                elif not self.independent_mode and not is_primary:
                    self._restore_primary_cursor()
            elif held_dev == hdevice:
                # THIS device holds a button (drag in progress).
                if is_primary:
                    user32.SetCursorPos(state["x"], state["y"])
                    self.cursor_x, self.cursor_y = state["x"], state["y"]
                elif self.independent_mode:
                    abs_x, abs_y = self._get_absolute_coords(state["x"], state["y"])
                    inp = INPUT_STRUCT()
                    inp.type = INPUT_MOUSE
                    inp.mi.dx = abs_x
                    inp.mi.dy = abs_y
                    inp.mi.mouseData = 0
                    inp.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
                    inp.mi.time = 0
                    inp.mi.dwExtraInfo = c_void_p(0)
                    user32.SendInput(1, byref(inp), sizeof(INPUT_STRUCT))
                    self.cursor_x, self.cursor_y = state["x"], state["y"]
            # else: another device holds button — don't move cursor

            # ---- SendInput for button events ----
            if self.independent_mode or not is_primary:
                if usButtonFlags & RI_MOUSE_LEFT_BUTTON_DOWN:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_LEFTDOWN, True)
                if usButtonFlags & RI_MOUSE_LEFT_BUTTON_UP:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_LEFTUP, False)
                if usButtonFlags & RI_MOUSE_RIGHT_BUTTON_DOWN:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_RIGHTDOWN, True)
                if usButtonFlags & RI_MOUSE_RIGHT_BUTTON_UP:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_RIGHTUP, False)
                if usButtonFlags & RI_MOUSE_MIDDLE_BUTTON_DOWN:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_MIDDLEDOWN, True)
                if usButtonFlags & RI_MOUSE_MIDDLE_BUTTON_UP:
                    self._send_mouse_button(state["x"], state["y"], MOUSEEVENTF_MIDDLEUP, False)

                # ---- Wheel events ----
                if usButtonFlags & RI_MOUSE_WHEEL:
                    delta = ctypes.c_short(usButtonData).value
                    self._send_wheel(state["x"], state["y"], delta, False)
                if usButtonFlags & RI_MOUSE_HWHEEL:
                    delta = ctypes.c_short(usButtonData).value
                    self._send_wheel(state["x"], state["y"], delta, True)

    # ------------------------------------------------------------------
    # Stationary overlay (primary mouse)
    # ------------------------------------------------------------------

    def _check_stationary(self):
        """Called on raw input events — sync overlay visibility."""
        self._sync_overlay_visibility()

    def _sync_overlay_visibility(self):
        """Hide overlay when system cursor is near the mouse position.
        
        Rule: prefer showing the system cursor. If the system cursor is at
        a mouse's position, hide that mouse's overlay. Otherwise show it.
        Primary overlay also requires the mouse to be stationary.
        
        Skipped during button holds to avoid any possible interference.
        """
        if self._find_button_held_device() is not None:
            return

        for hdevice, state in self.mice.items():
            overlay = state.get("overlay")
            if not overlay:
                continue
            dist = math.hypot(self.cursor_x - state["x"], self.cursor_y - state["y"])
            is_primary = state.get("is_primary", False)

            if dist < 10:  # System cursor near this mouse → hide overlay
                if state.get("overlay_visible", True):
                    overlay.hide()
                    state["overlay_visible"] = False
            else:
                # System cursor elsewhere → show overlay
                should_show = True
                if is_primary:
                    # Primary: only show when stationary
                    elapsed = time.time() - state.get("last_move_time", 0)
                    should_show = elapsed > self.stationary_timeout
                if should_show and not state.get("overlay_visible", True):
                    overlay.show()
                    state["overlay_visible"] = True

    # ------------------------------------------------------------------
    # SendInput helpers
    # ------------------------------------------------------------------

    def _get_absolute_coords(self, x, y):
        """Convert screen coordinates to 0-65535 normalized range for SendInput."""
        abs_x = int(((x - self._virt_x) * 65535) / self._virt_w)
        abs_y = int(((y - self._virt_y) * 65535) / self._virt_h)
        return max(0, min(abs_x, 65535)), max(0, min(abs_y, 65535))

    def _send_mouse_button(self, x, y, button_flag, is_down):
        """Send a mouse click via SendInput with absolute coordinates.
        
        Move and button are in one atomic SendInput batch.
        Right-click UP does NOT restore cursor — it stays at the click
        position so GetCursorPos() returns the correct location.
        """
        abs_x, abs_y = self._get_absolute_coords(x, y)
        is_right = button_flag in (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)

        if is_down or is_right:
            inputs = (INPUT_STRUCT * 2)()
            inputs[0].type = INPUT_MOUSE
            inputs[0].mi.dx = abs_x
            inputs[0].mi.dy = abs_y
            inputs[0].mi.mouseData = 0
            inputs[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
            inputs[0].mi.time = 0
            inputs[0].mi.dwExtraInfo = c_void_p(0)
            inputs[1].type = INPUT_MOUSE
            inputs[1].mi.dx = 0
            inputs[1].mi.dy = 0
            inputs[1].mi.mouseData = 0
            inputs[1].mi.dwFlags = button_flag
            inputs[1].mi.time = 0
            inputs[1].mi.dwExtraInfo = c_void_p(0)
            user32.SendInput(2, byref(inputs), sizeof(INPUT_STRUCT))
            self.cursor_x, self.cursor_y = x, y
        else:
            # Left-up: restore cursor to primary after release
            if self.primary_device and self.primary_device in self.mice:
                pm = self.mice[self.primary_device]
                restore_x, restore_y = self._get_absolute_coords(pm["x"], pm["y"])
            else:
                restore_x, restore_y = abs_x, abs_y

            inputs = (INPUT_STRUCT * 3)()
            inputs[0].type = INPUT_MOUSE
            inputs[0].mi.dx = abs_x
            inputs[0].mi.dy = abs_y
            inputs[0].mi.mouseData = 0
            inputs[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
            inputs[0].mi.time = 0
            inputs[0].mi.dwExtraInfo = c_void_p(0)
            inputs[1].type = INPUT_MOUSE
            inputs[1].mi.dx = 0
            inputs[1].mi.dy = 0
            inputs[1].mi.mouseData = 0
            inputs[1].mi.dwFlags = button_flag
            inputs[1].mi.time = 0
            inputs[1].mi.dwExtraInfo = c_void_p(0)
            inputs[2].type = INPUT_MOUSE
            inputs[2].mi.dx = restore_x
            inputs[2].mi.dy = restore_y
            inputs[2].mi.mouseData = 0
            inputs[2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
            inputs[2].mi.time = 0
            inputs[2].mi.dwExtraInfo = c_void_p(0)
            user32.SendInput(3, byref(inputs), sizeof(INPUT_STRUCT))
            if self.primary_device and self.primary_device in self.mice:
                pm = self.mice[self.primary_device]
                self.cursor_x, self.cursor_y = pm["x"], pm["y"]
            else:
                self.cursor_x, self.cursor_y = x, y

        if is_right and not is_down:
            self._sync_overlay_visibility()

    def _send_wheel(self, x, y, delta, horizontal=False):
        """Send a mouse wheel event at the given position via SendInput.
        
        Uses a 3-event atomic batch (move + wheel + restore) so the
        cursor doesn't visibly jump between windows, which causes
        choppy scrolling when the two mice are on different apps.
        """
        abs_x, abs_y = self._get_absolute_coords(x, y)

        if self.primary_device and self.primary_device in self.mice:
            pm = self.mice[self.primary_device]
            restore_x, restore_y = self._get_absolute_coords(pm["x"], pm["y"])
        else:
            restore_x, restore_y = abs_x, abs_y

        inputs = (INPUT_STRUCT * 3)()
        inputs[0].type = INPUT_MOUSE
        inputs[0].mi.dx = abs_x
        inputs[0].mi.dy = abs_y
        inputs[0].mi.mouseData = 0
        inputs[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
        inputs[0].mi.time = 0
        inputs[0].mi.dwExtraInfo = c_void_p(0)

        inputs[1].type = INPUT_MOUSE
        inputs[1].mi.dx = 0
        inputs[1].mi.dy = 0
        inputs[1].mi.mouseData = delta
        inputs[1].mi.dwFlags = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
        inputs[1].mi.time = 0
        inputs[1].mi.dwExtraInfo = c_void_p(0)

        inputs[2].type = INPUT_MOUSE
        inputs[2].mi.dx = restore_x
        inputs[2].mi.dy = restore_y
        inputs[2].mi.mouseData = 0
        inputs[2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | MOUSEEVENTF_MOVE
        inputs[2].mi.time = 0
        inputs[2].mi.dwExtraInfo = c_void_p(0)

        user32.SendInput(3, byref(inputs), sizeof(INPUT_STRUCT))
        if self.primary_device and self.primary_device in self.mice:
            pm = self.mice[self.primary_device]
            self.cursor_x, self.cursor_y = pm["x"], pm["y"]
        else:
            self.cursor_x, self.cursor_y = x, y

    def _find_button_held_device(self):
        """Return the device handle of the mouse that currently has a button held, or None."""
        for hdev, state in self.mice.items():
            if state.get("left") or state.get("right") or state.get("middle"):
                return hdev
        return None

    def _is_secondary_button_held(self):
        """Check if any non-primary mouse has a button currently held down."""
        for hdevice, state in self.mice.items():
            if not state.get("is_primary", True):
                if state.get("left") or state.get("right") or state.get("middle"):
                    return True
        return False

    def _restore_primary_cursor(self):
        """Restore system cursor to primary mouse position after a SendInput event."""
        if self.primary_device and self.primary_device in self.mice:
            pm = self.mice[self.primary_device]
            user32.SetCursorPos(pm["x"], pm["y"])
            self.cursor_x, self.cursor_y = pm["x"], pm["y"]

# ============================================================================
# Entry point
# ============================================================================

_manager = None

def main():
    """Launch the multi-mouse utility."""
    global _manager

    print("Initializing Multi-Mouse...")
    _manager = MultiMouseManager()

    try:
        _manager.start()
        while _manager.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if _manager:
            _manager.stop()

def cleanup():
    """Ensure cleanup on normal exit."""
    global _manager
    if _manager and _manager.running:
        _manager.stop()

atexit.register(cleanup)
