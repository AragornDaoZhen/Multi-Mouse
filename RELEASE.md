# v1.0.0 — Initial Release / 首次发布

让 Windows 同时使用多个物理鼠标，每个鼠标拥有独立的光标和点击。
Use multiple physical mice simultaneously on Windows — each with its own cursor and click target.

---

## 下载 / Download

| 文件 | 说明 |
|------|------|
| `multimouse.exe` | 主程序 / Main program — 双击运行，关闭窗口退出 / double-click to start, close to exit |
| `multimouse-settings.exe` | 设置面板 / Settings panel — 可视化调整光标大小、颜色等 / GUI config editor |

## 功能 / Features

- 🖱 多鼠标独立光标，互不干扰 / Independent cursors for each mouse
- 🎯 每个鼠标可独立左键/右键/拖拽 / Each mouse clicks, right-clicks, and drags independently
- 🎨 自定义光标图标（PNG 图片） / Custom cursor icons (PNG)
- ⚙ 可视化设置面板（中/English 切换） / GUI settings panel with i18n
- 🔧 零外部依赖 / Zero external dependencies

## 安装方式 / Installation

**方式一：下载 .exe（推荐普通用户）**
下载上方 `multimouse.exe`，双击运行。

**方式二：pip 安装（即将上线）**
```bash
pip install multimouse
multimouse
```

**方式三：从源码运行**
```bash
git clone https://github.com/AragornDaoZhen/Multi-Mouse.git
cd Multi-Mouse
python run.py
```

## 系统要求 / Requirements

- Windows 10 / 11（Vista+ 理论上支持）
- 无需管理员权限（以管理员运行可改善部分应用兼容性）
- No admin rights required (admin mode improves compatibility with some apps)

## 已知限制 / Known Limitations

1. 部分 UWP/管理员窗口点击可能无响应 / Some UWP/elevated windows may not respond
2. 无鼠标加速（1:1 像素映射） / No mouse acceleration (1:1 pixel mapping)
3. 杀毒软件可能报警（全局钩子） / Antivirus may flag the hook

---

**[完整说明 / Full README](https://github.com/AragornDaoZhen/Multi-Mouse)**
