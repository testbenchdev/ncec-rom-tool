"""電子スロットルのペダルマップを 1:1 寄り(ワイヤースロットル風ハイレスポンス)にするROMを生成。

★ 走行フィールに直結。予備/ベンチECUで確認し、元ROMは必ず保管すること。
本体ロジックは ncecu/dbw_throttle.py（対象アドレス・方式・注意はそちら）。

使い方:
  python tools/patch_throttle_1to1.py --base ncec_immo_off.bin --out ncec_immo_off_throttle1to1.bin
  python tools/patch_throttle_1to1.py --base X.bin --out Y.bin --blend 0.7 --cap-margin 10 --keep-idle 2
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import dbw_throttle as dbw  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(ROOT / "ncec_immo_off.bin"))
    ap.add_argument("--out", default=str(ROOT / "ncec_immo_off_throttle1to1.bin"))
    ap.add_argument("--blend", type=float, default=1.0, help="0=純正〜1=完全1:1 (既定1.0)")
    ap.add_argument("--cap-margin", type=float, default=10.0,
                    help="指令上限の引き上げ[%%] 監視の誤フォルト防止 (既定10)")
    ap.add_argument("--keep-idle", type=int, default=0,
                    help="アイドル直上の列数を純正のまま残す (既定0=純正どおり0,2.3%%は元から0)")
    a = ap.parse_args()
    base = pathlib.Path(a.base).read_bytes()
    try:
        rom = dbw.build(base, blend=a.blend, cap_margin=a.cap_margin, keep_idle_cols=a.keep_idle)
        dbw.verify_result(base, rom, blend=a.blend, cap_margin=a.cap_margin, keep_idle_cols=a.keep_idle)
    except (ValueError, AssertionError) as e:
        raise SystemExit(str(e))
    pathlib.Path(a.out).write_bytes(rom)
    diff = sum(1 for x, y in zip(base, rom) if x != y)
    print(f"{a.out}: blend={a.blend} cap_margin={a.cap_margin} keep_idle={a.keep_idle}  "
          f"差分{diff}バイト  checksum valid  (制御+監視10枚+上限2枚を更新)")


if __name__ == "__main__":
    main()
