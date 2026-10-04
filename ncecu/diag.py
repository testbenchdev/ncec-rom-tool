"""診断リクエスト／レスポンス（OBD-II / UDS 共通の要求応答処理）。"""
from .isotp import IsoTp

NRC_NAMES = {
    0x10: "generalReject", 0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
    0x13: "incorrectMessageLength", 0x21: "busyRepeatRequest", 0x22: "conditionsNotCorrect",
    0x24: "requestSequenceError", 0x31: "requestOutOfRange", 0x33: "securityAccessDenied",
    0x35: "invalidKey", 0x36: "exceedNumberOfAttempts", 0x37: "requiredTimeDelayNotExpired",
    0x72: "generalProgrammingFailure", 0x78: "responsePending",
    0x7E: "subFunctionNotSupportedInActiveSession", 0x7F: "serviceNotSupportedInActiveSession",
}


class NegativeResponse(Exception):
    def __init__(self, sid: int, nrc: int):
        self.sid, self.nrc = sid, nrc
        super().__init__(f"SID 0x{sid:02X} NRC 0x{nrc:02X} {NRC_NAMES.get(nrc, '')}")


class DiagClient:
    def __init__(self, tp: IsoTp):
        self.tp = tp

    def request(self, payload: bytes, timeout: float = 1.0) -> bytes | None:
        """要求を送り、肯定応答（SID+0x40 から始まるデータ）を返す。無応答なら None。"""
        sid = payload[0]
        self.tp.flush()
        self.tp.send(payload)
        while True:
            resp = self.tp.recv(timeout)
            if resp is None:
                return None
            if resp[0] == 0x7F and len(resp) >= 3 and resp[1] == sid:
                if resp[2] == 0x78:  # responsePending: 待ち延長
                    timeout = 5.0
                    continue
                raise NegativeResponse(sid, resp[2])
            if resp[0] == sid + 0x40:
                return resp
            # 関係ない応答は読み飛ばす

    def tester_present(self) -> bool:
        # この ECU は KWP2000 形式（3E 01）のみ受け付ける。3E 00 / 3E 80 は NRC 0x12
        try:
            return self.request(b"\x3E\x01") is not None
        except NegativeResponse:
            return True  # 応答があれば通信は生きている
