"""非破壊の大容量 ISO-TP 送信テスト(gs_usb 送信詰まりの診断・修正検証)。

フラッシュを使わずに、TransferData と同じ per-message 送信負荷(既定 ~1025B =
146 連続フレーム)を再現する。ECU は読み取り系 SID 0x22 の巨大要求を『ISO-TP で
再構成してから』NRC で弾くだけなので、**副作用なし**(セッション変更・セキュリティ
アクセス・書き込み・DTC消去は一切送らない)。= ブリックしない。

これで "この設定なら送り切れる" を安全に見つけてから、本物のフラッシュを再試行する。

使い方(PowerShell):
  python tools/tx_test.py                  # 既定: 1025B x8, floor=1ms, drain=ON
  python tools/tx_test.py --no-drain       # TXエコー吸い出しを切って比較
  python tools/tx_test.py --floor 0.003    # 連続フレーム間隔を3msに上げて試す
  python tools/tx_test.py --size 1025 --count 16
"""
import argparse
import datetime
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu.canbus import open_bus          # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.flash import realtime_guard     # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError  # noqa: E402

LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / "logs"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=1025, help="1メッセージのペイロード長(flash blockは1025)")
    ap.add_argument("--count", type=int, default=8, help="送信メッセージ数")
    ap.add_argument("--floor", type=float, default=0.001, help="連続フレーム最小間隔(秒)")
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--no-drain", action="store_true", help="TXエコー吸い出しを無効化(比較用)")
    ap.add_argument("--drain-every", type=int, default=8, help="何フレーム毎にエコー吸い出し(小=安全/遅, 大=速い)")
    ap.add_argument("--no-guard", action="store_true",
                    help="realtime_guard(タイマ1ms+高優先度)を使わない。既定は使う=実フラッシュと同条件")
    args = ap.parse_args()
    size = max(8, min(args.size, 0xFFF))   # 単一 ISO-TP メッセージ上限 0xFFF
    lines: list[str] = []

    def out(s: str = "") -> None:
        print(s)
        lines.append(s)

    bus = open_bus()
    try:
        tp = IsoTp(bus, tx_st_min_floor=args.floor, tx_retries=args.retries,
                   drain_tx_echo=not args.no_drain, drain_every=args.drain_every)
        diag = DiagClient(tp)
        out(f"tx_test {datetime.datetime.now().isoformat(timespec='seconds')}")
        out(f"size={size} (0x{size:X}) count={args.count} floor={args.floor}s "
            f"retries={args.retries} drain={not args.no_drain} drain_every={args.drain_every}")
        out("（SID 0x22 + ゼロ詰め = 読み取り要求。ECUは再構成後にNRCで弾くだけ=副作用なし）")
        out(f"realtime_guard={'OFF' if args.no_guard else 'ON(実フラッシュと同条件)'}")
        ok = 0
        times = []   # OK送信の所要ms(速度集計用)
        import contextlib
        guard = contextlib.nullcontext() if args.no_guard else realtime_guard(out)
        with guard:
            for i in range(args.count):
                payload = bytes([0x22]) + bytes(size - 1)   # 0x22 + (size-1) ゼロ
                t0 = time.monotonic()
                try:
                    r = diag.request(payload, timeout=5.0)
                    dt = (time.monotonic() - t0) * 1000
                    rs = r.hex(" ")[:30] if r else "(no resp)"
                    out(f"  #{i + 1:>2}: OK  送信完了+応答 {dt:6.0f}ms  resp={rs}")
                    ok += 1
                    times.append(dt)
                except NegativeResponse as e:
                    dt = (time.monotonic() - t0) * 1000
                    out(f"  #{i + 1:>2}: OK  送信完了(ECUがNRCで応答) {dt:6.0f}ms  {e}")
                    ok += 1
                    times.append(dt)
                except IsoTpError as e:
                    dt = (time.monotonic() - t0) * 1000
                    out(f"  #{i + 1:>2}: FAIL 送信失敗 {dt:6.0f}ms  IsoTpError: {e}")
                except Exception as e:  # noqa
                    dt = (time.monotonic() - t0) * 1000
                    out(f"  #{i + 1:>2}: FAIL 送信失敗 {dt:6.0f}ms  {type(e).__name__}: {e}")
        out(f"\n結果: {ok}/{args.count} 送信成功")
        if times:
            avg = sum(times) / len(times)
            kibs = size / (avg / 1000) / 1024 if avg else 0
            frames = (size + 6) // 7 + 1   # FF1 + CF群の概算
            full_blocks = 0xFF800 // 0x400  # フル書込の0x400ブロック数(≒1022)
            est = avg * full_blocks / 1000
            out(f"[速度] 1メッセージ平均 {avg:.0f}ms  {kibs:.2f}KiB/s  (~{frames}フレーム/msg, floor={args.floor}s)")
            out(f"       フル書込TX推定(≒{full_blocks}ブロック) ≒ {est:.0f}s  "
                f"※これは送信のみ。実フラッシュは各ブロックのECU書込待ちが加算される")
            out("       → floor を下げて再試行し、OKを保ったまま ms/KiB-s が改善する下限を探す。")
        if ok == args.count:
            out("→ この設定で大容量TXは安定。フラッシュ再試行の見込みが立つ(同設定が flash.py の既定)。")
        elif ok == 0:
            out("→ 全滅。--floor を上げる / --no-drain と比較。drainありで全滅なら gs_usb 側の別要因。")
        else:
            out("→ 断続的。--floor を上げて安定するか確認。")
    finally:
        bus.shutdown()

    LOG_DIR.mkdir(exist_ok=True)
    p = LOG_DIR / f"tx_test_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nsaved: {p}")


if __name__ == "__main__":
    main()
