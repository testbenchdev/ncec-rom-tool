"""アクセルオフ時の“アンチラグ”＝オーバーランのポップ/バーブル（減速時の「パンパン」）を
純正ECUで作るパッチ。NA(LF-VE)なので本来のアンチラグ(ALS)ではなく“音”を作る機能。

★ 排気管内で燃料を燃やす＝触媒・排気系の熱害。予備/ベンチECUで。公道・法規は自己責任。
  詳細は docs/tuning_overrun_pops_ja.md。番地/寸法は純正ROMと実例 ncec_immo_off_na_anti.bin で確認済み。

鳴る条件は2つ：(1) 減速中に燃料が残る（通常は DFCO=減速燃料カットで切られる）/ (2) 点火が大きく遅角。
3パターン（docs の レシピ A/B/C）：
  A. DFCO無効（全回転バーブル）  : DFCO→無効(常時燃料) ＋ 減速点火遅角を深く
  B. RPMゲート（3000rpm超だけ）★: DFCO有効のまま、減速燃料カット率をRPMで分け(低回転=全カット/高回転=残す) ＋ 遅角
  C. ツキ重視（踏み直しを鋭く）  : 遅角を浅く ＋ 点火/燃料の復帰を速く ＋ DFCO無効
"""
from __future__ import annotations

import struct

from . import checksum

ROM_SIZE = 0x100000

# --- 関連番地（CALID LFG7EG。純正ROM + 実例で寸法確認済み）---
DFCO = 0x45976            # uint16: 36610=有効(純正) / 9=無効(常時燃料)
DFCO_ON, DFCO_OFF = 36610, 9
DECEL_FUELCUT = 0xCC774   # float[6ギア×5RPM] 減速燃料カット エンリーン率(小=燃料残る=ポップ)
FUELCUT_ROWS, FUELCUT_COLS = 6, 5
BASE_RETARD = 0xD23E0     # float[9] 減速点火 遅角(X=コースト経過時間0-16s, 値=遅角°, 大=よく鳴る)
RESTORE_A = 0xD2428       # float[9] 点火復帰レート(大=素早く通常進角へ=ツキ良)
RESTORE_B = 0xD2470       # float[9] 点火復帰レート(別条件)
FUEL_RESTORE_ON = 0xCC6A8   # float 減速燃料 復帰エンリッチ率(ブレーキON)
FUEL_RESTORE_OFF = 0xCC6AC  # float 同(ブレーキOFF) 大=踏み直しで燃料が速く戻る=息つき防止

# --- 各パターンの目標値（docs のレシピに準拠）---
RPM_GATE_ROW = [0.05, 0.05, 0.05, 0.0005, 0.0005]    # 1000/2000/3000=全カット, 4000/5000=残す
RETARD_A = [0.0, 0.0, 10.0, 16.0, 20.0, 22.0, 22.0, 22.0, 22.0]   # 頭打ち~22°
RETARD_B = [0.0, 0.0, 10.0, 15.0, 18.0, 20.0, 20.0, 20.0, 20.0]   # 頭打ち~20°
RETARD_C = [0.0, 0.0, 8.0, 10.0, 12.0, 12.0, 12.0, 12.0, 12.0]    # 浅め~12°
RESTORE_A_FAST = [0.5, 0.8, 1.2, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6]
RESTORE_B_FAST = [0.6, 0.9, 1.2, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6]
FUEL_RESTORE_FAST = 0.02

PATTERNS = ("A", "B", "C")
PATTERN_NAME = {
    "A": ("DFCO無効（全回転バーブル）", "DFCO off (burble at all RPM)"),
    "B": ("RPMゲート（3000rpm超だけ）", "RPM gate (above 3000 rpm)"),
    "C": ("ツキ重視（踏み直しを鋭く）", "Response-focused (sharp tip-in)"),
}


def _f(b, o):
    return struct.unpack(">f", bytes(b[o:o + 4]))[0]


def _u16(b, o):
    return struct.unpack(">H", bytes(b[o:o + 2]))[0]


def _floats(b, o, n):
    return [round(_f(b, o + 4 * i), 6) for i in range(n)]


def verify_base(data: bytes) -> None:
    """このパッチを当てられるROMか（LFG7EG相当の純正構造か）を確認。"""
    if len(data) != ROM_SIZE:
        raise ValueError(f"ROMサイズが不正: {len(data)}")
    dfco = _u16(data, DFCO)
    if dfco not in (DFCO_ON, DFCO_OFF):
        raise ValueError(f"DFCO@0x{DFCO:X}={dfco} が想定外（未対応ROM?）")
    fc = _floats(data, DECEL_FUELCUT, FUELCUT_ROWS * FUELCUT_COLS)
    if not all(0.0 <= v <= 1.0 for v in fc):
        raise ValueError(f"減速燃料カット率@0x{DECEL_FUELCUT:X} が想定範囲外（未対応ROM?）")
    for a, n in ((BASE_RETARD, 9), (RESTORE_A, 9), (RESTORE_B, 9)):
        vs = _floats(data, a, n)
        if not all(-5.0 <= v <= 60.0 for v in vs):
            raise ValueError(f"@0x{a:X} が想定範囲外（未対応ROM?）")


def _edits_for(pattern: str):
    """(name_ja, name_en, addr, kind, new) の並び。kind: 'u16' / 'f1' / 'f9' / 'grid'。"""
    p = pattern.upper()
    if p == "A":
        return [
            ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_OFF),
            ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "f9", RETARD_A),
        ]
    if p == "B":
        grid = RPM_GATE_ROW * FUELCUT_ROWS   # 全ギア行に同じ RPM ゲートを適用
        return [
            ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_ON),
            ("減速燃料カット率(6ギア×5RPM)", "Decel fuel-cut enleanment", DECEL_FUELCUT, "grid", grid),
            ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "f9", RETARD_B),
        ]
    if p == "C":
        return [
            ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "f9", RETARD_C),
            ("点火復帰レートA(9点)", "Spark restore rate A", RESTORE_A, "f9", RESTORE_A_FAST),
            ("点火復帰レートB(9点)", "Spark restore rate B", RESTORE_B, "f9", RESTORE_B_FAST),
            ("燃料復帰エンリッチ(ブレーキON)", "Fuel restore (brake on)", FUEL_RESTORE_ON, "f1", FUEL_RESTORE_FAST),
            ("燃料復帰エンリッチ(ブレーキOFF)", "Fuel restore (brake off)", FUEL_RESTORE_OFF, "f1", FUEL_RESTORE_FAST),
            ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_OFF),
        ]
    raise ValueError(f"未知のパターン: {pattern}")


def _read(data, addr, kind):
    if kind == "u16":
        return _u16(data, addr)
    if kind == "f1":
        return round(_f(data, addr), 6)
    if kind == "f9":
        return _floats(data, addr, 9)
    if kind == "grid":
        return _floats(data, addr, FUELCUT_ROWS * FUELCUT_COLS)
    raise ValueError(kind)


def _write(rom, addr, kind, val):
    if kind == "u16":
        rom[addr:addr + 2] = struct.pack(">H", int(val))
    elif kind == "f1":
        rom[addr:addr + 4] = struct.pack(">f", float(val))
    else:  # f9 / grid
        rom[addr:addr + 4 * len(val)] = struct.pack(f">{len(val)}f", *[float(x) for x in val])


def _fmt(kind, v):
    if kind == "u16":
        return f"{v}（{'有効' if v == DFCO_ON else '無効' if v == DFCO_OFF else '?'}）"
    if kind == "f1":
        return f"{v:g}"
    return "[" + ", ".join(f"{x:g}" for x in v) + "]"


def build(base: bytes, pattern: str) -> tuple[bytearray, list[dict]]:
    """base にアンチラグ(パターン A/B/C)を当てた ROM（チェックサム補正済み）と、
    変更内容のリスト（リザルト表示用）を返す。"""
    verify_base(base)
    rom = bytearray(base)
    changes: list[dict] = []
    for name_ja, name_en, addr, kind, new in _edits_for(pattern):
        before = _read(base, addr, kind)
        _write(rom, addr, kind, new)
        after = _read(rom, addr, kind)
        changes.append({"name": name_ja, "name_en": name_en, "addr": addr, "kind": kind,
                        "before": _fmt(kind, before), "after": _fmt(kind, after),
                        "changed": before != after})
    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise ValueError("チェックサム補正に失敗")
    return rom, changes
