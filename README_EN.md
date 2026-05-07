# Multi-Mouse — Independent Cursors for Multiple Mice

Use multiple physical mice simultaneously on Windows, each with its own cursor and click target.

## Project Credits

- **Executor**：DeepSeek V4
- **Designer / Jack-of-all-trades**：AragornDaoZhen

## Quick Start

**With Python installed:**
```
python run.py
```
Or double-click `启动多鼠标.bat`. Close the window to exit.

**Without Python:**
Use PyInstaller to create a standalone executable:
```
pip install pyinstaller
pyinstaller --onefile --console run.py
```
Run the generated `dist\run.exe`.

## Custom Cursor Icons

Place PNG images in the project root directory (~32×32 recommended, transparent background supported):

| Filename | Mouse |
|----------|-------|
| `cursor0.png` | Primary mouse |
| `cursor1.png` | Second mouse |
| `cursor2.png` | Third mouse |

Without custom images, built-in triangular cursors are used (grey for primary, blue for secondary).

## How It Works

### Architecture

```
Physical mouse → WH_MOUSE_LL hook → Raw Input (WM_INPUT) → Synthetic events (SendInput) → Application
```

1. **WH_MOUSE_LL Low-Level Hook** — Blocks all physical mouse events from reaching applications
2. **Raw Input API (WM_INPUT)** — Receives per-device raw movement/click data, distinguishes mice by device handle
3. **SendInput Synthetic Events** — Generates correct cursor movement and click events based on raw input
4. **Layered Window Overlays** — Renders independent cursor icons for each mouse (transparent, topmost, click-through)

### Cursor Positioning

- Raw input provides relative deltas (delta X/Y); absolute coordinates are accumulated per device
- Primary mouse: system cursor follows via `SetCursorPos`
- Secondary mouse: system cursor follows via `SendInput(ABSOLUTE|MOVE)` (enables hover effects)
- Each mouse has its own overlay cursor (Layered Window), always displayed at the correct position
- Primary overlay auto-hides during movement (avoids overlap with system cursor), reappears after 250ms of stillness

### Click Handling

- Physical clicks are intercepted and discarded by WH_MOUSE_LL
- Synthetic clicks are sent via `SendInput` based on raw input button flags:
  - **Button down**: `(move to target, button down)` — 2-event atomic batch
  - **Button up**: `(move to target, button up, restore to primary position)` — 3-event atomic batch
- WH_MOUSE_LL checks the `LLMHF_INJECTED` flag to let synthetic events through

### Drag Support

- The mouse holding a button can drag normally (cursor follows movement)
- Movement from other mice does not interfere with an active drag

### Custom Cursor Loading

Uses Windows built-in GDI+ to load PNG images, renders to 32-bit BGRA DIB sections, displayed via `UpdateLayeredWindow`.

## Known Limitations

1. **Some UWP/elevated windows may not respond** — `SendInput` from a non-elevated process is subject to UIPI and cannot inject into higher-integrity windows. Running as administrator mitigates this.

2. **No mouse acceleration** — Raw input provides unprocessed device data; Windows pointer speed/acceleration settings do not apply. Cursor movement is 1:1 pixel mapping.

3. **Mouse count limited by USB ports** — Tested with 2–4 mice; theoretically supports more.

4. **Requires Windows Vista or later** — WH_MOUSE_LL and Raw Input API are Vista+ features.

5. **System cursor may flicker during secondary drag** — The system cursor follows the secondary mouse during a drag and returns to the primary position on release.

6. **DPI scaling** — Overlay cursor positions may have minor offsets on high-DPI displays (no DPI-awareness adaptation yet).

7. **Antivirus may flag the hook** — WH_MOUSE_LL is a global hook; some security software may classify it as suspicious behavior.
