"""OBD-II Mode 01 ライブデータ取得(読み取り専用)。

実行中ECUの運転点(回転数・負荷・水温など)をCAN経由でポーリングし、
エディタの「現在セル追従」やライブ数値表示に使う。ECUの状態は一切変えない
(セッション変更・セキュリティ・書き込みは行わない)。

- PID デコードは標準 OBD-II。各PIDに「軸ロール」(RPM/LOAD/ECT…)を割り当て、
  テーブル軸(RPM_xxxx, LOAD_xxxx, ECT, IAT, APP, TP, MAP, VSS …)と対応付ける。
- LiveReader はバックグラウンドスレッドで最新値を保持(GUIは after() で読むだけ)。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class Pid:
    pid: int
    name: str
    nbytes: int
    unit: str
    role: str
    decode: object  # callable(bytes)->float


def _u8(d):
    return d[0]


def _u16(d):
    return (d[0] << 8) | d[1]


# 標準 OBD-II Mode01 PID(本個体で supported 確認済みを中心に)
PIDS: dict[int, Pid] = {
    0x0C: Pid(0x0C, "RPM", 2, "rpm", "RPM", lambda d: _u16(d) / 4),
    0x04: Pid(0x04, "Calc Load", 1, "%", "LOAD", lambda d: _u8(d) * 100 / 255),
    0x43: Pid(0x43, "Abs Load", 2, "%", "LOAD", lambda d: _u16(d) * 100 / 255),
    0x05: Pid(0x05, "ECT", 1, "C", "ECT", lambda d: _u8(d) - 40),
    0x0F: Pid(0x0F, "IAT", 1, "C", "IAT", lambda d: _u8(d) - 40),
    0x0B: Pid(0x0B, "MAP", 1, "kPa", "MAP", lambda d: _u8(d)),
    0x10: Pid(0x10, "MAF", 2, "g/s", "MAF", lambda d: _u16(d) / 100),
    0x11: Pid(0x11, "Throttle", 1, "%", "TP", lambda d: _u8(d) * 100 / 255),
    0x45: Pid(0x45, "Rel Throttle", 1, "%", "TP", lambda d: _u8(d) * 100 / 255),
    0x49: Pid(0x49, "APP D", 1, "%", "APP", lambda d: _u8(d) * 100 / 255),
    0x4A: Pid(0x4A, "APP E", 1, "%", "APP", lambda d: _u8(d) * 100 / 255),
    0x0E: Pid(0x0E, "Timing", 1, "deg", "TIMING", lambda d: _u8(d) / 2 - 64),
    0x0D: Pid(0x0D, "VSS", 1, "kph", "VSS", lambda d: _u8(d)),
    0x42: Pid(0x42, "Module V", 2, "V", "VOLT", lambda d: _u16(d) / 1000),
    0x06: Pid(0x06, "STFT", 1, "%", "STFT", lambda d: _u8(d) * 100 / 128 - 100),
    0x07: Pid(0x07, "LTFT", 1, "%", "LTFT", lambda d: _u8(d) * 100 / 128 - 100),
    0x15: Pid(0x15, "O2 S2", 2, "V", "O2", lambda d: d[0] / 200),
    0x33: Pid(0x33, "Baro", 1, "kPa", "BARO", lambda d: _u8(d)),
    0x47: Pid(0x47, "Abs Thr B", 1, "%", "TP", lambda d: _u8(d) * 100 / 255),
    0x4C: Pid(0x4C, "Cmd Thr", 1, "%", "TP", lambda d: _u8(d) * 100 / 255),
    0x1F: Pid(0x1F, "Run Time", 2, "s", "RUNTIME", lambda d: _u16(d)),
    0x2C: Pid(0x2C, "Cmd EGR", 1, "%", "EGR", lambda d: _u8(d) * 100 / 255),
    0x2E: Pid(0x2E, "Cmd Evap", 1, "%", "EVAP", lambda d: _u8(d) * 100 / 255),
}

# エディタ標準表示に使う既定PID(順序は表示順)
DEFAULT_PIDS = [0x0C, 0x04, 0x43, 0x0B, 0x10, 0x11, 0x0E, 0x0D, 0x05, 0x0F, 0x42]
# ライブパネル2行目(センサ/トリム系)
EXTRA_PIDS = [0x49, 0x4A, 0x06, 0x07, 0x15, 0x33, 0x2C, 0x2E, 0x1F]

# 軸名プレフィックス → ロール(i18n.AXIS_LABELS と整合)
AXIS_ROLE = {
    "RPM": "RPM", "LOAD": "LOAD", "ECT": "ECT", "IAT": "IAT",
    "APP": "APP", "TP": "TP", "TPS": "TP", "MAP": "MAP", "MANIFOLD": "MAP",
    "MAF": "MAF", "VSS": "VSS",
}


def axis_role(axis_name: str) -> str | None:
    """軸名(例 'RPM_6DD8')からライブ・ロールを返す。対応が無ければ None。"""
    if not axis_name:
        return None
    import re
    pref = re.split(r"[_0-9/ ]", axis_name, 1)[0].upper()
    return AXIS_ROLE.get(pref)


def interp_index(breakpoints: list[float], value: float) -> float | None:
    """軸ブレークポイント列中での value の位置(連続インデックス)を返す。
    0.0=先頭, len-1=末尾。範囲外はクランプ。単調増加/減少の両方に対応。"""
    bp = [b for b in breakpoints if isinstance(b, (int, float))]
    n = len(bp)
    if n == 0:
        return None
    if n == 1:
        return 0.0
    asc = bp[-1] >= bp[0]
    seq = bp if asc else bp[::-1]
    if value <= seq[0]:
        idx = 0.0
    elif value >= seq[-1]:
        idx = float(n - 1)
    else:
        idx = float(n - 1)
        for i in range(n - 1):
            if seq[i] <= value <= seq[i + 1]:
                span = seq[i + 1] - seq[i]
                frac = (value - seq[i]) / span if span else 0.0
                idx = i + frac
                break
    return idx if asc else (n - 1 - idx)


def decode_dtc(a: int, b: int) -> str:
    """2バイトのDTCを 'P0301' 形式へ。"""
    letter = "PCBU"[(a >> 6) & 3]
    return f"{letter}{(a >> 4) & 3}{a & 0xF:X}{(b >> 4) & 0xF:X}{b & 0xF:X}"


def read_dtcs(diag) -> list[tuple[str, str]]:
    """OBD Mode 03(確定)/07(保留)の DTC を読む。[(code, kind), ...] を返す。"""
    from .diag import NegativeResponse
    from .isotp import IsoTpError
    out = []
    for sid, kind in ((0x03, "stored"), (0x07, "pending")):
        try:
            r = diag.request(bytes([sid]), timeout=1.0)
        except (NegativeResponse, IsoTpError, Exception):  # noqa: BLE001
            r = None
        if not r or r[0] != sid + 0x40:
            continue
        data = r[1:]
        if len(data) % 2 == 1:   # 先頭が件数バイトの形式
            data = data[1:]
        for i in range(0, len(data) - 1, 2):
            a, b = data[i], data[i + 1]
            if a == 0 and b == 0:
                continue
            out.append((decode_dtc(a, b), kind))
    return out


class LiveReader:
    """バックグラウンドで Mode01 PID と DTC をポーリングし最新値を保持(読み取り専用)。"""

    def __init__(self, pids=None, interval=0.1, open_bus=None, read_dtc=True):
        self.pid_ids = list(pids) if pids else list(DEFAULT_PIDS) + list(EXTRA_PIDS)
        self.read_dtc = read_dtc
        self._dtc_interval = 2.0
        self._last_dtc = 0.0
        self.dtcs: list[tuple[str, str]] = []
        self.interval = interval
        self._open_bus = open_bus
        self._bus = None
        self._diag = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.values: dict[str, float] = {}   # role -> value
        self.by_pid: dict[int, float] = {}    # pid -> value
        self.error: str | None = None
        self.connected = False
        self.last_update = 0.0

    def start(self):
        from .canbus import open_bus as _ob
        from .diag import DiagClient
        from .isotp import IsoTp
        opener = self._open_bus or _ob
        self._bus = opener()
        self._diag = DiagClient(IsoTp(self._bus))
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        from .diag import NegativeResponse
        from .isotp import IsoTpError
        while not self._stop.is_set():
            got = {}
            roles = {}
            for pid in self.pid_ids:
                if self._stop.is_set():
                    break
                spec = PIDS.get(pid)
                if not spec:
                    continue
                try:
                    r = self._diag.request(bytes([0x01, pid]), timeout=0.5)
                except (NegativeResponse, IsoTpError, Exception):  # noqa: BLE001
                    r = None
                if r and len(r) >= 2 + spec.nbytes and r[0] == 0x41 and r[1] == pid:
                    data = r[2:2 + spec.nbytes]
                    try:
                        val = float(spec.decode(data))
                    except Exception:  # noqa: BLE001
                        continue
                    got[pid] = val
                    roles[spec.role] = val
            dtcs = None
            now = time.monotonic()
            if self.read_dtc and (now - self._last_dtc) >= self._dtc_interval:
                self._last_dtc = now
                try:
                    dtcs = read_dtcs(self._diag)
                except Exception:  # noqa: BLE001
                    dtcs = None
            with self._lock:
                self.by_pid.update(got)
                self.values.update(roles)
                if dtcs is not None:
                    self.dtcs = dtcs
                self.connected = bool(got)
                self.last_update = time.monotonic()
            if self._stop.wait(self.interval):
                break

    def latest(self) -> dict[str, float]:
        with self._lock:
            return dict(self.values)

    def latest_by_pid(self) -> dict[int, float]:
        with self._lock:
            return dict(self.by_pid)

    def latest_dtcs(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self.dtcs)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self._bus = None
        self.connected = False
