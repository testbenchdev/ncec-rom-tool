"""シフトアップ時の回転落ちを速くする（レブハング低減）— **燃料側のみ・監視安全**の DFCO 強化。

== ねらい ==
アクセルを戻した瞬間（クラッチを切ってエンジンがフリー回転する間）に、減速燃料カット(DFCO)を
**より速く・より確実に**効かせて、燃焼トルクを早く消す＝回転落ちを速くする。電子スロットルの開度は
いっさい触らないので、E-Gas L2（スロットルがペダル以上に開くのを防ぐ監視）とは無関係＝弾かれる筋が無い。
燃料を「減らす」方向のみで、増やす側（ブリップ）が L2 で却下されたのと逆＝監視安全。

== なぜ効くか（RE 済み・2026-11-13）==
1. 突入デバウンス 0xC477D（減速状態へ入るのに必要なカウント, uint8=30）。
   コード 0x42620–0x4263E が「カウンタ >= 0xC477D なら減速フラグ=1」を判定（cmp/hs → フラグ書込）。
   このカウントを下げると、リフトから**より少ない周期で**DFCO が立ち上がる＝燃料カットが早い。
   30 のままだと、短いシフト操作の間に減速状態へ入り切らず燃料が流れ続けてレブハングの一因になる。
2. エンリーン率 0xCC774（6ギア×5RPM, float）ほか単値レート。燃料カット乗数は開始 0.6875(0xCC6A4)から
   このレートで毎周期減り、0.6(0xCC690, 全カットしきい値)を割ると全噴射停止。レート大＝全カットに
   早く到達。高回転列は純正で既に 0.05（速い）、低回転列は 0.007（穏やか＝アイドル付近の息つき防止）。

== 触らないもの（失速防止・安全） ==
- 0xC47FC 減速維持の最低回転 2312.5rpm（＝突入にも必要／これ未満で燃料復帰）。失速防止の下限なので
  **変更しない**。回転がこの下へ落ちれば純正どおり燃料が戻る＝回転落ちを速めても失速側は純正の保護のまま。
- Decel Fuel Restore Idle Thresholds（0xC48xx/0xC49xx 推定アイドル回転・復帰判定）および復帰レート
  0xCC6A8/AC ほか。**変更しない**＝エンスト防止ロジックを壊さない。
- 全カットしきい値 0xCC690(0.6) と開始値 0xCC6A4(0.6875) も**変更しない**（カットの“深さ/始点”は純正）。

※ スロットルを閉じる速さ（減速ダッシュポット）はレブハングのもう一つの要因だが、閉ペダルでの
  スロットル目標は純正で既に 0%（APP→TP Desired の APP=0 列が全RPM行 0.0）。残る“ハング”は過渡の
  閉じレート制限で、これは定義済み CAL ではなく DBW/トルク要求経路のコード定数（制御 ~0x939xx /
  監視 ~0x954xx）。アイドル目標スルーレート(0xD6AB8ほか)が監視プロセッサ保護で P0606 却下された
  のと同じ保護クラスにあたる可能性が高く、**本モジュールでは扱わない**（docs/revdrop_ja.md に記録）。

== 安全 ==
- 既定（enter_count/enlean_scale 未指定 or 既定値）は **inert＝純正とバイト等価**。
- 保存時 ncecu.checksum で全領域を自動補正（self-write も通る）。
- 範囲ガード＋ verify_result で、想定番地（0xC477D と 0xCC774/694/698/6A0、チェックサム表）以外は
  一切変化しないことを確認。
- 予備/ベンチECU専用。実車フラッシュはユーザー明示確認のうえ別途。段階的ベンチ手順は
  docs/revdrop_ja.md。
"""
from __future__ import annotations

import struct

from . import checksum

ROM_SIZE = 0x100000

# ---- 番地（CALID LFG7EG。ベンチ純正・実車純正・運用中ROMで同一・確認済み）----
ENTER_COUNT = 0xC477D          # uint8  減速突入に必要なカウント（純正30）小=DFCO突入が速い
ENLEAN_TABLE = 0xCC774         # float[6ギア×5RPM] 減速燃料カット エンリーン率（大=全カットに速く到達）
ENLEAN_ROWS, ENLEAN_COLS = 6, 5
# 単値エンリーン率（In-Gear / Not In-Gear の持続コースト用。6×5 と同じ“全カットへ近づく速さ”）
ENLEAN_SINGLES = (
    (0xCC694, "減速カット率 In-Gear/ブレーキON", "Enlean In-Gear, Brake On"),
    (0xCC698, "減速カット率 In-Gear/ブレーキOFF", "Enlean In-Gear, Brake Off"),
    (0xCC6A0, "減速カット率 Not In-Gear/MT", "Enlean Not In-Gear, MT"),
)

# 触らない（失速防止・カットの深さ）— 参考値。verify_base で純正であることを確認するのに使う。
RPM_FLOOR = 0xC47FC            # float 2312.5rpm（維持最低回転＝失速防止）
FULLCUT_THR = 0xCC690         # float 0.6（全カットしきい値）
FULLCUT_START = 0xCC6A4       # float 0.6875（カット乗数の開始値）

# 適用先 ROM の構造シグネチャ（コードのリテラルプールが想定番地を指すか）
_POOL_CHECK = (
    (0x42670, ENTER_COUNT),    # 減速突入デバウンス判定（cmp/hs カウンタ, *(0xC477D)）
    (0x93E08, ENLEAN_TABLE),   # 燃料カット率テーブル参照
)

STOCK_ENTER_COUNT = 30
ENLEAN_CLAMP_HI = 0.30         # エンリーン率の上限（0.6875→0.6 は 0.0875 なのでこの値で1周期未満＝即カット）
COUNT_LIMITS = (1, 30)         # enter_count の許容範囲
SCALE_LIMITS = (1.0, 8.0)      # enlean_scale の許容範囲（1.0=純正、増やす=速く・減らす方向は非対応）

PRESETS = {
    "off":    {"enter_count": STOCK_ENTER_COUNT, "enlean_scale": 1.0},   # inert（純正等価）
    "mild":   {"enter_count": 8, "enlean_scale": 2.0},                   # 穏やか
    "strong": {"enter_count": 3, "enlean_scale": 3.0},                   # 強め
}


def _f(b, o):
    return struct.unpack(">f", bytes(b[o:o + 4]))[0]


def _u32(b, o):
    return struct.unpack(">I", bytes(b[o:o + 4]))[0]


def _floats(b, o, n):
    return [round(_f(b, o + 4 * i), 6) for i in range(n)]


def verify_base(data) -> None:
    """このパッチを当てられる ROM か（LFG7EG 相当の純正構造か）を確認。違えば ValueError。"""
    if len(data) != ROM_SIZE:
        raise ValueError(f"ROMサイズが不正: {len(data)}")
    for pool, want in _POOL_CHECK:
        got = _u32(data, pool)
        if got != want:
            raise ValueError(
                f"未対応ROM: @0x{pool:X} のリテラルが 0x{want:X} ではありません（0x{got:X}）。"
                f"減速/燃料カットのコード構造が異なります。")
    cnt = data[ENTER_COUNT]
    if not 1 <= cnt <= 60:
        raise ValueError(f"突入カウント@0x{ENTER_COUNT:X}={cnt} が想定外（未対応ROM?）")
    tab = _floats(data, ENLEAN_TABLE, ENLEAN_ROWS * ENLEAN_COLS)
    if not all(0.0 <= v <= 1.0 for v in tab):
        raise ValueError(f"エンリーン率@0x{ENLEAN_TABLE:X} が想定範囲外（未対応ROM?）")
    for addr, *_ in ENLEAN_SINGLES:
        v = _f(data, addr)
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"エンリーン率@0x{addr:X}={v:g} が想定範囲外（未対応ROM?）")
    # 失速防止の下限が純正値であることを確認（壊れた/別物ROMを弾く）
    floor = _f(data, RPM_FLOOR)
    if not 1500.0 <= floor <= 3000.0:
        raise ValueError(f"維持最低回転@0x{RPM_FLOOR:X}={floor:g} が想定外（未対応ROM?）")


def can_apply(data) -> bool:
    try:
        verify_base(data)
    except ValueError:
        return False
    return True


def read(data) -> dict:
    """現在の設定値を返す。"""
    return {
        "enter_count": int(data[ENTER_COUNT]),
        "enlean_table": _floats(data, ENLEAN_TABLE, ENLEAN_ROWS * ENLEAN_COLS),
        "singles": {f"0x{a:X}": round(_f(data, a), 6) for a, *_ in ENLEAN_SINGLES},
    }


def is_stock(data) -> bool:
    """純正（このツール未適用）相当か。enter_count と単値レートで判定。"""
    cur = read(data)
    singles_stock = {"0xCC694": 0.007, "0xCC698": 0.015, "0xCC6A0": 0.007}
    return (cur["enter_count"] == STOCK_ENTER_COUNT
            and all(abs(cur["singles"][k] - v) < 1e-6 for k, v in singles_stock.items()))


def check_params(enter_count, enlean_scale) -> None:
    lo, hi = COUNT_LIMITS
    if not (lo <= int(enter_count) <= hi):
        raise ValueError(f"enter_count={enter_count} は範囲外（{lo}〜{hi}）")
    lo, hi = SCALE_LIMITS
    if not (lo <= float(enlean_scale) <= hi):
        raise ValueError(f"enlean_scale={enlean_scale} は範囲外（{lo:g}〜{hi:g}）")


def preset(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"未知のプリセット: {name}（{', '.join(PRESETS)}）")
    return dict(PRESETS[name])


def _scaled(v: float, scale: float) -> float:
    return round(min(ENLEAN_CLAMP_HI, v * scale), 6)


def build(base: bytes, *, enter_count=None, enlean_scale=1.0) -> tuple[bytearray, list[dict]]:
    """回転落ち高速化（DFCO 強化）を当てた ROM（チェックサム補正済み）と変更一覧を返す。

    enter_count: 減速突入に必要なカウント（None=現在値維持）。小さいほど DFCO が速く入る。
    enlean_scale: エンリーン率の倍率（1.0=純正=inert）。大きいほど全カットに速く到達。
    既定（enter_count=None, enlean_scale=1.0）は純正とバイト等価。"""
    verify_base(base)
    if enter_count is None:
        enter_count = int(base[ENTER_COUNT])
    check_params(enter_count, enlean_scale)
    enter_count = int(enter_count)
    enlean_scale = float(enlean_scale)

    rom = bytearray(base)
    changes: list[dict] = []

    # 1) 突入カウント
    before = int(base[ENTER_COUNT])
    rom[ENTER_COUNT] = enter_count & 0xFF
    changes.append({"name": "減速突入カウント", "name_en": "Decel enter count",
                    "addr": ENTER_COUNT, "kind": "u8",
                    "before": str(before), "after": str(enter_count),
                    "changed": before != enter_count})

    # 2) エンリーン率テーブル（6×5）
    tab_before = _floats(base, ENLEAN_TABLE, ENLEAN_ROWS * ENLEAN_COLS)
    tab_after = [_scaled(v, enlean_scale) for v in tab_before]
    rom[ENLEAN_TABLE:ENLEAN_TABLE + 4 * len(tab_after)] = struct.pack(
        f">{len(tab_after)}f", *tab_after)
    changes.append({"name": "減速カット率(6ギア×5RPM)", "name_en": "Decel enleanment rate grid",
                    "addr": ENLEAN_TABLE, "kind": "grid",
                    "before": "[" + ", ".join(f"{v:g}" for v in tab_before) + "]",
                    "after": "[" + ", ".join(f"{v:g}" for v in tab_after) + "]",
                    "changed": tab_before != tab_after})

    # 3) 単値エンリーン率
    for addr, nm_ja, nm_en in ENLEAN_SINGLES:
        b = round(_f(base, addr), 6)
        a = _scaled(b, enlean_scale)
        rom[addr:addr + 4] = struct.pack(">f", a)
        changes.append({"name": nm_ja, "name_en": nm_en, "addr": addr, "kind": "f1",
                        "before": f"{b:g}", "after": f"{a:g}", "changed": b != a})

    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise ValueError("チェックサム補正に失敗")
    verify_result(base, rom, enter_count=enter_count, enlean_scale=enlean_scale)
    return rom, changes


def verify_result(base, rom, *, enter_count, enlean_scale) -> None:
    """build の結果が設計どおりか（想定番地のみ変化・値が一致・不変条件）を確認。違えば ValueError。"""
    verify_base(rom)
    if rom[ENTER_COUNT] != (int(enter_count) & 0xFF):
        raise ValueError("突入カウントの書込結果が不一致")
    # 触らないはずの番地が純正のまま
    for addr, want, lo, hi in (
        (RPM_FLOOR, None, 1500.0, 3000.0),
        (FULLCUT_THR, 0.6, 0.0, 1.0),
        (FULLCUT_START, 0.6875, 0.0, 1.0),
    ):
        if _f(base, addr) != _f(rom, addr):
            raise ValueError(f"触ってはいけない番地が変化: 0x{addr:X}")
    # 変化が許される番地の集合
    allowed = set(range(ENTER_COUNT, ENTER_COUNT + 1))
    allowed.update(range(ENLEAN_TABLE, ENLEAN_TABLE + 4 * ENLEAN_ROWS * ENLEAN_COLS))
    for addr, *_ in ENLEAN_SINGLES:
        allowed.update(range(addr, addr + 4))
    cs_lo, cs_hi = checksum.TABLE_START, 0xFF800
    for i, (x, y) in enumerate(zip(base, rom)):
        if x != y and i not in allowed and not cs_lo <= i < cs_hi:
            raise ValueError(f"想定外の番地が変化しました: 0x{i:X}")


def changes_for(base, rom) -> list[dict]:
    """エディタのリザルト表示用（base→rom の差分を直接作る。build の changes と同形式）。"""
    out = []
    b = int(base[ENTER_COUNT]); a = int(rom[ENTER_COUNT])
    out.append({"name": "減速突入カウント", "addr": ENTER_COUNT,
                "before": str(b), "after": str(a), "changed": b != a})
    tb = _floats(base, ENLEAN_TABLE, ENLEAN_ROWS * ENLEAN_COLS)
    ta = _floats(rom, ENLEAN_TABLE, ENLEAN_ROWS * ENLEAN_COLS)
    out.append({"name": "減速カット率(6ギア×5RPM)", "addr": ENLEAN_TABLE,
                "before": "[" + ", ".join(f"{v:g}" for v in tb) + "]",
                "after": "[" + ", ".join(f"{v:g}" for v in ta) + "]", "changed": tb != ta})
    for addr, nm_ja, _ in ENLEAN_SINGLES:
        bb = round(_f(base, addr), 6); aa = round(_f(rom, addr), 6)
        out.append({"name": nm_ja, "addr": addr, "before": f"{bb:g}", "after": f"{aa:g}",
                    "changed": bb != aa})
    return out
