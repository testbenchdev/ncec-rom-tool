"""マップの軸に入る RAM 変数(この ROM での実番地)を、ROM のコードから割り出して ncecu/axis_ram.py を作る。

使い方:  python tools/gen_axis_ram.py [--check]
  --check  生成結果と ncecu/axis_ram.py が同じかだけ確かめる(書かない)。

背景(2026-11-16):
  LibreTuner 定義の軸名の末尾(例 RPM_6DD8)は、別の ROM の RAM 番地で、この ROM(LFG7EG)の番地とは
  ずれている(回転数は 0xFFFF6D5C、0xFFFF6DD8 は 0/1 のフラグ)。ずれ幅も場所で違う(0x7C・0x60・0x78 など)。
  そこで、表記述子(0x93xxx / 0x95xxx)を読み込んで表引き(0x2068 = 2D / 0x20DC = 3D)を呼ぶ箇所を探し、
  X 入力(fr4)と Y 入力(fr5)にどの RAM が入るかを、短い区間の記号実行で求める。

求め方の要点:
  - 記述子: 3D = [u16 nx, u16 ny, u32 X軸, u32 Y軸, u32 データ](20 バイト)、2D = [u16 n, u16 0, u32 軸, u32 データ]。
  - 呼び出しの直前 400 バイトから、mov.l の定数・fmov.s @Rn・読み取りヘルパ(0x1B984 / 0x1BB62 = float、
    0x2500 / 0x24C0 = u8 / u16 を float に)を追う。分岐はたどらない(直線で読む)ので、求まらない表もある。
  - RAM の float をそのまま、またはヘルパ経由で渡している場合だけを採る(計算式や監視側の構造体経由は採らない)。
  - 安全監視側(0xAE000〜0xB7000)は、制御側の RAM の番地を表 0xF4000 から取り出して読む(mov.l @(r0,rN))。その番地も追う。
コード部(0x2000〜0xB8000)は ROM 3 本で同じ(運用中 ROM のパッチ 12 バイトを除く)なので、結果は 3 本に共通。
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ncecu import ltdef  # noqa: E402

ROM = ROOT / "rom_data" / "ecu_readout_yahooauction.bin"
OUT = ROOT / "ncecu" / "axis_ram.py"
CAL_LO, CAL_HI = 0xB8000, 0xFC000
LOOKUP = {0x2068: "2D", 0x20DC: "3D"}
BACK = 400                          # 表引きの呼び出しの何バイト前から追うか
MON_CODE = (0xAE000, 0xB7000)       # 安全監視側のコード
MON_PTRS = 0xF4000                  # 監視側が読む制御側 RAM の番地の表(監視側は @(r0, この表) で番地を取り出す)
ACC_F = (0x1B984, 0x1BB62)          # float を返す読み取りヘルパ(r4 = 番地)
CONV = {0x2500: "u8", 0x24C0: "u16"}  # 整数(r4 = 値)を float にする(fr4 = 倍率, fr5 = 加算)

D = b""


def u16(o):
    return struct.unpack(">H", D[o:o + 2])[0]


def u32(o):
    return struct.unpack(">I", D[o:o + 4])[0]


def f32(o):
    return struct.unpack(">f", D[o:o + 4])[0]


def _cal(p):
    return CAL_LO <= p < CAL_HI


def _ascending(ptr, n):
    if not _cal(ptr) or ptr % 4 or n < 2 or n > 200:
        return False
    v = [f32(ptr + 4 * i) for i in range(n)]
    return all(x == x and abs(x) < 1e7 for x in v) and all(v[i] < v[i + 1] for i in range(n - 1))


def descriptors():
    """記述子の番地 -> (データ, [(軸の番地, 入力の位置 'x'|'y')])"""
    out = {}
    for o in range(0x80000, 0xB8000, 2):
        nx, ny = u16(o), u16(o + 2)
        p1, p2, p3 = u32(o + 4), u32(o + 8), u32(o + 12)
        if 2 <= nx <= 200 and 2 <= ny <= 200 and _cal(p3) and _ascending(p1, nx) and _ascending(p2, ny):
            out[o] = (p3, [(p1, "x"), (p2, "y")])
        elif 2 <= nx <= 200 and _cal(p2) and _ascending(p1, nx) and ny in (0, 0x0D00, 0x0D):
            out[o] = (p2, [(p1, "x")])
    return out


def literal_sites():
    idx = {}
    for a in range(0, 0xB8000, 2):
        op = u16(a)
        if (op >> 12) == 0xD:
            t = ((a + 4) & ~3) + ((op & 0xFF) << 2)
            if t + 4 <= len(D):
                idx.setdefault(u32(t), []).append(a)
    return idx


def _ram_of(reg):
    """レジスタの中身が RAM 番地の定数なら、その番地"""
    if reg and reg[0] == "lit" and reg[1] >= 0xFFFF0000:
        return reg[1]
    return None


def track(start, stop):
    """[start, stop] を直線で記号実行し、表引きの呼び出しごとに (r4, fr4, fr5) を返す。
    値の表し方: ("ram", 番地) = その RAM の値 / それ以外 = 採らない。"""
    r = [None] * 16
    fr = [None] * 16
    fpul = None
    found = []
    pending = None
    a = start
    while a <= stop:
        op = u16(a)
        hi, n, m, lo = op >> 12, (op >> 8) & 0xF, (op >> 4) & 0xF, op & 0xF
        is_call = False
        if hi == 0xD:
            r[n] = ("lit", u32(((a + 4) & ~3) + ((op & 0xFF) << 2)))
        elif hi == 0x9:
            v = u16(a + 4 + ((op & 0xFF) << 1))
            r[n] = ("lit", v - 0x10000 if v & 0x8000 else v)
        elif hi == 0xE:
            i = op & 0xFF
            r[n] = ("lit", i - 256 if i & 0x80 else i)
        elif hi == 0x7:
            i = op & 0xFF
            i = i - 256 if i & 0x80 else i
            r[n] = ("lit", r[n][1] + i) if r[n] and r[n][0] == "lit" else None
        elif op & 0xFF00 == 0xC700:
            r[0] = ("lit", ((a + 4) & ~3) + ((op & 0xFF) << 2))
        elif hi == 0x6 and lo == 3:
            r[n] = r[m]
        elif hi == 0x6 and lo in (0, 1, 2):
            ram = _ram_of(r[m])
            r[n] = ("int", ram, "bwl"[lo]) if ram else None
        elif hi == 0x6:
            r[n] = None
        elif hi == 0x0 and lo == 0xE:                      # mov.l @(R0,Rm),Rn
            r[n] = None
            if MON_CODE[0] <= a < MON_CODE[1] and r[0] and r[0][0] == "lit" and 0 <= r[0][1] < 0x400 and r[0][1] % 4 == 0:
                v = u32(MON_PTRS + r[0][1])
                if v >= 0xFFFF0000:
                    r[n] = ("lit", v)
        elif hi == 0x4 and lo == 0xB and m == 0:          # jsr @Rn
            pending, is_call = r[n], True
        elif hi == 0x4 and (op & 0xFF) == 0x5A:           # lds Rm,FPUL
            fpul = r[n]
        elif hi == 0xB:                                    # bsr
            d = op & 0xFFF
            pending, is_call = ("lit", a + 4 + 2 * (d - 0x1000 if d & 0x800 else d)), True
        elif hi == 0xF:
            if lo in (8, 9):                               # fmov.s @Rm(+),FRn
                ram = _ram_of(r[m])
                fr[n] = ("ram", ram) if ram else None
                if lo == 9:
                    r[m] = ("lit", r[m][1] + 4) if r[m] and r[m][0] == "lit" else None
            elif lo == 0xC:
                fr[n] = fr[m]
            elif lo in (0, 1, 2, 3, 6, 0xE):
                fr[n] = None
            elif lo == 0xD:
                if m in (2, 4, 5, 8, 9):
                    fr[n] = None
                elif m == 1:
                    fpul = fr[n]
        elif op == 0x000B:                                 # rts: 関数の終わり
            r, fr = [None] * 16, [None] * 16
        if pending is not None and not is_call:            # 遅延スロットの後で呼び出しを反映
            tgt = pending[1] if pending[0] == "lit" else None
            if tgt in LOOKUP:
                found.append((r[4], fr[4], fr[5]))
            nfr0 = None
            if tgt in ACC_F:
                ram = _ram_of(r[4])
                nfr0 = ("ram", ram) if ram else None
            elif tgt in CONV and r[4] and r[4][0] == "int":
                nfr0 = ("ram", r[4][1])
            for i in range(0, 8):
                r[i] = None
            for i in range(0, 12):
                fr[i] = None
            fr[0] = nfr0
            pending = None
        a += 2
    return found


def resolve():
    """表データの番地 -> {軸の番地: (RAM 番地, …)}"""
    lits = literal_sites()
    out = {}
    for daddr, (data, axes) in sorted(descriptors().items()):
        for site in lits.get(daddr, []):
            for r4, x, y in track(max(0, site - BACK), site + 40):
                if not (r4 and r4[0] == "lit" and r4[1] == daddr):
                    continue
                for ax_addr, which in axes:
                    v = x if which == "x" else y
                    if v and v[0] == "ram" and isinstance(v[1], int):
                        s = out.setdefault(data, {}).setdefault(ax_addr, [])
                        if v[1] not in s:
                            s.append(v[1])
    return out


def render(res, romdef):
    defined = {}
    for t in romdef.tables:
        for ax in t.axes:
            if ax.address:
                defined.setdefault(t.address, set()).add(ax.address)
    lines = [
        '"""マップの軸の入力 RAM(この ROM での実番地)。tools/gen_axis_ram.py が ROM のコードから生成する。手で直さない。',
        "",
        "TABLE_INPUTS[表データの番地][軸の番地] = (RAM 番地, …)",
        "  表引き(0x2068 / 0x20DC)の呼び出しで、その軸の入力(fr4 = X, fr5 = Y)に渡している RAM 変数。",
        "  LibreTuner の軸名の末尾(例 RPM_6DD8)は別 ROM の番地なので、この ROM の RAM を探すときはこちらを使う。",
        "  コードを直線で読んで求めたもので、計算式や構造体経由で渡す軸は含まない(載っていない = 未解決)。",
        "  監視側が表 0xF4000 から取り出して読む制御側の RAM は含む。",
        '"""',
        "",
        "TABLE_INPUTS = {",
    ]
    n_tab = n_ax = 0
    for data in sorted(res):
        axes = {a: v for a, v in res[data].items() if a in defined.get(data, ())}
        if not axes:
            continue
        n_tab += 1
        n_ax += len(axes)
        body = ", ".join("0x%05X: (%s,)" % (a, ", ".join("0x%08X" % x for x in sorted(v))) for a, v in sorted(axes.items()))
        lines.append("    0x%05X: {%s}," % (data, body))
    lines += ["}", "", "",
              "def inputs(table_addr, axis_addr):",
              '    """その表のその軸に入る RAM 番地のタプル。分からなければ空。"""',
              "    return TABLE_INPUTS.get(table_addr, {}).get(axis_addr, ())",
              "", "",
              "def tables_reading(ram):",
              '    """その RAM 変数を軸の入力に使う表データの番地の集合。"""',
              "    return {t for t, axes in TABLE_INPUTS.items() if any(ram in v for v in axes.values())}",
              ""]
    return "\n".join(lines), n_tab, n_ax


def main():
    global D
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    D = ROM.read_bytes()
    romdef = ltdef.parse(ROOT / "defs/libretuner/main.json", ROOT / "defs/libretuner/LFG7EG.json")
    text, n_tab, n_ax = render(resolve(), romdef)
    if a.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("axis_ram.py は生成結果と%s" % ("同じ" if same else "違う"))
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("%s を書いた: %d 表 / %d 軸" % (OUT.relative_to(ROOT), n_tab, n_ax))
    return 0


if __name__ == "__main__":
    sys.exit(main())
