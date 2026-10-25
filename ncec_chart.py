"""ロギング(livelog_*.jsonl)の分析チャート。

複数チャンネルを**縦に並べた時系列グラフ**として表示し、共通の時間軸で相関を見る
(例: 回転数・点火時期・AFR・KR を並べてノック時の挙動を確認)。
- 左: チャンネル選択(ログに含まれる項目)
- 右: 選択チャンネルを band として縦積み。マウスでカーソル線＋各値を表示
- ホイールで時間軸ズーム(カーソル中心)、ドラッグで横スクロール、[全体] で全域表示
"""
from __future__ import annotations

import json
import pathlib
import tkinter as tk
from tkinter import ttk

from ncec_dashboard import CH_RANGE, PID_LABEL

BG = "#0e1116"
PANEL = "#141a22"
GRID = "#243243"
AX = "#8fb0cc"
FG = "#eaf4ff"
CURSOR = "#ffb02e"
COLORS = ["#4ea1ff", "#7fe0a0", "#ffb02e", "#ff6b6b", "#c58cff", "#5ad1d1",
          "#f0a3c8", "#b5d33d", "#ff9f40", "#9fb0c8"]


def load_log(path):
    """jsonl を {ch:[(t,v)...]} と時間範囲に。ch は PID int / 合成ch int。"""
    series: dict[int, list] = {}
    tmin = tmax = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            t = float(rec.get("t", 0.0))
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
            for k, v in rec.get("pid", {}).items():
                try:
                    ch = int(k, 16) if isinstance(k, str) else int(k)
                    series.setdefault(ch, []).append((t, float(v)))
                except (ValueError, TypeError):
                    pass
    return series, (tmin or 0.0), (tmax or 0.0)


class ChartWindow(tk.Toplevel):
    def __init__(self, master, path, jp="Yu Gothic UI", mono="Consolas"):
        super().__init__(master)
        self.jp = jp
        self.mono = mono
        self.path = pathlib.Path(path)
        self.title("ログ分析チャート — " + self.path.name)
        self.geometry("1000x620")
        self.configure(bg=BG)
        self.series, self.t0, self.t1 = load_log(path)
        self.view0, self.view1 = self.t0, self.t1
        self._drag_x = None
        self._cursor_t = None

        order = [ch for ch in PID_LABEL if isinstance(ch, int) and ch in self.series]
        order += [ch for ch in self.series if ch not in order]
        self.order = order
        prefer = [0x0C, 0x0E, 0x34, 0x44, 0x11, 0x102, 0x05]
        self.sel = {ch: tk.BooleanVar(value=(ch in prefer or len(self.series) <= 4))
                    for ch in order}

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=f"{self.path.name}  ({len(self.series)}ch / {self.t1 - self.t0:.1f}s)",
                 bg=BG, fg=AX, font=(self.jp, 10)).pack(side="left", padx=8, pady=4)
        tk.Button(top, text="全体", command=self._fit).pack(side="right", padx=4)
        tk.Button(top, text="＋", width=3, command=lambda: self._zoom(0.7)).pack(side="right")
        tk.Button(top, text="－", width=3, command=lambda: self._zoom(1.4)).pack(side="right")
        tk.Label(top, text="ホイール=ズーム / ドラッグ=スクロール", bg=BG, fg=AX,
                 font=(self.jp, 9)).pack(side="right", padx=8)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=PANEL, width=170)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Label(left, text="表示チャンネル", bg=PANEL, fg=FG, font=(self.jp, 10, "bold")
                 ).pack(anchor="w", padx=8, pady=(8, 2))
        for i, ch in enumerate(order):
            name = PID_LABEL.get(ch, (f"0x{ch:X}",))[0]
            col = COLORS[i % len(COLORS)]
            f = tk.Frame(left, bg=PANEL)
            f.pack(fill="x", padx=6, pady=1)
            tk.Frame(f, bg=col, width=12, height=12).pack(side="left", padx=(0, 4))
            tk.Checkbutton(f, text=name, variable=self.sel[ch], bg=PANEL, fg=FG,
                           selectcolor="#0e1116", activebackground=PANEL, activeforeground=FG,
                           font=(self.jp, 9), command=self._redraw, anchor="w").pack(side="left", fill="x")

        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: (setattr(self, "_cursor_t", None), self._redraw()))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_pan)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_x", None))
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self._redraw()

    # ---- ズーム/スクロール ----
    def _fit(self):
        self.view0, self.view1 = self.t0, self.t1
        self._redraw()

    def _zoom(self, factor, center=None):
        span = (self.view1 - self.view0) * factor
        span = max(0.2, min(self.t1 - self.t0, span))
        if center is None:
            center = (self.view0 + self.view1) / 2
        self.view0 = center - span / 2
        self.view1 = center + span / 2
        self._clamp()
        self._redraw()

    def _clamp(self):
        span = self.view1 - self.view0
        if self.view0 < self.t0:
            self.view0, self.view1 = self.t0, self.t0 + span
        if self.view1 > self.t1:
            self.view1, self.view0 = self.t1, self.t1 - span
        self.view0 = max(self.t0, self.view0)
        self.view1 = min(self.t1, self.view1)

    def _on_wheel(self, e):
        c = self._t_at(e.x)
        self._zoom(0.8 if e.delta > 0 else 1.25, center=c)

    def _on_press(self, e):
        self._drag_x = e.x

    def _on_pan(self, e):
        if self._drag_x is None:
            return
        plot_w = max(1, self.canvas.winfo_width() - self._ml() - 10)
        dt = (e.x - self._drag_x) / plot_w * (self.view1 - self.view0)
        self.view0 -= dt
        self.view1 -= dt
        self._clamp()
        self._drag_x = e.x
        self._redraw()

    def _on_motion(self, e):
        self._cursor_t = self._t_at(e.x)
        self._redraw()

    def _ml(self):
        return 58   # 左マージン(y軸ラベル)

    def _t_at(self, px):
        ml = self._ml()
        plot_w = max(1, self.canvas.winfo_width() - ml - 10)
        fr = min(1.0, max(0.0, (px - ml) / plot_w))
        return self.view0 + (self.view1 - self.view0) * fr

    # ---- 描画 ----
    def _redraw(self):
        c = self.canvas
        c.delete("all")
        W = c.winfo_width() or 820
        H = c.winfo_height() or 560
        ml = self._ml()
        px0, px1 = ml, W - 10
        plot_w = max(1, px1 - px0)
        sel = [ch for ch in self.order if self.sel[ch].get()]
        if not sel:
            c.create_text(W / 2, H / 2, text="左でチャンネルを選択", fill=AX, font=(self.jp, 12))
            return
        top_pad, bot_pad = 8, 26
        band_h = max(40, (H - top_pad - bot_pad) / len(sel))

        def tx(t):
            return px0 + plot_w * (t - self.view0) / max(1e-6, self.view1 - self.view0)

        for bi, ch in enumerate(sel):
            by0 = top_pad + bi * band_h
            by1 = by0 + band_h - 6
            col = COLORS[self.order.index(ch) % len(COLORS)]
            name, unit, fmt = PID_LABEL.get(ch, (f"0x{ch:X}", "", "%.1f"))
            data = self.series.get(ch, [])
            vis = [(t, v) for t, v in data if self.view0 - 1 <= t <= self.view1 + 1]
            lo, hi = self._yrange(ch, vis)
            c.create_rectangle(px0, by0, px1, by1, fill=PANEL, outline=GRID)

            def py(v):
                fr = 0.0 if hi <= lo else min(1.0, max(0.0, (v - lo) / (hi - lo)))
                return by1 - (by1 - by0) * fr
            for gf in (0.0, 0.5, 1.0):
                yy = by0 + (by1 - by0) * gf
                c.create_line(px0, yy, px1, yy, fill=GRID)
                c.create_text(px0 - 4, yy, text=f"{hi - (hi - lo) * gf:g}", anchor="e",
                              fill=AX, font=(self.jp, 7))
            c.create_text(px0 + 6, by0 + 10, text=f"{name}{(' ['+unit+']') if unit else ''}",
                          anchor="w", fill=col, font=(self.jp, 9, "bold"))
            if len(vis) >= 2:
                pts = []
                for t, v in vis:
                    pts += [tx(t), py(v)]
                c.create_line(*pts, fill=col, width=1)
            # カーソル値
            if self._cursor_t is not None and vis:
                vv = self._sample_at(data, self._cursor_t)
                if vv is not None:
                    yy = py(vv)
                    c.create_oval(tx(self._cursor_t) - 3, yy - 3, tx(self._cursor_t) + 3, yy + 3,
                                  fill=col, outline="")
                    c.create_text(px1 - 4, by0 + 10, text=(fmt % vv) + (unit or ""), anchor="e",
                                  fill=FG, font=(self.mono, 10, "bold"))

        # 時間軸
        for gf in (0.0, 0.25, 0.5, 0.75, 1.0):
            t = self.view0 + (self.view1 - self.view0) * gf
            gx = px0 + plot_w * gf
            c.create_line(gx, top_pad, gx, H - bot_pad, fill="#1b2633")
            c.create_text(gx, H - bot_pad + 12, text=f"{t:.1f}s", fill=AX, font=(self.jp, 8))
        # カーソル線
        if self._cursor_t is not None:
            gx = tx(self._cursor_t)
            c.create_line(gx, top_pad, gx, H - bot_pad, fill=CURSOR)
            c.create_text(gx, top_pad, text=f"{self._cursor_t:.2f}s", anchor="n", fill=CURSOR,
                          font=(self.mono, 9))

    def _yrange(self, ch, vis):
        if ch in CH_RANGE:
            return CH_RANGE[ch]
        if not vis:
            return 0.0, 1.0
        vs = [v for _t, v in vis]
        lo, hi = min(vs), max(vs)
        if hi - lo < 1e-6:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.1
        return lo - pad, hi + pad

    @staticmethod
    def _sample_at(data, t):
        """時刻 t に最も近いサンプル値(前方保持)。"""
        if not data:
            return None
        best = None
        for tt, vv in data:
            if tt <= t + 1e-9:
                best = vv
            else:
                break
        return best if best is not None else data[0][1]
