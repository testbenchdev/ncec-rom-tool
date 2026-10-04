"""実機・非破壊プローブ: 認証 → B1 00 B2 00 → RequestDownload の応答だけを確認する。

**書き込みは一切しない**: TransferData(0x36)も TransferExit(0x37)も送らない。
目的:
  1. 今回実装した書き込み経路(認証/RoutineControl/RequestDownload)が実機で通るか再検証
  2. RequestDownload 肯定応答から最大ブロック長を読み取る(0x400 か 0xFFE かの確定材料)
最後に 11 01 でリセットし、ダウンロード保留状態を解除する。

使い方: python tools/probe_download.py
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp  # noqa: E402
from ncecu.flash import Flasher  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", default="00008000", help="RequestDownload addr(16進8桁)")
    ap.add_argument("--size", default="000FF800", help="RequestDownload size(16進8桁)")
    args = ap.parse_args()
    addr = int(args.addr, 16)
    size = int(args.size, 16)

    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    f = Flasher(diag, log=lambda s: print("  " + s))
    try:
        print("[1] 通信確認 3E 01 ...")
        tp = diag.tester_present()
        print("    tester_present:", tp)

        print("[2] 認証(10 85 → 27 01/02)… ※実コード Flasher.authenticate() を使用")
        f.authenticate()   # 10 85, 3E 01, 27 01(seed)→鍵→27 02。失敗で例外。

        print("[3] RoutineControl B1 00 B2 00 … ※Flasher.check_flash_counter()")
        r_b1 = f.check_flash_counter()
        print("    応答:", r_b1.hex(" "))

        print(f"[4] RequestDownload 34 {addr:08X} {size:08X}(応答のみ・転送しない)")
        req = bytes([0x34]) + addr.to_bytes(4, "big") + size.to_bytes(4, "big")
        try:
            r34 = diag.request(req, timeout=10.0)
            print("    肯定応答:", r34.hex(" "))
            # 74 [lengthFormatIdentifier] [maxNumberOfBlockLength...] の形なら解釈
            if r34[0] == 0x74 and len(r34) >= 2:
                lfid = r34[1]
                nbytes = (lfid >> 4) & 0x0F
                body = r34[2:2 + nbytes] if nbytes else r34[2:]
                if body:
                    mbl = int.from_bytes(body, "big")
                    print(f"    → lengthFormatId=0x{lfid:02X}  maxNumberOfBlockLength=0x{mbl:X} ({mbl})")
                else:
                    print(f"    → 追加データなし(応答={r34.hex(' ')})。ブロック長は既定運用(0x400/0xFFE)で要判断。")
        except NegativeResponse as e:
            print(f"    否定応答(NRC): {e}")

        print("[5] ★ 転送(0x36)・終了(0x37)は送信しません = 書き込みなし")
        print("[6] ECUリセット 11 01(ダウンロード保留解除)…")
        f.ecu_reset()
        print("    完了。消去・書き込みは発生していません。")
    except NegativeResponse as e:
        print("NEG:", e)
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
