"""マップ(表)を表示・編集するペイン。キャンバスに描くので、4 分割や別ウィンドウでも軽い。

1 枚の表を受け持ち、次を行う:
  - 軸の見出し・ヒートマップ・単位の描画、拡大/縮小
  - セルの選択(クリック / ドラッグ / Shift+クリック / Shift+矢印 / 行・列の見出しクリック)
  - 値の入力(数字を打つ・Enter/F2・ダブルクリック。複数セルを選んで入力すると全部に入る)
  - 一括操作(増減・設定・加算・％・倍率・補間・平滑化・下/右へコピー・コピー/貼り付け)
  - ライブの運転点(●)、保存後に変えたセルの印(左上の橙)、相方(制御⇔監視)と違うセルの印(右下の赤)
ROM への書き込み・元に戻す・相方への同時反映・範囲チェックはエディタ(host)が行う。
"""
from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from ncecu import i18n

BG = "#1e2128"
HEAD_BG = "#262b36"
HEAD_FG = "#dfe3ea"
BORDER_ON = "#3a8ee6"
BORDER_OFF = "#2b2f3a"
AXLBL_BG = "#3a4a63"
AXLBL_FG = "#eaf2ff"
HDR_BG = "#2b3340"
HDR_FG = "#cfe0f5"
HDR_EDIT_BG = "#45526b"
HDR_SEL_BG = "#4d6488"
CELL_FG = "#0b0d12"
NAN_BG = "#3a3f4b"
NAN_FG = "#8a94a6"
SEL_TINT = (70, 120, 220)
SEL_BOX = "#9fd0ff"
CURSOR = "#ffd60a"
CURSOR_IDLE = "#b8c2d0"
MARK_MOD = "#ff9f1c"
MARK_PAIR = "#ff3b30"
LIVE = "#ff3b30"


def heat_color(v: float, lo: float, hi: float) -> str:
    if hi <= lo:
        return "#2b2f3a"
    t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    # blue -> cyan -> green -> yellow -> red
    stops = [(0.0, (40, 70, 160)), (0.25, (30, 150, 170)),
             (0.5, (40, 160, 80)), (0.75, (210, 180, 50)), (1.0, (200, 60, 50))]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            r = int(c0[0] + (c1[0] - c0[0]) * f)
            g = int(c0[1] + (c1[1] - c0[1]) * f)
            b = int(c0[2] + (c1[2] - c0[2]) * f)
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#c83c32"


def _tint(hexcol: str, rgb=SEL_TINT, f=0.5) -> str:
    try:
        r, g, b = int(hexcol[1:3], 16), int(hexcol[3:5], 16), int(hexcol[5:7], 16)
    except (ValueError, IndexError):
        return hexcol
    r = int(r * (1 - f) + rgb[0] * f)
    g = int(g * (1 - f) + rgb[1] * f)
    b = int(b * (1 - f) + rgb[2] * f)
    return f"#{r:02x}{g:02x}{b:02x}"


def isnum(v) -> bool:
    return isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))


# ---------------- 数値操作(純粋関数。テストしやすいよう GUI から分けておく) ----------------
def positions(axis_vals, n: int) -> list[float]:
    """補間に使う位置。軸の値が数値で単調(昇順/降順)なら軸の値、そうでなければ 0..n-1。"""
    if axis_vals and len(axis_vals) >= n and all(isnum(a) for a in axis_vals[:n]):
        a = [float(x) for x in axis_vals[:n]]
        if all(a[i] < a[i + 1] for i in range(n - 1)) or all(a[i] > a[i + 1] for i in range(n - 1)):
            return a
    return [float(i) for i in range(n)]


def interp_1d(vals, pos, i0: int, i1: int) -> dict[int, float]:
    """vals[i0] と vals[i1] を端として、間を pos に沿って直線で埋める。{index: 値}"""
    if i1 - i0 < 2 or not (isnum(vals[i0]) and isnum(vals[i1])):
        return {}
    a, b = float(vals[i0]), float(vals[i1])
    pa, pb = pos[i0], pos[i1]
    out = {}
    for i in range(i0 + 1, i1):
        f = (pos[i] - pa) / (pb - pa) if pb != pa else (i - i0) / (i1 - i0)
        out[i] = a + (b - a) * f
    return out


def interp_2d(grid, r0, c0, r1, c1, xpos, ypos) -> dict[tuple[int, int], float]:
    """四隅の値から選択範囲を双線形で埋める(四隅は変えない)。"""
    if r1 - r0 < 1 or c1 - c0 < 1:
        return {}
    q = (grid[r0][c0], grid[r0][c1], grid[r1][c0], grid[r1][c1])
    if not all(isnum(v) for v in q):
        return {}
    q00, q01, q10, q11 = (float(v) for v in q)
    out = {}
    for r in range(r0, r1 + 1):
        fy = (ypos[r] - ypos[r0]) / (ypos[r1] - ypos[r0]) if ypos[r1] != ypos[r0] else (r - r0) / (r1 - r0)
        for c in range(c0, c1 + 1):
            if (r, c) in ((r0, c0), (r0, c1), (r1, c0), (r1, c1)):
                continue
            fx = (xpos[c] - xpos[c0]) / (xpos[c1] - xpos[c0]) if xpos[c1] != xpos[c0] else (c - c0) / (c1 - c0)
            out[(r, c)] = (q00 * (1 - fx) * (1 - fy) + q01 * fx * (1 - fy)
                           + q10 * (1 - fx) * fy + q11 * fx * fy)
    return out


def smooth(grid, cells) -> dict[tuple[int, int], float]:
    """各セルを周り 3×3(表の中にある数値だけ)の平均にする。中心は重み 2。"""
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    out = {}
    for r, c in cells:
        if not isnum(grid[r][c]):
            continue
        s = w = 0.0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols and isnum(grid[rr][cc]):
                    k = 2.0 if (dr == 0 and dc == 0) else 1.0
                    s += float(grid[rr][cc]) * k
                    w += k
        if w:
            out[(r, c)] = s / w
    return out


def parse_clip(text: str) -> list[list[float | None]]:
    """表計算ソフトから貼り付けた文字列(タブ/カンマ/空白区切り)を数値の2次元リストに。"""
    rows = []
    for line in text.replace("\r", "").split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t") if "\t" in line else (line.split(",") if "," in line else line.split())
        row = []
        for p in parts:
            try:
                row.append(float(p.strip()))
            except ValueError:
                row.append(None)
        rows.append(row)
    return rows


def ask_number(parent, title, prompt, initial="", font=None):
    """数値を1つ入力させる小さなダイアログ。キャンセルなら None。"""
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=BG)
    top.transient(parent.winfo_toplevel())
    tk.Label(top, text=prompt, bg=BG, fg=HEAD_FG, justify="left", anchor="w", wraplength=380,
             font=font).pack(fill="x", padx=12, pady=(10, 4))
    e = tk.Entry(top, width=16, font=font)
    e.insert(0, initial)
    e.select_range(0, "end")
    e.pack(padx=12, pady=4)
    res = {"v": None}

    def ok(_e=None):
        try:
            res["v"] = float(e.get().strip())
        except ValueError:
            e.configure(bg="#ffd0d0")
            return
        top.destroy()

    b = tk.Frame(top, bg=BG)
    b.pack(fill="x", padx=12, pady=(4, 10))
    tk.Button(b, text="OK", width=8, command=ok).pack(side="right")
    tk.Button(b, text="キャンセル" if i18n.get_language() != "en" else "Cancel",
              command=top.destroy).pack(side="right", padx=(0, 6))
    e.bind("<Return>", ok)
    e.bind("<KP_Enter>", ok)
    e.bind("<Escape>", lambda _e: top.destroy())
    top.grab_set()
    e.focus_set()
    parent.wait_window(top)
    return res["v"]


class TableView(tk.Frame):
    """1 枚の表を受け持つペイン。host はエディタ(ROM・定義・書き込み・ショートカットを持つ)。"""

    def __init__(self, master, host, slot):
        super().__init__(master, bg=BORDER_OFF)
        self.host = host
        self.slot = slot                    # 分割ペインの番号(0〜3) / "float"(別ウィンドウ)
        self.table = None
        self.zoom = 1.0
        self.grid_vals: list[list] = []
        self.rows = self.cols = 0
        self.xvals = self.yvals = None
        self.sc = None
        self.anchor = (0, 0)
        self.cursor = (0, 0)
        self.active = False
        self._items: dict[tuple[int, int], tuple[int, int]] = {}
        self._fill: dict[tuple[int, int], str] = {}
        self._texts: dict[tuple[int, int], str] = {}
        self._tinted: set = set()
        self._g = None                      # 描画の寸法
        self._edit = None
        self._live = None                   # (row_f, col_f)
        self._drag = False
        self._fonts = {}
        self.pair_diff = 0

        inner = tk.Frame(self, bg=BG)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        hdr = tk.Frame(inner, bg=HEAD_BG)
        hdr.pack(fill="x")
        self._hdr = hdr
        self.btn_close = tk.Label(hdr, text=" × ", bg=HEAD_BG, fg="#c9d2de", cursor="hand2",
                                  font=(host.jp, 10, "bold"))
        self.btn_close.pack(side="right")
        self.btn_detach = tk.Label(hdr, text=" ⧉ ", bg=HEAD_BG, fg="#c9d2de", cursor="hand2",
                                   font=(host.jp, 10))
        if slot != "float":
            self.btn_detach.pack(side="right")
        self.btn_pair = tk.Label(hdr, text=" ⇔ ", bg=HEAD_BG, fg="#c9d2de", cursor="hand2",
                                 font=(host.jp, 10, "bold"))
        self.btn_pair.pack(side="right")
        self.title = tk.Label(hdr, text="", bg=HEAD_BG, fg=HEAD_FG, anchor="w", justify="left",
                              font=(host.jp, 9, "bold"))
        self.title.pack(side="left", fill="x", expand=True, padx=(6, 2), pady=1)
        self.pair_lbl = tk.Label(inner, text="", bg=HEAD_BG, fg="#9fb0c8", anchor="w",
                                 font=(host.jp, 9))
        self.btn_close.bind("<Button-1>", lambda _e: host.view_close(self))
        self.btn_detach.bind("<Button-1>", lambda _e: host.view_detach(self))
        self.btn_pair.bind("<Button-1>", lambda _e: host.view_pair(self))
        for w in (hdr, self.title, self.pair_lbl):
            w.bind("<Button-1>", lambda _e: self.focus_table())

        # 4 枚のキャンバス: 左上(軸名)・上(X 軸の見出し)・左(Y 軸の見出し)・本体(セル)。
        # 見出しは本体と一緒にスクロールし、スクロールしても見えたままになる(見出しの固定)。
        body = tk.Frame(inner, bg=BG)
        body.pack(fill="both", expand=True)
        kw = dict(bg=BG, highlightthickness=0, bd=0)
        self.cv_corner = tk.Canvas(body, width=1, height=1, **kw)
        self.cv_xh = tk.Canvas(body, height=1, **kw)
        self.cv_yh = tk.Canvas(body, width=1, **kw)
        self.canvas = tk.Canvas(body, takefocus=1, xscrollincrement=16, yscrollincrement=16, **kw)
        self.vsb = ttk.Scrollbar(body, orient="vertical", command=self._yview)
        self.hsb = ttk.Scrollbar(body, orient="horizontal", command=self._xview)
        self.canvas.configure(xscrollcommand=self._on_xscroll, yscrollcommand=self._on_yscroll)
        self.cv_corner.grid(row=0, column=0, sticky="nsew")
        self.cv_xh.grid(row=0, column=1, sticky="nsew")
        self.cv_yh.grid(row=1, column=0, sticky="nsew")
        self.canvas.grid(row=1, column=1, sticky="nsew")
        self.vsb.grid(row=1, column=2, sticky="ns")
        self.hsb.grid(row=2, column=1, sticky="ew")
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(1, weight=1)
        c = self.canvas
        c.bind("<Button-1>", self._press)
        c.bind("<B1-Motion>", self._motion)
        c.bind("<ButtonRelease-1>", lambda _e: setattr(self, "_drag", False))
        c.bind("<Double-Button-1>", self._double)
        c.bind("<Button-3>", self._context)
        c.bind("<KeyPress>", self._key)
        c.bind("<FocusIn>", self._focus_in)
        c.bind("<FocusOut>", lambda _e: self._draw_selection())
        self.cv_xh.bind("<Button-1>", lambda e: self._hdr_press(e, "x"))
        self.cv_yh.bind("<Button-1>", lambda e: self._hdr_press(e, "y"))
        self.cv_xh.bind("<Double-Button-1>", lambda e: self._hdr_double(e, "x"))
        self.cv_yh.bind("<Double-Button-1>", lambda e: self._hdr_double(e, "y"))
        self.cv_corner.bind("<Button-1>", lambda _e: (self.focus_table(), self.select_all()))
        for w in (c, self.cv_xh, self.cv_yh, self.cv_corner):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda e: self._wheel(e, 120))
            w.bind("<Button-5>", lambda e: self._wheel(e, -120))
        self.redraw()

    # ---------------- スクロール(本体と見出しを一緒に) ----------------
    def _xview(self, *a):
        self.canvas.xview(*a)

    def _yview(self, *a):
        self.canvas.yview(*a)

    def _on_xscroll(self, f0, f1):
        self.hsb.set(f0, f1)
        self.cv_xh.xview_moveto(f0)
        try:                                    # 軸名は見えている範囲の左端に置く
            g = self._g
            if g and g.get("lab_h"):
                self.cv_xh.coords("xlabel", self.cv_xh.canvasx(0) + 6, g["lab_h"] / 2)
        except tk.TclError:
            pass

    def _on_yscroll(self, f0, f1):
        self.vsb.set(f0, f1)
        self.cv_yh.yview_moveto(f0)

    # ---------------- 状態 ----------------
    def focus_table(self):
        try:
            self.canvas.focus_set()
        except tk.TclError:
            pass
        self.host.set_active(self)

    def set_active(self, on: bool):
        self.active = on
        try:
            self.configure(bg=BORDER_ON if on else BORDER_OFF)
        except tk.TclError:
            pass

    def _focus_in(self, _e=None):
        self.host.set_active(self)
        self._draw_selection()

    def set_table(self, t, keep_sel=False):
        self.cancel_edit()
        changed = t is not self.table
        self.table = t
        self._live = None
        if changed and not keep_sel:
            self.anchor = self.cursor = (0, 0)
            try:
                self.canvas.xview_moveto(0)
                self.canvas.yview_moveto(0)
            except tk.TclError:
                pass
        self.redraw()

    def set_zoom(self, z):
        self.zoom = max(0.5, min(2.5, round(z, 2)))
        self.redraw()

    @property
    def editing(self) -> bool:
        return self._edit is not None

    # ---------------- 描画 ----------------
    def _font(self, size, bold=False, family=None):
        key = (family or self.host.mono, size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = tkfont.Font(family=key[0], size=size, weight="bold" if bold else "normal")
            self._fonts[key] = f
        return f

    def _read(self):
        h = self.host
        t = self.table
        self.sc = h.romdef.scalings.get(t.scaling)
        self.grid_vals = h.rom.read_table(t)
        self.rows, self.cols = h.rom.dims(t)
        xa, ya = t.x_axis, t.y_axis
        self.xvals = h.rom.read_axis(xa)[:self.cols] if xa else None
        self.yvals = h.rom.read_axis(ya)[:self.rows] if ya else None
        if not self.xvals:
            self.xvals = None
        if not self.yvals:
            self.yvals = None

    def _cell_text(self, v):
        return self.host.fmt_value(v, self.sc)

    def _ax_text(self, v):
        return self._cell_text(v) if isinstance(v, float) else str(v)

    def _clear_canvases(self):
        for cv in (self.canvas, self.cv_xh, self.cv_yh, self.cv_corner):
            cv.delete("all")

    def redraw(self):
        """表を読み直して全部描き直す。"""
        c = self.canvas
        self.cancel_edit()
        self._clear_canvases()
        self._items.clear()
        self._fill.clear()
        self._texts.clear()
        self._tinted = set()
        self._g = None
        h = self.host
        if self.table is None or h.rom is None or h.romdef is None:
            self.cv_corner.configure(width=1, height=1)
            self.cv_xh.configure(height=1)
            self.cv_yh.configure(width=1)
            msg = ("左の一覧から表を選ぶと、このペインに表示します（先にこのペインをクリック）。"
                   if h.lang != "en" else "Pick a table in the list to show it here (click this pane first).")
            c.create_text(12, 12, text=msg, anchor="nw", fill="#7f8b98", font=(h.jp, 10),
                          width=max(200, c.winfo_width() - 24))
            c.configure(scrollregion=(0, 0, 10, 10))
            self._update_header()
            return
        try:
            self._read()
        except Exception as e:  # noqa: BLE001  定義の異常で全体を止めない
            c.create_text(12, 12, text=f"表示できません: {e}", anchor="nw", fill="#ff8080")
            self._update_header()
            return
        self._layout_and_draw()
        self._update_header()

    def _layout_and_draw(self):
        c = self.canvas
        h = self.host
        t = self.table
        z = self.zoom
        rows, cols = self.rows, self.cols
        fsz = max(6, int(round(9 * z)))
        fcell = self._font(fsz)
        fhdr = self._font(fsz, True)
        flbl = self._font(max(6, int(round(9 * z))), True, h.jp)
        grid = self.grid_vals
        texts = [[self._cell_text(grid[r][col]) for col in range(cols)] for r in range(rows)]
        xt = [self._ax_text(v) for v in (self.xvals or [])]
        yt = [self._ax_text(v) for v in (self.yvals or [])]
        pad = int(10 * z)
        wmax = max([fcell.measure(s) for row in texts for s in row] + [fhdr.measure(s) for s in xt] + [10])
        cw = max(int(50 * z), wmax + pad)
        ch = fcell.metrics("linespace") + int(7 * z)
        x_label = i18n.axis_label(t.x_axis.name) if (t.x_axis and self.xvals) else ""
        y_label = i18n.axis_label(t.y_axis.name) if (t.y_axis and self.yvals) else ""
        show_labels = bool(x_label or y_label)
        yhw = 0
        if self.yvals:
            yhw = max([fhdr.measure(s) for s in yt] + [10]) + pad
            if y_label:
                yhw = max(yhw, flbl.measure(f"↓ {y_label}") + pad)
        lab_h = ch if show_labels else 0
        top_h = lab_h + (ch if self.xvals else 0)
        W, H = cols * cw, rows * ch
        self._g = {"cw": cw, "ch": ch, "yhw": yhw, "lab_h": lab_h, "top_h": top_h, "fcell": fcell, "fhdr": fhdr}

        # 色の範囲(NaN=未使用セルは除く)
        flat = [v for row in grid for v in row if isnum(v)]
        lo, hi = (min(flat), max(flat)) if flat else (0, 1)
        self._lohi = (lo, hi)

        # 見出しキャンバスの大きさ(見出しが無い側は 0 にする)
        self.cv_corner.configure(width=max(1, yhw), height=max(1, top_h))
        self.cv_xh.configure(height=max(1, top_h))
        self.cv_yh.configure(width=max(1, yhw))
        if y_label and lab_h:
            self.cv_corner.create_rectangle(0, 0, yhw - 1, lab_h - 1, fill=AXLBL_BG, outline="")
            self.cv_corner.create_text(yhw / 2, lab_h / 2, text=f"↓ {y_label}", fill=AXLBL_FG, font=flbl)
        if x_label and lab_h:
            self.cv_xh.create_rectangle(0, 0, W - 1, lab_h - 1, fill=AXLBL_BG, outline="")
            self.cv_xh.create_text(6, lab_h / 2, text=f"{x_label} →", fill=AXLBL_FG, font=flbl, anchor="w",
                                   tags=("xlabel",))
        ax_ed_x = h.axis_edit and t.x_axis is not None and not t.x_axis.static_values
        ax_ed_y = h.axis_edit and t.y_axis is not None and not t.y_axis.static_values
        self._hdr_bg = (HDR_EDIT_BG if ax_ed_x else HDR_BG, HDR_EDIT_BG if ax_ed_y else HDR_BG)
        for j, s in enumerate(xt):
            x = j * cw
            self.cv_xh.create_rectangle(x, lab_h, x + cw - 1, lab_h + ch - 1, fill=self._hdr_bg[0], outline="",
                                        tags=(f"xh{j}",))
            self.cv_xh.create_text(x + cw / 2, lab_h + ch / 2, text=s, fill="#ffffff" if ax_ed_x else HDR_FG,
                                   font=fhdr, tags=(f"xht{j}",))
        for i, s in enumerate(yt):
            y = i * ch
            self.cv_yh.create_rectangle(0, y, yhw - 1, y + ch - 1, fill=self._hdr_bg[1], outline="",
                                        tags=(f"yh{i}",))
            self.cv_yh.create_text(yhw / 2, y + ch / 2, text=s, fill="#ffffff" if ax_ed_y else HDR_FG,
                                   font=fhdr, tags=(f"yht{i}",))
        for r in range(rows):
            y = r * ch
            for col in range(cols):
                x = col * cw
                v = grid[r][col]
                if isnum(v):
                    fill, fg = heat_color(v, lo, hi), CELL_FG
                else:
                    fill, fg = NAN_BG, NAN_FG
                rid = c.create_rectangle(x, y, x + cw - 1, y + ch - 1, fill=fill, outline="")
                tid = c.create_text(x + cw / 2, y + ch / 2, text=texts[r][col], fill=fg, font=fcell)
                self._items[(r, col)] = (rid, tid)
                self._fill[(r, col)] = fill
                self._texts[(r, col)] = texts[r][col]
        units = i18n.unit_of(t.category, t.name)
        Hs = H
        if units:
            c.create_text(W - 2, H + 3, text=f"[{units}]", anchor="ne", fill="#9fb0c8",
                          font=(h.jp, max(7, int(round(9 * z))), "bold"))
            Hs += ch
        c.configure(scrollregion=(0, 0, W, Hs))
        self.cv_xh.configure(scrollregion=(0, 0, W, max(1, top_h)))
        self.cv_yh.configure(scrollregion=(0, 0, max(1, yhw), Hs))
        self._draw_marks()
        self._clamp_sel()
        self._draw_selection()
        self._draw_live()

    def refresh(self):
        """値だけ変わったとき(編集・元に戻す)。寸法が変わらなければ文字と色だけ差し替える。"""
        if self.table is None or self._g is None or self.host.rom is None:
            self.redraw()
            return
        try:
            old_dims = (self.rows, self.cols)
            self._read()
        except Exception:  # noqa: BLE001
            self.redraw()
            return
        g = self._g
        if (self.rows, self.cols) != old_dims:
            self.redraw()
            return
        grid = self.grid_vals
        texts = {(r, c): self._cell_text(grid[r][c]) for r in range(self.rows) for c in range(self.cols)}
        xt = [self._ax_text(v) for v in (self.xvals or [])]
        yt = [self._ax_text(v) for v in (self.yvals or [])]
        if any(g["fcell"].measure(s) + 6 > g["cw"] for s in texts.values()) \
                or any(g["fhdr"].measure(s) + 6 > g["cw"] for s in xt) \
                or any(g["fhdr"].measure(s) + 6 > g["yhw"] for s in yt):
            self.redraw()
            return
        flat = [v for row in grid for v in row if isnum(v)]
        lo, hi = (min(flat), max(flat)) if flat else (0, 1)
        self._lohi = (lo, hi)
        c = self.canvas
        for rc, (rid, tid) in self._items.items():
            v = grid[rc[0]][rc[1]]
            fill = heat_color(v, lo, hi) if isnum(v) else NAN_BG
            self._fill[rc] = fill
            if texts[rc] != self._texts.get(rc):
                c.itemconfigure(tid, text=texts[rc])
                self._texts[rc] = texts[rc]
            c.itemconfigure(rid, fill=_tint(fill) if rc in self._tinted else fill)
        for j, s in enumerate(xt):                 # 軸の値(軸編集のあと)
            self.cv_xh.itemconfigure(f"xht{j}", text=s)
        for i, s in enumerate(yt):
            self.cv_yh.itemconfigure(f"yht{i}", text=s)
        self._draw_marks()
        self._update_header()

    def _cell_box(self, r, col):
        g = self._g
        x = col * g["cw"]
        y = r * g["ch"]
        return x, y, x + g["cw"] - 1, y + g["ch"] - 1

    def _draw_marks(self):
        """保存後に変えたセル(左上の橙)と、相方(制御⇔監視)と違うセル(右下の赤)。"""
        c = self.canvas
        c.delete("mark")
        self.pair_diff = 0
        h = self.host
        t = self.table
        if t is None or self._g is None or self.sc is None:
            return
        size = self.sc.size
        data = h.rom.data
        orig = h.orig_data
        partner, ok = h.pair_info(t)
        k = max(4, int(6 * self.zoom))
        for (r, col) in self._items:
            off = (r * self.cols + col) * size
            a = t.address + off
            x0, y0, x1, y1 = self._cell_box(r, col)
            if h.show_marks and orig is not None and data[a:a + size] != orig[a:a + size]:
                c.create_polygon(x0, y0, x0 + k, y0, x0, y0 + k, fill=MARK_MOD, outline="", tags="mark")
            if partner is not None and ok:
                pa = partner.address + off
                if data[a:a + size] != data[pa:pa + size]:
                    self.pair_diff += 1
                    c.create_polygon(x1 + 1, y1 + 1, x1 + 1 - k, y1 + 1, x1 + 1, y1 + 1 - k,
                                     fill=MARK_PAIR, outline="", tags="mark")
        c.tag_raise("sel")
        c.tag_raise("live")

    def _update_header(self):
        h = self.host
        t = self.table
        ja = h.lang != "en"
        tag = (f"[{self.slot + 1}] " if isinstance(self.slot, int) else "")
        if t is None:
            self.title.config(text=tag + ("（空）" if ja else "(empty)"))
            self.pair_lbl.pack_forget()
            self.btn_pair.config(fg="#5a6372")
            return
        units = i18n.unit_of(t.category, t.name)
        self.title.config(text=f"{tag}{i18n.translate_table_name(t.name)}   @0x{t.address:X}   "
                               f"{self.rows}x{self.cols}" + (f"   [{units}]" if units else ""))
        partner, ok = h.pair_info(t)
        if partner is None:
            self.pair_lbl.pack_forget()
            self.btn_pair.config(fg="#5a6372")
            return
        self.btn_pair.config(fg="#c9d2de")
        side_j, side_e = h.pair_side(t)
        if not ok:
            txt = (f"⇔ {side_j} 0x{partner.address:X}：寸法か型が違うため照合・同時編集はしません" if ja
                   else f"⇔ {side_e} 0x{partner.address:X}: size/type differ - not compared or mirrored")
            fg = "#e2b33a"
        elif self.pair_diff:
            txt = (f"⚠ {side_j} 0x{partner.address:X} と {self.pair_diff} セル違います（右下の赤い印）。"
                   "制御側と監視側は同じ値にしてください" if ja else
                   f"⚠ {self.pair_diff} cells differ from {side_e} 0x{partner.address:X} (red corner). "
                   "Keep control and monitor equal")
            fg = "#ff8a80"
        else:
            txt = (f"⇔ {side_j} 0x{partner.address:X}：全セル一致" if ja
                   else f"⇔ {side_e} 0x{partner.address:X}: all cells equal")
            fg = "#7fe0a0"
        if h.mirror_pairs and ok:
            txt += ("　／ペア同時編集 ON" if ja else "  / paired editing ON")
        self.pair_lbl.config(text=txt, fg=fg)
        self.pair_lbl.pack(fill="x", after=self._hdr)

    # ---------------- 選択 ----------------
    def _clamp_sel(self):
        rmax, cmax = max(0, self.rows - 1), max(0, self.cols - 1)
        self.anchor = (min(self.anchor[0], rmax), min(self.anchor[1], cmax))
        self.cursor = (min(self.cursor[0], rmax), min(self.cursor[1], cmax))

    def sel_rect(self):
        (a0, a1), (b0, b1) = self.anchor, self.cursor
        return min(a0, b0), min(a1, b1), max(a0, b0), max(a1, b1)

    def sel_cells(self):
        r0, c0, r1, c1 = self.sel_rect()
        return [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                if r < self.rows and c < self.cols]

    def num_cells(self):
        return [(r, c) for (r, c) in self.sel_cells() if isnum(self.grid_vals[r][c])]

    def set_selection(self, anchor, cursor=None, notify=True, see=True):
        if self.table is None or not self._items:
            return
        self.anchor = tuple(anchor)
        self.cursor = tuple(cursor) if cursor is not None else tuple(anchor)
        self._clamp_sel()
        self._draw_selection()
        if see:
            self._see(self.cursor)
        if notify:
            self.host.on_selection(self)

    def _draw_selection(self):
        c = self.canvas
        try:
            c.delete("sel")
        except tk.TclError:
            return
        if self.table is None or not self._items or self._g is None:
            return
        r0, c0, r1, c1 = self.sel_rect()
        multi = (r1 > r0) or (c1 > c0)
        new = set(self.sel_cells()) if multi else set()
        for rc in self._tinted - new:
            if rc in self._items:
                c.itemconfigure(self._items[rc][0], fill=self._fill[rc])
        for rc in new - self._tinted:
            if rc in self._items:
                c.itemconfigure(self._items[rc][0], fill=_tint(self._fill[rc]))
        self._tinted = new
        # 選択中の行・列の見出しを明るく
        hb = getattr(self, "_hdr_bg", (HDR_BG, HDR_BG))
        for j in range(len(self.xvals or [])):
            self.cv_xh.itemconfigure(f"xh{j}", fill=HDR_SEL_BG if c0 <= j <= c1 else hb[0])
        for i in range(len(self.yvals or [])):
            self.cv_yh.itemconfigure(f"yh{i}", fill=HDR_SEL_BG if r0 <= i <= r1 else hb[1])
        try:
            focused = self.focus_get() is self.canvas
        except (tk.TclError, KeyError):
            focused = False
        x0, y0, _, _ = self._cell_box(r0, c0)
        _, _, x1, y1 = self._cell_box(r1, c1)
        if multi:
            c.create_rectangle(x0, y0, x1, y1, outline=SEL_BOX, width=2, tags="sel")
        cx0, cy0, cx1, cy1 = self._cell_box(*self.cursor)
        c.create_rectangle(cx0 + 1, cy0 + 1, cx1 - 1, cy1 - 1, outline=CURSOR if focused else CURSOR_IDLE,
                           width=2, tags="sel")
        c.tag_raise("mark")
        c.tag_raise("sel")
        c.tag_raise("live")

    def _see(self, rc):
        if self._g is None:
            return
        c = self.canvas
        try:
            sr = [float(v) for v in str(c.cget("scrollregion")).split()]
            W, H = sr[2], sr[3]
            vw, vh = c.winfo_width(), c.winfo_height()
            vx, vy = c.canvasx(0), c.canvasy(0)
        except (tk.TclError, ValueError, IndexError):
            return
        x0, y0, x1, y1 = self._cell_box(*rc)
        if W > vw and vw > 1:
            if x0 < vx:
                c.xview_moveto(max(0.0, x0 / W))
            elif x1 > vx + vw:
                c.xview_moveto(min(1.0, (x1 - vw + 2) / W))
        if H > vh and vh > 1:
            if y0 < vy:
                c.yview_moveto(max(0.0, y0 / H))
            elif y1 > vy + vh:
                c.yview_moveto(min(1.0, (y1 - vh + 2) / H))

    def move_cursor(self, dr, dc, extend=False, jump=False):
        if not self._items:
            return
        r, col = self.cursor
        if jump:
            r = (self.rows - 1 if dr > 0 else 0) if dr else r
            col = (self.cols - 1 if dc > 0 else 0) if dc else col
        else:
            r = max(0, min(self.rows - 1, r + dr))
            col = max(0, min(self.cols - 1, col + dc))
        if extend:
            self.set_selection(self.anchor, (r, col))
        else:
            self.set_selection((r, col))

    def select_all(self):
        if self._items:
            self.set_selection((0, 0), (self.rows - 1, self.cols - 1), see=False)

    # ---------------- ライブの運転点 ----------------
    def set_live(self, row_f, col_f):
        self._live = None if row_f is None or col_f is None else (row_f, col_f)
        self._draw_live()

    def _draw_live(self):
        c = self.canvas
        if self._live is None or self._g is None or not self._items:
            c.delete("live")
            return
        row_f, col_f = self._live
        g = self._g
        x = col_f * g["cw"] + g["cw"] / 2
        y = row_f * g["ch"] + g["ch"] / 2
        rad = max(4, int(5 * self.zoom))
        if c.find_withtag("live"):
            c.coords("live", x - rad, y - rad, x + rad, y + rad)
        else:
            c.create_oval(x - rad, y - rad, x + rad, y + rad, fill=LIVE, outline="#ffffff", width=1, tags="live")
        c.tag_raise("live")

    def goto_live(self):
        if self._live is None:
            return False
        r = max(0, min(self.rows - 1, int(round(self._live[0]))))
        col = max(0, min(self.cols - 1, int(round(self._live[1]))))
        self.set_selection((r, col))
        return True

    # ---------------- マウス・キー ----------------
    def _cell_at(self, ex, ey, clamp=False):
        g = self._g
        if g is None or not self._items:
            return None
        x, y = self.canvas.canvasx(ex), self.canvas.canvasy(ey)
        r, col = int(y // g["ch"]), int(x // g["cw"])
        if clamp:
            return max(0, min(self.rows - 1, r)), max(0, min(self.cols - 1, col))
        if 0 <= r < self.rows and 0 <= col < self.cols and x >= 0 and y >= 0:
            return r, col
        return None

    def _hdr_index(self, e, kind):
        g = self._g
        if g is None or not self._items:
            return None
        if kind == "x":
            if not self.xvals or self.cv_xh.canvasy(e.y) < g["lab_h"]:
                return None
            j = int(self.cv_xh.canvasx(e.x) // g["cw"])
            return j if 0 <= j < self.cols else None
        if not self.yvals:
            return None
        i = int(self.cv_yh.canvasy(e.y) // g["ch"])
        return i if 0 <= i < self.rows else None

    def _press(self, e):
        self.commit_edit()
        self.focus_table()
        rc = self._cell_at(e.x, e.y)
        if rc is None:
            return
        if e.state & 0x1:
            self.set_selection(self.anchor, rc)
        else:
            self.set_selection(rc)
        self._drag = True

    def _hdr_press(self, e, kind):
        """列/行の見出しクリック = 列/行ごと選択(Shift で範囲)。"""
        self.commit_edit()
        self.focus_table()
        k = self._hdr_index(e, kind)
        if k is None:
            return
        shift = bool(e.state & 0x1)
        if kind == "x":
            self.set_selection((0, self.anchor[1] if shift else k), (self.rows - 1, k), see=False)
        else:
            self.set_selection((self.anchor[0] if shift else k, 0), (k, self.cols - 1), see=False)

    def _hdr_double(self, e, kind):
        """軸編集 ON のとき、見出しのダブルクリックで軸の値を編集。"""
        if not self.host.axis_edit or self.table is None:
            return
        ax = self.table.x_axis if kind == "x" else self.table.y_axis
        k = self._hdr_index(e, kind)
        if ax is not None and not ax.static_values and k is not None:
            self.begin_edit(kind=kind, idx=k)

    def _motion(self, e):
        if not self._drag:
            return
        rc = self._cell_at(e.x, e.y, clamp=True)
        if rc and rc != self.cursor:
            self.set_selection(self.anchor, rc)

    def _double(self, e):
        rc = self._cell_at(e.x, e.y)
        if rc is not None:
            self.set_selection(rc)
            self.begin_edit()

    def _context(self, e):
        self.focus_table()
        rc = self._cell_at(e.x, e.y)
        if rc is not None and rc not in self.sel_cells():
            self.set_selection(rc)
        self.host.view_context_menu(self, e)

    def _wheel(self, e, delta=None):
        d = delta if delta is not None else e.delta
        if not d:
            return "break"
        if e.state & 0x4:                        # Ctrl+ホイール = 拡大/縮小
            self.set_zoom(self.zoom + (0.1 if d > 0 else -0.1))
            self.host._save_views_soon()
            return "break"
        step = -1 if d > 0 else 1
        if abs(d) >= 120:
            step *= max(1, abs(d) // 120) * 3
        if e.state & 0x1:
            self.canvas.xview_scroll(step, "units")
        else:
            self.canvas.yview_scroll(step, "units")
        return "break"

    _MOVE = {"Up": (-1, 0), "Down": (1, 0), "Left": (0, -1), "Right": (0, 1),
             "KP_Up": (-1, 0), "KP_Down": (1, 0), "KP_Left": (0, -1), "KP_Right": (0, 1)}

    def _key(self, e):
        if self.host.dispatch_key(e, self):
            return "break"
        ks = e.keysym
        st = e.state if isinstance(e.state, int) else 0
        shift, ctrl = bool(st & 0x1), bool(st & 0x4)
        if ks in self._MOVE:
            dr, dc = self._MOVE[ks]
            self.move_cursor(dr, dc, extend=shift, jump=ctrl)
            return "break"
        if ks in ("Home", "KP_Home", "End", "KP_End"):
            end = ks.endswith("End")
            r = (self.rows - 1 if end else 0) if ctrl else self.cursor[0]
            col = self.cols - 1 if end else 0
            if shift:
                self.set_selection(self.anchor, (r, col))
            else:
                self.set_selection((r, col))
            return "break"
        if ks in ("Tab", "ISO_Left_Tab"):
            self.move_cursor(0, -1 if (shift or ks == "ISO_Left_Tab") else 1)
            return "break"
        if ks == "Escape":
            self.set_selection(self.cursor)
            return "break"
        ch = e.char or ""
        if ch and ch in "0123456789." and not ctrl and not (st & self.host.altmask):
            self.begin_edit(initial=ch)
            return "break"
        return None

    # ---------------- 入力 ----------------
    def begin_edit(self, initial=None, kind="cell", idx=None):
        if self.table is None or self._g is None or not self._items:
            return
        self.commit_edit()
        g = self._g
        if kind == "cell":
            cv = self.canvas
            r, col = self.cursor
            self._see((r, col))
            x0, y0, x1, y1 = self._cell_box(r, col)
            text = self._texts.get((r, col), "")
            if text == "—":
                text = ""
        elif kind == "x":
            cv = self.cv_xh
            x0, y0 = idx * g["cw"], g["lab_h"]
            x1, y1 = x0 + g["cw"] - 1, y0 + g["ch"] - 1
            text = self._ax_text((self.xvals or [""])[idx])
        else:
            cv = self.cv_yh
            x0, y0 = 0, idx * g["ch"]
            x1, y1 = g["yhw"] - 1, y0 + g["ch"] - 1
            text = self._ax_text((self.yvals or [""])[idx])
        ent = tk.Entry(cv, font=g["fcell"], justify="center", relief="flat", bd=0,
                       bg="#ffffff", fg="#000000", insertbackground="#000000",
                       highlightthickness=1, highlightcolor=CURSOR, highlightbackground=CURSOR)
        ent.insert(0, text if initial is None else initial)
        if initial is None:
            ent.select_range(0, "end")
        ent.icursor("end")
        cv.create_window(x0, y0, window=ent, anchor="nw", width=x1 - x0 + 1, height=y1 - y0 + 1,
                         tags="editor")
        self._edit = {"entry": ent, "kind": kind, "idx": idx, "done": False, "cv": cv}
        ent.bind("<Return>", lambda _e: (self.commit_edit(), "break")[1])
        ent.bind("<KP_Enter>", lambda _e: (self.commit_edit(), "break")[1])
        ent.bind("<Escape>", lambda _e: (self.cancel_edit(refocus=True), "break")[1])
        ent.bind("<Tab>", lambda _e: (self.commit_edit(move=(0, 1)), "break")[1])
        ent.bind("<Up>", lambda _e: (self.commit_edit(move=(-1, 0)), "break")[1])
        ent.bind("<Down>", lambda _e: (self.commit_edit(move=(1, 0)), "break")[1])
        ed = self._edit
        ent.bind("<FocusOut>", lambda _e: self.after_idle(lambda: self.commit_edit(only=ed)))
        ent.focus_set()

    def cancel_edit(self, refocus=False):
        ed = self._edit
        if not ed:
            return
        ed["done"] = True
        self._edit = None
        try:
            ed.get("cv", self.canvas).delete("editor")
            ed["entry"].destroy()
        except tk.TclError:
            pass
        if refocus:
            try:
                self.canvas.focus_set()
            except tk.TclError:
                pass

    def commit_edit(self, move=None, only=None):
        ed = self._edit
        if not ed or ed["done"] or (only is not None and ed is not only):
            return
        ed["done"] = True
        try:
            s = ed["entry"].get().strip()
        except tk.TclError:
            s = ""
        refocus = False
        try:
            refocus = self.focus_get() is ed["entry"] or only is None
        except (tk.TclError, KeyError):
            pass
        self._edit = None
        try:
            ed.get("cv", self.canvas).delete("editor")
            ed["entry"].destroy()
        except tk.TclError:
            pass
        try:
            val = float(s)
        except ValueError:
            val = None
        if val is not None and self.table is not None:
            if ed["kind"] == "cell":
                cells = self.sel_cells()
                if len(cells) <= 1:
                    cells = [self.cursor]
                cells = [rc for rc in cells if isnum(self.grid_vals[rc[0]][rc[1]]) or rc == self.cursor]
                self.host.edit_cells(self, {rc: val for rc in cells},
                                     "入力" if self.host.lang != "en" else "Typed value")
            else:
                self.host.edit_axis(self, ed["kind"], ed["idx"], val)
        if move:
            self.move_cursor(*move)
        if refocus or move:
            try:
                self.canvas.focus_set()
            except tk.TclError:
                pass

    # ---------------- 一括操作(書き込みは host) ----------------
    def _label(self, ja, en):
        return en if self.host.lang == "en" else ja

    def op_delta(self, sign, big=False):
        cells = self.num_cells()
        if not cells:
            return
        small, large = self.host.steps_for(self.table, self.grid_vals)
        d = (large if big else small) * sign
        self.host.edit_cells(self, {(r, c): float(self.grid_vals[r][c]) + d for r, c in cells},
                             self._label("増減", "Increment"))

    def op_map(self, fn, label):
        cells = self.num_cells()
        if cells:
            self.host.edit_cells(self, {(r, c): fn(float(self.grid_vals[r][c])) for r, c in cells}, label)

    def op_interp(self, kind):
        r0, c0, r1, c1 = self.sel_rect()
        g = self.grid_vals
        out = {}
        if kind == "h":
            xpos = positions(self.xvals, self.cols)
            for r in range(r0, r1 + 1):
                out.update({(r, i): v for i, v in interp_1d(g[r], xpos, c0, c1).items()})
        elif kind == "v":
            ypos = positions(self.yvals, self.rows)
            for col in range(c0, c1 + 1):
                colv = [g[r][col] for r in range(self.rows)]
                out.update({(i, col): v for i, v in interp_1d(colv, ypos, r0, r1).items()})
        else:
            out = interp_2d(g, r0, c0, r1, c1, positions(self.xvals, self.cols), positions(self.yvals, self.rows))
        out = {rc: v for rc, v in out.items() if isnum(g[rc[0]][rc[1]])}
        if not out:
            self.host.status_note(self._label(
                "補間するには、端の値が入った3セル以上(2次元補間は2×2以上)を選んでください。",
                "Select 3+ cells in a line (2x2+ for 2D) with numeric ends to interpolate."))
            return
        self.host.edit_cells(self, out, self._label("補間", "Interpolate"))

    def op_smooth(self):
        out = smooth(self.grid_vals, self.sel_cells())
        if out:
            self.host.edit_cells(self, out, self._label("平滑化", "Smooth"))

    def op_fill(self, down=True):
        r0, c0, r1, c1 = self.sel_rect()
        g = self.grid_vals
        out = {}
        if down:
            for col in range(c0, c1 + 1):
                for r in range(r0 + 1, r1 + 1):
                    if isnum(g[r0][col]) and isnum(g[r][col]):
                        out[(r, col)] = float(g[r0][col])
        else:
            for r in range(r0, r1 + 1):
                for col in range(c0 + 1, c1 + 1):
                    if isnum(g[r][c0]) and isnum(g[r][col]):
                        out[(r, col)] = float(g[r][c0])
        if out:
            self.host.edit_cells(self, out, self._label("コピー(下/右)", "Fill"))

    def copy(self):
        r0, c0, r1, c1 = self.sel_rect()
        lines = []
        for r in range(r0, r1 + 1):
            row = []
            for col in range(c0, c1 + 1):
                v = self.grid_vals[r][col]
                row.append("" if not isnum(v) else (f"{v:.7g}" if isinstance(v, float) else str(v)))
            lines.append("\t".join(row))
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
        except tk.TclError:
            return
        self.host.status_note(self._label(f"{len(lines)}行をコピーしました（表計算ソフトに貼り付けできます）",
                                          f"Copied {len(lines)} rows"))

    def paste(self):
        try:
            data = parse_clip(self.clipboard_get())
        except tk.TclError:
            return
        if not data:
            return
        r0, c0, r1, c1 = self.sel_rect()
        out = {}
        g = self.grid_vals
        if len(data) == 1 and len(data[0]) == 1 and data[0][0] is not None:
            for rc in self.sel_cells():                    # 1つの値 → 選択範囲すべて
                if isnum(g[rc[0]][rc[1]]):
                    out[rc] = data[0][0]
        else:
            for i, row in enumerate(data):
                for j, v in enumerate(row):
                    r, col = r0 + i, c0 + j
                    if v is not None and r < self.rows and col < self.cols and isnum(g[r][col]):
                        out[(r, col)] = v
            if out:
                rr = max(r for r, _ in out)
                cc = max(col for _, col in out)
                self.anchor, self.cursor = (r0, c0), (rr, cc)
        if out:
            self.host.edit_cells(self, out, self._label("貼り付け", "Paste"))
