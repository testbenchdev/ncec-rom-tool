"""WSL2/socketcan 接続ヘルパ(GUIから使う薄い層)。

NCEC ROM Map Editor を WSL2(WSLg) 上で socketcan で動かすときの「接続状態の確認」と
「再接続(usbipd attach + can0 up)」を提供する。Windows/gs_usb 実行時や非Linux環境では
すべて安全に no-op / 空情報を返し、既存のフォールバック起動(Windowsのgs_usb)に影響しない。

設計方針(docs/setup_wsl_ja.md と対):
- アダプタは VID:PID 1d50:606f(candleLight/SH-C30L)を usbipd.exe list から検索(busidハードコード無し)。
- usbipd.exe は WSL interop 経由で呼べる(Windows PATH が WSL に継承される)。
- can0 の up は root 権限が要るが、setup で /usr/local/sbin/ncec-can0-up への NOPASSWD sudoers を
  入れてあるので `sudo -n` で一般ユーザーのまま実行できる。

重依存なし(標準ライブラリのみ)。Windows から import しても安全。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time

CAN_VIDPID = "1d50:606f"              # candleLight / SH-C30L(Geschwister Schneider CAN)
CAN0_UP = "/usr/local/sbin/ncec-can0-up"
DEFAULT_CHANNEL = "can0"


def active_method() -> str:
    """現在のCAN方式。環境変数 NCEC_CAN の値(例 'socketcan:can0')、無ければ 'gs_usb'。"""
    return os.environ.get("NCEC_CAN") or "gs_usb"


def is_socketcan() -> bool:
    return active_method().split(":", 1)[0].strip() == "socketcan"


def on_linux() -> bool:
    return sys.platform.startswith("linux")


def channel() -> str:
    """NCEC_CAN=socketcan:<ch> の <ch>。未指定なら can0。"""
    m = active_method()
    if ":" in m:
        return m.split(":", 1)[1].strip() or DEFAULT_CHANNEL
    return DEFAULT_CHANNEL


STUCK_NOTE = "コマンドが終了しません(カーネル内で停止)。WSLの再起動が必要です。"

STALE_MSG = (
    "⚠ CANアダプタの USB/IP 接続が切れています"
    "(Windows側=未接続 / WSL側={ch} が残ったまま)。\n"
    "この状態で {ch} を操作するとコマンドが固まるため、状態取得と再接続を止めています。\n"
    "復旧手順: ①エディタを閉じる ②Windows で `wsl --shutdown` ③NCEC_Editor_WSL.bat で起動し直す。\n"
    "主な原因: Wi-Fi/ネットワークの切替、スリープ復帰、USBの抜き差し"
    "(WSLの仮想ネットワークがリセットされると切れます。車での作業中は Wi-Fi を切ると防げます)。"
)


def _run(cmd, timeout: float = 15.0) -> tuple[int, str]:
    """subprocess を安全に実行し (rc, 出力) を返す。失敗時も例外を投げない。

    タイムアウト時は子を kill するが、**終了を無期限には待たない**。USB/IP 接続が切れた状態の
    `ip` はカーネル内で割り込み不能(D状態)になり kill しても終わらない。subprocess.run は
    タイムアウト後に子の終了を待つため、そのままだと呼び出し側(GUIスレッド)ごと固まる
    (2026-11-12 のフリーズ)。kill 後は短時間だけ回収を試み、だめなら放棄して戻る。
    """
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, ((out or "") + (err or "")).strip()
    except subprocess.TimeoutExpired:
        try:
            p.kill()
        except Exception:  # noqa: BLE001
            pass
        try:
            p.communicate(timeout=2.0)
        except Exception:  # noqa: BLE001
            return -1, f"TimeoutExpired: {timeout:g}s  {STUCK_NOTE}"
        return -1, f"TimeoutExpired: {timeout:g}s"
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def _usbipd() -> str | None:
    """WSL interop 経由の usbipd 実体。見つからなければ None。"""
    return shutil.which("usbipd.exe") or shutil.which("usbipd")


_STATE_RE = re.compile(r"\s{2,}(Attached|Shared(?: \(forced\))?|Not shared)\s*$")


def parse_usbipd_list(out: str) -> tuple[str | None, str | None]:
    """`usbipd list` の出力から SH-C30L(1d50:606f) の (busid, state) を返す。
    state は 'Attached' / 'Shared' / 'Not shared' など。見つからなければ (None, None)。"""
    for line in out.splitlines():
        if CAN_VIDPID in line.lower():
            tok = line.split()
            if tok and re.match(r"^\d+-\d+$", tok[0]):
                m = _STATE_RE.search(line)
                return tok[0], (m.group(1) if m else None)
    return None, None


def adapter_info() -> tuple[str | None, str | None]:
    """Windows 側(usbipd)から見たアダプタの (busid, state)。usbipd が無い/失敗は (None, None)。"""
    exe = _usbipd()
    if not exe:
        return None, None
    rc, out = _run([exe, "list"], timeout=8.0)
    if rc != 0:
        return None, None
    return parse_usbipd_list(out)


def _sysfs(ch: str, name: str) -> str | None:
    """/sys/class/net/<ch>/<name> を読む。flags / operstate / tx_queue_len は RTNL ロックも
    USB 通信も要らないので、USB/IP 接続が切れていても固まらない(carrier は固まるので読まない)。"""
    try:
        with open(f"/sys/class/net/{ch}/{name}", encoding="ascii", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return None


def iface_exists(ch: str | None = None) -> bool:
    return os.path.isdir(f"/sys/class/net/{ch or channel()}")


def iface_up(ch: str | None = None) -> bool:
    """IFF_UP(管理上の up)かどうか。sysfs の flags から判定(コマンド実行なし)。"""
    flags = _sysfs(ch or channel(), "flags")
    try:
        return bool(int(flags, 16) & 0x1)
    except (TypeError, ValueError):
        return False


def link_stale(state: str | None = None, ch: str | None = None) -> bool:
    """USB/IP 接続切れ(Windows側は未接続なのに WSL 側に can0 が残っている)なら True。

    WSL の仮想ネットワークがリセットされる(Wi-Fi 切替/スリープ復帰など)と usbipd との TCP が切れ、
    Windows 側は 'Shared' に戻るが、WSL 側の vhci は気づかず can0 が残る。この状態で
    `ip -details link show can0` や `ip link set can0 ...` を実行すると、gs_usb の USB 制御転送が
    返らずコマンドが D 状態で固まり、RTNL ロックを握ったままになる(以後の ip も全滅)。
    state 省略時は usbipd に問い合わせる。usbipd が無い(ネイティブLinux等)場合は False。
    """
    if not on_linux() or not iface_exists(ch):
        return False
    if state is None:
        _busid, state = adapter_info()
    return _detached(state)


def _detached(state: str | None) -> bool:
    """usbipd の state が「WSLへ未接続」を示すか。None(usbipd 不明)は未接続とみなさない。"""
    return state is not None and state != "Attached"


def can0_status(state: str | None = None) -> tuple[bool, str]:
    """can0(または NCEC_CAN 指定ch)の状態 (up, 詳細)。Linux以外は (False, 説明)。

    up/down は sysfs から読む(固まらない)。bitrate やバス状態などの詳細(`ip -details`)は、
    USB/IP 接続が生きていると確認できたときだけ取得する。state は adapter_info() の結果を
    渡せる(省略時は問い合わせる)。
    """
    if not on_linux():
        return False, "socketcan は WSL2/Linux 上でのみ使用します(現在は非Linux実行)。"
    ch = channel()
    if not iface_exists(ch):
        return False, f"{ch} が見つかりません(未attach の可能性)。"
    if state is None:
        _busid, state = adapter_info()
    if _detached(state):            # can0 は在るのに Windows 側は未接続＝USB/IP 接続切れ
        return False, STALE_MSG.format(ch=ch)
    up = iface_up(ch)
    detail = (f"{ch}: {'UP' if up else 'DOWN'}  operstate={_sysfs(ch, 'operstate')}"
              f"  txqueuelen={_sysfs(ch, 'tx_queue_len')}")
    if shutil.which("ip"):
        rc, out = _run(["ip", "-details", "link", "show", ch], timeout=5.0)
        detail += "\n" + (out if rc == 0 else f"(ip -details 取得失敗: {out})")
    return up, detail


def find_busid() -> str | None:
    """usbipd.exe list から SH-C30L(1d50:606f) の BUSID を探す。無ければ None。"""
    return adapter_info()[0]


def reconnect() -> tuple[bool, str]:
    """usbipd attach(→WSL) と can0 up を実行して (ok, ログ文字列) を返す。GUIから呼ぶ。

    手順: usbipd.exe attach --wsl --busid <自動検出> → sudo -n ncec-can0-up(NOPASSWD)。
    どちらの段でも例外は投げず、人が読めるログを返す。
    """
    if not on_linux():
        return False, "再接続は WSL2/Linux 実行時のみ有効です(現在は非Linux実行)。"
    log: list[str] = []
    exe = _usbipd()
    busid, state = adapter_info() if exe else (None, None)
    # USB/IP 接続切れ(can0 残留)のまま can0 を触ると固まるので、何も実行せず復旧手順を返す。
    if iface_exists() and _detached(state):
        return False, STALE_MSG.format(ch=channel())
    if exe:
        if busid and state == "Attached":
            log.append(f"usbipd: busid={busid} は接続済み(attach 省略)。")
        elif busid:
            rc, out = _run([exe, "attach", "--wsl", "--busid", busid], timeout=30.0)
            log.append(f"$ usbipd attach --wsl --busid {busid}\n{out or '(ok)'}")
        else:
            log.append("usbipd: SH-C30L(1d50:606f) が list に見つかりません(USB接続を確認)。")
    else:
        log.append("usbipd.exe が PATH にありません(WSL interop/usbipd導入を確認)。"
                   "手動 attach 済みなら can0 up のみ試みます。")
    # can0 up(NOPASSWD sudoers 経由)。attach 直後は can0 出現まで僅かなラグがあるので数回試す。
    rc = -1
    out = ""
    for _ in range(3):
        rc, out = _run(["sudo", "-n", CAN0_UP])
        if rc == 0 or STUCK_NOTE in out:
            break               # 固まった場合は再試行しない(固まったプロセスを増やさない)
        time.sleep(0.6)
    log.append(f"$ sudo -n {CAN0_UP}\n{out}")
    if STUCK_NOTE in out:
        log.append(f"[結果] {channel()} の操作が固まりました。`wsl --shutdown` 後に起動し直してください。")
        return False, "\n".join(log)
    up, _detail = can0_status()
    log.append(f"[結果] {channel()} up={up}")
    return up, "\n".join(log)


def summary() -> str:
    """接続状態の1〜数行サマリ(GUI表示用)。"""
    method = active_method()
    if not is_socketcan():
        return f"CAN方式: {method}(socketcan無効＝従来のgs_usb/明示指定方式)"
    busid, state = adapter_info() if on_linux() else (None, None)
    up, detail = can0_status(state)
    head = f"CAN方式: {method}   {channel()}: {'UP(接続OK)' if up else 'DOWN/未接続'}"
    if busid:
        head += f"   usbipd busid={busid} ({state or '?'})"
    return head + "\n" + detail
