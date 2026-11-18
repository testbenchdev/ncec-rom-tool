"""ショートカットキー: 操作の一覧(既定キー付き)、キー入力の正規化、設定ダイアログ。

キーは "Ctrl+Shift+S" のような文字列で持つ。修飾は Ctrl / Alt / Shift の順。
記号キー(+ - * = / など)は Shift の有無を区別しない(JIS 配列では + も * も Shift が要るため)。
テンキーの + - * / と Enter は本体側と同じキーとして扱う。

操作の範囲(scope):
  "global" … エディタのどこにフォーカスがあっても効く(検索欄などの入力中は、Ctrl/Alt 付きか F キーだけ)
  "table"  … 表(マップ)にフォーカスがあるときだけ効く(表の編集・選択)
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class Action:
    id: str
    group: str
    ja: str
    en: str
    keys: tuple = ()
    scope: str = "global"
    text_ok: bool = True        # 入力欄にフォーカスがあっても実行してよいか(元に戻す等は不可)

    def label(self, lang: str) -> str:
        return self.en if lang == "en" else self.ja


GROUPS = {
    "file": ("ファイル", "File"),
    "edit": ("表の編集", "Table editing"),
    "select": ("選択・移動", "Selection / navigation"),
    "view": ("表示・レイアウト", "View / layout"),
    "live": ("ライブ・計測", "Live / logging"),
    "ecu": ("ECU", "ECU"),
    "other": ("その他", "Other"),
}

ACTIONS: list[Action] = [
    # ファイル
    Action("open_rom", "file", "ROMを開く…", "Open ROM…", ("Ctrl+O",)),
    Action("save", "file", "保存", "Save", ("Ctrl+S",)),
    Action("save_as", "file", "名前を付けて保存…", "Save as…", ("Ctrl+Shift+S",)),
    Action("cmp_rom", "file", "ROM比較…", "Compare ROM files…"),
    Action("undo", "file", "元に戻す", "Undo", ("Ctrl+Z",), text_ok=False),
    Action("redo", "file", "やり直し", "Redo", ("Ctrl+Y", "Ctrl+Shift+Z"), text_ok=False),
    # 表の編集
    Action("edit_cell", "edit", "セルを編集(入力開始)", "Edit cell", ("F2", "Enter"), "table"),
    Action("inc", "edit", "増やす(小)", "Increase (small)", ("+",), "table"),
    Action("dec", "edit", "減らす(小)", "Decrease (small)", ("-",), "table"),
    Action("inc_big", "edit", "増やす(大)", "Increase (large)", ("PgUp",), "table"),
    Action("dec_big", "edit", "減らす(大)", "Decrease (large)", ("PgDn",), "table"),
    Action("set_value", "edit", "値を設定…", "Set value…", ("=",), "table"),
    Action("add_value", "edit", "値を加算…", "Add value…", ("A",), "table"),
    Action("percent", "edit", "％で増減…", "Change by %…", ("*",), "table"),
    Action("multiply", "edit", "倍率を掛ける…", "Multiply by…", ("M",), "table"),
    Action("interp_h", "edit", "横方向に補間", "Interpolate horizontally", ("H",), "table"),
    Action("interp_v", "edit", "縦方向に補間", "Interpolate vertically", ("V",), "table"),
    Action("interp_2d", "edit", "四隅から2次元補間", "Interpolate 2D (from corners)", ("B",), "table"),
    Action("smooth", "edit", "平滑化", "Smooth", ("S",), "table"),
    Action("fill_down", "edit", "下へコピー(先頭行)", "Fill down", ("Ctrl+D",), "table"),
    Action("fill_right", "edit", "右へコピー(先頭列)", "Fill right", ("Ctrl+R",), "table"),
    Action("copy", "edit", "コピー", "Copy", ("Ctrl+C",), "table"),
    Action("paste", "edit", "貼り付け", "Paste", ("Ctrl+V",), "table"),
    Action("revert_sel", "edit", "選択範囲を保存済みの値に戻す", "Revert selection to saved values",
           ("Ctrl+Shift+R",), "table"),
    Action("copy_to_pair", "edit", "選択範囲を相方(制御⇔監視)へコピー", "Copy selection to the paired table",
           (), "table"),
    Action("set_step", "edit", "増減幅の設定…", "Increment settings…", ("I",), "table"),
    Action("axis_edit", "edit", "軸編集 ON/OFF", "Axis edit on/off"),
    # 選択・移動
    Action("select_all", "select", "すべて選択", "Select all", ("Ctrl+A",), "table"),
    Action("goto_live", "select", "運転点(●)のセルを選択", "Select the live operating-point cell", ("Space",), "table"),
    Action("find", "select", "検索欄へ移動", "Go to search box", ("Ctrl+F",)),
    Action("tree_focus", "select", "テーブル一覧へ移動", "Go to table list", ("Ctrl+T",), text_ok=False),
    Action("table_focus", "select", "表(アクティブなペイン)へ移動", "Go to the active table", ("Ctrl+E",)),
    Action("next_table", "select", "次のテーブルを開く", "Open next table", ("Ctrl+PgDn",)),
    Action("prev_table", "select", "前のテーブルを開く", "Open previous table", ("Ctrl+PgUp",)),
    # 表示・レイアウト
    Action("layout_1", "view", "レイアウト: 1画面", "Layout: single", ("Ctrl+1",)),
    Action("layout_2h", "view", "レイアウト: 左右2分割", "Layout: 2 side by side", ("Ctrl+2",)),
    Action("layout_2v", "view", "レイアウト: 上下2分割", "Layout: 2 stacked", ("Ctrl+3",)),
    Action("layout_4", "view", "レイアウト: 4分割", "Layout: 4 (2x2)", ("Ctrl+4",)),
    Action("layout_3", "view", "レイアウト: 3分割(左1・右2)", "Layout: 3 (1 left, 2 right)", ("Ctrl+5",)),
    Action("next_pane", "view", "次のペインへ", "Next pane", ("Ctrl+Tab",)),
    Action("prev_pane", "view", "前のペインへ", "Previous pane", ("Ctrl+Shift+Tab",)),
    Action("show_pair", "view", "相方(制御⇔監視)を隣に表示", "Show the paired table next to it", ("Ctrl+P",)),
    Action("detach", "view", "別ウィンドウで開く", "Open in a separate window", ("Ctrl+Shift+D",)),
    Action("close_pane", "view", "ペインを閉じる(空にする)", "Close pane (clear)", ("Ctrl+W",)),
    Action("zoom_in", "view", "表を拡大", "Zoom in", ("Ctrl++", "Ctrl+=")),
    Action("zoom_out", "view", "表を縮小", "Zoom out", ("Ctrl+-",)),
    Action("zoom_reset", "view", "表を標準の大きさに", "Reset zoom", ("Ctrl+0",)),
    Action("toggle_desc", "view", "説明欄の表示 ON/OFF", "Show/hide description", ("Ctrl+H",), text_ok=False),
    Action("mirror_pairs", "view", "ペア同時編集 ON/OFF", "Paired editing on/off"),
    Action("lang", "view", "言語の切り替え", "Switch language"),
    # ライブ・計測
    Action("live", "live", "Live 接続/切断", "Live connect/disconnect", ("F5",)),
    Action("dashboard", "live", "ダッシュボード", "Dashboard", ("F6",)),
    Action("record", "live", "記録 開始/停止", "Start/stop logging", ("F8",)),
    Action("replay", "live", "リプレイ…", "Replay…"),
    Action("chart", "live", "ログ分析…", "Log analysis…", ("F9",)),
    Action("live_intervals", "live", "ライブPID間引き…", "Live PID intervals…"),
    # ECU(書き込みは誤操作防止のためショートカット対象外)
    Action("dump", "ecu", "ECU吸出し", "Read ECU"),
    Action("cmp_ecu", "ecu", "ECUと照合", "Compare with ECU"),
    Action("dtc_clear", "ecu", "DTCクリア…", "Clear DTCs…"),
    # その他
    Action("help", "other", "ヘルプ", "Help", ("F1",)),
    Action("shortcuts", "other", "ショートカットキーの設定…", "Keyboard shortcuts…"),
]
BY_ID = {a.id: a for a in ACTIONS}

# 割り当てられないキー(表の中の移動・入力に使う)
_NAV = ("Up", "Down", "Left", "Right", "Home", "End")
RESERVED = set(_NAV) | {f"Shift+{k}" for k in _NAV} | {f"Ctrl+{k}" for k in _NAV} \
    | {f"Ctrl+Shift+{k}" for k in _NAV} | {"Tab", "Shift+Tab", "Esc", "."} | {str(i) for i in range(10)}

_SYM = {
    "plus": "+", "KP_Add": "+", "minus": "-", "KP_Subtract": "-", "asterisk": "*", "KP_Multiply": "*",
    "slash": "/", "KP_Divide": "/", "equal": "=", "KP_Equal": "=", "period": ".", "KP_Decimal": ".",
    "comma": ",", "KP_Separator": ",", "semicolon": ";", "colon": ":", "percent": "%", "at": "@",
    "bracketleft": "[", "bracketright": "]", "braceleft": "{", "braceright": "}", "backslash": "\\",
    "yen": "\\", "underscore": "_", "asciicircum": "^", "asciitilde": "~", "grave": "`", "apostrophe": "'",
    "quotedbl": '"', "exclam": "!", "numbersign": "#", "dollar": "$", "ampersand": "&", "parenleft": "(",
    "parenright": ")", "less": "<", "greater": ">", "question": "?", "bar": "|",
    "Prior": "PgUp", "KP_Prior": "PgUp", "Next": "PgDn", "KP_Next": "PgDn",
    "Return": "Enter", "KP_Enter": "Enter", "space": "Space", "KP_Space": "Space", "Escape": "Esc",
    "Delete": "Del", "KP_Delete": "Del", "BackSpace": "Backspace", "ISO_Left_Tab": "Tab", "Insert": "Ins",
    "KP_Insert": "Ins", "KP_Home": "Home", "KP_End": "End", "KP_Up": "Up", "KP_Down": "Down",
    "KP_Left": "Left", "KP_Right": "Right",
}
_MODIFIER_KEYS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                  "Super_L", "Super_R", "Caps_Lock", "Num_Lock", "ISO_Level3_Shift", "Win_L", "Win_R",
                  "App", "Kana_Lock", "Hiragana_Katakana", "Zenkaku_Hankaku", "Kanji", "Muhenkan",
                  "Henkan_Mode", "Eisu_toggle", "Mode_switch", "??"}


def alt_mask(widget) -> int:
    """Alt の state ビット。Windows の Tk は 0x20000、X11(WSLg) は Mod1=0x8。"""
    try:
        ws = widget.tk.call("tk", "windowingsystem")
    except tk.TclError:
        ws = "win32"
    return 0x20000 if ws == "win32" else 0x8


def event_to_key(ev, altmask: int) -> str | None:
    """Tk の KeyPress イベント → "Ctrl+Shift+S" 形式。修飾キー単独は None。"""
    ks = ev.keysym
    if ks in _MODIFIER_KEYS:
        return None
    st = ev.state if isinstance(ev.state, int) else 0
    ctrl, shift, alt = bool(st & 0x4), bool(st & 0x1), bool(st & altmask)
    if ks == "ISO_Left_Tab":
        shift = True
    key = _SYM.get(ks)
    if key is None:
        if len(ks) == 1:
            key = ks.upper() if ks.isalpha() else ks
        elif ks.startswith("KP_") and ks[3:].isdigit():
            key = ks[3:]
        else:
            key = ks
    if len(key) == 1 and not key.isalnum():
        shift = False                      # 記号は Shift の有無を区別しない
    mods = [m for m, on in (("Ctrl", ctrl), ("Alt", alt), ("Shift", shift)) if on]
    return "+".join(mods + [key])


def has_modifier(key: str) -> bool:
    """Ctrl/Alt 付き、または F キー(入力欄で文字を打っている最中でも誤爆しないキー)。"""
    if key.startswith(("Ctrl+", "Alt+")):
        return True
    k = key[6:] if key.startswith("Shift+") else key
    return len(k) >= 2 and k[0] == "F" and k[1:].isdigit()


def defaults() -> dict[str, list[str]]:
    return {a.id: list(a.keys) for a in ACTIONS}


def load_keymap(overrides) -> dict[str, list[str]]:
    """既定に保存済みの変更(overrides={id:[keys]})を重ねる。重複したキーは後の操作から外す。"""
    km = defaults()
    if isinstance(overrides, dict):
        for aid, keys in overrides.items():
            if aid in km and isinstance(keys, list):
                km[aid] = [str(k) for k in keys if isinstance(k, str) and k and k not in RESERVED]
    seen = set()
    for a in ACTIONS:
        out = []
        for k in km[a.id]:
            if k not in seen:
                seen.add(k)
                out.append(k)
        km[a.id] = out
    return km


def overrides_of(km: dict[str, list[str]]) -> dict[str, list[str]]:
    d = defaults()
    return {aid: keys for aid, keys in km.items() if keys != d.get(aid)}


def reverse(km: dict[str, list[str]]) -> dict[str, str]:
    """キー → 操作 id"""
    return {k: aid for aid, keys in km.items() for k in keys}


def accel(km: dict[str, list[str]], aid: str) -> str:
    """メニューに出すキー表記(最初の1つ)。"""
    keys = km.get(aid) or []
    return keys[0] if keys else ""


# ---------------- 設定ダイアログ ----------------
class ShortcutDialog:
    """操作ごとのキー割り当てを変える。OK で on_apply(keymap) を呼ぶ。"""

    def __init__(self, parent, keymap, lang, on_apply, font=("TkDefaultFont", 10)):
        self.parent = parent
        self.km = {k: list(v) for k, v in keymap.items()}
        self.lang = lang
        self.on_apply = on_apply
        ja = lang != "en"
        self.ja = ja
        self.altmask = alt_mask(parent)
        top = self.top = tk.Toplevel(parent)
        top.title("ショートカットキーの設定" if ja else "Keyboard shortcuts")
        top.configure(bg="#1e2128")
        top.transient(parent)
        top.geometry("760x620")
        note = ("操作を選んで［キーを割り当て］を押し、使いたいキーを押してください（Esc で取り消し）。1つの操作に複数のキーを"
                "割り当てられます。表の中の移動（矢印・Shift+矢印・Home/End・Tab）と数字・小数点（そのまま入力が始まる）は"
                "割り当てられません。負の値を入力するときは Enter か F2 で入力を始めてから「-」を打ちます。"
                "『表の編集』『選択・移動』の多くは表（マップ）をクリックしてフォーカスがあるときだけ効きます。"
                "ECU書き込みは誤操作を防ぐためショートカットの対象外です。"
                if ja else
                "Pick an action, press [Assign key] and then the key you want (Esc cancels). An action can have several "
                "keys. Navigation inside the table (arrows, Shift+arrows, Home/End, Tab) and digits/decimal point "
                "(they start typing) cannot be assigned. To type a negative value, start editing with Enter or F2 "
                "first. Most table-editing actions work only while the table has focus. ECU flashing has no shortcut "
                "on purpose.")
        tk.Label(top, text=note, bg="#1e2128", fg="#b9c6da", wraplength=730, justify="left", anchor="w",
                 font=font).pack(fill="x", padx=10, pady=(8, 4))
        frm = tk.Frame(top, bg="#1e2128")
        frm.pack(fill="both", expand=True, padx=10)
        self.tree = ttk.Treeview(frm, columns=("keys", "scope"), selectmode="browse")
        self.tree.heading("#0", text="操作" if ja else "Action")
        self.tree.heading("keys", text="キー" if ja else "Keys")
        self.tree.heading("scope", text="効く場所" if ja else "Works in")
        self.tree.column("#0", width=360)
        self.tree.column("keys", width=220)
        self.tree.column("scope", width=120)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._assign())
        self._fill()
        btns = tk.Frame(top, bg="#1e2128")
        btns.pack(fill="x", padx=10, pady=8)
        b = (("キーを割り当て…", "Assign key…", self._assign),
             ("キーを外す", "Remove keys", self._clear),
             ("この操作を既定に戻す", "Reset this action", self._reset_one),
             ("すべて既定に戻す", "Reset all", self._reset_all))
        for j, e, cmd in b:
            tk.Button(btns, text=j if ja else e, command=cmd).pack(side="left", padx=(0, 6))
        tk.Button(btns, text="キャンセル" if ja else "Cancel", command=top.destroy).pack(side="right")
        tk.Button(btns, text="OK", width=8, command=self._ok).pack(side="right", padx=(0, 6))

    def _fill(self):
        sel = self._sel()
        self.tree.delete(*self.tree.get_children())
        for g, (gj, ge) in GROUPS.items():
            gid = self.tree.insert("", "end", text=gj if self.ja else ge, open=True)
            for a in ACTIONS:
                if a.group != g:
                    continue
                scope = (("表" if a.scope == "table" else "どこでも") if self.ja
                         else ("table" if a.scope == "table" else "anywhere"))
                self.tree.insert(gid, "end", iid=a.id, text=a.label(self.lang),
                                 values=(" / ".join(self.km.get(a.id, [])), scope))
        if sel and self.tree.exists(sel):
            self.tree.selection_set(sel)
            self.tree.see(sel)

    def _sel(self):
        s = self.tree.selection() if hasattr(self, "tree") else ()
        return s[0] if s and s[0] in BY_ID else None

    def _assign(self):
        aid = self._sel()
        if not aid:
            return
        cap = tk.Toplevel(self.top)
        cap.title("キー入力" if self.ja else "Press a key")
        cap.configure(bg="#1e2128")
        cap.transient(self.top)
        tk.Label(cap, text=(f"「{BY_ID[aid].label(self.lang)}」に割り当てるキーを押してください\n（Esc で取り消し）"
                            if self.ja else f"Press the key for '{BY_ID[aid].label(self.lang)}'\n(Esc cancels)"),
                 bg="#1e2128", fg="#dfe3ea", padx=20, pady=16, justify="center").pack()
        cap.grab_set()
        cap.focus_force()

        def on_key(ev):
            k = event_to_key(ev, self.altmask)
            if k is None:
                return "break"
            if k == "Esc":
                cap.destroy()
                return "break"
            if k in RESERVED:
                messagebox.showwarning(cap.title(), (f"「{k}」は表の中の移動・入力に使うので割り当てられません。"
                                                     if self.ja else f"'{k}' is reserved for table navigation/typing."),
                                       parent=cap)
                return "break"
            owner = next((a for a, ks in self.km.items() if k in ks and a != aid), None)
            if owner:
                if not messagebox.askyesno(cap.title(), (
                        f"「{k}」はいま「{BY_ID[owner].label(self.lang)}」に割り当てられています。\nそちらから外して割り当てますか？"
                        if self.ja else f"'{k}' is used by '{BY_ID[owner].label(self.lang)}'. Move it?"), parent=cap):
                    return "break"
                self.km[owner] = [x for x in self.km[owner] if x != k]
            if k not in self.km.setdefault(aid, []):
                self.km[aid].append(k)
            cap.destroy()
            self._fill()
            return "break"

        cap.bind("<KeyPress>", on_key)

    def _clear(self):
        aid = self._sel()
        if aid:
            self.km[aid] = []
            self._fill()

    def _reset_one(self):
        aid = self._sel()
        if not aid:
            return
        d = list(BY_ID[aid].keys)
        for k in d:                       # 既定キーを別の操作が使っていたら、そちらから外す
            for a, ks in self.km.items():
                if a != aid and k in ks:
                    self.km[a] = [x for x in ks if x != k]
        self.km[aid] = d
        self._fill()

    def _reset_all(self):
        self.km = defaults()
        self._fill()

    def _ok(self):
        self.on_apply(load_keymap(overrides_of(self.km)))
        self.top.destroy()
