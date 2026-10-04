"""NCEC ROM チェックサム検証・再計算。

チェックサムテーブル: 0xFF650 以降、12バイト/エントリ = (start, end, stored) の 32bit BE 3語。
各領域で「32bitワード和 + stored = MAGIC(0x5AA5A55A)」が成立する。
編集後は各領域の stored を (MAGIC - ワード和) に再設定して整合させる。
"""
from __future__ import annotations

MAGIC = 0x5AA5A55A
TABLE_START = 0xFF650
TABLE_END = 0xFF7FC
ENTRY = 12
M = 0xFFFFFFFF


def _w32(d, o):
    return int.from_bytes(d[o:o + 4], "big")


def entries(data) -> list[tuple[int, int, int]]:
    out = []
    o = TABLE_START
    while o < TABLE_END:
        s, e, c = _w32(data, o), _w32(data, o + 4), _w32(data, o + 8)
        if s == 0xFFFFFFFF or s > e or e >= len(data):
            break
        out.append((s, e, c))
        o += ENTRY
    return out


def wordsum(data, s, e) -> int:
    acc = 0
    for a in range(s, e + 1, 4):
        acc = (acc + _w32(data, a)) & M
    return acc


def verify(data) -> list[tuple[int, int, bool]]:
    """各領域 (start, end, ok) を返す。"""
    res = []
    for s, e, c in entries(data):
        ok = ((wordsum(data, s, e) + c) & M) == MAGIC
        res.append((s, e, ok))
    return res


def all_valid(data) -> bool:
    return all(ok for _, _, ok in verify(data))


def recalculate(data: bytearray) -> list[tuple[int, int, int, int]]:
    """各領域の stored を再計算して書き込む。(start, end, old, new) のリストを返す。"""
    changed = []
    o = TABLE_START
    while o < TABLE_END:
        s, e, old = _w32(data, o), _w32(data, o + 4), _w32(data, o + 8)
        if s == 0xFFFFFFFF or s > e or e >= len(data):
            break
        new = (MAGIC - wordsum(data, s, e)) & M
        if new != old:
            data[o + 8:o + 12] = new.to_bytes(4, "big")
        changed.append((s, e, old, new))
        o += ENTRY
    return changed
