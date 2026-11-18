"""NCEC (LFG7EG) セキュリティアクセス: seed → key 計算。

ECUの ROM 内のキー検証ルーチン 0x7DFE0 を SH-2E エミュレータで
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

_ROOT = pathlib.Path(__file__).resolve().parents[1]
# キー計算に使うROM。キー検証ルーチン(コード部)は LFG7EG の全ROMで同一なので、吸い出しならどれでもよい。
# v2.71 で ROM を rom_data/ に集約したため、そこから探す(旧 ncec_rom_dump.bin は最後の候補)。
_ROM_CANDIDATES = (_ROOT / "rom_data" / "ecu_readout_yahooauction.bin",
                   _ROOT / "rom_data" / "ecu_readout_original.bin",
                   _ROOT / "ncec_rom_dump.bin")
_ROM_SIZE = 0x100000
_rom_cache: dict[str, bytes] = {}
_default_rom: pathlib.Path | None = None


def default_rom() -> pathlib.Path:
    """キー計算に使うROMを返す。決まった名前が無ければ、rom_data/ の 1MB の .bin のうち
    既知シード/キー(KNOWN_PAIRS)の自己検証に通るものを使う(ファイル名を変えていても動く)。"""
    global _default_rom
    if _default_rom is not None and _default_rom.exists():
        return _default_rom
    for c in _ROM_CANDIDATES:
        if c.exists() and c.stat().st_size == _ROM_SIZE:
            _default_rom = c
            return c
    for c in sorted((_ROOT / "rom_data").glob("*.bin")):
        try:
            if c.stat().st_size == _ROM_SIZE and selftest(c):
                _default_rom = c
                return c
        except Exception:  # noqa: BLE001  このROMでは計算できない=次を試す
            continue
    raise FileNotFoundError(
        "セキュリティキーの計算に使うROMが見つかりません。rom_data/ フォルダに、このECU(LFG7EG)の"
        "吸い出しROM(1MBの .bin。例 ecu_readout_yahooauction.bin)を置いてください。")


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
                         rom_path=None, budget: int = 40000) -> bytes:
    """3バイトシード(int または bytes)から 3バイトキーを返す。rom_path 省略時は default_rom()。"""
    s = _to_int(seed)
    rom = _load_rom(rom_path if rom_path is not None else default_rom())
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


def selftest(rom_path=None) -> bool:
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
