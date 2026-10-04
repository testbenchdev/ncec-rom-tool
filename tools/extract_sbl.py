"""CANログ(フラッシュセッション)から SBL とプログラムデータを抽出する。

RomDrop の candump.raw など、実機を1回フラッシュしたCANキャプチャがあれば、
その 0x7E0(要求ID)側の ISO-TP を再構成し、RequestDownload(0x34)以降の
TransferData(0x36)ペイロードを連結 → 先頭 0x1800 バイト = SBL、残り = プログラムデータ、
として取り出す(SBLはフラッシュ中に平文で流れるため)。

対応フォーマット(自動判定):
  - SocketCAN candump テキストログ:  (ts) can0 7E0#021001   /  7E0#021001
  - python-can .asc (簡易)
  - 生バイナリ(RomDrop candump.raw 等): レコード構造を推定、--bin-* で上書き可

使い方:
  python tools/extract_sbl.py <logfile> [--req-id 7E0] [--out-dir .]
  python tools/extract_sbl.py <logfile> --inspect        # フォーマット診断(先頭をダンプ)
  python tools/extract_sbl.py --selftest                 # 合成ログで抽出ロジックを検証
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

SBL_SIZE = 0x1800
REQ_ID = 0x7E0
SID_REQUEST_DOWNLOAD = 0x34
SID_TRANSFER_DATA = 0x36
SID_TRANSFER_EXIT = 0x37


# ---------------- CAN frame readers ----------------
def _parse_text(data: str):
    """candump ログ / 一般的な ID#HEX テキストから (id, bytes) を列挙。"""
    frames = []
    # (ts) iface ID#DATA  または  ID#DATA   (IDは3 or 8 hex)
    pat = re.compile(r"(?:\(\s*[\d.]+\)\s*)?(?:\S+\s+)?([0-9A-Fa-f]{3,8})#([0-9A-Fa-f]*)")
    # python-can asc 形式: "... <id> Rx d <len> b0 b1 ..." も拾う
    asc = re.compile(r"\b([0-9A-Fa-f]{3,8})\s+Rx\s+d\s+(\d+)\s+((?:[0-9A-Fa-f]{2}\s+)+)", re.I)
    for line in data.splitlines():
        m = asc.search(line)
        if m:
            cid = int(m.group(1), 16)
            bys = bytes(int(x, 16) for x in m.group(3).split())
            frames.append((cid, bys))
            continue
        m = pat.search(line.strip())
        if m and "#" in line:
            cid = int(m.group(1), 16)
            hexs = m.group(2)
            if len(hexs) % 2:
                hexs = hexs[:-1]
            frames.append((cid, bytes.fromhex(hexs)))
    return frames


def _parse_binary(raw: bytes, rec_len=None, id_off=None, data_off=None, id_size=4):
    """生バイナリから (id, 8bytes) を推定抽出。既定はヒューリスティック。

    多くの candump バイナリは固定長レコード [timestamp..][id][dlc][data8..] 形式。
    レコード長・オフセット不明時は、7E0/7E8 が周期的に現れる位置からレコード長を推定する。
    """
    frames = []
    if rec_len and id_off is not None and data_off is not None:
        for o in range(0, len(raw) - rec_len + 1, rec_len):
            cid = int.from_bytes(raw[o + id_off:o + id_off + id_size], "little")
            cid2 = int.from_bytes(raw[o + id_off:o + id_off + id_size], "big")
            # どちらのエンディアンでも 0x7E0/0x7E8 を優先
            use = cid if cid in (0x7E0, 0x7E8) else cid2
            frames.append((use & 0x7FF, raw[o + data_off:o + data_off + 8]))
        return frames
    # ヒューリスティック: 0x7E0 を含む 4バイト境界を探し、間隔からレコード長を推定
    import collections
    positions = []
    target = (0x7E0).to_bytes(4, "little")
    target_be = (0x7E0).to_bytes(4, "big")
    for i in range(len(raw) - 4):
        if raw[i:i + 4] == target or raw[i:i + 4] == target_be:
            positions.append(i)
    if len(positions) >= 3:
        diffs = collections.Counter(positions[i + 1] - positions[i] for i in range(len(positions) - 1))
        rl = diffs.most_common(1)[0][0]
        if 12 <= rl <= 64:
            id0 = positions[0] % rl
            be = raw[positions[0]:positions[0] + 4] == target_be
            # data は id の直後 + dlc(1〜数バイト) と仮定 → id_off+4 から 8バイト
            return _parse_binary(raw, rec_len=rl, id_off=id0, data_off=id0 + 4, id_size=4)
    raise ValueError("binary format not auto-detected; use --inspect and set --bin-record-len/--bin-id-off/--bin-data-off")


def read_frames(path: pathlib.Path, binargs=None):
    raw = path.read_bytes()
    # テキストっぽいか判定
    try:
        text = raw.decode("utf-8")
        if "#" in text or re.search(r"\bRx\s+d\b", text):
            fr = _parse_text(text)
            if fr:
                return fr, "text"
    except UnicodeDecodeError:
        pass
    if binargs and binargs.get("rec_len"):
        return _parse_binary(raw, binargs["rec_len"], binargs["id_off"], binargs["data_off"]), "binary(manual)"
    return _parse_binary(raw), "binary(auto)"


# ---------------- offline ISO-TP reassembly ----------------
def reassemble_isotp(frames, req_id=REQ_ID):
    """req_id の ISO-TP メッセージ列(bytesのリスト)を返す。FC(ECU側)は無視して連結。"""
    msgs = []
    pending = None  # (remaining, buf, next_sn)
    for cid, data in frames:
        if cid != req_id or not data:
            continue
        pci = data[0] >> 4
        if pending is None:
            if pci == 0:  # Single Frame
                n = data[0] & 0x0F
                msgs.append(bytes(data[1:1 + n]))
            elif pci == 1:  # First Frame
                total = ((data[0] & 0x0F) << 8) | data[1]
                buf = bytearray(data[2:8])
                pending = [total, buf, 1]
        else:
            if pci == 2:  # Consecutive Frame
                pending[1] += data[1:8]
                pending[2] = (pending[2] + 1) & 0x0F
                if len(pending[1]) >= pending[0]:
                    msgs.append(bytes(pending[1][:pending[0]]))
                    pending = None
    return msgs


# ---------------- flash-session extraction ----------------
def extract(frames, req_id=REQ_ID):
    msgs = reassemble_isotp(frames, req_id)
    # RequestDownload を探す
    dl_idx = next((i for i, m in enumerate(msgs) if m and m[0] == SID_REQUEST_DOWNLOAD), None)
    if dl_idx is None:
        raise ValueError("RequestDownload (0x34) not found in request stream")
    rd = msgs[dl_idx]
    info = {"request_download": rd.hex(" ")}
    # RequestDownload の addr/size を解釈(34 <addr4> <size4>)
    dl_addr = dl_size = None
    if len(rd) >= 9:
        dl_addr = int.from_bytes(rd[1:5], "big")
        dl_size = int.from_bytes(rd[5:9], "big")
        info["dl_addr"] = f"0x{dl_addr:X}"
        info["dl_size"] = f"0x{dl_size:X}"
    # 以降の TransferData(0x36) ペイロードを TransferExit まで連結
    stream = bytearray()
    nblocks = 0
    for m in msgs[dl_idx + 1:]:
        if not m:
            continue
        if m[0] == SID_TRANSFER_DATA:
            stream += m[1:]
            nblocks += 1
        elif m[0] == SID_TRANSFER_EXIT:
            break
    info["transfer_blocks"] = nblocks
    info["total_transferred"] = len(stream)
    sbl = bytes(stream[:SBL_SIZE])
    program = bytes(stream[SBL_SIZE:])

    # --- このキャプチャが使える SBL か検証 ---
    warnings = []
    if len(sbl) != SBL_SIZE:
        warnings.append(f"SBL size 0x{len(sbl):X} != 0x{SBL_SIZE:X}")
    # フル書き込み(start=0x2000)なら total=0xFF800。これ以外はSBLが別物(部分書き込み)
    if dl_size is not None and dl_size != 0xFF800:
        warnings.append(f"RequestDownload size 0x{dl_size:X} != 0xFF800 "
                        "(=部分/動的書き込みのキャプチャ。full-flash/start=0x2000 のSBLではない)")
    # program = 補正ROM[0x2000:] なので program[0x30] = ROM@0x2030 = 世代バイト(0x35=NC1)
    gen = None
    if len(program) > 0x30:
        gb = program[0x30]
        gen = {0x35: "NC1", 0x36: "NC2", 0x37: "NC2"}.get(gb, f"UNKNOWN(0x{gb:02X})")
        info["capture_generation"] = gen
        if gen != "NC1":
            warnings.append(f"capture generation={gen} (本個体は NC1。NC1 のキャプチャが必要)")
    info["warnings"] = warnings
    return sbl, program, info


# ---------------- self test ----------------
def _build_synth_log():
    """合成: 34 + (SBL 0x1800 + program) を 0x36/0x400ブロックで ISO-TP フレーム化した candumpテキスト。"""
    import struct  # noqa
    sbl = bytes((i * 7 + 3) & 0xFF for i in range(SBL_SIZE))
    prog = bytearray((i * 13 + 5) & 0xFF for i in range(0x900))
    prog[0x30] = 0x35  # program[0x30] = ROM@0x2030 = 世代バイト(NC1)
    program = bytes(prog)
    lines = []

    def emit(payload):
        # ISO-TP フレーム化(req 0x7E0)
        if len(payload) <= 7:
            d = bytes([len(payload)]) + payload
            lines.append(f"(0.0) can0 7E0#{d.hex().upper()}")
            return
        total = len(payload)
        ff = bytes([0x10 | (total >> 8), total & 0xFF]) + payload[:6]
        lines.append(f"(0.0) can0 7E0#{ff.hex().upper()}")
        pos, sn = 6, 1
        while pos < total:
            cf = bytes([0x20 | sn]) + payload[pos:pos + 7]
            lines.append(f"(0.0) can0 7E0#{cf.hex().upper()}")
            pos += 7
            sn = (sn + 1) & 0x0F

    emit(bytes([0x34]) + (0x8000).to_bytes(4, "big") + (0xFF800).to_bytes(4, "big"))
    data = sbl + program
    for o in range(0, len(data), 0x400):
        emit(bytes([0x36]) + data[o:o + 0x400])
    emit(bytes([0x37]))
    return "\n".join(lines), sbl, program


def _selftest():
    text, sbl, program = _build_synth_log()
    frames = _parse_text(text)
    got_sbl, got_prog, info = extract(frames)
    ok = (got_sbl == sbl and got_prog == program)
    print("synth frames:", len(frames), "| info:", info)
    print("SBL match:", got_sbl == sbl, "| program match:", got_prog == program)
    print("SELFTEST:", "OK" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", nargs="?", help="CAN log (candump.raw / .log / .asc)")
    ap.add_argument("--req-id", default="7E0")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--inspect", action="store_true", help="先頭をダンプしてフォーマット診断")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bin-record-len", type=int)
    ap.add_argument("--bin-id-off", type=int)
    ap.add_argument("--bin-data-off", type=int)
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if _selftest() else 1)
    if not args.logfile:
        ap.error("logfile required (or --selftest)")
    path = pathlib.Path(args.logfile)
    req_id = int(args.req_id, 16)

    if args.inspect:
        raw = path.read_bytes()
        print(f"size: {len(raw)} bytes")
        print("first 64 bytes hex:")
        print(raw[:64].hex(" "))
        occ = [i for i in range(len(raw) - 3) if raw[i:i + 4] in ((0x7E0).to_bytes(4, "little"), (0x7E0).to_bytes(4, "big"))][:8]
        print("0x7E0 (4-byte) positions:", [hex(x) for x in occ])
        return

    binargs = None
    if args.bin_record_len:
        binargs = {"rec_len": args.bin_record_len, "id_off": args.bin_id_off, "data_off": args.bin_data_off}
    frames, fmt = read_frames(path, binargs)
    print(f"format: {fmt}, frames: {len(frames)}")
    sbl, program, info = extract(frames, req_id)
    warnings = info.pop("warnings", [])
    print("info:", info)
    outd = pathlib.Path(args.out_dir)
    outd.mkdir(exist_ok=True)
    (outd / "sbl.bin").write_bytes(sbl)
    (outd / "program.bin").write_bytes(program)
    print(f"SBL: {len(sbl)} bytes -> {outd/'sbl.bin'}   {'(0x1800 OK)' if len(sbl)==SBL_SIZE else '(!! size != 0x1800)'}")
    print(f"program: {len(program)} bytes -> {outd/'program.bin'}")
    if warnings:
        print("\n!! 警告(このSBLは本個体に使えない可能性):")
        for w in warnings:
            print("   - " + w)
    else:
        print("\nOK: NC1 / full-flash(start=0x2000) のSBLとして妥当。ncecu/flash.py の --sbl に使えます。")


if __name__ == "__main__":
    main()
