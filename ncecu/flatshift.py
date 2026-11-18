"""フラットシフト関連: 点火カット/遅角パッチ（第6ドラフト＝スクラッチ無し・読み取り専用）と、エディタ用の追加定義。

★ 点火制御を書き換えるカスタムファームウェア。生成物は「ベンチ検証用ドラフト」扱い。実走前にベンチ/予備ECUで確認必須。

== 設計（第6ドラフト）==
実車で「安定して書き込める空きRAM」が存在しないと判明（Mode23可視RAMは全域が使用中か、走行で書かれる
揮発スタック/バッファ。固定スクラッチ不可。ATUレジスタはMode23で検証できず誤書込=エンジン損傷で不採用）。
→ **RAMにもレジスタにも一切書き込まない読み取り専用設計**に変更。ms窓・ハードタイマ(TCNT2B)・累積・
  cut_activeフラグは廃止。両ケーブが毎回ECU状態を読んでその場で判定する（＝RAM破壊リスク原理ゼロ）。

発動条件（両方式共通。この間だけ発動）:
  クラッチ踏込(0xFFFF7100=1) かつ APP>しきい値 かつ RPM>しきい値 かつ 車速>下限。
  窓時間はクラッチを踏んでいる長さ＝ドライバが制御。RPMしきい値が上限として働く（ソフトリミッタ）。
  test_mode=1 のときは車速ゲートだけ無視し、クラッチ＋APP＋RPM は生かす（停車デバッグ用）。始動／アイドルは
  回転が低くゲート不成立なので発動せず（＝クラッチを踏む始動を妨げない）、停車Nで回転を上げると発動する。

方式（CAL method）:
  0 = 点火遅角: cave1 が最終進角から retard[deg] を引く。下限 floor[deg]（純正の最大リタードに縛られず
      深く＝大遅角もこれで調整）。cave2 は素通り。
  1 = 点火カット（本物のスパーク停止）: cave2 が発火経路のコイル充電ハンドラ 0x19D04 を差し替え、発動中は
      充電をスキップ（コイル未通電＝火花なし）。cave1 は進角を触らない。

== 発火経路 / 注入点 ==
  最終進角 clamp(0x4D9D0→0x2404) → 気筒別点火 → イベント状態機械(設定表 0x2DE98/0x2DEA4 の関数ポインタ)
  → ATU出力でコイル充電/発火。状態機械の充電ハンドラ 0x19D04(ポインタ格納 0x2DEB0)を cave2 へ差し替え。
  ・cave1 = クランプ呼び出しのリテラル @0x4DA98(=0x2404) を cave1(0xDE200)へ。発動中かつ遅角方式なら
    fr4/fr5 を書き換えてから純正クランプ 0x2404 へ末尾ジャンプ。fr5 は jsr遅延スロット0x4D9D2で@r14から
    再ロード済・クランプ後0x4D9D4で上書きされ再利用されないので書換え安全。r13/r14/fr6 不可侵。
  ・cave2 = 0x2DEB0(=0x19D04) を cave2(0xDE400)へ。発動中かつカット方式なら充電本処理を飛ばし、
    0x19D04 の末尾記帳(struct[1]=1/struct[2]=0)だけ行って rts（＝そのサイクルの充電スキップ=火花なし）。
    非発動なら 0x19D04 へそのまま jmp。r4(構造体)・r13/r14 温存。
  ⚠ 「0x19D04 が充電か発火か」「毎サイクル実際にjsrされるか」は実車のみ確認可（スクラッチ無しのため
    skip_count は廃止。確認はタイミングライトで“踏込中に発火が消える”＋RPM低下＋電圧維持で行う）。
    もし効かない/コイル過熱の兆候(電圧ドロップ)があれば別ハンドラへ再フックが必要。tools/flatshift_debug.py 参照。
"""
from __future__ import annotations

import struct

from . import checksum
from .defs import Scaling, Table

CLAMP_LIT = 0x4DA98      # 最終進角クランプ呼び出し(0x4D9D0)が使うリテラル
CLAMP_FUNC = 0x2404      # 純正 clamp(fr4, fr5=min, fr6=max) -> fr0
HANDLER_PTR = 0x2DEB0    # 発火状態機械 設定表の「コイル充電ハンドラ」ポインタ格納番地
H19D04 = 0x00019D04      # そのポインタの純正値（コイル充電スケジューラ本体）
RAM_CPP = 0xFFFF7100     # クラッチスイッチ 踏込=1(実車RAM差分で特定・ROM参照14)
RAM_APP = 0xFFFF56C8     # アクセル開度 [%]
RAM_RPM = 0xFFFF6D5C     # エンジン回転 [rpm]
RAM_VSS = 0xFFFF6D04     # 車速 [km/h]

CAVE = 0xDE200           # ケーブ1（クランプ・フック＝遅角）
CAVE2 = 0xDE400          # ケーブ2（コイル充電ハンドラ差し替え＝カット）
CALS = 0xDE300           # 定数（固定番地）
_CALS_LEN = 0x1C         # CAL 7個(float5 + u32 2 = 28B)

CAL_ADDRS = {
    "app": CALS + 0, "rpm": CALS + 4, "vss": CALS + 8,     # ゲート float
    "retard": CALS + 12, "floor": CALS + 16,               # 遅角量 / 下限(最小進角) float
    "method": CALS + 20,                                   # 0=遅角 1=カット u32
    "test_mode": CALS + 24,                                # 1=車速ゲートだけ無視しクラッチ+回転+アクセルで発動(停車デバッグ) u32
}
_FLOAT_KEYS = ("app", "rpm", "vss", "retard", "floor")
_INT_KEYS = ("method", "test_mode")

LIMITS = {
    "app": (0.0, 100.0), "rpm": (1000.0, 8000.0), "vss": (0.0, 250.0),
    "retard": (0.0, 60.0), "floor": (-30.0, 20.0),
    "method": (0.0, 1.0), "test_mode": (0.0, 1.0),
}
DEFAULTS = {
    "app": 80.0, "rpm": 7000.0, "vss": 10.0,
    "retard": 20.0, "floor": -10.0, "method": 0, "test_mode": 0,
}

# 純正の停車中クラッチ連動スロットルカット（ルーチン 0x097346）の、定義に無い定数
CPP_VSS_THRESHOLD = 0xC53B8
CPP_HYSTERESIS = 0xC53C4

PATCH_CATEGORY = "Patch - Flat Shift"
CPP_CATEGORY = "Engine Limiters - RPM"

_PATCH_ITEMS = [
    ("method", "Flat Shift - Method (0 Retard / 1 Cut)", "%.0f", "uint32"),
    ("test_mode", "Flat Shift - Debug Test Mode (0 off / 1 clutch-only)", "%.0f", "uint32"),
    ("app", "Flat Shift - APP Threshold", "%.1f", "float"),
    ("rpm", "Flat Shift - RPM Threshold", "%.0f", "float"),
    ("vss", "Flat Shift - Vehicle Speed Minimum", "%.1f", "float"),
    ("retard", "Flat Shift - Retard Amount [deg]", "%.1f", "float"),
    ("floor", "Flat Shift - Min Advance Floor [deg]", "%.1f", "float"),
]
_STOCK_ITEMS = [
    ("cpp_vss", CPP_VSS_THRESHOLD, "Rev Limit Throttle Cut | CPP set - Vehicle Speed Threshold",
     "%.1f", (0.0, 300.0)),
    ("cpp_hys", CPP_HYSTERESIS, "Rev Limit Throttle Cut | CPP set - Hysteresis", "%.0f", (0.0, 1000.0)),
]
EXTRA_ADDRS = {CAL_ADDRS[k] for k, *_ in _PATCH_ITEMS} | {a for _, a, *_ in _STOCK_ITEMS}


# ---------- ケーブ・アセンブラ ----------

def _movl(n: int, target: int, at: int) -> int:
    disp = target - ((at + 4) & ~3)
    assert target % 4 == 0 and 0 <= disp < 1024 and disp % 4 == 0, (hex(at), hex(target))
    return 0xD000 | n << 8 | disp // 4


def _bcond(op: int, target: int, at: int) -> int:
    disp = (target - (at + 4)) // 2
    assert -128 <= disp < 128 and (target - at) % 2 == 0, (hex(at), hex(target))
    return op | (disp & 0xFF)


def _bra(target: int, at: int) -> int:
    disp = (target - (at + 4)) // 2
    assert -2048 <= disp < 2048 and (target - at) % 2 == 0, (hex(at), hex(target))
    return 0xA000 | (disp & 0xFFF)


def _assemble(prog, base, pool_vals):
    labels: dict[str, int] = {}
    addr = base
    for ent in prog:
        if ent[0] == "L":
            labels[ent[1]] = addr
        else:
            addr += 2
    pool = ((addr + 3) & ~3)
    lit = {name: pool + 4 * i for i, name in enumerate(pool_vals)}
    code: list[int] = []
    addr = base
    for ent in prog:
        k = ent[0]
        if k == "L":
            continue
        if k == "op":
            code.append(ent[1])
        elif k == "movl":
            code.append(_movl(ent[1], lit[ent[2]], addr))
        elif k == "bt":
            code.append(_bcond(0x8900, labels[ent[1]], addr))
        elif k == "bf":
            code.append(_bcond(0x8B00, labels[ent[1]], addr))
        elif k == "bra":
            code.append(_bra(labels[ent[1]], addr))
        else:
            raise AssertionError(k)
        addr += 2
    pad = (pool - (base + 2 * len(code)))
    blob = struct.pack(f">{len(code)}H", *code) + b"\xff" * pad
    blob += struct.pack(f">{len(pool_vals)}I", *(pool_vals[n] for n in pool_vals))
    return blob, pool


def _cmp(ram, cal, fail_label):
    """RAM値 > しきい値 の1軸比較（不成立で fail_label へ）。r1/fr0/fr1 を潰す。"""
    return [("movl", 1, ram), ("op", 0xF018),              # fr0 = RAM値
            ("movl", 1, cal), ("op", 0xF118),              # fr1 = しきい値
            ("op", 0xF015), ("bf", fail_label)]            # fr0>fr1 でなければ fail


def _cave1_prog():
    # クランプ・フック（遅角）。発動中かつ method==0 のとき fr4-=retard, fr5=floor。末尾で純正クランプへ。
    # ゲート: クラッチ＋APP＋RPM は常時、車速は test_mode==0 のときだけ判定（test_mode=1=停車デバッグ）。
    return [
        ("movl", 1, "method"), ("op", 0x6112), ("op", 0x2118), ("bf", "done"),  # method!=0(カット)→何もしない
        ("movl", 1, "cpp"), ("op", 0x6110), ("op", 0x2118), ("bt", "done"),      # クラッチ0→done
        *_cmp("app", "p_app", "done"),                                           # APP>しきい値
        *_cmp("rpm", "p_rpm", "done"),                                           # RPM>しきい値
        ("movl", 1, "test"), ("op", 0x6112), ("op", 0x2118), ("bf", "apply"),    # test!=0→車速ゲート飛ばす
        *_cmp("vss", "p_vss", "done"),                                           # 車速>下限（test_mode=0のみ）
        ("L", "apply"),
        ("movl", 1, "p_ret"), ("op", 0xF718), ("op", 0xF471),                    # fr7=retard; fr4-=fr7
        ("movl", 1, "p_floor"), ("op", 0xF518),                                  # fr5=floor
        ("L", "done"),
        ("movl", 1, "clamp"), ("op", 0x412B), ("op", 0x0009),                    # jmp clamp
    ]


def _cave2_prog():
    # コイル充電ハンドラ差し替え（カット）。発動中かつ method==1 のとき充電スキップ(記帳のみ)。
    # ゲート: クラッチ＋APP＋RPM は常時、車速は test_mode==0 のときだけ判定（test_mode=1=停車デバッグ）。
    return [
        ("movl", 1, "method"), ("op", 0x6112), ("op", 0x2118), ("bt", "passthru"),  # method0(遅角)→素通り
        ("movl", 1, "cpp"), ("op", 0x6110), ("op", 0x2118), ("bt", "passthru"),     # クラッチ0→素通り
        *_cmp("app", "p_app", "passthru"),                                          # APP>しきい値
        *_cmp("rpm", "p_rpm", "passthru"),                                          # RPM>しきい値
        ("movl", 1, "test"), ("op", 0x6112), ("op", 0x2118), ("bf", "docut"),       # test!=0→車速ゲート飛ばす
        *_cmp("vss", "p_vss", "passthru"),                                          # 車速>下限（test_mode=0のみ）
        ("L", "docut"),
        ("op", 0xE001), ("op", 0x8041),                                             # struct[1]=1
        ("op", 0xE000), ("op", 0x8042),                                             # struct[2]=0
        ("op", 0x000B), ("op", 0x0009),                                             # rts; nop (r0=0)
        ("L", "passthru"),
        ("movl", 1, "h19d04"), ("op", 0x412B), ("op", 0x0009),                      # jmp @0x19D04
    ]


def _cave1_pool():
    return {"method": CAL_ADDRS["method"], "cpp": RAM_CPP, "test": CAL_ADDRS["test_mode"],
            "app": RAM_APP, "p_app": CAL_ADDRS["app"], "rpm": RAM_RPM, "p_rpm": CAL_ADDRS["rpm"],
            "vss": RAM_VSS, "p_vss": CAL_ADDRS["vss"], "p_ret": CAL_ADDRS["retard"],
            "p_floor": CAL_ADDRS["floor"], "clamp": CLAMP_FUNC}


def _cave2_pool():
    return {"method": CAL_ADDRS["method"], "cpp": RAM_CPP, "test": CAL_ADDRS["test_mode"],
            "app": RAM_APP, "p_app": CAL_ADDRS["app"], "rpm": RAM_RPM, "p_rpm": CAL_ADDRS["rpm"],
            "vss": RAM_VSS, "p_vss": CAL_ADDRS["vss"], "h19d04": H19D04}


def assemble_cave1() -> bytes:
    blob, _ = _assemble(_cave1_prog(), CAVE, _cave1_pool())
    assert CAVE + len(blob) <= CALS, (hex(CAVE + len(blob)), hex(CALS))
    return blob


def assemble_cave2() -> bytes:
    blob, _ = _assemble(_cave2_prog(), CAVE2, _cave2_pool())
    return blob


# ---------- ROM への適用 ----------

def _u32(data, a) -> int:
    return struct.unpack(">I", bytes(data[a:a + 4]))[0]


def is_applied(data) -> bool:
    c1, c2 = assemble_cave1(), assemble_cave2()
    return (len(data) > CAVE2 + len(c2)
            and _u32(data, CLAMP_LIT) == CAVE and _u32(data, HANDLER_PTR) == CAVE2
            and bytes(data[CAVE:CAVE + len(c1)]) == c1
            and bytes(data[CAVE2:CAVE2 + len(c2)]) == c2)


def can_apply(data) -> bool:
    c1, c2 = assemble_cave1(), assemble_cave2()
    if not (len(data) > CAVE2 + len(c2)
            and _u32(data, CLAMP_LIT) == CLAMP_FUNC and _u32(data, HANDLER_PTR) == H19D04):
        return False
    return (set(bytes(data[CAVE:CAVE + len(c1)])) == {0xFF}
            and set(bytes(data[CALS:CALS + _CALS_LEN])) == {0xFF}
            and set(bytes(data[CAVE2:CAVE2 + len(c2)])) == {0xFF})


def check_values(**vals) -> None:
    for k, v in vals.items():
        lo, hi = LIMITS[k]
        if not lo <= float(v) <= hi:
            raise ValueError(f"{k}={v} は範囲外（{lo}〜{hi}）")


def build(base: bytes, *, app=None, rpm=None, vss=None, retard=None, floor=None,
          method=None, test_mode=None) -> bytearray:
    """base にパッチを当てた ROM（チェックサム補正済み）を返す。未指定は DEFAULTS。"""
    vals = dict(DEFAULTS)
    for k, v in dict(app=app, rpm=rpm, vss=vss, retard=retard, floor=floor,
                     method=method, test_mode=test_mode).items():
        if v is not None:
            vals[k] = v
    check_values(**vals)
    if not can_apply(base):
        if is_applied(base):
            raise ValueError("このROMには既にパッチが当たっています")
        raise ValueError(f"未対応ROM/別パッチと衝突（@{CLAMP_LIT:#x}/@{HANDLER_PTR:#x}/ケーブ領域を確認）")
    rom = bytearray(base)
    rom[CAVE:CAVE + len(assemble_cave1())] = assemble_cave1()
    rom[CAVE2:CAVE2 + len(assemble_cave2())] = assemble_cave2()
    for k in _FLOAT_KEYS:
        rom[CAL_ADDRS[k]:CAL_ADDRS[k] + 4] = struct.pack(">f", float(vals[k]))
    for k in _INT_KEYS:
        rom[CAL_ADDRS[k]:CAL_ADDRS[k] + 4] = struct.pack(">I", int(round(float(vals[k]))))
    rom[CLAMP_LIT:CLAMP_LIT + 4] = struct.pack(">I", CAVE)
    rom[HANDLER_PTR:HANDLER_PTR + 4] = struct.pack(">I", CAVE2)
    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise ValueError("チェックサム補正に失敗")
    return rom


# ---------- エディタ用の追加定義 ----------

def _table(key, addr, name, category, fmt, lo, hi, storagetype="float"):
    sc = Scaling(name=f"sc::extra::{key}", toexpr="x", frexpr="x", fmt=fmt,
                 storagetype=storagetype, vmin=lo, vmax=hi)
    t = Table(name=name, category=category, ttype="1D", address=addr, elements=1,
              scaling=sc.name, fixed_dims=(1, 1))
    return t, sc


def extra_tables(data) -> list[tuple[Table, Scaling]]:
    out = [_table(k, a, n, CPP_CATEGORY, f, *rng) for k, a, n, f, rng in _STOCK_ITEMS]
    if is_applied(data):
        out += [_table(k, CAL_ADDRS[k], n, PATCH_CATEGORY, f, *LIMITS[k], st)
                for k, n, f, st in _PATCH_ITEMS]
    return out


def strict_range(t: Table) -> tuple[float, float] | None:
    for k, _n, _f, _st in _PATCH_ITEMS:
        if t.address == CAL_ADDRS[k] and t.category == PATCH_CATEGORY:
            return LIMITS[k]
    for _k, a, _n, _f, rng in _STOCK_ITEMS:
        if t.address == a and t.category == CPP_CATEGORY:
            return rng
    return None


def is_extra(t: Table) -> bool:
    return t.address in EXTRA_ADDRS and t.category in (PATCH_CATEGORY, CPP_CATEGORY)
