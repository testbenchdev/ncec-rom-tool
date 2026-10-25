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
    ap.add_argument("--rom", help="書き込むROM(既定=ncec_rom_dump.bin)。編集ROMはこれで指定")
    ap.add_argument("--confirm", action="store_true", help="実際に消去+書き込みを行う(不可逆)")
    ap.add_argument("--verify-u16", help="書込み後、このアドレス(hex)の16bit(BE)を読み戻して表示")
    args = ap.parse_args()

    pristine = DUMP.read_bytes()
    rom = pathlib.Path(args.rom).read_bytes() if args.rom else pristine
    edited = (rom != pristine)
    sbl = pathlib.Path(args.sbl).read_bytes() if args.sbl else None
    romname = (args.rom or DUMP.name)
    out(f"flash_writeback {datetime.datetime.now().isoformat(timespec='seconds')}")
    out(f"ROM: {romname}  size=0x{len(rom):X}  {'[編集ROM=純正ダンプと差分あり]' if edited else '[無改変=純正ダンプ]'}  SBL: "
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
        cb, ca = before.get("CALID"), after.get("CALID")
        vb, va = before.get("CVN"), after.get("CVN")
        calid_ok = (cb is not None and cb == ca)
        cvn_same = (vb is not None and vb == va)
        out(f"  CALID: {'一致' if calid_ok else '不一致!'}  前={cb}  後={ca}")
        if edited:
            # 編集ROM: 校正領域を変えたので CVN は「変わる」のが正常。
            out(f"  CVN: {'変化(編集反映=正常)' if not cvn_same else '不変(!)編集が効いていない可能性'}  前={vb}  後={va}")
            ok = calid_ok and (not cvn_same) and (va is not None)
            out("  => " + ("★ 成功: 編集ROM書込み・ECU健全(CALID不変・CVN変化=校正更新反映)"
                           if ok else "⚠ 要確認: CALID不一致 or CVN不変 or 無応答(電源入れ直し+probeで確認)"))
        else:
            ok = calid_ok and cvn_same
            out(f"  CVN: {'一致' if cvn_same else '不一致!'}  前={vb}  後={va}")
            out("  => " + ("★ 成功: 書き込みパイプライン実証(内容バイト同一・ECU健全)"
                           if ok else "⚠ 不一致: 要確認(電源入れ直しで復帰を試す)"))

        if args.verify_u16:
            addr = int(args.verify_u16, 16)
            out(f"[5] 読み戻し確認 @0x{addr:X} (Mode23)")
            try:
                f.authenticate()
                data = f.read_memory(addr, 2)
                val = (data[0] << 8) | data[1]
                exp = (rom[addr] << 8) | rom[addr + 1]
                out(f"  実機={val} (0x{val:04X})  期待(書込ROM)={exp} (0x{exp:04X})  "
                    f"{'一致=パッチ反映確認' if val == exp else '不一致!'}")
                out("  ※ 読み戻しでプログラミングセッションに入ったので、車両搭載前に一度電源を入れ直すこと。")
            except Exception as e:  # noqa
                out(f"  読み戻し失敗(致命ではない): {type(e).__name__}: {e}")
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
