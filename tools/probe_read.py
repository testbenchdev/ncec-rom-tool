"""アンロック後に各種読み出しサービスを試す（読み取りのみ・安全）。通れば実機メモリをダンプと直接比較できる。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp  # noqa: E402
from ncecu.security import compute_security_key  # noqa: E402

ROM = (pathlib.Path(__file__).resolve().parents[1] / "ncec_rom_dump.bin").read_bytes()


def unlock(diag, ses=0x85):
    diag.request(bytes([0x10, ses]))
    diag.request(b"\x3E\x01")
    sr = diag.request(b"\x27\x01")
    if not sr or sr[0] != 0x67:
        return False
    seed = bytes(sr[2:5])
    if seed == b"\x00\x00\x00":
        return True
    kr = diag.request(bytes([0x27, 0x02]) + compute_security_key(seed))
    return bool(kr and kr[0] == 0x67 and kr[1] == 0x02)


def show(diag, label, req):
    diag.request(b"\x3E\x01")
    try:
        r = diag.request(req)
    except NegativeResponse as e:
        print(f"  {label:<34} NEG {e}")
        return None
    print(f"  {label:<34} {r.hex(' ') if r else '(none)'}")
    return r


def main():
    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    try:
        if not unlock(diag):
            print("unlock failed")
            return
        print("unlocked. probing read services:")
        addr = 0x00008000
        # RequestUpload 0x35: dataFormat 00, ALFID 44 (4 addr,4 size)
        show(diag, "35 RequestUpload @8000 sz100", b"\x35\x00\x44" + addr.to_bytes(4, "big") + (0x100).to_bytes(4, "big"))
        show(diag, "35 (ALFID33) @8000 sz100", b"\x35\x00\x33" + addr.to_bytes(3, "big") + (0x100).to_bytes(3, "big"))
        show(diag, "34 RequestDownload probe", b"\x34\x00\x44" + addr.to_bytes(4, "big") + (0x100).to_bytes(4, "big"))
        show(diag, "3C 01 readDataByLocalId", b"\x3C\x01")
        show(diag, "21 01 readDataByLocalId", b"\x21\x01")
        show(diag, "23 14 @B8000 len8", b"\x23\x14" + (0x000B8000).to_bytes(4, "big") + b"\x08")
        show(diag, "23 14 @2000 len8", b"\x23\x14" + (0x00002000).to_bytes(4, "big") + b"\x08")
        # some Mazda/Denso use AF/B? custom. try a few
        show(diag, "A8 (mazda read?)", b"\xA8\x00")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
