"""フラットシフト用 点火リタード注入パッチ（第3ドラフト・ベンチ検証用）を生成する。

★ 点火制御を書き換えるカスタムファームウェア。生成物は「ベンチ検証用ドラフト」扱い。
  実走前にベンチECUでタイミングライト / Live点火時期PIDによる確認が必須。

点火の経路（2026-10-16 確定）:
  タスク 0x4D8DA: 最終進角 = clamp(0x7AE0+0x7B98+0x7DA4, 最大リタード@0x7AFC, 最大進角@0xCE20C)
                  （helper 0x2404 を 0x4D9D0 で呼ぶ）→ RAM 0xFFFF7AA4
  タスク 0x4D84E: 0x7AA4 → 進角側レート制限 → 0xFFFF7AA0（OBD PID 0x0E の元）
                  → 気筒別補正 @0xCE1F4..0xCE200 を加算 → 気筒別点火値 0xFFFF7AC8/CC/D0/D4
  0x19B44:        気筒別点火値から点火イベント角度を計算（(進角-9.8)*65536 → イベント構造体）
  ※タスク 0x4DD58 の 0xFFFF7AAC/7AB0 はトルクモデル（点火効率）専用で、点火そのものには使われない。

注入点:
  0x4D9D0 のクランプ呼び出しが使うリテラル @0x4DA98 (=0x00002404、読むのは 0x4D9C8 だけ) を
  ケーブへ差し替え、条件成立時は値からリタード量を引いてから 0x2404 へ末尾ジャンプする。
  → リタードはクランプ前に入るので、純正の最大リタード(@0xCE210..)で自動的に下限制限される。
  → 下流（0x7AA0 / 気筒別 / トルクモデル）はすべてリタード後の値を使うので整合が取れる。
  → 特殊モード(0xFFFF7A94 bit7/bit6)の経路はこのクランプを通らないので影響しない。

発動条件（第3ドラフト。すべて成立でリタード）:
  クラッチ踏込  byte  0xFFFF6FCC != 0      （純正 0x0979A0 が使うCPP状態）
  APP > しきい値 float 0xFFFF56C8 [%]       （APP1/APP2合成後の最終ペダル開度 0〜100）
  RPM > しきい値 float 0xFFFF6D5C [rpm]     （OBD PID 0x0C の元）
  車速 > 下限    float 0xFFFF6D04 [km/h]    （OBD PID 0x0D の元）
  ※第2ドラフトが使った純正フラグ 0xFFFF3827 は「クラッチ踏込 かつ 車速<2km/h かつ
    RPM>@0x0C53BC」でしか立たない（停車中専用）ため、走行中のシフトでは使えない。
  ※走行中はクラッチを踏んでも純正のスロットルカットは入らない（CPP-clear=10000rpm）ので
    スロットルは開いたまま。RPMしきい値はリタードによる“ソフトリミッタ”として働き、
    抑えきれない分は純正の燃料カット(MT 7500rpm)が受け止める。

ケーブ (空きROM 0xDE200〜):
  DE200 mov.l  L_CPP,r1 / mov.b @r1,r0 / tst r0,r0 / bt done
  DE208 mov.l  L_APP,r1 / fmov.s @r1,fr0 / mov.l P_APP_THR,r2 / fmov.s @r2,fr1 / fcmp/gt fr1,fr0 / bf done
  DE214 (RPM 同様) / DE220 (車速 同様)
  DE22C mov.l  P_RET,r2 / fmov.s @r2,fr7 / fsub fr7,fr4      ; 値 -= リタード量
  DE232 done: mov.l L_CLAMP,r1 / jmp @r1 / nop                ; 純正クランプへ（戻りは呼び出し元のPR）
  DE238 リテラル: 0xFFFF6FCC 0xFFFF56C8 0xFFFF6D5C 0xFFFF6D04 0x00002404 + 定数4個へのポインタ
  DE260 定数(float): APPしきい値 / RPMしきい値 / 車速下限 / リタード量
  使用レジスタ r0-r2 / fr0,fr1,fr7: 呼び出し元(0x4D9D0)は戻り後に fr0 だけを使い r2 は再ロードする。
  入力 fr5(最大リタード=@0x7AFC)/fr6(最大進角) と r13/r14 には触れない。

使い方:
  python tools/patch_flatshift_retard.py                         # ncec_rom_dump.bin → ncec_flatshift_retard_draft3.bin
  python tools/patch_flatshift_retard.py --base X.bin --out Y.bin --retard 15 --rpm 6800 --app 85 --vss 15
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import checksum  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

CLAMP_LIT = 0x4DA98      # タスク0x4D8DAの最終進角クランプ(0x4D9D0)が使うリテラル
CLAMP_FUNC = 0x2404      # 純正 clamp(fr4, fr5=min, fr6=max) -> fr0
RAM_CPP = 0xFFFF6FCC     # クラッチ(CPP) 踏込=非0
RAM_APP = 0xFFFF56C8     # アクセル開度 [%]
RAM_RPM = 0xFFFF6D5C     # エンジン回転 [rpm]
RAM_VSS = 0xFFFF6D04     # 車速 [km/h]
CAVE = 0xDE200
POOL = CAVE + 0x38
CALS = CAVE + 0x60       # APPしきい値 / RPMしきい値 / 車速下限 / リタード量 (float x4)
CAVE_END = CALS + 16

# 生成物の検証・エディタ表示用に定数の番地を公開
CAL_ADDRS = {"app": CALS, "rpm": CALS + 4, "vss": CALS + 8, "retard": CALS + 12}
LIMITS = {"app": (0.0, 100.0), "rpm": (3000.0, 7500.0), "vss": (0.0, 250.0), "retard": (0.0, 30.0)}


def _movl(n: int, target: int, at: int) -> int:
    disp = target - ((at + 4) & ~3)
    assert target % 4 == 0 and 0 <= disp < 1024 and disp % 4 == 0, (hex(at), hex(target))
    return 0xD000 | n << 8 | disp // 4


def _bcond(op: int, target: int, at: int) -> int:
    disp = (target - (at + 4)) // 2
    assert -128 <= disp < 128 and (target - at) % 2 == 0, (hex(at), hex(target))
    return op | (disp & 0xFF)


def assemble() -> bytes:
    """ケーブのコード＋リテラルプール（定数本体は含まない）を組み立てる。"""
    lit = {name: POOL + 4 * i for i, name in enumerate(
        ("cpp", "app", "rpm", "vss", "clamp", "p_app", "p_rpm", "p_vss", "p_ret"))}
    done = CAVE + 0x32
    code = []

    def emit(fn):
        code.append(fn(CAVE + 2 * len(code)))

    emit(lambda a: _movl(1, lit["cpp"], a))
    emit(lambda a: 0x6010)                     # mov.b @r1,r0
    emit(lambda a: 0x2008)                     # tst r0,r0
    emit(lambda a: _bcond(0x8900, done, a))    # bt done
    for ram, cal in (("app", "p_app"), ("rpm", "p_rpm"), ("vss", "p_vss")):
        emit(lambda a, r=ram: _movl(1, lit[r], a))
        emit(lambda a: 0xF018)                 # fmov.s @r1,fr0
        emit(lambda a, c=cal: _movl(2, lit[c], a))
        emit(lambda a: 0xF128)                 # fmov.s @r2,fr1
        emit(lambda a: 0xF015)                 # fcmp/gt fr1,fr0  (T = fr0 > fr1)
        emit(lambda a: _bcond(0x8B00, done, a))  # bf done
    emit(lambda a: _movl(2, lit["p_ret"], a))
    emit(lambda a: 0xF728)                     # fmov.s @r2,fr7
    emit(lambda a: 0xF471)                     # fsub fr7,fr4
    assert CAVE + 2 * len(code) == done
    emit(lambda a: _movl(1, lit["clamp"], a))
    emit(lambda a: 0x412B)                     # jmp @r1
    emit(lambda a: 0x0009)                     # nop (遅延スロット)
    assert CAVE + 2 * len(code) == POOL
    pool = (RAM_CPP, RAM_APP, RAM_RPM, RAM_VSS, CLAMP_FUNC,
            CAL_ADDRS["app"], CAL_ADDRS["rpm"], CAL_ADDRS["vss"], CAL_ADDRS["retard"])
    return struct.pack(f">{len(code)}H", *code) + struct.pack(f">{len(pool)}I", *pool)


def build(base: bytes, retard: float, rpm: float, app: float, vss: float) -> bytearray:
    vals = {"app": app, "rpm": rpm, "vss": vss, "retard": retard}
    for k, v in vals.items():
        lo, hi = LIMITS[k]
        if not lo <= v <= hi:
            raise SystemExit(f"--{k} {v} は範囲外（{lo}〜{hi}）")
    rom = bytearray(base)
    if struct.unpack(">I", rom[CLAMP_LIT:CLAMP_LIT + 4])[0] != CLAMP_FUNC:
        raise SystemExit(f"@{CLAMP_LIT:#x} が 0x{CLAMP_FUNC:08X} ではない（未対応ROM/適用済み？）")
    if set(rom[CAVE:CAVE_END]) != {0xFF}:
        raise SystemExit(f"ケーブ @{CAVE:#x} が空き(0xFF)ではない")
    code = assemble()
    rom[CAVE:CAVE + len(code)] = code
    for k, a in CAL_ADDRS.items():
        rom[a:a + 4] = struct.pack(">f", vals[k])
    rom[CLAMP_LIT:CLAMP_LIT + 4] = struct.pack(">I", CAVE)
    checksum.recalculate(rom)
    if not checksum.all_valid(rom):
        raise SystemExit("チェックサム補正に失敗")
    return rom


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(ROOT / "ncec_rom_dump.bin"))
    ap.add_argument("--out", default=str(ROOT / "ncec_flatshift_retard_draft3.bin"))
    ap.add_argument("--retard", type=float, default=20.0, help="リタード量[deg] (既定20)")
    ap.add_argument("--rpm", type=float, default=7000.0, help="RPMしきい値[rpm] (既定7000)")
    ap.add_argument("--app", type=float, default=80.0, help="APPしきい値[%%] (既定80)")
    ap.add_argument("--vss", type=float, default=10.0, help="車速下限[km/h] (既定10)")
    a = ap.parse_args()
    base = pathlib.Path(a.base).read_bytes()
    rom = build(base, a.retard, a.rpm, a.app, a.vss)
    pathlib.Path(a.out).write_bytes(rom)
    diff = sum(1 for x, y in zip(base, rom) if x != y)
    print(f"{a.out}: retard={a.retard}deg rpm>{a.rpm} app>{a.app}% vss>{a.vss}km/h  "
          f"差分{diff}バイト  checksum valid")


if __name__ == "__main__":
    main()
