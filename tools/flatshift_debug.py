"""フラットシフト 点火カット 停車デバッグ・モニタ（Mode23＋OBD。読み取り専用）。

第6ドラフト（スクラッチ無し・読み取り専用設計）では、ケーブは内部フラグをRAMに持たない。
よって本ツールは起動時に **書き込み済みROMの設定（方式/test_mode/各しきい値・パッチ適用の有無）を Mode23 で
flash 直読**して表示し、以降 **クラッチ＋APP＋RPM＋車速＋バッテリ電圧** を監視して、ケーブと同じゲートを
その場で評価する（「不発ならどの条件が原因か」をライブ表示）。点火カットの可否は電圧＋回転頭打ち＋
タイミングライトの“効果”で判定する。

★ 前提:
  - フラットシフト・パッチ適用済みROMを書き込み、**CAL test_mode=1**（エディタの『デバッグ テストモード』
    またはCLIの --test）にしておく。test_mode=1 だと**車速ゲートだけ無視**し、クラッチ＋回転＋アクセルで発動
    （始動/アイドルは低回転でゲート不成立＝発動しないのでクラッチ始動を妨げない。停車Nで回転を上げると発動）。
  - Mode23有効化パッチ適用済み（クラッチ値の読み出し用）。CAN/OBD接続。エンジンはアイドル、
    **ニュートラル・サイドブレーキ**。消火器・電源遮断の準備。走行では必ず test_mode=0 に戻すこと。

★ 手順:
  1. 本ツールを起動（アイドル放置の値が流れる）。test_mode=1 でも始動/アイドルは低回転でゲート不成立のため
     発動しないので、普通に始動・アイドルできる（＝クラッチ始動を妨げない）。
  2. 停車確認用に RPMしきい値を低め（例3000rpm）・APPしきい値も低め（例15%）にしておく（エディタ/CLIで設定）。
     **ニュートラルのままクラッチを踏み、アクセルを軽くあおって回転をRPMしきい値以上へ**。あおり中の値を見る:
     - 回転がしきい値付近で頭打ち/ばらつく/伸びない → 点火が止まっている＝カット効果あり
     - **電圧が維持**                → コイル未充電＝「充電スキップ」で想定どおり（安全）
     - **電圧が大きくドロップ**       → コイル通電しっぱなしの疑い＝発火を止めた可能性。**即アクセル/クラッチを離し
                                        test_mode=0 に戻す**（過熱回避）。
  3. タイミングライトを#1に当て、あおり中に**発火が消える**ことを確認（これが最終・確実な判定）。
     あおって回転がしきい値を超えても素通りで吹け上がる場合は、しきい値が高すぎるか、充電ハンドラ0x19D04が
     呼ばれていない可能性（しきい値を下げて再確認。それでも駄目なら別ハンドラへの再フックが必要）→報告のこと。

使い方: python tools/flatshift_debug.py        （Ctrl+C で終了）
"""
import pathlib
import struct
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ncecu import flatshift, mode23                      # noqa: E402
from ncecu.canbus import close_bus, open_bus             # noqa: E402
from ncecu.diag import DiagClient, NegativeResponse      # noqa: E402
from ncecu.isotp import IsoTp, IsoTpError                # noqa: E402


def _ram(diag, addr, n):
    try:
        data = mode23.parse_read(diag.request(mode23.read_request(addr, n), timeout=0.5), n)
    except (NegativeResponse, IsoTpError):
        return None
    return int.from_bytes(data, "big") if data else None


def _f32(diag, addr):
    raw = _ram(diag, addr, 4)
    return struct.unpack(">f", raw.to_bytes(4, "big"))[0] if raw is not None else None


def _pid(diag, pid, nbytes):
    try:
        r = diag.request(bytes([0x01, pid]), timeout=0.5)
    except (NegativeResponse, IsoTpError):
        return None
    if r and len(r) >= 2 + nbytes and r[0] == 0x41 and r[1] == pid:
        return int.from_bytes(r[2:2 + nbytes], "big")
    return None


def _pct(diag, pid):
    """100/255スケールのパーセント系OBD PID（0x11スロットル, 0x49ペダルD 等）を%で。"""
    raw = _pid(diag, pid, 1)
    return raw * 100 / 255 if raw is not None else None


def _lambda(diag):
    """ワイドバンドO2(PID0x34)の当量比λ。1=理論空燃比、>1=リーン。
    点火カット中は未燃焼の空気/燃料が排気へ出る＝O2余り＝λが跳ね上がる（カットのソフト検出に使える）。"""
    try:
        r = diag.request(bytes([0x01, 0x34]), timeout=0.5)
    except (NegativeResponse, IsoTpError):
        return None
    if r and len(r) >= 4 and r[0] == 0x41 and r[1] == 0x34:
        return (r[2] * 256 + r[3]) * 2 / 65536
    return None


def _timing(diag):
    """点火時期(進角, PID0x0E)を度で。A/2-64。
    method=0(遅角)は発動中に点火時期が下がる＝遅角の直接証拠。method=1(カット)は下がらない(正常)。"""
    raw = _pid(diag, 0x0E, 1)
    return raw / 2 - 64 if raw is not None else None


def _num(x):
    return x if (x is not None and x == x) else float("nan")


def read_config(diag):
    """書き込み済みROMの flatshift 設定を Mode23 で flash 直読する。dict or None。"""
    clamp = _ram(diag, flatshift.CLAMP_LIT, 4)
    hptr = _ram(diag, flatshift.HANDLER_PTR, 4)
    if clamp is None or hptr is None:
        return None
    cfg = {"applied": clamp == flatshift.CAVE and hptr == flatshift.CAVE2,
           "clamp": clamp, "hptr": hptr, "cals": {}}
    for k, a in flatshift.CAL_ADDRS.items():
        raw = _ram(diag, a, 4)
        if raw is None:
            cfg["cals"] = None
            break
        cfg["cals"][k] = (struct.unpack(">f", raw.to_bytes(4, "big"))[0]
                          if k in flatshift._FLOAT_KEYS else raw)
    return cfg


def print_config(cfg):
    """設定を表示し、発動に向けた警告を出す。先へ進めそうなら True。"""
    if cfg is None:
        print("!! Mode23で読めません。有効化パッチ/配線/IG ON を確認してください。")
        return False
    print("── 書き込み済みROMの設定（Mode23でflash直読）──")
    print(f"  パッチ適用: {'はい' if cfg['applied'] else '**いいえ**'}"
          f"  (@{flatshift.CLAMP_LIT:X}={cfg['clamp']:08X}/期待{flatshift.CAVE:08X},"
          f" @{flatshift.HANDLER_PTR:X}={cfg['hptr']:08X}/期待{flatshift.CAVE2:08X})")
    if not cfg["applied"]:
        print("  → フラットシフト未適用か別ROM。パッチ適用ROMを書き込んでください。")
        return False
    c = cfg["cals"]
    if c is None:
        print("  CAL読み取りに失敗（配線/タイミング）。ライブ値のみ表示します。")
        return True
    print(f"  方式 method={c['method']}({'点火カット' if c['method'] else '点火遅角'})"
          f"  test_mode={c['test_mode']}"
          f"({'停車デバッグ=車速ゲート無視' if c['test_mode'] else '通常=停車では不発'})")
    print(f"  しきい値: RPM>{c['rpm']:.0f}  APP>{c['app']:.0f}%  車速>{c['vss']:.0f}km/h"
          f"   遅角={c['retard']:.0f}° 下限={c['floor']:.0f}°")
    for w in (["method=0=点火遅角です（充電スキップのカットではない）。カット確認は method=1 に。"] if not c["method"] else []) \
            + (["test_mode=0 のため停車(車速0)では車速ゲートが通らず発動しません。停車確認は test_mode=1 に。"] if not c["test_mode"] else []) \
            + ([f"APPしきい値 {c['app']:.0f}% が高め。軽い空ぶかしでは APP がこれを超えず不発になりがち（停車確認は10〜15%推奨）。"] if c["app"] > 30 else []):
        print(f"  ⚠ {w}")
    print("  ※ 下の『ゲート判定』で、踏込中にどの条件が不成立か＝何が原因かを確認できます。")
    return True


def gate_eval(cfg, clutch, app, rpm, vss):
    """ケーブのゲートをそのまま評価。(発動する?, 理由) を返す。"""
    c = cfg.get("cals") if cfg else None
    if not clutch:
        return False, "クラッチOFF"
    if c is None:
        return False, "CAL不明"
    if app is None or rpm is None:
        return False, "読取不可"
    if not app > c["app"]:
        return False, f"APP {app:.0f}%≦{c['app']:.0f}%"
    if not rpm > c["rpm"]:
        return False, f"RPM {rpm:.0f}≦{c['rpm']:.0f}"
    if not c["test_mode"] and not (vss is not None and vss > c["vss"]):
        return False, f"車速 {_num(vss):.0f}≦{c['vss']:.0f}(test_mode=0)"
    return True, "発動条件成立"


def main():
    print(__doc__)
    bus = open_bus()
    diag = DiagClient(IsoTp(bus))
    diag.tp.timeout = 5.0
    try:
        cfg = read_config(diag)
        if not print_config(cfg):
            return
        print(f"\n監視(Mode23): clutch@{flatshift.RAM_CPP:X} APP@{flatshift.RAM_APP:X} "
              f"RPM@{flatshift.RAM_RPM:X} VSS@{flatshift.RAM_VSS:X} ＋ 電圧(PID42)\n")
        print("  ※ gAPP=ゲートAPP(0xFFFF56C8) ped49=実ペダル(PID49) thr=スロットル(PID11)。gAPPとped49が大きくズレ=APP番地/スケール要確認")
        print("  ※ max踏R=クラッチ踏込中の最大RPM（離すとリセット）。armed(踏)でしきい値付近に頭打ち＆disarmed(離)で同じ踏み方でも素通り＝カット有効の証拠")
        print("  ※ 点火°=点火時期(PID0x0E)。method=0(遅角)は発動中に下がる＝遅角の直接証拠。method=1(カット)は下がらない(正常)")
        print("  ※ λ=当量比(1=理論空燃比)。カット中は燃焼状態が変わりλが乱れる（定常λ≈1なら未燃O2でリーン寄り／加速増量中は元々リッチなのでリッチ寄り）。向きでなく“動くこと”が手掛かり＝主判定は回転A/B")
        print("  時刻 clutch gAPP ped49  thr    RPM  max踏R 点火°   λ   電圧V  ゲート判定")
        method = (cfg.get("cals") or {}).get("method") if cfg else None
        v_base = None
        max_rpm = 0.0
        while True:
            t = time.monotonic()
            clutch = _ram(diag, flatshift.RAM_CPP, 1)
            app = _f32(diag, flatshift.RAM_APP)
            rpm = _f32(diag, flatshift.RAM_RPM)
            vss = _f32(diag, flatshift.RAM_VSS)
            ped = _pct(diag, 0x49)
            thr = _pct(diag, 0x11)
            tim = _timing(diag)
            lam = _lambda(diag)
            volt = _pid(diag, 0x42, 2)
            v = (volt / 1000) if volt is not None else float("nan")
            if v_base is None and v == v and not clutch:
                v_base = v
            if clutch and rpm is not None:
                max_rpm = max(max_rpm, rpm)
            elif not clutch:
                max_rpm = 0.0
            active, why = gate_eval(cfg, clutch, app, rpm, vss)
            if active and method == 0:
                hint = "発動中(遅角): 点火°がfloor方向へ下がれば効いている"
            elif active and v_base and v == v and v < v_base - 0.8:
                hint = "発動中(カット) ⚠電圧ドロップ=発火停止の疑い→即アクセル/クラッチ離!"
            elif active:
                hint = "発動中(カット): 回転頭打ち(max踏R)・点火°不変が正常・λ乱れ・電圧維持"
            else:
                hint = f"不発: {why}"
            print(f"  {t % 1000:6.1f} {('踏' if clutch else '離'):>4} {_num(app):4.0f} {_num(ped):5.0f} "
                  f"{_num(thr):4.0f} {_num(rpm):6.0f} {max_rpm:6.0f} {_num(tim):5.1f} {_num(lam):5.2f} {v:6.2f}  {hint}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n終了。")
    finally:
        close_bus(bus)


if __name__ == "__main__":
    main()
