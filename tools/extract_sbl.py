"""CANログ(フラッシュセッション)から SBL とプログラムデータを抽出する。

RomDrop の candump.raw / nc-flash・mx5studio・EcuFlash での実書き込みを1回
キャプチャしたCANログがあれば、その 0x7E0(要求ID)側の ISO-TP を再構成し、
RequestDownload(0x34)以降の TransferData(0x36)ペイロードを連結 →
先頭 0x1800 バイト = SBL、残り = プログラムデータ、として取り出す
(SBLはフラッシュ中に平文で流れるため)。

本個体(NC1 / CALID LFG7EG000 / start=0x2000)で使える SBL かどうかを多重に検証し、
キャプチャの取りこぼし(フレーム欠落・部分書き込み・別世代)は**強い警告**で弾く
(壊れたSBLを実機に流すとブリックするため)。

対応フォーマット(自動判定):
  - SocketCAN candump -L ログ :      (1612.34) can0 7E0#100E340000800000
  - SocketCAN candump 既定出力 :      can0  7E0  [8]  10 0E 34 00 00 80 00
  - 一般 ID#DATA テキスト      :      7E0#100E34...
  - Vector / SavvyCAN .asc     :      0.000 1  7E0  Tx  d 8 10 0E 34 ...   (Rx/Tx両対応)
  - SavvyCAN / GVRET .csv      :      Time Stamp,ID,Extended,Dir,Bus,LEN,D1..D8
  - 生バイナリ(candump.raw等) :      レコード構造を推定、--bin-* で上書き可

使い方:
  python tools/extract_sbl.py <logfile> [--req-id 7E0] [--out-dir .]
  python tools/extract_sbl.py <logfile> --inspect        # フォーマット診断(先頭をダンプ)
  python tools/extract_sbl.py --selftest                 # 合成ログ(全形式)で抽出ロジックを検証

キャプチャ手順(①自前キャプチャ・ルート):
  1. SBLを内蔵する既存ツール(nc-flash 配布バイナリ / mx5studio / EcuFlash+kernel)で
     予備ECUを**1回だけ**フル書き込み(同一内容の無害な再書込みで十分)。
  2. 同時に CAN を記録(candump -L can0 > flash.log 等)。full-flash(start=0x2000)にすること
     — 部分/動的書き込みのキャプチャは SBL が別物で使えない。
  3. python tools/extract_sbl.py flash.log  →  sbl.bin(0x1800, NC1)が出れば成功。
  4. python tools/flash_writeback.py --sbl sbl.bin   (まずドライラン。--confirm で実書込み)
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

SBL_SIZE = 0x1800
REQ_ID = 0x7E0
DOWNLOAD_ADDR = 0x8000
DOWNLOAD_SIZE = 0xFF800          # 実機が受理する唯一値 = SBL(0x1800) + 補正ROM[0x2000:](0xFE000)
BLOCK_SIZE = 0x400              # TransferData データ長/ブロック(実機 74 04 01)
SID_REQUEST_DOWNLOAD = 0x34
SID_TRANSFER_DATA = 0x36
SID_TRANSFER_EXIT = 0x37

_GEN = {0x35: "NC1", 0x36: "NC2", 0x37: "NC2"}


# ---------------- CAN frame readers (text) ----------------
def _clean_hex(tok: str) -> str:
    tok = tok.strip()
    if tok[:2].lower() == "0x":
        tok = tok[2:]
    return tok


def _bytes_from_tokens(tokens, dlc=None) -> bytes:
    out = bytearray()
    for t in tokens:
        t = _clean_hex(t)
        if len(t) == 2 and re.fullmatch(r"[0-9A-Fa-f]{2}", t):
            out.append(int(t, 16))
    if dlc is not None:
        out = out[:dlc]
    return bytes(out)


# per-line matchers
_RE_HASH = re.compile(r"(?:\(\s*[\d.]+\)\s*)?(?:\S+\s+)?([0-9A-Fa-f]{3,8})#([0-9A-Fa-f]*)")
_RE_BRACKET = re.compile(r"(?:0x)?([0-9A-Fa-f]{3,8})\s+\[(\d+)\]\s+((?:(?:0x)?[0-9A-Fa-f]{2}\s*)+)")
_RE_ASC = re.compile(r"\b(?:0x)?([0-9A-Fa-f]{3,8})\s+(?:Rx|Tx)\s+d\s+(\d+)\s+((?:(?:0x)?[0-9A-Fa-f]{2}\s*)+)", re.I)


def _parse_csv_header(line: str):
    """SavvyCAN/GVRET CSV ヘッダなら列インデックス dict を返す。違えば None。"""
    low = line.lower()
    if "," not in line or "id" not in low:
        return None
    cols = [c.strip().strip('"').lower() for c in line.split(",")]
    if "id" not in cols:
        return None
    idx = {"id": cols.index("id")}
    for name in ("len", "dlc"):
        if name in cols:
            idx["len"] = cols.index(name)
            break
    # D1..D8 / data0.. のバイト列開始
    data_start = None
    for i, c in enumerate(cols):
        if re.fullmatch(r"d\d+|data\d*|b\d+", c):
            data_start = i
            break
    if data_start is None and "len" in idx:
        data_start = idx["len"] + 1
    if data_start is None:
        return None
    idx["data_start"] = data_start
    idx["dir"] = cols.index("dir") if "dir" in cols else None
    return idx


def _parse_text(data: str):
    """candump ログ / ID#HEX / bracket / ASC / CSV から (id, bytes) を列挙。"""
    frames = []
    csv_cols = None
    for line in data.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "//", ";")) and "#" not in s[1:]:
            # コメント行(先頭 # だが ID#DATA ではない)
            if s.startswith(("//", ";")):
                continue
        # 1) CSV
        if csv_cols is None:
            hdr = _parse_csv_header(s)
            if hdr is not None:
                csv_cols = hdr
                continue
        if csv_cols is not None and "," in s:
            parts = [p.strip().strip('"') for p in s.split(",")]
            try:
                cid = int(_clean_hex(parts[csv_cols["id"]]), 16)
            except (ValueError, IndexError):
                continue
            dlc = None
            if "len" in csv_cols and csv_cols["len"] < len(parts):
                try:
                    dlc = int(parts[csv_cols["len"]])
                except ValueError:
                    dlc = None
            toks = parts[csv_cols["data_start"]:]
            frames.append((cid, _bytes_from_tokens(toks, dlc)))
            continue
        # 2) ID#DATA
        if "#" in s:
            m = _RE_HASH.search(s)
            if m:
                cid = int(m.group(1), 16)
                hexs = m.group(2)
                if len(hexs) % 2:
                    hexs = hexs[:-1]
                frames.append((cid, bytes.fromhex(hexs)))
                continue
        # 3) ASC (Rx/Tx d <dlc> <bytes>)
        m = _RE_ASC.search(s)
        if m:
            cid = int(m.group(1), 16)
            dlc = int(m.group(2))
            frames.append((cid, _bytes_from_tokens(m.group(3).split(), dlc)))
            continue
        # 4) candump 既定出力 (iface ID [dlc] b b b)
        m = _RE_BRACKET.search(s)
        if m:
            cid = int(m.group(1), 16)
            dlc = int(m.group(2))
            frames.append((cid, _bytes_from_tokens(m.group(3).split(), dlc)))
            continue
    return frames


# ---------------- CAN frame readers (binary) ----------------
def _parse_binary(raw: bytes, rec_len=None, id_off=None, data_off=None, id_size=4):
    """生バイナリから (id, 8bytes) を推定抽出。既定はヒューリスティック。"""
    frames = []
    if rec_len and id_off is not None and data_off is not None:
        for o in range(0, len(raw) - rec_len + 1, rec_len):
            cid_le = int.from_bytes(raw[o + id_off:o + id_off + id_size], "little")
            cid_be = int.from_bytes(raw[o + id_off:o + id_off + id_size], "big")
            use = cid_le if (cid_le & 0x7FF) in (0x7E0, 0x7E8) else cid_be
            frames.append((use & 0x7FF, raw[o + data_off:o + data_off + 8]))
        return frames
    # ヒューリスティック: 0x7E0/0x7E8 を含む 4バイト境界の周期からレコード長を推定
    positions = []
    anchors = [(0x7E0).to_bytes(4, "little"), (0x7E0).to_bytes(4, "big"),
               (0x7E8).to_bytes(4, "little"), (0x7E8).to_bytes(4, "big")]
    for i in range(len(raw) - 4):
        if raw[i:i + 4] in anchors:
            positions.append(i)
    if len(positions) >= 3:
        diffs = collections.Counter(positions[i + 1] - positions[i] for i in range(len(positions) - 1))
        rl = diffs.most_common(1)[0][0]
        if 12 <= rl <= 64:
            # 同一レコード内の 0x7E0 の相対位置を多数決で決める
            id0 = collections.Counter(p % rl for p in positions).most_common(1)[0][0]
            # id の後ろのデータ位置はフォーマット依存(id直後 / id+dlc / SocketCAN can_frame=id+8)。
            # 候補を試し、0x34(RequestDownload)が再構成できる配置を採用する。
            for doff in (id0 + 8, id0 + 5, id0 + 4):
                if doff + 8 > rl:
                    continue
                fr = _parse_binary(raw, rec_len=rl, id_off=id0, data_off=doff, id_size=4)
                if _has_request_download(fr):
                    return fr
    raise ValueError("binary format not auto-detected; use --inspect and "
                     "set --bin-record-len/--bin-id-off/--bin-data-off")


def _has_request_download(frames, req_id=REQ_ID) -> bool:
    msgs, _ = reassemble_isotp(frames, req_id)
    return any(m and m[0] == SID_REQUEST_DOWNLOAD for m in msgs)


def read_frames(path: pathlib.Path, binargs=None):
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None:
        fr = _parse_text(text)
        if fr:
            return fr, "text"
    if binargs and binargs.get("rec_len"):
        return _parse_binary(raw, binargs["rec_len"], binargs["id_off"], binargs["data_off"]), "binary(manual)"
    return _parse_binary(raw), "binary(auto)"


# ---------------- offline ISO-TP reassembly ----------------
def reassemble_isotp(frames, req_id=REQ_ID, stats=None):
    """req_id の ISO-TP メッセージ列を返す。FC(ECU側)は無視して連結。

    連結フレーム(CF)のシーケンス番号(SN)欠落・順序乱れ、未完メッセージを
    stats に記録する(サイレント破損検知)。戻り値 = (msgs, stats)。
    """
    if stats is None:
        stats = {}
    stats.setdefault("sn_errors", 0)
    stats.setdefault("incomplete", 0)
    msgs = []
    pending = None  # [total, buf, next_sn]
    for cid, data in frames:
        if cid != req_id or not data:
            continue
        pci = data[0] >> 4
        if pending is None:
            if pci == 0:  # Single Frame
                n = data[0] & 0x0F
                if n == 0 and len(data) >= 2:  # CAN-FD escape SF
                    n = data[1]
                    msgs.append(bytes(data[2:2 + n]))
                else:
                    msgs.append(bytes(data[1:1 + n]))
            elif pci == 1:  # First Frame
                n = ((data[0] & 0x0F) << 8) | data[1]
                if n == 0 and len(data) >= 6:  # escape FF: 10 00 <4B len>
                    n = int.from_bytes(data[2:6], "big")
                    first = data[6:8]
                else:
                    first = data[2:8]
                pending = [n, bytearray(first), 1]
            # 単独の CF/FC(pending無し)は無視
        else:
            if pci == 2:  # Consecutive Frame
                sn = data[0] & 0x0F
                if sn != pending[2]:
                    stats["sn_errors"] += 1
                pending[1] += data[1:8]
                pending[2] = (pending[2] + 1) & 0x0F
                if len(pending[1]) >= pending[0]:
                    msgs.append(bytes(pending[1][:pending[0]]))
                    pending = None
            elif pci == 1:  # 新FFが割り込み → 前メッセージ未完
                stats["incomplete"] += 1
                n = ((data[0] & 0x0F) << 8) | data[1]
                first = data[2:8] if n else data[6:8]
                pending = [n or int.from_bytes(data[2:6], "big"), bytearray(first), 1]
    if pending is not None:
        stats["incomplete"] += 1
        msgs.append(bytes(pending[1][:pending[0]]))  # best effort
    return msgs, stats


# ---------------- flash-session extraction ----------------
def _scan_sessions(msgs):
    """msgs 中の各 RequestDownload(0x34)について、続く 0x36 を連結した
    フラッシュセッション候補を列挙。"""
    sessions = []
    dl_indices = [i for i, m in enumerate(msgs) if m and m[0] == SID_REQUEST_DOWNLOAD]
    for k, dl_idx in enumerate(dl_indices):
        rd = msgs[dl_idx]
        dl_addr = dl_size = None
        if len(rd) >= 9:
            dl_addr = int.from_bytes(rd[1:5], "big")
            dl_size = int.from_bytes(rd[5:9], "big")
        stream = bytearray()
        block_lens = []
        stop = dl_indices[k + 1] if k + 1 < len(dl_indices) else len(msgs)
        for m in msgs[dl_idx + 1:stop]:
            if not m:
                continue
            if m[0] == SID_TRANSFER_DATA:
                stream += m[1:]
                block_lens.append(len(m) - 1)
            elif m[0] == SID_TRANSFER_EXIT:
                break
        sessions.append({
            "rd": rd, "dl_addr": dl_addr, "dl_size": dl_size,
            "stream": bytes(stream), "block_lens": block_lens,
        })
    return sessions


def extract(frames, req_id=REQ_ID):
    stats = {}
    msgs, stats = reassemble_isotp(frames, req_id, stats)
    sessions = _scan_sessions(msgs)
    if not sessions:
        raise ValueError("RequestDownload (0x34) not found in request stream "
                         f"(0x{req_id:X} の ISO-TP メッセージ {len(msgs)}件)")

    # 最良セッションを選択: dl_size==0xFF800 を最優先、次いで転送量最大
    def score(s):
        return (1 if s["dl_size"] == DOWNLOAD_SIZE else 0, len(s["stream"]))
    sess = max(sessions, key=score)

    stream = sess["stream"]
    sbl = stream[:SBL_SIZE]
    program = stream[SBL_SIZE:]
    dl_addr, dl_size = sess["dl_addr"], sess["dl_size"]
    block_lens = sess["block_lens"]

    info = {
        "request_download": sess["rd"].hex(" "),
        "sessions_found": len(sessions),
        "transfer_blocks": len(block_lens),
        "total_transferred": len(stream),
    }
    if dl_addr is not None:
        info["dl_addr"] = f"0x{dl_addr:X}"
        info["dl_size"] = f"0x{dl_size:X}"
    # 観測ブロック長(最終ブロック以外の最頻値)
    observed_block = None
    if block_lens:
        body = block_lens[:-1] or block_lens
        observed_block = collections.Counter(body).most_common(1)[0][0]
        info["observed_block"] = f"0x{observed_block:X}"
    gen = None
    if len(program) > 0x30:
        gen = _GEN.get(program[0x30], f"UNKNOWN(0x{program[0x30]:02X})")
        info["capture_generation"] = gen

    # --- このキャプチャが本個体(NC1/full-flash)に使える SBL かを検証 ---
    warnings = []
    # サイレント破損(最重要): フレーム欠落・順序乱れ・未完
    if stats["sn_errors"]:
        warnings.append(f"★致命: 連結フレームのSN不整合 {stats['sn_errors']}件 "
                        "= フレーム欠落/順序乱れ。SBLは破損の可能性大。書き込まず再キャプチャを。")
    if stats["incomplete"]:
        warnings.append(f"★致命: 未完ISO-TPメッセージ {stats['incomplete']}件 "
                        "= ログが途中欠落。SBLが不完全。書き込まず再キャプチャを。")
    if len(sbl) != SBL_SIZE:
        warnings.append(f"SBL size 0x{len(sbl):X} != 0x{SBL_SIZE:X} "
                        "(転送が短い=キャプチャ不完全 or 部分書き込み)")
    if dl_size is not None and dl_size != DOWNLOAD_SIZE:
        warnings.append(f"RequestDownload size 0x{dl_size:X} != 0x{DOWNLOAD_SIZE:X} "
                        "(=部分/動的書き込みのキャプチャ。full-flash/start=0x2000 のSBLではない)")
    if dl_addr is not None and dl_addr != DOWNLOAD_ADDR:
        warnings.append(f"RequestDownload addr 0x{dl_addr:X} != 0x{DOWNLOAD_ADDR:X} "
                        "(別モデル/別ハンドシェイクのキャプチャの可能性)")
    if observed_block is not None and observed_block != BLOCK_SIZE:
        warnings.append(f"観測ブロック長 0x{observed_block:X} != 0x{BLOCK_SIZE:X} "
                        "(本個体は 0x400。別ECUのキャプチャの可能性)")
    if gen is not None and gen != "NC1":
        warnings.append(f"capture generation={gen} (本個体は NC1。NC1 のキャプチャが必要)")
    warnings += _sbl_sanity(sbl)
    info["isotp_sn_errors"] = stats["sn_errors"]
    info["isotp_incomplete"] = stats["incomplete"]
    info["warnings"] = warnings
    return sbl, program, info


def _sbl_sanity(sbl: bytes):
    """SBL が「コードらしく」ないと警告(空白/パディングを掴んでいないか)。"""
    issues = []
    if not sbl:
        return ["SBL empty"]
    c = collections.Counter(sbl)
    top, topn = c.most_common(1)[0]
    if topn / len(sbl) > 0.6:
        issues.append(f"SBLの{topn * 100 // len(sbl)}%が 0x{top:02X} "
                      "(空白/パディングを掴んでいる疑い=コードでない)")
    return issues


# ---------------- self test ----------------
def _synth_payload(gen_byte=0x35, prog_len=0x900):
    sbl = bytes((i * 7 + 3) & 0xFF for i in range(SBL_SIZE))
    prog = bytearray((i * 13 + 5) & 0xFF for i in range(prog_len))
    prog[0x30] = gen_byte  # program[0x30] = ROM@0x2030 = 世代バイト
    return sbl, bytes(prog)


def _isotp_frames(payload: bytes, can_id=REQ_ID):
    """payload を ISO-TP で CANフレーム列 [(id, bytes<=8)] に分割。"""
    out = []
    if len(payload) <= 7:
        out.append((can_id, bytes([len(payload)]) + payload))
        return out
    total = len(payload)
    out.append((can_id, bytes([0x10 | (total >> 8), total & 0xFF]) + payload[:6]))
    pos, sn = 6, 1
    while pos < total:
        out.append((can_id, bytes([0x20 | sn]) + payload[pos:pos + 7]))
        pos += 7
        sn = (sn + 1) & 0x0F
    return out


def _session_frames(sbl, program, dl_size=DOWNLOAD_SIZE):
    """1フラッシュセッション分の CANフレーム列を生成。"""
    frames = []
    frames += _isotp_frames(bytes([SID_REQUEST_DOWNLOAD]) +
                            DOWNLOAD_ADDR.to_bytes(4, "big") + dl_size.to_bytes(4, "big"))
    data = sbl + program
    for o in range(0, len(data), BLOCK_SIZE):
        frames += _isotp_frames(bytes([SID_TRANSFER_DATA]) + data[o:o + BLOCK_SIZE])
    frames += _isotp_frames(bytes([SID_TRANSFER_EXIT]))
    return frames


# ---- renderers: 同一フレーム列を各形式のテキストに描画 ----
def _r_candump_log(frames):
    return "\n".join(f"(0.000000) can0 {cid:03X}#{d.hex().upper()}" for cid, d in frames)


def _r_candump_bracket(frames):
    out = []
    for cid, d in frames:
        bys = " ".join(f"{b:02X}" for b in d)
        out.append(f"  can0  {cid:03X}   [{len(d)}]  {bys}")
    return "\n".join(out)


def _r_asc(frames):
    out = ["date Mon Jan 1 00:00:00 2024", "base hex  timestamps absolute", "Begin Triggerblock"]
    for i, (cid, d) in enumerate(frames):
        bys = " ".join(f"{b:02X}" for b in d)
        out.append(f"   {i * 0.001:.6f} 1  {cid:X}             Tx   d {len(d)} {bys}")
    out.append("End Triggerblock")
    return "\n".join(out)


def _r_csv(frames):
    out = ["Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8"]
    for i, (cid, d) in enumerate(frames):
        cells = [f"0x{b:02X}" for b in d] + [""] * (8 - len(d))
        out.append(f"{i},0x{cid:X},false,Tx,0,{len(d)}," + ",".join(cells))
    return "\n".join(out)


def _r_binary(frames):
    """固定長レコード: [ts4 LE][id4 LE][dlc1][data8] = 17B/rec。"""
    out = bytearray()
    for i, (cid, d) in enumerate(frames):
        out += i.to_bytes(4, "little")
        out += cid.to_bytes(4, "little")
        out += bytes([len(d)])
        out += d + bytes(8 - len(d))
    return bytes(out)


def _selftest():
    sbl, program = _synth_payload()
    frames = _session_frames(sbl, program)
    ok_all = True

    # 1) 全テキスト形式でクロス検証
    renderers = {
        "candump -L": _r_candump_log,
        "candump []": _r_candump_bracket,
        "asc (Tx)": _r_asc,
        "csv": _r_csv,
    }
    for name, r in renderers.items():
        fr = _parse_text(r(frames))
        got_sbl, got_prog, info = extract(fr)
        ok = got_sbl == sbl and got_prog == program and not info["warnings"]
        ok_all &= ok
        print(f"  [{name:11}] frames={len(fr):4} sbl={'OK' if got_sbl==sbl else 'NG'} "
              f"prog={'OK' if got_prog==program else 'NG'} warn={len(info['warnings'])} -> {'OK' if ok else 'FAIL'}")

    # 2) バイナリ(手動オフセット)
    raw = _r_binary(frames)
    fr = _parse_binary(raw, rec_len=17, id_off=4, data_off=9)
    got_sbl, got_prog, _ = extract(fr)
    okb = got_sbl == sbl and got_prog == program
    ok_all &= okb
    print(f"  [binary(man) ] recs={len(fr):4} -> {'OK' if okb else 'FAIL'}")
    # 2b) バイナリ自動判定
    try:
        fr_auto = _parse_binary(raw)
        got_sbl2, _, _ = extract(fr_auto)
        print(f"  [binary(auto)] -> {'OK' if got_sbl2==sbl else 'FAIL'}")
        ok_all &= got_sbl2 == sbl
    except Exception as e:  # noqa
        print(f"  [binary(auto)] -> FAIL ({e})")
        ok_all = False

    # 3) 異常系: 本来警告が出るべきケース
    print("  --- 異常系(警告が出れば正常) ---")
    # 3a NC2 世代
    sbl2, prog2 = _synth_payload(gen_byte=0x36)
    _, _, info = extract(_parse_text(_r_candump_log(_session_frames(sbl2, prog2))))
    w = any("generation" in x for x in info["warnings"])
    print(f"  [NC2 capture ] warn-gen={'OK' if w else 'FAIL'}"); ok_all &= w
    # 3b 部分書き込み(dl_size != 0xFF800)
    _, _, info = extract(_parse_text(_r_candump_log(_session_frames(sbl, program, dl_size=0x40000))))
    w = any("!= 0xFF800" in x for x in info["warnings"])
    print(f"  [partial size] warn-size={'OK' if w else 'FAIL'}"); ok_all &= w
    # 3c 連結フレーム1枚脱落 → SN不整合検知
    fr = _parse_text(_r_candump_log(frames))
    # 最初の 0x36 セッション内の CF を1枚間引く
    dropped = []
    removed = False
    for cid, d in fr:
        if not removed and cid == REQ_ID and d and (d[0] >> 4) == 2 and (d[0] & 0x0F) == 3:
            removed = True  # SN=3 の CF を1枚落とす
            continue
        dropped.append((cid, d))
    _, _, info = extract(dropped)
    w = info["isotp_sn_errors"] > 0 or info["isotp_incomplete"] > 0
    print(f"  [dropped CF  ] warn-corrupt={'OK' if w else 'FAIL'}"); ok_all &= w

    print("SELFTEST:", "OK" if ok_all else "FAIL")
    return ok_all


def main():
    try:  # cp932 コンソールでの日本語/N·m 文字化け回避
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", nargs="?", help="CAN log (candump.raw / .log / .asc / .csv)")
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
        print("first 64 bytes hex:\n" + raw[:64].hex(" "))
        try:
            print("first 3 lines:\n  " + "\n  ".join(raw.decode("utf-8", "replace").splitlines()[:3]))
        except Exception:  # noqa
            pass
        occ = [i for i in range(len(raw) - 3)
               if raw[i:i + 4] in ((0x7E0).to_bytes(4, "little"), (0x7E0).to_bytes(4, "big"))][:8]
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
    print(f"SBL: {len(sbl)} bytes -> {outd / 'sbl.bin'}   "
          f"{'(0x1800 OK)' if len(sbl) == SBL_SIZE else '(!! size != 0x1800)'}")
    print(f"program: {len(program)} bytes -> {outd / 'program.bin'}")
    if warnings:
        print("\n!! 警告(このSBLは本個体に使えない/壊れている可能性):")
        for w in warnings:
            print("   - " + w)
        print("\n★ 警告がある間は flash_writeback に渡さないこと(ブリック防止)。full-flash/NC1/無欠落で再取得を。")
        sys.exit(2)
    print("\nOK: NC1 / full-flash(start=0x2000) / 無欠落 の妥当なSBL。")
    print("    次: python tools/flash_writeback.py --sbl " + str(outd / "sbl.bin") + "   (まずドライラン)")


if __name__ == "__main__":
    main()
