"""ライブ・ダッシュボード(大きなタイル式・多彩な表示モード)。

接続中ECUのライブ値を、設定可能なタイルで表示する別ウィンドウ。
- 表示モード: 数値 / 棒(バーメーター・縦横) / メーター(アナログ) / グラフ(時系列)
- 更新スタイル: リアルタイム / なめらか(直近2値を線形補間して約30fpsで描画)
- 項目ごとに 表示範囲・アラーム(上限、KRは下限)・更新周期 を設定
- メーター/棒はアラーム値に赤い帯(レッドゾーン)を表示。全体がタイル内に収まる(はみ出し対策)
- ドラッグで移動、右下角でサイズ変更、右クリックでメニュー
- レイアウト(位置/サイズ/モード/範囲/アラーム/向き)は dashboard_layout.json に保存/復元
値の供給はエディタ側(LiveReader)から update_values() で渡す(読み取り専用)。
更新周期の設定/取得はエディタから渡される set_interval/get_interval 経由で LiveReader に反映。
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import time
import tkinter as tk
from tkinter import colorchooser

LAYOUT_PATH = pathlib.Path(__file__).resolve().parent / "dashboard_layout.json"

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
    0x34: ("AFR(実測)", "", "%.2f"),
    0x44: ("AFR(目標)", "", "%.2f"),
    0x2C: ("EGR指令", "%", "%.0f"),
    0x1F: ("稼働時間", "s", "%.0f"),
    0x101: ("減速ステータス", "", "%.0f"),
    0x107: ("クラッチ", "", "%.0f"),
    0x102: ("KR(ノック遅角)", "°", "%.1f"),
    0x103: ("排気温(推定)", "°C", "%.0f"),
    0x104: ("ノックカウント", "", "%.0f"),
    0x105: ("ノック強度", "", "%.1f"),
    0x106: ("ノックリタード", "°", "%.1f"),
    "DTC": ("DTC件数", "", "%.0f"),
}
CH_RANGE = {
    0x0C: (0, 8000), 0x05: (40, 120), 0x0F: (-10, 70), 0x0B: (0, 110), 0x33: (0, 110),
    0x10: (0, 150), 0x11: (0, 100), 0x49: (0, 100), 0x04: (0, 100), 0x43: (0, 120),
    0x0E: (-10, 60), 0x42: (10, 16), 0x0D: (0, 200), 0x06: (-20, 20), 0x07: (-20, 20),
    0x15: (0, 1), 0x34: (9, 20), 0x44: (9, 20), 0x2C: (0, 100), 0x1F: (0, 3600),
    0x101: (0, 1), 0x102: (-15, 5), 0x103: (0, 900), 0x107: (0, 1),
    0x104: (0, 50), 0x105: (0, 100), 0x106: (0, 15), "DTC": (0, 10),
}
# アラーム: ノックカウントは「成立」しきい値(Minimum Proto-Knock Count=24)で赤
CH_ALARM = {0x0C: 6800, 0x05: 105, 0x103: 850, 0x102: -3.0, 0x104: 24, 0x106: 5.0}
LOW_ALARM = {0x102}
BIG_SCALE = {0x0C}               # 目盛りを1000で割って ×1000 表記

MODES = ["num", "bar", "gauge", "graph"]
MODE_LABEL = {"num": "数値", "bar": "棒(バー)", "gauge": "メーター", "graph": "グラフ"}
GRAPH_SEC = 12.0
INTERVAL_CHOICES = [(0.0, "毎回"), (0.5, "0.5秒"), (1.0, "1秒"), (2.0, "2秒"),
                    (5.0, "5秒"), (10.0, "10秒")]

DEFAULT_LAYOUT = [
    {"ch": 0x0C, "x": 20, "y": 20, "w": 280, "h": 220, "mode": "gauge"},
    {"ch": 0x0D, "x": 310, "y": 20, "w": 150, "h": 100, "mode": "num"},
    {"ch": 0x34, "x": 470, "y": 20, "w": 320, "h": 100, "mode": "bar"},
    {"ch": 0x04, "x": 310, "y": 130, "w": 110, "h": 230, "mode": "bar"},
    {"ch": 0x11, "x": 430, "y": 130, "w": 110, "h": 230, "mode": "bar"},
    {"ch": 0x0E, "x": 550, "y": 130, "w": 150, "h": 110, "mode": "num"},
    {"ch": 0x05, "x": 710, "y": 130, "w": 150, "h": 110, "mode": "num"},
    {"ch": 0x42, "x": 550, "y": 250, "w": 310, "h": 100, "mode": "bar"},
]

BG = "#0e1116"
TILE_BG = "#181c20"
TILE_EDGE = "#2b3340"
LABEL_FG = "#9aa6b2"
VAL = "#35d07f"            # 値(緑)
UNIT_FG = "#7f8b98"
ACCENT = "#2d7dd2"
HANDLE = "#4a5663"
GRID = "#2a333d"
TRACK = "#20262c"
NEEDLE = "#eef3f7"
FILL = "#35d07f"
ALARM = "#ff4d4d"
TICK = "#b9c3cd"


def _rng(ch, t=None):
    if t and "vmin" in t and "vmax" in t:
        return t["vmin"], t["vmax"]
    return CH_RANGE.get(ch, (0.0, 100.0))


def _alarm_of(ch, t):
    return t.get("alarm", CH_ALARM.get(ch))


def _in_alarm(ch, t, v):
    a = _alarm_of(ch, t)
    if a is None or v is None:
        return False
    return v <= a if ch in LOW_ALARM else v >= a


class DashboardWindow(tk.Toplevel):
    def __init__(self, master, jp="Yu Gothic UI", mono="Consolas",
                 get_interval=None, set_interval=None):
        super().__init__(master)
        self.title("ライブ・ダッシュボード")
        self.geometry("900x380")
        self.configure(bg=BG)
        self.jp = jp
        self.mono = mono
        self._get_interval = get_interval   # ch -> 秒(0=毎回) / None
        self._set_interval = set_interval    # (ch, 秒) を適用
        self.values = {}
        self.dtcs = []
        self._drag = None
        self._track = {}
        self._hist = {}
        self.tiles = self._load_layout()

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x")
        tk.Button(bar, text="項目を追加", command=self._add_menu).pack(side="left", padx=4, pady=4)
        tk.Button(bar, text="既定レイアウト", command=self._reset_layout).pack(side="left", padx=2)
        tk.Label(bar, text="ドラッグ=移動 / 右下=サイズ / 右クリック=表示方式・色・スケール・向き・横軸時間・更新周期・アラーム",
                 bg=BG, fg=LABEL_FG, font=(self.jp, 9)).pack(side="right", padx=8)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._anim_after = self.after(33, self._anim)

    # ---- レイアウト ----
    def _norm(self, t):
        t.setdefault("mode", "num")
        if t["mode"] not in MODES:
            t["mode"] = "num"
        return t

    def _load_layout(self):
        try:
            data = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
            out = []
            for t in data:
                ch = t["ch"]
                if isinstance(ch, str) and ch != "DTC":
                    ch = int(ch)
                d = {"ch": ch, "x": t["x"], "y": t["y"], "w": t["w"], "h": t["h"]}
                for k in ("mode", "vmin", "vmax", "alarm", "smooth", "bar_dir",
                          "color", "tick", "graph_sec"):
                    if k in t:
                        d[k] = t[k]
                out.append(self._norm(d))
            return out or [self._norm(dict(d)) for d in DEFAULT_LAYOUT]
        except Exception:  # noqa: BLE001
            return [self._norm(dict(d)) for d in DEFAULT_LAYOUT]

    def _save_layout(self):
        try:
            LAYOUT_PATH.write_text(json.dumps(self.tiles, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _reset_layout(self):
        self.tiles = [self._norm(dict(d)) for d in DEFAULT_LAYOUT]
        self._save_layout()

    # ---- 値の供給 ----
    def update_values(self, by_pid: dict, dtcs=None):
        now = time.monotonic()
        self.values = dict(by_pid)
        if dtcs is not None:
            self.dtcs = dtcs
            self.values["DTC"] = len(dtcs)
        for ch, v in self.values.items():
            if not isinstance(v, (int, float)):
                continue
            tr = self._track.get(ch)
            if tr is None:
                self._track[ch] = {"cur": v, "prev": v, "t": now, "iv": 0.1}
            elif v != tr["cur"]:
                dt = max(1e-3, now - tr["t"])
                tr["iv"] = tr["iv"] * 0.6 + dt * 0.4
                tr["prev"], tr["cur"], tr["t"] = tr["cur"], v, now
            self._hist.setdefault(ch, collections.deque(maxlen=6000)).append((now, float(v)))

    def _disp(self, ch, smooth):
        tr = self._track.get(ch)
        if tr is None:
            return self.values.get(ch)
        if not smooth:
            return tr["cur"]
        prog = min(1.0, max(0.0, (time.monotonic() - tr["t"]) / max(1e-3, tr["iv"])))
        return tr["prev"] + (tr["cur"] - tr["prev"]) * prog

    def _ivlabel(self, ch):
        if not self._get_interval:
            return ""
        try:
            s = self._get_interval(ch)
        except Exception:  # noqa: BLE001
            return ""
        if not s:
            return ""
        return f" [{s:g}s]"

    # ---- アニメーション(約30fps) ----
    def _anim(self):
        try:
            self._redraw()
        except tk.TclError:
            return
        self._anim_after = self.after(33, self._anim)

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        for t in self.tiles:
            try:
                self._draw_tile(t)
            except Exception:  # noqa: BLE001
                pass

    # ---- タイル ----
    def _draw_tile(self, t):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        ch = t["ch"]
        label, unit, fmt = PID_LABEL.get(ch, (str(ch), "", "%.0f"))
        label += (f" ({unit})" if unit else "") + self._ivlabel(ch)
        mode = t.get("mode", "num")
        smooth = bool(t.get("smooth", mode in ("gauge", "bar")))
        v = self._disp(ch, smooth)
        alarm = _in_alarm(ch, t, self.values.get(ch))
        c.create_rectangle(x, y, x + w, y + h, fill=TILE_BG,
                           outline=ALARM if alarm else TILE_EDGE, width=2 if alarm else 1)
        lab_sz = max(8, min(11, int(h * 0.10)))     # 項目名は小さめ(主役はモニタ値)
        c.create_text(x + 8, y + 3 + lab_sz, text=label, anchor="w", fill=LABEL_FG,
                      font=(self.jp, lab_sz))
        col = ALARM if alarm else t.get("color", VAL)   # パネルごとの表示色(アラーム時は赤)
        self._lab_h = 6 + lab_sz
        if mode == "num":
            self._draw_num(t, v, fmt, unit, col)
        elif mode == "bar":
            self._draw_bar(t, v, fmt, col)
        elif mode == "gauge":
            self._draw_gauge(t, ch, v, fmt, col)
        elif mode == "graph":
            self._draw_graph(t, v, fmt, unit, col)
        r = 7
        c.create_oval(x + w - r - 4, y + h - r - 4, x + w - 4, y + h - 4, fill=HANDLE, outline="")

    def _vstr(self, v, fmt):
        if v is None:
            return "--"
        try:
            return fmt % v
        except Exception:  # noqa: BLE001
            return str(v)

    def _ticks(self, lo, hi, t):
        """目盛り値の一覧。t['tick']>0 ならその間隔、無ければ4分割(5点)。"""
        if hi <= lo:
            return [lo]
        step = t.get("tick")
        if step and step > 0:
            if (hi - lo) / step > 40:            # 過密防止
                step = (hi - lo) / 40.0
            vals, k = [], 0
            while True:
                vv = lo + k * step
                if vv > hi + step * 1e-6 or len(vals) > 60:
                    break
                vals.append(round(vv, 6))
                k += 1
            if not vals or vals[-1] < hi - step * 1e-6:
                vals.append(hi)
            return vals
        return [lo + (hi - lo) * i / 4.0 for i in range(5)]

    # ---- 数値 ----
    def _draw_num(self, t, v, fmt, unit, col):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        val_sz = max(16, int(h * 0.40))
        c.create_text(x + w / 2, y + self._lab_h + (h - self._lab_h) / 2,
                      text=self._vstr(v, fmt), fill=col if v is not None else UNIT_FG,
                      font=(self.mono, val_sz, "bold"))

    # ---- 棒(縦/横) ----
    def _bar_dir(self, t):
        return t.get("bar_dir") or ("v" if t["h"] >= t["w"] else "h")

    def _draw_bar(self, t, v, fmt, col):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        ch = t["ch"]
        lo, hi = _rng(ch, t)
        a = _alarm_of(ch, t)
        low = ch in LOW_ALARM
        val_sz = max(13, int(min(w, h) * 0.22))
        c.create_text(x + w / 2, y + self._lab_h + val_sz * 0.6, text=self._vstr(v, fmt),
                      fill=col if v is not None else UNIT_FG, font=(self.mono, val_sz, "bold"))

        def frac(val):
            return 0.0 if hi <= lo else min(1.0, max(0.0, (val - lo) / (hi - lo)))

        if self._bar_dir(t) == "v":
            bx0 = x + 14
            bx1 = min(x + 14 + max(16, w * 0.35), x + w - 44)
            by0 = y + self._lab_h + val_sz + 8
            by1 = y + h - 12
            c.create_rectangle(bx0, by0, bx1, by1, fill=TRACK, outline=GRID)
            if a is not None and lo <= a <= hi:
                ay = by1 - (by1 - by0) * frac(a)
                zy0, zy1 = (ay, by1) if low else (by0, ay)      # 赤帯(アラーム側)
                c.create_rectangle(bx0, zy0, bx1, zy1, fill="#3a1414", outline="")
                c.create_line(bx0, ay, bx1, ay, fill=ALARM, width=2)
            if v is not None:
                fy = by1 - (by1 - by0) * frac(v)
                c.create_rectangle(bx0, fy, bx1, by1, fill=col, outline="")
            for val in self._ticks(lo, hi, t):
                yy = by1 - (by1 - by0) * frac(val)
                c.create_line(bx1, yy, bx1 + 4, yy, fill=TICK)
                c.create_text(bx1 + 7, yy, text=f"{val:g}", anchor="w",
                              fill=UNIT_FG, font=(self.jp, max(7, int(h * 0.045))))
        else:
            bx0 = x + 12
            bx1 = x + w - 12
            by1 = y + h - 22
            bh = max(12, int(h * 0.30))
            by0 = by1 - bh
            c.create_rectangle(bx0, by0, bx1, by1, fill=TRACK, outline=GRID)
            if a is not None and lo <= a <= hi:
                ax = bx0 + (bx1 - bx0) * frac(a)
                zx0, zx1 = (bx0, ax) if low else (ax, bx1)
                c.create_rectangle(zx0, by0, zx1, by1, fill="#3a1414", outline="")
                c.create_line(ax, by0, ax, by1, fill=ALARM, width=2)
            if v is not None:
                fx = bx0 + (bx1 - bx0) * frac(v)
                c.create_rectangle(bx0, by0, fx, by1, fill=col, outline="")
            for val in self._ticks(lo, hi, t):
                gx = bx0 + (bx1 - bx0) * frac(val)
                c.create_line(gx, by1, gx, by1 + 4, fill=TICK)
                c.create_text(gx, by1 + 6, text=f"{val:g}", anchor="n",
                              fill=UNIT_FG, font=(self.jp, max(7, int(h * 0.085))))

    # ---- メーター(アナログ・はみ出し対策) ----
    def _draw_gauge(self, t, ch, v, fmt, col):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        lo, hi = _rng(ch, t)
        pad = 8
        gap = max(3, int(h * 0.02))                      # 項目名との隙間(被り対策)
        lab_h = self._lab_h
        avail_w = w - 2 * pad
        avail_h = h - lab_h - pad - gap
        r = max(16, min(avail_w / 2, avail_h / 1.707))   # 270°(下開き)がタイル内に収まる半径
        cx = x + w / 2
        cy = y + lab_h + gap + r
        big = ch in BIG_SCALE
        div = 1000.0 if big else 1.0

        def ang(f):
            return math.radians(225 - 270 * min(1.0, max(0.0, f)))

        def pt(f, rad):
            a = ang(f)
            return cx + rad * math.cos(a), cy - rad * math.sin(a)

        aw = max(3, int(r * 0.10))
        c.create_arc(cx - r, cy - r, cx + r, cy + r, start=-45, extent=270, style="arc",
                     outline=GRID, width=aw)
        # アラーム赤帯(レッドゾーン)
        a = _alarm_of(ch, t)
        if a is not None and lo < hi:
            fa = min(1.0, max(0.0, (a - lo) / (hi - lo)))
            if ch in LOW_ALARM:
                c.create_arc(cx - r, cy - r, cx + r, cy + r, start=225, extent=-270 * fa,
                             style="arc", outline=ALARM, width=aw)
            else:
                c.create_arc(cx - r, cy - r, cx + r, cy + r, start=-45, extent=270 * (1 - fa),
                             style="arc", outline=ALARM, width=aw)
        # 目盛り + 内側ラベル(目盛り間隔は _ticks で調整可)
        lsz = max(7, int(r * 0.13))
        for val in self._ticks(lo, hi, t):
            f = 0.0 if hi <= lo else (val - lo) / (hi - lo)
            x1, y1 = pt(f, r - aw)
            x2, y2 = pt(f, r - aw - max(5, r * 0.09))
            c.create_line(x1, y1, x2, y2, fill=TICK, width=1)
            lx, ly = pt(f, r - aw - max(5, r * 0.09) - lsz)
            c.create_text(lx, ly, text=f"{val / div:g}", fill=UNIT_FG,
                          font=(self.jp, lsz))
        if big:
            c.create_text(x + pad + 2, y + h - 6, text="×1000", anchor="sw", fill=UNIT_FG,
                          font=(self.jp, max(8, int(r * 0.12))))
        # 針(細め・目盛り数値を隠さない)
        if v is not None and hi > lo:
            nx, ny = pt((v - lo) / (hi - lo), r - aw - 2)
            c.create_line(cx, cy, nx, ny, fill=col,
                          width=max(1, int(r * 0.035)), capstyle="round")
        hub = max(4, int(r * 0.09))
        c.create_oval(cx - hub, cy - hub, cx + hub, cy + hub, fill=NEEDLE, outline="")
        # 中央下に数値(小さめ・開口部の内側)
        c.create_text(cx, cy + r * 0.46, text=self._vstr(v, fmt),
                      fill=col if v is not None else UNIT_FG,
                      font=(self.mono, max(10, int(r * 0.18)), "bold"))

    # ---- グラフ ----
    def _draw_graph(self, t, v, fmt, unit, col):
        c = self.canvas
        x, y, w, h = t["x"], t["y"], t["w"], t["h"]
        ch = t["ch"]
        lo, hi = _rng(ch, t)
        gsec = float(t.get("graph_sec", GRAPH_SEC)) or GRAPH_SEC
        gx0, gy0 = x + 10, y + self._lab_h + 4
        gx1, gy1 = x + w - 10, y + h - 18        # 下に横軸(時間)ラベル分を確保

        def py(val):
            fr = 0.0 if hi <= lo else min(1.0, max(0.0, (val - lo) / (hi - lo)))
            return gy1 - (gy1 - gy0) * fr
        # 横グリッド(目盛り間隔で調整可)＋縦軸ラベル
        ticks = self._ticks(lo, hi, t)
        for val in ticks:
            yy = py(val)
            c.create_line(gx0, yy, gx1, yy, fill=GRID)
            if len(ticks) <= 7:
                c.create_text(gx0 + 2, yy - 1, text=f"{val:g}", anchor="sw",
                              fill=UNIT_FG, font=(self.jp, max(7, int(h * 0.085))))
        # 横軸(時間)ラベル
        for f in (0.0, 0.5, 1.0):
            xx = gx0 + (gx1 - gx0) * f
            txt = "0" if f >= 1.0 else f"{-gsec * (1.0 - f):g}s"
            c.create_text(xx, gy1 + 2, text=txt, anchor="n",
                          fill=UNIT_FG, font=(self.jp, max(7, int(h * 0.085))))
        a = _alarm_of(ch, t)
        if a is not None and lo <= a <= hi:
            c.create_line(gx0, py(a), gx1, py(a), fill=ALARM, dash=(3, 3))
        hist = self._hist.get(ch)
        now = time.monotonic()
        if hist:
            pts = [(tt, vv) for tt, vv in hist if now - tt <= gsec]
            if len(pts) >= 2:
                xs = []
                for tt, vv in pts:
                    xs += [gx0 + (gx1 - gx0) * (1.0 - (now - tt) / gsec), py(vv)]
                c.create_line(*xs, fill=col, width=2)
        c.create_text(x + w - 10, y + self._lab_h, text=self._vstr(v, fmt), anchor="ne",
                      fill=col if v is not None else UNIT_FG, font=(self.mono, max(10, int(h * 0.15)), "bold"))

    # ---- 操作 ----
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
        if (t["x"] + t["w"] - e.x) <= 16 and (t["y"] + t["h"] - e.y) <= 16:
            self._drag = (t, "resize", e.x - (t["x"] + t["w"]), e.y - (t["y"] + t["h"]))
        else:
            self._drag = (t, "move", e.x - t["x"], e.y - t["y"])
        self.tiles.remove(t)
        self.tiles.append(t)

    def _on_drag(self, e):
        if not self._drag:
            return
        t, mode, dx, dy = self._drag
        if mode == "move":
            t["x"] = max(0, e.x - dx)
            t["y"] = max(0, e.y - dy)
        else:
            t["w"] = max(80, e.x - t["x"] - dx)
            t["h"] = max(60, e.y - t["y"] - dy)

    def _on_release(self, e):
        if self._drag:
            self._drag = None
            self._save_layout()

    def _on_right(self, e):
        t = self._tile_at(e.x, e.y)
        if not t:
            return
        lbl = PID_LABEL.get(t["ch"], (str(t["ch"]),))[0]
        m = tk.Menu(self, tearoff=0)
        sub = tk.Menu(m, tearoff=0)
        for mo in MODES:
            mark = "● " if t.get("mode", "num") == mo else "　"
            sub.add_command(label=mark + MODE_LABEL[mo], command=lambda t=t, mo=mo: self._set_mode(t, mo))
        m.add_cascade(label="表示方式", menu=sub)
        if t.get("mode") == "bar":
            d = self._bar_dir(t)
            m.add_command(label=("棒の向き: 縦 → 横" if d == "v" else "棒の向き: 横 → 縦"),
                          command=lambda t=t: self._toggle_bardir(t))
        cur_smooth = bool(t.get("smooth", t.get("mode", "num") in ("gauge", "bar")))
        m.add_command(label=("更新: なめらか ✓" if cur_smooth else "更新: なめらかにする"),
                      command=lambda t=t: self._toggle_smooth(t))
        if self._set_interval is not None:
            sub2 = tk.Menu(m, tearoff=0)
            cur = None
            if self._get_interval:
                try:
                    cur = self._get_interval(t["ch"])
                except Exception:  # noqa: BLE001
                    cur = None
            for sec, name in INTERVAL_CHOICES:
                mark = "● " if (cur is not None and abs((cur or 0) - sec) < 1e-6) else "　"
                sub2.add_command(label=mark + name, command=lambda t=t, s=sec: self._set_iv(t, s))
            m.add_cascade(label="更新周期", menu=sub2)
        m.add_command(label="表示色…", command=lambda t=t: self._set_color(t))
        m.add_command(label="スケール(範囲・目盛り間隔)…", command=lambda t=t: self._set_scale(t))
        if t.get("mode") == "graph":
            m.add_command(label="横軸の時間…", command=lambda t=t: self._set_graphsec(t))
        m.add_command(label="アラーム値を設定…", command=lambda t=t: self._set_alarm(t))
        m.add_separator()
        m.add_command(label=f"「{lbl}」を削除", command=lambda t=t: self._remove(t))
        m.tk_popup(e.x_root, e.y_root)

    def _set_mode(self, t, mode):
        t["mode"] = mode
        self._save_layout()

    def _toggle_bardir(self, t):
        t["bar_dir"] = "h" if self._bar_dir(t) == "v" else "v"
        self._save_layout()

    def _toggle_smooth(self, t):
        t["smooth"] = not bool(t.get("smooth", t.get("mode", "num") in ("gauge", "bar")))
        self._save_layout()

    def _set_iv(self, t, sec):
        if self._set_interval:
            try:
                self._set_interval(t["ch"], sec)
            except Exception:  # noqa: BLE001
                pass

    def _set_color(self, t):
        cur = t.get("color", VAL)
        try:
            _rgb, hexv = colorchooser.askcolor(color=cur, parent=self, title="表示色")
        except Exception:  # noqa: BLE001
            hexv = None
        if hexv:
            t["color"] = hexv
            self._save_layout()

    def _set_scale(self, t):
        lo, hi = _rng(t["ch"], t)
        d = _ScaleDialog(self, PID_LABEL.get(t["ch"], (str(t["ch"]),))[0], lo, hi, t.get("tick"))
        self.wait_window(d.top)
        if d.result:
            lo2, hi2, tick = d.result
            t["vmin"], t["vmax"] = lo2, hi2
            if tick and tick > 0:
                t["tick"] = tick
            else:
                t.pop("tick", None)
            self._save_layout()

    def _set_graphsec(self, t):
        cur = float(t.get("graph_sec", GRAPH_SEC))
        d = _ValueDialog(self, "横軸の時間", "表示する時間幅 (秒, 1〜600)", cur, lo=1.0, hi=600.0)
        self.wait_window(d.top)
        if d.done and d.value:
            t["graph_sec"] = d.value
            self._save_layout()

    def _set_alarm(self, t):
        cur = _alarm_of(t["ch"], t)
        d = _AlarmDialog(self, PID_LABEL.get(t["ch"], (str(t["ch"]),))[0], cur, t["ch"] in LOW_ALARM)
        self.wait_window(d.top)
        if d.done:
            if d.value is None:
                t.pop("alarm", None)
            else:
                t["alarm"] = d.value
            self._save_layout()

    def _remove(self, t):
        if t in self.tiles:
            self.tiles.remove(t)
            self._save_layout()

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
        self.tiles.append(self._norm({"ch": ch, "x": 20, "y": 20, "w": 170, "h": 110}))
        self._save_layout()

    def _on_close(self):
        if self._anim_after:
            try:
                self.after_cancel(self._anim_after)
            except Exception:  # noqa: BLE001
                pass
        self._save_layout()
        self.destroy()


class _ScaleDialog:
    """表示範囲(下限/上限)と目盛り間隔(空欄=自動)を設定。"""

    def __init__(self, parent, title, lo, hi, tick=None):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title(f"スケール — {title}")
        self.top.configure(bg=BG)
        self.top.transient(parent)
        rows = [("下限", f"{lo:g}"), ("上限", f"{hi:g}"),
                ("目盛り間隔 (空欄=自動)", f"{tick:g}" if tick else "")]
        self.ents = []
        for i, (lab, val) in enumerate(rows):
            tk.Label(self.top, text=lab, bg=BG, fg=LABEL_FG).grid(row=i, column=0, padx=8, pady=6, sticky="e")
            e = tk.Entry(self.top, width=10)
            e.insert(0, val)
            e.grid(row=i, column=1, padx=8)
            self.ents.append(e)
        tk.Button(self.top, text="OK", command=self._ok).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        tk.Button(self.top, text="キャンセル", command=self.top.destroy).grid(row=3, column=0, padx=8)

    def _ok(self):
        try:
            lo = float(self.ents[0].get())
            hi = float(self.ents[1].get())
            ts = self.ents[2].get().strip()
            tick = float(ts) if ts else None
            if hi > lo and (tick is None or tick > 0):
                self.result = (lo, hi, tick)
        except ValueError:
            pass
        self.top.destroy()


class _ValueDialog:
    """1つの数値を入力(範囲チェック付き)。"""

    def __init__(self, parent, title, label, cur, lo=None, hi=None):
        self.done = False
        self.value = None
        self.lo, self.hi = lo, hi
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.configure(bg=BG)
        self.top.transient(parent)
        tk.Label(self.top, text=label, bg=BG, fg=LABEL_FG).grid(row=0, column=0, columnspan=2, padx=8, pady=6)
        self.e = tk.Entry(self.top, width=12)
        self.e.insert(0, f"{cur:g}")
        self.e.grid(row=1, column=0, columnspan=2, padx=8)
        tk.Button(self.top, text="OK", command=self._ok).grid(row=2, column=1, sticky="e", padx=8, pady=8)
        tk.Button(self.top, text="キャンセル", command=self.top.destroy).grid(row=2, column=0, padx=8)

    def _ok(self):
        try:
            v = float(self.e.get())
            if (self.lo is None or v >= self.lo) and (self.hi is None or v <= self.hi):
                self.value = v
                self.done = True
        except ValueError:
            pass
        self.top.destroy()


class _AlarmDialog:
    def __init__(self, parent, title, cur, low):
        self.done = False
        self.value = None
        self.top = tk.Toplevel(parent)
        self.top.title(f"アラーム — {title}")
        self.top.configure(bg=BG)
        self.top.transient(parent)
        tk.Label(self.top, text=("下限" if low else "上限") + "アラーム値 (空欄=無効)",
                 bg=BG, fg=LABEL_FG).grid(row=0, column=0, columnspan=2, padx=8, pady=6)
        self.e = tk.Entry(self.top, width=12)
        if cur is not None:
            self.e.insert(0, f"{cur:g}")
        self.e.grid(row=1, column=0, columnspan=2, padx=8)
        tk.Button(self.top, text="OK", command=self._ok).grid(row=2, column=1, sticky="e", padx=8, pady=8)
        tk.Button(self.top, text="キャンセル", command=self.top.destroy).grid(row=2, column=0, padx=8)

    def _ok(self):
        s = self.e.get().strip()
        if s == "":
            self.value = None
            self.done = True
        else:
            try:
                self.value = float(s)
                self.done = True
            except ValueError:
                pass
        self.top.destroy()
