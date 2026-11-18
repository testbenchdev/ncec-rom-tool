"""画面の状態を ui_settings.json に保存/復元する(個人設定。git・配布 zip の対象外)。

保存するもの:
  - "editor" / "dashboard": ウィンドウの位置とサイズ(最大化の有無を含む)
  - "views": エディタの表の分割レイアウト(表示中の表・拡大率・別ウィンドウ)
  - "shortcuts": ショートカットキー(既定から変えたものだけ)
  - "steps": 表ごとの増減幅(既定から変えたものだけ)
  - "options": ペア同時編集などの表示/編集オプション

エディタとダッシュボードは同じプロセスで動くので、内容はこのモジュールが1つだけ持ち、
書き換えのたびにファイルへ書く(読み取りは起動時の1回)。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

PATH = pathlib.Path(__file__).resolve().parent / "ui_settings.json"

_data: dict | None = None


def _load() -> dict:
    global _data
    if _data is None:
        try:
            d = json.loads(PATH.read_text(encoding="utf-8"))
            _data = d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            _data = {}
    return _data


def get(section: str, default=None):
    v = _load().get(section)
    return default if v is None else v


def put(section: str, value) -> None:
    """section を value に置き換えて保存する。失敗しても例外は出さない(設定の保存は補助機能)。"""
    d = _load()
    d[section] = value
    try:
        PATH.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# ---------------- ウィンドウの位置/サイズ ----------------
_GEO = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")


def _virtual_screen(win):
    """全モニタを合わせた領域 (x, y, w, h)。Windows は仮想スクリーン、それ以外は X のスクリーン。"""
    if sys.platform == "win32":
        try:
            import ctypes
            gsm = ctypes.windll.user32.GetSystemMetrics
            x, y, w, h = gsm(76), gsm(77), gsm(78), gsm(79)
            if w > 0 and h > 0:
                return x, y, w, h
        except Exception:  # noqa: BLE001
            pass
    return 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()


def restore_geometry(win, state: dict | None, default: str, min_w: int = 240, min_h: int = 160) -> None:
    """保存した位置/サイズを win に当てる。画面の外に出てしまう位置(モニタを外した等)はサイズだけ使う。"""
    geo = (state or {}).get("geometry") if isinstance(state, dict) else None
    m = _GEO.match(geo or "")
    if not m:
        win.geometry(default)
    else:
        w, h = max(min_w, int(m.group(1))), max(min_h, int(m.group(2)))
        x, y = int(m.group(3)), int(m.group(4))
        vx, vy, vw, vh = _virtual_screen(win)
        w, h = min(w, max(min_w, vw)), min(h, max(min_h, vh))
        # タイトルバー付近(左上から 120x40)が画面内にあるときだけ位置も戻す
        onscreen = (vx - 40 <= x <= vx + vw - 120) and (vy - 10 <= y <= vy + vh - 40)
        win.geometry(f"{w}x{h}{x:+d}{y:+d}" if onscreen else f"{w}x{h}")
    if isinstance(state, dict) and state.get("zoomed"):
        def _zoom():
            try:
                win.state("zoomed")              # Windows
            except Exception:  # noqa: BLE001
                try:
                    win.attributes("-zoomed", True)  # X11(WSLg)
                except Exception:  # noqa: BLE001
                    pass
        win.after(50, _zoom)


def is_zoomed(win) -> bool:
    try:
        if win.state() == "zoomed":
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(int(win.attributes("-zoomed")))
    except Exception:  # noqa: BLE001
        return False


class GeometryKeeper:
    """win の位置/サイズを追いかけて section に保存する。最大化中は最大化前の大きさを残す。
    <Configure> のたびに書くと重いので 600ms まとめてから保存し、閉じるときは save_now() を呼ぶ。"""

    def __init__(self, win, section: str):
        self.win = win
        self.section = section
        self.normal = None
        self._after = None
        st = get(section, {})
        if isinstance(st, dict):
            self.normal = st.get("geometry")
        win.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, e):
        if e.widget is not self.win:
            return
        try:
            if not is_zoomed(self.win) and self.win.state() == "normal":
                self.normal = self.win.wm_geometry()
        except Exception:  # noqa: BLE001
            return
        if self._after is not None:
            try:
                self.win.after_cancel(self._after)
            except Exception:  # noqa: BLE001
                pass
        self._after = self.win.after(600, self.save_now)

    def save_now(self):
        self._after = None
        try:
            zoomed = is_zoomed(self.win)
            if not zoomed and self.win.state() == "normal":
                self.normal = self.win.wm_geometry()
        except Exception:  # noqa: BLE001
            return
        if self.normal:
            put(self.section, {"geometry": self.normal, "zoomed": zoomed})
