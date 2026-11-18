"""NCEC ROM マップエディタ (tkinter) — LFG7xx 用。

機能: ROM/定義の読み込み、カテゴリ別テーブル一覧、2D/3Dマップの表示・編集(ヒートマップ)、
チェックサム再計算付き保存。実ECUには触れない(オフライン編集)。

起動: python ncec_editor.py
"""
from __future__ import annotations

import math
import pathlib
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ncec_chart
import ncec_dashboard
import ncec_popup as popup
import ncec_shortcuts as shortcuts
import ncec_tableview as tableview
import ncec_uistate as uistate
from ncec_tableview import heat_color  # noqa: F401  (旧版からの互換のため残す)
from ncecu import (antilag, axis_ram, checksum, convhint, dbw_throttle, defs, ectcount, flash as flashmod,
                   flatshift, i18n, livelog, ltdef, revdrop, romdiff, wslcan)
from ncecu.rom import Rom

# ツリーに追加CAL(LibreTuner定義に無いパッチ定数)を出すモジュール群。
# いずれも is_extra / extra_tables / strict_range を同じ形で備える。
# ※オートブリッピング(autoblip*/idle_slew)は 2026-11-12 にエディタから外し、v2.71 でモジュール/CLIも撤去した。
#   ROM編集では監視と整合する高速ブリップが作れないため(経緯は docs/project_index_ja.md §13/§16)。
#   アイドル回転補正パッチ(idle_base)も v2.71 で撤去(Idle Speed - Base の制御側/監視側を直接編集する)。
_EXTRA_MODS = (flatshift,)


def _any_extra(t) -> bool:
    return any(m.is_extra(t) for m in _EXTRA_MODS)


def _extra_strict_range(t):
    for m in _EXTRA_MODS:
        rng = m.strict_range(t)
        if rng:
            return rng
    return None

HERE = pathlib.Path(__file__).resolve().parent
ROM_DIR = HERE / "rom_data"                            # 保存ROMデータ専用フォルダ(著作権ROM=git/zip対象外)
# 起動時に自動で開くROM。ROMは rom_data/ に集約(v2.71)。ベンチECUの吸い出し原本を既定にする
# (旧 ncec_rom_dump.bin と同一内容)。無ければ旧配置にフォールバック、それも無ければ空で起動。
DEFAULT_ROM = next((c for c in (ROM_DIR / "ecu_readout_yahooauction.bin", HERE / "ncec_rom_dump.bin")
                    if c.exists()), ROM_DIR / "ecu_readout_yahooauction.bin")
DEFAULT_DEF = HERE / "defs" / "lfg7eg.xml"              # RomRaider XML(予備)
DEFAULT_LT_MAIN = HERE / "defs" / "libretuner" / "main.json"
DEFAULT_LT_CALID = HERE / "defs" / "libretuner" / "LFG7EG.json"
LIVE_INTERVALS_PATH = HERE / "live_intervals.json"   # ライブPID間引きのユーザ設定(既定からの差分)
RAM_READS_PATH = HERE / "ram_reads.json"             # ライブRAM読み出し(Mode23)チャンネル設定


def _rom_dir() -> str:
    """保存ROMデータ専用フォルダのパスを返す(無ければ作成)。
    ROM・吸い出し・ROM比較の各ダイアログの既定の場所。ROMはマツダの著作物なので
    .gitignore と配布zipの対象外(/rom_data/)。作成に失敗したらアプリ直下にフォールバック。"""
    try:
        ROM_DIR.mkdir(exist_ok=True)
        return str(ROM_DIR)
    except OSError:
        return str(HERE)


def _read_version() -> str:
    """同梱の VERSION ファイルからバージョン文字列を読む(無ければ 'dev')。"""
    try:
        return (HERE / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"


__version__ = _read_version()


class Editor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"NCEC ROM Map Editor  v{__version__}")
        uistate.restore_geometry(self, uistate.get("editor"), "1360x780", 800, 500)
        self._geo_keeper = uistate.GeometryKeeper(self, "editor")   # 前回の位置/大きさを覚える
        self.configure(bg="#1e2128")
        self.rom: Rom | None = None
        self.rom_path: pathlib.Path | None = None
        self.romdef: defs.RomDef | None = None
        self.modified = False
        self.orig_data: bytes | None = None   # 読み込み/保存した時点の内容(変えたセルの印・元に戻す)
        self._log_fp = None         # ライブ記録ファイル
        self._log_t0 = None
        self._log_path = None
        self._replay = None         # リプレイ状態
        self.axis_edit = False          # 軸ブレークポイント編集モード(既定OFF・誤操作防止)
        # ライブ(実機 OBD)状態
        self.live_reader: livelog.LiveReader | None = None
        self._live_after = None
        self.dash_win = None
        self.lang = "ja"
        i18n.set_language(self.lang)
        self.live_pid_overrides = self._load_live_intervals()  # pid->秒(既定と異なるもの)
        self.ram_reads = self._load_ram_reads()                # ライブRAM読み出しチャンネル
        # 表の分割表示(ペイン)・別ウィンドウ・編集履歴・ショートカット
        self.views: list[tableview.TableView] = []             # 分割ペイン(レイアウトの順)
        self.float_views: list[tableview.TableView] = []       # 別ウィンドウ
        self.active_view: tableview.TableView | None = None
        self.layout = "1"
        self.pane_state = [{"table": None, "zoom": 1.0} for _ in range(4)]
        self._pws: list = []                                   # レイアウトの PanedWindow(外側から)
        self.history: list[dict] = []                          # 元に戻す
        self.redo_stack: list[dict] = []
        opts = uistate.get("options", {}) or {}
        self.mirror_pairs = bool(opts.get("mirror_pairs", True))   # 制御⇔監視へ同じ値を書く
        self.show_marks = bool(opts.get("show_marks", True))       # 保存後に変えたセルの印
        self.show_desc = bool(opts.get("show_desc", True))
        self.steps = dict(uistate.get("steps", {}) or {})          # 表ごとの増減幅 {"C7EE4": [小, 大]}
        self.keymap = shortcuts.load_keymap(uistate.get("shortcuts", {}))
        self._keyrev = shortcuts.reverse(self.keymap)
        self.altmask = shortcuts.alt_mask(self)
        self._pairs: dict[int, tuple[int, str]] = {}
        for _c, _m in i18n.CONTROL_MONITOR_PAIRS:
            self._pairs[_c] = (_m, "control")
            self._pairs[_m] = (_c, "monitor")
        self._save_views_after = None
        self._build()
        self._auto_load()
        self._restore_views()
        self.bind("<KeyPress>", self._on_root_key)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def cur_table(self):
        """アクティブなペインの表(説明欄・ライブ追従の基準)。"""
        v = self.active_view
        return v.table if v is not None else None

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

        # メニューバー(設定) — 各パッチ適用/DTCクリアもここへ集約(ツールバー見切れ対策)
        self._build_menus()

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
        # 各パッチ(フラットシフト/アンチラグ/回転落ち/電スロ)の適用は[設定]メニューへ移動。
        # 言語/軸編集/検索は右端に固定し、ウィンドウ幅が狭くても見切れないようにする。
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._populate_tree())
        self.search_entry = tk.Entry(bar, textvariable=self.search_var, width=20)
        self.search_entry.pack(side="right", padx=4)
        self.search_lbl = tk.Label(bar, text=i18n.ui("search"), bg="#1e2128", fg="#dfe3ea")
        self.search_lbl.pack(side="right")
        self.lang_btn = tk.Button(bar, text=i18n.ui("lang"), command=self.toggle_lang)
        self.lang_btn.pack(side="right", padx=(8, 8))
        self.axis_btn = tk.Button(bar, text=i18n.ui("axis_edit_off"), command=self.toggle_axis_edit)
        self.axis_btn.pack(side="right", padx=2)
        # ボタンの既定の面色/文字色を生成時に控える。WSLg/Linux の Tk では "SystemButtonFace" が
        # 無効な色名で config が TclError になり、Live/記録/軸編集ボタンが有効色(青/赤/橙)のまま
        # 戻らない不具合があったため、プラットフォーム既定値をそのまま復帰色に使う。
        self._btn_face = self.live_btn.cget("background")
        self._btn_fg = self.live_btn.cget("foreground")

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
        self.tree.bind("<Return>", lambda _e: (self._focus_active_view(), "break")[1])
        self.tree.bind("<Button-3>", self._tree_context)
        main.add(left, width=360)

        right = tk.Frame(main, bg="#1e2128")
        self.info = tk.Label(right, text="", bg="#1e2128", fg="#9fb0c8",
                             anchor="w", justify="left", font=(self.jp, 10))
        self.info.pack(fill="x", padx=4, pady=(2, 0))
        self.live_lbl = tk.Label(right, text="", bg="#1e2128", fg="#7fe0a0",
                                 anchor="w", justify="left", font=(self.mono, 10),
                                 wraplength=1000)
        self.live_lbl.pack(fill="x", padx=4, pady=(0, 0))
        self.desc = tk.Label(right, text="マップを選ぶと、ここに説明が表示されます。",
                             bg="#232733", fg="#b9c6da", anchor="w", justify="left",
                             font=(self.jp, 10), wraplength=820, padx=8, pady=6)
        self.desc.pack(fill="x", padx=4, pady=(2, 4))

        # 右ペイン幅に合わせて Liveモニタ/説明を折り返す(横に見切れないように)。
        def _on_right_resize(e):
            try:
                self.live_lbl.config(wraplength=max(240, e.width - 16))
                if getattr(self, "desc", None) is not None:
                    self.desc.config(wraplength=max(240, e.width - 24))
            except tk.TclError:
                pass
        right.bind("<Configure>", _on_right_resize)
        # 表を出す場所。レイアウト(1/左右2/上下2/3/4分割)に合わせて PanedWindow を組み直す。
        # 境界(サッシ)はドラッグで自由に動かせる。表は別ウィンドウにも出せる(自由配置)。
        self.view_host = tk.Frame(right, bg="#1e2128")
        self.view_host.pack(fill="both", expand=True)
        if not self.show_desc:
            self.desc.pack_forget()
        main.add(right)

        sbar = tk.Frame(self, bg="#11131a")
        sbar.pack(fill="x", side="bottom")
        self.status_sel = tk.Label(sbar, text="", bg="#11131a", fg="#7fc4ff", anchor="e",
                                   font=(self.jp, 9))
        self.status_sel.pack(side="right", padx=(8, 6))
        self.status = tk.Label(sbar, text="準備完了", bg="#11131a", fg="#9fb0c8",
                               anchor="w", font=(self.jp, 9))
        self.status.pack(side="left", fill="x", expand=True)

    # ---------- メニュー ----------
    def _act_item(self, menu, aid, label=None):
        """操作 aid をメニューに出す(右側にショートカットキーを表示)。"""
        a = shortcuts.BY_ID[aid]
        menu.add_command(label=label or a.label(self.lang), accelerator=shortcuts.accel(self.keymap, aid),
                         command=lambda aid=aid: self.run_action(aid))

    def _build_menus(self):
        """メニューバーを現在の言語で(再)構築する。ファイル/編集/表示は操作一覧(ncec_shortcuts)から作り、
        ショートカットキーを右に出す。設定配下にパッチ適用とDTCクリアを集約。"""
        ja = self.lang == "ja"
        self.menubar = tk.Menu(self)
        fm = tk.Menu(self.menubar, tearoff=0)
        for aid in ("open_rom", "save", "save_as", "cmp_rom"):
            self._act_item(fm, aid)
        fm.add_separator()
        for aid in ("dump", "cmp_ecu"):
            self._act_item(fm, aid)
        fm.add_separator()
        fm.add_command(label="終了" if ja else "Exit", command=self._on_close)
        self.menubar.add_cascade(label="ファイル" if ja else "File", menu=fm)

        em = tk.Menu(self.menubar, tearoff=0)
        for aid in ("undo", "redo"):
            self._act_item(em, aid)
        em.add_separator()
        for aid in ("copy", "paste", "select_all", "goto_live"):
            self._act_item(em, aid)
        em.add_separator()
        for aid in ("set_value", "add_value", "percent", "multiply", "inc", "dec", "inc_big", "dec_big"):
            self._act_item(em, aid)
        em.add_separator()
        for aid in ("interp_h", "interp_v", "interp_2d", "smooth", "fill_down", "fill_right"):
            self._act_item(em, aid)
        em.add_separator()
        for aid in ("revert_sel", "copy_to_pair", "set_step", "axis_edit"):
            self._act_item(em, aid)
        self.menubar.add_cascade(label="編集" if ja else "Edit", menu=em)

        vm = tk.Menu(self.menubar, tearoff=0)
        for aid in ("layout_1", "layout_2h", "layout_2v", "layout_3", "layout_4"):
            a = shortcuts.BY_ID[aid]
            vm.add_command(label=("● " if self.layout == aid[7:] else "　") + a.label(self.lang),
                           accelerator=shortcuts.accel(self.keymap, aid),
                           command=lambda aid=aid: self.run_action(aid))
        vm.add_separator()
        for aid in ("next_pane", "prev_pane", "show_pair", "detach", "close_pane"):
            self._act_item(vm, aid)
        vm.add_separator()
        for aid in ("zoom_in", "zoom_out", "zoom_reset"):
            self._act_item(vm, aid)
        vm.add_separator()
        self._mv_mirror = tk.BooleanVar(value=self.mirror_pairs)
        self._mv_marks = tk.BooleanVar(value=self.show_marks)
        self._mv_desc = tk.BooleanVar(value=self.show_desc)
        vm.add_checkbutton(label=("ペア同時編集（制御側⇔監視側に同じ値を書く）" if ja
                                  else "Paired editing (write control and monitor together)"),
                           variable=self._mv_mirror, accelerator=shortcuts.accel(self.keymap, "mirror_pairs"),
                           command=lambda: self._set_option("mirror_pairs", self._mv_mirror.get()))
        vm.add_checkbutton(label=("保存後に変えたセルに印を付ける" if ja else "Mark cells changed since saving"),
                           variable=self._mv_marks,
                           command=lambda: self._set_option("show_marks", self._mv_marks.get()))
        vm.add_checkbutton(label=("説明欄を表示" if ja else "Show description"), variable=self._mv_desc,
                           accelerator=shortcuts.accel(self.keymap, "toggle_desc"),
                           command=lambda: self._set_option("show_desc", self._mv_desc.get()))
        vm.add_separator()
        self._act_item(vm, "lang")
        self.menubar.add_cascade(label="表示" if ja else "View", menu=vm)

        m = tk.Menu(self.menubar, tearoff=0)
        self.settings_menu = m
        m.add_command(label=i18n.ui("menu_live_intervals"), command=self.open_live_intervals)
        m.add_command(label=i18n.ui("menu_chart"), command=self.open_chart,
                      accelerator=shortcuts.accel(self.keymap, "chart"))
        m.add_command(label=("ショートカットキー…" if ja else "Keyboard shortcuts…"), command=self.open_shortcuts)
        m.add_separator()
        pm = tk.Menu(m, tearoff=0)
        pm.add_command(label=i18n.ui("fs_patch"), command=self.apply_flatshift)
        pm.add_command(label=i18n.ui("al_patch"), command=self.apply_antilag)
        pm.add_command(label=i18n.ui("rd_patch"), command=self.apply_revdrop)
        pm.add_command(label=i18n.ui("th_patch"), command=self.apply_throttle)
        m.add_cascade(label=i18n.ui("menu_patches"), menu=pm)
        m.add_separator()
        m.add_command(label=i18n.ui("menu_dtc_clear"), command=self.clear_dtcs_action)
        # WSL2/socketcan 実行時のみ「CAN接続(状態確認・再接続)」を出す。gs_usb(Windows)では非表示。
        if wslcan.is_socketcan():
            m.add_separator()
            m.add_command(label=i18n.ui("menu_can_connect"), command=self.open_can_connect)
        self.menubar.add_cascade(label=i18n.ui("menu_settings"), menu=m)
        try:
            self.config(menu=self.menubar)
        except tk.TclError:
            pass

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

        def open_manual():
            """統合マニュアル(目次付きHTML)を既定のブラウザで開く。"""
            import webbrowser
            p = HERE / "docs" / ("map_analysis_JA.html" if self.lang == "ja" else "map_analysis.html")
            if p.exists():
                webbrowser.open(p.as_uri())
            else:
                messagebox.showinfo("ヘルプ", f"統合マニュアルが見つかりません:\n{p}", parent=win)

        btns = tk.Frame(win, bg="#1e2128")
        btns.pack(pady=6)
        tk.Button(btns, text=("統合マニュアルを開く（ブラウザ）" if self.lang == "ja"
                              else "Open the full manual (browser)"),
                  command=open_manual).pack(side="left", padx=4)
        tk.Button(btns, text=("閉じる" if self.lang == "ja" else "Close"),
                  command=win.destroy).pack(side="left", padx=4)
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
        self.orig_data = bytes(data)
        self.history.clear()
        self.redo_stack.clear()
        self._set_rom(data)
        self.rom_path = pathlib.Path(rom_path)
        self.modified = False
        self._populate_tree()
        self._update_status()

    def _set_rom(self, data: bytes, record=False):
        """ROM を設定する。定義(LibreTuner)に無い追加項目(各パッチの追加CAL)を
        この ROM に合わせて差し替える(パッチ定数はパッチ適用済み ROM のときだけ出す)。
        record=True(パッチ適用)なら、変わったバイトを「元に戻す」に記録する。"""
        old = bytes(self.rom.data) if (record and self.rom is not None) else None
        if self.romdef and getattr(self.romdef, "source", "") == "libretuner":
            self.romdef.tables = [t for t in self.romdef.tables if not _any_extra(t)]
            for mod in _EXTRA_MODS:
                for t, sc in mod.extra_tables(data):
                    self.romdef.scalings[sc.name] = sc
                    self.romdef.tables.append(t)
        self.rom = Rom(data, self.romdef)
        if old is not None and len(old) == len(data):
            ch = self._diff_bytes(old, bytes(data))
            if ch:
                self._push_history("パッチ適用" if self.lang == "ja" else "Patch", ch, extras=True)
        self._rebind_views()

    def _load(self, rom_path, def_path):
        self.romdef = defs.parse(def_path)
        self._finish_load(rom_path)

    def _load_lt(self, rom_path, main_path, calid_path):
        self.romdef = ltdef.parse(main_path, calid_path)
        self._finish_load(rom_path)

    def open_rom(self):
        p = filedialog.askopenfilename(title="ROM (.bin)", initialdir=_rom_dir(),
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

    # ---------- 検索(名前 / 0xアドレス) ----------
    @staticmethod
    def _addr_query(q: str):
        """検索語が 0x で始まる16進アドレスなら (先頭ゼロを除いた16進文字列, 数値) を返す。
        それ以外(名前検索)は None。入力途中("0x" や "0xd6c")でも使えるよう接頭辞も扱う。"""
        if not q.startswith("0x"):
            return None
        h = q[2:].replace("_", "")
        if any(c not in "0123456789abcdef" for c in h):
            return None
        h = h.lstrip("0")
        return h, (int(h, 16) if h else 0)

    def _table_spans(self, t):
        """このテーブルがROM上で占める範囲 [(先頭番地, バイト数), …]。本体＋各軸。"""
        sc = self.romdef.scalings.get(t.scaling)
        try:
            rows, cols = self.rom.dims(t) if self.rom else (1, t.elements)
        except Exception:  # noqa: BLE001
            rows, cols = 1, t.elements
        spans = [(t.address, max(1, rows * cols * (sc.size if sc else 1)))]
        for ax in t.axes:
            if ax.static_values or not ax.address:
                continue
            asc = self.romdef.scalings.get(ax.scaling)
            spans.append((ax.address, max(1, ax.elements * (asc.size if asc else 1))))
        return spans

    def _addr_match(self, t, addr_q) -> bool:
        """アドレス検索の一致判定。次のどれかで一致とする:
        - 本体/軸の先頭番地が、入力した16進の並びで始まる(入力途中の絞り込み。例 0xd6c → 0xD6C9C)
        - 入力した番地が、本体/軸の範囲の中にある(表の途中の番地でも見つかる)
        - RAM番地(0xFFFFxxxx)なら、その RAM 変数を軸の入力に使う表(ncecu/axis_ram.py。ROM のコードから
          求めたこの ROM の実番地。例 回転数 0xFFFF6D5C)。軸名の末尾(例 RPM_6DD8)は LibreTuner が使った
          別 ROM の番地でずれているので、照合に使わない"""
        h, val = addr_q
        if not h:
            return True                      # "0x" だけ=まだ絞り込まない
        for start, size in self._table_spans(t):
            if f"{start:x}".startswith(h) or start <= val < start + size:
                return True
        if h.startswith("ffff"):         # RAM 番地(0xFFFFxxxx)
            if len(h) < 8:               # 入力途中(0xffff6d 等)は前方一致で絞り込む
                return any(f"{r:x}".startswith(h) for ax in t.axes for r in axis_ram.inputs(t.address, ax.address))
            return t.address in axis_ram.tables_reading(val)
        return False

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.romdef:
            return
        q = self.search_var.get().lower().strip()
        addr_q = self._addr_query(q)          # "0x…" ならアドレス検索(名前検索はしない)
        cats: dict[str, str] = {}
        for i, t in enumerate(self.romdef.tables):
            cat_ja = i18n.translate_category(t.category)
            name_disp = i18n.translate_table_name(t.name)
            if addr_q is not None:
                if not self._addr_match(t, addr_q):
                    continue
            elif q and q not in t.name.lower() and q not in t.category.lower() \
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
        self.open_table(self.romdef.tables[int(vals[0])])

    def open_table(self, t, view=None):
        """表 t をペインに出す(既定はアクティブなペイン)。"""
        v = view or self.active_view or (self.views[0] if self.views else None)
        if v is None:
            return
        v.set_table(t)
        if v is not self.active_view:
            self.set_active(v)
        else:
            self._show_desc()
        self._sync_follow()
        self._sync_pair_selection(v)
        self._save_views_soon()

    def fmt_value(self, v, sc):
        return self._disp(v, sc)

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
        """互換用: 全ペインを描き直し、説明欄を更新する。"""
        for v in self._all_views():
            v.redraw()
        self._show_desc()

    def _show_desc(self):
        """アクティブなペインの表の情報行と説明欄を作る。"""
        self._conv_idx = None    # 説明欄の「換算」行の位置(A/D値・タイマ・増量%の表だけ。編集後に差し替える)
        self._desc_parts = None
        t = self.cur_table
        if not t or not self.rom:
            self.info.config(text="")
            self.desc.config(text=("マップを選ぶと、ここに説明が表示されます。" if self.lang == "ja"
                                   else "Pick a map to see its description here."))
            return
        sc = self.romdef.scalings.get(t.scaling)
        grid = self.rom.read_table(t)
        rows, cols = self.rom.dims(t)
        xa, ya = t.x_axis, t.y_axis
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
        rams = self._axis_ram_text(t)
        if rams:
            parts.append(rams)
        tdesc = i18n.table_desc(t)
        if tdesc:
            parts.append(tdesc)
        parts.append(f"● {i18n.ui('effect')}: {i18n.effect_of(t.category)}")
        # 水温センサの A/D 値で持たれている表(電動ファンの水温しきい値)は ℃ 換算を、ファンのタイマは秒、
        # 閉ループ目標の増量%は λ を出す(編集の補助)。
        if ectcount.is_count_table(t.name) or convhint.applies(t.name):
            self._conv_idx = len(parts)
            parts.append(self._conv_text(t, grid))

        is_lt =getattr(self.romdef, "source", "") == "libretuner" and not _any_extra(t)
        if _any_extra(t):
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
        elif not _any_extra(t):
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
        self._desc_parts = parts
        self.desc.config(text="\n".join(parts))

    # ---------- 書き込み(ペインから呼ばれる)・元に戻す ----------
    def _all_views(self):
        out = []
        for v in self.views + self.float_views:
            try:
                if v.winfo_exists():
                    out.append(v)
            except tk.TclError:
                pass
        return out

    def pair_info(self, t):
        """(相方の表, 照合・同時編集できるか)。制御側⇔監視側の写し(i18n.CONTROL_MONITOR_PAIRS)。"""
        if t is None or not self.romdef:
            return None, False
        pr = self._pairs.get(t.address)
        if not pr:
            return None, False
        partner = next((x for x in self.romdef.tables if x.address == pr[0]), None)
        if partner is None:
            return None, False
        try:
            sa = self.romdef.scalings.get(t.scaling)
            sb = self.romdef.scalings.get(partner.scaling)
            ok = (self.rom is not None and self.rom.dims(t) == self.rom.dims(partner)
                  and sa is not None and sb is not None and sa.storagetype == sb.storagetype
                  and (sa.toexpr or "x") == (sb.toexpr or "x"))
        except Exception:  # noqa: BLE001
            ok = False
        return partner, ok

    def pair_side(self, t):
        """相方がどちら側か (日本語, 英語)。"""
        pr = self._pairs.get(t.address) if t is not None else None
        if not pr:
            return "", ""
        return ("監視側", "monitor") if pr[1] == "control" else ("制御側", "control")

    def steps_for(self, t, grid=None):
        """表の増減幅 (小, 大)。ユーザーが決めた値が無ければ値の大きさから決める。"""
        st = self.steps.get(f"{t.address:X}")
        if isinstance(st, list) and len(st) == 2 and all(isinstance(x, (int, float)) and x > 0 for x in st):
            return float(st[0]), float(st[1])
        return self._default_steps(t, grid)

    def _default_steps(self, t, grid=None):
        sc = self.romdef.scalings.get(t.scaling)
        if grid is None:
            grid = self.rom.read_table(t)
        vals = [abs(float(v)) for row in grid for v in row if tableview.isnum(v)]
        m = max(vals) if vals else 0.0
        if not m and sc:
            m = max(abs(sc.vmin), abs(sc.vmax))
        small = 10 ** math.floor(math.log10(m)) / 100 if m > 0 else 0.01
        if sc is not None and sc.storagetype != "float":
            unit = abs(sc.to_real(1) - sc.to_real(0)) or 1.0      # 生値 1 の実値
            small = max(unit, round(small / unit) * unit)
        return small, small * 10

    def edit_cells(self, view, updates: dict, label: str = "") -> bool:
        """ペインの表へ {(行, 列): 値} を書く。範囲チェック、ペア同時編集(相方へ同じバイト)、
        元に戻す の記録、表示の更新までここで行う。"""
        t = view.table if view is not None else None
        if t is None or self.rom is None or not updates:
            return False
        rng = _extra_strict_range(t)
        if rng:
            bad = [v for v in updates.values() if not (rng[0] <= v <= rng[1])]
            if bad:
                # 追加項目(パッチ定数等)は範囲外を受け付けない
                messagebox.showwarning(i18n.ui("range_title"),
                                       i18n.ui("range_msg").format(lo=rng[0], hi=rng[1], v=bad[0]))
                view.refresh()
                return False
        sc = self.romdef.scalings.get(t.scaling)
        size = sc.size if sc else 1
        rows, cols = self.rom.dims(t)
        partner, ok = self.pair_info(t)
        mirror = partner if (self.mirror_pairs and ok) else None
        data = self.rom.data
        changes = []
        for (r, c), val in updates.items():
            if not (0 <= r < rows and 0 <= c < cols):
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(val):
                continue
            off = (r * cols + c) * size
            a = t.address + off
            old = bytes(data[a:a + size])
            self.rom.write_cell(t, r, c, val)
            new = bytes(data[a:a + size])
            if old != new:
                changes.append((a, old, new))
            if mirror is not None:
                pa = mirror.address + off
                pold = bytes(data[pa:pa + size])
                if pold != new:
                    data[pa:pa + size] = new
                    changes.append((pa, pold, new))
        if not changes:
            view.refresh()
            return False
        if mirror is not None:
            label += ("（相方 0x%X にも同じ値）" % mirror.address) if self.lang == "ja" \
                else (" (also paired 0x%X)" % mirror.address)
        self._push_history(f"{label} — {i18n.translate_table_name(t.name)}", changes)
        self._after_write()
        return True

    def edit_axis(self, view, role, idx, val) -> bool:
        """軸(ブレークポイント)の1点を書く。昇順を崩す値は受け付けない。相方の軸も同時編集する。"""
        t = view.table
        if t is None or self.rom is None:
            return False
        ax = t.x_axis if role == "x" else t.y_axis
        if ax is None or ax.static_values:
            return False
        vals = self.rom.read_axis(ax)
        if idx >= len(vals):
            return False
        old = vals[idx]
        if isinstance(old, float) and abs(old - val) < 1e-9:
            view.refresh()
            return False
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
            view.refresh()
            return False
        asc = self.romdef.scalings.get(ax.scaling)
        size = asc.size if asc else 4
        data = self.rom.data
        a = ax.address + idx * size
        oldb = bytes(data[a:a + size])
        self.rom.write_axis_value(ax, idx, val)
        newb = bytes(data[a:a + size])
        changes = [(a, oldb, newb)] if oldb != newb else []
        partner, ok = self.pair_info(t)
        if self.mirror_pairs and ok and newb != oldb:
            pax = partner.x_axis if role == "x" else partner.y_axis
            if pax is not None and not pax.static_values and pax.address != ax.address \
                    and pax.scaling == ax.scaling and idx < pax.elements:
                pa = pax.address + idx * size
                pold = bytes(data[pa:pa + size])
                if pold != newb:
                    data[pa:pa + size] = newb
                    changes.append((pa, pold, newb))
        if not changes:
            view.refresh()
            return False
        self._push_history(("軸の編集" if self.lang == "ja" else "Axis edit")
                           + f" — {i18n.translate_table_name(t.name)}", changes)
        self._after_write()
        return True

    def revert_cells(self, view):
        """選択範囲を、読み込み/保存した時点の値に戻す(ペア同時編集が ON なら相方も)。"""
        t = view.table
        if t is None or self.orig_data is None:
            return
        sc = self.romdef.scalings.get(t.scaling)
        size = sc.size if sc else 1
        _, cols = self.rom.dims(t)
        partner, ok = self.pair_info(t)
        bases = [t.address] + ([partner.address] if (self.mirror_pairs and ok) else [])
        data = self.rom.data
        changes = []
        for r, c in view.sel_cells():
            for base in bases:
                a = base + (r * cols + c) * size
                cur = bytes(data[a:a + size])
                org = bytes(self.orig_data[a:a + size])
                if cur != org:
                    data[a:a + size] = org
                    changes.append((a, cur, org))
        if not changes:
            self.status_note("選択範囲は保存済みの値のままです。" if self.lang == "ja" else "Nothing to revert.")
            return
        self._push_history(("保存済みの値に戻す" if self.lang == "ja" else "Revert")
                           + f" — {i18n.translate_table_name(t.name)}", changes)
        self._after_write()

    def copy_to_pair(self, view):
        """選択範囲の値(バイト)を相方の表の同じセルへ写す。"""
        t = view.table
        partner, ok = self.pair_info(t)
        ja = self.lang == "ja"
        if partner is None or not ok:
            self.status_note("この表には同じ寸法の相方(制御⇔監視)がありません。" if ja
                             else "No compatible paired table.")
            return
        sc = self.romdef.scalings.get(t.scaling)
        size = sc.size if sc else 1
        _, cols = self.rom.dims(t)
        data = self.rom.data
        changes = []
        for r, c in view.sel_cells():
            off = (r * cols + c) * size
            src = bytes(data[t.address + off:t.address + off + size])
            pa = partner.address + off
            old = bytes(data[pa:pa + size])
            if old != src:
                data[pa:pa + size] = src
                changes.append((pa, old, src))
        if not changes:
            self.status_note("相方と同じ値です。" if ja else "Already equal.")
            return
        self._push_history((f"相方 0x{partner.address:X} へコピー" if ja else f"Copy to 0x{partner.address:X}"),
                           changes)
        self._after_write()

    def _push_history(self, label, changes, extras=False):
        self.history.append({"label": label, "changes": changes, "extras": extras})
        if len(self.history) > 300:
            del self.history[0]
        self.redo_stack.clear()

    def _after_write(self):
        self.modified = self.orig_data is None or bytes(self.rom.data) != self.orig_data
        for v in self._all_views():
            if v.table is not None:
                v.refresh()
        self._refresh_conv()
        self._update_status()
        self.on_selection(self.active_view)

    def _apply_history(self, h, undo):
        data = self.rom.data
        for a, old, new in (reversed(h["changes"]) if undo else h["changes"]):
            data[a:a + len(old)] = old if undo else new
        if h.get("extras"):                    # パッチ: 追加項目(ツリー)を作り直す
            self._set_rom(bytes(data))
            self._populate_tree()
        self._after_write()

    def undo(self):
        ja = self.lang == "ja"
        if not self.history or self.rom is None:
            self.status_note("元に戻す操作はありません。" if ja else "Nothing to undo.")
            return
        h = self.history.pop()
        self._apply_history(h, undo=True)
        self.redo_stack.append(h)
        self.status_note(("元に戻しました: " if ja else "Undone: ") + h["label"])

    def redo(self):
        ja = self.lang == "ja"
        if not self.redo_stack or self.rom is None:
            self.status_note("やり直す操作はありません。" if ja else "Nothing to redo.")
            return
        h = self.redo_stack.pop()
        self._apply_history(h, undo=False)
        self.history.append(h)
        self.status_note(("やり直しました: " if ja else "Redone: ") + h["label"])

    @staticmethod
    def _diff_bytes(a: bytes, b: bytes, chunk: int = 256):
        """2つの同じ長さのバイト列の差分 [(番地, 旧, 新)]。"""
        out = []
        n = len(a)
        for i in range(0, n, chunk):
            j = min(n, i + chunk)
            if a[i:j] == b[i:j]:
                continue
            k = i
            while k < j:
                if a[k] != b[k]:
                    s = k
                    while k < j and a[k] != b[k]:
                        k += 1
                    out.append((s, bytes(a[s:k]), bytes(b[s:k])))
                else:
                    k += 1
        return out

    # ---------- ペイン(分割表示・別ウィンドウ) ----------
    LAYOUTS = {"1": 1, "2h": 2, "2v": 2, "3": 3, "4": 4}

    def set_active(self, view):
        if view is self.active_view:
            return
        self.active_view = view
        for v in self._all_views():
            v.set_active(v is view)
        self._show_desc()
        self._sync_follow()
        self.on_selection(view)

    def _focus_active_view(self):
        v = self.active_view or (self.views[0] if self.views else None)
        if v is not None:
            v.focus_table()
        return "break"

    def _resolve(self, t):
        """定義を読み直したあとに、同じ表(番地と名前)を探す。"""
        if t is None or not self.romdef:
            return None
        for x in self.romdef.tables:
            if x is t:
                return t
        return (next((x for x in self.romdef.tables if x.address == t.address and x.name == t.name), None)
                or next((x for x in self.romdef.tables if x.address == t.address), None))

    def _find_table(self, key):
        if not isinstance(key, dict) or not self.romdef:
            return None
        addr, name = key.get("addr"), key.get("name")
        return (next((x for x in self.romdef.tables if x.address == addr and x.name == name), None)
                or next((x for x in self.romdef.tables if x.address == addr), None))

    def _rebind_views(self):
        """ROM/定義を入れ替えたあと、各ペインの表を引き直して描き直す。"""
        for st in self.pane_state:
            st["table"] = self._resolve(st.get("table"))
        for v in self._all_views():
            v.table = self._resolve(v.table)
            v.redraw()
            if v.slot == "float" and v.table is not None:
                v.winfo_toplevel().title(i18n.translate_table_name(v.table.name))
        self._show_desc()
        self._sync_follow()

    def set_layout(self, mode):
        if mode not in self.LAYOUTS:
            return
        for v in self.views:
            self.pane_state[v.slot] = {"table": v.table, "zoom": v.zoom, "anchor": v.anchor, "cursor": v.cursor}
        act = self.active_view
        active_slot = act.slot if (act is not None and act in self.views) else (0 if act is None else None)
        for w in self.view_host.winfo_children():
            w.destroy()
        self.views = []
        self._pws = []
        if act in self.views or (act is not None and act.slot != "float"):
            self.active_view = None
        self.layout = mode
        opts = dict(sashwidth=6, bd=0, bg="#151820", sashrelief="flat", opaqueresize=True)

        def mk(parent, slot):
            v = tableview.TableView(parent, self, slot)
            st = self.pane_state[slot]
            v.zoom = st.get("zoom", 1.0) or 1.0
            v.table = self._resolve(st.get("table"))
            v.anchor = st.get("anchor", (0, 0))
            v.cursor = st.get("cursor", (0, 0))
            v.redraw()
            self.views.append(v)
            return v

        def pw(parent, orient):
            p = tk.PanedWindow(parent, orient=orient, **opts)
            self._pws.append(p)
            return p

        if mode == "1":
            mk(self.view_host, 0).pack(fill="both", expand=True)
        elif mode in ("2h", "2v"):
            p = pw(self.view_host, "horizontal" if mode == "2h" else "vertical")
            p.pack(fill="both", expand=True)
            for i in range(2):
                p.add(mk(p, i), stretch="always", minsize=80)
        elif mode == "3":
            outer = pw(self.view_host, "horizontal")
            outer.pack(fill="both", expand=True)
            outer.add(mk(outer, 0), stretch="always", minsize=80)
            inner = pw(outer, "vertical")
            inner.add(mk(inner, 1), stretch="always", minsize=60)
            inner.add(mk(inner, 2), stretch="always", minsize=60)
            outer.add(inner, stretch="always", minsize=80)
        else:
            outer = pw(self.view_host, "vertical")
            outer.pack(fill="both", expand=True)
            rows = []
            for k in range(2):
                row = pw(outer, "horizontal")
                rows.append(row)
            for k, row in enumerate(rows):
                for i in range(2):
                    row.add(mk(row, k * 2 + i), stretch="always", minsize=80)
                outer.add(row, stretch="always", minsize=60)
        self.after(80, self._equalize_sashes)
        if self.active_view is None:
            tgt = next((v for v in self.views if v.slot == active_slot), self.views[0])
            self.set_active(tgt)
        else:
            for v in self._all_views():
                v.set_active(v is self.active_view)
        self._build_menus()
        self._sync_follow()
        self._save_views_soon()

    def _equalize_sashes(self, fracs=None):
        try:
            self.update_idletasks()
        except tk.TclError:
            return
        for k, p in enumerate(self._pws):
            try:
                n = len(p.panes())
                if n < 2:
                    continue
                horiz = str(p.cget("orient")) == "horizontal"
                total = p.winfo_width() if horiz else p.winfo_height()
                if total <= 10:
                    continue
                fr = fracs[k] if (isinstance(fracs, list) and k < len(fracs) and isinstance(fracs[k], list)
                                  and len(fracs[k]) == n - 1) else [(i + 1) / n for i in range(n - 1)]
                for i, f in enumerate(fr):
                    pos = int(total * max(0.05, min(0.95, float(f))))
                    if horiz:
                        p.sash_place(i, pos, 0)
                    else:
                        p.sash_place(i, 0, pos)
            except (tk.TclError, ValueError, TypeError):
                pass

    def _sash_fracs(self):
        out = []
        for p in self._pws:
            try:
                n = len(p.panes())
                horiz = str(p.cget("orient")) == "horizontal"
                total = p.winfo_width() if horiz else p.winfo_height()
                if total <= 10:
                    out.append(None)
                    continue
                out.append([round(p.sash_coord(i)[0 if horiz else 1] / total, 4) for i in range(n - 1)])
            except (tk.TclError, ValueError):
                out.append(None)
        return out

    def open_float(self, table, zoom=1.0, geometry=None):
        """表を別ウィンドウ(自由に動かせる/大きさを変えられる)で開く。"""
        win = tk.Toplevel(self)
        win.configure(bg="#1e2128")
        uistate.restore_geometry(win, {"geometry": geometry} if geometry else None, "640x420", 240, 160)
        v = tableview.TableView(win, self, "float")
        v.pack(fill="both", expand=True)
        v.zoom = zoom or 1.0
        v.set_table(table)
        win.title(i18n.translate_table_name(table.name) if table is not None else "NCEC")
        win.bind("<KeyPress>", self._on_root_key)
        win.protocol("WM_DELETE_WINDOW", lambda v=v: self._close_float(v))
        win.bind("<Configure>", lambda e, w=win: self._save_views_soon() if e.widget is w else None, add="+")
        self.float_views.append(v)
        self.set_active(v)
        v.focus_table()
        self._save_views_soon()
        return v

    def _close_float(self, v):
        if v in self.float_views:
            self.float_views.remove(v)
        if self.active_view is v:
            self.active_view = None
            if self.views:
                self.set_active(self.views[0])
        try:
            v.winfo_toplevel().destroy()
        except tk.TclError:
            pass
        self._sync_follow()
        self._save_views_soon()

    def view_close(self, v):
        if v.slot == "float":
            self._close_float(v)
            return
        v.set_table(None)
        v.set_live(None, None)
        self.pane_state[v.slot]["table"] = None
        if v is self.active_view:
            self._show_desc()
        self._sync_follow()
        self._save_views_soon()

    def view_detach(self, v):
        if v.table is None:
            return
        nv = self.open_float(v.table, zoom=v.zoom)
        nv.set_selection(v.anchor, v.cursor, notify=False)

    def view_pair(self, v):
        """相方(制御⇔監視)の表を隣のペイン(別ウィンドウなら別ウィンドウ)に出す。"""
        ja = self.lang == "ja"
        partner, _ok = self.pair_info(v.table)
        if partner is None:
            self.status_note("この表には制御側/監視側の写しがありません。" if ja
                             else "This table has no control/monitor copy.")
            return
        if v.slot == "float":
            nv = self.open_float(partner, zoom=v.zoom)
        else:
            slot = v.slot
            if len(self.views) < 2:
                self.pane_state[slot] = {"table": v.table, "zoom": v.zoom, "anchor": v.anchor,
                                         "cursor": v.cursor}
                self.set_layout("2h")
                v = self.views[slot] if slot < len(self.views) else self.views[0]
            nv = self.views[(v.slot + 1) % len(self.views)]
            nv.zoom = v.zoom
            nv.set_table(partner)
        nv.set_selection(v.anchor, v.cursor, notify=False, see=True)
        self.set_active(v)
        v.focus_table()
        self._sync_follow()
        self._save_views_soon()

    def _open_with_pair(self, t):
        self.open_table(t)
        if self.active_view is not None:
            self.view_pair(self.active_view)

    def _cycle_pane(self, d):
        allv = [v for v in self._all_views()]
        if not allv:
            return
        i = allv.index(self.active_view) if self.active_view in allv else 0
        nv = allv[(i + d) % len(allv)]
        if nv.slot == "float":
            try:
                nv.winfo_toplevel().lift()
            except tk.TclError:
                pass
        nv.focus_table()

    def _step_table(self, d):
        """ツリー上の次/前の表を開く(フォーカスは表のまま)。"""
        items = [k for c in self.tree.get_children("") for k in self.tree.get_children(c)]
        if not items:
            return
        sel = self.tree.selection()
        i = items.index(sel[0]) if (sel and sel[0] in items) else -1
        j = max(0, min(len(items) - 1, i + d))
        if j == i:
            return
        parent = self.tree.parent(items[j])
        if parent:
            self.tree.item(parent, open=True)
        self.tree.selection_set(items[j])
        self.tree.see(items[j])

    def _sync_pair_selection(self, view):
        """同じ表か相方の表を出しているほかのペインに、選択範囲をそろえる(比べやすくするため)。"""
        if view is None or view.table is None:
            return
        partner, _ok = self.pair_info(view.table)
        addrs = {view.table.address} | ({partner.address} if partner is not None else set())
        for v in self._all_views():
            if v is not view and v.table is not None and v.table.address in addrs:
                v.set_selection(view.anchor, view.cursor, notify=False, see=False)

    def on_selection(self, view):
        """選択範囲の情報(セル位置・軸の値・平均/最小/最大)をステータスバー右に出す。"""
        ja = self.lang == "ja"
        try:
            if view is None or view.table is None or not view._items:
                self.status_sel.config(text="")
                return
            cells = view.sel_cells()
            vals = [float(view.grid_vals[r][c]) for r, c in cells if tableview.isnum(view.grid_vals[r][c])]
            r0, c0, r1, c1 = view.sel_rect()
            r, c = view.cursor
            if len(cells) <= 1:
                parts = [f"({r + 1},{c + 1})"]
                if view.xvals and c < len(view.xvals):
                    parts.append(f"X={self._disp(view.xvals[c], view.sc)}")
                if view.yvals and r < len(view.yvals):
                    parts.append(f"Y={self._disp(view.yvals[r], view.sc)}")
                parts.append(("値=" if ja else "value=") + self._disp(view.grid_vals[r][c], view.sc))
                txt = "  ".join(parts)
            elif vals:
                txt = ((f"選択 {r1 - r0 + 1}×{c1 - c0 + 1} = {len(cells)}セル  平均 {sum(vals) / len(vals):.5g}"
                        f"  最小 {min(vals):.5g}  最大 {max(vals):.5g}") if ja else
                       (f"{r1 - r0 + 1}x{c1 - c0 + 1} = {len(cells)} cells  avg {sum(vals) / len(vals):.5g}"
                        f"  min {min(vals):.5g}  max {max(vals):.5g}"))
            else:
                txt = ""
            self.status_sel.config(text=txt)
        except (tk.TclError, IndexError, ValueError):
            pass
        self._sync_pair_selection(view)

    def status_note(self, msg, ms=5000):
        """ステータスバーに一時的なお知らせを出す(ms 後に通常表示へ戻す)。"""
        try:
            self.status.config(text=msg, fg="#e2b33a")
        except tk.TclError:
            return
        if getattr(self, "_note_after", None):
            try:
                self.after_cancel(self._note_after)
            except tk.TclError:
                pass

        def back():
            self._note_after = None
            try:
                self.status.config(fg="#9fb0c8")
            except tk.TclError:
                return
            self._update_status()
        self._note_after = self.after(ms, back)

    def _set_option(self, name, val):
        val = bool(val)
        setattr(self, name, val)
        uistate.put("options", {"mirror_pairs": self.mirror_pairs, "show_marks": self.show_marks,
                                "show_desc": self.show_desc})
        var = {"mirror_pairs": "_mv_mirror", "show_marks": "_mv_marks", "show_desc": "_mv_desc"}.get(name)
        if var and hasattr(self, var):
            getattr(self, var).set(val)
        if name == "show_desc":
            if val:
                self.desc.pack(fill="x", padx=4, pady=(2, 4), before=self.view_host)
            else:
                self.desc.pack_forget()
        for v in self._all_views():
            if v.table is not None:
                v.refresh()
        if name == "mirror_pairs":
            ja = self.lang == "ja"
            self.status_note(("ペア同時編集 ON：制御側と監視側の写しへ同じ値を書きます。" if val else
                              "ペア同時編集 OFF：表示中の表だけに書きます（相方との違いは赤い印で出ます）。") if ja else
                             ("Paired editing ON." if val else "Paired editing OFF."))

    def _save_views_soon(self):
        if self._save_views_after is not None:
            try:
                self.after_cancel(self._save_views_after)
            except tk.TclError:
                pass
        self._save_views_after = self.after(800, self._save_views_now)

    def _views_state(self):
        def key(t):
            return {"addr": t.address, "name": t.name} if t is not None else None
        panes = []
        for slot in range(4):
            v = next((x for x in self.views if x.slot == slot), None)
            if v is not None:
                panes.append({"table": key(v.table), "zoom": v.zoom})
            else:
                st = self.pane_state[slot]
                panes.append({"table": key(st.get("table")), "zoom": st.get("zoom", 1.0)})
        floats = []
        for v in self.float_views:
            try:
                if v.table is not None:
                    floats.append({"table": key(v.table), "zoom": v.zoom,
                                   "geometry": v.winfo_toplevel().wm_geometry()})
            except tk.TclError:
                pass
        act = self.active_view
        return {"layout": self.layout, "panes": panes, "floats": floats, "sash": self._sash_fracs(),
                "active": act.slot if (act is not None and act in self.views) else 0}

    def _save_views_now(self):
        self._save_views_after = None
        try:
            uistate.put("views", self._views_state())
        except tk.TclError:
            pass

    def _restore_views(self):
        st = uistate.get("views", {}) or {}
        for i, p in enumerate((st.get("panes") or [])[:4]):
            if isinstance(p, dict):
                self.pane_state[i] = {"table": self._find_table(p.get("table")),
                                      "zoom": float(p.get("zoom", 1.0) or 1.0)}
        mode = st.get("layout", "1")
        self.set_layout(mode if mode in self.LAYOUTS else "1")
        a = st.get("active", 0)
        if isinstance(a, int) and 0 <= a < len(self.views):
            self.set_active(self.views[a])
        for f in st.get("floats") or []:
            t = self._find_table(f.get("table")) if isinstance(f, dict) else None
            if t is not None:
                self.open_float(t, zoom=float(f.get("zoom", 1.0) or 1.0), geometry=f.get("geometry"))
        if st.get("sash"):
            self.after(200, lambda: self._equalize_sashes(st.get("sash")))
        if self.views and self.active_view in self.float_views and len(self.float_views) > 0:
            self.set_active(self.views[0])

    # ---------- ショートカット・操作 ----------
    @staticmethod
    def _view_of(w):
        while w is not None:
            if isinstance(w, tableview.TableView):
                return w
            w = getattr(w, "master", None)
        return None

    def _focus_widget(self):
        try:
            return self.focus_get()
        except (KeyError, tk.TclError):
            return None

    def _on_root_key(self, ev):
        w = self._focus_widget()
        if self.dispatch_key(ev, self._view_of(w), w):
            return "break"
        return None

    def dispatch_key(self, ev, view, w=None) -> bool:
        """キー入力をショートカットの操作に振り分ける。実行したら True。"""
        key = shortcuts.event_to_key(ev, self.altmask)
        if not key:
            return False
        aid = self._keyrev.get(key)
        if not aid:
            return False
        a = shortcuts.BY_ID[aid]
        if w is None:
            w = self._focus_widget()
        in_text = isinstance(w, (tk.Entry, tk.Spinbox, tk.Text, ttk.Entry))
        if a.scope == "table":
            if view is None or in_text:
                return False
        elif in_text and (not a.text_ok or not shortcuts.has_modifier(key)):
            return False
        self.run_action(aid, view)
        return True

    _TABLE_ACTIONS = {a.id for a in shortcuts.ACTIONS if a.scope == "table"}

    def run_action(self, aid, view=None):
        v = view if view is not None else self.active_view
        if v is not None and v.editing:
            v.commit_edit()
        ja = self.lang == "ja"
        glob = {
            "open_rom": self.open_rom, "save": self.save_rom, "save_as": self.save_rom_as,
            "cmp_rom": self.compare_files, "undo": self.undo, "redo": self.redo,
            "axis_edit": self.toggle_axis_edit, "find": self._focus_search,
            "tree_focus": lambda: self.tree.focus_set(), "table_focus": self._focus_active_view,
            "next_table": lambda: self._step_table(1), "prev_table": lambda: self._step_table(-1),
            "layout_1": lambda: self.set_layout("1"), "layout_2h": lambda: self.set_layout("2h"),
            "layout_2v": lambda: self.set_layout("2v"), "layout_3": lambda: self.set_layout("3"),
            "layout_4": lambda: self.set_layout("4"),
            "next_pane": lambda: self._cycle_pane(1), "prev_pane": lambda: self._cycle_pane(-1),
            "show_pair": lambda: v is not None and v.table is not None and self.view_pair(v),
            "detach": lambda: v is not None and self.view_detach(v),
            "close_pane": lambda: v is not None and self.view_close(v),
            "zoom_in": lambda: v is not None and v.set_zoom(v.zoom + 0.1),
            "zoom_out": lambda: v is not None and v.set_zoom(v.zoom - 0.1),
            "zoom_reset": lambda: v is not None and v.set_zoom(1.0),
            "toggle_desc": lambda: self._set_option("show_desc", not self.show_desc),
            "mirror_pairs": lambda: self._set_option("mirror_pairs", not self.mirror_pairs),
            "lang": self.toggle_lang,
            "live": self.toggle_live, "dashboard": self.open_dashboard, "record": self.toggle_record,
            "replay": self.open_replay, "chart": self.open_chart, "live_intervals": self.open_live_intervals,
            "dump": self.dump_ecu, "cmp_ecu": self.compare_ecu, "dtc_clear": self.clear_dtcs_action,
            "help": self.show_help, "shortcuts": self.open_shortcuts,
        }
        if aid in glob:
            glob[aid]()
            if aid in ("zoom_in", "zoom_out", "zoom_reset"):
                self._save_views_soon()
            return
        if aid not in self._TABLE_ACTIONS:
            return
        if v is None or v.table is None or self.rom is None:
            self.status_note("先に表を選んでください。" if ja else "Pick a table first.")
            return
        tv = v
        if aid == "edit_cell":
            tv.begin_edit()
        elif aid in ("inc", "dec", "inc_big", "dec_big"):
            tv.op_delta(1 if aid.startswith("inc") else -1, big=aid.endswith("_big"))
        elif aid in ("set_value", "add_value", "percent", "multiply"):
            self._ask_and_apply(tv, aid)
        elif aid in ("interp_h", "interp_v", "interp_2d"):
            tv.op_interp(aid[7:])
        elif aid == "smooth":
            tv.op_smooth()
        elif aid in ("fill_down", "fill_right"):
            tv.op_fill(down=aid == "fill_down")
        elif aid == "copy":
            tv.copy()
        elif aid == "paste":
            tv.paste()
        elif aid == "revert_sel":
            self.revert_cells(tv)
        elif aid == "copy_to_pair":
            self.copy_to_pair(tv)
        elif aid == "set_step":
            self.open_step_dialog(tv)
        elif aid == "select_all":
            tv.select_all()
        elif aid == "goto_live":
            if not tv.goto_live():
                self.status_note("運転点(●)が出ていません（Live かリプレイ中で、軸が追従できる表のとき）。" if ja
                                 else "No live operating point on this table.")

    def _ask_and_apply(self, tv, kind):
        ja = self.lang == "ja"
        cells = tv.num_cells()
        if not cells:
            return
        n = len(cells)
        cur = tv.grid_vals[tv.cursor[0]][tv.cursor[1]]
        f = (self.jp, 10)
        if kind == "set_value":
            v = tableview.ask_number(self, "値を設定" if ja else "Set value",
                                     (f"選択した {n} セルに入れる値:" if ja else f"Value for the {n} selected cells:"),
                                     self._disp(cur, tv.sc) if tableview.isnum(cur) else "", f)
            if v is not None:
                tv.op_map(lambda _x: v, "値を設定" if ja else "Set value")
        elif kind == "add_value":
            v = tableview.ask_number(self, "値を加算" if ja else "Add",
                                     (f"選択した {n} セルに足す値（負の値で引く）:" if ja else f"Amount to add to {n} cells:"),
                                     "0", f)
            if v is not None:
                tv.op_map(lambda x: x + v, (f"加算 {v:+g}" if ja else f"Add {v:+g}"))
        elif kind == "percent":
            v = tableview.ask_number(self, "％で増減" if ja else "Change by %",
                                     (f"選択した {n} セルを何％変えるか（5 で +5％、-3 で −3％）:" if ja
                                      else f"Percent change for {n} cells (5 = +5 %):"), "0", f)
            if v is not None:
                tv.op_map(lambda x: x * (1.0 + v / 100.0), (f"{v:+g}％" if ja else f"{v:+g} %"))
        elif kind == "multiply":
            v = tableview.ask_number(self, "倍率を掛ける" if ja else "Multiply",
                                     (f"選択した {n} セルに掛ける倍率（例 1.05）:" if ja else f"Factor for {n} cells:"),
                                     "1", f)
            if v is not None:
                tv.op_map(lambda x: x * v, (f"×{v:g}" if ja else f"x{v:g}"))

    def open_step_dialog(self, tv):
        """表ごとの増減幅(小/大)を決める。空欄=自動。"""
        ja = self.lang == "ja"
        t = tv.table
        auto = self._default_steps(t, tv.grid_vals)
        cur = self.steps_for(t, tv.grid_vals)
        top = tk.Toplevel(self)
        top.title("増減幅の設定" if ja else "Increment settings")
        top.configure(bg="#1e2128")
        top.transient(self)
        tk.Label(top, text=((f"{i18n.translate_table_name(t.name)}（0x{t.address:X}）\n"
                             f"［増やす/減らす］で1回に変える量。自動の値は 小 {auto[0]:g} / 大 {auto[1]:g}。")
                            if ja else f"{t.name} (0x{t.address:X})\nAuto: small {auto[0]:g} / large {auto[1]:g}."),
                 bg="#1e2128", fg="#dfe3ea", justify="left", anchor="w", font=(self.jp, 10)
                 ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))
        ents = []
        for i, (lab, val) in enumerate(((("小（＋ / −）" if ja else "Small (+/-)"), cur[0]),
                                        (("大（PgUp / PgDn）" if ja else "Large (PgUp/PgDn)"), cur[1]))):
            tk.Label(top, text=lab, bg="#1e2128", fg="#dfe3ea", font=(self.jp, 10)
                     ).grid(row=i + 1, column=0, sticky="e", padx=(12, 6), pady=3)
            e = tk.Entry(top, width=12)
            e.insert(0, f"{val:g}")
            e.grid(row=i + 1, column=1, sticky="w", padx=(0, 12), pady=3)
            ents.append(e)

        def ok():
            try:
                a, b = float(ents[0].get()), float(ents[1].get())
                if a <= 0 or b <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(top.title(), "正の数を入れてください。" if ja else "Enter positive numbers.",
                                       parent=top)
                return
            self.steps[f"{t.address:X}"] = [a, b]
            uistate.put("steps", self.steps)
            top.destroy()

        def reset():
            self.steps.pop(f"{t.address:X}", None)
            uistate.put("steps", self.steps)
            top.destroy()

        b = tk.Frame(top, bg="#1e2128")
        b.grid(row=3, column=0, columnspan=2, sticky="e", padx=12, pady=(6, 10))
        tk.Button(b, text="自動に戻す" if ja else "Auto", command=reset).pack(side="left", padx=(0, 12))
        tk.Button(b, text="キャンセル" if ja else "Cancel", command=top.destroy).pack(side="right")
        tk.Button(b, text="OK", width=8, command=ok).pack(side="right", padx=(0, 6))
        top.grab_set()

    def open_shortcuts(self):
        def apply(km):
            self.keymap = km
            self._keyrev = shortcuts.reverse(km)
            uistate.put("shortcuts", shortcuts.overrides_of(km))
            self._build_menus()
            self.status_note("ショートカットキーを保存しました。" if self.lang == "ja" else "Shortcuts saved.")
        shortcuts.ShortcutDialog(self, self.keymap, self.lang, apply, font=(self.jp, 9))

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
        except (AttributeError, tk.TclError):
            pass

    def view_context_menu(self, view, ev):
        """表の右クリックメニュー(ショートカットキー付き)。"""
        ja = self.lang == "ja"
        m = self._new_menu()
        for aid in ("set_value", "add_value", "percent", "multiply"):
            self._act_item(m, aid)
        m.add_separator()
        for aid in ("inc", "dec", "inc_big", "dec_big"):
            self._act_item(m, aid)
        m.add_separator()
        for aid in ("interp_h", "interp_v", "interp_2d", "smooth", "fill_down", "fill_right"):
            self._act_item(m, aid)
        m.add_separator()
        for aid in ("copy", "paste", "select_all", "revert_sel"):
            self._act_item(m, aid)
        partner, ok = self.pair_info(view.table)
        if partner is not None:
            m.add_separator()
            self._act_item(m, "show_pair")
            if ok:
                self._act_item(m, "copy_to_pair")
        m.add_separator()
        if view.slot != "float":
            self._act_item(m, "detach")
        self._act_item(m, "set_step")
        self._act_item(m, "goto_live")
        self._popup_menu(m, ev.x_root, ev.y_root, ev.widget)

    def _new_menu(self):
        """右クリックメニューの入れ物。X11(WSLg)ではウィンドウの中に描く InlineMenu、Windows では tk.Menu。
        WSLg の tk.Menu は別ウィンドウとして描かれ、外側を押すと一度消えて再び現れ、閉じても約1秒残る
        (2026-11-18 にコマ撮りで確認。ncec_popup.py の説明)。"""
        try:
            x11 = self.tk.call("tk", "windowingsystem") == "x11"
        except tk.TclError:
            x11 = False
        return popup.InlineMenu(self, font=(self.jp, 10)) if x11 else tk.Menu(self, tearoff=0)

    def _popup_menu(self, m, x, y, widget=None):
        """右クリックメニューを出す。tk.Menu では tk_popup の直後に grab_release しないこと:
        X11(WSLg)では外側クリックがメニューに届かず、メニューは閉じないまま(見えなくなるだけで出たまま)になり、
        カーソルを元の場所へ戻すと再び現れる(2026-11-18、XTest の実クリックで再現・確認)。
        前に出したメニューは閉じて壊してから出す(出たままの古いメニューを残さない)。"""
        old = getattr(self, "_ctx_menu", None)
        if old is not None and old is not m:
            try:
                old.unpost()
                old.destroy()
            except tk.TclError:
                pass
        if isinstance(m, popup.InlineMenu):
            if m.post(x, y, widget):
                self._ctx_menu = m
                return
            m = popup.native_from(m, self)      # ウィンドウに収まらない(小さな別ウィンドウ)ときだけ通常のメニュー
        self._ctx_menu = m
        m.tk_popup(x, y)

    def _tree_context(self, ev):
        """一覧の右クリック: どのペインに出すか・別ウィンドウ・相方と並べる。"""
        iid = self.tree.identify_row(ev.y)
        if not iid:
            return
        vals = self.tree.item(iid, "values")
        if not vals or not self.romdef:
            return
        t = self.romdef.tables[int(vals[0])]
        ja = self.lang == "ja"
        m = self._new_menu()
        for v in self.views:
            m.add_command(label=(f"ペイン{v.slot + 1}に表示" if ja else f"Show in pane {v.slot + 1}"),
                          command=lambda v=v: self.open_table(t, v))
        m.add_command(label="別ウィンドウで開く" if ja else "Open in a separate window",
                      command=lambda: self.open_float(t))
        partner, _ok = self.pair_info(t)
        if partner is not None:
            m.add_separator()
            m.add_command(label=("相方（制御⇔監視）と並べて表示" if ja else "Show with its paired table"),
                          command=lambda: self._open_with_pair(t))
        self._popup_menu(m, ev.x_root, ev.y_root, ev.widget)

    # ---------- A/D 値の表の ℃ 換算(電動ファンの水温しきい値) ----------
    def _axis_ram_text(self, t):
        """軸の入力に入る RAM 変数(この ROM の実番地)。ROM のコードから求めた ncecu/axis_ram.py による。"""
        names = (("X", t.x_axis), ("Y", t.y_axis)) if t.ttype == "3D" else (("", t.x_axis or t.y_axis),)
        out = []
        for role, ax in names:
            if not ax:
                continue
            rams = axis_ram.inputs(t.address, ax.address)
            if rams:
                out.append((role + "=" if role else "") + " / ".join(f"0x{r:08X}" for r in rams))
        if not out:
            return ""
        head = "● 軸の入力 RAM(ROM のコードで確認)" if self.lang == "ja" else "● Axis input RAM (checked in the ROM code)"
        return f"{head}: " + "　".join(out)

    def _conv_text(self, t, grid=None):
        """説明欄に出す換算(現在値の ℃・式・目安表、またはカウント→秒、増量%→λ)。"""
        try:
            if grid is None:
                grid = self.rom.read_table(t)
            vals = [v for row in grid for v in row]
            if convhint.applies(t.name):
                return convhint.describe(t.name, vals, self.lang)
            partner = None
            pn = ectcount.partner_name(t.name)
            pt = next((x for x in self.romdef.tables if x.name == pn), None) if pn else None
            if pt is not None:
                partner = [v for row in self.rom.read_table(pt) for v in row]
            return ectcount.describe(t.name, vals, ectcount.curve_from(self.rom, self.romdef),
                                     self.lang, partner)
        except Exception as e:          # 換算は補助表示。失敗しても表の編集は止めない
            return f"● 換算: 表示できません ({e})"

    def _refresh_conv(self):
        """セル編集のあと、説明欄の換算行を今の値で差し替える。換算を出さない表では何もしない。"""
        idx, parts = getattr(self, "_conv_idx", None), getattr(self, "_desc_parts", None)
        if idx is None or not parts or idx >= len(parts) or not self.cur_table:
            return
        parts[idx] = self._conv_text(self.cur_table)
        self.desc.config(text="\n".join(parts))

    def toggle_axis_edit(self):
        if not self.axis_edit:
            if not messagebox.askyesno(i18n.ui("axis_edit_warn_title"), i18n.ui("axis_edit_warn")):
                return
        self.axis_edit = not self.axis_edit
        self.axis_btn.config(
            text=i18n.ui("axis_edit_on" if self.axis_edit else "axis_edit_off"),
            bg=("#b5651d" if self.axis_edit else self._btn_face),
            fg=("#ffffff" if self.axis_edit else self._btn_fg))
        for v in self._all_views():
            v.redraw()
        if self.axis_edit:
            self.status_note("軸編集 ON：軸の見出しをダブルクリックすると値を変えられます。" if self.lang == "ja"
                             else "Axis edit ON: double-click an axis header to edit it.")

    # ---------- save ----------
    def save_rom(self):
        if not self.rom_path:
            return self.save_rom_as()
        self._do_save(self.rom_path)

    def save_rom_as(self):
        if not self.rom:
            return
        p = filedialog.asksaveasfilename(defaultextension=".bin", initialdir=_rom_dir(),
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
        self.orig_data = bytes(data)          # 変えたセルの印・元に戻す の基準を保存した内容に
        for v in self._all_views():
            if v.table is not None:
                v.refresh()
        self._update_status()
        messagebox.showinfo("保存完了",
                            f"保存しました:\n{path}\n\nチェックサム再計算: {nch} 領域更新")

    # ---------- フラットシフト点火リタード・パッチ ----------
    def apply_flatshift(self):
        """フラットシフト・パッチ(第6ドラフト=スクラッチ無し・読み取り専用, ncecu/flatshift.py)を
        メモリ上の ROM に当てる。方式(点火遅角/本物の点火カット)・ゲート(クラッチ+回転+アクセル+車速)・
        デバッグtest_modeをダイアログで指定(ms窓/スクラッチRAMは廃止)。
        ファイルは保存するまで変わらない(保存時にチェックサム自動補正)。"""
        if not self.rom:
            return
        ja = self.lang == "ja"
        title = i18n.ui("fs_title")
        data = self.rom.bytes_out()
        if flatshift.is_applied(data):
            messagebox.showinfo(title, i18n.ui("fs_already"))
            self._reveal_category(flatshift.PATCH_CATEGORY)
            return
        if not flatshift.can_apply(data):
            messagebox.showerror(title, i18n.ui("fs_unsupported").format(
                err=f"@0x{flatshift.CLAMP_LIT:X}/@0x{flatshift.HANDLER_PTR:X} / cave @0x{flatshift.CAVE:X}"))
            return
        vals = self._pick_flatshift()
        if not vals:
            return
        try:
            new = flatshift.build(data, **vals)
        except ValueError as e:
            messagebox.showerror(title, i18n.ui("fs_unsupported").format(err=e))
            return
        self._set_rom(bytes(new), record=True)
        self.modified = True
        self._populate_tree()
        self._update_status()
        self._reveal_category(flatshift.PATCH_CATEGORY)
        self._show_patch_result(
            ("フラットシフト（点火カット/遅角）" if ja else "Flat shift (ignition cut/retard)"),
            self._flatshift_changes(vals))

    def _pick_flatshift(self):
        """方式・ゲート・test_mode を入力。build(**vals) 用 dict または None。"""
        ja = self.lang == "ja"
        d = flatshift.DEFAULTS
        top = tk.Toplevel(self)
        top.title(i18n.ui("fs_title"))
        top.configure(bg="#1e2128")
        top.transient(self)
        top.grab_set()
        tk.Label(top, text=("クラッチ踏込 かつ 回転>しきい値 かつ アクセル>しきい値 かつ 車速>下限 の間だけ発動します"
                            "（RAMに一切書き込まない読み取り専用設計。窓時間はクラッチを踏んでいる長さ＝回転しきい値が上限)。"
                            if ja else
                            "Acts while clutch pressed AND RPM>threshold AND APP>threshold AND speed>minimum "
                            "(read-only, no RAM writes; the clutch dip is the window, RPM threshold caps it)."),
                 bg="#1e2128", fg="#dfe3ea", wraplength=560, justify="left", anchor="w",
                 font=(self.jp, 10)).pack(fill="x", padx=12, pady=(10, 6))
        mvar = tk.IntVar(value=int(d["method"]))
        mfrm = tk.Frame(top, bg="#1e2128")
        mfrm.pack(fill="x", padx=12, pady=(0, 4))
        for val, lab in ((0, ("点火遅角（最終進角から遅角量を引く。下限まで深く引ける＝大遅角もこれで調整）"
                              if ja else "Ignition retard (subtract degrees, down to the floor = also big retard)")),
                         (1, ("点火カット（本物のスパーク停止。発動中コイル通電を止める＝火花なし）"
                              if ja else "Ignition cut (true spark stop: suppress coil charge while active)"))):
            tk.Radiobutton(mfrm, text=lab, variable=mvar, value=val,
                           bg="#1e2128", fg="#dfe3ea", selectcolor="#2b3340",
                           activebackground="#1e2128", activeforeground="#ffffff",
                           wraplength=540, justify="left", anchor="w", font=(self.jp, 10)
                           ).pack(fill="x", anchor="w")
        grid = tk.Frame(top, bg="#1e2128")
        grid.pack(fill="x", padx=12, pady=(2, 2))
        rows = [
            ("rpm", ("回転しきい値 [rpm]" if ja else "RPM threshold")),
            ("app", ("アクセルしきい値 [%]" if ja else "APP threshold [%]")),
            ("vss", ("車速下限 [km/h]" if ja else "vehicle speed minimum [km/h]")),
            ("retard", ("遅角量 [deg]（遅角方式）" if ja else "retard amount [deg] (retard method)")),
            ("floor", ("下限=最小進角 [deg]（遅角方式。負=ATDC）" if ja else "min advance floor [deg] (retard; neg=ATDC)")),
        ]
        ents = {}
        for i, (key, lab) in enumerate(rows):
            tk.Label(grid, text=lab, bg="#1e2128", fg="#dfe3ea", anchor="w", font=(self.jp, 10)
                     ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=2)
            e = tk.Entry(grid, width=9)
            e.insert(0, f"{d[key]:g}")
            e.grid(row=i, column=1, sticky="w", pady=2)
            ents[key] = e
        tvar = tk.IntVar(value=int(d["test_mode"]))
        tk.Checkbutton(top, variable=tvar,
                       text=("デバッグ test_mode（停車確認用：車速ゲートだけ無視しクラッチ＋回転＋アクセルで発動。始動/アイドルは不発＝始動を妨げない。停車Nで回転を上げると発動。走行時は必ずOFF）"
                             if ja else
                             "Debug test_mode (standstill check: ignore only the speed gate; clutch+RPM+APP still required, so it won't fire at idle/cranking. Rev in neutral to trigger. OFF to drive)"),
                       bg="#1e2128", fg="#e2b33a", selectcolor="#2b3340",
                       activebackground="#1e2128", activeforeground="#ffffff",
                       wraplength=540, justify="left", anchor="w", font=(self.jp, 9)
                       ).pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(top, text=("⚠ 点火カットは生ガスを排気へ＝バックファイア/高EGT。短いクラッチ操作で。**本物のカットが効くか・"
                            "コイル過熱しないかは実車でのみ確認**（タイミングライト＋電圧。tools/flatshift_debug.py）。まずベンチ/予備ECUで。"
                            if ja else
                            "WARN: ignition cut dumps raw fuel to exhaust = backfire/high EGT. Keep clutch dips short. The cut and "
                            "coil-overheat safety are ONLY confirmable on-car (timing light + voltage; tools/flatshift_debug.py). Bench ECU first."),
                 bg="#1e2128", fg="#e2b33a", wraplength=560, justify="left", anchor="w",
                 font=(self.jp, 9)).pack(fill="x", padx=12, pady=(4, 4))
        result = {"v": None}

        def ok():
            try:
                vals = {"method": mvar.get(), "test_mode": tvar.get()}
                for key, _lab in rows:
                    vals[key] = float(ents[key].get())
                flatshift.check_values(**{**flatshift.DEFAULTS, **vals})
            except ValueError as e:
                messagebox.showwarning(top.title(), str(e))
                return
            result["v"] = vals
            top.destroy()

        btns = tk.Frame(top, bg="#1e2128")
        btns.pack(fill="x", padx=12, pady=(4, 10))
        tk.Button(btns, text=("適用" if ja else "Apply"), command=ok).pack(side="right")
        tk.Button(btns, text=("キャンセル" if ja else "Cancel"),
                  command=top.destroy).pack(side="right", padx=(0, 6))
        self.wait_window(top)
        return result["v"]

    def _flatshift_changes(self, vals):
        """フラットシフト適用のリザルト用リスト。"""
        ja = self.lang == "ja"
        v = {**flatshift.DEFAULTS, **vals}
        method = int(v["method"])
        mname = (("本物の点火カット" if method else "点火遅角") if ja
                 else ("True ignition cut" if method else "Retard"))
        out = [
            {"name": ("注入点1：最終進角クランプ呼び出し" if ja else "Injection 1: final-advance clamp call"),
             "addr": flatshift.CLAMP_LIT,
             "before": f"0x{flatshift.CLAMP_FUNC:08X}", "after": f"0x{flatshift.CAVE:08X} (cave1)", "changed": True},
            {"name": ("注入点2：コイル充電ハンドラ（カット用）" if ja else "Injection 2: coil-charge handler (cut)"),
             "addr": flatshift.HANDLER_PTR,
             "before": f"0x{flatshift.H19D04:08X}", "after": f"0x{flatshift.CAVE2:08X} (cave2)", "changed": True},
            {"name": ("方式" if ja else "Method"), "addr": flatshift.CAL_ADDRS["method"],
             "before": "-", "after": f"{method} = {mname}", "changed": True},
            {"name": ("発動条件＝ゲート（クラッチ＋回転/アクセル/車速。窓なし・RAM非書込）"
                      if ja else "Trigger = gates (clutch + RPM/APP/VSS; no window, no RAM writes)"),
             "addr": flatshift.CAL_ADDRS["rpm"], "before": "-",
             "after": f"クラッチ かつ RPM>{v['rpm']:g} / APP>{v['app']:g}% / {v['vss']:g}km/h", "changed": True},
            {"name": (("遅角量 / 下限" if method == 0 else "カット＝コイル充電スキップ（進角は不変）") if ja
                      else ("Retard / floor" if method == 0 else "Cut = skip coil charge (advance unchanged)")),
             "addr": (flatshift.CAL_ADDRS["retard"] if method == 0 else flatshift.CAL_ADDRS["method"]),
             "before": "-",
             "after": (f"{v['retard']:g} / 下限{v['floor']:g} deg" if method == 0
                       else ("充電ハンドラ0x19D04をスキップ" if ja else "skip charge handler 0x19D04")),
             "changed": True},
            {"name": ("デバッグ test_mode" if ja else "Debug test_mode"),
             "addr": flatshift.CAL_ADDRS["test_mode"], "before": "-",
             "after": (("ON（停車確認用・走行前にOFFへ）" if ja else "ON (standstill check; set OFF to drive)")
                       if int(v["test_mode"]) else ("OFF（通常）" if ja else "OFF (normal)")),
             "changed": True},
        ]
        return out

    # ---------- アンチラグ(オーバーランのポップ) ----------
    def apply_antilag(self):
        """アクセルオフ時のアンチラグ(オーバーランのポップ)パッチを当てる(ncecu/antilag.py)。
        パターン A/B/C/D を選択。B・C は有効回転数を指定できる。
        メモリ上の ROM だけ変更(保存時にチェックサム自動補正)。"""
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
        opt = self._pick_antilag()
        if not opt:
            return
        pat, gate = opt
        try:
            new, changes = antilag.build(data, pat, gate_rpm=gate)
        except ValueError as e:
            messagebox.showerror(title, str(e))
            return
        self._set_rom(bytes(new), record=True)
        self.modified = True
        self._populate_tree()
        self._update_status()
        name = antilag.PATTERN_NAME[pat][0 if ja else 1]
        if pat in antilag.GATED:
            name += (f"・有効回転数 {gate}rpm〜" if ja else f", active above {gate} rpm")
        self._show_patch_result(
            (f"アンチラグ パターン{pat}: {name}" if ja else f"Anti-lag {pat}: {name}"), changes)

    def _pick_antilag(self):
        """A/B/C/D と有効回転数(B・C)を選ぶダイアログ。(パターン, 有効回転数) または None を返す。"""
        ja = self.lang == "ja"
        top = tk.Toplevel(self)
        top.title("アンチラグ" if ja else "Anti-lag")
        top.configure(bg="#1e2128")
        top.transient(self)
        top.grab_set()
        w = antilag.GATE_WIDTH
        desc = {
            "A": ("A. DFCO無効（全回転バーブル）\n一番簡単。減速燃料カットを常時オフ＋減速点火を深く遅角(22°)。低回転でも鳴る/燃費悪化/踏み直しの穴が深い。",
                  "A. DFCO off (burble at all RPM)\nSimplest. Always-on fuel + deep decel retard (22deg)."),
            "B": ("B. RPMゲート ★おすすめ\nDFCOは有効のまま、有効回転数より上だけ燃料を残してポップ。下は無音で通常の燃料カット。遅角20°。",
                  "B. RPM gate (recommended)\nDFCO stays on; fuel kept only above the active rpm. 20deg retard."),
            "C": ("C. RPMゲート＋ツキ重視（DFCO有効のまま）\nBと同じくDFCO有効・有効回転数より上だけ。遅角を浅く(12°)＋点火/燃料の復帰を速くして、踏み直しのツキを優先。ポップは控えめ。",
                  "C. RPM gate + response-focused (DFCO stays on)\nLike B (DFCO on, above the active rpm), with shallow retard (12deg) and fast spark/fuel restore."),
            "D": ("D. ツキ重視・DFCO無効（v2.70までのC）\n遅角を浅く(12°)＋点火/燃料の復帰を速く＋DFCO無効(全回転で燃料が残る)。",
                  "D. Response-focused, DFCO off (C up to v2.70)\nShallow retard, fast restore, DFCO off."),
        }
        tk.Label(top, text=("有効化の方法を選択してください:" if ja else "Choose how to enable:"),
                 bg="#1e2128", fg="#dfe3ea", font=(self.jp, 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=12, pady=(10, 4))
        var = tk.StringVar(value="B")
        for k in antilag.PATTERNS:
            tk.Radiobutton(top, text=desc[k][0 if ja else 1], variable=var, value=k,
                           bg="#1e2128", fg="#dfe3ea", selectcolor="#2b3340",
                           activebackground="#1e2128", activeforeground="#ffffff",
                           wraplength=580, justify="left", anchor="w", font=(self.jp, 10),
                           command=lambda: sync()).pack(fill="x", padx=16, pady=3)
        lo, hi = antilag.GATE_LIMITS
        row = tk.Frame(top, bg="#1e2128")
        row.pack(fill="x", padx=16, pady=(8, 0))
        gate_lbl = tk.Label(row, text=("アンチラグ有効回転数 [rpm]（B・C）:" if ja else "Active rpm (B, C):"),
                            bg="#1e2128", fg="#dfe3ea", font=(self.jp, 10))
        gate_lbl.pack(side="left")
        gate_var = tk.StringVar(value=str(antilag.GATE_DEFAULT))
        gate_ent = tk.Spinbox(row, from_=lo, to=hi, increment=antilag.GATE_STEP, width=7,
                              textvariable=gate_var)
        gate_ent.pack(side="left", padx=(6, 0))
        gate_note = tk.Label(top, bg="#1e2128", fg="#b9c6da", wraplength=580, justify="left",
                             anchor="w", font=(self.jp, 9))
        gate_note.pack(fill="x", padx=16, pady=(2, 0))

        def note_text():
            try:
                g = int(float(gate_var.get()))
            except ValueError:
                g = None
            rng = f"{lo}〜{hi}rpm・{antilag.GATE_STEP}rpm刻み" if ja else f"{lo}-{hi} rpm, step {antilag.GATE_STEP}"
            if g is None:
                return rng
            return ((f"{g}rpm 以下は無音（通常の燃料カット）。{g}rpm を超えると効き始め、{g + w}rpm で完全に有効。"
                     f"設定範囲 {rng}。既定 {antilag.GATE_DEFAULT}rpm は純正の回転軸のまま。")
                    if ja else
                    (f"Silent up to {g} rpm; ramps in above it; fully active at {g + w} rpm. Range {rng}. "
                     f"Default {antilag.GATE_DEFAULT} keeps the stock RPM axis."))

        def sync(*_a):
            on = var.get() in antilag.GATED
            gate_ent.config(state=("normal" if on else "disabled"))
            gate_lbl.config(fg=("#dfe3ea" if on else "#6b7684"))
            gate_note.config(text=(note_text() if on else
                                   ("（A・D は全回転で有効＝有効回転数の設定はありません）" if ja
                                    else "(A and D are active at all RPM; no active-rpm setting)")))

        gate_var.trace_add("write", sync)
        sync()
        tk.Label(top, text=("⚠ 排気管内で燃料を燃やします＝触媒・排気系の熱害。純正触媒/マフラー車の常用は非推奨。予備/ベンチECUで。公道・騒音・排ガスは自己責任。"
                            if ja else
                            "WARN: burns fuel in the exhaust = heat damage to cat/exhaust. Bench/spare ECU; your responsibility on road."),
                 bg="#1e2128", fg="#e2b33a", wraplength=580, justify="left", anchor="w",
                 font=(self.jp, 9)).pack(fill="x", padx=12, pady=(8, 4))
        result = {"v": None}

        def ok():
            pat = var.get()
            gate = antilag.GATE_DEFAULT
            if pat in antilag.GATED:
                try:
                    gate = antilag.check_gate(gate_var.get())
                except ValueError as e:
                    messagebox.showerror(top.title(), str(e), parent=top)
                    return
            result["v"] = (pat, gate)
            top.destroy()

        btns = tk.Frame(top, bg="#1e2128")
        btns.pack(fill="x", padx=12, pady=(4, 10))
        tk.Button(btns, text=("適用" if ja else "Apply"), command=ok).pack(side="right")
        tk.Button(btns, text=("キャンセル" if ja else "Cancel"),
                  command=top.destroy).pack(side="right", padx=(0, 6))
        self.wait_window(top)
        return result["v"]

    # ---------- 回転落ち高速化(レブハング低減) ----------
    def apply_revdrop(self):
        """シフトアップ時の回転落ちを速くする(DFCO=減速燃料カットを早く・強く)。燃料側のみで
        電子スロットルは触らない=監視安全(ncecu/revdrop.py)。メモリ上のROMだけ変更(保存時に
        チェックサム自動補正)。"""
        if not self.rom:
            return
        ja = self.lang == "ja"
        title = "回転落ち高速化" if ja else "Faster rev drop"
        data = self.rom.bytes_out()
        try:
            revdrop.verify_base(data)
        except ValueError as e:
            messagebox.showerror(title, (f"このROMには適用できません:\n{e}" if ja
                                         else f"Cannot apply to this ROM:\n{e}"))
            return
        opt = self._pick_revdrop()
        if not opt:
            return
        try:
            new, changes = revdrop.build(data, enter_count=opt["enter_count"],
                                         enlean_scale=opt["enlean_scale"])
        except (ValueError, AssertionError) as e:
            messagebox.showerror(title, str(e))
            return
        self._set_rom(bytes(new), record=True)
        self.modified = True
        self._populate_tree()
        self._update_status()
        self._show_patch_result(
            (f"回転落ち高速化（突入カウント={opt['enter_count']} / カット率×{opt['enlean_scale']:g}）" if ja
             else f"Faster rev drop (enter count={opt['enter_count']} / enlean x{opt['enlean_scale']:g})"),
            changes)

    def _pick_revdrop(self):
        """プリセット/個別値を入力。{'enter_count':int,'enlean_scale':float} または None。"""
        ja = self.lang == "ja"
        top = tk.Toplevel(self)
        top.title("回転落ち高速化" if ja else "Faster rev drop")
        top.configure(bg="#1e2128")
        top.transient(self)
        top.grab_set()
        tk.Label(top, text=("アクセルを戻した瞬間に減速燃料カット(DFCO)を早く・強く効かせ、シフトアップ時の"
                            "回転落ちを速くします（燃料側のみ・スロットルは不変＝E-Gas監視と無関係）。"
                            "失速防止の下限(2312.5rpm)と燃料復帰判定は変更しません。"
                            if ja else
                            "Make decel fuel cut (DFCO) engage sooner/harder on lift for a faster rev drop on "
                            "upshift (fuel-side only, throttle untouched = independent of E-Gas monitor). "
                            "The anti-stall RPM floor and fuel-restore logic are left stock."),
                 bg="#1e2128", fg="#dfe3ea", wraplength=560, justify="left", anchor="w",
                 font=(self.jp, 10)).pack(fill="x", padx=12, pady=(10, 6))

        pvar = tk.StringVar(value="mild")
        presets = [
            ("off", ("純正に戻す（inert＝変更なし）" if ja else "Stock (inert, no change)")),
            ("mild", ("穏やか（突入8/カット率×2）★おすすめ" if ja else "Mild (enter 8 / x2) - recommended")),
            ("strong", ("強め（突入3/カット率×3）" if ja else "Strong (enter 3 / x3)")),
            ("custom", ("個別指定（下の数値を使う）" if ja else "Custom (use the values below)")),
        ]
        pf = tk.Frame(top, bg="#1e2128")
        pf.pack(fill="x", padx=16, pady=(0, 4))
        for val, lab in presets:
            tk.Radiobutton(pf, text=lab, variable=pvar, value=val,
                           bg="#1e2128", fg="#dfe3ea", selectcolor="#2b3340",
                           activebackground="#1e2128", activeforeground="#ffffff",
                           wraplength=540, justify="left", anchor="w", font=(self.jp, 10)
                           ).pack(fill="x", anchor="w")

        grid = tk.Frame(top, bg="#1e2128")
        grid.pack(fill="x", padx=16, pady=(2, 2))
        lo_c, hi_c = revdrop.COUNT_LIMITS
        lo_s, hi_s = revdrop.SCALE_LIMITS
        rows = [("突入カウント（{}〜{}・小=速い）".format(lo_c, hi_c) if ja
                 else f"enter count ({lo_c}-{hi_c}, low=sooner)", "8"),
                ("カット率倍率（{:g}〜{:g}・大=速い）".format(lo_s, hi_s) if ja
                 else f"enlean scale ({lo_s:g}-{hi_s:g}, high=faster)", "2.0")]
        ents = []
        for i, (lab, dv) in enumerate(rows):
            tk.Label(grid, text=lab, bg="#1e2128", fg="#dfe3ea", anchor="w", font=(self.jp, 10)
                     ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=3)
            e = tk.Entry(grid, width=8)
            e.insert(0, dv)
            e.grid(row=i, column=1, sticky="w", pady=3)
            ents.append(e)

        tk.Label(top, text=("⚠ 速くしすぎるとシフトがガクつく/低回転で息つき感。停車→低速の順に段階的に確認を。"
                            "予備/ベンチECU専用。実車フラッシュは別途・明示確認のうえで。"
                            if ja else
                            "WARN: too aggressive = jerky shifts / low-rpm stumble. Test staged (idle->low speed). "
                            "Bench/spare ECU only; flashing a real car is a separate, explicit step."),
                 bg="#1e2128", fg="#e2b33a", wraplength=560, justify="left", anchor="w",
                 font=(self.jp, 9)).pack(fill="x", padx=12, pady=(8, 4))
        result = {"v": None}

        def ok():
            name = pvar.get()
            if name == "custom":
                try:
                    ec = int(ents[0].get())
                    sc = float(ents[1].get())
                except ValueError:
                    messagebox.showerror(top.title(), "数値を入力してください" if ja else "Enter numbers")
                    return
            else:
                p = revdrop.preset(name)
                ec, sc = p["enter_count"], p["enlean_scale"]
            try:
                revdrop.check_params(ec, sc)
            except ValueError as e:
                messagebox.showerror(top.title(), str(e))
                return
            result["v"] = {"enter_count": ec, "enlean_scale": sc}
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
        self._set_rom(bytes(new), record=True)
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
    def _sync_follow(self):
        """表示中マップの軸ロール(RPM/負荷/水温/APP…)を LiveReader に伝える。
        MAP追従(●)に必要な信号は、間引き設定が「無視」や遅い値でも読ませるため。"""
        lr = self.live_reader
        if lr is None:
            return
        roles = set()
        for v in self._all_views():          # 表示中のすべてのペイン(別ウィンドウ含む)の軸
            t = v.table
            if t is None:
                continue
            for ax in (t.x_axis, t.y_axis):
                r = livelog.axis_role(ax.name) if ax is not None else None
                if r:
                    roles.add(r)
        lr.set_follow_roles(roles)

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
            self._sync_follow()
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
            self.live_btn.config(text=i18n.ui("live_on"), bg=self._btn_face, fg=self._btn_fg)
        except tk.TclError:
            pass

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
        """現在の運転点に ● を重ね描き(表示中のすべてのペイン)。連続インデックスで
        セル間も滑らかに移動する。"""
        if not self.rom:
            return
        for v in self._all_views():
            t = v.table
            if t is None or not v._items:
                continue
            rows, cols = v.rows, v.cols
            col_f = self._axis_pos_f(t.x_axis, roles, cols, v.xvals)
            row_f = self._axis_pos_f(t.y_axis, roles, rows, v.yvals)
            if col_f is None and cols == 1:
                col_f = 0.0
            if row_f is None and rows == 1:
                row_f = 0.0
            if row_f is None or col_f is None:
                v.set_live(None, None)
                continue
            v.set_live(max(0.0, min(rows - 1, row_f)), max(0.0, min(cols - 1, col_f)))

    # ライブ値(OBD)の取り得る範囲(ロール別)。軸範囲と重ならなければ別量の軸=追従しない。
    _LIVE_RANGE = {"RPM": (0, 9000), "LOAD": (0, 100), "ECT": (-45, 160), "IAT": (-45, 160),
                   "APP": (0, 100), "TP": (0, 100), "MAP": (0, 260), "MAF": (0, 660),
                   "VSS": (0, 260)}

    def _axis_pos_f(self, axis, roles: dict, n: int, vals=None):
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
            src = vals if vals is not None else self.rom.read_axis(axis)
            vals = [x for x in src[:n]
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
        for v in self._all_views():
            v.set_live(None, None)

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
            self.record_btn.config(text="記録 ●", bg=self._btn_face, fg=self._btn_fg)
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
        roles = livelog.roles_from_pids(by_pid)        # ライブと同じロール付け(負荷=0x43, APP=正規化)
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
    # ---------- DTCクリア(OBD Mode04) ----------
    def clear_dtcs_action(self):
        """故障コード(DTC)を消去する。Live中はポーリングスレッド経由、停止中は専用バスで実行。"""
        if not messagebox.askyesno(i18n.ui("dtc_title"), i18n.ui("dtc_confirm")):
            return
        if self.live_reader is not None:
            res = self.live_reader.clear_dtcs()
            self._report_dtc_clear(res, None, None)
            return
        self._run_dtc_clear_offline()

    def _report_dtc_clear(self, res, before, after):
        ja = (self.lang == "ja")
        none = "なし" if ja else "none"
        kind, payload = res
        title = i18n.ui("dtc_title")
        if kind == "ok" and payload and payload[0] == 0x44:
            msg = i18n.ui("dtc_ok")
            if before is not None:
                msg += "\n\n" + i18n.ui("dtc_before_after").format(
                    before=(" ".join(before) if before else none),
                    after=(none if after is None else (" ".join(after) or none)))
            messagebox.showinfo(title, msg)
        elif kind == "ok":
            r = payload.hex(" ") if payload else "(0)"
            messagebox.showwarning(title, i18n.ui("dtc_nak").format(resp=r))
        elif kind == "timeout":
            messagebox.showwarning(title, i18n.ui("dtc_timeout"))
        else:
            messagebox.showerror(title, i18n.ui("dtc_err").format(err=payload))

    def _run_dtc_clear_offline(self):
        """Live停止中: 専用バスを開いて消去前後のDTCを読みつつ Mode04 を送る(flashと同じ接続手順)。"""
        def work():
            from ncecu.canbus import close_bus, open_bus
            from ncecu.diag import DiagClient
            from ncecu.isotp import IsoTp
            from ncecu.livelog import read_dtcs
            bus = None
            before = after = None
            try:
                bus = open_bus()
                diag = DiagClient(IsoTp(bus))
                try:
                    before = [c for c, _ in read_dtcs(diag)]
                except Exception:  # noqa: BLE001
                    before = None
                try:
                    resp = diag.request(b"\x04", timeout=1.5)
                    res = ("ok", resp)
                except Exception as e:  # noqa: BLE001
                    res = ("err", e)
                if res[0] == "ok" and res[1] and res[1][0] == 0x44:
                    try:
                        after = [c for c, _ in read_dtcs(diag)]
                    except Exception:  # noqa: BLE001
                        after = None
            except Exception as e:  # noqa: BLE001
                res = ("err", e)
            finally:
                try:
                    close_bus(bus)
                except Exception:  # noqa: BLE001
                    pass
            self.after(0, lambda: self._report_dtc_clear(res, before, after))
        threading.Thread(target=work, daemon=True).start()

    def open_can_connect(self):
        """WSL2/socketcan の接続状態を表示し、GUIから再接続(attach + can0 up)できるダイアログ。

        ランチャー(NCEC_Editor_WSL.bat)が起動時に接続済みだが、USBを挿し直した/can0 が
        落ちた場合に、端末へ戻らず GUI だけで復旧するためのもの(wslcan.reconnect)。
        """
        win = tk.Toplevel(self)
        win.title(i18n.ui("can_title"))
        win.configure(bg="#1e2128")
        win.geometry("700x380")
        txt = tk.Text(win, bg="#11131a", fg="#d8e0ea", font=(self.mono, 9), relief="flat")
        txt.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        bar = tk.Frame(win, bg="#1e2128")
        bar.pack(fill="x", padx=6, pady=6)

        def render(extra=""):
            try:
                txt.delete("1.0", "end")
                body = wslcan.summary() + "\n\n" + i18n.ui("can_hint")
                if extra:
                    body += "\n\n--- reconnect ---\n" + extra
                txt.insert("end", body)
                txt.see("end")
            except tk.TclError:
                pass

        def do_reconnect():
            recon_btn.config(state="disabled", text=i18n.ui("can_reconnecting"))

            def work():
                _ok, log = wslcan.reconnect()
                self.after(0, lambda: (render(log),
                                       recon_btn.config(state="normal",
                                                        text=i18n.ui("can_reconnect"))))
            threading.Thread(target=work, daemon=True).start()

        recon_btn = tk.Button(bar, text=i18n.ui("can_reconnect"), command=do_reconnect)
        recon_btn.pack(side="left")
        tk.Button(bar, text=i18n.ui("can_refresh"),
                  command=lambda: render()).pack(side="left", padx=6)
        tk.Button(bar, text=i18n.ui("can_close"), command=win.destroy).pack(side="right")
        render()

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
        _sc = wslcan.is_socketcan()
        hold = "約1〜2分間" if _sc else "約10分間"
        conn_line = "・接続: socketcan(WSL2)＝高速書込(floor=0)\n" if _sc else ""
        msg = ("⚠ 実機フラッシュ(消去を伴う不可逆操作・ブリックの実リスク)\n\n"
               "・対象: いま開いているROM(編集内容をチェックサム補正して書込み)\n"
               "・予備/ベンチECU以外には使わないこと\n"
               f"・電源を安定させ、{hold} 抜線/電源断をしないこと\n"
               + conn_line
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
        # 転送速度(連続フレームのSTmin下限)の決定。
        #   socketcan(WSL2): per-frame USB往復が無く floor=0 が常に安全・最速 → 無条件で最速。
        #   gs_usb(Windows): 1.0ms→0.5ms 短縮は任意(まれに送信FIFO溢れ=Errno10060。背景化しても
        #     realtime_guard がタイマを1msに固定するので値どおり効く。予備ECU・readback照合推奨)。
        if _sc:
            tx_floor = 0.0
        else:
            fast = messagebox.askyesno(
                "ECU書き込み",
                "高速転送モードを使いますか？\n\n"
                "連続フレームの最小間隔を 1.0ms→0.5ms に短縮して書き込み時間を縮めます"
                "(デバッグ反復向け)。\n予備ECU専用。まれに送信FIFO溢れで失敗し得ます"
                "(その場合は[いいえ]で通常速度)。書込後は readback 照合を推奨。")
            tx_floor = 0.0005 if fast else None
        self._run_flash(bytes(self.rom.data), sbl, tx_floor=tx_floor)

    def _run_flash(self, rom_bytes, sbl, tx_floor=None):
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
                # 高速転送時はエコー吸い出しも間引く(drain_every 8->32: 実測で約12%短縮・安定)。
                diag = DiagClient(IsoTp(bus, drain_every=(32 if tx_floor else 8)))
                diag.tp.timeout = 10.0
                log(f"通信確認: tester_present={diag.tester_present()}")
                f = flashmod.Flasher(diag, log=log)
                started = True   # ここから f.flash = 消去+書込みが走る
                f.flash(rom_bytes, sbl, flash_start=flashmod.ROM_FLASH_START_MIN,
                        confirm=True, tx_st_min_floor=tx_floor)
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
        self._build_menus()   # メニュー文言(設定/パッチ/DTC)を現在言語で作り直す
        # ツリーと現在マップを再描画
        self._populate_tree()
        self._render_table()
        for v in self.float_views:
            if v.table is not None:
                v.winfo_toplevel().title(i18n.translate_table_name(v.table.name))
        self._update_status()

    # ---------- ライブPID間引き設定 ----------
    # 選択肢は PID・ライブRAM・ダッシュボードで共通(毎回/0.1s/0.2s/0.5s/1s/2s/5s/10s/無視)。
    CHOICE_SECONDS = list(livelog.INTERVAL_CHOICES)

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
                out[pid] = livelog.snap_interval(v)     # 負=無視。リスト外の値は最寄りへ
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
                for c in d:                              # 間隔は共通の選択肢へそろえる(負=無視)
                    c["interval"] = livelog.snap_interval(c.get("interval", 0.5))
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
        return livelog.interval_label(v, self.lang == "ja")

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
            for s in self.CHOICE_SECONDS:
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
            cur = livelog.snap_interval(self._effective_interval(pid))
            labels = [self._interval_label(s) for s in self.CHOICE_SECONDS]
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
        tk.Label(win, text=i18n.ui("li_follow"), bg="#1e2128", fg="#b9c6da", justify="left",
                 anchor="w", wraplength=760, font=(self.jp, 9)).pack(fill="x", padx=10, pady=(0, 2))

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
                cur = livelog.snap_interval(chn.get("interval", 0.5))
                o = self.CHOICE_SECONDS             # PIDと同じ並び(以前は項目ごとに違っていた)
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
        seconds = livelog.snap_interval(seconds)        # 負=無視(読まない)
        lr = self.live_reader
        if isinstance(ch, int) and ch >= 0x100:        # ライブRAM(合成ch)
            for c in self.ram_reads:
                if c.get("ch") == ch:
                    c["interval"] = seconds
            if lr is not None:
                lr.set_ram_interval(ch, seconds)
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
        # ダッシュボードの上でも Live(F5)・記録(F8) などのショートカットを効かせる(表の操作は除く)
        self.dash_win.bind("<KeyPress>", lambda e: "break" if self.dispatch_key(e, None) else None, add="+")
        if self.live_reader is None:
            messagebox.showinfo(
                "ダッシュボード",
                "ダッシュボードを開きました。数値を表示するには「Live ▶」で実機に接続してください。")

    def _on_close(self):
        if self.modified and self.rom is not None:
            if not messagebox.askyesno(
                    "終了" if self.lang == "ja" else "Exit",
                    ("保存していない変更があります。保存せずに終了しますか？" if self.lang == "ja"
                     else "There are unsaved changes. Exit without saving?")):
                return
        self._stop_live()
        try:
            self._save_views_now()               # 分割レイアウト・別ウィンドウ
            self._geo_keeper.save_now()          # エディタの位置/大きさ
        except Exception:  # noqa: BLE001  設定の保存失敗で終了を止めない
            pass
        if self.dash_win is not None:
            try:
                self.dash_win._on_close()        # ダッシュボードの配置と大きさも保存して閉じる
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
                # socketcan はカーネルが受信バッファリングするので、FCのBSペーシング
                # (gs_usb の受信溢れ対策=BS 0x10)が不要。BS=0 で ECU に全CFを連続送信させ、
                # ブロック毎の FC 往復(約147CF→BS16だと約9往復)を無くして読み出しを速める実験。
                # 読み取り専用のため失敗してもリトライで安全(seq mismatch なら NRC 無しで再試行)。
                rx_bs = 0 if wslcan.is_socketcan() else 0x10
                diag = DiagClient(IsoTp(bus, rx_block_size=rx_bs))
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
                state["t_end"] = time.monotonic()
                state["done"] = True

        state["t0"] = time.monotonic()
        threading.Thread(target=worker, daemon=True).start()

        def _kibs(nbytes, secs):
            return (nbytes / 1024.0 / secs) if secs > 0 else 0.0

        def poll():
            pb["value"] = state["prog"]
            el = time.monotonic() - state["t0"]
            lbl.config(text=f"読み出し中: {state['prog']:,}/{flashmod.ROM_SIZE:,} バイト"
                            f"   {_kibs(state['prog'], el):.1f} KiB/s   {el:.0f}s")
            if state["done"]:
                try:
                    win.destroy()
                except tk.TclError:
                    pass
                if state["err"]:
                    messagebox.showerror(title, f"読み出し失敗:\n{state['err']}")
                elif state["rom"] is not None:
                    total = len(state["rom"])
                    secs = (state.get("t_end") or time.monotonic()) - state["t0"]
                    kibs = _kibs(total, secs)
                    self._last_read_stats = {"bytes": total, "secs": secs, "kibs": kibs}
                    # コンソール(WSLランチャーの窓)にも残す。gs_usb/socketcan の比較用に経路も併記。
                    print(f"[ECU read] {total:,} bytes in {secs:.1f}s "
                          f"({kibs:.1f} KiB/s) via {wslcan.active_method()}")
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
                filetypes=[("BIN", "*.bin")], initialdir=_rom_dir(),
                initialfile="ecu_readout.bin")
            if p:
                pathlib.Path(p).write_bytes(rom)
                gen = self._safe(lambda: flashmod.detect_generation(rom), "?")
                cal = self._safe(lambda: flashmod.get_cal_id(rom), "?")
                crc = self._safe(lambda: f"{flashmod.calibration_crc(rom):08X}", "?")
                st = getattr(self, "_last_read_stats", None)
                tline = (f"読み出し {st['bytes']:,}B / {st['secs']:.1f}s "
                         f"({st['kibs']:.1f} KiB/s)\n") if st else ""
                if messagebox.askyesno(
                        "保存完了",
                        f"保存しました:\n{p}\n\nCALID={cal} 世代={gen} calCRC={crc}\n"
                        f"{tline}\n"
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

        def _after(rom):
            st = getattr(self, "_last_read_stats", None)
            note = (f"ECU読み出し {st['bytes']:,}B / {st['secs']:.1f}s "
                    f"({st['kibs']:.1f} KiB/s)") if st else ""
            self._show_diff(base, rom, base_name, "ECU実機", read_note=note)
        self._ecu_read_rom_async(_after, "ECUと照合(読み出し中)")

    def compare_files(self):
        pa = filedialog.askopenfilename(title="ROM A (基準)", initialdir=_rom_dir(),
                                        filetypes=[("BIN", "*.bin"), ("All", "*.*")])
        if not pa:
            return
        pb_ = filedialog.askopenfilename(title="ROM B (比較対象)", initialdir=_rom_dir(),
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
        self.orig_data = bytes(data)
        self.history.clear()
        self.redo_stack.clear()
        self._set_rom(data)
        self.rom_path = pathlib.Path(path) if path else None
        self.modified = False
        self._populate_tree()
        self._update_status()

    def _show_diff(self, a: bytes, b: bytes, name_a: str, name_b: str, read_note: str = ""):
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
               else ("特殊領域の変化: " + (", ".join(flags) if flags else "なし")))
            + (("\n" + read_note) if read_note else "")))
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
