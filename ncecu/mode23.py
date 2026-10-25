"""Mode23(ReadMemoryByAddress)によるライブRAM読み出しの補助と、有効化手順の資料。

このモジュールは **読み出し側(クライアント)** と **有効化パッチの番地資料** のみを提供する。
Mode23の認証を外す**パッチ生成・書き込みはこのツールでは行わない**
（認証無効化＝セキュリティ低下に当たるため）。有効化はユーザが別途行う。

── 有効化パッチ（ユーザが適用する。番地はRE済み・資料のみ）───────────────
  診断ディスパッチ表 @0x84BFC: SID 0x23 → handler 0x7F708 / flags 0x00000006。
  読み出し本体 0x7F874 の範囲チェックは ROM 0..0x100000 と RAM 0xFFFF0000..0xFFFFE000 を許可
  （サイズ 1..0x400）。既定セッションで Mode23 を通すには次の3点を変更する:
    @0x84C04 (flags上位) 0x00 → 0x10
    @0x84C07 (flags下位) 0x06 → 0x0F     … flags = 0x1000000F（Mode22と同じ=既定セッション可）
    @0x7F734 (bf/s=認証NG→NRC33) 0x8F17 → 0x0009 (nop)
  変更後はチェックサム再計算が必要。⚠ 認証なしでRAM/ROMを読める状態になる（書込は別サービスで不可）。
──────────────────────────────────────────────────────────

有効化後は、既定セッションのまま `23 <addr:4 BE> <size:2 BE>` → `63 <data>` でメモリを読める。
ライブRAM計測（KR/クラッチ/EGT等のダッシュボード表示）に使う。
"""
from __future__ import annotations

import struct

ROM_SIZE = 0x100000
RAM_LO, RAM_HI = 0xFFFF0000, 0xFFFFE000
MAX_SIZE = 0x400

# 有効化パッチの番地と値（資料。適用はユーザ側で）。(addr, 純正, 有効化後, 幅)
ENABLE_EDITS = [
    (0x84C04, 0x00, 0x10, 1),
    (0x84C07, 0x06, 0x0F, 1),
    (0x7F734, 0x8F17, 0x0009, 2),
]


def _get(data, addr, width):
    return int.from_bytes(bytes(data[addr:addr + width]), "big")


def is_enabled_rom(data) -> bool:
    """このROMにMode23有効化が当たっているか（判定のみ）。"""
    return len(data) >= 0x84C08 and all(_get(data, a, w) == pv for a, _s, pv, w in ENABLE_EDITS)


def addr_readable(addr: int, size: int = 1) -> bool:
    """この番地・サイズが Mode23 の許可範囲か（ハンドラ 0x7F874 と同じ判定）。"""
    if not 1 <= size <= MAX_SIZE:
        return False
    end = addr + size
    if end <= ROM_SIZE:
        return True
    return RAM_LO <= addr and end <= RAM_HI


def read_request(addr: int, size: int) -> bytes:
    """`23 <addr:4 BE> <size:2 BE>` を組み立てる。"""
    return bytes([0x23]) + (addr & 0xFFFFFFFF).to_bytes(4, "big") + (size & 0xFFFF).to_bytes(2, "big")


def parse_read(resp: bytes | None, size: int) -> bytes | None:
    """応答 `63 <data>` から data を取り出す。失敗は None。"""
    if not resp or resp[0] != 0x63:
        return None
    data = bytes(resp[1:1 + size])
    return data if len(data) == size else None


def decode(data: bytes, typ: str):
    """RAMバイト列を数値へ。u8/u16/s16/u32/s32/f32(いずれもBE)。"""
    if typ == "u8":
        return data[0]
    if typ == "u16":
        return struct.unpack(">H", data[:2])[0]
    if typ == "s16":
        return struct.unpack(">h", data[:2])[0]
    if typ == "u32":
        return struct.unpack(">I", data[:4])[0]
    if typ == "s32":
        return struct.unpack(">i", data[:4])[0]
    if typ == "f32":
        return struct.unpack(">f", data[:4])[0]
    raise ValueError(f"未知の型: {typ}")


_SIZE = {"u8": 1, "u16": 2, "s16": 2, "u32": 4, "s32": 4, "f32": 4}


def type_size(typ: str) -> int:
    return _SIZE[typ]
