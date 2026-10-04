"""SH-2E 逆アセンブラ補助（capstone, big-endian）。ROM解析用。"""
import pathlib
import sys

import capstone

ROM = pathlib.Path(__file__).resolve().parents[1] / "ncec_rom_dump.bin"


def get_md():
    md = capstone.Cs(capstone.CS_ARCH_SH,
                     capstone.CS_MODE_SH2 + capstone.CS_MODE_BIG_ENDIAN)
    md.detail = False
    return md


def disasm(data: bytes, base: int, start: int, count: int):
    md = get_md()
    out = []
    for insn in md.disasm(data[start:start + count * 2 + 32], base + start):
        out.append((insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str))
        if len(out) >= count:
            break
    return out


def main():
    data = ROM.read_bytes()
    start = int(sys.argv[1], 16)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    for addr, hx, mn, ops in disasm(data, 0, start, count):
        print(f"{addr:06X}  {hx:<8} {mn:<10} {ops}")


if __name__ == "__main__":
    main()
