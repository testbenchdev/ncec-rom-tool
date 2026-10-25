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

import ncec_chart
import ncec_dashboard
from ncecu import (antilag, checksum, dbw_throttle, defs, flash as flashmod, flatshift,
                   i18n, livelog, ltdef, romdiff)
from ncecu.rom import Rom

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ROM = HERE / "ncec_rom_dump.bin"
DEFAULT_DEF = HERE / "defs" / "lfg7eg.xml"              # RomRaider XML(予備)
DEFAULT_LT_MAIN = HERE / "defs" / "libretuner" / "main.json"
DEFAULT_LT_CALID = HERE / "defs" / "libretuner" / "LFG7EG.json"
LIVE_INTERVALS_PATH = HERE / "live_intervals.json"   # ライブPID間引きのユーザ設定(既定からの差分)
RAM_READS_PATH = HERE / "ram_reads.json"             # ライブRAM読み出し(Mode23)チャンネル設定


def _read_version() -> str:
    """同梱の VERSION ファイルからバージョン文字列を読む(無ければ 'dev')。"""
    try:
        return (HERE / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


__version__ = _read_version()


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
        self.title(f"NCEC ROM Map Editor  v{__version__}")
        self.geometry("1360x780")
        self.configure(bg="#1e2128")
        self.rom: Rom | None = None
        self.rom_path: pathlib.Path | None = None
        self.romdef: defs.RomDef | None = None
        self.cur_table: defs.Table | None = None
        self.modified = False
        self.cells: list[list[tk.Entry]] = []
        self._dot = None            # ライブ運転点(●)オーバーレイ
        self._log_fp = None         # ライブ記録ファイル
        self._log_t0 = None
        self._log_path = None
        self._replay = None         # リプレイ状態
        self.axis_edit = False          # 軸ブレークポイント編集モード(既定OFF・誤操作防止)
        self.xcells: list[tk.Entry] = []
        self.ycells: list[tk.Entry] = []
        # ライブ(実機 OBD)状態
        self.live_reader: livelog.LiveReader | None = None
        self._live_after = None
        self._live_cell: tuple[int, int] | None = None
        self.dash_win = None
        self.lang = "ja"
        i18n.set_language(self.lang)
        self.live_pid_overrides = self._load_live_intervals()  # pid->秒(既定と異なるもの)
        self.ram_reads = self._load_ram_reads()                # ライブRAM読み出しチャンネル
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

        # メニューバー(設定)
        self.menubar = tk.Menu(self)
        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.settings_menu.add_command(label=i18n.ui("menu_live_intervals"),
                                       command=self.open_live_intervals)
        self.settings_menu.add_command(label="ログ分析チャート…", command=self.open_chart)
        self.menubar.add_cascade(label=i18n.ui("menu_settings"), menu=self.settings_menu)
        self._settings_idx = self.menubar.index("end")
        try:
            self.config(menu=self.menubar)
        except tk.TclError:
            pass

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
        self.record_btn = tk.Button(bar, text="記録 ●", command=self.toggle_record)
        self.record_btn.pack(side="left", padx=2)
        self.replay_btn = tk.Button(bar, text="リプレイ", command=self.open_replay)
        self.replay_btn.pack(side="left", padx=2)
        self.flash_btn = tk.Button(bar, text="ECU書き込み", command=self.flash_ecu, fg="#a00000")
        self.flash_btn.pack(side="left", padx=2)
        self.btns["fs_patch"] = tk.Button(bar, text=i18n.ui("fs_patch"), command=self.apply_flatshift)
        self.btns["fs_patch"].pack(side="left", padx=2)
        self.btns["al_patch"] = tk.Button(bar, text=i18n.ui("al_patch"), command=self.apply_antilag)
        self.btns["al_patch"].pack(side="left", padx=2)
        self.btns["th_patch"] = tk.Button(bar, text=i18n.ui("th_patch"), command=self.apply_throttle)
        self.btns["th_patch"].pack(side="left", padx=2)
        self.axis_btn = tk.Button(bar, text=i18n.ui("axis_edit_off"), command=self.toggle_axis_edit)
        self.axis_btn.pack(side="left", padx=(12, 2))
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
        if len(data) != flashmod.ROM_SIZE:
            messagebox.showerror(
                "ROM読み込み",
                f"ROMサイズが不正です: {len(data):,} バイト\n"
                f"このECUのROMは {flashmod.ROM_SIZE:,} バイト(1MB)である必要があります。\n"
                "別のファイルを選ぶか、[ECU吸出し]でダンプを作成してください。")
            return
        self._set_rom(data)
        self.rom_path = pathlib.Path(rom_path)
        self.modified = False
        self._populate_tree()
        self._update_status()

    def _set_rom(self, data: bytes):
        """ROM を設定する。定義(LibreTuner)に無い追加項目(フラットシフト関連)を
        この ROM に合わせて差し替える(パッチ定数はパッチ適用済み ROM のときだけ出す)。"""
        if self.romdef and getattr(self.romdef, "source", "") == "libretuner":
            self.romdef.tables = [t for t in self.romdef.tables if not flatshift.is_extra(t)]
            for t, sc in flatshift.extra_tables(data):
                self.romdef.scalings[sc.name] = sc
                self.romdef.tables.append(t)
        self.rom = Rom(data, self.romdef)

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

    def _disp(self, v, sc):
        """表示用フォーマット。定義の書式(sc.fmt)で桁落ちする小さい値は精度を上げて
        正確に表示する(例: %.3f だと 0.0005→"0.001" になるのを防ぐ)。"""
        if isinstance(v, float) and math.isnan(v):
            return "—"
        if isinstance(v, float):
            if sc:
                s = sc.fmt % v
                try:
                    if v != 0 and abs(float(s) - v) > abs(v) * 0.005:  # 0.5%超の桁落ち
                        s = f"{v:.6g}"
                except (ValueError, OverflowError):
                    pass
                return s
            return f"{v:g}"
        return str(v)

    def _render_table(self):
        for w in self.gf.winfo_children():
            w.destroy()
        self.cells = []
        self.xcells = []
        self.ycells = []
        self._live_cell = None   # セル再構築で旧ハイライト参照を破棄
        self._dot = None         # ●オーバーレイもグリッド破棄で無効化→次tickで再生成
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
        # 点数は軸の宣言 size(ax.elements)ではなく実グリッド次元(cols/rows)を表示する。
        # 定義の size は複数 variant 共用の最大値で、この CALID の実テーブル幅/高さより大きい
        # ことがあり(53テーブルで不一致)、グリッド本体と桁数がずれて見えるため。
        if t.ttype == "3D" and xa and ya:
            shape.append(f"{i18n.ui('map3d')}: {i18n.ui('axis_x')}={i18n.axis_label(xa.name)} "
                         f"{cols}{pt} / {i18n.ui('axis_y')}={i18n.axis_label(ya.name)} "
                         f"{rows}{pt}")
        elif t.ttype == "2D":
            ax = ya or xa
            n = max(rows, cols) if ax else cols * rows
            albl = i18n.axis_label(ax.name) if ax else ""
            shape.append(f"{i18n.ui('map2d')}: {albl} {n}{pt}")
        else:
            shape.append(i18n.ui("val1d"))
        vr = ""
        if sc and (sc.vmin or sc.vmax) and sc.vmin != sc.vmax:
            vr = f" / {i18n.ui('range')} {sc.fmt % sc.vmin}〜{sc.fmt % sc.vmax}"
        shape.append(f"{i18n.ui('unit')}={units or '-'}{vr}")
        parts.append("　".join(shape))
        tdesc = i18n.table_desc(t)
        if tdesc:
            parts.append(tdesc)
        parts.append(f"● {i18n.ui('effect')}: {i18n.effect_of(t.category)}")

        is_lt = getattr(self.romdef, "source", "") == "libretuner" and not flatshift.is_extra(t)
        if flatshift.is_extra(t):
            parts.append(i18n.ui("extra_note"))
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
        elif not flatshift.is_extra(t):
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
            return self._disp(v, sc)

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
        # X値見出し(ブレークポイント)。軸編集ONかつ書込可能な軸なら Entry で編集可。
        ax_editable_x = self.axis_edit and xa is not None and not xa.static_values
        ax_editable_y = self.axis_edit and ya is not None and not ya.static_values
        if xvals:
            if yvals:
                tk.Label(self.gf, text="", bg="#1e2128").grid(row=xhdr_row, column=0)
            for j, xv in enumerate(xvals):
                txt = fmt(xv) if isinstance(xv, float) else str(xv)
                if ax_editable_x and isinstance(xv, float):
                    e = tk.Entry(self.gf, width=8, justify="center", font=(self.mono, 9, "bold"),
                                 relief="flat", bd=1, bg="#45526b", fg="#ffffff",
                                 insertbackground="#ffffff")
                    e.insert(0, txt)
                    e.grid(row=xhdr_row, column=c0 + j, sticky="nsew", padx=1, pady=1)
                    e.bind("<Return>", lambda ev, jj=j: self._commit_axis("x", jj))
                    e.bind("<FocusOut>", lambda ev, jj=j: self._commit_axis("x", jj))
                    self.xcells.append(e)
                else:
                    tk.Label(self.gf, text=txt,
                             bg="#2b3340", fg="#cfe0f5", font=(self.mono, 9, "bold"),
                             width=8, borderwidth=1, relief="flat").grid(row=xhdr_row, column=c0 + j, sticky="nsew", padx=1, pady=1)
                    self.xcells.append(None)
        for i in range(rows):
            if yvals:
                yv = yvals[i] if i < len(yvals) else ""
                ytxt = fmt(yv) if isinstance(yv, float) else str(yv)
                if ax_editable_y and isinstance(yv, float):
                    e = tk.Entry(self.gf, width=8, justify="center", font=(self.mono, 9, "bold"),
                                 relief="flat", bd=1, bg="#45526b", fg="#ffffff",
                                 insertbackground="#ffffff")
                    e.insert(0, ytxt)
                    e.grid(row=r0 + i, column=0, sticky="nsew", padx=1, pady=1)
                    e.bind("<Return>", lambda ev, ii=i: self._commit_axis("y", ii))
                    e.bind("<FocusOut>", lambda ev, ii=i: self._commit_axis("y", ii))
                    self.ycells.append(e)
                else:
                    tk.Label(self.gf, text=ytxt,
                             bg="#2b3340", fg="#cfe0f5", font=(self.mono, 9, "bold"),
                             width=8, borderwidth=1, relief="flat").grid(row=r0 + i, column=0, sticky="nsew", padx=1, pady=1)
                    self.ycells.append(None)
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
            # 不正入力は保存値へ戻す(軸編集と同じ挙動)
            cur = self.rom.read_table(self.cur_table)[i][j]
            sc0 = self.romdef.scalings.get(self.cur_table.scaling)
            e.delete(0, "end")
            e.insert(0, self._disp(cur, sc0))
            return
        sc = self.romdef.scalings.get(self.cur_table.scaling)
        old = self.rom.read_table(self.cur_table)[i][j]
        rng = flatshift.strict_range(self.cur_table)
        if rng and not (rng[0] <= val <= rng[1]):
            # 追加項目(パッチ定数等)は範囲外を受け付けない
            messagebox.showwarning(i18n.ui("range_title"),
                                   i18n.ui("range_msg").format(lo=rng[0], hi=rng[1], v=val))
            e.delete(0, "end")
            e.insert(0, self._disp(old, sc))
            return
        if sc and isinstance(old, float) and abs(old - val) < 1e-9:
            return
        self.rom.write_cell(self.cur_table, i, j, val)
        self.modified = True
        # 該当セルのみ更新（全再描画は重いので避ける）: 保存値を読み直して表示・色を更新
        actual = self.rom.read_table(self.cur_table)[i][j]
        lo, hi = getattr(self, "_lohi", (0, 1))
        e.delete(0, "end")
        e.insert(0, self._disp(actual, sc))
        if isinstance(actual, (int, float)):
            e.config(bg=heat_color(actual, lo, hi), fg="#0b0d12")
        self._update_status()

    # ---------- 軸(ブレークポイント)編集 ----------
    def _axis_fmt(self, v):
        t = self.cur_table
        tsc = self.romdef.scalings.get(t.scaling) if (t and self.romdef) else None
        return self._disp(v, tsc)

    def _revert_axis(self, ax, role, idx):
        cells = self.xcells if role == "x" else self.ycells
        if idx >= len(cells) or cells[idx] is None:
            return
        vals = self.rom.read_axis(ax)
        cur = vals[idx] if idx < len(vals) else 0.0
        cells[idx].delete(0, "end")
        cells[idx].insert(0, self._axis_fmt(cur))

    def _commit_axis(self, role, idx):
        if not self.cur_table or not self.rom:
            return
        t = self.cur_table
        ax = t.x_axis if role == "x" else t.y_axis
        cells = self.xcells if role == "x" else self.ycells
        if ax is None or idx >= len(cells) or cells[idx] is None:
            return
        try:
            val = float(cells[idx].get())
        except ValueError:
            self._revert_axis(ax, role, idx)
            return
        vals = self.rom.read_axis(ax)
        old = vals[idx] if idx < len(vals) else None
        if isinstance(old, float) and abs(old - val) < 1e-9:
            return
        # 単調増加(昇順)チェック: 左 < val < 右
        lo = vals[idx - 1] if idx > 0 else None
        hi = vals[idx + 1] if idx + 1 < len(vals) else None
        if (lo is not None and val <= lo) or (hi is not None and val >= hi):
            messagebox.showerror(
                i18n.ui("axis_mono_title"),
                i18n.ui("axis_mono_msg").format(
                    lo=("-" if lo is None else f"{lo:g}"),
                    hi=("-" if hi is None else f"{hi:g}"),
                    v=f"{val:g}"))
            self._revert_axis(ax, role, idx)
            return
        self.rom.write_axis_value(ax, idx, val)
        self.modified = True
        actual = self.rom.read_axis(ax)[idx]
        cells[idx].delete(0, "end")
        cells[idx].insert(0, self._axis_fmt(actual))
        self._update_status()

    def toggle_axis_edit(self):
        if not self.axis_edit:
            if not messagebox.askyesno(i18n.ui("axis_edit_warn_title"), i18n.ui("axis_edit_warn")):
                return
        self.axis_edit = not self.axis_edit
        self.axis_btn.config(
            text=i18n.ui("axis_edit_on" if self.axis_edit else "axis_edit_off"),
            bg=("#b5651d" if self.axis_edit else "SystemButtonFace"),
            fg=("#ffffff" if self.axis_edit else "#000000"))
        if self.cur_table:
            self._render_table()

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

    # ---------- フラットシフト点火リタード・パッチ ----------
    def apply_flatshift(self):
        """点火リタード・パッチ(第3ドラフト, ncecu/flatshift.py)をメモリ上の ROM に当てる。
        ファイルは保存するまで変わらない(保存時にチェックサム自動補正)。"""
        if not self.rom:
            return
        title = i18n.ui("fs_title")
        data = self.rom.bytes_out()
        if flatshift.is_applied(data):
            messagebox.showinfo(title, i18n.ui("fs_already"))
            self._reveal_category(flatshift.PATCH_CATEGORY)
            return
        if not flatshift.can_apply(data):
            messagebox.showerror(title, i18n.ui("fs_unsupported").format(
                err=f"@0x{flatshift.CLAMP_LIT:X} / cave @0x{flatshift.CAVE:X}"))
            return
        if not messagebox.askyesno(title, i18n.ui("fs_confirm").format(**flatshift.DEFAULTS),
                                   icon="warning"):
            return
        try:
            new = flatshift.build(data, **flatshift.DEFAULTS)
        except ValueError as e:
            messagebox.showerror(title, i18n.ui("fs_unsupported").format(err=e))
            return
        self._set_rom(bytes(new))
        self.modified = True
        self._populate_tree()
        self._update_status()
        self._reveal_category(flatshift.PATCH_CATEGORY)
        messagebox.showinfo(title, i18n.ui("fs_done"))

    # ---------- アンチラグ(オーバーランのポップ) ----------
    def apply_antilag(self):
        """アクセルオフ時のアンチラグ(オーバーランのポップ)パッチを当てる(ncecu/antilag.py)。
        パターン A/B/C を選択。メモリ上の ROM だけ変更(保存時にチェックサム自動補正)。"""
        if not self.rom:
            return
        ja = self.lang == "ja"
        title = "アンチラグ" if ja else "Anti-lag"
        data = self.rom.bytes_out()
        try:
            antilag.verify_base(data)
        except ValueError as e:
            messagebox.showerror(title, (f"このROMには適用できません:\n{e}" if ja
                                         else f"Cannot apply to this ROM:\n{e}"))
            return
        pat = self._pick_antilag()
        if not pat:
            return
        try:
            new, changes = antilag.build(data, pat)
        except ValueError as e:
            messagebox.showerror(title, str(e))
            return
        self._set_rom(bytes(new))
        self.modified = True
        self._populate_tree()
        self._update_status()
        name = antilag.PATTERN_NAME[pat][0 if ja else 1]
        self._show_patch_result(
            (f"アンチラグ パターン{pat}: {name}" if ja else f"Anti-lag {pat}: {name}"), changes)

    def _pick_antilag(self):
        """A/B/C を選ぶダイアログ。選択('A'/'B'/'C')またはキャンセル(None)を返す。"""
        ja = self.lang == "ja"
        top = tk.Toplevel(self)
        top.title("アンチラグ" if ja else "Anti-lag")
        top.configure(bg="#1e2128")
        top.transient(self)
        top.grab_set()
        desc = {
            "A": ("A. DFCO無効（全回転バーブル）— 一番簡単。減速燃料カットを常時オフ＋減速点火を深く遅角。低回転でも鳴る/燃費悪化/踏み直しの穴が深い。",
                  "A. DFCO off (burble at all RPM) — simplest. Always-on fuel + deep decel retard."),
            "B": ("B. RPMゲート（3000rpm超だけ）★おすすめ — DFCOは有効のまま、燃料の残り方をRPMで分ける(≤3000=無音/>3000=ポップ)＋遅角20°。",
                  "B. RPM gate (above 3000 rpm) — recommended. DFCO on; fuel kept only above threshold + 20deg retard."),
            "C": ("C. ツキ重視（踏み直しを鋭く）— 遅角を浅く(12°)＋点火/燃料の復帰を速く＋DFCO無効。ポップ控えめ、レスポンス優先。",
                  "C. Response-focused — shallow retard (12deg), fast spark/fuel restore, DFCO off."),
        }
        tk.Label(top, text=("有効化の方法を選択してください:" if ja else "Choose how to enable:"),
                 bg="#1e2128", fg="#dfe3ea", font=(self.jp, 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=12, pady=(10, 4))
        var = tk.StringVar(value="B")
        for k in ("A", "B", "C"):
            tk.Radiobutton(top, text=desc[k][0 if ja else 1], variable=var, value=k,
                           bg="#1e2128", fg="#dfe3ea", selectcolor="#2b3340",
                           activebackground="#1e2128", activeforeground="#ffffff",
                           wraplength=560, justify="left", anchor="w", font=(self.jp, 10)
                           ).pack(fill="x", padx=16, pady=3)
        tk.Label(top, text=("⚠ 排気管内で燃料を燃やします＝触媒・排気系の熱害。純正触媒/マフラー車の常用は非推奨。予備/ベンチECUで。公道・騒音・排ガスは自己責任。"
                            if ja else
                            "WARN: burns fuel in the exhaust = heat damage to cat/exhaust. Bench/spare ECU; your responsibility on road."),
                 bg="#1e2128", fg="#e2b33a", wraplength=560, justify="left", anchor="w",
                 font=(self.jp, 9)).pack(fill="x", padx=12, pady=(8, 4))
        result = {"v": None}

        def ok():
            result["v"] = var.get()
            top.destroy()

        btns = tk.Frame(top, bg="#1e2128")
        btns.pack(fill="x", padx=12, pady=(4, 10))
        tk.Button(btns, text=("適用" if ja else "Apply"), command=ok).pack(side="right")
        tk.Button(btns, text=("キャンセル" if ja else "Cancel"),
                  command=top.destroy).pack(side="right", padx=(0, 6))
        self.wait_window(top)
        return result["v"]

    # ---------- 電スロチューニング(DBW 1:1化) ----------
    def apply_throttle(self):
        """電子スロットルのペダルマップを1:1寄りに立てる(ncecu/dbw_throttle.py)。"""
        if not self.rom:
            return
        ja = self.lang == "ja"
        title = "電スロチューニング" if ja else "DBW throttle"
        data = self.rom.bytes_out()
        try:
            dbw_throttle.verify_base(data)
        except ValueError as e:
            messagebox.showerror(title, (f"このROMには適用できません:\n{e}" if ja else f"Cannot apply:\n{e}"))
            return
        opt = self._pick_throttle()
        if not opt:
            return
        blend, cap, keep = opt
        try:
            new = dbw_throttle.build(data, blend=blend, cap_margin=cap, keep_idle_cols=keep)
            dbw_throttle.verify_result(data, new, blend=blend, cap_margin=cap, keep_idle_cols=keep)
        except (ValueError, AssertionError) as e:
            messagebox.showerror(title, str(e))
            return
        changes = self._throttle_changes(data, new, blend, cap, keep)
        self._set_rom(bytes(new))
        self.modified = True
        self._populate_tree()
        self._update_status()
        self._show_patch_result(
            (f"電スロチューニング（blend={blend:g} / 上限+{cap:g}%）" if ja
             else f"DBW throttle (blend={blend:g} / cap +{cap:g}%)"), changes)

    def _pick_throttle(self):
        """blend / cap_margin / keep_idle を入力。(blend,cap,keep) または None。"""
        ja = self.lang == "ja"
        top = tk.Toplevel(self)
        top.title("電スロチューニング" if ja else "DBW throttle")
        top.configure(bg="#1e2128")
        top.transient(self)
        top.grab_set()
        tk.Label(top, text=("ペダルマップ(アクセル→スロットル)を1:1寄りに立てます。制御＋安全監視の両コピーを同値で更新。"
                            if ja else "Raise the pedal map toward 1:1 (updates control + monitor copies)."),
                 bg="#1e2128", fg="#dfe3ea", wraplength=520, justify="left", anchor="w",
                 font=(self.jp, 10)).pack(fill="x", padx=12, pady=(10, 6))
        grid = tk.Frame(top, bg="#1e2128")
        grid.pack(fill="x", padx=12)
        rows = [("blend (0=純正 / 1=完全1:1)" if ja else "blend (0=stock / 1=full 1:1)", "1.0"),
                ("指令上限の引き上げ [%]" if ja else "cap margin [%]", "10"),
                ("アイドル直上で純正のまま残す列数" if ja else "keep idle columns", "0")]
        ents = []
        for i, (lab, dv) in enumerate(rows):
            tk.Label(grid, text=lab, bg="#1e2128", fg="#dfe3ea", anchor="w", font=(self.jp, 10)
                     ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=3)
            e = tk.Entry(grid, width=8)
            e.insert(0, dv)
            e.grid(row=i, column=1, sticky="w", pady=3)
            ents.append(e)
        tk.Label(top, text=("⚠ 2速低回転の50%上限(トラクション保護)は1:1化で外れます。立てすぎはギクシャク。実走未検証。予備/ベンチECUで。"
                            if ja else "WARN: removes the 2nd-gear 50% cap; not road-tested. Use a bench/spare ECU."),
                 bg="#1e2128", fg="#e2b33a", wraplength=520, justify="left", anchor="w",
                 font=(self.jp, 9)).pack(fill="x", padx=12, pady=(8, 4))
        result = {"v": None}

        def ok():
            try:
                blend = float(ents[0].get())
                cap = float(ents[1].get())
                keep = int(ents[2].get())
            except ValueError:
                messagebox.showwarning(top.title(), "数値を入力してください。" if ja else "Enter numbers.")
                return
            if not (0.0 <= blend <= 1.0 and 0.0 <= cap <= 100.0 and 0 <= keep <= 18):
                messagebox.showwarning(top.title(),
                                       "範囲: blend 0〜1 / 上限 0〜100 / 残す列 0〜18" if ja else "out of range")
                return
            result["v"] = (blend, cap, keep)
            top.destroy()

        btns = tk.Frame(top, bg="#1e2128")
        btns.pack(fill="x", padx=12, pady=(4, 10))
        tk.Button(btns, text=("適用" if ja else "Apply"), command=ok).pack(side="right")
        tk.Button(btns, text=("キャンセル" if ja else "Cancel"),
                  command=top.destroy).pack(side="right", padx=(0, 6))
        self.wait_window(top)
        return result["v"]

    def _throttle_changes(self, base, rom, blend, cap, keep):
        """電スロ変更のリザルト用リストを作る。"""
        ja = self.lang == "ja"

        def changed(addr, n):
            return base[addr:addr + 4 * n] != rom[addr:addr + 4 * n]

        out = []
        for g, c, m in dbw_throttle.GEAR_PAIRS:
            out.append({"name": (f"ペダルマップ {g}（制御/監視）" if ja else f"Pedal map {g} (ctrl/mon)"),
                        "addr": c,
                        "before": ("純正" if ja else "stock"),
                        "after": (f"1:1寄せ blend={blend:g}（制御@0x{c:X} / 監視@0x{m:X}）" if ja
                                  else f"blend={blend:g} (ctrl@0x{c:X}/mon@0x{m:X})"),
                        "changed": changed(c, dbw_throttle.ROWS * dbw_throttle.COLS)})
        if cap > 0:
            for a in dbw_throttle.CAP_ADDRS:
                out.append({"name": ("指令上限 Max（9点）" if ja else "Commanded Max (9)"),
                            "addr": a, "before": ("純正" if ja else "stock"), "after": f"+{cap:g}%",
                            "changed": changed(a, dbw_throttle.CAP_N)})
        return out

    def _show_patch_result(self, title, changes):
        """適用したパッチで変更された map データの一覧(リザルト)を表示。"""
        ja = self.lang == "ja"
        top = tk.Toplevel(self)
        top.title(title)
        top.configure(bg="#1e2128")
        top.transient(self)
        n = sum(1 for c in changes if c.get("changed", True))
        tk.Label(top, text=(f"次の map データを変更しました（{n}件・未保存。保存時にチェックサム自動補正）:"
                            if ja else f"Changed the following map data ({n} items, unsaved):"),
                 bg="#1e2128", fg="#dfe3ea", anchor="w", wraplength=660, justify="left",
                 font=(self.jp, 10)).pack(fill="x", padx=12, pady=(10, 6))
        frm = tk.Frame(top, bg="#1e2128")
        frm.pack(fill="both", expand=True, padx=12)
        txt = tk.Text(frm, width=92, height=min(20, max(6, len(changes) * 3 + 1)),
                      bg="#12151a", fg="#dfe3ea", wrap="word", font=(self.mono, 9), bd=0,
                      insertbackground="#dfe3ea")
        sb = ttk.Scrollbar(frm, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        for c in changes:
            if c.get("changed", True):
                mark = "●"
            else:
                mark = "○（変更なし）" if ja else "o (no change)"
            txt.insert("end", f"{mark} {c['name']}  @0x{c['addr']:X}\n")
            txt.insert("end", f"    {c['before']}\n      → {c['after']}\n\n")
        txt.configure(state="disabled")
        tk.Button(top, text=("閉じる" if ja else "Close"), command=top.destroy).pack(pady=(6, 10))

    def _reveal_category(self, category: str):
        """ツリーで指定カテゴリを開き、先頭の項目を選択する。"""
        label = i18n.translate_category(category)
        for iid in self.tree.get_children(""):
            if self.tree.item(iid, "text") == label:
                self.tree.item(iid, open=True)
                kids = self.tree.get_children(iid)
                if kids:
                    self.tree.selection_set(kids[0])
                    self.tree.see(kids[0])
                return

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
                lr = livelog.LiveReader(interval=0.0,    # 待ち0=最速ポーリング
                                        pid_intervals=self.live_pid_overrides,
                                        ram_reads=self.ram_reads)
                if self._log_fp is not None:
                    lr.on_update = self._log_cycle
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
        if self._log_fp is not None:
            self._stop_record()
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
        try:
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
                line1 = f"● {lr.rate:.1f}Hz  " + fmt(livelog.DEFAULT_PIDS)
                line2 = "  " + fmt(livelog.EXTRA_PIDS)
                dtcs = lr.latest_dtcs()
                if dtcs:
                    codes = " ".join(c for c, _ in dtcs[:10])
                    more = f" +{len(dtcs) - 10}" if len(dtcs) > 10 else ""
                    line3 = f"DTC({len(dtcs)}): {codes}{more}"
                else:
                    line3 = "DTC: なし"
                lines = [line1, line2, line3]
                if self.ram_reads:
                    if lr.mode23_ok is False:
                        lines.append("RAM(クラッチ/KR/減速/排気温/ノック): Mode23未有効化のため読めません")
                    else:
                        rv = []
                        for c in self.ram_reads:
                            v = lr.ram_values.get(c.get("role"))
                            if v is not None:
                                rv.append(f"{c.get('name', c.get('role'))}:{v:.1f}{c.get('unit', '')}")
                        lines.append("RAM " + ("  ".join(rv) if rv else "取得待ち…"))
                self.live_lbl.config(text="\n".join(lines), fg="#7fe0a0")
                self._update_live_cell(lr.latest())
                if self.dash_win is not None:
                    try:
                        if self.dash_win.winfo_exists():
                            self.dash_win.update_values(bp, dtcs)
                        else:
                            self.dash_win = None
                    except tk.TclError:
                        self.dash_win = None
        except tk.TclError:
            return                       # ウィジェット破棄中(終了時)=ループ終了
        except Exception:  # noqa: BLE001  一時的な例外で Live ループを止めない
            pass
        self._live_after = self.after(50, self._live_tick)   # ~20Hz でダッシュ/●/数値を更新

    def _update_live_cell(self, roles: dict):
        """現在の運転点に ● を重ね描き(開いているマップのみ)。連続インデックスで
        セル間も滑らかに移動する。"""
        t = self.cur_table
        if not t or not self.rom or not self.cells:
            return
        rows, cols = self.rom.dims(t)
        col_f = self._axis_pos_f(t.x_axis, roles, cols)
        row_f = self._axis_pos_f(t.y_axis, roles, rows)
        if col_f is None and cols == 1:
            col_f = 0.0
        if row_f is None and rows == 1:
            row_f = 0.0
        if row_f is None or col_f is None:
            self._clear_live_highlight()
            return
        row_f = max(0.0, min(rows - 1, row_f))
        col_f = max(0.0, min(cols - 1, col_f))
        self._apply_live_dot(row_f, col_f)

    # ライブ値(OBD)の取り得る範囲(ロール別)。軸範囲と重ならなければ別量の軸=追従しない。
    _LIVE_RANGE = {"RPM": (0, 9000), "LOAD": (0, 100), "ECT": (-45, 160), "IAT": (-45, 160),
                   "APP": (0, 100), "TP": (0, 100), "MAP": (0, 260), "MAF": (0, 660),
                   "VSS": (0, 260)}

    def _axis_pos_f(self, axis, roles: dict, n: int):
        """軸のライブ値から連続インデックス(小数)を返す。ライブ値と軸の量/単位が
        合わない軸(派生式・センサ電圧・デルタ・レンジ不一致)は誤った●を避けるため None。"""
        if axis is None:
            return None
        role = livelog.axis_role(axis.name)
        if role is None or role not in roles:
            return None
        # 派生/センサ電圧/デルタ等=ライブ値とは別量 → 追従しない(誤●防止)
        nm = axis.name.upper()
        if (" - " in axis.name
                or any(tok in nm for tok in ("_V_", "DELTA", "PROTO", "BITSHIFT", "/", "*", "+"))):
            return None
        try:
            vals = [x for x in self.rom.read_axis(axis)[:n]
                    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x))]
        except Exception:  # noqa: BLE001
            return None
        if not vals:
            return None
        amin, amax = min(vals), max(vals)
        v = roles[role]
        lo, hi = self._LIVE_RANGE.get(role, (None, None))
        # 単位整合: %系ライブ値を正規化軸(amax<=約1)へ /100(負荷の「常に1.000行」対策)
        if role in ("LOAD", "APP", "TP") and amax <= 2.0 and v > amax:
            v = v / 100.0
            if lo is not None:
                lo, hi = lo / 100.0, hi / 100.0
        # 妥当性: ライブ値レンジと軸レンジが全く重ならない=別量の軸 → ●を出さない
        if lo is not None and (amax < lo or amin > hi):
            return None
        return livelog.interp_index(vals, v)

    def _clear_live_highlight(self):
        if self._dot is not None:
            try:
                self._dot.place_forget()
            except tk.TclError:
                pass
        self._live_cell = None

    def _apply_live_dot(self, row_f, col_f):
        """運転点(row_f,col_f=小数)の画素位置に ● を place。下のセル色に馴染ませる。"""
        if not self.cells or not self.cells[0]:
            return
        ri = max(0, min(len(self.cells) - 1, int(round(row_f))))
        ci = max(0, min(len(self.cells[ri]) - 1, int(round(col_f))))
        try:
            self.gf.update_idletasks()
            c00 = self.cells[0][0]
            x0, y0 = c00.winfo_x(), c00.winfo_y()
            cw, ch = c00.winfo_width(), c00.winfo_height()
            pitch_x = (self.cells[0][1].winfo_x() - x0) if len(self.cells[0]) > 1 else (cw + 2)
            pitch_y = (self.cells[1][0].winfo_y() - y0) if len(self.cells) > 1 else (ch + 2)
            cx = x0 + col_f * pitch_x + cw / 2
            cy = y0 + row_f * pitch_y + ch / 2
        except (tk.TclError, IndexError):
            return
        if self._dot is None or not self._dot.winfo_exists():
            self._dot = tk.Label(self.gf, text="●", fg="#ff3b30",
                                 font=(self.mono, 13, "bold"), bd=0, padx=0, pady=0)
        try:
            self._dot.config(bg=self.cells[ri][ci].cget("bg"))
        except tk.TclError:
            pass
        try:
            self._dot.place(x=cx, y=cy, anchor="center")
            self._dot.lift()
        except tk.TclError:
            pass
        self._live_cell = (ri, ci)

    # ---------- ライブ記録 ----------
    def toggle_record(self):
        import datetime
        import json
        if self._log_fp is not None:
            self._stop_record()
            return
        if self.live_reader is None:
            messagebox.showinfo("記録", "先に Live ▶ を開始してください(Live中の値を記録します)。")
            return
        logs = HERE / "logs"
        logs.mkdir(exist_ok=True)
        path = logs / f"livelog_{datetime.datetime.now():%Y%m%d_%H%M%S}.jsonl"
        try:
            self._log_fp = open(path, "w", encoding="utf-8")
        except OSError as e:
            messagebox.showerror("記録", f"ファイルを開けません: {e}")
            return
        self._log_fp.write(json.dumps(
            {"_meta": "ncec livelog v1",
             "pids": [f"0x{p:02X}" for p in (livelog.DEFAULT_PIDS + livelog.EXTRA_PIDS)]},
            ensure_ascii=False) + "\n")
        self._log_t0 = None
        self._log_path = path
        if self.live_reader is not None:
            self.live_reader.on_update = self._log_cycle   # ポーリング周期ごとに高精度記録
        try:
            self.record_btn.config(text="記録停止 ■", bg="#a00000", fg="#ffffff")
        except tk.TclError:
            pass
        self._update_status()

    def _stop_record(self):
        if self._log_fp is None:
            return
        if self.live_reader is not None:
            self.live_reader.on_update = None   # 先にコールバック解除(書込みレース防止)
        try:
            self._log_fp.close()
        except OSError:
            pass
        self._log_fp = None
        p = self._log_path
        try:
            self.record_btn.config(text="記録 ●", bg="SystemButtonFace", fg="#000000")
        except tk.TclError:
            pass
        if p:
            messagebox.showinfo("記録", f"記録を保存しました:\n{p}\n\n[リプレイ] で再生できます。")

    def _log_cycle(self, by_pid, dtcs, t):
        """LiveReader の読取スレッドから1ポーリング周期ごとに呼ばれる(高精度記録)。"""
        import json
        fp = self._log_fp
        if fp is None:
            return
        if self._log_t0 is None:
            self._log_t0 = t
        rec = {"t": round(t - self._log_t0, 3),
               "pid": {f"0x{p:02X}": round(float(v), 4) for p, v in by_pid.items()},
               "dtc": [c for c, _ in (dtcs or [])]}
        try:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except (OSError, ValueError):
            pass

    # ---------- リプレイ ----------
    def open_replay(self):
        import json
        if self.live_reader is not None:
            messagebox.showinfo("リプレイ", "Live を停止してからリプレイしてください。")
            return
        path = filedialog.askopenfilename(
            title="ログを選択", initialdir=str(HERE / "logs"),
            filetypes=[("live log", "*.jsonl"), ("all", "*.*")])
        if not path:
            return
        frames = []
        try:
            with open(path, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    o = json.loads(line)
                    if "t" in o and "pid" in o:
                        frames.append(o)
        except (OSError, ValueError) as e:
            messagebox.showerror("リプレイ", f"読み込み失敗: {e}")
            return
        if not frames:
            messagebox.showinfo("リプレイ", "再生できるフレームがありません。")
            return
        self.open_dashboard()
        self._replay = {"frames": frames, "i": 0, "playing": True, "speed": 1.0,
                        "after": None, "seeking": False}
        self._build_replay_ui(path)
        self._replay_step()

    def _build_replay_ui(self, path):
        rp = self._replay
        win = tk.Toplevel(self)
        win.title("リプレイ — " + pathlib.Path(path).name)
        win.configure(bg="#1e2128")
        win.geometry("560x120")
        rp["win"] = win
        n = len(rp["frames"])
        bar = tk.Frame(win, bg="#1e2128")
        bar.pack(fill="x", pady=6)
        rp["btn"] = tk.Button(bar, text="⏸ 一時停止", width=12, command=self._replay_toggle)
        rp["btn"].pack(side="left", padx=6)
        tk.Label(bar, text="速度", bg="#1e2128", fg="#cccccc").pack(side="left")
        sp = ttk.Combobox(bar, width=5, values=["0.5x", "1x", "2x", "4x"], state="readonly")
        sp.set("1x")
        sp.pack(side="left", padx=4)
        sp.bind("<<ComboboxSelected>>",
                lambda e: self._replay.update(speed=float(sp.get().rstrip("x"))))
        rp["tlbl"] = tk.Label(bar, text="", bg="#1e2128", fg="#9fb0c8")
        rp["tlbl"].pack(side="left", padx=8)
        rp["scale"] = tk.Scale(win, from_=0, to=max(0, n - 1), orient="horizontal",
                               bg="#1e2128", fg="#cccccc", showvalue=False,
                               troughcolor="#11131a", highlightthickness=0,
                               command=self._replay_seek)
        rp["scale"].pack(fill="x", padx=10)
        win.protocol("WM_DELETE_WINDOW", self._close_replay)

    def _replay_toggle(self):
        rp = self._replay
        if not rp:
            return
        if rp.get("playing"):
            rp["playing"] = False
            if rp.get("after"):
                try:
                    self.after_cancel(rp["after"])
                except Exception:  # noqa: BLE001
                    pass
            rp["btn"].config(text="▶ 再生")
        else:
            rp["playing"] = True
            rp["btn"].config(text="⏸ 一時停止")
            self._replay_step()

    def _replay_seek(self, v):
        rp = self._replay
        if not rp or rp.get("seeking"):
            return
        i = max(0, min(len(rp["frames"]) - 1, int(float(v))))
        rp["i"] = i
        self._apply_replay_frame(rp["frames"][i])

    def _replay_step(self):
        rp = self._replay
        if not rp or not rp.get("playing"):
            return
        frames = rp["frames"]
        i = rp["i"]
        if i >= len(frames):
            rp["playing"] = False
            rp["i"] = 0
            try:
                rp["btn"].config(text="▶ 再生(先頭へ)")
            except tk.TclError:
                pass
            return
        self._apply_replay_frame(frames[i])
        rp["seeking"] = True
        try:
            rp["scale"].set(i)
            rp["tlbl"].config(text=f"{frames[i].get('t', 0):.1f}s  [{i + 1}/{len(frames)}]")
        except tk.TclError:
            pass
        rp["seeking"] = False
        dt = 0.1
        if i + 1 < len(frames):
            dt = max(0.0, frames[i + 1].get("t", 0) - frames[i].get("t", 0))
        rp["i"] = i + 1
        delay = max(10, int(dt * 1000 / max(0.1, rp.get("speed", 1.0))))
        rp["after"] = self.after(delay, self._replay_step)

    def _apply_replay_frame(self, frame):
        by_pid = {}
        for k, v in frame.get("pid", {}).items():
            try:
                by_pid[int(k, 16)] = v
            except (ValueError, TypeError):
                pass
        roles = {}
        for pid, v in by_pid.items():
            s = livelog.PIDS.get(pid)
            if s:
                roles[s.role] = v
        dtcs = [(c, "") for c in frame.get("dtc", [])]
        self._update_live_cell(roles)
        if self.dash_win is not None:
            try:
                if self.dash_win.winfo_exists():
                    self.dash_win.update_values(by_pid, dtcs)
                else:
                    self.dash_win = None
            except tk.TclError:
                self.dash_win = None
        try:
            self.live_lbl.config(text=f"[リプレイ] t={frame.get('t', 0):.1f}s", fg="#7fc4ff")
        except tk.TclError:
            pass

    def _close_replay(self):
        rp = self._replay
        if rp:
            if rp.get("after"):
                try:
                    self.after_cancel(rp["after"])
                except Exception:  # noqa: BLE001
                    pass
            try:
                rp["win"].destroy()
            except tk.TclError:
                pass
        self._replay = None

    # ---------- ROM 書き込み(実機フラッシュ) ----------
    def flash_ecu(self):
        if not self.rom:
            messagebox.showinfo("ECU書き込み", "先にROMを開いてください。")
            return
        if self.live_reader is not None:
            messagebox.showinfo("ECU書き込み", "Live を停止してください(CANアダプタは排他)。")
            return
        sbl_def = HERE / "Decryption_sbl" / "sbl_nc1_flash_0x2000.bin"
        if sbl_def.exists():
            sbl_line = (f"・使用SBL: Decryption_sbl\\{sbl_def.name}"
                        "(0x1800, NC1)※次画面で確認\n")
        else:
            sbl_line = (f"・SBL(0x1800, NC1)が必要: 次画面で {sbl_def.name} を選択\n")
        msg = ("⚠ 実機フラッシュ(消去を伴う不可逆操作・ブリックの実リスク)\n\n"
               "・対象: いま開いているROM(編集内容をチェックサム補正して書込み)\n"
               "・予備/ベンチECU以外には使わないこと\n"
               "・電源を安定させ、約10分間 抜線/電源断をしないこと\n"
               + sbl_line + "\n"
               "続行しますか?")
        if not messagebox.askyesno("ECU書き込み(本番)", msg):
            return
        sbl_path = filedialog.askopenfilename(
            title=f"SBLを選択(既定 {sbl_def.name} / 0x1800, NC1)",
            initialdir=str(sbl_def.parent if sbl_def.exists() else HERE),
            initialfile=(sbl_def.name if sbl_def.exists() else ""),
            filetypes=[("SBL bin", "*.bin"), ("all", "*.*")])
        if not sbl_path:
            return
        try:
            sbl = pathlib.Path(sbl_path).read_bytes()
        except OSError as e:
            messagebox.showerror("ECU書き込み", f"SBL読込失敗: {e}")
            return
        if len(sbl) != 0x1800:
            if not messagebox.askyesno(
                    "ECU書き込み", f"SBLサイズが0x{len(sbl):X}(想定0x1800)です。続行?"):
                return
        self._run_flash(bytes(self.rom.data), sbl)

    def _run_flash(self, rom_bytes, sbl):
        win = tk.Toplevel(self)
        win.title("ECU書き込み中…")
        win.configure(bg="#1e2128")
        win.geometry("660x360")
        txt = tk.Text(win, bg="#11131a", fg="#d8e0ea", font=(self.mono, 9), relief="flat")
        txt.pack(fill="both", expand=True, padx=6, pady=6)

        def log(s=""):
            def ins():
                try:
                    txt.insert("end", str(s) + "\n")
                    txt.see("end")
                except tk.TclError:
                    pass
            self.after(0, ins)

        def work():
            import time as _t
            from ncecu.canbus import open_bus, close_bus
            from ncecu.diag import DiagClient
            from ncecu.isotp import IsoTp
            bus = None
            started = False   # True になってから先が「消去が起き得る」区間
            try:
                # open_bus はハンドル解放待ちで一時的に Errno13 になり得る → 短いリトライ
                last = None
                for attempt in range(4):
                    try:
                        bus = open_bus()
                        last = None
                        break
                    except Exception as e:  # noqa: BLE001
                        last = e
                        log(f"  CAN接続リトライ {attempt + 1}/4 … ({type(e).__name__})")
                        _t.sleep(0.8)
                if bus is None:
                    raise last
                diag = DiagClient(IsoTp(bus))
                diag.tp.timeout = 10.0
                log(f"通信確認: tester_present={diag.tester_present()}")
                f = flashmod.Flasher(diag, log=log)
                started = True   # ここから f.flash = 消去+書込みが走る
                f.flash(rom_bytes, sbl, flash_start=flashmod.ROM_FLASH_START_MIN, confirm=True)
                log("\n★ 書き込み完了。車両搭載前に一度電源を入れ直してください。")
            except Exception as e:  # noqa: BLE001
                name = type(e).__name__
                if not started:
                    log(f"\n!! 接続失敗(書き込み=消去は一切行っていません=完全に安全): {name}: {e}")
                    s = str(e)
                    if "Errno 13" in s or "Access" in s or "USB" in name or "USB" in s:
                        log("原因: CANアダプタ(SH-C30L)が他に掴まれています。対処:")
                        log("  ① 端末で動作中の probe.py / tx_test.py / flash_writeback.py を終了")
                        log("  ② SH-C30L のUSBを一度抜き挿し、またはエディタを再起動")
                        log("  ③ もう一つのエディタ/他プロセス(mt5_monitor.py 等)がCANを使っていないか確認")
                        log("  → その後もう一度 [ECU書き込み] を実行(ECUは無傷なので安全に再試行可)")
                    else:
                        log("  ECUの電源・CAN配線・通常セッションを確認してください。")
                else:
                    log(f"\n!! 失敗: {name}: {e}")
                    log("電源を保ったまま状況を確認(SBL段=安全 / プログラム段=消去済みの可能性)。")
            finally:
                if bus is not None:
                    close_bus(bus)
        threading.Thread(target=work, daemon=True).start()

    def toggle_lang(self):
        self.lang = "en" if self.lang == "ja" else "ja"
        i18n.set_language(self.lang)
        # ボタン等の文言を更新
        for key, b in self.btns.items():
            b.config(text=i18n.ui(key))
        self.lang_btn.config(text=i18n.ui("lang"))
        self.search_lbl.config(text=i18n.ui("search"))
        self.live_btn.config(text=i18n.ui("live_off") if self.live_reader else i18n.ui("live_on"))
        self.axis_btn.config(text=i18n.ui("axis_edit_on" if self.axis_edit else "axis_edit_off"))
        if getattr(self, "menubar", None) is not None:
            try:
                self.menubar.entryconfigure(self._settings_idx, label=i18n.ui("menu_settings"))
                self.settings_menu.entryconfigure(0, label=i18n.ui("menu_live_intervals"))
            except tk.TclError:
                pass
        # ツリーと現在マップを再描画
        self._populate_tree()
        if self.cur_table:
            self._render_table()
        self._update_status()

    # ---------- ライブPID間引き設定 ----------
    CHOICE_SECONDS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0]

    def _load_live_intervals(self):
        """live_intervals.json(既定からの差分)を読む。{pid:秒} を返す。"""
        import json
        try:
            d = json.loads(LIVE_INTERVALS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        out = {}
        for k, v in (d.items() if isinstance(d, dict) else []):
            try:
                pid = int(str(k), 16) if str(k).lower().startswith("0x") else int(k)
                out[pid] = max(0.0, float(v))
            except (ValueError, TypeError):
                pass
        return out

    def _save_live_intervals(self):
        import json
        try:
            LIVE_INTERVALS_PATH.write_text(
                json.dumps({f"0x{p:02X}": v for p, v in sorted(self.live_pid_overrides.items())},
                           ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:  # noqa: BLE001
            messagebox.showwarning(i18n.ui("li_title"), f"保存に失敗: {e}")

    def _load_ram_reads(self):
        """ram_reads.json を読む。無ければ既定(livelog.RAM_CHANNELS)。
        既存ファイルには、未収録の既定ch(新機能追加分=ノック等)を追補する
        (ユーザが変更した番地/間隔は保持)。"""
        import json
        try:
            d = json.loads(RAM_READS_PATH.read_text(encoding="utf-8"))
            if isinstance(d, list) and all(isinstance(x, dict) and "addr" in x for x in d):
                have = {x.get("ch") for x in d}
                for c in livelog.RAM_CHANNELS:
                    if c.get("ch") not in have:
                        d.append(dict(c))
                return d
        except (OSError, ValueError):
            pass
        return [dict(c) for c in livelog.RAM_CHANNELS]

    def _save_ram_reads(self):
        import json
        try:
            RAM_READS_PATH.write_text(json.dumps(self.ram_reads, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        except OSError:
            pass

    def _interval_label(self, v):
        if v == 0:
            return i18n.ui("li_every")
        return f"{v:g}秒" if self.lang == "ja" else f"{v:g}s"

    def _effective_interval(self, pid):
        return self.live_pid_overrides.get(pid, livelog.DEFAULT_PID_INTERVALS.get(pid, 0.0))

    def open_live_intervals(self):
        """ライブ計測のPIDごと＋ライブRAM(クラッチ/KR/減速/排気温/ノック)の問い合わせ間隔を設定。"""
        pids = list(livelog.DEFAULT_PIDS) + list(livelog.EXTRA_PIDS)
        win = tk.Toplevel(self)
        win.title(i18n.ui("li_title"))
        win.configure(bg="#1e2128")
        win.transient(self)
        tk.Label(win, text=i18n.ui("li_note"), bg="#1e2128", fg="#b9c6da",
                 justify="left", anchor="w", font=(self.jp, 9)).pack(fill="x", padx=10, pady=(8, 4))
        grid = tk.Frame(win, bg="#1e2128")
        grid.pack(fill="both", expand=True, padx=10, pady=4)
        vars_ = {}

        def sel_seconds(pid):
            lab = vars_[pid].get()
            for s in self._opts_for(pid):
                if self._interval_label(s) == lab:
                    return s
            return 0.0

        def update_est():
            fast = sum(1 for p in pids if sel_seconds(p) == 0)
            req = (fast + 5) // 6 if fast else 0
            est.config(text=i18n.ui("li_estimate").format(n=fast, req=req))

        def add_row(parent, r, c, pid):
            spec = livelog.PIDS[pid]
            tk.Label(parent, text=f"{spec.name} (0x{pid:02X}) {spec.unit}", bg="#1e2128",
                     fg="#dfe3ea", anchor="w", font=(self.jp, 10)
                     ).grid(row=r, column=c * 3, sticky="w", padx=(0, 6), pady=1)
            cur = self._effective_interval(pid)
            labels = [self._interval_label(s) for s in self._opts_for(pid)]
            var = tk.StringVar(value=self._interval_label(cur))
            vars_[pid] = var
            cb = ttk.Combobox(parent, textvariable=var, values=labels, state="readonly", width=9)
            cb.grid(row=r, column=c * 3 + 1, sticky="w", padx=(0, 18), pady=1)
            cb.bind("<<ComboboxSelected>>", lambda _e: update_est())

        half = (len(pids) + 1) // 2
        for i, pid in enumerate(pids):
            add_row(grid, i if i < half else i - half, 0 if i < half else 1, pid)

        est = tk.Label(win, text="", bg="#1e2128", fg="#7fe0a0", anchor="w", font=(self.jp, 10))
        est.pack(fill="x", padx=10, pady=(4, 2))
        update_est()

        # --- ライブRAM読み出し(Mode23) チャンネルの間隔 ---
        ram_vars = {}
        if self.ram_reads:
            hdr = ("ライブRAM読み出し（Mode23：クラッチ/KR/減速/排気温/ノック）"
                   if self.lang == "ja" else "Live RAM reads (Mode23: KR/clutch/EGT/knock)")
            tk.Label(win, text=hdr, bg="#1e2128", fg="#b9c6da", anchor="w",
                     font=(self.jp, 9)).pack(fill="x", padx=10, pady=(6, 0))
            rgrid = tk.Frame(win, bg="#1e2128")
            rgrid.pack(fill="both", expand=True, padx=10, pady=(2, 4))

            def add_ram_row(r, c, chn):
                cur = chn.get("interval", 0.5)
                o = sorted(set(self.CHOICE_SECONDS + [cur]))
                name = chn.get("name", chn.get("role", ""))
                tk.Label(rgrid, text=f"{name} (0x{chn.get('addr', 0):08X})", bg="#1e2128",
                         fg="#dfe3ea", anchor="w", font=(self.jp, 10)
                         ).grid(row=r, column=c * 3, sticky="w", padx=(0, 6), pady=1)
                var = tk.StringVar(value=self._interval_label(cur))
                ram_vars[chn["ch"]] = (var, o)
                cb = ttk.Combobox(rgrid, textvariable=var,
                                  values=[self._interval_label(s) for s in o],
                                  state="readonly", width=9)
                cb.grid(row=r, column=c * 3 + 1, sticky="w", padx=(0, 18), pady=1)

            rhalf = (len(self.ram_reads) + 1) // 2
            for i, chn in enumerate(self.ram_reads):
                add_ram_row(i if i < rhalf else i - rhalf, 0 if i < rhalf else 1, chn)

        def ram_sel(ch):
            var, o = ram_vars[ch]
            lab = var.get()
            for s in o:
                if self._interval_label(s) == lab:
                    return s
            return 0.5

        def do_reset():
            for pid in pids:
                vars_[pid].set(self._interval_label(livelog.DEFAULT_PID_INTERVALS.get(pid, 0.0)))
            defiv = {c["ch"]: c.get("interval", 0.5) for c in livelog.RAM_CHANNELS}
            for ch, (var, _o) in ram_vars.items():
                var.set(self._interval_label(defiv.get(ch, 0.5)))
            update_est()

        def do_apply():
            eff = {pid: sel_seconds(pid) for pid in pids}
            self.live_pid_overrides = {p: v for p, v in eff.items()
                                       if v != livelog.DEFAULT_PID_INTERVALS.get(p, 0.0)}
            self._save_live_intervals()
            if self.live_reader is not None:          # 接続中なら即時反映
                for pid, v in eff.items():
                    self.live_reader.set_pid_interval(pid, v)
            for ch in list(ram_vars):                 # ライブRAMの間隔を反映(保存＋即時)
                self._set_ch_interval(ch, ram_sel(ch))
            win.destroy()
            messagebox.showinfo(i18n.ui("li_title"), i18n.ui("li_saved"))

        btns = tk.Frame(win, bg="#1e2128")
        btns.pack(fill="x", padx=10, pady=(4, 10))
        tk.Button(btns, text=i18n.ui("li_reset"), command=do_reset).pack(side="left")
        tk.Button(btns, text=i18n.ui("li_cancel"), command=win.destroy).pack(side="right", padx=(6, 0))
        tk.Button(btns, text=i18n.ui("li_apply"), command=do_apply).pack(side="right")

    def _opts_for(self, pid):
        """この PID の選択肢(秒)。現在値が既定の候補に無ければ足す。"""
        cur = self._effective_interval(pid)
        opts = list(self.CHOICE_SECONDS)
        if cur not in opts:
            opts = sorted(set(opts + [cur]))
        return opts

    def open_chart(self):
        """ロギング(livelog_*.jsonl)を分析チャートで開く。"""
        logs = HERE / "logs"
        p = filedialog.askopenfilename(
            title="ログを選択 (livelog_*.jsonl)",
            initialdir=str(logs) if logs.exists() else str(HERE),
            filetypes=[("live log", "*.jsonl"), ("all", "*.*")])
        if not p:
            return
        try:
            ncec_chart.ChartWindow(self, p, jp=self.jp, mono=self.mono)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("ログ分析", f"開けませんでした:\n{e}")

    def _ch_interval(self, ch):
        """チャンネルの現在の更新周期[秒](0=毎回)。PID と ライブRAM(合成ch) に対応。"""
        if isinstance(ch, int) and ch >= 0x100:
            for c in self.ram_reads:
                if c.get("ch") == ch:
                    return c.get("interval", 0.5)
            return None
        if isinstance(ch, int):
            return self.live_pid_overrides.get(ch, livelog.DEFAULT_PID_INTERVALS.get(ch, 0.0))
        return None

    def _set_ch_interval(self, ch, seconds):
        """ダッシュボードからの更新周期変更を LiveReader と設定ファイルに反映。"""
        seconds = max(0.0, float(seconds))
        lr = self.live_reader
        if isinstance(ch, int) and ch >= 0x100:        # ライブRAM(合成ch)
            for c in self.ram_reads:
                if c.get("ch") == ch:
                    c["interval"] = seconds
            if lr is not None:
                for c in getattr(lr, "ram_reads", []):
                    if c.get("ch") == ch:
                        c["interval"] = seconds
                lr._ram_last.pop(ch, None)
            self._save_ram_reads()
        elif isinstance(ch, int):                       # PID 間引き
            default = livelog.DEFAULT_PID_INTERVALS.get(ch, 0.0)
            if abs(seconds - default) < 1e-6:
                self.live_pid_overrides.pop(ch, None)
            else:
                self.live_pid_overrides[ch] = seconds
            if lr is not None:
                lr.set_pid_interval(ch, seconds)
            self._save_live_intervals()

    def open_dashboard(self):
        if self.dash_win is not None:
            try:
                if self.dash_win.winfo_exists():
                    self.dash_win.lift()
                    return
            except tk.TclError:
                pass
        self.dash_win = ncec_dashboard.DashboardWindow(
            self, jp=self.jp, mono=self.mono,
            get_interval=self._ch_interval, set_interval=self._set_ch_interval)
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
            from ncecu.canbus import open_bus, close_bus
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
                    close_bus(bus)
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
        self._set_rom(data)
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
                # 本体グリッドと同じ適応精度表示を使う(定義書式で桁落ちする小さい値も正確に)
                sc = self.romdef.scalings.get(tc.scaling) if self.romdef else None
                for (r, c, va, vb) in tc.samples:
                    txt.insert("end",
                               f"    ({r},{c})  {self._disp(va, sc)}  →  {self._disp(vb, sc)}\n")
                if tc.ncells > len(tc.samples):
                    txt.insert("end", f"    … 他 {tc.ncells - len(tc.samples)} セル\n")
                txt.insert("end", "\n")
        txt.configure(state="disabled")
        tk.Button(win, text="閉じる", command=win.destroy).pack(pady=6)
        win.transient(self)


if __name__ == "__main__":
    Editor().mainloop()
