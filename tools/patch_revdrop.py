"""シフトアップ時の回転落ちを速くする（レブハング低減）ROM を生成。

燃料側のみ（DFCO=減速燃料カットを早く・強く）で、電子スロットルは触らない＝監視安全。
本体ロジック・番地・注意は ncecu/revdrop.py、段階ベンチ手順は docs/revdrop_ja.md。

使い方:
  # プリセット
  python tools/patch_revdrop.py --base rom_data/<現在のROM>.bin --out rom_data/revdrop_mild.bin --preset mild
  python tools/patch_revdrop.py --base rom_data/<現在のROM>.bin --out rom_data/revdrop_strong.bin --preset strong
  # 個別指定（enter_count=突入カウント 1..30 / enlean_scale=カット率倍率 1.0..8.0）
  python tools/patch_revdrop.py --base rom_data/<現在のROM>.bin --out rom_data/out.bin --enter-count 6 --enlean-scale 2.5
  # inert（純正等価・検証用）
  python tools/patch_revdrop.py --base rom_data/<現在のROM>.bin --out rom_data/inert.bin --preset off
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import revdrop  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=str(ROOT / "rom_data" / "ecu_readout_yahooauction.bin"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--preset", choices=sorted(revdrop.PRESETS), default=None,
                    help="off(inert)/mild/strong")
    ap.add_argument("--enter-count", type=int, default=None,
                    help="減速突入カウント 1..30（小=DFCOが速く入る）")
    ap.add_argument("--enlean-scale", type=float, default=None,
                    help="エンリーン率倍率 1.0..8.0（大=全カットに速く到達）")
    a = ap.parse_args()

    params = revdrop.preset(a.preset) if a.preset else {"enter_count": None, "enlean_scale": 1.0}
    if a.enter_count is not None:
        params["enter_count"] = a.enter_count
    if a.enlean_scale is not None:
        params["enlean_scale"] = a.enlean_scale

    base = pathlib.Path(a.base).read_bytes()
    try:
        rom, changes = revdrop.build(base, enter_count=params["enter_count"],
                                     enlean_scale=params["enlean_scale"])
    except (ValueError, AssertionError) as e:
        raise SystemExit(f"エラー: {e}")

    pathlib.Path(a.out).write_bytes(rom)
    diff = sum(1 for x, y in zip(base, rom) if x != y)
    print(f"{a.out}: enter_count={params['enter_count']} enlean_scale={params['enlean_scale']}  "
          f"差分{diff}バイト  checksum OK")
    for c in changes:
        mark = "*" if c["changed"] else " "
        print(f"  {mark} 0x{c['addr']:X} {c['name']}: {c['before']} -> {c['after']}")


if __name__ == "__main__":
    main()
