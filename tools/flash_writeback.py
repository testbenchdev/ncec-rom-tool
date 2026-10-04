"""実機・書き戻しテスト: 無改変の現行ダンプをそのまま書き込み、パイプラインを実証する。

★ 消去を伴う不可逆操作(ブリックの実リスク)。--confirm が無ければドライラン。
★ SBL(0x1800バイト, NC1/start=0x2000)が必須。--sbl <file> で渡す。未指定ならドライラン。

手順(nc-flash 準拠, ncecu/flash.py):
  ID読取(前) → flash(rom, sbl, confirm) → ID読取(後) → CALID/CVN 前後一致を判定
    = 認証 → B1 00 B2 00 → RequestDownload(0x8000,0xFF800)
      → TransferData[ SBL(0x1800) + 補正ROM[0x2000:](0xFE000) ] 0x400ブロック → 0x37 → リセット

使い方:
  python tools/flash_writeback.py                      # ドライラン(SBL無し・書き込まない)
  python tools/flash_writeback.py --sbl nc1_sbl.bin    # ドライラン(SBL検証のみ)
  python tools/flash_writeback.py --sbl nc1_sbl.bin --confirm   # 実書き込み(要ブリック覚悟)
"""
import argparse
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import flash  # noqa: E402
from ncecu.canbus import open_bus  # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse  # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DUMP = ROOT / "ncec_rom_dump.bin"
LOG_DIR = ROOT / "logs"
lines: list[str] = []


def out(s: str = "") -> None:
    print(s)
    lines.append(s)


def read_id(diag: DiagClient, tag: str) -> dict:
    """Mode 09 で VIN/CALID/CVN を読む(読み取り専用)。"""
    out(f"--- 識別情報 [{tag}] ---")
    res = {}
    for pid, name in [(0x02, "VIN"), (0x04, "CALID"), (0x06, "CVN")]:
        try:
            r = diag.request(bytes([0x09, pid]), timeout=2.0)
        except (NegativeResponse, IsoTpError) as e:
            out(f"  {name:<6} ERR {e}")
            res[name] = None
            continue
        if r is None:
            out(f"  {name:<6} (no response)")
            res[name] = None
            continue
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in r)
        out(f"  {name:<6} {r.hex(' ')}  |{txt}|")
        res[name] = r.hex(" ")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sbl", help="SBL バイナリ(0x1800バイト, NC1/start=0x2000)")
    ap.add_argument("--confirm", action="store_true", help="実際に消去+書き込みを行う(不可逆)")
    args = ap.parse_args()

    rom = DUMP.read_bytes()
    sbl = pathlib.Path(args.sbl).read_bytes() if args.sbl else None
    out(f"flash_writeback {datetime.datetime.now().isoformat(timespec='seconds')}")
    out(f"ダンプ: {DUMP.name}  size=0x{len(rom):X}  SBL: "
        f"{(args.sbl + ' (0x%X)' % len(sbl)) if sbl else '(なし=ドライラン)'}")

    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    diag.tp.timeout = 10.0   # 消去/フロー制御待ちに余裕を持たせる
    f = flash.Flasher(diag, log=out)
    try:
        out("[1] 通信確認")
        out(f"  tester_present: {diag.tester_present()}")
        before = read_id(diag, "書き込み前")

        out("[2] 書き込み " + ("(本番)" if (args.confirm and sbl) else "(ドライラン)"))
        plan = f.flash(rom, sbl, flash_start=flash.ROM_FLASH_START_MIN, confirm=args.confirm)
        out(f"  plan: {plan}")

        if not (args.confirm and sbl):
            out("\n[ドライラン] 実書き込みは行っていません。"
                "--sbl <file> と --confirm の両方で実行します。")
            return

        out("[3] リセット後の再起動待ち (4s) ...")
        import time
        time.sleep(4.0)
        for _ in range(5):
            try:
                if diag.tester_present():
                    break
            except (NegativeResponse, IsoTpError):
                break
            time.sleep(1.0)
        after = read_id(diag, "書き込み後")

        out("[4] 判定")
        ok = True
        for k in ("CALID", "CVN"):
            b, a = before.get(k), after.get(k)
            same = (b is not None and b == a)
            ok = ok and same
            out(f"  {k}: {'一致' if same else '不一致!'}  前={b}  後={a}")
        out("  => " + ("★ 成功: 書き込みパイプライン実証(内容バイト同一・ECU健全)"
                       if ok else "⚠ 不一致: 要確認(電源入れ直しで復帰を試す)"))
    except Exception as e:  # noqa: BLE001
        out(f"!! 例外: {type(e).__name__}: {e}")
        raise
    finally:
        bus.shutdown()
        LOG_DIR.mkdir(exist_ok=True)
        p = LOG_DIR / f"flash_writeback_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
        p.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nsaved: {p}")


if __name__ == "__main__":
    main()
