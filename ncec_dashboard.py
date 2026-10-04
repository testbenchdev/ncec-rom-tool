"""ライブ・ダッシュボード(大きな数値タイル式)。

接続中ECUのライブ値を、設定可能なタイルで表示する別ウィンドウ。
- 項目(チャンネル)の追加/削除
- ドラッグで配置変更、右下ハンドルでサイズ変更
- レイアウトは dashboard_layout.json に自動保存/復元
値の供給はエディタ側(LiveReader)から update_values() で渡す(読み取り専用)。
"""
from __future__ import annotations

import json
import pathlib
import tkinter as tk

LAYOUT_PATH = pathlib.Path(__file__).resolve().parent / "dashboard_layout.json"

# チャンネル定義: key -> (日本語ラベル, 単位, フォーマット)。key は OBD PID(int)。
PID_LABEL = {
    0x0C: ("エンジン回転数", "rpm", "%.0f"),
    0x05: ("水温", "°C", "%.0f"),
    0x0F: ("吸気温", "°C", "%.0f"),
    0x0B: ("吸気圧 MAP", "kPa", "%.0f"),
    0x33: ("大気圧", "kPa", "%.0f"),
    0x10: ("エアフロ MAF", "g/s", "%.1f"),
    0x11: ("スロットル", "%", "%.0f"),
    0x49: ("アクセル開度", "%", "%.0f"),
    0x04: ("エンジン負荷", "%", "%.0f"),
    0x43: ("絶対負荷", "%", "%.0f"),
    0x0E: ("点火時期", "°", "%.1f"),
    0x42: ("バッテリ電圧", "V", "%.2f"),
    0x0D: ("車速", "km/h", "%.0f"),
    0x06: ("短期燃料補正", "%", "%.1f"),
    0x07: ("長期燃料補正", "%", "%.1f"),
    0x15: ("O2(リア)", "V", "%.2f"),
    0x2C: ("EGR指令", "%", "%.0f"),
    0x1F: ("稼働時間", "s", "%.0f"),
    "DTC": ("DTC件数", "", "%.0f"),
}
DEFAULT_LAYOUT = [
    {"ch": 0x0C, "x": 20, "y": 20, "w": 260, "h": 150},
    {"ch": 0x05, "x": 300, "y": 20, "w": 150, "h": 100},
    {"ch": 0x0F, "x": 470, "y": 20, "w": 150, "h": 100},
    {"ch": 0x42, "x": 640, "y": 20, "w": 150, "h": 100},
    {"ch": 0x11, "x": 300, "y": 140, "w": 150, "h": 90},
    {"ch": 0x0E, "x": 470, "y": 140, "w": 150, "h": 90},
    {"ch": 0x0B, "x": 640, "y": 140, "w": 150, "h": 90},
    {"ch": 0x0D, "x": 20, "y": 190, "w": 150, "h": 90},
]

BG = "#0e1116"
TILE_BG = "#18202b"
TILE_EDGE = "#2b3a4d"
LABEL_FG = "#8fb0cc"
VALUE_FG = "#eaf4ff"
UNIT_FG = "#7f93a8"
ACCENT = "#2d7dd2"
HANDLE = "#3a6ea5"


def _warn_color(ch, v):
    """簡易しきい値色(水温高/電圧低などを強調)。"""
    if v is None:
        return VALUE_FG
    if ch == 0x05 and v >= 105:
        return "#ff5a4d"
    if ch == 0x05 and v >= 98:
        return "#ffb02e"
    if ch == 0x42 and v < 11.5:
        return "#ff5a4d"
    if ch == "DTC" and v >= 1:
        return "#ff5a4d"
    return VALUE_FG


class DashboardWindow(tk.Toplevel):
    def __init__(self, master, jp="Yu Gothic UI", mono="Consolas"):
        super().__init__(master)
        self.title("ライブ・ダッシュボード")
        self.geometry("840x340")
        self.configure(bg=BG)
        self.jp = jp
        self.mono = mono
        self.values = {}      # ch -> value
        self.dtcs = []
        self._drag = None     # (tile, mode, dx, dy)
        self.tiles = self._load_layout()

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x")
        tk.Button(bar, text="項目を追加", command=self._add_menu).pack(side="left", padx=4, pady=4)
        tk.Button(bar, text="既定レイアウト", command=self._reset_layout).pack(side="left", padx=2)
        tk.Label(bar, text="ドラッグ=移動 / 右下角=サイズ変更 / 右クリック=削除",
                 bg=BG, fg=LABEL_FG, font=(self.jp, 9)).pack(side="right", padx=8)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._redraw()

    # ---- レイアウト保存/復元 ----
    def _load_layout(self):
        try:
            data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
            out = []
            for t in data:
                ch = t["ch"]
                if isinstance(ch, str) and ch != "DTC":
                    ch = int(ch)
                out.append({"ch": ch, "x": t["x"], "y": t["y"], "w": t["w"], "h": t["h"]})
            return out or [dict(d) for d in DEFAULT_LAYOUT]
        except Exception:  # noqa: BLE001
            return [dict(d) for d in DEFAULT_LAYOUT]

    def _save_layout(self):
        try:
            LAYOUT_PATH.write_text(json.dumps(self.tiles, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _reset_layout(self):
        self.tiles = [dict(d) for d in DEFAULT_LAYOUT]
        self._save_layout()
        self._redraw()

    # ---- 値の供給(エディタの LiveReader から)----
    def update_values(self, by_pid: dict, dtcs=None):
        self.values = dict(by_pid)
        if dtcs is not None:
            self.dtcs = dtcs
            self.values["DTC"] = len(dtcs)
        self._redraw()

    # ---- 描画 ----
    def _redraw(self):
        c = self.canvas
        c.delete("all")
        for t in self.tiles:
            self._draw_tile(t)

    def _draw_tile(self, t):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        ch = t["ch"]
        label, unit, fmt = PID_LABEL.get(ch, (str(ch), "", "%.0f"))
        c.create_rectangle(x, y, x + w, y + h, fill=TILE_BG, outline=TILE_EDGE, width=1)
        c.create_rectangle(x, y, x + w, y + 4, fill=ACCENT, outline=ACCENT)
        lab_sz = max(9, min(16, int(h * 0.16)))
        val_sz = max(14, int(h * 0.42))
        unit_sz = max(9, min(18, int(h * 0.18)))
        c.create_text(x + 10, y + 8 + lab_sz, text=label, anchor="w",
                      fill=LABEL_FG, font=(self.jp, lab_sz))
        v = self.values.get(ch)
        if v is None:
            vs = "--"
            col = UNIT_FG
        else:
            try:
                vs = fmt % v
            except Exception:  # noqa: BLE001
                vs = str(v)
            col = _warn_color(ch, v)
        c.create_text(x + 12, y + h * 0.60, text=vs, anchor="w",
                      fill=col, font=(self.mono, val_sz, "bold"))
        if unit:
            c.create_text(x + w - 10, y + h - 10, text=unit, anchor="se",
                          fill=UNIT_FG, font=(self.jp, unit_sz))
        # リサイズハンドル(右下)
        c.create_polygon(x + w - 14, y + h, x + w, y + h, x + w, y + h - 14,
                         fill=HANDLE, outline=HANDLE)

    # ---- ヒットテスト ----
    def _tile_at(self, px, py):
        for t in reversed(self.tiles):
            if t["x"] <= px <= t["x"] + t["w"] and t["y"] <= py <= t["y"] + t["h"]:
                return t
        return None

    def _on_press(self, e):
        t = self._tile_at(e.x, e.y)
        if not t:
            self._drag = None
            return
        # 右下14pxならリサイズ、それ以外は移動
        if (t["x"] + t["w"] - e.x) <= 16 and (t["y"] + t["h"] - e.y) <= 16:
            self._drag = (t, "resize", e.x - (t["x"] + t["w"]), e.y - (t["y"] + t["h"]))
        else:
            self._drag = (t, "move", e.x - t["x"], e.y - t["y"])
        # 最前面へ
        self.tiles.remove(t)
        self.tiles.append(t)
        self._redraw()

    def _on_drag(self, e):
        if not self._drag:
            return
        t, mode, dx, dy = self._drag
        if mode == "move":
            t["x"] = max(0, e.x - dx)
            t["y"] = max(0, e.y - dy)
        else:
            t["w"] = max(90, e.x - t["x"] - dx)
            t["h"] = max(60, e.y - t["y"] - dy)
        self._redraw()

    def _on_release(self, e):
        if self._drag:
            self._drag = None
            self._save_layout()

    def _on_right(self, e):
        t = self._tile_at(e.x, e.y)
        if not t:
            return
        m = tk.Menu(self, tearoff=0)
        lbl = PID_LABEL.get(t["ch"], (str(t["ch"]),))[0]
        m.add_command(label=f"「{lbl}」を削除",
                      command=lambda: self._remove(t))
        m.tk_popup(e.x_root, e.y_root)

    def _remove(self, t):
        if t in self.tiles:
            self.tiles.remove(t)
            self._save_layout()
            self._redraw()

    def _add_menu(self):
        shown = {t["ch"] for t in self.tiles}
        m = tk.Menu(self, tearoff=0)
        added = False
        for ch, (label, _u, _f) in PID_LABEL.items():
            if ch in shown:
                continue
            m.add_command(label=label, command=lambda c=ch: self._add(c))
            added = True
        if not added:
            m.add_command(label="(追加できる項目はありません)", state="disabled")
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    def _add(self, ch):
        self.tiles.append({"ch": ch, "x": 20, "y": 20, "w": 160, "h": 100})
        self._save_layout()
        self._redraw()

    def _on_close(self):
        self._save_layout()
        self.destroy()
