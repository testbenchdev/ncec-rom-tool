"""nc-flash / mx5studio の配布バイナリ(PyInstaller等)から SBL(0x1800, NC1)を
**静的に**取り出す。ルート①-A:追加ハード不要・実機書込み不要・ブリック無し。

SBLはこれらツールのバイナリに内蔵されている(nc-flash: "SBL upload for programming
session"、mx5studio: "includes its own Secondary Boot Loader implementation")。
本スクリプトは配布物を**実行せず**、中の .pyc の定数列と同梱データを走査して
0x1800バイトの SH-2 コード塊(= SBL)を探す。`_SBL_NC1` のように名前付きで格納
されていれば、バイトコード(dis・非実行)から NC1 を判別する。

安全:
  - ダウンロードしたバイナリを **import も実行もしない**(marshal.loads + dis のみ)。
    marshal は未知データからコードオブジェクトを構築するが実行はしない。
  - 展開物は「信頼できないダウンロードデータ」。本スクリプトは別ディレクトリに置き、
    対象はパス引数で渡し、`python -I` で起動すること(カレント/対象dirからの副作用importを防ぐ)。

使い方:
  # 1) nc-flash を入手し、onefile .exe なら pyinstxtractor-ng で展開(.tar.gz onedir は展開のみ)
  #    python pyinstxtractor-ng.py NCFlash.exe        -> NCFlash.exe_extracted/
  # 2) 展開フォルダ / .tar.gz / .zip を渡す
  python -I tools/extract_sbl_from_binary.py <path-to-extracted-dir-or-archive> --out-dir out
  python -I tools/extract_sbl_from_binary.py --selftest
"""
from __future__ import annotations

import argparse
import bz2
import collections
import dis
import gzip
import io
import lzma
import marshal
import pathlib
import sys
import tarfile
import zipfile
import zlib

SBL_SIZE = 0x1800
_PYC_HEADER_OFFSETS = (16, 12, 8, 0)   # Python版/抽出ツールにより異なる


# ---------------- SH-2 "コードらしさ" 検証 ----------------
def _entropy(data: bytes) -> float:
    import math
    if not data:
        return 0.0
    c = collections.Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def validate_sh2(blob: bytes):
    """(ok, score 0..1, reasons[])。SBLは RAM 0x8000 で走る SH-2(ビッグエンディアン16bit命令)。

    重要: 実コードのバイトエントロピーは ~6–7.2 bit/byte。圧縮/暗号化/ランダムは ~8.0 に
    なり、他の指標(多様性・ニブル分布)も「コードっぽく」見えてしまうので、**エントロピーを
    ハードゲート**にして圧縮データの誤検出を弾く。"""
    reasons = []
    if len(blob) != SBL_SIZE:
        return False, 0.0, [f"size 0x{len(blob):X} != 0x{SBL_SIZE:X}"]
    c = collections.Counter(blob)
    top, topn = c.most_common(1)[0]
    dom = topn / len(blob)
    words = [int.from_bytes(blob[i:i + 2], "big") for i in range(0, len(blob), 2)]
    zero_w = sum(1 for w in words if w == 0) / len(words)
    distinct = len(set(words)) / len(words)
    nib = collections.Counter(w >> 12 for w in words)
    codey = sum(nib[n] for n in (0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9, 0xA, 0xB, 0xD, 0xE)) / len(words)
    ent = _entropy(blob)

    # ハードゲート: 高エントロピー=圧縮/暗号化/ランダム(SH-2コードは6KBで~8.0にならない)
    if ent > 7.5:
        return False, 0.0, [f"エントロピー {ent:.2f} bit/B が高すぎ(圧縮/暗号化/ランダム=コードでない)"]
    if dom > 0.6:
        return False, 0.0, [f"単一バイト {top:#04x} が{dom*100:.0f}%(パディング/空白)"]

    score = 0.0
    score += 0.25 if dom <= 0.5 else 0.0
    if zero_w <= 0.30:
        score += 0.15
    else:
        reasons.append(f"0x0000ワードが{zero_w*100:.0f}%")
    if distinct >= 0.20:
        score += 0.20
    else:
        reasons.append(f"ワード多様性 {distinct:.2f}(低=データ/繰り返し)")
    if codey >= 0.55:
        score += 0.20
    else:
        reasons.append(f"命令ニブル率 {codey:.2f}(低)")
    if 4.5 <= ent <= 7.2:
        score += 0.20
    else:
        reasons.append(f"エントロピー {ent:.2f}(コードの常域 5–7 から外れ)")
    ok = score >= 0.70
    return ok, round(score, 3), reasons


# ---------------- .pyc 解析(非実行) ----------------
def _load_code(data: bytes):
    """.pyc バイト列から module code object を復元(ヘッダ長を総当り)。失敗時 None。"""
    for off in _PYC_HEADER_OFFSETS:
        if off > len(data):
            continue
        try:
            obj = marshal.loads(data[off:])
        except Exception:  # noqa
            continue
        if hasattr(obj, "co_consts"):
            return obj
    return None


def _walk_codes(code):
    """code とネストした全 code object を列挙。"""
    yield code
    for const in code.co_consts:
        if hasattr(const, "co_consts"):
            yield from _walk_codes(const)


def _collect_bytes_consts(code):
    """全 code object の bytes/bytearray 定数を集める。"""
    out = []
    for c in _walk_codes(code):
        for const in c.co_consts:
            if isinstance(const, (bytes, bytearray)):
                out.append(bytes(const))
    return out


def _name_to_const(code):
    """LOAD_CONST <x>; STORE_NAME/STORE_GLOBAL/STORE_FAST <name> を dis で対応付け(非実行)。
    戻り: {name: const}。名前に NC1/NC2 が含まれる SBL を特定するのに使う。"""
    mapping = {}
    for c in _walk_codes(code):
        prev = None
        try:
            instrs = list(dis.get_instructions(c))
        except Exception:  # noqa
            continue
        for ins in instrs:
            if ins.opname == "LOAD_CONST":
                prev = ins.argval
            elif ins.opname in ("STORE_NAME", "STORE_GLOBAL", "STORE_FAST", "STORE_DEREF"):
                if isinstance(prev, (bytes, bytearray)):
                    mapping[ins.argval] = bytes(prev)
                prev = None
            else:
                prev = None
    return mapping


# ---------------- 圧縮/符号化の取り回し ----------------
def _maybe_decompress(data: bytes):
    """data とその各種解凍結果を列挙(SBLが圧縮格納されている場合に備える)。"""
    yield data
    for fn in (zlib.decompress, gzip.decompress, bz2.decompress, lzma.decompress):
        try:
            d = fn(data)
            if d and d != data:
                yield d
        except Exception:  # noqa
            pass


_SLIDE_CAP = 64 * 1024   # これ以下のファイルのみ総当りスライド走査(本命は.pycの名前付き定数)


def _windows_0x1800(data: bytes):
    """data 中の 0x1800 窓を列挙。完全一致サイズは即採用。大きいデータは
    スライド走査が高コストなので _SLIDE_CAP までに限定(本命は.pyc定数側)。"""
    n = len(data)
    if n == SBL_SIZE:
        yield 0, data
        return
    if n < SBL_SIZE or n > _SLIDE_CAP:
        return
    step = 2  # SH-2命令境界
    for o in range(0, n - SBL_SIZE + 1, step):
        head = data[o:o + 64]
        if head == head[:1] * 64:   # 全同一バイトの塊は捨てる(軽量プレフィルタ)
            continue
        yield o, data[o:o + SBL_SIZE]


# ---------------- 走査本体 ----------------
def _add_candidate(cands, data, source, name=None):
    if len(data) != SBL_SIZE:
        return
    ok, score, reasons = validate_sh2(data)
    key = data
    for c in cands:
        if c["data"] == key:  # 重複は名前/ソースを補強
            if name and not c.get("name"):
                c["name"] = name
            return
    cands.append({"data": data, "source": source, "name": name,
                  "ok": ok, "score": score, "reasons": reasons})


def _scan_blob(data: bytes, source: str, cands, name=None, force=False):
    """blob(と解凍結果)から 0x1800 候補を登録。
    ちょうど0x1800 と 名前付き(force) は常に採用、それ以外のスライド窓は
    SH-2検証に通った時だけ採用(低スコアのノイズを排除)。"""
    for d in _maybe_decompress(data):
        if len(d) == SBL_SIZE:
            _add_candidate(cands, d, source, name=name)
        else:
            for off, w in _windows_0x1800(d):
                if force or validate_sh2(w)[0]:
                    _add_candidate(cands, w, f"{source}@0x{off:X}", name=name)


def scan_pyc_bytes(data: bytes, source: str, cands):
    code = _load_code(data)
    if code is None:
        return
    for name, blob in _name_to_const(code).items():   # 名前付き(NC1/NC2判別用)
        _scan_blob(blob, f"{source}::{name}", cands, name=name, force=True)
    for blob in _collect_bytes_consts(code):           # その他の bytes 定数
        _scan_blob(blob, f"{source}::const", cands)


def scan_raw_bytes(data: bytes, source: str, cands):
    _scan_blob(data, source, cands)


def _process_member(name: str, data: bytes, cands):
    low = name.lower()
    if low.endswith(".pyc"):
        scan_pyc_bytes(data, name, cands)
    elif low.endswith((".py", ".txt", ".md", ".json", ".dll", ".so", ".exe")):
        return  # ソース/巨大バイナリは原則対象外(.pyc / データファイル優先)
    else:
        scan_raw_bytes(data, name, cands)  # 走査範囲は _windows_0x1800 側で制限


def scan_path(path: pathlib.Path, cands):
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file():
                try:
                    _process_member(str(p.relative_to(path)), p.read_bytes(), cands)
                except Exception:  # noqa
                    pass
        return
    low = path.name.lower()
    if low.endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(path, "r:*") as tf:
            for m in tf.getmembers():
                if m.isfile():
                    f = tf.extractfile(m)
                    if f:
                        _process_member(m.name, f.read(), cands)
    elif low.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            for nm in zf.namelist():
                try:
                    _process_member(nm, zf.read(nm), cands)
                except Exception:  # noqa
                    pass
    elif low.endswith(".pyc"):
        scan_pyc_bytes(path.read_bytes(), path.name, cands)
    else:
        # onefile .exe 等: PYZは圧縮されており生走査では出ないことが多い。
        # pyinstxtractor-ng で展開後の **フォルダ** を渡すよう促す。
        scan_raw_bytes(path.read_bytes(), path.name, cands)


def pick_best(cands):
    """NC1 名前付き → スコア順。無ければスコア最大の有効候補。"""
    named_nc1 = [c for c in cands if c.get("name") and "nc1" in c["name"].lower()]
    pool = named_nc1 or [c for c in cands if c["ok"]] or cands
    return sorted(pool, key=lambda c: c["score"], reverse=True)


# ---------------- self test ----------------
def _synth_sbl(seed=1):
    """現実的な SH-2 っぽいコード列(低~中エントロピー)。頻出命令の語彙＋リテラルプール＋
    少量のゼロで構成し、実コードに近いエントロピー(~6)にする。"""
    import random
    r = random.Random(seed)
    OPS = [0x0009, 0x000B, 0x0008, 0x6003, 0x6103, 0x6203, 0x6303, 0x2112, 0x2122,
           0x4F22, 0x4F26, 0x7001, 0x70FF, 0x3C0C, 0x3C08, 0xE000, 0xE001, 0xE0FF,
           0xA000, 0xB000, 0xD000, 0x9000, 0x5001, 0x1001, 0x4010, 0x400B, 0x6EF6, 0x6FF6]
    var = {0x6, 0xD, 0x9, 0xE, 0xA, 0xB, 0x1, 0x5}  # 変位/レジスタ可変な命令群
    words = []
    while len(words) < SBL_SIZE // 2:
        x = r.random()
        if x < 0.82:
            base = r.choice(OPS)
            if (base >> 12) in var:
                base = (base & 0xF000) | (r.randint(0, 0x0FFF))
            words.append(base & 0xFFFF)
        elif x < 0.92:                      # リテラルプール(32bit定数)
            words.append(r.choice([0xFFFF, 0x0000, 0xFFF6, 0x0001]))
            words.append(r.randint(0, 0xFFFF))
        else:
            words.append(0x0000)            # ゼロ/パディング
    return b"".join((w & 0xFFFF).to_bytes(2, "big") for w in words[:SBL_SIZE // 2])


def _make_pyc(tmp: pathlib.Path):
    import importlib.util
    nc1 = _synth_sbl(1)
    nc2 = _synth_sbl(2)
    src = f"_SBL_NC1 = {nc1!r}\n_SBL_NC2 = {nc2!r}\nJUNK = b'\\x00' * 100\n"
    code = compile(src, "_secure_sbl.py", "exec")
    blob = importlib.util.MAGIC_NUMBER + b"\x00" * 12 + marshal.dumps(code)
    p = tmp / "_internal" / "ecu" / "_secure" / "_sbl.pyc"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(blob)
    # 同梱データファイルとしても1個(圧縮)置く
    (tmp / "_internal" / "sbl_blob.z").write_bytes(zlib.compress(_synth_sbl(3)))
    return nc1, nc2


def _selftest():
    import tempfile
    ok_all = True
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        nc1, nc2 = _make_pyc(tmp)
        # (a) ディレクトリ走査
        cands = []
        scan_path(tmp, cands)
        best = pick_best(cands)
        got = best[0] if best else None
        a = got is not None and got["data"] == nc1 and "nc1" in (got["name"] or "").lower()
        print(f"  [dir/pyc name-assoc] cands={len(cands)} best={got and got['name']} sbl=NC1? {'OK' if a else 'FAIL'}")
        ok_all &= a
        # (b) NC1/NC2両方を候補として検出できたか
        names = {c.get("name") for c in cands}
        b = "_SBL_NC1" in names and "_SBL_NC2" in names
        print(f"  [both blobs found ] {sorted(n for n in names if n)} -> {'OK' if b else 'FAIL'}")
        ok_all &= b
        # (c) 圧縮データファイルの解凍検出
        comp = any("sbl_blob.z" in (c["source"] or "") for c in cands)
        print(f"  [zlib data file   ] decompressed+found -> {'OK' if comp else 'FAIL'}")
        ok_all &= comp
        # (d) .tar.gz 経由
        tgz = tmp / "dist.tar.gz"
        with tarfile.open(tgz, "w:gz") as tf:
            tf.add(tmp / "_internal", arcname="_internal")
        cands2 = []
        scan_path(tgz, cands2)
        best2 = pick_best(cands2)
        d = best2 and best2[0]["data"] == nc1
        print(f"  [tar.gz archive   ] cands={len(cands2)} sbl=NC1? {'OK' if d else 'FAIL'}")
        ok_all &= bool(d)
        # (e) 異常系: 空白blobは弾く
        okx, sc, _ = validate_sh2(b"\x00" * SBL_SIZE)
        e = not okx
        print(f"  [reject padding   ] score={sc} rejected? {'OK' if e else 'FAIL'}")
        ok_all &= e
        # (f) 異常系: 圧縮/ランダム(高エントロピー)は弾く ← 誤検出防止の要
        import random as _rnd
        rr = _rnd.Random(99)
        randblob = bytes(rr.randint(0, 255) for _ in range(SBL_SIZE))
        okr, scr, _ = validate_sh2(randblob)
        # 純粋な圧縮ストリーム(埋め無し): 実コード4本を圧縮して先頭0x1800を取る=高エントロピー
        comp = zlib.compress(b"".join(_synth_sbl(s) for s in (7, 8, 9, 10)), 9)
        compblob = comp[:SBL_SIZE]
        assert len(compblob) == SBL_SIZE, f"compressed too short: {len(comp)}"
        okc, scc, _ = validate_sh2(compblob)
        f = (not okr) and (not okc)
        print(f"  [reject random/zip] rnd(score={scr}) zip(score={scc}) rejected? {'OK' if f else 'FAIL'}")
        ok_all &= f
        # (g) 正常系: 現実的コード列は通る
        okg, scg, rg = validate_sh2(nc1)
        print(f"  [accept code blob ] NC1 score={scg} ent-ok ok={okg} {'OK' if okg else 'FAIL'}")
        ok_all &= okg
    print("SELFTEST:", "OK" if ok_all else "FAIL")
    return ok_all


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="展開フォルダ / .tar.gz / .zip / .pyc")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if _selftest() else 1)
    if not args.path:
        ap.error("path required (or --selftest)")

    cands = []
    scan_path(pathlib.Path(args.path), cands)
    if not cands:
        print("0x1800 の候補が見つからなかった。")
        print(" - onefile .exe はそのままだと PYZ が圧縮されていて出ません。")
        print("   pyinstxtractor-ng で展開 → 出来た *_extracted フォルダを渡してください。")
        print(" - それでも出ない場合、SBLが強い難読化で格納されている可能性 → ルートB(実キャプチャ)が確実。")
        sys.exit(1)

    ranked = pick_best(cands)
    print(f"候補 {len(cands)} 件(有効 {sum(1 for c in cands if c['ok'])} 件):")
    for c in ranked[:8]:
        tag = "NC1" if (c.get("name") and "nc1" in c["name"].lower()) else "?"
        print(f"  score={c['score']:.2f} ok={c['ok']} gen={tag} name={c.get('name')} src={c['source']}")
        if c["reasons"]:
            print("       - " + "; ".join(c["reasons"]))

    best = ranked[0]
    outd = pathlib.Path(args.out_dir)
    outd.mkdir(exist_ok=True)
    (outd / "sbl.bin").write_bytes(best["data"])
    named_nc1 = bool(best.get("name") and "nc1" in best["name"].lower())
    print(f"\n-> {outd / 'sbl.bin'} (0x{len(best['data']):X}) を書き出し。")
    if best["ok"] and named_nc1:
        print("OK: 名前付き NC1 / SH-2らしさ良好。高確度。")
    elif best["ok"]:
        print("注意: SH-2らしさは良好だが NC1/NC2 の名前判別ができていない。")
        print("      0x1800 候補が複数あるなら、どれが NC1 かは実機 or ルートB のSBLと突き合わせて確認を。")
    else:
        print("警告: SH-2らしさが低い。誤検出の可能性 → そのまま書き込まないこと。")
    print("\n次(必ずドライランから):")
    print(f"  python -I tools/flash_writeback.py --sbl {outd / 'sbl.bin'}")
    print("※ 実書込みは本個体がブリックし得る不可逆操作。ドライランで計画を確認し、")
    print("  可能なら別経路(ルートB=実フラッシュの candump → extract_sbl.py)で同一性を相互検証してから。")


if __name__ == "__main__":
    main()
