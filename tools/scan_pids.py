"""Mode 0x22（ReadDataByIdentifier）で応答する 16bit PID を総当たりで調べる（読み取りのみ）。

使い方: python tools/scan_pids.py [start_hex] [end_hex]
結果は logs/pids_<日時>.csv に保存（pid, 応答データ長, データ）。
"""
import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError  # noqa: E402


def main() -> None:
    start = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x0000
    end = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0xFFFF
    log_dir = pathlib.Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    path = log_dir / f"pids_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"

    bus = open_bus()
    diag = DiagClient(IsoTp(bus, timeout=0.3))
    found = 0
    t0 = time.monotonic()
    try:
        with path.open("w", encoding="utf-8") as f:
            f.write("pid,len,data\n")
            for pid in range(start, end + 1):
                try:
                    r = diag.request(bytes([0x22, pid >> 8, pid & 0xFF]), timeout=0.3)
                except NegativeResponse as e:
                    if e.nrc != 0x31:
                        f.write(f"{pid:04X},NRC{e.nrc:02X},\n")
                    continue
                except IsoTpError:
                    continue
                if r is None:
                    f.write(f"{pid:04X},TIMEOUT,\n")
                    continue
                data = r[3:]
                f.write(f"{pid:04X},{len(data)},{data.hex()}\n")
                f.flush()
                found += 1
                if pid % 0x100 == 0 or found % 20 == 0:
                    print(f"  {pid:04X}  found={found}  {time.monotonic() - t0:.0f}s", flush=True)
    finally:
        bus.shutdown()
    print(f"done: {found} PIDs  -> {path}")


if __name__ == "__main__":
    main()
