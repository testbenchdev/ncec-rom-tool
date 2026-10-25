"""電子スロットル(DBW)のペダルマップ(APP→スロットル開度)を 1:1 寄りに立てて、
ワイヤースロットル風のハイレスポンス特性にする。

★ 実車の走行フィールに直結する変更。予備/ベンチECUで確認し、元ROMは必ず保管すること。
  スロットルは物理上100%(約85°)以上は開かない＝到達の速さ/付きが変わるだけで、全開時の空気量は増えない。

対象(2026-10-20 ブロック探索で確定):
  ペダルマップ APP%(18) × RPM(10) の720Bブロックが、**制御**と**安全監視(Data Integrity)**で
  完全同一に二重化されている。片方だけ変えると監視が不一致を検出しフェイルセーフ(スロットルを絞る)
  になるため、**必ず両方**を同じ値にする。
    1速     制御 @0xC7EE4 / 監視 @0xF7C90
    2速     制御 @0xC81B4 / 監視 @0xF7F60
    3速     制御 @0xC8484 / 監視 @0xF8230
    4〜6速  制御 @0xC8754 / 監視 @0xF8500
    ニュートラル 制御 @0xC8A24 / 監視 @0xF87D0   (1速と同一内容)
  上限(Data Integrity Checks - DBW Throttle Duty Commanded Limits - Maximum, 9値)も
  制御/監視で二重化: @0xC55FC / @0xF7C24。

方式:
  各セル new = stock*(1-blend) + APP軸値*blend （0〜100でクランプ）。
  blend=1.0 で完全 1:1(スロットル% = アクセル%、全ギア共通)。blend=0 で純正。
  1:1 は純正の上限ライン上(中〜高ペダルで余裕ゼロ)に乗るため、監視の誤フォルト防止に
  上限を cap_margin[%] だけ引き上げる(既定10、0で据え置き、100でクランプ)。
  ※ WIP/ブレーキ/フォルト時などの特殊ペダルマップは安全側なので変更しない。
"""
from __future__ import annotations

import struct

from . import checksum

ROWS, COLS = 10, 18
BLOCK = ROWS * COLS * 4                      # 720B
APP_AXIS_ADDR = 0xD9BF0                      # APP軸(18 float BE, 0..100%)

# (ギア, 制御アドレス, 監視アドレス)
GEAR_PAIRS = [
    ("1st", 0xC7EE4, 0xF7C90),
    ("2nd", 0xC81B4, 0xF7F60),
    ("3rd", 0xC8484, 0xF8230),
    ("4-6", 0xC8754, 0xF8500),
    ("Neutral", 0xC8A24, 0xF87D0),
]
PEDAL_ADDRS = [a for _, c, m in GEAR_PAIRS for a in (c, m)]
CAP_ADDRS = [0xC55FC, 0xF7C24]               # Throttle Duty Commanded - Maximum (9値) 制御/監視
CAP_N = 9

ROM_SIZE = 0x100000


def _f(b, o):
    return struct.unpack(">f", bytes(b[o:o + 4]))[0]


def app_axis(data) -> list[float]:
    return [_f(data, APP_AXIS_ADDR + 4 * i) for i in range(COLS)]


def read_block(data, addr):
    return [[_f(data, addr + 4 * (r * COLS + c)) for c in range(COLS)] for r in range(ROWS)]


def _looks_like_pedal_map(data, addr) -> bool:
    b = read_block(data, addr)
    flat = [v for row in b for v in row]
    if not all(-1.0 <= v <= 101.0 for v in flat):
        return False
    # ペダルマップの署名: 各行はアクセル増で非減少、先頭は閉(≒0)、全開近くは50%以上開く。
    # (2速は低回転で50%上限にクランプされるので「≧80」ではなく「≧49」)
    for row in b:
        if row[0] > 5.0 or row[-1] < 49.0:
            return False
        if any(row[c + 1] < row[c] - 0.5 for c in range(COLS - 1)):
            return False
    return True


def _axis_ok(data) -> bool:
    ax = app_axis(data)
    if abs(ax[0]) > 0.1 or abs(ax[-1] - 100.0) > 0.1:
        return False
    return all(ax[i + 1] > ax[i] for i in range(COLS - 1))


def verify_base(data) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"ROMサイズが不正: {len(data)}")
    if not _axis_ok(data):
        raise ValueError(f"APP軸(@0x{APP_AXIS_ADDR:X})が想定(0→100の昇順18点)と異なる(未対応ROM?)")
    for addr in PEDAL_ADDRS:
        if not _looks_like_pedal_map(data, addr):
            raise ValueError(f"@0x{addr:X} がペダルマップに見えない(未対応ROM?)")
    # 制御==監視 を確認(純正はこの不変条件を満たす)
    for g, c, m in GEAR_PAIRS:
        if read_block(data, c) != read_block(data, m):
            raise ValueError(f"{g}: 制御@0x{c:X} と監視@0x{m:X} が不一致(ベースが破損/改変済み?)")


def build(base: bytes, blend: float = 1.0, cap_margin: float = 10.0,
          keep_idle_cols: int = 0) -> bytearray:
    """base に 1:1 寄りのペダルマップを適用した ROM(チェックサム補正済み)を返す。"""
    if not 0.0 <= blend <= 1.0:
        raise ValueError("blend は 0〜1")
    if not 0.0 <= cap_margin <= 100.0:
        raise ValueError("cap_margin は 0〜100")
    verify_base(base)
    rom = bytearray(base)
    axis = app_axis(base)

    for addr in PEDAL_ADDRS:
        for r in range(ROWS):
            for c in range(COLS):
                o = addr + 4 * (r * COLS + c)
                stock = _f(base, o)
                target = axis[c]
                if c < keep_idle_cols:          # アイドル直上を純正のまま残すオプション
                    new = stock
                else:
                    new = stock * (1.0 - blend) + target * blend
                new = min(100.0, max(0.0, new))
                rom[o:o + 4] = struct.pack(">f", new)

    if cap_margin > 0:
        for addr in CAP_ADDRS:
            for i in range(CAP_N):
                o = addr + 4 * i
                v = min(100.0, _f(base, o) + cap_margin)
                rom[o:o + 4] = struct.pack(">f", v)

    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise ValueError("チェックサム補正に失敗")
    return rom


def verify_result(base: bytes, rom: bytes, blend: float = 1.0, cap_margin: float = 10.0,
                  keep_idle_cols: int = 0) -> None:
    """生成結果の自己検証: 制御==監視 / 値が設計どおり / 1:1は上限内。"""
    axis = app_axis(base)
    for g, c, m in GEAR_PAIRS:
        if read_block(rom, c) != read_block(rom, m):
            raise AssertionError(f"{g}: 制御/監視が不一致")
    # ペダル値の確認
    for addr in PEDAL_ADDRS:
        b0 = read_block(base, addr)
        b1 = read_block(rom, addr)
        for r in range(ROWS):
            for c in range(COLS):
                exp = b0[r][c] if c < keep_idle_cols else min(100.0, max(0.0,
                      b0[r][c] * (1 - blend) + axis[c] * blend))
                if abs(b1[r][c] - exp) > 1e-3:
                    raise AssertionError(f"@0x{addr:X}[{r}][{c}] {b1[r][c]} != {exp}")
    # 1:1(blend=1)なら上限内か
    if blend >= 1.0:
        for addr in CAP_ADDRS:
            cap = [_f(rom, addr + 4 * i) for i in range(CAP_N)]
            capx = [0.0, 12.5, 25.0, 37.5, 50.0, 62.5, 75.0, 87.5, 100.0]
            for x, cmax in zip(capx, cap):
                if x > cmax + 1e-6:
                    raise AssertionError(f"1:1 がMax上限超過: APP{x} > {cmax} @0x{addr:X}")
    if not checksum.all_valid(rom):
        raise AssertionError("チェックサム不正")
