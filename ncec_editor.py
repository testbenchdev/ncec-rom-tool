"""NCEC ROM マップエディタ (tkinter) — LFG7xx 用。

機能: ROM/定義の読み込み、カテゴリ別テーブル一覧、2D/3Dマップの表示・編集(ヒートマップ)、
チェックサム再計算付き保存。実ECUには触れない(オフライン編集)。

起動: python ncec_editor.py
"""
from __future__ import annotations

import math
import pathlib
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ncec_dashboard
from ncecu import checksum, defs, flash as flashmod, i18n, livelog, ltdef, romdiff
from ncecu.rom import Rom

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ROM = HERE / "ncec_rom_dump.bin"
DEFAULT_DEF = HERE / "defs" / "lfg7eg.xml"              # RomRaider XML(予備)
DEFAULT_LT_MAIN = HERE / "defs" / "libretuner" / "main.json"
DEFAULT_LT_CALID = HERE / "defs" / "libretuner" / "LFG7EG.json"


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


class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NCEC ROM Map Editor")
        self.geometry("1200x780")
        self.configure(bg="#1e2128")
        self.rom: Rom | None = None
        self.rom_path: pathlib.Path | None = None
        self.romdef: defs.RomDef | None = None
        self.cur_table: defs.Table | None = None
        self.modified = False
        self.cells: list[list[tk.Entry]] = []
        # ライブ(実機 OBD)状態
        self.live_reader: livelog.LiveReader | None = None
        self._live_after = None
        self._live_cell: tuple[int, int] | None = None
        self.dash_win = None
        self.lang = "ja"
        i18n.set_language(self.lang)
        self._build()
        self._auto_load()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _pick_font(self, candidates):
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        for c in candidates:
            if c in fams:
                return c
        return candidates[-1]

    def _build(self):
        # 日本語対応フォント(UI用)と数値グリッド用の等幅フォント
        self.jp = self._pick_font(["Meiryo UI", "Yu Gothic UI", "MS UI Gothic", "TkDefaultFont"])
        self.mono = self._pick_font(["Consolas", "MS Gothic", "Courier New"])
        # アプリ全体の既定フォント(ボタン/メニュー等)を日本語フォントに
        self.option_add("*Font", (self.jp, 10))

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background="#262a33", fieldbackground="#262a33",
                        foreground="#dfe3ea", rowheight=22, font=(self.jp, 10))
        style.map("Treeview", background=[("selected", "#3a6ea5")])

        bar = tk.Frame(self, bg="#1e2128")
        bar.pack(fill="x", padx=6, pady=4)
        self.btns = {}
        self.btns["open"] = tk.Button(bar, text=i18n.ui("open"), command=self.open_rom)
        self.btns["open"].pack(side="left", padx=2)
        self.btns["save"] = tk.Button(bar, text=i18n.ui("save"), command=self.save_rom)
        self.btns["save"].pack(side="left", padx=2)
        self.btns["saveas"] = tk.Button(bar, text=i18n.ui("saveas"), command=self.save_rom_as)
        self.btns["saveas"].pack(side="left", padx=2)
        self.btns["help"] = tk.Button(bar, text=i18n.ui("help"), command=self.show_help)
        self.btns["help"].pack(side="left", padx=2)
        self.live_btn = tk.Button(bar, text=i18n.ui("live_on"), command=self.toggle_live)
        self.live_btn.pack(side="left", padx=(12, 2))
        self.btns["dashboard"] = tk.Button(bar, text=i18n.ui("dashboard"), command=self.open_dashboard)
        self.btns["dashboard"].pack(side="left", padx=2)
        self.btns["dump"] = tk.Button(bar, text=i18n.ui("dump"), command=self.dump_ecu)
        self.btns["dump"].pack(side="left", padx=2)
        self.btns["cmp_ecu"] = tk.Button(bar, text=i18n.ui("cmp_ecu"), command=self.compare_ecu)
        self.btns["cmp_ecu"].pack(side="left", padx=2)
        self.btns["cmp_rom"] = tk.Button(bar, text=i18n.ui("cmp_rom"), command=self.compare_files)
        self.btns["cmp_rom"].pack(side="left", padx=2)
        self.lang_btn = tk.Button(bar, text=i18n.ui("lang"), command=self.toggle_lang)
        self.lang_btn.pack(side="left", padx=(12, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._populate_tree())
        tk.Entry(bar, textvariable=self.search_var, width=28).pack(side="right", padx=4)
        self.search_lbl = tk.Label(bar, text=i18n.ui("search"), bg="#1e2128", fg="#dfe3ea")
        self.search_lbl.pack(side="right")

        main = tk.PanedWindow(self, orient="horizontal", bg="#1e2128",
                              sashwidth=5, bd=0)
        main.pack(fill="both", expand=True, padx=6, pady=4)

        left = tk.Frame(main, bg="#1e2128")
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        main.add(left, width=360)

        right = tk.Frame(main, bg="#1e2128")
        self.info = tk.Label(right, text="", bg="#1e2128", fg="#9fb0c8",
                             anchor="w", justify="left", font=(self.jp, 10))
        self.info.pack(fill="x", padx=4, pady=(2, 0))
        self.live_lbl = tk.Label(right, text="", bg="#1e2128", fg="#7fe0a0",
                                 anchor="w", justify="left", font=(self.mono, 10))
        self.live_lbl.pack(fill="x", padx=4, pady=(0, 0))
        self.desc = tk.Label(right, text="マップを選ぶと、ここに説明が表示されます。",
                             bg="#232733", fg="#b9c6da", anchor="w", justify="left",
                             font=(self.jp, 10), wraplength=820, padx=8, pady=6)
        self.desc.pack(fill="x", padx=4, pady=(2, 4))
        gridwrap = tk.Frame(right, bg="#1e2128")
        gridwrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(gridwrap, bg="#1e2128", highlightthickness=0)
        self.gf = tk.Frame(self.canvas, bg="#1e2128")
        vsb = ttk.Scrollbar(gridwrap, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(gridwrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0, 0), window=self.gf, anchor="nw")
        self.gf.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        main.add(right)

        self.status = tk.Label(self, text="準備完了", bg="#11131a", fg="#9fb0c8",
                               anchor="w", font=(self.jp, 9))
        self.status.pack(fill="x", side="bottom")

    # ---------- help ----------
    def show_help(self):
        help_path = HERE / "docs" / "editor_help_ja.md"
        try:
            text = help_path.read_text(encoding="utf-8")
        except OSError:
            text = ("NCEC ROM マップエディタ\n\n"
                    "左のツリーでテーブルを選び、右のマップのセルをクリックして数値を入力し "
                    "Enter で確定します。[保存] でチェックサムを自動再計算して書き出します。\n"
                    "(詳細ヘルプ docs/editor_help_ja.md が見つかりませんでした)")
        win = tk.Toplevel(self)
        win.title("ヘルプ — NCEC ROM マップエディタ")
        win.geometry("760x600")
        win.configure(bg="#1e2128")
        frm = tk.Frame(win, bg="#1e2128")
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        txt = tk.Text(frm, wrap="word", bg="#262a33", fg="#dfe3ea",
                      font=(self.jp, 11), relief="flat", padx=10, pady=10,
                      insertbackground="#dfe3ea")
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        # 見出し(■ 行)を強調
        txt.tag_configure("h", foreground="#7fc4ff", font=(self.jp, 12, "bold"))
        txt.tag_configure("t", foreground="#cfe0f5", font=(self.jp, 14, "bold"))
        for line in text.splitlines():
            if line.startswith("■"):
                txt.insert("end", line + "\n", "h")
            elif line and set(line) <= set("=＝"):
                txt.insert("end", line + "\n")
            elif line and not line.startswith(" ") and line.strip() and "NCEC ROM" in line:
                txt.insert("end", line + "\n", "t")
            else:
                txt.insert("end", line + "\n")
        txt.configure(state="disabled")
        tk.Button(win, text="閉じる", command=win.destroy).pack(pady=6)
        win.transient(self)

    # ---------- load ----------
    def _auto_load(self):
        if not DEFAULT_ROM.exists():
            return
        if DEFAULT_LT_MAIN.exists() and DEFAULT_LT_CALID.exists():
            self._load_lt(DEFAULT_ROM, DEFAULT_LT_MAIN, DEFAULT_LT_CALID)
        elif DEFAULT_DEF.exists():
            self._load(DEFAULT_ROM, DEFAULT_DEF)

    def _finish_load(self, rom_path):
        data = pathlib.Path(rom_path).read_bytes()
        self.rom = Rom(data, self.romdef)
        self.rom_path = pathlib.Path(rom_path)
        self.modified = False
        self._populate_tree()
        self._update_status()

    def _load(self, rom_path, def_path):
        self.romdef = defs.parse(def_path)
        self._finish_load(rom_path)

    def _load_lt(self, rom_path, main_path, calid_path):
        self.romdef = ltdef.parse(main_path, calid_path)
        self._finish_load(rom_path)

    def open_rom(self):
        p = filedialog.askopenfilename(title="ROM (.bin)",
                                       filetypes=[("BIN", "*.bin"), ("All", "*.*")])
        if not p:
            return
        # LibreTuner 定義があれば最優先(この個体 ROM への適合が最も良い)
        if DEFAULT_LT_MAIN.exists() and DEFAULT_LT_CALID.exists():
            self._load_lt(p, DEFAULT_LT_MAIN, DEFAULT_LT_CALID)
            return
        dp = DEFAULT_DEF
        if not dp.exists():
            dp = filedialog.askopenfilename(title="定義XML",
                                            filetypes=[("XML", "*.xml")])
            if not dp:
                return
        self._load(p, dp)

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.romdef:
            return
        q = self.search_var.get().lower().strip()
        cats: dict[str, str] = {}
        for i, t in enumerate(self.romdef.tables):
            cat_ja = i18n.translate_category(t.category)
            name_disp = i18n.translate_table_name(t.name)
            if q and q not in t.name.lower() and q not in t.category.lower() \
                    and q not in cat_ja.lower() and q not in name_disp.lower():
                continue
            if t.category not in cats:
                cats[t.category] = self.tree.insert("", "end", text=cat_ja, open=bool(q))
            self.tree.insert(cats[t.category], "end", text=f"{name_disp}  [{t.ttype}]",
                             values=(i,), tags=("tbl",))

    # ---------- table view ----------
    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        self.cur_table = self.romdef.tables[int(vals[0])]
        self._render_table()

    def _render_table(self):
        for w in self.gf.winfo_children():
            w.destroy()
        self.cells = []
        self._live_cell = None   # セル再構築で旧ハイライト参照を破棄
        t = self.cur_table
        if not t or not self.rom:
            return
        sc = self.romdef.scalings.get(t.scaling)
        grid = self.rom.read_table(t)
        rows, cols = self.rom.dims(t)
        xa, ya = t.x_axis, t.y_axis
        xvals = self.rom.read_axis(xa) if xa else None
        yvals = self.rom.read_axis(ya) if ya else None
        # 補正次元に合わせて軸のゴミ尾をトリム
        if xvals:
            xvals = xvals[:cols]
        if yvals:
            yvals = yvals[:rows]
        units = i18n.unit_of(t.category, t.name)
        self._cur_unit = units
        self.info.config(text=f"{t.name}   @0x{t.address:X}   {rows}x{cols}   "
                              f"{i18n.ui('unit')}:{units or '-'}   型:{sc.storagetype if sc else '?'}")

        pt = "点" if self.lang == "ja" else "pt"
        cat_ja = i18n.translate_category(t.category)
        cat_desc = i18n.describe_category(t.category)
        parts = [f"【{cat_ja}】 {cat_desc}" if cat_desc else f"【{cat_ja}】"]
        shape = []
        if t.ttype == "3D" and xa and ya:
            shape.append(f"{i18n.ui('map3d')}: {i18n.ui('axis_x')}={i18n.axis_label(xa.name)} "
                         f"{xa.elements}{pt} / {i18n.ui('axis_y')}={i18n.axis_label(ya.name)} "
                         f"{ya.elements}{pt}")
        elif t.ttype == "2D":
            ax = ya or xa
            n = (ax.elements if ax else cols * rows)
            albl = i18n.axis_label(ax.name) if ax else ""
            shape.append(f"{i18n.ui('map2d')}: {albl} {n}{pt}")
        else:
            shape.append(i18n.ui("val1d"))
        vr = ""
        if sc and (sc.vmin or sc.vmax) and sc.vmin != sc.vmax:
            vr = f" / {i18n.ui('range')} {sc.fmt % sc.vmin}〜{sc.fmt % sc.vmax}"
        shape.append(f"{i18n.ui('unit')}={units or '-'}{vr}")
        parts.append("　".join(shape))
        if t.desc:
            parts.append(f"{t.desc}")
        parts.append(f"● {i18n.ui('effect')}: {i18n.effect_of(t.category)}")

        is_lt = getattr(self.romdef, "source", "") == "libretuner"
        # ECUディスクリプタ由来の補正が当たっているか
        try:
            from ncecu.corrections import corrected_dims
            is_corrected = corrected_dims(t.address) is not None
        except Exception:
            is_corrected = False

        _flat0 = [v for row in grid for v in row
                  if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))]
        frac_out = 0.0
        if sc and sc.vmax > sc.vmin and _flat0:
            span = sc.vmax - sc.vmin
            tol = span * 0.05 + 1e-6
            frac_out = sum(1 for v in _flat0 if v < sc.vmin - tol or v > sc.vmax + tol) / len(_flat0)

        if is_lt:
            # LibreTuner 定義はこの個体 CALID で次元・アドレスを検証済み。信頼して編集可。
            parts.append(i18n.ui("trusted"))
            if frac_out > 0.2:
                parts.append("※ 一部の値が『目安範囲』外ですが、これは定義の目安(min/max)が"
                             "狭めに設定されているためで、配置ずれではありません(閉ループ目標・補正項など)。")
        else:
            warn = False
            if is_corrected:
                parts.append("✓ このマップはECU内部の記述子から真の次元を復元し、値が妥当範囲に収まることを"
                             "検証済みです(自動補正)。")
            if t.ttype in ("2D", "3D") and t.elements and rows * cols != t.elements:
                warn = True
            if frac_out > 0.2:
                warn = True
            if warn and not is_corrected:
                parts.append("⚠ このマップは定義(lfg7eg.xml)がこの個体ROMに完全一致しておらず、"
                             "表示が桁ずれ・隣接データ混入している可能性が高いです(目安範囲外の値はその症状)。"
                             "数値の信頼性が低いため、編集は避けてください。詳細は docs/table_audit_ja.md。")
        self.desc.config(text="\n".join(parts))
        def _isnan(v):
            return isinstance(v, float) and math.isnan(v)

        flat = [v for row in grid for v in row if isinstance(v, (int, float)) and not _isnan(v)]
        lo, hi = (min(flat), max(flat)) if flat else (0, 1)
        self._lohi = (lo, hi)
        self._sc_cur = sc

        def fmt(v):
            if _isnan(v):
                return "—"
            return (sc.fmt % v) if (sc and isinstance(v, float)) else str(v)

        c0 = 1 if yvals else 0
        x_label = i18n.axis_label(xa.name) if xa else ""
        y_label = i18n.axis_label(ya.name) if ya else ""
        show_labels = bool((xvals and x_label) or (yvals and y_label))
        base = 1 if show_labels else 0        # 軸ラベル行(row 0)
        xhdr_row = base                        # X値見出し行
        r0 = base + (1 if xvals else 0)        # セル(とY値見出し)の開始行

        # 軸ラベル行
        if show_labels:
            if yvals and y_label:
                tk.Label(self.gf, text=f"↓ {y_label}", bg="#3a4a63", fg="#eaf2ff",
                         font=(self.jp, 9, "bold"), borderwidth=1, relief="flat",
                         anchor="center").grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
            if xvals and x_label:
                span = max(1, cols)
                tk.Label(self.gf, text=f"{x_label} →", bg="#3a4a63", fg="#eaf2ff",
                         font=(self.jp, 9, "bold"), borderwidth=1, relief="flat",
                         anchor="center").grid(row=0, column=c0, columnspan=span,
                                               sticky="nsew", padx=1, pady=1)
        # X値見出し(ブレークポイント)
        if xvals:
            if yvals:
                tk.Label(self.gf, text="", bg="#1e2128").grid(row=xhdr_row, column=0)
            for j, xv in enumerate(xvals):
                tk.Label(self.gf, text=fmt(xv) if isinstance(xv, float) else str(xv),
                         bg="#2b3340", fg="#cfe0f5", font=(self.mono, 9, "bold"),
                         width=8, borderwidth=1, relief="flat").grid(row=xhdr_row, column=c0 + j, sticky="nsew", padx=1, pady=1)
        for i in range(rows):
            if yvals:
                yv = yvals[i] if i < len(yvals) else ""
                tk.Label(self.gf, text=fmt(yv) if isinstance(yv, float) else str(yv),
                         bg="#2b3340", fg="#cfe0f5", font=(self.mono, 9, "bold"),
                         width=8, borderwidth=1, relief="flat").grid(row=r0 + i, column=0, sticky="nsew", padx=1, pady=1)
            rowcells = []
            for j in range(cols):
                v = grid[i][j]
                e = tk.Entry(self.gf, width=8, justify="center", font=(self.mono, 9),
                             relief="flat", bd=1, disabledforeground="#0b0d12")
                e.insert(0, fmt(v))
                if _isnan(v):
                    e.config(bg="#3a3f4b", fg="#8a94a6")  # 未使用(0xFF)セル
                elif isinstance(v, (int, float)):
                    e.config(bg=heat_color(v, lo, hi), fg="#0b0d12")
                e.grid(row=r0 + i, column=c0 + j, sticky="nsew", padx=1, pady=1)
                e.bind("<Return>", lambda ev, ii=i, jj=j: self._commit_cell(ii, jj))
                e.bind("<FocusOut>", lambda ev, ii=i, jj=j: self._commit_cell(ii, jj))
                rowcells.append(e)
            self.cells.append(rowcells)
        # 調整値の単位をグリッド右下に表示
        if units:
            tk.Label(self.gf, text=f"[{units}]", bg="#1e2128", fg="#9fb0c8",
                     font=(self.jp, 10, "bold")).grid(
                row=r0 + rows, column=max(c0, c0 + cols - 1), sticky="e", padx=3, pady=(3, 0))

    def _commit_cell(self, i, j):
        if not self.cur_table:
            return
        e = self.cells[i][j]
        try:
            val = float(e.get())
        except ValueError:
            return
        sc = self.romdef.scalings.get(self.cur_table.scaling)
        old = self.rom.read_table(self.cur_table)[i][j]
        if sc and isinstance(old, float) and abs(old - val) < 1e-9:
            return
        self.rom.write_cell(self.cur_table, i, j, val)
        self.modified = True
        # 該当セルのみ更新（全再描画は重いので避ける）: 保存値を読み直して表示・色を更新
        actual = self.rom.read_table(self.cur_table)[i][j]
        lo, hi = getattr(self, "_lohi", (0, 1))
        e.delete(0, "end")
        e.insert(0, (sc.fmt % actual) if (sc and isinstance(actual, float)) else str(actual))
        if isinstance(actual, (int, float)):
            e.config(bg=heat_color(actual, lo, hi), fg="#0b0d12")
        self._update_status()

    # ---------- save ----------
    def save_rom(self):
        if not self.rom_path:
            return self.save_rom_as()
        self._do_save(self.rom_path)

    def save_rom_as(self):
        if not self.rom:
            return
        p = filedialog.asksaveasfilename(defaultextension=".bin",
                                         filetypes=[("BIN", "*.bin")])
        if p:
            self._do_save(pathlib.Path(p))

    def _do_save(self, path):
        data = bytearray(self.rom.bytes_out())
        changed = checksum.recalculate(data)
        nch = sum(1 for s, e, o, n in changed if o != n)
        path.write_bytes(bytes(data))
        self.rom = Rom(bytes(data), self.romdef)
        self.rom_path = path
        self.modified = False
        self._update_status()
        messagebox.showinfo("保存完了",
                            f"保存しました:\n{path}\n\nチェックサム再計算: {nch} 領域更新")

    def _update_status(self):
        if not self.rom:
            self.status.config(text="ROM未読み込み")
            return
        ok = checksum.all_valid(self.rom.data)
        md = "  [未保存の変更あり]" if self.modified else ""
        self.status.config(
            text=f"{self.rom_path.name if self.rom_path else '?'}  |  "
                 f"{self.romdef.xmlid}  |  チェックサム: {'OK' if ok else '要再計算(保存時に自動)'}{md}")

    # ---------- ライブ(実機 OBD, 読み取り専用) ----------
    def toggle_live(self):
        if self.live_reader is None:
            try:
                lr = livelog.LiveReader(interval=0.1)
                lr.start()
            except Exception as e:  # noqa: BLE001
                messagebox.showerror(
                    "Live 接続失敗",
                    f"CANに接続できませんでした:\n{e}\n\n"
                    "ECUの電源・CANアダプタ(gs_usb)・通常セッションを確認してください。")
                return
            self.live_reader = lr
            self.live_btn.config(text=i18n.ui("live_off"), bg="#3a6ea5", fg="#ffffff")
            self._live_after = self.after(200, self._live_tick)
        else:
            self._stop_live()

    def _stop_live(self):
        if self._live_after is not None:
            try:
                self.after_cancel(self._live_after)
            except Exception:  # noqa: BLE001
                pass
            self._live_after = None
        if self.live_reader is not None:
            self.live_reader.stop()
            self.live_reader = None
        self._clear_live_highlight()
        self.live_lbl.config(text="")
        try:
            self.live_btn.config(text=i18n.ui("live_on"), bg="SystemButtonFace", fg="#000000")
        except tk.TclError:
            self.live_btn.config(text=i18n.ui("live_on"))

    def _live_tick(self):
        lr = self.live_reader
        if lr is None:
            return
        bp = lr.latest_by_pid()
        if not bp:
            self.live_lbl.config(text="Live: 待機中(応答なし — 電源/通常セッションを確認)",
                                 fg="#d08770")
        else:
            def fmt(pids):
                out = []
                for pid in pids:
                    if pid in bp:
                        s = livelog.PIDS[pid]
                        out.append(f"{s.name}:{bp[pid]:.0f}{s.unit}")
                return "  ".join(out)
            line1 = "● " + fmt(livelog.DEFAULT_PIDS)
            line2 = "  " + fmt(livelog.EXTRA_PIDS)
            dtcs = lr.latest_dtcs()
            if dtcs:
                codes = " ".join(c for c, _ in dtcs[:10])
                more = f" +{len(dtcs) - 10}" if len(dtcs) > 10 else ""
                line3 = f"DTC({len(dtcs)}): {codes}{more}"
            else:
                line3 = "DTC: なし"
            self.live_lbl.config(text="\n".join([line1, line2, line3]), fg="#7fe0a0")
            self._update_live_cell(lr.latest())
            if self.dash_win is not None:
                try:
                    if self.dash_win.winfo_exists():
                        self.dash_win.update_values(bp, dtcs)
                    else:
                        self.dash_win = None
                except tk.TclError:
                    self.dash_win = None
        self._live_after = self.after(150, self._live_tick)

    def _update_live_cell(self, roles: dict):
        """現在の運転点に対応するセルをハイライト(開いているマップのみ)。"""
        t = self.cur_table
        if not t or not self.rom or not self.cells:
            return
        rows, cols = self.rom.dims(t)
        xa, ya = t.x_axis, t.y_axis
        col = self._axis_pos(xa, roles, cols)
        row = self._axis_pos(ya, roles, rows)
        # 片軸しか対応しない場合、残りの次元が1ならそこを0に
        if col is None and cols == 1:
            col = 0
        if row is None and rows == 1:
            row = 0
        if row is None or col is None:
            self._clear_live_highlight()
            return
        row = max(0, min(rows - 1, row))
        col = max(0, min(cols - 1, col))
        self._apply_live_highlight(row, col)

    def _axis_pos(self, axis, roles: dict, n: int):
        """軸のライブ・ロールと現在値から、丸めたセル位置を返す。対応が無ければ None。"""
        if axis is None:
            return None
        role = livelog.axis_role(axis.name)
        if role is None or role not in roles:
            return None
        try:
            vals = self.rom.read_axis(axis)[:n]
        except Exception:  # noqa: BLE001
            return None
        idx = livelog.interp_index(vals, roles[role])
        if idx is None:
            return None
        return int(round(idx))

    def _clear_live_highlight(self):
        if self._live_cell is not None:
            r, c = self._live_cell
            if r < len(self.cells) and c < len(self.cells[r]):
                try:
                    self.cells[r][c].config(highlightthickness=0)
                except tk.TclError:
                    pass
            self._live_cell = None

    def _apply_live_highlight(self, r, c):
        if self._live_cell == (r, c):
            return
        self._clear_live_highlight()
        if r < len(self.cells) and c < len(self.cells[r]):
            try:
                self.cells[r][c].config(highlightthickness=3,
                                        highlightbackground="#ff3b30",
                                        highlightcolor="#ff3b30")
                self._live_cell = (r, c)
            except tk.TclError:
                pass

    def toggle_lang(self):
        self.lang = "en" if self.lang == "ja" else "ja"
        i18n.set_language(self.lang)
        # ボタン等の文言を更新
        for key, b in self.btns.items():
            b.config(text=i18n.ui(key))
        self.lang_btn.config(text=i18n.ui("lang"))
        self.search_lbl.config(text=i18n.ui("search"))
        self.live_btn.config(text=i18n.ui("live_off") if self.live_reader else i18n.ui("live_on"))
        # ツリーと現在マップを再描画
        self._populate_tree()
        if self.cur_table:
            self._render_table()
        self._update_status()

    def open_dashboard(self):
        if self.dash_win is not None:
            try:
                if self.dash_win.winfo_exists():
                    self.dash_win.lift()
                    return
            except tk.TclError:
                pass
        self.dash_win = ncec_dashboard.DashboardWindow(self, jp=self.jp, mono=self.mono)
        if self.live_reader is None:
            messagebox.showinfo(
                "ダッシュボード",
                "ダッシュボードを開きました。数値を表示するには「Live ▶」で実機に接続してください。")

    def _on_close(self):
        self._stop_live()
        if self.dash_win is not None:
            try:
                self.dash_win.destroy()
            except tk.TclError:
                pass
        self.destroy()

    # ---------- ECU 吸い出し / 照合 ----------
    def _ecu_read_rom_async(self, on_done, title="ECU 吸い出し"):
        """ECUから全ROMをバックグラウンドで読み出し、完了時に on_done(bytes) を呼ぶ。"""
        if self.live_reader is not None:
            self._stop_live()   # gs_usb は1ハンドル=排他
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg="#1e2128")
        win.geometry("460x130")
        win.transient(self)
        lbl = tk.Label(win, text="認証して読み出しています...", bg="#1e2128",
                       fg="#dfe3ea", font=(self.jp, 10))
        lbl.pack(padx=12, pady=(14, 6), anchor="w")
        pb = ttk.Progressbar(win, maximum=flashmod.ROM_SIZE, length=420)
        pb.pack(padx=12, pady=4)
        state = {"rom": None, "err": None, "done": False, "prog": 0,
                 "cancel": threading.Event()}
        tk.Button(win, text="中止", command=lambda: state["cancel"].set()).pack(pady=4)

        def worker():
            from ncecu.canbus import open_bus
            from ncecu.diag import DiagClient
            from ncecu.isotp import IsoTp
            bus = None
            try:
                bus = open_bus()
                diag = DiagClient(IsoTp(bus))
                diag.tp.timeout = 10.0
                f = flashmod.Flasher(diag, log=lambda s: None)

                def prog(off, total):
                    state["prog"] = off
                    if state["cancel"].is_set():
                        raise flashmod.FlashError("ユーザー中止")
                state["rom"] = f.read_full_rom(progress=prog)
            except Exception as e:  # noqa: BLE001
                state["err"] = str(e)
            finally:
                if bus is not None:
                    try:
                        bus.shutdown()
                    except Exception:  # noqa: BLE001
                        pass
                state["done"] = True

        threading.Thread(target=worker, daemon=True).start()

        def poll():
            pb["value"] = state["prog"]
            lbl.config(text=f"読み出し中: {state['prog']:,}/{flashmod.ROM_SIZE:,} バイト")
            if state["done"]:
                try:
                    win.destroy()
                except tk.TclError:
                    pass
                if state["err"]:
                    messagebox.showerror(title, f"読み出し失敗:\n{state['err']}")
                elif state["rom"] is not None:
                    on_done(state["rom"])
            else:
                self.after(150, poll)
        poll()

    def dump_ecu(self):
        if not messagebox.askyesno(
                "ECU 吸い出し",
                "接続中のECUから全ROM(1MB)を読み出します。\n"
                "・プログラミングセッション+セキュリティ解除を行います(読み取り専用)。\n"
                "・消去/書き込みは一切行いません。\n\n実行しますか?"):
            return

        def done(rom):
            p = filedialog.asksaveasfilename(
                title="吸い出したROMを保存", defaultextension=".bin",
                filetypes=[("BIN", "*.bin")],
                initialfile="ecu_readout.bin")
            if p:
                pathlib.Path(p).write_bytes(rom)
                gen = self._safe(lambda: flashmod.detect_generation(rom), "?")
                cal = self._safe(lambda: flashmod.get_cal_id(rom), "?")
                crc = self._safe(lambda: f"{flashmod.calibration_crc(rom):08X}", "?")
                if messagebox.askyesno(
                        "保存完了",
                        f"保存しました:\n{p}\n\nCALID={cal} 世代={gen} calCRC={crc}\n\n"
                        "このROMをエディタで開きますか?"):
                    self._load_bytes(rom, pathlib.Path(p))
        self._ecu_read_rom_async(done, "ECU 吸い出し")

    def compare_ecu(self):
        if not self.rom:
            messagebox.showinfo("ECUと照合", "先に比較の基準となるROMを開いてください。")
            return
        if not messagebox.askyesno(
                "ECUと照合",
                "接続中のECUを読み出し、現在開いているROMと照合します。\n"
                "(読み取り専用。消去/書き込みはしません)\n\n実行しますか?"):
            return
        base = self.rom.bytes_out()
        base_name = self.rom_path.name if self.rom_path else "開いているROM"
        self._ecu_read_rom_async(
            lambda rom: self._show_diff(base, rom, base_name, "ECU実機"),
            "ECUと照合(読み出し中)")

    def compare_files(self):
        pa = filedialog.askopenfilename(title="ROM A (基準)",
                                        filetypes=[("BIN", "*.bin"), ("All", "*.*")])
        if not pa:
            return
        pb_ = filedialog.askopenfilename(title="ROM B (比較対象)",
                                         filetypes=[("BIN", "*.bin"), ("All", "*.*")])
        if not pb_:
            return
        a = pathlib.Path(pa).read_bytes()
        b = pathlib.Path(pb_).read_bytes()
        self._show_diff(a, b, pathlib.Path(pa).name, pathlib.Path(pb_).name)

    def _safe(self, fn, default):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            return default

    def _load_bytes(self, data: bytes, path):
        """読み出した/選んだ bytes をエディタに読み込む(定義は現行を使用)。"""
        if not self.romdef:
            if flashmod and DEFAULT_LT_MAIN.exists() and DEFAULT_LT_CALID.exists():
                self.romdef = ltdef.parse(DEFAULT_LT_MAIN, DEFAULT_LT_CALID)
        self.rom = Rom(data, self.romdef)
        self.rom_path = pathlib.Path(path) if path else None
        self.modified = False
        self._populate_tree()
        self._update_status()

    def _show_diff(self, a: bytes, b: bytes, name_a: str, name_b: str):
        res = romdiff.compare(a, b, self.romdef)
        win = tk.Toplevel(self)
        win.title(f"照合: {name_a}  ⇔  {name_b}")
        win.geometry("820x600")
        win.configure(bg="#1e2128")
        head = tk.Label(win, bg="#1e2128", fg="#dfe3ea", anchor="w", justify="left",
                        font=(self.jp, 10), padx=10, pady=8)
        flags = []
        if res.counter_changed:
            flags.append("フラッシュカウンタ(書込毎に変化・正常)")
        if res.checksum_changed:
            flags.append("チェックサム表")
        head.config(text=(
            f"A: {name_a}   B: {name_b}\n"
            f"差分バイト数: {res.byte_total:,}   変化領域: {len(res.regions)}   "
            f"変化テーブル: {len(res.tables)}\n"
            + ("完全一致(同一内容)" if res.identical
               else ("特殊領域の変化: " + (", ".join(flags) if flags else "なし")))))
        head.pack(fill="x")
        frm = tk.Frame(win, bg="#1e2128")
        frm.pack(fill="both", expand=True, padx=8, pady=4)
        txt = tk.Text(frm, wrap="none", bg="#262a33", fg="#dfe3ea",
                      font=(self.mono, 10), relief="flat")
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        if res.identical:
            txt.insert("end", "2つのROMは完全に同一です。\n")
        elif not res.tables:
            txt.insert("end", "既知テーブル内に差分はありません"
                              "(差分はテーブル外の領域・チェックサム等)。\n")
        else:
            txt.insert("end", f"変化したテーブル {len(res.tables)} 件:\n\n")
            for tc in res.tables:
                cat = i18n.translate_category(tc.category)
                txt.insert("end", f"■ [{cat}] {tc.name}  @0x{tc.address:X}  "
                                  f"変化セル {tc.ncells}\n")
                for (r, c, va, vb) in tc.samples:
                    def _f(v):
                        return "—" if (isinstance(v, float) and math.isnan(v)) \
                            else (f"{v:.3f}" if isinstance(v, float) else str(v))
                    txt.insert("end", f"    ({r},{c})  {_f(va)}  →  {_f(vb)}\n")
                if tc.ncells > len(tc.samples):
                    txt.insert("end", f"    … 他 {tc.ncells - len(tc.samples)} セル\n")
                txt.insert("end", "\n")
        txt.configure(state="disabled")
        tk.Button(win, text="閉じる", command=win.destroy).pack(pady=6)
        win.transient(self)


if __name__ == "__main__":
    Editor().mainloop()
