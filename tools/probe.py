"""予備ECUの読み取り専用プローブ。

- バス上の自発送信フレームを数秒観測
- OBD-II: Mode01（対応PID・回転数・水温等）、Mode03（DTC）、Mode09（VIN/CALID/CVN）
- UDS ReadDataByIdentifier(0x22) の代表的DID

ECU の状態を変える要求（セッション変更・セキュリティアクセス・書き込み・DTC消去）は一切送らない。
"""
import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError  # noqa: E402

LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / "logs"
lines: list[str] = []


def out(s: str = "") -> None:
    print(s)
    lines.append(s)


def try_req(diag: DiagClient, label: str, payload: bytes) -> bytes | None:
    try:
        r = diag.request(payload)
    except NegativeResponse as e:
        out(f"  {label:<28} NEG  {e}")
        return None
    except IsoTpError as e:
        out(f"  {label:<28} ERR  {e}")
        return None
    if r is None:
        out(f"  {label:<28} (no response)")
    else:
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in r)
        out(f"  {label:<28} {r.hex(' ')}  |{txt}|")
    return r


def sniff(bus, seconds: float) -> None:
    out(f"[1] passive sniff {seconds:.0f}s")
    seen: dict[int, tuple[int, bytes]] = {}
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        m = bus.recv(0.1)
        if m is not None:
            cnt, _ = seen.get(m.arbitration_id, (0, b""))
            seen[m.arbitration_id] = (cnt + 1, bytes(m.data))
    if not seen:
        out("  (no frames)")
    for aid in sorted(seen):
        cnt, data = seen[aid]
        out(f"  0x{aid:03X}  x{cnt:<5} last={data.hex(' ')}")


def main() -> None:
    bus = open_bus()
    try:
        out(f"probe {datetime.datetime.now().isoformat(timespec='seconds')}")
        sniff(bus, 3.0)
        diag = DiagClient(IsoTp(bus))

        out("[2] tester present")
        try_req(diag, "3E 00", b"\x3E\x00")

        out("[3] OBD-II Mode 01")
        for pid, name in [(0x00, "supported 01-20"), (0x20, "supported 21-40"),
                          (0x40, "supported 41-60"), (0x01, "monitor status"),
                          (0x05, "coolant temp"), (0x0C, "rpm"), (0x0F, "intake air temp"),
                          (0x11, "throttle pos"), (0x42, "ECU voltage")]:
            try_req(diag, f"01 {pid:02X} {name}", bytes([0x01, pid]))

        out("[4] OBD-II Mode 03 / 07 (DTC)")
        try_req(diag, "03 stored DTC", b"\x03")
        try_req(diag, "07 pending DTC", b"\x07")

        out("[5] OBD-II Mode 09 (vehicle info)")
        for pid, name in [(0x00, "supported"), (0x02, "VIN"), (0x04, "CALID"),
                          (0x06, "CVN"), (0x0A, "ECU name")]:
            try_req(diag, f"09 {pid:02X} {name}", bytes([0x09, pid]))

        out("[6] UDS 0x22 ReadDataByIdentifier")
        for did, name in [(0xF190, "VIN"), (0xF188, "ECU SW number"), (0xF18C, "ECU serial"),
                          (0xF187, "spare part no"), (0xF195, "SW version"), (0xF18A, "supplier")]:
            try_req(diag, f"22 {did:04X} {name}", bytes([0x22, did >> 8, did & 0xFF]))

        out("[7] KWP2000 0x1A ReadEcuIdentification")
        for opt in (0x80, 0x87, 0x90, 0x9B):
            try_req(diag, f"1A {opt:02X}", bytes([0x1A, opt]))
    finally:
        bus.shutdown()

    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"probe_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nsaved: {path}")


if __name__ == "__main__":
    main()
