"""フラッシュ手順の安全検証(書き込み・消去リスクなし)。

実行するのは: プログラミングセッション + セキュリティアンロック + フラッシュ回数(識別)読み出しのみ。
RequestDownload(0x34) 以降は送らない。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp  # noqa: E402
from ncecu.security import compute_security_key  # noqa: E402


def show(diag, label, payload, timeout=3.0):
    diag.request(b"\x3E\x01")
    try:
        r = diag.request(payload, timeout=timeout)
    except NegativeResponse as e:
        print(f"  {label:<30} NEG {e}")
        return None
    print(f"  {label:<30} {r.hex(' ') if r else '(none)'}")
    return r


def main():
    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    try:
        print("1) プログラミングセッション 10 85")
        print("   ->", (diag.request(b"\x10\x85") or b"").hex(" "))
        diag.request(b"\x3E\x01")
        print("2) セキュリティアクセス 27")
        sr = diag.request(b"\x27\x01")
        if not sr or sr[0] != 0x67:
            print("   requestSeed 失敗:", (sr or b"").hex(" "))
            return
        seed = bytes(sr[2:5])
        key = compute_security_key(seed)
        print(f"   seed={seed.hex(' ')} key={key.hex(' ')}")
        kr = diag.request(bytes([0x27, 0x02]) + key)
        if not (kr and kr[0] == 0x67 and kr[1] == 0x02):
            print("   アンロック失敗:", (kr or b"").hex(" "))
            return
        print("   アンロック成功 67 02")
        print("3) フラッシュ回数/識別の読み出し(読み取りのみ)")
        show(diag, "22 E6 11 (flash counter?)", b"\x22\xE6\x11")
        show(diag, "22 F1 11", b"\x22\xF1\x11")
        show(diag, "B1 00 B2 00 (routine query?)", b"\xB1\x00\xB2\x00")
        print("\n[安全検証ここまで] RequestDownload(0x34) は送っていません。")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
