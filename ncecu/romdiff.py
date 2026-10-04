"""ROM 比較(バイト単位 + テーブル単位)。

- byte_regions: 2つのROMで異なるバイトの連続領域(近接は結合)。
- table_changes: 定義(RomDef)の各テーブルを値比較し、変化したテーブル/セルを列挙。
- compare: 上記をまとめ、フラッシュカウンタ(0xFFB00:8)/チェックサム表(0xFF650:0xFF7FC)の
  変化も分類して返す(= 中身の実質差分と、書込毎に変わる部分を区別する)。
ECU非接触・純関数。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .rom import Rom

FLASH_COUNTER = (0xFFB00, 0xFFB08)
CHECKSUM_TABLE = (0xFF650, 0xFF7FC)


def byte_regions(a: bytes, b: bytes, merge_gap: int = 16) -> list[tuple[int, int]]:
    """異なるバイトの連続領域 [(start, end_excl), ...]。merge_gap 以内の隙間は結合。"""
    n = min(len(a), len(b))
    regions = []
    i = 0
    cur = None
    while i < n:
        if a[i] != b[i]:
            if cur is None:
                cur = [i, i + 1]
            else:
                cur[1] = i + 1
        else:
            if cur is not None and i - cur[1] >= merge_gap:
                regions.append((cur[0], cur[1]))
                cur = None
        i += 1
    if cur is not None:
        regions.append((cur[0], cur[1]))
    if len(a) != len(b):
        regions.append((n, max(len(a), len(b))))
    return regions


def _differ(va, vb) -> bool:
    na = isinstance(va, float) and math.isnan(va)
    nb = isinstance(vb, float) and math.isnan(vb)
    if na and nb:
        return False
    if na != nb:
        return True
    if isinstance(va, float) or isinstance(vb, float):
        return abs(va - vb) > 1e-6
    return va != vb


@dataclass
class TableChange:
    name: str
    category: str
    address: int
    ncells: int
    samples: list[tuple[int, int, object, object]]  # (row, col, old, new)


@dataclass
class DiffResult:
    byte_total: int = 0
    regions: list[tuple[int, int]] = field(default_factory=list)
    counter_changed: bool = False
    checksum_changed: bool = False
    tables: list[TableChange] = field(default_factory=list)
    identical: bool = True


def table_changes(a: bytes, b: bytes, romdef, max_samples: int = 8) -> list[TableChange]:
    ra, rb = Rom(a, romdef), Rom(b, romdef)
    out = []
    for t in romdef.tables:
        try:
            ga, gb = ra.read_table(t), rb.read_table(t)
        except Exception:  # noqa: BLE001
            continue
        samples = []
        ncells = 0
        for i in range(min(len(ga), len(gb))):
            for j in range(min(len(ga[i]), len(gb[i]))):
                if _differ(ga[i][j], gb[i][j]):
                    ncells += 1
                    if len(samples) < max_samples:
                        samples.append((i, j, ga[i][j], gb[i][j]))
        if ncells:
            out.append(TableChange(t.name, t.category, t.address, ncells, samples))
    return out


def _in(region, span) -> bool:
    s, e = span
    for i in range(s, e):
        if i < min(len(region[0]), len(region[1])) and region[0][i] != region[1][i]:
            return True
    return False


def compare(a: bytes, b: bytes, romdef=None, max_samples: int = 8) -> DiffResult:
    res = DiffResult()
    n = min(len(a), len(b))
    res.byte_total = sum(1 for i in range(n) if a[i] != b[i]) + abs(len(a) - len(b))
    res.identical = (res.byte_total == 0)
    res.regions = byte_regions(a, b)
    res.counter_changed = _in((a, b), FLASH_COUNTER)
    res.checksum_changed = _in((a, b), CHECKSUM_TABLE)
    if romdef is not None and not res.identical:
        res.tables = table_changes(a, b, romdef, max_samples)
    return res
