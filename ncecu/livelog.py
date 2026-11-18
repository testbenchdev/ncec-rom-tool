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
    # ★負荷は2種類ある。マップの負荷軸(LOAD_6F44。この ROM での入力 RAM は 0xFFFF6EC8)と一致するのは 0x43 絶対負荷。
    #   根拠: Knock Listen の負荷しきい値 0.40(入)/0.353(出=0.4-ヒス0.047) が、ログ上 0x43 の
    #   40%/36% 通過と一致(0x04 計算負荷はその時 52%/44% で不一致)。0x04 は別ロール(CALCLOAD)にして
    #   MAP追従(LOAD)へ混ざらないようにした(以前は同じLOADロールで、●が約1秒ごとに行ずれしていた)。
    0x04: Pid(0x04, "Calc Load", 1, "%", "CALCLOAD", lambda d: _u8(d) * 100 / 255),
    0x43: Pid(0x43, "Abs Load", 2, "%", "LOAD", lambda d: _u16(d) * 100 / 255),
    0x05: Pid(0x05, "ECT", 1, "C", "ECT", lambda d: _u8(d) - 40),
    0x0F: Pid(0x0F, "IAT", 1, "C", "IAT", lambda d: _u8(d) - 40),
    0x0B: Pid(0x0B, "MAP", 1, "kPa", "MAP", lambda d: _u8(d)),
    0x10: Pid(0x10, "MAF", 2, "g/s", "MAF", lambda d: _u16(d) / 100),
    0x11: Pid(0x11, "Throttle", 1, "%", "TP", lambda d: _u8(d) * 100 / 255),
    0x45: Pid(0x45, "Rel Throttle", 1, "%", "TPREL", lambda d: _u8(d) * 100 / 255),
    # APP D/E はペダルの2系統センサ(同じ踏み量の重複)。どちらも生値(全閉≒31%/20%)で、マップの
    #   APP軸(0-100%正規化)とは単位が違う。MAP追従の APP ロールは roles_from_pids() で 0x49 を正規化して作る。
    0x49: Pid(0x49, "APP D", 1, "%", "APPRAW", lambda d: _u8(d) * 100 / 255),
    0x4A: Pid(0x4A, "APP E", 1, "%", "APPRAW2", lambda d: _u8(d) * 100 / 255),
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
    0x47: Pid(0x47, "Abs Thr B", 1, "%", "TPB", lambda d: _u8(d) * 100 / 255),
    0x4C: Pid(0x4C, "Cmd Thr", 1, "%", "TPCMD", lambda d: _u8(d) * 100 / 255),
    0x1F: Pid(0x1F, "Run Time", 2, "s", "RUNTIME", lambda d: _u16(d)),
    0x2C: Pid(0x2C, "Cmd EGR", 1, "%", "EGR", lambda d: _u8(d) * 100 / 255),
    0x2E: Pid(0x2E, "Cmd Evap", 1, "%", "EVAP", lambda d: _u8(d) * 100 / 255),
}

# エディタ標準表示に使う既定PID(順序は表示順)
DEFAULT_PIDS = [0x0C, 0x43, 0x04, 0x0B, 0x10, 0x11, 0x0E, 0x0D, 0x05, 0x0F, 0x42]
# ライブパネル2行目(センサ/トリム系)
EXTRA_PIDS = [0x49, 0x4A, 0x06, 0x07, 0x15, 0x34, 0x44, 0x33, 0x2C, 0x2E, 0x1F]

# ---- 読み出し間隔(間引き) ----
# 間隔[秒]の特別値: 0=毎回 / 負(IGNORE)=無視(その信号は読まない)。
IGNORE = -1.0
# 間引きの選択肢。エディタの「ライブPID間引き」ダイアログ(PID・ライブRAMの両方)と、
# ダッシュボードの「更新周期」メニューで共通に使う(以前は場所ごとにリストが違っていた)。
INTERVAL_CHOICES = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, IGNORE]


def is_ignored(seconds) -> bool:
    """間隔が「無視」(読まない)か。"""
    return seconds is not None and seconds < 0


def interval_label(seconds, ja: bool = True) -> str:
    """間隔の表示名: 毎回 / 0.1s … 10s / 無視。"""
    if is_ignored(seconds):
        return "無視" if ja else "Ignore"
    if not seconds:
        return "毎回" if ja else "Every"
    return f"{seconds:g}s"


def snap_interval(seconds) -> float:
    """任意の秒数を INTERVAL_CHOICES の最も近い値へ丸める(負は IGNORE)。
    設定ファイルにリスト外の値(例 0.3)が残っていても、選択肢は常に同じ並びで出せる。"""
    try:
        v = float(seconds)
    except (TypeError, ValueError):
        return 0.0
    if v < 0:
        return IGNORE
    return min((c for c in INTERVAL_CHOICES if c >= 0), key=lambda c: abs(c - v))


# ---- MAP追従(現在セルの●)に使うロールと、その供給元PID ----
# 1ロール=1PID。表示中マップの軸がこのロールなら、間引き設定が「無視」や遅い値でも
# FOLLOW_MAX_INTERVAL 以内で必ず読む(LiveReader.set_follow_roles)。
FOLLOW_PID = {"RPM": 0x0C, "LOAD": 0x43, "ECT": 0x05, "IAT": 0x0F, "APP": 0x49,
              "TP": 0x11, "MAP": 0x0B, "MAF": 0x10, "VSS": 0x0D}
FOLLOW_MAX_INTERVAL = 0.2

# ライブRAM(Mode23)を1周期に読むブロック数の上限。RAMは隣接番地以外まとめられず 1ブロック=1往復
# かかるので、無制限だとRAMのch数に比例して全体の周期(=回転・負荷の更新)が遅くなる。
RAM_READS_PER_CYCLE = 2

# アクセル開度の正規化(MAP追従用)。PID 0x49 は生値で全閉≒31.4%/全開≒72.3%(実車ログ10800点で、
# ECU内部の正規化APP 0xFFFF56C8 と ほぼ直線: 内部APP ≒ (PID−31.4)×2.445)。マップのAPP軸は0-100%。
# ※個体・学習値で数%ずれうる近似。ダッシュボード/ログの 0x49 は生値のまま。
APP_REST, APP_FULL = 31.4, 72.3


def app_normalized(app_d_pct: float) -> float:
    """PID 0x49(生値%) → ECU内部相当の正規化アクセル開度[0-100%]。"""
    return max(0.0, min(100.0, (app_d_pct - APP_REST) * 100.0 / (APP_FULL - APP_REST)))


def roles_from_pids(by_pid: dict) -> dict:
    """{pid:値} → {ロール:値}。MAP追従用の APP(正規化)を付け加える。ライブと再生で共通。"""
    roles = {PIDS[p].role: v for p, v in by_pid.items() if p in PIDS}
    if 0x49 in by_pid:
        roles["APP"] = app_normalized(by_pid[0x49])
    return roles

# ライブRAM読み出し(Mode23有効化ROMが前提)の既定チャンネル。
# ch は合成キー(0x100台=実PIDと衝突しない)。role はダッシュボード/エディタ表示用。
# ⚠ ECU側でMode23有効化パッチが当たっていないと読めない(未有効化なら自動で停止)。
# ノック系の番地は純正ノック制御(Proto-Knock)のRE結果。RAMブロック 0xFFFF7C20-7CD0。
#   ベンチROMと実車ROM(同CAL LFG7EG)で該当コードは完全一致=実車に転用可。
# ★確定版(2026-11-14 静的RE＋全ログ照合。同日の途中説明「低負荷ゲート」「イネーブル0xFFFF4E14が非活性」は
#   どちらも誤りだったので破棄。詳細 docs/knock_re_ja.md):
#   - 0xFFFF4E14 は「イネーブル」ではなく**ノックセンサの生検出フラグ**。気筒イベントごとのルーチン 0xB32A の末尾
#     (0xB61A-0xB62C)で 4E14 = (今回のノックレベル 0xFFFF4E20 ≥ 適応しきい値 0xFFFF4E58)。しきい値は
#     clamp(平均0xFFFF4E3C + ノイズ0xFFFF4E54 × 倍率0xFFFF4E18)。0xFFFF7E89 はその写し(コード0x52A40)。
#     → 0 = 「ノックを検出していない」。条件待ちのイネーブルではない。
#   - 0xFFFF7C3A は「ノック回数」でも「センチネル」でもなく**始動後の燃焼イベント数(255で飽和)**。
#     コード0x4FE06: エンジン停止ビット(0xFFFF7346 bit7)で0、以後1イベントごと+1(飽和加算0x2478)。
#     ログ実測: 冷間始動ログ(..211638)で 0→1,3,5..と回転数に比例(1300rpmで約43/s=2回/回転)して255へ。
#     他のログは始動後に接続=ずっと255。= 255固定は正常。
#   - ノックイベント 0xFFFF7C3C = (7E89==1) かつ (7C3A ≥ 24 @0xBBCA7)。＝始動直後24燃焼は無視するだけ。
#   - **本物のKR(ノック遅角)= 0xFFFF7C44**(本体は0xFFFF7C20、7C44はその1イベント遅れの写し。0x4FCB8/0x4FD54)。
#     ログで cal と完全一致: +1.7(KR Increment 0xBBCAC)で立ち、−0.17/イベント(Listen Active 0xBBF98)、
#     負荷<40%では −0.3515/イベント(Listen Inactive 0xBC0FC)で減衰。全ログで3回作動(1100-1330rpm・負荷52-67%)。
#   - 旧「KR」0xFFFF7C4C = 表 0xBBDF0「KR Accumulator - Minimum KR for Accumulation」の引き値(3.867/4.57…)。
#     KRではない(0x4FF2E-0x4FF3C)。0xFFFF7C60 もノック強度ではない(未確認の別項。ノックレベルは 0xFFFF4E20)。
#   - 全開ログでKR=0だったのは「その場面でセンサがしきい値を超えなかった」＝ノック未検出、が正しい読み。
#   余裕度を見たいときは ram_reads.json に 0xFFFF4E20(f32 ノックレベル) と 0xFFFF4E58(f32 しきい値) を足す。
IPW_CH = 0x109       # 噴射パルス幅(0xFFFF7380, ms)。実走ログで確定(下記コメント)
DUTY_CH = 0x10A      # 開弁率[%]＝派生計算(IPW×RPM/1200)。RAM読み出しではなく _run で算出
GEAR_CH = 0x10D      # 現在ギア(1-6)＝派生。r=RPM/車速 を校正済み6帯へ最近傍割当(RAM読みではない)。
#   純正ECUにクリーンなギアバイトは無く(候補0xFFFF7060等は未使用プールのパディング誤検出だった。
#   2026-11-03 実走sweepで全候補が不変=確定)、代わりに r で判定する。各帯の境界は幾何平均。
#   r実測(1-6速)=135/82/59/42.5/36/30 → 境界=105/70/50/39/33。クラッチ接続・車速≥8km/hで有効、他は0。
GEAR_BOUNDS = ((105.0, 1), (70.0, 2), (50.0, 3), (39.0, 4), (33.0, 5))  # これ未満は6速
RAM_CHANNELS = [
    # 0xFFFF6FCC は実車確認の結果「クラッチ」ではなく減速ステータス(Decel Status)だった。
    #   0=駆動中(ギア入・アクセルON) / 1=減速コースト・ニュートラル・アイドル・停止。
    #   定義「Decel Transition … Hold Decel Status | In-Gear」に対応。旧role名 CLUTCH は誤り。
    {"ch": 0x101, "addr": 0xFFFF6FCC, "type": "u8", "role": "DECEL",
     "name": "減速ステータス", "unit": "", "interval": 0.2},
    {"ch": 0x103, "addr": 0xFFFF777C, "type": "f32", "role": "EGT",
     "name": "排気温(触媒推定)", "unit": "°C", "interval": 2.0},
    # --- ノック(Proto-Knock)。2026-11-14 確定版(上のコメント参照)。監視は「レベル＋KR」の2本に集約 ---
    # ★ノックレベル = ノックセンサの強さ(float)。気筒イベントごとに算出され、しきい値0xFFFF4E58 を超えると検出。
    #   連続値なので「どれだけ近いか」が見える。内部スケール(単位無し)なので実車で見てスケール調整すること。
    {"ch": 0x114, "addr": 0xFFFF4E20, "type": "f32", "role": "KNOCKLVL",
     "name": "ノックレベル", "unit": "", "interval": 0.2},
    # ★KR(ノック遅角)。0なら遅角無し、>0で遅角作動(=リタード)。+1.7で立ち 0.17/0.3515ずつ減衰(ログで確認済み)。
    #   短い(約0.25秒)ので速めに読む。遅角が入ったかどうかはこの1本で分かる(別途の検出フラグは不要)。
    {"ch": 0x106, "addr": 0xFFFF7C44, "type": "f32", "role": "KR",
     "name": "KR(ノック遅角)", "unit": "°", "interval": 0.2},
    # ※以下はライブ監視から外した(ユーザー指示「レベルとリタードで十分」)。意味づけは docs/knock_re_ja.md に残す。
    #   見たいときは ram_reads.json に追加可:
    #   - ノックイベント 0xFFFF7C3C(u8,0/1)=検出 / 生検出 0xFFFF7E89(u8,0/1)=レベル≥しきい値(=KRが立つかの元)
    #   - しきい値 0xFFFF4E58(f32)=レベルと対にすると余裕度が出る
    #   - 始動後燃焼カウント 0xFFFF7C3A(u8,すぐ255飽和) / 0xFFFF7C60(f32,未確認) / KR積算最小 0xFFFF7C4C(f32)
    # クラッチスイッチ(実車のRAM差分で特定・ROM参照14箇所の本家入力)。0=離す/1=踏む。
    {"ch": 0x107, "addr": 0xFFFF7100, "type": "u8", "role": "CLUTCH",
     "name": "クラッチ", "unit": "", "interval": 0.2},
    # ブレーキスイッチ(実車 ram_diff で特定・クラッチの隣=同じ駆動系入力モジュール)。0=離す/1=踏む。
    #   NCはDBW車のためブレーキSWが2系統(ブレーキ灯SW＋クルーズ/DBW冗長SW)。ECUは両者を照合する。
    #   0xFFFF70EC=本命, 0xFFFF70EE=第2系統(冗長)。0xFFFF70EFは上の反転照合コピー。
    #   オートブリッピングのトリガ(ブレーキ＋クラッチ同時)はこの2本の AND(両方1)で判定する方針。
    {"ch": 0x10B, "addr": 0xFFFF70EC, "type": "u8", "role": "BRAKE",
     "name": "ブレーキ", "unit": "", "interval": 0.2},
    # ブレーキ2は本命(0xFFFF70EC)と同じ踏み込みの重複 → 既定は「無視」(間引き設定でいつでも戻せる)。
    {"ch": 0x10C, "addr": 0xFFFF70EE, "type": "u8", "role": "BRAKE2",
     "name": "ブレーキ2(冗長)", "unit": "", "interval": IGNORE},
    # フラットシフトのゲートが読むアクセル開度(0xFFFF56C8, f32=値がそのまま%)。ncecu/flatshift.py の
    #   RAM_APP＝この番地。APP閾値(既定80%)が実走WOTで成立するかの校正・発動確認に使う(＝フラットシフト用)。
    #   ★OBDのペダル(PID0x49/0x4A)とは別物(ECU内部の加工値)。停車空ぶかしで両者がズレた実績あり。
    {"ch": 0x108, "addr": 0xFFFF56C8, "type": "f32", "role": "GAPP",
     "name": "ゲートAPP(フラットシフト)", "unit": "%", "interval": 0.2},
    # ※旧IPW候補 0xFFFF7498 は実車ログで否定（0.47〜0.62でほぼ一定・負荷と負相関＝デッドタイム等）。
    # 噴射パルス幅(IPW) = 0xFFFF7380。2026-11-02の実走ログ(6408rec/193s)で確定：
    #   ・惰行燃料カットで 0.000ms に落ちる(＝インジェクタ停止)。負荷/MAP/MAFと強い正相関(r≒0.97)、RPMとは弱(0.19)。
    #   ・アイドル約2ms／全開約11ms と物理的に妥当。計算連鎖 0xFFFF7374(要求ベース)→×補正[0xFFFF7550/100]→0xFFFF7380(最終)。
    #   ・不採用: 0xFFFF7374=カット前の要求ベースで0に落ちない(最小0.85)。0xFFFF7378/737C=7380のパイプライン中間値(定常で同一)。
    #   開弁率[%]は DUTY_CH(派生) として _run で IPW×RPM/1200 から算出(RAM読みではない)。
    {"ch": IPW_CH, "addr": 0xFFFF7380, "type": "f32", "role": "IPW",
     "name": "噴射パルス幅", "unit": "ms", "interval": 0.1},
]


# PIDごとの既定の問い合わせ間隔[秒]。0(またはこの表に無いPID)=毎周期取得。IGNORE=読まない。
# Mode01 は1要求=最大6PID。「毎回」を6個に収めると1周期=1要求になり最速。
#   毎回(6個=1要求): 0x0C 回転 / 0x43 絶対負荷 / 0x11 スロットル / 0x49 アクセル / 0x0E 点火 / 0x0B MAP
#     ＝MAP追従の主役(回転・負荷・スロットル・アクセル)＋チューニングで常に見る点火・MAP。
#   0.2秒: MAF と AFR(実測)。0.2秒ごとに2本目の要求が1回出て、空き4枠に遅い項目が相乗りする
#     (遅い項目のための追加要求は発生しない)。
#   無視: 0x04 計算負荷(0x43 と重複。マップの負荷軸は 0x43) / 0x4A APP E(0x49 と重複)。
# 以前は「毎回」が7個(ユーザ設定で 0x49 を毎回にした場合)で毎周期2要求になっていた。
DEFAULT_PID_INTERVALS: dict[int, float] = {
    0x10: 0.2, 0x34: 0.2,                                   # MAF・AFR実測
    0x0D: 0.5, 0x45: 0.5,                                   # 車速(現在ギアの算出にも使う)・相対スロットル
    0x44: 1.0, 0x06: 1.0, 0x07: 1.0,                        # AFR目標・STFT・LTFT
    0x2C: 1.0, 0x47: 1.0, 0x4C: 1.0,                        # EGR・絶対スロB・指令スロ
    0x05: 2.0, 0x0F: 2.0, 0x15: 2.0, 0x2E: 2.0,            # 水温・吸気温・O2・Evap
    0x42: 5.0, 0x33: 5.0, 0x1F: 5.0,                        # 電圧・大気圧・経過時間
    0x04: IGNORE, 0x4A: IGNORE,                             # 重複(計算負荷・APP E)
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
                 pid_intervals=None, decimate=True, ram_reads=None,
                 rx_filter=True, rx_id=0x7E8, ram_per_cycle=RAM_READS_PER_CYCLE):
        self.pid_ids = list(pids) if pids else list(DEFAULT_PIDS) + list(EXTRA_PIDS)
        # ライブRAM読み出し(Mode23)。各要素 {ch,addr,type,role,name,unit,interval}。
        self.ram_reads = [dict(c) for c in (ram_reads or [])]
        self._ram_last: dict[int, float] = {}   # ch -> 最後に読んだ時刻
        self._ram_groups = None                  # 隣接RAMをまとめ読みするブロック群(遅延生成)
        self.ram_per_cycle = ram_per_cycle       # 1周期に読むRAMブロック数の上限(0/None=無制限)
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
        # MAP追従に必要なPID(表示中マップの軸)。間引き設定より優先して読む。
        self._follow: set[int] = set()
        self.read_dtc = read_dtc
        self._dtc_interval = dtc_interval
        self._last_dtc = 0.0
        self.dtcs: list[tuple[str, str]] = []
        self._req_q: list[dict] = []   # ワンオフ診断要求(DTCクリア等)をポーリングスレッドで実行
        self.interval = interval
        # 応答ID(0x7E8)だけ通す python-can 受信フィルタ。既定ON。
        # gs_usb はHWフィルタ非対応なので全フレームが一旦USBを越えて届くが、python-can が
        # C側の recv ループで非マッチ(自局TXエコー=0x7E0、走行中は車体CAN)をまとめて捨てる
        # ため、IsoTp が Python 側で1フレームずつ recv し直す往復が減り体感が速くなる
        # (机上 約10Hz→約20Hz)。フィルタOFFだと echo/ノイズ分だけ recv 往復が増えて半減。
        # ※以前フィルタ付き flush のドレイン漏れで更新レートが徐々に低下する不具合があったが、
        #   isotp.flush() をハードドレイン化(ドレイン中だけフィルタ一時解除で空まで読み切り)して
        #   解消済み=フィルタONでも消し残し(漸減)は起きない。
        self.rx_filter = rx_filter
        self._rx_id = rx_id
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
        """PIDごとの問い合わせ間隔[秒]を設定(0=毎回 / 負=無視)。UIから変更する用。"""
        seconds = float(seconds)
        self._intervals[pid] = IGNORE if seconds < 0 else seconds
        if seconds < 0 and pid not in self._follow:
            self._forget(pid)

    def set_ram_interval(self, ch: int, seconds: float) -> None:
        """ライブRAM(合成ch)の読み出し間隔[秒]を設定(負=無視)。まとめ読みブロックを作り直す。"""
        seconds = float(seconds)
        for c in self.ram_reads:
            if c.get("ch") == ch:
                c["interval"] = IGNORE if seconds < 0 else seconds
        self._ram_last.pop(ch, None)
        self._ram_groups = None
        if seconds < 0:
            self._forget(ch)

    def set_follow_roles(self, roles) -> None:
        """MAP追従に使うロール(表示中マップの軸)を伝える。該当PIDは間引き設定が「無視」や
        遅い値でも FOLLOW_MAX_INTERVAL 以内で読む。空集合で解除。"""
        self._follow = {FOLLOW_PID[r] for r in (roles or ()) if r in FOLLOW_PID}

    def _forget(self, ch: int) -> None:
        """無視にした信号の直前値を消す(止まった値が表示/ログに残り続けないように)。"""
        with self._lock:
            self.by_pid.pop(ch, None)
            spec = PIDS.get(ch)
            if spec is not None:
                self.values.pop(spec.role, None)
                if ch == 0x49:
                    self.values.pop("APP", None)
            for c in self.ram_reads:
                if c.get("ch") == ch:
                    self.values.pop(c.get("role"), None)
                    self.ram_values.pop(c.get("role"), None)

    def _eff_interval(self, pid: int) -> float:
        """このPIDの実効間隔。MAP追従に必要なPIDは無視/遅い設定を上書きする。"""
        iv = self._intervals.get(pid, 0.0)
        if pid in self._follow:
            return FOLLOW_MAX_INTERVAL if iv < 0 else min(iv, FOLLOW_MAX_INTERVAL)
        return iv

    def _due_pids(self, now: float) -> list[int]:
        """この周期で問い合わせるPIDの並びを返す。
        - interval が 0 のPID(毎回)と、前回から interval 以上経過したPIDを対象にする。
        - 6個単位の要求枠に空きがあれば、まだ期限の来ていないPIDを“次に期限が近い順”で
          詰める(ついで取得。要求回数は増やさない)。"""
        due, rest = [], []
        for p in self.pid_ids:
            iv = self._eff_interval(p)
            if iv < 0:
                continue                      # 無視=読まない(ついで取得にも入れない)
            if iv == 0 or (now - self._last_poll.get(p, -1e9)) >= iv:
                due.append(p)
            else:
                rest.append(p)
        cap = ((len(due) + 5) // 6) * 6
        spare = cap - len(due)
        if spare > 0 and rest:
            rest.sort(key=lambda p: self._last_poll.get(p, -1e9) + self._eff_interval(p))
            due += rest[:spare]
        return due

    def start(self):
        from .canbus import open_bus as _ob
        from .diag import DiagClient
        from .isotp import IsoTp
        opener = self._open_bus or _ob
        flt = ([{"can_id": self._rx_id, "can_mask": 0x7FF, "extended": False}]
               if self.rx_filter else None)
        if flt is not None:
            try:
                self._bus = opener(can_filters=flt)
            except TypeError:        # can_filters 非対応の opener(テストの仮想バス等)
                self._bus = opener()
                flt = None
        else:
            self._bus = opener()
        # flush() は can_filters の有無に関わらずハードドレイン(空まで読み切り)で
        # 自己修復するため、フィルタ別の切替は不要。
        self._diag = DiagClient(IsoTp(self._bus, rx_id=self._rx_id))
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

            # ワンオフ診断要求(DTCクリア等)を先に処理(PID往復とバスを分離)。
            if self._req_q:
                self._drain_requests()

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
            roles = roles_from_pids(got)

            # --- ライブRAM読み出し(Mode23有効化ROM前提。未有効化なら自動停止) ---
            if self.ram_reads and self.mode23_ok is not False:
                self._poll_ram(got, roles)

            # 開弁率[%]（派生）: IPW[ms]×RPM/1200（4ストローク＝2回転に1噴射）。
            #   IPWとRPMが揃えば毎周期算出し、got/roles に載せてログ・ダッシュボードへ流す。
            _ipw = got.get(IPW_CH, self.by_pid.get(IPW_CH))
            _rpm = got.get(0x0C, self.by_pid.get(0x0C))
            if _ipw is not None and _rpm is not None:
                got[DUTY_CH] = _ipw * _rpm / 1200.0
                roles["DUTY"] = got[DUTY_CH]

            # 現在ギア[1-6]（派生）: r=RPM/車速 を校正済み6帯へ割当（RAM読みではない・読み取りのみ）。
            #   クラッチ接続(0x107==0)かつ車速≥8km/h のときだけ。それ以外(切/停止)は 0=不明。
            _spd = got.get(0x0D, self.by_pid.get(0x0D))
            _cl = got.get(0x107, self.by_pid.get(0x107))
            _g = 0.0
            if _rpm and _spd and _spd >= 8 and (_cl in (0, 0.0, None)):
                _r = _rpm / _spd
                _g = 6.0
                for _bnd, _gn in GEAR_BOUNDS:
                    if _r >= _bnd:
                        _g = float(_gn)
                        break
            got[GEAR_CH] = _g
            roles["GEAR"] = _g

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

    def _drain_requests(self):
        """ポーリングスレッド上でキュー済みのワンオフ診断要求を実行する。"""
        while True:
            with self._lock:
                if not self._req_q:
                    return
                job = self._req_q.pop(0)
            try:
                resp = self._diag.request(job["payload"], timeout=job["timeout"])
                job["result"] = ("ok", resp)
            except Exception as e:  # noqa: BLE001
                job["result"] = ("err", e)
            finally:
                job["ev"].set()

    def submit_request(self, payload, timeout=1.5, wait=4.0):
        """ワンオフ診断要求をポーリングスレッドで実行し結果を返す(バス競合を回避)。
        戻り値 ('ok', resp) / ('err', Exception) / ('timeout', None)。"""
        ev = threading.Event()
        job = {"payload": bytes(payload), "timeout": timeout, "ev": ev, "result": None}
        with self._lock:
            self._req_q.append(job)
        if ev.wait(wait):
            return job["result"]
        return ("timeout", None)

    def clear_dtcs(self):
        """OBD Mode04(DTC消去)をポーリングスレッド経由で送る。成功時は保持DTCを空にし次周期で再読込。"""
        res = self.submit_request(b"\x04", timeout=1.5, wait=4.0)
        if res[0] == "ok" and res[1] and res[1][0] == 0x44:
            with self._lock:
                self.dtcs = []
            self._last_dtc = 0.0
        return res

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
        """期限が来たRAMを Mode23 (23 addr size) で読む(既定セッション・読み取り専用)。

        隣接番地は mode23.group_channels で1ブロックにまとめ、1回の読みで複数chを取得する
        (個別読みの往復を削減してライブ更新レートを上げる)。グループ内のどれか1chでも期限が
        来ていればブロック全体を1回読み、全メンバを直近値として更新する。"""
        from . import mode23
        from .diag import NegativeResponse
        from .isotp import IsoTpError
        now = time.monotonic()
        if self._ram_groups is None:      # 「無視」のchはブロックに入れない(読む範囲も広げない)
            self._ram_groups = mode23.group_channels(
                [c for c in self.ram_reads if not is_ignored(c.get("interval", 0.5))])
        # 期限が来たブロックを「遅れの大きい順」に並べ、1周期あたり ram_per_cycle 個までだけ読む。
        # RAMは1ブロック=1往復なので、全部を毎周期読むとPID(回転・負荷=MAP追従)の更新まで遅くなる。
        # 上限を設けるとPIDの周期は一定に保たれ、RAMは設定間隔を目標にしたベストエフォートになる
        # (読み切れない分は次の周期へ回る。遅れが大きいものから読むので特定のchが飢えることはない)。
        cand = []
        for i, g in enumerate(self._ram_groups):
            late = max(now - self._ram_last.get(c["ch"], -1e9) - max(0.0, c.get("interval", 0.5))
                       for c, _off in g["members"])
            if late >= 0:
                cand.append((late, i))
        cand.sort(reverse=True)
        if self.ram_per_cycle:
            cand = cand[:self.ram_per_cycle]
        for _late, i in cand:
            g = self._ram_groups[i]
            members = g["members"]
            start, size = g["start"], g["size"]
            for c, _off in members:           # 試行時刻を記録(失敗したブロックが枠を占有し続けないように)
                self._ram_last[c["ch"]] = now
            if not mode23.addr_readable(start, size):
                continue
            try:
                resp = self._diag.request(mode23.read_request(start, size), timeout=0.4)
            except NegativeResponse:          # 未有効化なら NRC が返る
                self._ram_nrc += 1
                if self._ram_nrc >= 4:
                    self.mode23_ok = False     # 未有効化と判断してライブRAMを停止
                return
            except (IsoTpError, Exception):   # noqa: BLE001  一時的エラーはスキップ(停止はしない)
                return
            block = mode23.parse_read(resp, size)
            if block is None:
                continue
            for c, off in members:
                typ = c.get("type", "u8")
                n = mode23.type_size(typ)
                try:
                    val = float(mode23.decode(block[off:off + n], typ))
                except Exception:  # noqa: BLE001
                    continue
                val = val * c.get("scale", 1.0) + c.get("offset", 0.0)
                got[c["ch"]] = val
                roles[c["role"]] = val
                self.ram_values[c["role"]] = val
                self._ram_last[c["ch"]] = now
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
