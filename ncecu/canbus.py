"""CAN インターフェースの生成（candleLight / gs_usb）。"""
import time

import can

DEFAULT_BITRATE = 500_000


def open_bus(bitrate: int = DEFAULT_BITRATE, interface: str = "gs_usb",
             channel: int = 0, index: int = 0,
             retries: int = 5, retry_delay: float = 0.6) -> can.BusABC:
    """CAN バスを開く。テスト用に interface="virtual" も指定できる。

    gs_usb(candleLight系)は前のハンドルの解放がOSレベルで非同期のため、Live停止
    直後やフラッシュ直後の再オープンで USBError [Errno 13] Access denied になることが
    ある。短いリトライ(既定 5回×0.6s)でこの解放ラグを吸収する。本当にデバイスが
    無い/他プロセスが掴みっぱなしの場合は、リトライ後に最後の例外を送出する。
    """
    last = None
    for attempt in range(max(1, retries)):
        try:
            if interface == "gs_usb":
                return can.Bus(interface="gs_usb", channel=channel, index=index,
                               bitrate=bitrate)
            return can.Bus(interface=interface, channel=channel, bitrate=bitrate)
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
