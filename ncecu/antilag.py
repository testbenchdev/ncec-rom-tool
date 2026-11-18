"""アクセルオフ時の“アンチラグ”＝オーバーランのポップ/バーブル（減速時の「パンパン」）を
純正ECUで作るパッチ。NA(LF-VE)なので本来のアンチラグ(ALS)ではなく“音”を作る機能。

★ 排気管内で燃料を燃やす＝触媒・排気系の熱害。予備/ベンチECUで。公道・法規は自己責任。
  番地/寸法は純正ROM(実車・ベンチとも同値)で確認済み。

鳴る条件は2つ：(1) 減速中に燃料が残る（通常は DFCO=減速燃料カットで切られる）/ (2) 点火が大きく遅角。
4パターン：
  A. DFCO無効（全回転バーブル）        : DFCO→無効(常時燃料) ＋ 減速点火遅角を深く
  B. RPMゲート（設定回転以上だけ）★    : DFCO有効のまま、減速燃料カット率を回転数で分ける
                                         (設定回転以下=全カット/それ以上=燃料を残す) ＋ 遅角
  C. RPMゲート＋ツキ重視（DFCO有効）   : B と同じ回転ゲート(DFCO有効のまま)に、浅い遅角＋
                                         点火/燃料の復帰を速く＝踏み直しのツキを優先      [v2.71 新設]
  D. ツキ重視・DFCO無効（旧C）         : 遅角を浅く ＋ 点火/燃料の復帰を速く ＋ DFCO無効  [v2.70までの C]

アンチラグ有効回転数（B・C）:
  減速燃料カット率の表(6ギア×5回転)は回転軸(5点)を補間して引く。ゲートは「回転軸のブレークポイントを
  動かす」ことで任意の回転数に置ける。回転軸 0xCC748 はこの表専用（ROM内の参照は表記述子 0x93E00 の
  1箇所だけ）なので、他のマップには影響しない。
    回転軸 = [x0, x1, gate, gate+GATE_WIDTH, x4]、値 = [全カット, 全カット, 全カット, 残す, 残す]
  → gate 以下は無音、gate を超えると効き始め、gate+1000rpm で完全に有効。
  既定 gate=3000 のとき回転軸は [1000,2000,3000,4000,5000]＝純正の軸そのまま（v2.70 までの B と同一バイト）。
"""
from __future__ import annotations

import struct

from . import checksum

ROM_SIZE = 0x100000

# --- 関連番地（CALID LFG7EG。純正ROMで寸法確認済み）---
DFCO = 0x45976            # uint16: 36610=有効(純正) / 9=無効(常時燃料)
DFCO_ON, DFCO_OFF = 36610, 9
DECEL_FUELCUT = 0xCC774   # float[6ギア×5RPM] 減速燃料カット エンリーン率(小=燃料残る=ポップ)
FUELCUT_ROWS, FUELCUT_COLS = 6, 5
FUELCUT_RPM_AXIS = 0xCC748   # float[5] 上の表の回転軸(純正 1000/2000/3000/4000/5000)。この表専用
FUELCUT_DESC_AXIS_PTR = 0x93E00   # 表記述子の中の「回転軸へのポインタ」(=0x000CC748)。構造チェック用
BASE_RETARD = 0xD23E0     # float[9] 減速点火 遅角(X=0〜16の9点。定義上の軸名は LOAD_DELTA_7C00、値=遅角°, 大=よく鳴る)
RESTORE_A = 0xD2428       # float[9] 点火復帰レート(大=素早く通常進角へ=ツキ良)
RESTORE_B = 0xD2470       # float[9] 点火復帰レート(別条件)
FUEL_RESTORE_ON = 0xCC6A8   # float 減速燃料 復帰エンリッチ率(ブレーキON)
FUEL_RESTORE_OFF = 0xCC6AC  # float 同(ブレーキOFF) 大=踏み直しで燃料が速く戻る=息つき防止

# --- 各パターンの目標値 ---
FUEL_CUT, FUEL_KEEP = 0.05, 0.0005
RPM_GATE_ROW = [FUEL_CUT, FUEL_CUT, FUEL_CUT, FUEL_KEEP, FUEL_KEEP]   # 軸の3点目=gate までカット、4点目から残す
RETARD_A = [0.0, 0.0, 10.0, 16.0, 20.0, 22.0, 22.0, 22.0, 22.0]   # 頭打ち~22°
RETARD_B = [0.0, 0.0, 10.0, 15.0, 18.0, 20.0, 20.0, 20.0, 20.0]   # 頭打ち~20°
RETARD_SHALLOW = [0.0, 0.0, 8.0, 10.0, 12.0, 12.0, 12.0, 12.0, 12.0]    # 浅め~12°(ツキ重視)
RESTORE_A_FAST = [0.5, 0.8, 1.2, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6]
RESTORE_B_FAST = [0.6, 0.9, 1.2, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6]
FUEL_RESTORE_FAST = 0.02

# --- アンチラグ有効回転数(B・C) ---
GATE_DEFAULT = 3000          # 既定=純正の回転軸のまま(3000以下は無音、4000で完全有効)
GATE_LIMITS = (1500, 6000)   # 設定できる範囲[rpm]
GATE_STEP = 100              # 刻み[rpm]
GATE_WIDTH = 1000            # gate から完全有効までの幅[rpm]
GATED = ("B", "C")           # 有効回転数を持つパターン

PATTERNS = ("A", "B", "C", "D")
PATTERN_NAME = {
    "A": ("DFCO無効（全回転バーブル）", "DFCO off (burble at all RPM)"),
    "B": ("RPMゲート（設定回転以上だけ）", "RPM gate (above the set rpm)"),
    "C": ("RPMゲート＋ツキ重視（DFCO有効のまま）", "RPM gate + response-focused (DFCO stays on)"),
    "D": ("ツキ重視・DFCO無効（旧C）", "Response-focused, DFCO off (former C)"),
}


def _f(b, o):
    return struct.unpack(">f", bytes(b[o:o + 4]))[0]


def _u16(b, o):
    return struct.unpack(">H", bytes(b[o:o + 2]))[0]


def _u32(b, o):
    return struct.unpack(">I", bytes(b[o:o + 4]))[0]


def _floats(b, o, n):
    return [round(_f(b, o + 4 * i), 6) for i in range(n)]


def check_gate(gate_rpm) -> int:
    """有効回転数の範囲・刻みを確認して int で返す。範囲外は ValueError。"""
    try:
        g = float(gate_rpm)
    except (TypeError, ValueError):
        raise ValueError(f"アンチラグ有効回転数が数値ではありません: {gate_rpm!r}") from None
    lo, hi = GATE_LIMITS
    if not (lo <= g <= hi):
        raise ValueError(f"アンチラグ有効回転数は {lo}〜{hi} rpm で指定してください（入力 {g:g}）")
    if abs(g / GATE_STEP - round(g / GATE_STEP)) > 1e-9:
        raise ValueError(f"アンチラグ有効回転数は {GATE_STEP} rpm 刻みで指定してください（入力 {g:g}）")
    return int(round(g))


def gate_axis(gate_rpm) -> list[float]:
    """有効回転数 gate に対する回転軸5点 [x0, x1, gate, gate+幅, x4]（単調増加）。
    gate=3000 なら純正と同じ [1000,2000,3000,4000,5000]。"""
    g = check_gate(gate_rpm)
    x1 = min(2000, g - 500)
    x0 = min(1000, x1 - 500)
    x3 = g + GATE_WIDTH
    x4 = max(5000, x3 + 1000)
    axis = [float(x0), float(x1), float(g), float(x3), float(x4)]
    if not all(b > a for a, b in zip(axis, axis[1:])) or axis[0] < 0:
        raise ValueError(f"回転軸が単調増加になりません: {axis}")
    return axis


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
    # 回転軸: 表記述子がこの軸を指していること(構造)＋5点の単調増加(中身)
    if _u32(data, FUELCUT_DESC_AXIS_PTR) != FUELCUT_RPM_AXIS:
        raise ValueError(f"表記述子@0x{FUELCUT_DESC_AXIS_PTR:X} が回転軸0x{FUELCUT_RPM_AXIS:X}を指していません（未対応ROM?）")
    ax = _floats(data, FUELCUT_RPM_AXIS, FUELCUT_COLS)
    if not (all(b > a for a, b in zip(ax, ax[1:])) and 0.0 <= ax[0] and ax[-1] <= 10000.0):
        raise ValueError(f"減速燃料カットの回転軸@0x{FUELCUT_RPM_AXIS:X}={ax} が想定外（未対応ROM?）")
    for a, n in ((BASE_RETARD, 9), (RESTORE_A, 9), (RESTORE_B, 9)):
        vs = _floats(data, a, n)
        if not all(-5.0 <= v <= 60.0 for v in vs):
            raise ValueError(f"@0x{a:X} が想定範囲外（未対応ROM?）")


def _gate_edits(gate_rpm):
    """回転ゲート(B・C共通): DFCO有効＋回転軸＋カット率の表。"""
    grid = RPM_GATE_ROW * FUELCUT_ROWS   # 全ギア行に同じ回転ゲートを適用
    return [
        ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_ON),
        ("減速燃料カットの回転軸(5点)＝有効回転数", "Fuel-cut RPM axis (= active rpm)",
         FUELCUT_RPM_AXIS, "fv", gate_axis(gate_rpm)),
        ("減速燃料カット率(6ギア×5RPM)", "Decel fuel-cut enleanment", DECEL_FUELCUT, "fv", grid),
    ]


def _response_edits():
    """ツキ重視(C・D共通): 浅い遅角＋点火/燃料の復帰を速く。"""
    return [
        ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "fv", RETARD_SHALLOW),
        ("点火復帰レートA(9点)", "Spark restore rate A", RESTORE_A, "fv", RESTORE_A_FAST),
        ("点火復帰レートB(9点)", "Spark restore rate B", RESTORE_B, "fv", RESTORE_B_FAST),
        ("燃料復帰エンリッチ(ブレーキON)", "Fuel restore (brake on)", FUEL_RESTORE_ON, "f1", FUEL_RESTORE_FAST),
        ("燃料復帰エンリッチ(ブレーキOFF)", "Fuel restore (brake off)", FUEL_RESTORE_OFF, "f1", FUEL_RESTORE_FAST),
    ]


def _edits_for(pattern: str, gate_rpm=GATE_DEFAULT):
    """(name_ja, name_en, addr, kind, new) の並び。kind: 'u16' / 'f1' / 'fv'(float配列)。"""
    p = pattern.upper()
    if p == "A":
        return [
            ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_OFF),
            ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "fv", RETARD_A),
        ]
    if p == "B":
        return _gate_edits(gate_rpm) + [
            ("減速点火 遅角(9点)", "Decel spark retard", BASE_RETARD, "fv", RETARD_B),
        ]
    if p == "C":
        return _gate_edits(gate_rpm) + _response_edits()
    if p == "D":
        return _response_edits() + [
            ("DFCO 減速燃料カット", "DFCO decel fuel cut", DFCO, "u16", DFCO_OFF),
        ]
    raise ValueError(f"未知のパターン: {pattern}")


def _read(data, addr, kind, n=1):
    if kind == "u16":
        return _u16(data, addr)
    if kind == "f1":
        return round(_f(data, addr), 6)
    if kind == "fv":
        return _floats(data, addr, n)
    raise ValueError(kind)


def _write(rom, addr, kind, val):
    if kind == "u16":
        rom[addr:addr + 2] = struct.pack(">H", int(val))
    elif kind == "f1":
        rom[addr:addr + 4] = struct.pack(">f", float(val))
    else:  # fv
        rom[addr:addr + 4 * len(val)] = struct.pack(f">{len(val)}f", *[float(x) for x in val])


def _size(kind, val):
    return 2 if kind == "u16" else 4 if kind == "f1" else 4 * len(val)


def _fmt(kind, v):
    if kind == "u16":
        return f"{v}（{'有効' if v == DFCO_ON else '無効' if v == DFCO_OFF else '?'}）"
    if kind == "f1":
        return f"{v:g}"
    return "[" + ", ".join(f"{x:g}" for x in v) + "]"


def verify_result(base: bytes, rom: bytes, pattern: str, gate_rpm=GATE_DEFAULT) -> None:
    """パッチ結果の検査: 変わってよいのは「このパターンの編集番地」と「チェックサム表」だけ。"""
    allowed = bytearray(ROM_SIZE)
    for _ja, _en, addr, kind, new in _edits_for(pattern, gate_rpm):
        n = _size(kind, new)
        allowed[addr:addr + n] = b"\x01" * n
    lo, hi = checksum.TABLE_START, 0xFF800      # チェックサム表(他のパッチモジュールと同じ範囲)
    allowed[lo:hi] = b"\x01" * (hi - lo)
    bad = [i for i in range(ROM_SIZE) if base[i] != rom[i] and not allowed[i]]
    if bad:
        raise ValueError(f"想定外の番地が変化: 0x{bad[0]:X} ほか {len(bad)} バイト")
    if not checksum.all_valid(rom):
        raise ValueError("チェックサムが不正")


def build(base: bytes, pattern: str, gate_rpm=None) -> tuple[bytearray, list[dict]]:
    """base にアンチラグ(パターン A/B/C/D)を当てた ROM（チェックサム補正済み）と、
    変更内容のリスト（リザルト表示用）を返す。gate_rpm=アンチラグ有効回転数(B・Cのみ。None=既定3000)。"""
    verify_base(base)
    p = pattern.upper()
    if p not in PATTERNS:
        raise ValueError(f"未知のパターン: {pattern}")
    gate = check_gate(GATE_DEFAULT if gate_rpm is None else gate_rpm) if p in GATED else GATE_DEFAULT
    rom = bytearray(base)
    changes: list[dict] = []
    for name_ja, name_en, addr, kind, new in _edits_for(p, gate):
        n = len(new) if kind == "fv" else 1
        before = _read(base, addr, kind, n)
        _write(rom, addr, kind, new)
        after = _read(rom, addr, kind, n)
        changes.append({"name": name_ja, "name_en": name_en, "addr": addr, "kind": kind,
                        "before": _fmt(kind, before), "after": _fmt(kind, after),
                        "changed": before != after})
    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise ValueError("チェックサム補正に失敗")
    verify_result(base, rom, p, gate)
    return rom, changes
