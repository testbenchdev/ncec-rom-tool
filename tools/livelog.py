"""実機ライブ値を端末に表示(読み取り専用・OBD-II Mode01)。

使い方:
  python tools/livelog.py              # 既定PIDを 10 秒表示
  python tools/livelog.py --seconds 30
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.livelog import LiveReader, PIDS, DEFAULT_PIDS, EXTRA_PIDS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--interval", type=float, default=0.2)
    args = ap.parse_args()

    lr = LiveReader(interval=args.interval)
    lr.start()
    try:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            time.sleep(0.3)
            bp = lr.latest_by_pid()
            if not bp:
                print("  (待機: 応答なし — 通常セッション/電源を確認)")
                continue
            def fmt(pids):
                return "  ".join(f"{PIDS[p].name}={bp[p]:.1f}{PIDS[p].unit}"
                                 for p in pids if p in bp)
            print("  " + fmt(DEFAULT_PIDS))
            print("    " + fmt(EXTRA_PIDS))
            dtcs = lr.latest_dtcs()
            print("    DTC: " + (", ".join(f"{c}[{k}]" for c, k in dtcs) if dtcs else "なし"))
    finally:
        lr.stop()


if __name__ == "__main__":
    main()
