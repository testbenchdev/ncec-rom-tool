"""ISO 15765-2 (ISO-TP) の最小実装。通常アドレッシング、11bit ID、8バイトパディング。"""
import time

import can


class IsoTpError(Exception):
    pass


class IsoTp:
    def __init__(self, bus: can.BusABC, tx_id: int = 0x7E0, rx_id: int = 0x7E8,
                 pad: int = 0x00, timeout: float = 1.0):
        self.bus = bus
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.pad = pad
        self.timeout = timeout

    # ---- 低レベル ----
    def _send_frame(self, data: bytes) -> None:
        data = bytes(data) + bytes([self.pad]) * (8 - len(data))
        self.bus.send(can.Message(arbitration_id=self.tx_id, data=data,
                                  is_extended_id=False))

    def _recv_frame(self, timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            msg = self.bus.recv(remaining)
            if msg is None:
                return None
            if msg.arbitration_id == self.rx_id and not msg.is_extended_id:
                return bytes(msg.data)

    def flush(self) -> None:
        while self.bus.recv(0) is not None:
            pass

    # ---- 送信 ----
    def send(self, payload: bytes) -> None:
        n = len(payload)
        if n <= 7:
            self._send_frame(bytes([n]) + payload)
            return
        if n > 0xFFF:
            raise IsoTpError("payload too long")
        self._send_frame(bytes([0x10 | (n >> 8), n & 0xFF]) + payload[:6])
        pos, sn = 6, 1
        block_size, st_min, sent_in_block = self._wait_flow_control()
        while pos < n:
            if block_size and sent_in_block == block_size:
                block_size, st_min, sent_in_block = self._wait_flow_control()
            time.sleep(st_min)
            self._send_frame(bytes([0x20 | sn]) + payload[pos:pos + 7])
            pos += 7
            sn = (sn + 1) & 0x0F
            sent_in_block += 1

    def _wait_flow_control(self) -> tuple[int, float, int]:
        while True:
            fr = self._recv_frame(self.timeout)
            if fr is None:
                raise IsoTpError("flow control timeout")
            if fr[0] >> 4 != 3:
                continue
            fs = fr[0] & 0x0F
            if fs == 1:  # WAIT
                continue
            if fs == 2:
                raise IsoTpError("flow control overflow")
            st = fr[2]
            st_min = st / 1000 if st <= 0x7F else (st - 0xF0) / 10000 if 0xF1 <= st <= 0xF9 else 0.127
            return fr[1], st_min, 0

    # ---- 受信 ----
    def recv(self, timeout: float | None = None) -> bytes | None:
        fr = self._recv_frame(self.timeout if timeout is None else timeout)
        if fr is None:
            return None
        pci = fr[0] >> 4
        if pci == 0:
            return fr[1:1 + (fr[0] & 0x0F)]
        if pci != 1:
            raise IsoTpError(f"unexpected frame {fr.hex(' ')}")
        n = ((fr[0] & 0x0F) << 8) | fr[1]
        data = bytearray(fr[2:8])
        # Flow Control: CTS, BS=0（全部送れ）, STmin=0
        self._send_frame(bytes([0x30, 0x00, 0x00]))
        expect_sn = 1
        while len(data) < n:
            cf = self._recv_frame(self.timeout)
            if cf is None:
                raise IsoTpError("consecutive frame timeout")
            if cf[0] >> 4 != 2:
                continue
            if cf[0] & 0x0F != expect_sn:
                raise IsoTpError("sequence number mismatch")
            data += cf[1:8]
            expect_sn = (expect_sn + 1) & 0x0F
        return bytes(data[:n])
