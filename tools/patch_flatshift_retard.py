"""フラットシフト用 点火リタード注入パッチ（第3ドラフト・ベンチ検証用）を生成する。

★ 点火制御を書き換えるカスタムファームウェア。生成物は「ベンチ検証用ドラフト」扱い。
  実走前にベンチECUでタイミングライト / Live点火時期PIDによる確認が必須。

本体は ncecu/flatshift.py（注入点・発動条件・ケーブの詳細もそちら）。エディタの
「点火リタード」ボタンも同じ処理を使う。

使い方:
  python tools/patch_flatshift_retard.py                         # ncec_rom_dump.bin → ncec_flatshift_retard_draft3.bin
  python tools/patch_flatshift_retard.py --base X.bin --out Y.bin --retard 15 --rpm 6800 --app 85 --vss 15
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import flatshift  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = flatshift.DEFAULTS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(ROOT / "ncec_rom_dump.bin"))
    ap.add_argument("--out", default=str(ROOT / "ncec_flatshift_retard_draft3.bin"))
    ap.add_argument("--retard", type=float, default=D["retard"], help=f"リタード量[deg] (既定{D['retard']:g})")
    ap.add_argument("--rpm", type=float, default=D["rpm"], help=f"RPMしきい値[rpm] (既定{D['rpm']:g})")
    ap.add_argument("--app", type=float, default=D["app"], help=f"APPしきい値[%%] (既定{D['app']:g})")
    ap.add_argument("--vss", type=float, default=D["vss"], help=f"車速下限[km/h] (既定{D['vss']:g})")
    a = ap.parse_args()
    base = pathlib.Path(a.base).read_bytes()
    try:
        rom = flatshift.build(base, a.retard, a.rpm, a.app, a.vss)
    except ValueError as e:
        raise SystemExit(str(e))
    pathlib.Path(a.out).write_bytes(rom)
    diff = sum(1 for x, y in zip(base, rom) if x != y)
    print(f"{a.out}: retard={a.retard}deg rpm>{a.rpm} app>{a.app}% vss>{a.vss}km/h  "
          f"差分{diff}バイト  checksum valid")


if __name__ == "__main__":
    main()
