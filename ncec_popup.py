"""右クリックメニューを、別ウィンドウではなく親ウィンドウの中に描く(WSLg 用)。

WSLg(Weston/XWayland)では tk.Menu が別ウィンドウとして描かれるため、外側を押した瞬間に一度消えて再び現れ、
閉じたあとも約 1 秒画面に残る(2026-11-18、XTest の実クリックと Windows 側のコマ撮りで確認。Tk 側は離した
約 0.1 秒後に閉じており、ウィンドウを壊しても残る時間は変わらなかった)。メニューを親ウィンドウの中の
Frame として描けば別ウィンドウが無いので、この現象は起きない。

使い方は tk.Menu の一部と同じ:
    add_command(label=, accelerator=, command=, state="disabled") / add_separator() /
    add_cascade(label=, menu=<InlineMenu>) / post(x_root, y_root, widget)
- サブメニュー(cascade)は、その行をクリックすると下に開く折りたたみ式(別ウィンドウを出さないため)。
- 親ウィンドウの高さに収まらないときは、複数の列に並べる。幅も収まらないときは post が False を返すので、
  呼び出し側で tk.Menu に切り替える(native_from)。
操作: 項目をクリック / 上下キーと Enter(サブメニューは Enter・右キーで開く、左キーで閉じる)/ Esc。
外側をクリックすると閉じる(そのクリックは下の画面に渡さない)。
"""
from __future__ import annotations

import tkinter as tk

BG = "#343a47"          # 画面(#1e2128 など)より明るくして、重なっていることが分かるように
FG = "#e8ecf2"
ACC_FG = "#a9b8cc"
DIS_FG = "#7d8796"
HDR_FG = "#cfe0f5"
HOVER_BG = "#3a6ea5"
HOVER_FG = "#ffffff"
BORDER = "#7a8698"
SEP = "#4f5768"


class InlineMenu:
    def __init__(self, master, font=None):
        self.master = master
        self.font = font
        self.items: list[tuple] = []          # ("cmd", label, accel, command, state) / ("sep",) / ("cascade", label, sub)
        self.frame = None
        self._top = None
        self._anchor = (0, 0)
        self._rows: list[tuple] = []          # (entry, row frame, (label, accel label))
        self._active = None
        self._expanded = None                 # 開いているサブメニュー(items の番号)
        self._prev_focus = None
        self._pressed_inside = False

    # ---- tk.Menu と同じ形の追加 ----
    def add_command(self, label="", accelerator="", command=None, state="normal", **_kw):
        self.items.append(("cmd", label, accelerator or "", command, state))

    def add_separator(self):
        self.items.append(("sep",))

    def add_cascade(self, label="", menu=None, **_kw):
        self.items.append(("cascade", label, menu))

    # ---- 表示 ----
    def is_open(self) -> bool:
        try:
            return self.frame is not None and bool(self.frame.winfo_exists())
        except tk.TclError:
            return False

    def post(self, x_root, y_root, widget=None) -> bool:
        top = (widget or self.master).winfo_toplevel()
        self.close()
        self._top = top
        try:
            self._anchor = (int(x_root) - top.winfo_rootx() + 2, int(y_root) - top.winfo_rooty() + 2)
        except tk.TclError:
            return False
        self.frame = tk.Frame(top, bg=BORDER, bd=0, highlightthickness=0, takefocus=1)
        self._expanded = None
        if not self._layout():
            fr, self.frame = self.frame, None
            fr.destroy()
            return False
        fr = self.frame
        try:
            self._prev_focus = top.focus_get()
        except (tk.TclError, KeyError):
            self._prev_focus = None
        fr.bind("<ButtonPress>", self._outside_press)
        fr.bind("<KeyPress>", self._key)
        fr.bind("<FocusOut>", lambda _e: fr.after(30, self._check_focus))
        fr.focus_set()
        self._grab(fr, 0)
        return True

    def _entries(self):
        """いま見せる行: (種類, 表示名, キー, コマンド, 状態, 深さ, cascade の番号)"""
        out = []
        for i, it in enumerate(self.items):
            if it[0] == "sep":
                out.append(("sep", "", "", None, "normal", 0, None))
            elif it[0] == "cmd":
                out.append(("cmd", it[1], it[2], it[3], it[4], 0, None))
            else:
                opened = self._expanded == i
                out.append(("cascade", it[1], "▾" if opened else "▸", None, "normal", 0, i))
                if opened and it[2] is not None:
                    for sub in it[2].items:
                        if sub[0] == "cmd":
                            out.append(("cmd", sub[1], sub[2], sub[3], sub[4], 1, None))
                        elif sub[0] == "sep":
                            out.append(("sep", "", "", None, "normal", 1, None))
        return out

    def _layout(self) -> bool:
        """行を作り直して置く。高さが足りなければ複数列。幅が足りなければ False。"""
        fr, top = self.frame, self._top
        for w in fr.winfo_children():
            w.destroy()
        self._rows = []
        self._active = None
        try:
            probe = tk.Label(fr, text="Ag項", font=self.font, padx=0, pady=2)   # 実際の行の高さを測る
            rh = probe.winfo_reqheight()
            probe.destroy()
            top.update_idletasks()
            tw, th = top.winfo_width(), top.winfo_height()
        except tk.TclError:
            return False
        avail = max(rh * 3, th - 6)
        cols, cur, h = [], [], 0
        for e in self._entries():
            eh = 7 if e[0] == "sep" else rh
            if cur and h + eh > avail:
                cols.append(cur)
                cur, h = [], 0
                if e[0] == "sep":
                    continue
            cur.append(e)
            h += eh
        if cur:
            cols.append(cur)
        inner = tk.Frame(fr, bg=BG)
        inner.pack(padx=1, pady=1)
        for ci, col in enumerate(cols):
            if ci:
                tk.Frame(inner, width=1, bg=SEP).pack(side="left", fill="y", pady=4)
            cf = tk.Frame(inner, bg=BG)
            cf.pack(side="left", fill="y", anchor="n")
            for e in col:
                self._make_row(cf, e)
        top.update_idletasks()
        w, h = fr.winfo_reqwidth(), fr.winfo_reqheight()
        if w > tw:
            return False
        x, y = self._anchor
        if x + w > tw:
            x = max(0, x - w - 4)
        if y + h > th:
            y = max(0, th - h)
        fr.place(x=x, y=y)
        fr.lift()
        return True

    def _make_row(self, parent, e):
        kind, label, accel, _cmd, state, depth, _ci = e
        if kind == "sep":
            tk.Frame(parent, height=1, bg=SEP).pack(fill="x", padx=8, pady=3)
            return
        row = tk.Frame(parent, bg=BG)
        fg = DIS_FG if state == "disabled" else (HDR_FG if kind == "cascade" else FG)
        l1 = tk.Label(row, text=label, bg=BG, fg=fg, anchor="w", font=self.font, padx=0, pady=2)
        l2 = tk.Label(row, text=accel, bg=BG, fg=ACC_FG, anchor="e", font=self.font, padx=0, pady=2)
        if accel:
            l1.pack(side="left", padx=(16 + 18 * depth, 28))
            l2.pack(side="right", padx=(0, 14))
        else:                                     # キー表示の無い行は詰める(列にしたとき幅を取りすぎない)
            l1.pack(side="left", padx=(16 + 18 * depth, 16))
        row.pack(fill="x")
        k = len(self._rows)
        for w in (row, l1, l2):
            w.bind("<Enter>", lambda _e, k=k: self._set_active(k))
            w.bind("<ButtonPress-1>", lambda _e: self._press_inside())
            w.bind("<ButtonRelease-1>", lambda _e, k=k: self._release(k))
        self._rows.append((e, row, (l1, l2)))

    def _grab(self, fr, tries):
        """外側のクリックもこの Frame に届くよう掴む(閉じるために使う)。place した直後はまだ画面に出ておらず
        grab_set が "window not viewable" で失敗するので、出るまで少し待って掛け直す。"""
        if fr is not self.frame:
            return
        try:
            fr.grab_set()
        except tk.TclError:
            if tries < 50:
                fr.after(10, lambda: self._grab(fr, tries + 1))

    def close(self):
        fr, self.frame = self.frame, None
        self._active = None
        if fr is None:
            return
        try:
            fr.grab_release()
        except tk.TclError:
            pass
        try:
            fr.destroy()
        except tk.TclError:
            pass
        pf, self._prev_focus = self._prev_focus, None
        try:
            if pf is not None and pf.winfo_exists():
                pf.focus_set()
        except tk.TclError:
            pass

    # tk.Menu と同じ名前でも閉じられるように
    unpost = close
    destroy = close

    # ---- 操作 ----
    def _paint(self, k, on):
        e, row, (l1, l2) = self._rows[k]
        dis = e[4] == "disabled"
        bg = HOVER_BG if (on and not dis) else BG
        row.config(bg=bg)
        l1.config(bg=bg, fg=HOVER_FG if (on and not dis) else
                  (DIS_FG if dis else (HDR_FG if e[0] == "cascade" else FG)))
        l2.config(bg=bg, fg=HOVER_FG if (on and not dis) else ACC_FG)

    def _set_active(self, k):
        if self._active == k or not self.is_open():
            return
        if self._active is not None and self._active < len(self._rows):
            self._paint(self._active, False)
        self._active = k
        if k is not None and k < len(self._rows):
            self._paint(k, True)

    def _press_inside(self):
        self._pressed_inside = True
        return "break"

    def _release(self, k):
        if not self._pressed_inside:              # 右クリックを離しただけ等では実行しない
            return "break"
        self._pressed_inside = False
        self._invoke(k)
        return "break"

    def _toggle(self, ci, keep_label=None):
        self._expanded = None if self._expanded == ci else ci
        if not self._layout():                    # 開いたら収まらない → 閉じた状態に戻す
            self._expanded = None
            self._layout()
        for k, (e, _r, _l) in enumerate(self._rows):   # 開閉した行を選んだままにする
            if e[0] == "cascade" and e[6] == ci:
                self._set_active(k)
                break

    def _invoke(self, k):
        if k is None or k >= len(self._rows):
            return
        e = self._rows[k][0]
        if e[0] == "cascade":
            self._toggle(e[6])
            return
        if e[4] == "disabled":
            return
        cmd = e[3]
        self.close()                              # 先に閉じる(コマンドがダイアログを出すため)
        if cmd is not None:
            cmd()

    def _outside_press(self, e):
        fr = self.frame
        if fr is None:
            return "break"
        inside = 0 <= e.x < fr.winfo_width() and 0 <= e.y < fr.winfo_height()
        if not inside:
            self.close()
        return "break"                            # 閉じるためのクリックは下の画面に渡さない

    def _key(self, e):
        ks = e.keysym
        n = len(self._rows)
        if ks == "Escape":
            self.close()
        elif ks in ("Down", "KP_Down", "Up", "KP_Up") and n:
            d = 1 if ks.endswith("Down") else -1
            k = self._active if self._active is not None else (-1 if d > 0 else 0)
            for _ in range(n):                    # 区切りは行に入っていないので、そのまま次へ
                k = (k + d) % n
                if self._rows[k][0][4] != "disabled":
                    break
            self._set_active(k)
        elif ks in ("Return", "KP_Enter", "space"):
            if self._active is not None:
                self._invoke(self._active)
        elif ks in ("Right", "KP_Right") and self._active is not None:
            e2 = self._rows[self._active][0]
            if e2[0] == "cascade" and self._expanded != e2[6]:
                self._toggle(e2[6])
        elif ks in ("Left", "KP_Left") and self._expanded is not None:
            self._toggle(self._expanded)
        return "break"                            # メニューを開いている間はショートカットを効かせない

    def _check_focus(self):
        fr = self.frame
        if fr is None:
            return
        try:
            f = fr.focus_get()
        except (tk.TclError, KeyError):
            f = None
        if f is None:                             # アプリ自体がフォーカスを持っていないだけ(WSLg で起きる)。閉じない
            return
        w = f
        while w is not None:
            if w is fr:
                return
            w = getattr(w, "master", None)
        self.close()                              # アプリの中のほかの部品へフォーカスが移った


def is_x11(widget) -> bool:
    try:
        return widget.tk.call("tk", "windowingsystem") == "x11"
    except tk.TclError:
        return False


def make_menu(master, font=None):
    """右クリックメニューの入れ物。X11(WSLg)では InlineMenu、Windows では tk.Menu。"""
    return InlineMenu(master, font=font) if is_x11(master) else tk.Menu(master, tearoff=0)


def native_from(inline: InlineMenu, master) -> tk.Menu:
    """InlineMenu と同じ項目の tk.Menu を作る(親ウィンドウに収まらないときの代わり)。"""
    m = tk.Menu(master, tearoff=0)
    for it in inline.items:
        if it[0] == "sep":
            m.add_separator()
        elif it[0] == "cmd":
            m.add_command(label=it[1], accelerator=it[2], command=it[3], state=it[4])
        elif it[2] is not None:
            m.add_cascade(label=it[1], menu=native_from(it[2], m))
    return m
