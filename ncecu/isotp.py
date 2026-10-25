"""ISO 15765-2 (ISO-TP) の最小実装。通常アドレッシング、11bit ID、8バイトパディング。"""
import time

import can


class IsoTpError(Exception):
    pass


class IsoTp:
    def __init__(self, bus: can.BusABC, tx_id: int = 0x7E0, rx_id: int = 0x7E8,
                 pad: int = 0x00, timeout: float = 1.0,
                 rx_block_size: int = 0x10, rx_st_min: int = 0x00,
                 tx_st_min_floor: float = 0.001, tx_retries: int = 5,
                 drain_tx_echo: bool = True, drain_every: int = 8):
        self.bus = bus
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.pad = pad
        self.timeout = timeout
        # 送信ペーシング: ECU の FC が STmin=0 を返しても、連続フレームを無遅延で
        # 送ると gs_usb(candleLight系)の送信FIFOがバス排出より速く溢れ、USBバルク
        # 書込みがタイムアウト(CanOperationError/[Errno 10060])する。最低間隔を設けて防ぐ。
        # 8バイト標準フレームの500kbps送信時間は ~0.26ms なので 1ms で十分な余裕。
        self.tx_st_min_floor = tx_st_min_floor
        # 一過性のUSBつまりに備えた bus.send のリトライ回数。
        self.tx_retries = tx_retries
        # 送信バースト中、gs_usb(candleLight系)は送信エコーを device→host に返す。
        # 連続フレームを送る間これを読まないと IN 側が溢れ、OUT 側(bus.send)が
        # タイムアウトする。各送信後に受信キューを吸い出してエコーを捨てる(真の応答=
        # rx_id フレームは _rxbuf に退避して後段の FC/応答受信で使う)。
        self.drain_tx_echo = drain_tx_echo
        # 毎フレームで recv(0) すると gs_usb の recv 遅延(~10ms)が積み上がって遅い。
        # drain_every フレームごとにまとめて吸い出すと、バッファを溢れさせずに高速化できる。
        self.drain_every = max(1, drain_every)
        self._rxbuf: list[bytes] = []
        # 受信時に送るフロー制御(FC)のパラメータ。
        # rx_block_size: ECU が一度に送る連続フレーム数(0=無制限)。大きい応答(Mode23の
        #   0x400B=約146CF)で BS=0 にするとホストの受信バッファが溢れて取りこぼし→
        #   "sequence number mismatch" になるため、既定で 0x10 ごとに FC を返してペーシングする。
        # rx_st_min: 連続フレームの最小間隔(0x00-0x7F=ms, 0xF1-0xF9=100-900us)。
        self.rx_block_size = rx_block_size
        self.rx_st_min = rx_st_min

    # ---- 低レベル ----
    def _send_frame(self, data: bytes) -> None:
        data = bytes(data) + bytes([self.pad]) * (8 - len(data))
        msg = can.Message(arbitration_id=self.tx_id, data=data, is_extended_id=False)
        # 送信失敗(FIFO溢れ/一過性USBつまり)はフレームが出ていないので再送しても重複しない。
        last = None
        for attempt in range(max(1, self.tx_retries)):
            try:
                self.bus.send(msg)
                return
            except can.CanError as e:
                last = e
                time.sleep(0.002 * (attempt + 1))
        raise IsoTpError(f"frame send failed after {self.tx_retries} retries: {last}")

    def _drain(self) -> None:
        """受信キューを即時に空にする。rx_id のフレームは _rxbuf に退避、
        それ以外(TXエコー=tx_id 等)は捨てる。送信バースト中の IN 側詰まり防止。"""
        while True:
            m = self.bus.recv(0)
            if m is None:
                return
            if m.arbitration_id == self.rx_id and not m.is_extended_id:
                self._rxbuf.append(bytes(m.data))

    def _recv_frame(self, timeout: float) -> bytes | None:
        if self._rxbuf:
            return self._rxbuf.pop(0)
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
        # バス上の残フレームに加え、送信中にバッファした受信フレーム(_rxbuf)も破棄する。
        # これを消さないと前トランザクションの残りが次要求の応答として誤読される。
        self._rxbuf.clear()
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
        if self.drain_tx_echo:
            self._drain()
        pos, sn, k = 6, 1, 0
        block_size, st_min, sent_in_block = self._wait_flow_control()
        while pos < n:
            if block_size and sent_in_block == block_size:
                block_size, st_min, sent_in_block = self._wait_flow_control()
            time.sleep(max(st_min, self.tx_st_min_floor))  # STmin下限でFIFO溢れを防ぐ
            self._send_frame(bytes([0x20 | sn]) + payload[pos:pos + 7])
            k += 1
            if self.drain_tx_echo and k % self.drain_every == 0:
                self._drain()                              # 数フレーム毎にTXエコーを吸い出す
            pos += 7
            sn = (sn + 1) & 0x0F
            sent_in_block += 1
        if self.drain_tx_echo:
            self._drain()                                  # 末尾で残りエコーを掃除

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
        bs = self.rx_block_size & 0xFF
        stmin = self.rx_st_min & 0xFF
        # Flow Control: CTS。BS ごとに FC を返してペーシング(受信バッファ溢れ=取りこぼし防止)
        self._send_frame(bytes([0x30, bs, stmin]))
        expect_sn = 1
        in_block = 0
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
            in_block += 1
            # このブロック分を受け切ったら、まだ続きがある限り次の FC(CTS)を送る
            if bs and in_block >= bs and len(data) < n:
                self._send_frame(bytes([0x30, bs, stmin]))
                in_block = 0
        return bytes(data[:n])
