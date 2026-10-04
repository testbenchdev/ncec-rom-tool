"""予備ECU セキュリティアクセス(27)アンロック。

既定は **ドライラン**（シード要求＋キー算出まで。実機へキーは送らない）。
実際にキーを送る場合のみ `--send` を付ける（誤キーはロックアウトの恐れ）。

使い方:
    python tools/unlock.py            # 安全: セッション投入→27 01→キー算出を表示（送信しない）
    python tools/unlock.py --session 87
    python tools/unlock.py --send     # 実際に 27 02 を送信
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp  # noqa: E402
from ncecu.security import compute_security_key  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="85", help="診断セッション(16進, 既定85)")
    ap.add_argument("--level", type=int, default=1, help="セキュリティレベル index(既定1)")
    ap.add_argument("--send", action="store_true", help="実際にキーを送信する")
    args = ap.parse_args()
    ses = int(args.session, 16)

    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    try:
        r = diag.request(bytes([0x10, ses]))
        print(f"session 10 {ses:02X} -> {r.hex(' ') if r else '(none)'}")
        diag.request(b"\x3E\x01")  # tester present

        seed_resp = diag.request(b"\x27\x01")
        if seed_resp is None or seed_resp[0] != 0x67:
            print(f"requestSeed failed: {seed_resp.hex(' ') if seed_resp else '(none)'}")
            return
        seed = bytes(seed_resp[2:5])
        key = compute_security_key(seed, level=args.level)
        print(f"seed = {seed.hex(' ')}")
        print(f"computed key = {key.hex(' ')}")

        if seed == b"\x00\x00\x00":
            print("seed is 00 00 00 -> すでにアンロック済み/不要")
            return

        if not args.send:
            print("\n[ドライラン] キーは送信していません。送信するには --send を付けてください。")
            return

        print("\n送信: 27 02 " + key.hex(" "))
        key_resp = diag.request(bytes([0x27, 0x02]) + key)
        if key_resp is None:
            print("応答なし")
        elif key_resp[0] == 0x67 and key_resp[1] == 0x02:
            print(f"*** アンロック成功: {key_resp.hex(' ')} ***")
        else:
            print(f"失敗: {key_resp.hex(' ')}")
    except NegativeResponse as e:
        print(f"NEG: {e}")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
