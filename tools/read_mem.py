"""アンロック後に ReadMemoryByAddress(0x23) の形式を探り、既知ROM先頭と照合する（読み取りのみ）。"""
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
    key = compute_security_key(seed)
    kr = diag.request(bytes([0x27, 0x02]) + key)
    return bool(kr and kr[0] == 0x67 and kr[1] == 0x02)


def main():
    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    try:
        if not unlock(diag):
            print("unlock failed")
            return
        print("unlocked. probing 0x23 read formats at addr 0x00000000 (expect 00 00 0a ac ...)")
        want = ROM[0:16].hex(" ")
        print(f"  dump[0:16] = {want}")
        # 形式 23 14 <4byte addr> <1byte len> で読める領域を探す
        addrs = [0x00000000, 0x00008000, 0x00080000, 0x000B8000, 0x000C0000,
                 0x000FF000, 0xFFFF0000, 0xFFFF8000, 0xFFFF91A0, 0xFFFFC000,
                 0x00000800, 0x00002000]
        for addr in addrs:
            diag.request(b"\x3E\x01")
            req = b"\x23\x14" + addr.to_bytes(4, "big") + b"\x08"
            try:
                r = diag.request(req)
            except NegativeResponse as e:
                print(f"  @{addr:08X} len8  NEG {e}")
                continue
            if r is None:
                print(f"  @{addr:08X} len8  (no response)")
            else:
                data = r[1:]
                cmp = ""
                if addr < len(ROM):
                    cmp = " dump=" + ROM[addr:addr+8].hex(" ")
                print(f"  @{addr:08X} len8  {data.hex(' ')}{cmp}")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
