"""実機RAM差分ツール: ある操作(例: クラッチON/OFF)で RAM のどのバイトが変わるかを特定する。

Mode23(ReadMemoryByAddress)で指定RAM範囲を読み、**複数回トグルの共通集合**で絞り込む。読み取り専用。
★ 前提: ECU側に Mode23 有効化パッチが当たっていること(既定セッションで `23` が通ること)。

使い方(端末で対話的に実行):
  python -X utf8 tools/ram_diff.py                           # 既定 0xFFFF0000-0xFFFFE000(RAM全域)
  python -X utf8 tools/ram_diff.py --start FFFF6000 --end FFFFA000
  python -X utf8 tools/ram_diff.py --chunk 200               # 1回の読み出しサイズ(hex)

手順:
  1) クラッチを【離して】Enter            → 基準OFF
  2) 以降くり返し: 【踏んで】Enter → 【離して】Enter
     毎サイクル、「OFFで同じ値・ONで同じ値」に“連動し続けた”バイトだけが残る。
  3) 数サイクル回すと、ノイズが落ちて **クラッチ連動バイトだけ**に収束する。'q'+Enterで終了。

コツ: **イグニッションON・エンジンOFF(KOEO)** が最適。RAMが静止するので読みも比較もぶれない。
      KOEOで0件なら、アイドル・ニュートラルで(ギア/アクセルは動かさず)数サイクル回す。
"""
import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import mode23                                   # noqa: E402
from ncecu.canbus import close_bus, open_bus              # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse       # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError                 # noqa: E402


def read_range(diag, start, end, chunk):
    out = {}
    addr = start
    while addr < end:
        n = min(chunk, end - addr)
        if not mode23.addr_readable(addr, n):
            addr += n
            continue
        data = None
        for _ in range(2):
            try:
                data = mode23.parse_read(diag.request(mode23.read_request(addr, n), timeout=2.0), n)
            except (NegativeResponse, IsoTpError):
                data = None
            if data is not None:
                break
        if data is not None:
            for i, b in enumerate(data):
                out[addr + i] = b
        addr += n
    return out


def snapshot(diag, start, end, chunk, label):
    t0 = time.monotonic()
    snap = read_range(diag, start, end, chunk)
    print(f"  [{label}] {len(snap)}バイト読み出し ({time.monotonic() - t0:.1f}s)")
    return snap


def show(cand):
    print(f"  → 連動し続けている候補: {len(cand)} バイト")
    if 0 < len(cand) <= 40:
        for k in sorted(cand):
            off, on = cand[k]
            print(f"     0x{k:08X}: OFF=0x{off:02X} / ON=0x{on:02X}")
    elif len(cand) > 40:
        print("     (まだ多い。もう1サイクル回してください)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="FFFF0000")
    ap.add_argument("--end", default="FFFFE000")
    ap.add_argument("--chunk", default="200")
    args = ap.parse_args()
    start, end = int(args.start, 16), int(args.end, 16)
    chunk = max(1, min(mode23.MAX_SIZE, int(args.chunk, 16)))
    print(f"RAM差分ツール(共通集合方式)  範囲 0x{start:08X}-0x{end:08X}  chunk=0x{chunk:X}")
    print("※ Mode23有効化ROM・CAN接続・イグニッションON が前提。読み取り専用。")
    print("※ 可能なら【エンジンOFF(KOEO)】で。クラッチ以外は動かさないこと。\n")

    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    diag.tp.timeout = 5.0
    try:
        if not read_range(diag, start, min(start + chunk, end), chunk):
            print("!! この範囲を Mode23 で読めません。Mode23有効化・配線・IG ONを確認してください。")
            return

        input("クラッチを【離した】状態にして Enter (基準OFF) ... ")
        off = snapshot(diag, start, end, chunk, "基準OFF")
        cand = None          # {addr: (off_val, on_val)}
        cycle = 0
        while True:
            s = input("\nクラッチを【踏んで】 Enter  / 'q'で終了 ... ")
            if s.strip().lower() == "q":
                break
            on = snapshot(diag, start, end, chunk, "ON")
            s = input("クラッチを【離して】 Enter  / 'q'で終了 ... ")
            if s.strip().lower() == "q":
                break
            off2 = snapshot(diag, start, end, chunk, "OFF")
            cycle += 1
            if cand is None:
                # 初回: ON で変化し、OFF に戻ったバイト
                cand = {k: (off[k], on[k]) for k in off
                        if k in on and k in off2 and on[k] != off[k] and off2[k] == off[k]}
            else:
                # 以降: OFF値・ON値が毎回一致し続けるものだけ残す
                cand = {k: v for k, v in cand.items()
                        if k in on and k in off2 and on[k] == v[1] and off2[k] == v[0]}
            print(f"--- サイクル {cycle} ---")
            show(cand)
            if cand is not None and 0 < len(cand) <= 5 and cycle >= 2:
                print("  （収束しました。これが本物のクラッチ連動バイトの最有力です）")
            off = off2
        print("\n=== 最終候補 ===")
        if cand:
            for k in sorted(cand):
                print(f"  0x{k:08X}: OFF=0x{cand[k][0]:02X} / ON=0x{cand[k][1]:02X}")
        else:
            print("  連動バイトなし。KOEOなら→アイドル・ニュートラルで再試行。")
            print("  それでも0なら、PCMがクラッチを直接読んでいない可能性大。")
    finally:
        close_bus(bus)


if __name__ == "__main__":
    main()
