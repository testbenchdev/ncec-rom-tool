"""NCEC フラッシュ書き込みドライバ(ホスト側)。

このECU(Denso NC / SH7058)の確定フラッシュ手順(nc-flash 2.20.0 のソース解析 +
本個体の実機プローブで確認済み):

  1. 10 85            プログラミングセッション
  2. 27 01 / 27 02    セキュリティアクセス(ncecu.security で鍵算出)
  3. B1 00 B2 00      RoutineControl(フラッシュカウンタ / RequestDownload の前提)
  4. 34 00008000 000FF800   RequestDownload(RAM 0x8000 へ、総サイズ 0xFF800)
  5. 36 <data>        TransferData を 0x400 バイト/ブロックで:
                        ① SBL(0x1800)を先に転送 → ② 補正ROM[flash_start:] を転送
                        (フル書き込み flash_start=0x2000: 0x1800 + 0xFE000 = 0xFF800)
  6. 37               TransferExit
  7. 11 01            ECUリセット

**唯一の必須入力 = SBL(0x1800バイト)**。SBL は世代(NC1/NC2)と flash_start で決まり、
CALIDには依存しない(get_sbl_data(flash_start, generation) 相当)。本個体は **NC1**。
SBL はどのツールも非公開だが、フラッシュ中に 0x36 で平文送信される(= NC1 車のフル書き込み
candump から抽出可能)。

**安全策**: 実機への書き込みは sbl_data があり、かつ confirm=True の時だけ実行(既定はドライラン)。
書き込み前に必ずチェックサムを補正する(ncecu.checksum は nc-flash と byte 一致を検証済み)。
"""
from __future__ import annotations

import time
import zlib
from dataclasses import dataclass

from . import checksum
from .diag import DiagClient, NegativeResponse
from .isotp import IsoTpError
from .security import compute_security_key

# --- ROM / フラッシュ パラメータ(nc-flash constants.py と一致・実機確認済み)---
ROM_SIZE = 0x100000
SBL_SIZE = 0x1800
SBL_UPLOAD_ADDR = 0x00008000       # RequestDownload addr(SBL の RAM ロード先)
DOWNLOAD_ADDR = SBL_UPLOAD_ADDR
DOWNLOAD_SIZE = 0x000FF800         # = SBL(0x1800) + 補正ROM[0x2000:](0xFE000)。実機が受理する唯一値
BLOCK_SIZE = 0x400                 # TransferData データ長/ブロック(実機 74 04 01 = maxBlock 0x401)
ROM_FLASH_START_MIN = 0x2000       # フル書き込みのプログラム開始オフセット(0x0-0x1FFF は保護)
PROG_SESSION = 0x85
DOWNLOAD_SESSION = 0x87            # ROM 読み出し(Mode23)用

# 世代判定(nc-flash: byte @0x2030)
GEN_DETECT_OFFSET = 0x2030
GEN_MAP = {0x35: "NC1", 0x36: "NC2", 0x37: "NC2"}

# チェックサム表は ncecu.checksum(0xFF650)。フラッシュカウンタは書込毎にECUが更新する領域で
# 読み戻し照合から除外する。
FLASH_COUNTER_OFFSET = 0xFFB00
FLASH_COUNTER_SIZE = 8

# キャリブCRC 領域(romdrop/nc-flash と一致: rom[0x2000:0x100000] の zlib CRC-32)
CAL_CRC_OFFSET = 0x2000
CAL_CRC_END = 0x100000
CAL_ID_OFFSETS = (0xC0046, 0xB8046)


class FlashError(Exception):
    pass


# ---- ROM 検査ユーティリティ(ECU非接触)----
def detect_generation(rom_data: bytes) -> str:
    """ROM byte @0x2030 から世代(NC1/NC2)を判定。"""
    if len(rom_data) <= GEN_DETECT_OFFSET:
        raise FlashError("ROM too small for generation detect")
    b = rom_data[GEN_DETECT_OFFSET]
    gen = GEN_MAP.get(b)
    if gen is None:
        raise FlashError(f"unknown generation byte 0x{b:02X} @0x{GEN_DETECT_OFFSET:X}")
    return gen


def get_cal_id(rom_data: bytes) -> str:
    """CALID(先頭 'L' の6文字)を 0xC0046→0xB8046 の順に探す。"""
    for off in CAL_ID_OFFSETS:
        if len(rom_data) >= off + 6 and rom_data[off:off + 1] == b"L":
            return rom_data[off:off + 6].decode("ascii", "replace")
    return ""


def calibration_crc(rom_data: bytes, clear_flash_counter: bool = True) -> int:
    """rom[0x2000:0x100000] の zlib CRC-32。clear_flash_counter で 0xFFB00:8 を 0xFF 化。
    nc-flash/romdrop と同一(例ROMで A2… 一致を検証済み)。"""
    buf = bytearray(rom_data[CAL_CRC_OFFSET:CAL_CRC_END])
    if clear_flash_counter:
        rel = FLASH_COUNTER_OFFSET - CAL_CRC_OFFSET
        buf[rel:rel + FLASH_COUNTER_SIZE] = b"\xff" * FLASH_COUNTER_SIZE
    return zlib.crc32(bytes(buf)) & 0xFFFFFFFF


def prepare_image(rom_data: bytes) -> tuple[bytes, int]:
    """ROMを検証しチェックサムを補正。(corrected_rom, 補正件数) を返す。"""
    if len(rom_data) != ROM_SIZE:
        raise FlashError(f"ROM must be {ROM_SIZE} bytes, got {len(rom_data)}")
    buf = bytearray(rom_data)
    changed = checksum.recalculate(buf)
    ncorr = sum(1 for s, e, o, n in changed if o != n)
    if not checksum.all_valid(buf):
        raise FlashError("checksum still invalid after correction")
    return bytes(buf), ncorr


def verify_readback(expected_corrected: bytes, readback: bytes,
                    flash_start: int = ROM_FLASH_START_MIN) -> list[int]:
    """書き込んだ領域 [flash_start:] を読み戻しと比較(フラッシュカウンタ除外)。
    不一致オフセットのリストを返す(空なら完全一致)。"""
    diffs = []
    n = min(len(expected_corrected), len(readback))
    cstart, cend = FLASH_COUNTER_OFFSET, FLASH_COUNTER_OFFSET + FLASH_COUNTER_SIZE
    for i in range(flash_start, n):
        if cstart <= i < cend:
            continue
        if expected_corrected[i] != readback[i]:
            diffs.append(i)
    return diffs


@dataclass
class FlashPlan:
    """書き込み計画(ドライランで中身を提示する)。"""
    rom_size: int
    flash_start: int
    program_bytes: int
    sbl_bytes: int
    checksum_corrections: int
    generation: str = ""
    cal_id: str = ""
    cal_crc: int = 0
    total_transfer: int = 0
    download_addr: int = DOWNLOAD_ADDR
    download_size: int = DOWNLOAD_SIZE


class Flasher:
    def __init__(self, diag: DiagClient, log=print):
        self.diag = diag
        self.log = log

    def _req(self, payload: bytes, timeout: float = 5.0) -> bytes:
        r = self.diag.request(payload, timeout=timeout)
        if r is None:
            raise FlashError(f"no response to {payload[:4].hex()}")
        return r

    def authenticate(self) -> None:
        self.log("プログラミングセッション 10 85 ...")
        self._req(bytes([0x10, PROG_SESSION]))
        self.diag.request(b"\x3E\x01")
        self.log("セキュリティ 27 01 (seed) ...")
        sr = self._req(b"\x27\x01")
        if sr[0] != 0x67:
            raise FlashError(f"requestSeed failed: {sr.hex()}")
        seed = bytes(sr[2:5])
        key = compute_security_key(seed)
        self.log(f"  seed={seed.hex(' ')} -> key={key.hex(' ')}  送信 27 02 ...")
        kr = self._req(bytes([0x27, 0x02]) + key)
        if not (kr[0] == 0x67 and kr[1] == 0x02):
            raise FlashError(f"security rejected: {kr.hex()}")
        self.log("  アンロック成功")

    def check_flash_counter(self) -> bytes:
        # RoutineControl B1 00 B2 00 — RequestDownload の前提条件。実機で受理確認済み。
        self.log("RoutineControl B1 00 B2 00 (flash counter / arm) ...")
        return self._req(b"\xB1\x00\xB2\x00")

    def request_download(self, addr=DOWNLOAD_ADDR, size=DOWNLOAD_SIZE) -> bytes:
        self.log(f"RequestDownload 34 addr=0x{addr:08X} size=0x{size:06X} ...")
        return self._req(bytes([0x34]) + addr.to_bytes(4, "big") + size.to_bytes(4, "big"),
                         timeout=10.0)

    def transfer_data(self, data: bytes, label: str, progress=None,
                      block: int = BLOCK_SIZE) -> None:
        total = len(data)
        sent = 0
        self.log(f"TransferData ({label}): {total} bytes, {block}B/block")
        while sent < total:
            chunk = data[sent:sent + block]
            self._req(bytes([0x36]) + chunk, timeout=10.0)
            sent += len(chunk)
            if progress:
                progress(sent, total)

    def transfer_exit(self) -> None:
        self.log("TransferExit 37 ...")
        self._req(b"\x37", timeout=10.0)

    # ---- ROM 読み出し(Mode 23 ReadMemoryByAddress・SBL不要・読み取り専用)----
    def read_memory(self, addr: int, size: int, timeout: float = 5.0,
                    retries: int = 2) -> bytes:
        """23 <addr:4BE> <size:2BE>(ALFIDバイト無し, Mazda NC流)。応答 63+data。"""
        req = bytes([0x23]) + addr.to_bytes(4, "big") + size.to_bytes(2, "big")
        last = None
        for _ in range(retries + 1):
            try:
                r = self._req(req, timeout=timeout)
            except (NegativeResponse, FlashError, IsoTpError) as e:
                # IsoTpError(SN不一致/CFタイムアウト)は取りこぼし起因が多い。
                # 次要求の先頭で tp.flush() が残フレームを捨てるので、そのまま再試行で回復する。
                last = e
                continue
            if r and r[0] == 0x63:
                data = bytes(r[1:1 + size])
                if len(data) == size:
                    return data
                last = FlashError(f"short read {len(data)}/{size} @0x{addr:X}")
            else:
                last = FlashError(f"bad read resp {r[:4].hex() if r else None}")
        raise FlashError(f"read @0x{addr:X} failed: {last}")

    def read_full_rom(self, progress=None, do_auth: bool = True,
                      block: int = BLOCK_SIZE, restore_session: bool = True) -> bytes:
        """ECU から全 1MB を読み出して返す(認証→Mode23ループ)。消去・書込は一切しない。"""
        if do_auth:
            self.authenticate()
        self.log(f"ROM読み出し開始(0x{ROM_SIZE:X}, {block}B/block)...")
        buf = bytearray(ROM_SIZE)
        off = 0
        t0 = time.monotonic()
        while off < ROM_SIZE:
            n = min(block, ROM_SIZE - off)
            buf[off:off + n] = self.read_memory(off, n)
            off += n
            if progress:
                progress(off, ROM_SIZE)
        self.log(f"読み出し完了 0x{ROM_SIZE:X} ({time.monotonic() - t0:.1f}s)")
        if restore_session:
            try:
                self.diag.request(b"\x10\x81", timeout=2.0)  # 通常セッションへ復帰
            except Exception:  # noqa: BLE001
                pass
        return bytes(buf)

    def ecu_reset(self) -> None:
        self.log("ECUリセット 11 01 ...")
        try:
            self._req(b"\x11\x01", timeout=10.0)
        except (NegativeResponse, FlashError):
            pass  # リセットは応答が返らないことがある

    # ---- 本体 ----
    def flash(self, rom_data: bytes, sbl_data: bytes | None,
              flash_start: int = ROM_FLASH_START_MIN,
              confirm: bool = False) -> FlashPlan:
        """フラッシュ実行(nc-flash 準拠)。sbl_data が None か confirm=False ならドライラン。

        手順: 認証 → B1 00 B2 00 → RequestDownload(0x8000, 0xFF800)
              → TransferData[ SBL + 補正ROM[flash_start:] ] 0x400ブロック → TransferExit → リセット。
        """
        corrected, ncorr = prepare_image(rom_data)
        generation = detect_generation(corrected)
        cal_id = get_cal_id(corrected)
        program = corrected[flash_start:]
        total = (len(sbl_data) if sbl_data else 0) + len(program)
        plan = FlashPlan(
            rom_size=len(corrected), flash_start=flash_start,
            program_bytes=len(program), sbl_bytes=len(sbl_data) if sbl_data else 0,
            checksum_corrections=ncorr, generation=generation, cal_id=cal_id,
            cal_crc=calibration_crc(corrected), total_transfer=total)

        self.log(f"[計画] CALID={cal_id} 世代={generation} "
                 f"補正={ncorr}領域 calCRC={plan.cal_crc:08X}")
        self.log(f"       flash_start=0x{flash_start:X} program=0x{len(program):X} "
                 f"SBL=0x{plan.sbl_bytes:X} 合計転送=0x{total:X} (既定DL=0x{DOWNLOAD_SIZE:X})")

        if sbl_data is None:
            self.log("[ドライラン] SBL 未指定のため書き込みは行いません。"
                     f"(要: NC1/start=0x{flash_start:X} の {SBL_SIZE}バイトSBL)")
            return plan
        if len(sbl_data) != SBL_SIZE:
            raise FlashError(f"SBL size must be {SBL_SIZE}, got {len(sbl_data)}")
        # フル書き込みでは SBL+program == DOWNLOAD_SIZE になるはず(実機はこのサイズのみ受理)
        if flash_start == ROM_FLASH_START_MIN and total != DOWNLOAD_SIZE:
            raise FlashError(f"transfer size 0x{total:X} != DOWNLOAD_SIZE 0x{DOWNLOAD_SIZE:X}")
        if not confirm:
            self.log("[ドライラン] confirm=False のため書き込みは行いません。")
            return plan

        # ---- 実書き込み(消去を伴う不可逆操作)----
        self.authenticate()
        self.check_flash_counter()
        self.request_download(DOWNLOAD_ADDR, DOWNLOAD_SIZE)
        t0 = time.monotonic()
        self.transfer_data(sbl_data, "SBL")
        self.transfer_data(
            program, "ROM program",
            progress=lambda s, t: self.log(f"  ROM {s}/{t}")
            if s % (BLOCK_SIZE * 32) == 0 else None)
        self.transfer_exit()
        self.ecu_reset()
        self.log(f"完了 ({time.monotonic() - t0:.1f}s)")
        return plan
