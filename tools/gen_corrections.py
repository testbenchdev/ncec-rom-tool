"""ECU内部ディスクリプタから要注意テーブルの真次元を取得し、検証して
ncecu/_corrections_data.py を生成する。

ディスクリプタ形式: [Y_axis_ptr, X_axis_ptr, data_ptr, 0x00000000, (rows<<16 | cols)]
(各 ptr は 0x2000..0x100000 の ROM アドレス、rows/cols は 1..64)
採用条件: (rows,cols) または (cols,rows) で読んだ値の in-range>=0.85 かつ元より改善。
"""
import math
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ncecu import defs
from ncecu.rom import Rom

ROOT = pathlib.Path(__file__).resolve().parents[1]
data = (ROOT / "ncec_rom_dump.bin").read_bytes()
rd = defs.parse(ROOT / "defs" / "lfg7eg.xml")
rom = Rom(data, rd)
N = len(data)
SZ = {"float": 4, "uint32": 4, "uint16": 2, "uint8": 1, "int16": 2, "int8": 1, "int32": 4}


def w32(o):
    return int.from_bytes(data[o:o + 4], "big")


def w16(o):
    return int.from_bytes(data[o:o + 2], "big")


def isnan(v):
    return isinstance(v, float) and math.isnan(v)


def scan_descriptors():
    descr = {}
    for o in range(0, N - 20, 4):
        if w32(o + 12) != 0:
            continue
        y, x, d = w32(o), w32(o + 4), w32(o + 8)
        if not all(0x2000 <= p < 0x100000 for p in (y, x, d)):
            continue
        a, b = w16(o + 16), w16(o + 18)
        if 1 <= a <= 64 and 1 <= b <= 64:
            descr[d] = (a, b)
    return descr


def inrange(addr, rows, cols, sc):
    sz = SZ.get(sc.storagetype, 4)
    tot = rows * cols
    if tot == 0 or addr + tot * sz > N:
        return -1
    sp = (sc.vmax - sc.vmin) or 1
    tol = sp * 0.05 + 1e-6
    inr = cnt = 0
    for k in range(tot):
        b = data[addr + k * sz:addr + k * sz + sz]
        if sc.storagetype == "float":
            v = struct.unpack(">f", b)[0]
            if isnan(v):
                continue
        else:
            v = int.from_bytes(b, "big", signed=sc.storagetype.startswith("int"))
        v = sc.to_real(v)
        cnt += 1
        if sc.vmin - tol <= v <= sc.vmax + tol:
            inr += 1
    return inr / cnt if cnt else 0


def suspect(t):
    r, c = rom.dims(t)
    if t.ttype in ("2D", "3D") and t.elements and r * c != t.elements:
        return True
    sc = rd.scalings.get(t.scaling)
    if sc and sc.vmax > sc.vmin:
        g = rom.read_table(t)
        fl = [v for row in g for v in row if isinstance(v, (int, float)) and not isnan(v)]
        if fl:
            sp = sc.vmax - sc.vmin
            tol = sp * 0.05 + 1e-6
            if sum(1 for v in fl if v < sc.vmin - tol or v > sc.vmax + tol) / len(fl) > 0.2:
                return True
    return False


def main():
    descr = scan_descriptors()
    corr = {}
    fixed = []
    for t in rd.tables:
        if not suspect(t) or t.address not in descr:
            continue
        sc = rd.scalings.get(t.scaling)
        if not sc or sc.vmax <= sc.vmin:
            continue
        a, b = descr[t.address]
        orows, ocols = rom.dims(t)
        of = inrange(t.address, orows, ocols, sc)
        # try both orientations, pick best in-range
        cand = [((a, b), inrange(t.address, a, b, sc)), ((b, a), inrange(t.address, b, a, sc))]
        (dims, f) = max(cand, key=lambda z: z[1])
        if f >= 0.85 and f > of + 0.02:
            corr[t.address] = dims
            fixed.append((t.address, dims, f, of, t.name))

    out = ROOT / "ncecu" / "_corrections_data.py"
    lines = ['"""自動生成 (tools/gen_corrections.py)。ECUディスクリプタ由来の検証済み次元補正。"""',
             "CORRECTIONS = {"]
    for a in sorted(corr):
        r, c = corr[a]
        lines.append(f"    0x{a:X}: ({r}, {c}),")
    lines.append("}")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"descriptors={len(descr)}  corrected(validated)={len(corr)}")
    print(f"saved {out}")
    for a, dims, f, of, nm in fixed[:15]:
        print(f"  @{a:X} -> {dims}  in-range {of:.2f}->{f:.2f}  {nm[:40]}")


if __name__ == "__main__":
    main()
