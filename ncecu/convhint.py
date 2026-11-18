"""編集の補助に、説明欄へ出す換算(カウント→秒、増量%→λ)。2026-11-16 の逆解析で分かった単位。

- 電動ファンのタイマ: 値はカウント。1 カウントの時間は OS のタスク周期から求めた
  (CMT1 の 1ms 割り込み → 5ms ごとのメッセージ → 5 本のサブタスクを順に回すので 25ms。
   アフタークーリングのタイマはその 4 回に 1 回 = 100ms で減る)。1ms 刻みと 25ms のサブタスクは
   2026-11-17 に実車で確認(キーON・エンジン停止。10ms ごとの CAN フレームと ECU のカウンタを比較)。
   ファンが実際に入り切りする時間は測っていない。
- Fuel Target CL - Base: 値は理論空燃比からの燃料増量%。ほかの増量項と合計して
  目標λ = 100 / (100 + Σ%) にする(0x4B5B0)。ここではほかの項を 0 とした λ を出す。
水温しきい値の A/D 値は ncecu/ectcount.py が扱う(ここでは扱わない)。
"""
from __future__ import annotations

# 表の名前 -> 1 カウントの秒数
TICK_S = {
    "Fan Speed Transition - Delay": 0.025,
    "After Cooling - Low Speed Fan Timer": 0.1,
    "After Cooling - Primary Med Speed Fan Timer": 0.1,
    "After Cooling - Secondary Med Speed Fan Timer": 0.1,
    "After Cooling - High Speed Fan Timer": 0.1,
}
LAMBDA_TABLES = {"Fuel Target CL - Base (Lambda)"}


def applies(name: str) -> bool:
    return name in TICK_S or name in LAMBDA_TABLES


def count_to_s(name: str, count: float) -> float:
    return count * TICK_S[name]


def s_to_count(name: str, seconds: float) -> int:
    return int(round(seconds / TICK_S[name]))


def pct_to_lambda(pct: float) -> float:
    """増量% → λ(ほかの増量項を 0 とした場合)"""
    return 100.0 / (100.0 + pct)


def lambda_to_pct(lam: float) -> float:
    return 100.0 / lam - 100.0


def _nums(vals):
    return [v for v in vals if isinstance(v, (int, float)) and v == v]


def describe(name: str, vals, lang: str = "ja") -> str:
    vals = _nums(vals)
    if not vals:
        return ""
    en = lang == "en"
    if name in TICK_S:
        tick = TICK_S[name]
        ms = "%g ms" % (tick * 1000)
        uniq = sorted(set(vals))
        cur = " / ".join("%g = %.1f %s" % (v, v * tick, "s" if en else "秒") for v in uniq[:6])
        if len(uniq) > 6:
            cur += " …"
        if en:
            return ("● Conversion: 1 count = %s (OS task period; the 1 ms tick and 25 ms sub-task were confirmed on "
                    "the car, the fan timing itself was not timed). Now: %s. "
                    "count = seconds / %g." % (ms, cur, tick))
        return ("● 換算: 1 カウント = %s(OS のタスク周期。1ms 刻みと 25ms のサブタスクは実車で確認、"
                "ファンの入り切りの時間そのものは未計測)。いまの値: %s。"
                "カウント = 秒 ÷ %g。" % (ms, cur, tick))
    if name in LAMBDA_TABLES:
        lo, hi = min(vals), max(vals)
        ex = "  ".join("%g%%→λ%.4f" % (p, pct_to_lambda(p)) for p in (0.25, 0.5, 1.0, 1.5))
        if en:
            return ("● Conversion: values are enrichment %% over stoich; target lambda = 100 / (100 + sum of terms). "
                    "With the other terms at 0: min %.3f%% -> lambda %.4f, max %.3f%% -> lambda %.4f.  %s" %
                    (lo, pct_to_lambda(lo), hi, pct_to_lambda(hi), ex))
        return ("● 換算: 値は理論空燃比からの増量%%。目標λ = 100 ÷ (100 + 増量項の合計)。ほかの項を 0 とすると "
                "最小 %.3f%% → λ%.4f、最大 %.3f%% → λ%.4f。  %s" %
                (lo, pct_to_lambda(lo), hi, pct_to_lambda(hi), ex))
    return ""
