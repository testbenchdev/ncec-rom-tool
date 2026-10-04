"""CAN インターフェースの生成（candleLight / gs_usb）。"""
import can

DEFAULT_BITRATE = 500_000


def open_bus(bitrate: int = DEFAULT_BITRATE, interface: str = "gs_usb",
             channel: int = 0, index: int = 0) -> can.BusABC:
    """CAN バスを開く。テスト用に interface="virtual" も指定できる。"""
    if interface == "gs_usb":
        return can.Bus(interface="gs_usb", channel=channel, index=index,
                       bitrate=bitrate)
    return can.Bus(interface=interface, channel=channel, bitrate=bitrate)
