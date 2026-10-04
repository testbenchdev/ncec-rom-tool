"""NCEC (LFG7EG) セキュリティアクセス: seed → key 計算。

予備ECUの ROM(ncec_rom_dump.bin)内のキー検証ルーチン 0x7DFE0 を SH-2E エミュレータで
実行し、与えたシードに対して ECU が期待するキーを算出する。ROM 実機のロジックそのものを
使うため推測がなく、公開既知ペア 2 組で検証済み（レベル index=1）:
    B3A84A -> 4470E8 ,  AAC102 -> 7F26F4

ECU プロトコル:
    要求シード: 27 01            応答: 67 01 S0 S1 S2
    キー送信  : 27 02 K0 K1 K2   応答: 67 02 (肯定) / 7F 27 35 (invalidKey)
"""
import pathlib

from .sh2emu import SH2

# 0x7DFE0 内の定数（固定: "MazdA" 連結 + レベルテーブル）。index=1 がレベル1(27 01)。
_FN = 0x7DFE0
_SENT = 0xFFFFFE
_SEEDBUF = 0xFFFF9000
_KEYBUF = 0xFFFF9010
_DEFAULT_LEVEL = 1

_DEFAULT_ROM = pathlib.Path(__file__).resolve().parents[1] / "ncec_rom_dump.bin"
_rom_cache: dict[str, bytes] = {}


def _load_rom(rom_path) -> bytes:
    p = str(rom_path)
    if p not in _rom_cache:
        _rom_cache[p] = pathlib.Path(rom_path).read_bytes()
    return _rom_cache[p]


def _to_int(seed) -> int:
    if isinstance(seed, (bytes, bytearray)):
        if len(seed) != 3:
            raise ValueError("seed must be 3 bytes")
        return (seed[0] << 16) | (seed[1] << 8) | seed[2]
    return seed & 0xFFFFFF


def compute_security_key(seed, level: int = _DEFAULT_LEVEL,
                         rom_path=_DEFAULT_ROM, budget: int = 40000) -> bytes:
    """3バイトシード(int または bytes)から 3バイトキーを返す。"""
    s = _to_int(seed)
    rom = _load_rom(rom_path)
    cpu = SH2(rom)
    cpu.r[15] = 0xFFFFBC00
    cpu.pr = _SENT
    sb = _SEEDBUF - cpu.ram_base
    cpu.ram[sb] = (s >> 16) & 0xFF
    cpu.ram[sb + 1] = (s >> 8) & 0xFF
    cpu.ram[sb + 2] = s & 0xFF
    cpu.r[4] = level
    cpu.r[5] = _SEEDBUF
    cpu.r[6] = _KEYBUF
    cpu.pc = _FN
    b0 = b1 = b2 = None
    for _ in range(budget):
        pc = cpu.pc
        if pc == _SENT:
            break
        if pc == 0x7E182:
            if b0 is None:
                b0 = cpu.r[6] & 0xFF
            if b1 is None:
                b1 = cpu.rd(cpu.r[15] + 4, 1) & 0xFF
        if pc in (0x7E188, 0x7E1AE) and b2 is None:
            b2 = cpu.r[7] & 0xFF
        if pc < 0 or (pc >= len(rom) and not (cpu.ram_base <= pc < cpu.ram_base + len(cpu.ram))):
            break
        cpu.step()
    if None in (b0, b1, b2):
        raise RuntimeError("key computation did not reach comparison point")
    return bytes([b0, b1, b2])


# 既知ペア（公開 romdrop ログ由来、レベル1）での自己検証用
KNOWN_PAIRS = [
    (bytes([0xB3, 0xA8, 0x4A]), bytes([0x44, 0x70, 0xE8])),
    (bytes([0xAA, 0xC1, 0x02]), bytes([0x7F, 0x26, 0xF4])),
]


def selftest(rom_path=_DEFAULT_ROM) -> bool:
    for seed, key in KNOWN_PAIRS:
        got = compute_security_key(seed, rom_path=rom_path)
        if got != key:
            raise AssertionError(f"seed {seed.hex()} -> {got.hex()} expected {key.hex()}")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        s = int(sys.argv[1], 16)
        print(compute_security_key(s).hex(" "))
    else:
        print("selftest:", "OK" if selftest() else "FAIL")
