"""OBD-II Mode 01 ライブデータ取得(読み取り専用)。

実行中ECUの運転点(回転数・負荷・水温など)をCAN経由でポーリングし、
エディタの「現在セル追従」やライブ数値表示に使う。ECUの状態は一切変えない
(セッション変更・セキュリティ・書き込みは行わない)。

- PID デコードは標準 OBD-II。各PIDに「軸ロール」(RPM/LOAD/ECT…)を割り当て、
  テーブル軸(RPM_xxxx, LOAD_xxxx, ECT, IAT, APP, TP, MAP, VSS …)と対応付ける。
- LiveReader はバックグラウンドスレッドで最新値を保持(GUIは after() で読むだけ)。
"""
from __future__ import annotations

import struct  # noqa: F401  (将来の拡張用)
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
    # 前O2=ワイドレンジA/Fセンサ。0x34先頭2バイト=等価比λ((256A+B)/32768)→実測AFR(λ×14.64)
    0x34: Pid(0x34, "AFR", 4, "AFR", "AFR", lambda d: _u16(d) / 32768 * 14.64),
    # 0x44=指令等価比(ECUの目標λ)→目標AFR
    0x44: Pid(0x44, "AFR Tgt", 2, "AFR", "AFRCMD", lambda d: _u16(d) / 32768 * 14.64),
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
EXTRA_PIDS = [0x49, 0x4A, 0x06, 0x07, 0x15, 0x34, 0x44, 0x33, 0x2C, 0x2E, 0x1F]

# ライブRAM読み出し(Mode23有効化ROMが前提)の既定チャンネル。
# ch は合成キー(0x100台=実PIDと衝突しない)。role はダッシュボード/エディタ表示用。
# ⚠ ECU側でMode23有効化パッチが当たっていないと読めない(未有効化なら自動で停止)。
# ノック系の番地は純正ノック制御(Proto-Knock)のRE結果。RAMブロック 0xFFFF7C20-7CD0。
#   ベンチROMと実車ROM(同CAL LFG7EG)で該当コードは完全一致=実車に転用可。
#   Count/Event は cal 由来で確度高、Magnitude/Retard は確度中(実車で確認)。
# 番地は候補。実車で確認し、必要なら ram_reads.json で変更すること。
RAM_CHANNELS = [
    {"ch": 0x101, "addr": 0xFFFF6FCC, "type": "u8", "role": "CLUTCH",
     "name": "クラッチ", "unit": "", "interval": 0.2},
    {"ch": 0x102, "addr": 0xFFFF7C4C, "type": "f32", "role": "KR",
     "name": "KR(ノック遅角・候補)", "unit": "°", "interval": 0.5},
    {"ch": 0x103, "addr": 0xFFFF777C, "type": "f32", "role": "EGT",
     "name": "排気温(触媒推定)", "unit": "°C", "interval": 2.0},
    # --- ノック(Proto-Knock)RE結果 ---
    {"ch": 0x104, "addr": 0xFFFF7C3A, "type": "u8", "role": "KNOCKCNT",
     "name": "ノックカウント", "unit": "", "interval": 0.2},
    {"ch": 0x105, "addr": 0xFFFF7C60, "type": "f32", "role": "KNOCKMAG",
     "name": "ノック強度(候補)", "unit": "", "interval": 0.2},
    {"ch": 0x106, "addr": 0xFFFF7C44, "type": "f32", "role": "KNOCKRTD",
     "name": "ノックリタード(適用・候補)", "unit": "°", "interval": 0.5},
]


# PIDごとの既定の問い合わせ間隔[秒]。0(またはこの表に無いPID)=毎周期取得。
# 変化のゆっくりした項目を間引くと、1要求=最大6PIDの枠に速い項目が収まり、
# 回転数などの更新が速くなる(Mode01は1要求6PIDまで)。UIから set_pid_interval で変更可。
DEFAULT_PID_INTERVALS: dict[int, float] = {
    # 毎回(0.0): 0x0C RPM / 0x04 Load / 0x0B MAP / 0x10 MAF / 0x11 Throttle / 0x0E Timing
    0x34: 0.5, 0x45: 0.5, 0x49: 0.5, 0x4A: 0.5,            # AFR実測・相対スロットル・APP
    0x43: 1.0, 0x44: 1.0, 0x06: 1.0, 0x07: 1.0,            # 絶対負荷・AFR目標・STFT・LTFT
    0x2C: 1.0, 0x0D: 1.0, 0x47: 1.0, 0x4C: 1.0,            # EGR・車速・絶対スロB・指令スロ
    0x05: 2.0, 0x0F: 2.0, 0x15: 2.0, 0x2E: 2.0,            # 水温・吸気温・O2・Evap
    0x42: 5.0, 0x33: 5.0, 0x1F: 5.0,                        # 電圧・大気圧・経過時間
}

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

    def __init__(self, pids=None, interval=0.0, open_bus=None, read_dtc=True,
                 on_update=None, multi=True, dtc_interval=5.0,
                 pid_intervals=None, decimate=True, ram_reads=None):
        self.pid_ids = list(pids) if pids else list(DEFAULT_PIDS) + list(EXTRA_PIDS)
        # ライブRAM読み出し(Mode23)。各要素 {ch,addr,type,role,name,unit,interval}。
        self.ram_reads = [dict(c) for c in (ram_reads or [])]
        self._ram_last: dict[int, float] = {}   # ch -> 最後に読んだ時刻
        self._ram_nrc = 0                        # 連続NRC回数(未有効化の検出)
        self.mode23_ok: bool | None = None       # None=未試行 / True=読めた / False=未有効化
        self.ram_values: dict[str, float] = {}   # role -> value
        # PIDごとの間引き間隔[秒]。decimate=Falseで無効(全て毎回)。
        self.decimate = decimate
        base = dict(DEFAULT_PID_INTERVALS)
        if pid_intervals:
            base.update(pid_intervals)
        self._intervals: dict[int, float] = base if decimate else {}
        self._last_poll: dict[int, float] = {}   # pid -> 最後に問い合わせた時刻(monotonic)
        self.read_dtc = read_dtc
        self._dtc_interval = dtc_interval
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
        # on_update(by_pid, dtcs, t): 1ポーリング周期ごとに読取スレッドから呼ぶ(高精度ロギング用)
        self.on_update = on_update
        # マルチPID一括要求(J1979: 1要求で最大6PID)。None=1周目で対応判定, True/False=確定
        self.multi = None if multi else False
        self.rate = 0.0          # 実測更新レート(Hz, EMA)
        self._prev = None

    def set_pid_interval(self, pid: int, seconds: float) -> None:
        """PIDごとの問い合わせ間隔[秒]を設定(0=毎回)。UIから変更する用。"""
        self._intervals[pid] = max(0.0, float(seconds))

    def _due_pids(self, now: float) -> list[int]:
        """この周期で問い合わせるPIDの並びを返す。
        - interval が 0 のPID(毎回)と、前回から interval 以上経過したPIDを対象にする。
        - 6個単位の要求枠に空きがあれば、まだ期限の来ていないPIDを“次に期限が近い順”で
          詰める(ついで取得。要求回数は増やさない)。"""
        due, rest = [], []
        for p in self.pid_ids:
            iv = self._intervals.get(p, 0.0)
            if iv <= 0 or (now - self._last_poll.get(p, -1e9)) >= iv:
                due.append(p)
            else:
                rest.append(p)
        cap = ((len(due) + 5) // 6) * 6
        spare = cap - len(due)
        if spare > 0 and rest:
            rest.sort(key=lambda p: self._last_poll.get(p, -1e9) + self._intervals.get(p, 0.0))
            due += rest[:spare]
        return due

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
        while not self._stop.is_set():
            c0 = time.monotonic()
            if self._prev is not None:
                per = c0 - self._prev
                if per > 0:
                    inst = 1.0 / per
                    self.rate = inst if self.rate == 0 else self.rate * 0.7 + inst * 0.3
            self._prev = c0

            # この周期で取得するPID(間引き後)。遅い項目は期限が来たときだけ問い合わせ、
            # 未取得のPIDは直前値をそのまま保持する(values/by_pidは上書きしないため)。
            req = self._due_pids(c0)
            for p in req:
                self._last_poll[p] = c0

            got = {}
            # --- マルチPID一括要求(対応時: 往復回数を約1/6に) ---
            if self.multi is not False:
                ok = True
                for k in range(0, len(req), 6):
                    if self._stop.is_set():
                        break
                    chunk = [p for p in req[k:k + 6] if p in PIDS]
                    res = self._read_pids(chunk)
                    if res is None:
                        ok = False
                        break
                    got.update(res)
                if self.multi is None:            # 1周目で対応判定
                    self.multi = ok and len(got) >= min(3, len(req))
                    if not self.multi:
                        got = {}                  # 誤解釈の可能性→捨てて per-PID でやり直し
                elif not ok:
                    self.multi = False
                    got = {}
            # --- 1個ずつ(非対応/フォールバック) ---
            if self.multi is False and not got:
                for pid in req:
                    if self._stop.is_set():
                        break
                    v = self._read_one(pid)
                    if v is not None:
                        got[pid] = v
            roles = {PIDS[p].role: v for p, v in got.items() if p in PIDS}

            # --- ライブRAM読み出し(Mode23有効化ROM前提。未有効化なら自動停止) ---
            if self.ram_reads and self.mode23_ok is not False:
                self._poll_ram(got, roles)

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
                self.last_update = now
                snap = dict(self.by_pid)   # 間引き中の項目も直前値で記録できるよう全値のスナップショット
            # 高精度ロギング: 取得した瞬間に(UIの描画周期に依存せず)コールバック
            if self.on_update is not None and got:
                try:
                    self.on_update(snap,
                                   dtcs if dtcs is not None else list(self.dtcs), now)
                except Exception:  # noqa: BLE001
                    pass
            if self._stop.wait(self.interval):
                break

    def _read_pids(self, pids):
        """複数PIDを1要求(01 pid1 pid2 …)で取得。{pid:value} を返す。失敗/未対応は None。
        応答 41 pid d.. pid d.. を PID→nbytes で自己記述的にパースする。"""
        if not pids:
            return {}
        from .diag import NegativeResponse
        from .isotp import IsoTpError
        try:
            r = self._diag.request(bytes([0x01]) + bytes(pids), timeout=0.6)
        except (NegativeResponse, IsoTpError, Exception):  # noqa: BLE001
            return None
        if not r or r[0] != 0x41:
            return None
        out = {}
        i, n = 1, len(r)
        while i < n:
            spec = PIDS.get(r[i])
            if spec is None:
                break                      # 未知PID=長さ不明→打ち切り(得た分は返す)
            data = r[i + 1:i + 1 + spec.nbytes]
            if len(data) < spec.nbytes:
                break
            try:
                out[r[i]] = float(spec.decode(data))
            except Exception:  # noqa: BLE001
                pass
            i += 1 + spec.nbytes
        return out

    def _read_one(self, pid):
        from .diag import NegativeResponse
        from .isotp import IsoTpError
        spec = PIDS.get(pid)
        if spec is None:
            return None
        try:
            r = self._diag.request(bytes([0x01, pid]), timeout=0.5)
        except (NegativeResponse, IsoTpError, Exception):  # noqa: BLE001
            return None
        if r and len(r) >= 2 + spec.nbytes and r[0] == 0x41 and r[1] == pid:
            try:
                return float(spec.decode(r[2:2 + spec.nbytes]))
            except Exception:  # noqa: BLE001
                return None
        return None

    def _poll_ram(self, got, roles):
        """期限が来たRAMチャンネルを Mode23 (23 addr size) で読む(既定セッション・読み取り専用)。"""
        from . import mode23
        from .diag import NegativeResponse
        from .isotp import IsoTpError
        now = time.monotonic()
        for c in self.ram_reads:
            ch = c["ch"]
            if now - self._ram_last.get(ch, -1e9) < c.get("interval", 0.5):
                continue
            self._ram_last[ch] = now
            typ = c.get("type", "u8")
            size = mode23.type_size(typ)
            if not mode23.addr_readable(c["addr"], size):
                continue
            try:
                resp = self._diag.request(mode23.read_request(c["addr"], size), timeout=0.4)
            except NegativeResponse:          # 未有効化なら NRC が返る
                self._ram_nrc += 1
                if self._ram_nrc >= 4:
                    self.mode23_ok = False     # 未有効化と判断してライブRAMを停止
                return
            except (IsoTpError, Exception):   # noqa: BLE001  一時的エラーはスキップ(停止はしない)
                return
            data = mode23.parse_read(resp, size)
            if data is None:
                continue
            val = float(mode23.decode(data, typ))
            val = val * c.get("scale", 1.0) + c.get("offset", 0.0)
            got[ch] = val
            roles[c["role"]] = val
            self.ram_values[c["role"]] = val
            self.mode23_ok = True
            self._ram_nrc = 0

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
            from .canbus import close_bus
            close_bus(self._bus)   # pyusb デバイスを dispose して確実に解放(再接続Errno13防止)
            self._bus = None
        self.connected = False
