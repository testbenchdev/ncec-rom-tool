"""CAN インターフェースの生成（candleLight / gs_usb、または Linux/WSL2 の socketcan）。

接続方式は環境変数 NCEC_CAN で上書きできる（既定 gs_usb の呼び出しだけに作用。テストの
virtual 等 明示指定はそのまま）:
  NCEC_CAN=socketcan:can0   … WSL2/Linux の socketcan(can0)。bitrate は OS 側(ip link)で設定。
  NCEC_CAN=socketcan        … 同上、channel=can0 既定。
  NCEC_CAN=gs_usb           … 既定(Windows の candleLight)。
socketcan は TX エコーが無く(= drain不要)、カーネル送信でフレーム毎のユーザ空間USB往復も
無いため、gs_usb(Windows) より大幅に速い。WSL2 導入手順は docs/setup_wsl_ja.md。
"""
import os
import time

import can

DEFAULT_BITRATE = 500_000

_libusb_backend_ready = False


def _prefer_bundled_libusb() -> None:
    """libusb-1.0.dll が OS 側に無い PC でも gs_usb を使えるようにする保険。

    pyusb の既定バックエンドは libusb-1.0.dll を PATH/システムから探すため、DLL を
    配置していない別PCでは NoBackendError になる。libusb-package(pip)が入っていれば、
    その同梱 DLL を libusb1 バックエンドの既定に差し込む。パッケージや DLL が無ければ
    何もしない(従来どおり OS の libusb を使う)。管理者権限・PATH 変更・DLLコピーは不要。
    """
    global _libusb_backend_ready
    if _libusb_backend_ready:
        return
    _libusb_backend_ready = True
    try:
        import pathlib

        import libusb_package
        import usb.backend.libusb1 as _libusb1

        dll = pathlib.Path(libusb_package.__file__).parent / "libusb-1.0.dll"
        if not dll.is_file():
            return
        backend = _libusb1.get_backend(find_library=lambda _name: str(dll))
        if backend is not None:
            _libusb1.get_backend = lambda find_library=None: backend
    except Exception:  # noqa: BLE001
        pass


def open_bus(bitrate: int = DEFAULT_BITRATE, interface: str = "gs_usb",
             channel: int = 0, index: int = 0,
             retries: int = 5, retry_delay: float = 0.6,
             can_filters=None) -> can.BusABC:
    """CAN バスを開く。テスト用に interface="virtual" も指定できる。

    can_filters: python-can の受信フィルタ(例 [{"can_id":0x7E8,"can_mask":0x7FF,
      "extended":False}])。None=フィルタ無し(全フレーム受信)。gs_usb はHWフィルタ非対応で
      USB受信量自体は減らないが、python-can が非マッチ(自局TXエコー/車体CAN)をC側の recv
      ループで捨てるため、IsoTp の Python 側 recv 往復が減りライブ更新が速くなる
      (ライブは既定でこのフィルタを使用)。IsoTp.flush() はドレイン中だけフィルタを一時解除
      してハードドレインするので、フィルタを当てても古い応答の消し残し(レート漸減)は起きない。

    gs_usb(candleLight系)は前のハンドルの解放がOSレベルで非同期のため、Live停止
    直後やフラッシュ直後の再オープンで USBError [Errno 13] Access denied になることが
    ある。短いリトライ(既定 5回×0.6s)でこの解放ラグを吸収する。本当にデバイスが
    無い/他プロセスが掴みっぱなしの場合は、リトライ後に最後の例外を送出する。
    """
    # 環境変数 NCEC_CAN による方式上書き(既定 gs_usb の呼び出しのみ。virtual等の明示指定は不変)。
    env = os.environ.get("NCEC_CAN")
    if env and interface == "gs_usb":
        parts = env.split(":", 1)
        interface = parts[0].strip()
        if len(parts) > 1 and parts[1].strip():
            channel = parts[1].strip()
        elif interface == "socketcan":
            channel = "can0"

    last = None
    for attempt in range(max(1, retries)):
        try:
            if interface == "gs_usb":
                _prefer_bundled_libusb()
                return can.Bus(interface="gs_usb", channel=channel, index=index,
                               bitrate=bitrate, can_filters=can_filters)
            if interface == "socketcan":
                # bitrate は OS 側(ip link set can0 type can bitrate 500000)で設定済み前提。
                # socketcan は TX エコー無し(receive_own_messages 既定False)なので drain は空振り=無害。
                return can.Bus(interface="socketcan", channel=channel, can_filters=can_filters)
            return can.Bus(interface=interface, channel=channel, bitrate=bitrate,
                           can_filters=can_filters)
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(retry_delay)
    raise last


def close_bus(bus) -> None:
    """CAN バスを確実に閉じる。

    python-can の gs_usb は shutdown() で USB デバイス(pyusb ハンドル)を
    dispose しないため、同一プロセス内では解放されず、次の open_bus() が
    USBError [Errno 13] Access denied になる(Live停止→即再接続で多発)。
    shutdown 後に pyusb デバイスを明示 dispose して即解放する。
    """
    if bus is None:
        return
    try:
        bus.shutdown()
    except Exception:  # noqa: BLE001
        pass
    # gs_usb: bus.gs_usb(=GsUsb) .gs_usb(=usb.core.Device) を dispose して libusb ハンドルを解放
    try:
        import usb.util
        dev = getattr(getattr(bus, "gs_usb", None), "gs_usb", None)
        if dev is not None:
            usb.util.dispose_resources(dev)
    except Exception:  # noqa: BLE001
        pass
