"""フラットシフト 点火カット/遅角パッチ（第6ドラフト・ベンチ検証用）を生成する。

★ 点火制御を書き換えるカスタムファームウェア。生成物は「ベンチ検証用ドラフト」扱い。
  実走前にベンチ/予備ECUで確認必須。**RAMに一切書かない読み取り専用設計**。
  発動＝クラッチ踏込 かつ 回転>しきい値 かつ アクセル>しきい値 かつ 車速>下限 の間だけ
  （窓時間はクラッチを踏んでいる長さ＝ドライバ制御／回転しきい値が上限）。
  test_mode=1 で車速ゲートだけ無視（クラッチ＋回転＋アクセルは生かす）＝停車デバッグ用
  （始動/アイドルは低回転で不発＝クラッチ始動を妨げない。停車Nで回転を上げると発動）。

本体は ncecu/flatshift.py（注入点・2ケーブの詳細もそちら）。エディタの「フラットシフト」ボタンも同じ処理。

使い方:
  python tools/patch_flatshift_retard.py                           # 既定(遅角)
  python tools/patch_flatshift_retard.py --method 1 --rpm 6800     # 本物の点火カット
  python tools/patch_flatshift_retard.py --method 0 --retard 30 --floor -12   # 点火大遅角
  python tools/patch_flatshift_retard.py --method 1 --test         # 停車デバッグ(車速だけ無視)
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
    ap.add_argument("--base", default=str(ROOT / "rom_data" / "ecu_readout_yahooauction.bin"))
    ap.add_argument("--out", default=str(ROOT / "rom_data" / "flatshift_out.bin"))
    ap.add_argument("--method", type=int, default=D["method"], choices=(0, 1),
                    help="0=点火遅角 / 1=本物の点火カット (既定%d)" % D["method"])
    ap.add_argument("--retard", type=float, default=D["retard"], help=f"遅角量[deg] (既定{D['retard']:g})")
    ap.add_argument("--floor", type=float, default=D["floor"],
                    help=f"下限=最小進角[deg] 負=ATDC 大遅角用 (既定{D['floor']:g})")
    ap.add_argument("--rpm", type=float, default=D["rpm"], help=f"RPMしきい値[rpm] (既定{D['rpm']:g})")
    ap.add_argument("--app", type=float, default=D["app"], help=f"APPしきい値[%%] (既定{D['app']:g})")
    ap.add_argument("--vss", type=float, default=D["vss"], help=f"車速下限[km/h] (既定{D['vss']:g})")
    ap.add_argument("--test", action="store_true",
                    help="停車デバッグ: test_mode=1(車速ゲートだけ無視・クラッチ+回転+アクセルは生かす)")
    a = ap.parse_args()
    base = pathlib.Path(a.base).read_bytes()
    try:
        rom = flatshift.build(base, method=a.method, retard=a.retard, floor=a.floor,
                              rpm=a.rpm, app=a.app, vss=a.vss, test_mode=1 if a.test else 0)
    except ValueError as e:
        raise SystemExit(str(e))
    pathlib.Path(a.out).write_bytes(rom)
    diff = sum(1 for x, y in zip(base, rom) if x != y)
    mname = "点火カット" if a.method else "点火遅角"
    amt = "コイル充電スキップ" if a.method else f"retard={a.retard:g}/floor={a.floor:g}deg"
    tm = " [test_mode=1]" if a.test else ""
    print(f"{a.out}: {mname} {amt}  ゲート: クラッチ∧rpm>{a.rpm:g}∧app>{a.app:g}%∧vss>{a.vss:g}km/h{tm}  "
          f"差分{diff}バイト  checksum valid（RAM非書込・窓なし）")


if __name__ == "__main__":
    main()
