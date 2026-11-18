"""水温センサの A/D 値 ⇔ 水温(℃) の換算（電動ファンの水温しきい値の編集補助）。

電動ファン制御（Engine Fan Control）の水温しきい値 10 表は、℃ ではなく
**水温センサ電圧の 10 ビット A/D 値**で持たれている（CAL LFG7EG を逆アセンブルして確認）。

- 比較相手は RAM `0xFFFF710E` ＝ 水温の A/D ワード（`0xFFFF4CAC`）を 6 ビット右シフトした値（0〜1023）。
- 電圧 [V] ＝ A/D 値 × 5 / 1024。水温は同じ A/D ワードから `ECT Scaling - Voltage to ECT`
  （`0xB8258`、軸 `0xB81BC`）の直線補間で求めている（`0x87E8`）。
- 水温センサは NTC（高温ほど電圧が低い）なので、**値が大きいほど低い水温**を表す。
- 判定は「A/D 値 ≦ 作動しきい値」でフラグ ON、「A/D 値 ＞ 停止しきい値」でフラグ OFF
  （`0x98F9E`＝走行中の中速/高速、`0x99278`＝アフタークーリングの低速/中速/高速）。

ROM の曲線をそのまま使って換算するので、曲線を編集した ROM でも ECU と同じ結果になる。
"""
from __future__ import annotations

ADC_FULL = 1024          # 10 ビット
ADC_VREF = 5.0           # A/D 基準電圧 [V]（ECU の水温計算と同じ 5/65536 × 16 ビット値）
CURVE_TABLE = "ECT Scaling - Voltage to ECT"

# 表名 -> (段, 種別)。種別 "on"＝A/D 値がこの値以下でフラグ ON、"off"＝この値を超えるとフラグ OFF。
COUNT_TABLES = {
    "Fan Mid Speed - ECT Activation Threshold | AC Off": ("mid", "on"),
    "Fan Mid Speed - ECT Deactivation Threshold | AC Off": ("mid", "off"),
    "Fan High Speed - ECT Activation Threshold | AC Off": ("high", "on"),
    "Fan High Speed - ECT Deactivation Threshold | AC Off": ("high", "off"),
    "After Cooling - Low Speed Fan Enable - Estimated ECT Threshold": ("ac_low", "on"),
    "After Cooling - Low Speed Fan Disable - Estimated ECT Threshold": ("ac_low", "off"),
    "After Cooling - Med Speed Fan Enable - Estimated ECT Threshold": ("ac_mid", "on"),
    "After Cooling - Med Speed Fan Disable - Estimated ECT Threshold": ("ac_mid", "off"),
    "After Cooling - High Speed Fan Enable - Estimated ECT Threshold": ("ac_high", "on"),
    "After Cooling - High Speed Fan Disable - Estimated ECT Threshold": ("ac_high", "off"),
}
UNIT = "A/D"

_STAGE = {
    "mid": ("中速", "mid speed"),
    "high": ("高速", "high speed"),
    "ac_low": ("アフタークーリング低速", "after-cooling low"),
    "ac_mid": ("アフタークーリング中速", "after-cooling mid"),
    "ac_high": ("アフタークーリング高速", "after-cooling high"),
}
# 目安表に出す水温 [℃]
REF_TEMPS = (80, 85, 90, 95, 100, 105, 110)


def is_count_table(name: str) -> bool:
    """この表の値が水温センサの A/D 値（℃ではない）なら True。"""
    return (name or "").strip() in COUNT_TABLES


def role(name: str):
    """(段, 種別) を返す。対象外は None。"""
    return COUNT_TABLES.get((name or "").strip())


def partner_name(name: str):
    """作動側⇔停止側の相方の表名（同じ段の反対側）。対象外は None。"""
    r = role(name)
    if r is None:
        return None
    for other, rr in COUNT_TABLES.items():
        if rr[0] == r[0] and rr[1] != r[1]:
            return other
    return None


def count_to_volt(count: float) -> float:
    return float(count) * ADC_VREF / ADC_FULL


def volt_to_degc(volt: float, curve) -> float:
    """ECU と同じ直線補間（範囲外は端の値）。curve=(電圧の昇順リスト, 水温リスト)。"""
    xs, ys = curve
    if volt <= xs[0]:
        return ys[0]
    if volt >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= volt <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            if span <= 0:
                return ys[i]
            return ys[i] + (volt - xs[i]) / span * (ys[i + 1] - ys[i])
    return ys[-1]


def count_to_degc(count: float, curve) -> float:
    return volt_to_degc(count_to_volt(count), curve)


def degc_to_count(temp: float, curve) -> int:
    """水温 temp[℃] にいちばん近い A/D 値（0〜1023）。"""
    best, err = 0, None
    for c in range(ADC_FULL):
        e = abs(count_to_degc(c, curve) - temp)
        if err is None or e < err:
            best, err = c, e
    return best


def curve_from(rom, romdef):
    """開いている ROM から水温の変換曲線 (電圧[], 水温[]) を読む。無ければ None。"""
    try:
        t = next(t for t in romdef.tables if t.name == CURVE_TABLE)
        ax = t.x_axis or t.y_axis
        if ax is None:
            return None
        xs = [float(v) for v in rom.read_axis(ax)]
        ys = [float(v) for row in rom.read_table(t) for v in row]
        n = min(len(xs), len(ys))
        xs, ys = xs[:n], ys[:n]
        if n < 2 or any(xs[i] >= xs[i + 1] for i in range(n - 1)):
            return None                      # 軸が昇順でない＝換算できない
        return xs, ys
    except Exception:
        return None


def switch_temp(name: str, value: float, curve):
    """しきい値 value が実際に切り替わる水温 [℃] と向きを返す: (水温, "on"/"off")。

    "on"  … A/D 値 ≦ value で ON ＝ 水温がこの値以上で作動
    "off" … A/D 値 ＞ value で OFF ＝ A/D 値 value+1 の水温以下で停止
    """
    r = role(name)
    if r is None:
        return None
    kind = r[1]
    c = float(value) if kind == "on" else float(value) + 1.0
    return count_to_degc(c, curve), kind


def _floats(values):
    out = []
    for v in values or ():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:
            out.append(f)
    return out


def pair_problem(name: str, values, partner_values) -> bool:
    """作動値が停止値以上（＝入り切りの幅が無い）なら True。相方が読めないときは False。"""
    r = role(name)
    mine, other = _floats(values), _floats(partner_values)
    if r is None or not mine or not other:
        return False
    on, off = (mine, other) if r[1] == "on" else (other, mine)
    return any(a >= b for a, b in zip(on, off))


def describe(name: str, values, curve, lang: str = "ja", partner_values=None) -> str:
    """エディタの説明欄に出す換算の説明（現在値の換算＋目安表）。対象外は空文字。

    partner_values に相方（作動⇔停止）の表の値を渡すと、幅が無いときに警告を付ける。"""
    r = role(name)
    if r is None:
        return ""
    ja = lang != "en"
    stage = _STAGE[r[0]][0 if ja else 1]
    kind = r[1]
    if curve is None:
        return ("● 換算: この値は ℃ ではなく水温センサ電圧の A/D 値（電圧 = 値×5/1024）。"
                "水温の変換曲線（ECT Scaling）が読めないため ℃ 換算は表示できません。"
                if ja else
                "● Conversion: this value is an ECT-sensor A/D count (volts = value×5/1024), not °C. "
                "The ECT Scaling curve could not be read, so no °C conversion is shown.")
    uniq = []
    for f in _floats(values):
        if f not in uniq:
            uniq.append(f)
    cur = []
    for f in uniq[:4]:
        volt = count_to_volt(f)
        temp, _k = switch_temp(name, f, curve)
        if ja:
            tail = (f"水温 {temp:.1f}℃ 以上で{stage}ON" if kind == "on"
                    else f"水温 {temp:.1f}℃ 以下で{stage}OFF")
        else:
            tail = (f"{stage} ON at {temp:.1f}°C or above" if kind == "on"
                    else f"{stage} OFF at {temp:.1f}°C or below")
        cur.append(f"{f:.0f} → {volt:.3f}V → {tail}")
    ref = " / ".join(f"{t}℃≈{degc_to_count(t, curve)}" if ja else f"{t}°C≈{degc_to_count(t, curve)}"
                     for t in REF_TEMPS)
    step = abs(count_to_degc(100, curve) - count_to_degc(101, curve))
    if ja:
        lines = [
            "● 換算（この値は ℃ ではなく水温センサ電圧の A/D 値。値が大きいほど低い水温）",
            "　現在値: " + " ／ ".join(cur),
            "　式: 電圧[V] = 値 × 5 ÷ 1024 → 水温は「ECT Scaling - Voltage to ECT」の曲線で換算（ECU と同じ直線補間）",
            f"　目安（水温 ≈ 入れる値）: {ref}　※1 は約 {step:.1f}℃",
            ("　作動側は「A/D 値 ≦ この値」で ON。停止側（Deactivation / Disable）より小さい値にする。"
             if kind == "on" else
             "　停止側は「A/D 値 ＞ この値」で OFF。作動側（Activation / Enable）より大きい値にする（差が入り切りの幅）。"),
        ]
    else:
        lines = [
            "● Conversion (the value is an ECT-sensor A/D count, not °C; a larger value means a LOWER temperature)",
            "  Now: " + " / ".join(cur),
            "  Formula: volts = value × 5 ÷ 1024 → °C through the \"ECT Scaling - Voltage to ECT\" curve "
            "(same linear interpolation as the ECU)",
            f"  Guide (temperature ≈ value to enter): {ref}   (1 count ≈ {step:.1f}°C)",
            ("  ON side: flag sets when count ≤ this value. Keep it below the OFF-side value."
             if kind == "on" else
             "  OFF side: flag clears when count > this value. Keep it above the ON-side value (the gap is the hysteresis)."),
        ]
    if pair_problem(name, values, partner_values):
        lines.append("　⚠ 作動側の値が停止側の値以上になっています。入り切りの幅が無くなり、リレーが細かく入り切りします。"
                     if ja else
                     "  WARNING: the ON-side value is not below the OFF-side value: no hysteresis, the relay will chatter.")
    return "\n".join(lines)
