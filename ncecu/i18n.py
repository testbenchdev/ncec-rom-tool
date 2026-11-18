"""カテゴリ名の日本語対訳(LFG7xx 定義の 77 カテゴリ)。

テーブル名は英語のまま(チューニング資料との対応のため)。カテゴリ表示のみ日本語化する。
translate_category() は前後空白を無視して引く。未登録はそのまま返す。
言語は set_language("ja"/"en") で切替。英語モードは定義の原文(英語)を返す。
"""

from . import ectcount

_LANG = "ja"


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if str(lang).lower().startswith("en") else "ja"


def get_language() -> str:
    return _LANG


CATEGORY_JA = {
    "CAN - Inputs and Outputs": "CAN - 入出力",
    "DBW - Throttle Angle Commanded Conversion": "DBW(電子スロットル) - 目標角度変換",
    "DBW - Throttle Duty Delta (Data Integrity)": "DBW - デューティ差分(データ整合性)",
    "DBW - Throttle Duty Desired": "DBW - 目標スロットルデューティ",
    "DBW - Throttle Duty Desired (Data Integrity)": "DBW - 目標デューティ(データ整合性)",
    "DBW - Throttle Duty Limits": "DBW - スロットルデューティ上限",
    "DTC - Activation Flags": "DTC(診断コード) - 有効化フラグ",
    "DTC - Activation Thresholds": "DTC - 有効化しきい値",
    "Emission System - EGR": "排ガス - EGR",
    "Emission System - EVAP": "排ガス - EVAP(蒸発ガス)",
    "Engine Displacement": "エンジン排気量",
    "Engine Fan Control": "エンジンファン制御",
    "Engine Limiters - RPM": "エンジンリミッタ - 回転数(RPM)",
    "Engine Limiters - VSS": "エンジンリミッタ - 車速(VSS)",
    "Engine Load - Limits": "エンジン負荷 - 上限",
    "Engine Load - Scaling": "エンジン負荷 - スケーリング",
    "Engine Sensor - AFS": "エンジンセンサ - 空燃比(AFS)",
    "Engine Sensor - ECT": "エンジンセンサ - 水温(ECT)",
    "Engine Sensor - Flex Fuel": "エンジンセンサ - フレックス燃料",
    "Engine Sensor - IAT": "エンジンセンサ - 吸気温(IAT)",
    "Engine Sensor - KS": "エンジンセンサ - ノックセンサ(KS)",
    "Engine Sensor - MAF": "エンジンセンサ - エアフロ(MAF)",
    "Engine Sensor - MAF Emulation (Alpha-N)": "エンジンセンサ - MAFエミュ(Alpha-N)",
    "Engine Sensor - MAF Emulation (Speed Density)": "エンジンセンサ - MAFエミュ(スピードデンシティ)",
    "Engine Sensor - MAP": "エンジンセンサ - 吸気圧(MAP)",
    "Fuel Comp - After Start Enrichment": "燃料補正 - 始動後増量",
    "Fuel Comp - LTFT": "燃料補正 - 長期学習(LTFT)",
    "Fuel Comp - LTFT MAF Breakpoints": "燃料補正 - LTFT MAFブレークポイント",
    "Fuel Comp - Radiant Intake Heat": "燃料補正 - 吸気輻射熱",
    "Fuel Comp - Tip-In Enrichment": "燃料補正 - 加速増量(Tip-In)",
    "Fuel Comp CL - Decel Recovery": "燃料補正(閉ループ) - 減速復帰",
    "Fuel Comp CL - RO2S Emissions Monitor No Activity Check": "燃料補正(閉ループ) - リアO2排ガスモニタ無活動チェック",
    "Fuel Comp CL - Warm Up Cat Efficiency Check RO2S Trim": "燃料補正(閉ループ) - 暖機触媒効率チェック リアO2トリム",
    "Fuel Comp CL - Warm-Up Cat Efficiency Check": "燃料補正(閉ループ) - 暖機触媒効率チェック",
    "Fuel Comp OL - Corrective Spark Enrichment": "燃料補正(開ループ) - 点火補正増量",
    "Fuel Comp OL - Decel Fuel Cut": "燃料補正(開ループ) - 減速燃料カット",
    "Fuel Comp OL - Decel Fuel Restore": "燃料補正(開ループ) - 減速燃料復帰",
    "Fuel Comp OL - Power Enleanment": "燃料補正(開ループ) - パワー時リーン化",
    "Fuel IPW - Base": "燃料噴射時間(IPW) - ベース",
    "Fuel IPW - Cranking": "燃料噴射時間 - クランキング",
    "Fuel IPW - Minimum": "燃料噴射時間 - 最小",
    "Fuel IPW - Offset and Scaling": "燃料噴射時間 - オフセット/スケーリング",
    "Fuel IPW - Transient Fueling (X-Tau)": "燃料噴射時間 - 過渡補正(X-Tau)",
    "Fuel Status OL - Decel": "燃料状態(開ループ) - 減速",
    "Fuel Status OL - Transition": "燃料状態(開ループ) - 遷移",
    "Fuel Status OL - Transition Delay": "燃料状態(開ループ) - 遷移ディレイ",
    "Fuel Target - Warm-Up": "目標空燃比 - 暖機",
    "Fuel Target CL - Base": "目標空燃比(閉ループ) - ベース",
    "Fuel Target OL - Base": "目標空燃比(開ループ) - ベース",
    "Gear Ratio": "ギア比",
    "Idle Speed": "アイドル回転数",
    "Idle Status": "アイドル状態",
    "Ignition Coil Dwell Time": "点火コイル通電時間(ドウェル)",
    "Intake Manifold Runner Control (AT Only)": "吸気マニホールド ランナー制御(AT限定)",
    "Intake Manifold Tuning Valve": "吸気マニホールド チューニングバルブ",
    "Patch - Decel Fuel Cut Off": "パッチ - 減速燃料カット",
    "Patch - Immobilizer": "パッチ - イモビライザー",
    "Patch - Open Loop Short Term Fuel Trim Fix": "パッチ - 開ループ短期燃料補正の修正",
    "Spark Base": "点火 - ベース",
    "Spark Base - High Fuel Demand Transition": "点火ベース - 高燃料要求遷移",
    "Spark Base Comp - ECT / IAT": "点火ベース補正 - 水温/吸気温",
    "Spark Base Limit": "点火ベース上限",
    "Spark Base Limit Comp - Power": "点火ベース上限補正 - パワー",
    "Spark Correction - Cold Advance": "点火補正 - 冷間進角",
    "Spark Correction - EGR Advance": "点火補正 - EGR進角",
    "Spark Correction - Knock Retard": "点火補正 - ノックリタード",
    "Spark Correction - Launch Control Retard": "点火補正 - ローンチコントロールリタード",
    "Spark Correction - Stumble Recovery Retard": "点火補正 - ストール復帰リタード",
    "Spark Correction - Tip-In Retard": "点火補正 - 加速時リタード(Tip-In)",
    "Spark Idle Limit": "点火 - アイドル上限",
    "Spark Idle Load - Base": "点火アイドル負荷 - ベース",
    "Spark To Cylinders": "点火 - 気筒割り当て",
    "Variable Cam Timing - Base": "可変バルブタイミング(VCT) - ベース",
    "Vehicle Instrument Cluster - CEL Warning": "メーター - 警告灯(CEL)",
    "Vehicle Instrument Cluster - ECT Gauge": "メーター - 水温計",
    "Vehicle Instrument Cluster - Speedometer": "メーター - スピードメーター",
}


# LibreTuner 定義(124カテゴリ)の用語辞書。完全一致で引けないカテゴリは、
# ここの語句を「長いものから順に」置換して日本語化する。英語の区切り ' - ' は残す。
_LT_TERMS_RAW = {
    # --- 複合フレーズ(長い語を優先) ---
    "Data Integrity Checks": "データ整合性チェック",
    "Data Integrity Thresholds": "データ整合性しきい値",
    "DBW Throttle Duty Desired + Comp to Torque Request": "目標スロットルデューティ+トルク要求補正",
    "DBW Throttle Duty Commanded Limits": "スロットルデューティ指令 上限",
    "DBW Throttle Duty Desired Comp": "目標スロットルデューティ補正",
    "DBW Throttle Duty Desired": "目標スロットルデューティ",
    "DBW Throttle Duty Target": "スロットルデューティ目標",
    "DBW Torque Request": "電子スロットル トルク要求",
    "Throttle Angle Commanded Conversion": "スロットル開度指令 変換",
    "Throttle Duty Desired Comp": "目標スロットルデューティ補正",
    "Throttle Duty Desired": "目標スロットルデューティ",
    "Comp to Torque Request": "トルク要求への補正",
    "Torque Request": "トルク要求",
    "Cruise Control": "クルーズコントロール",
    "Emission System": "排出ガスシステム",
    "Engine Fan Control": "電動ファン制御",
    "Engine Limiters": "エンジンリミッター",
    "Engine Sensors": "エンジンセンサー",
    "Engine Load": "エンジン負荷",
    "RO2S Emissions Monitor No Activity Check": "リアO2 無活動チェック",
    "RO2S Trim (ZERO)": "リアO2トリム(ゼロ)",
    "RO2S Trim": "リアO2トリム",
    "STFT Correction Coefficients": "短期補正係数(STFT)",
    "STFT Transition Delay": "短期補正 移行遅延(STFT)",
    "Transition to Closed Loop": "閉ループ移行",
    "Warm Up Cat Efficiency Check RO2S Trim": "暖機 触媒効率チェック リアO2トリム",
    "Warm-Up Cat Efficency Check": "暖機 触媒効率チェック",
    "Warm-Up Cat Efficiency Check": "暖機 触媒効率チェック",
    "Corrective Spark Enrichment": "点火補正増量",
    "Decel Fuel Restore Idle Thresholds": "減速燃料復帰 アイドルしきい値",
    "Decel Fuel Restore": "減速燃料復帰",
    "Decel Fuel Cutoff": "減速燃料カット",
    "Decel Fuel Cut": "減速燃料カット",
    "Decel Recovery": "減速復帰",
    "Power Enleanment (OEM Bypassed)": "高負荷リーン化(純正無効)",
    "Power Enleanment": "高負荷リーン化",
    "Start-Up Enrichment (Catalyst)": "始動増量(触媒)",
    "Increasing Load Enrichment": "負荷増大時増量",
    "LTFT MAF Breakpoints": "長期補正 MAFブレークポイント",
    "MAF Thresholds WIP": "MAFしきい値(作業中)",
    "Radiant Intake Heat": "吸気輻射熱",
    "IMRC Transition": "可変吸気(IMRC)移行",
    "Dynamic Trim Mult A (Large)": "動的トリム係数A(大)",
    "Dynamic Trim Mult B (Small)": "動的トリム係数B(小)",
    "Dynamic Trim Mult C": "動的トリム係数C",
    "Offset and Scaling": "オフセット/スケーリング",
    "Fuel Status OL Delay Reset (Secondary)": "燃料状態OL 遅延リセット(セカンダリ)",
    "Fuel Status OL Delayed (Secondary)": "燃料状態OL 遅延(セカンダリ)",
    "Fuel Status OL (Primary)": "燃料状態OL(プライマリ)",
    "Fuel Status OL (Secondary)": "燃料状態OL(セカンダリ)",
    "Fuel Status OL": "燃料状態OL",
    "Catalyst Temp": "触媒温度",
    "Fuel Comp CL": "燃料補正(閉ループ)",
    "Fuel Comp OL/CL": "燃料補正(開/閉ループ)",
    "Fuel Comp OL": "燃料補正(開ループ)",
    "Fuel Target CL": "目標空燃比(閉ループ)",
    "Fuel Target OL": "目標空燃比(開ループ)",
    "Warm-Up Fuel Target OL": "暖機 目標空燃比(開ループ)",
    "Fuel IPW": "燃料噴射時間(IPW)",
    "Base (no patch required)": "ベース(パッチ不要)",
    "Base (requires patch)": "ベース(要パッチ)",
    "Base Patch": "ベースパッチ",
    "Gear Ratio": "ギア比",
    "Idle Speed Comp": "アイドル回転補正",
    "Idle Speed": "アイドル回転数",
    "Idle Transition Delay": "アイドル移行遅延",
    "Ignition Coil Dwell Time": "点火コイル ドウェル時間",
    "Intake Manifold Runner Control (AT Only)": "可変吸気ランナー制御(AT限定)",
    "Intake Manifold Tuning Valve": "可変吸気バルブ(IMTV)",
    "Engine Displacement": "排気量",
    "Immobilizer Disable": "イモビライザー無効",
    "Open Loop Short Term Fuel Trim Fix": "開ループ短期補正 修正",
    "UDS Read Memory By Address (Mode 23)": "UDSメモリ読出し(Mode23)",
    "Spark Base / Idle Transition": "点火ベース/アイドル移行",
    "Spark Base Comp": "点火ベース補正",
    "Spark Base Limit Comp": "点火ベース上限補正",
    "Spark Base Limit": "点火ベース上限",
    "Spark Base": "点火ベース(基本進角)",
    "Spark Idle / Base Limit Correction": "点火アイドル/ベース上限 補正",
    "Spark Idle / Base Limit": "点火アイドル/ベース上限",
    "Spark Idle Limit Correction": "点火アイドル上限 補正",
    "Spark Idle Limit": "点火アイドル上限",
    "Spark Idle Load": "点火アイドル負荷",
    "Spark Correction": "点火補正",
    "Spark Comp": "点火補正",
    "Spark Limits": "点火上限",
    "Spark To Cylinders": "気筒別点火",
    "High Fuel Request Transition": "高燃料要求 移行",
    "High Fuel Request": "高燃料要求",
    "Low Fuel Request": "低燃料要求",
    "ECT / IAT Combined": "水温/吸気温 複合",
    "Cold Advance": "冷間進角",
    "EGR Advance": "EGR進角",
    "Feedback WIP (AT)": "フィードバック(作業中/AT)",
    "High ECT Spark Corection WIP (AT Only)": "高水温点火補正(作業中/AT限定)",
    "High RPM and ECT": "高回転・高水温",
    "Knock Retard": "ノックリタード",
    "Stumble Recovery": "ストール回復",
    "Tip-In Anti Lug": "急開 低回転保護",
    "Tip-In First Gear": "急開 1速",
    "Tip-In From Stop": "急開 発進時",
    "Tip-In High Speed": "急開 高速",
    "Tip-In Shared": "急開 共通",
    "Tip-In": "急開(ティップイン)",
    "Transition from In-Gear to Idle": "走行→アイドル移行",
    "Transition from Decel": "減速からの移行",
    "Special Warm-Up WIP": "特殊暖機(作業中)",
    "AC Cycle Transition": "A/C断続移行",
    "PS Cycle Transition": "パワステ断続移行",
    "Idle Error": "アイドル偏差",
    "Alternator Compensation": "オルタネータ補正",
    "PSP Compensation": "パワステ(PSP)補正",
    "Variable Cam Timing": "可変バルブタイミング(VVT)",
    "DO NOT MODIFY": "変更禁止",
    "AC Comp": "A/C補正",
    "Alternator Comp": "オルタネータ補正",
    "PSP Comp": "パワステ(PSP)補正",
    "VSS Comp": "車速補正",
    "DTC Flags B": "診断コード フラグB",
    "DTC Thresholds": "診断コード しきい値",
    # --- 単独語(最後に当てる短い語) ---
    "Catalyst": "触媒",
    "Cranking": "クランキング",
    "Minimum": "最小",
    "Aggregate": "総合",
    "Scaling": "スケーリング",
    "Limits": "上限",
    "Limit": "上限",
    "Decel": "減速",
    "Load": "負荷",
    "Base": "ベース",
    "Comp": "補正",
    "Power": "高負荷",
    "Patch": "パッチ",
    "Alternator": "オルタネータ",
    "DBW": "電子スロットル(DBW)",
    "RPM": "回転数",
    "VSS": "車速",
    "APP": "アクセル開度(APP)",
    "AFS": "A/F(空燃比)センサ(AFS)",
    "ECT": "水温(ECT)",
    "IAT": "吸気温(IAT)",
    "MAF": "MAF",
    "MAP": "MAP",
    "KS": "ノックセンサー(KS)",
    "EGR": "EGR",
    "EVAP": "EVAP(蒸発ガス)",
    "LTFT": "長期燃料補正(LTFT)",
    "STFT": "短期燃料補正(STFT)",
    "Transition": "移行",
    "WIP": "作業中(WIP)",
    "TD": "TD",
}
# 単一パス置換用: 長いキーを優先するよう長さ降順に並べた正規表現。
# re.sub は左→右で一度マッチした箇所を再走査しないため、JA出力に含まれる英字
# (STFT 等)が二重置換される不具合を防げる。
import re as _re

_LT_TERMS = sorted(_LT_TERMS_RAW.items(), key=lambda kv: len(kv[0]), reverse=True)
_LT_PATTERN = _re.compile("|".join(_re.escape(k) for k, _ in _LT_TERMS))


def _translate_lt_category(en: str) -> str:
    return _LT_PATTERN.sub(lambda m: _LT_TERMS_RAW[m.group(0)], en)


# LibreTuner 124カテゴリの「意味が分かる」日本語訳(直訳でなく機能で表す)。
CATEGORY_JA_LT = {
    "DBW - Cruise Control": "電子スロットル - クルーズコントロール",
    "DBW - Throttle Angle Commanded Conversion": "電子スロットル - 目標開度の内部変換",
    "DBW - Throttle Duty Desired": "電子スロットル - 目標スロットル開度(ペダル→スロットル)",
    "DBW - Throttle Duty Desired Comp - Aggregate": "電子スロットル - 目標スロットル開度 補正(総合)",
    "DTC Flags B": "診断コード(DTC) 有効/無効フラグ",
    "DTC Thresholds": "診断コード(DTC) 判定しきい値",
    "Data Integrity Checks - DBW Throttle Duty Commanded Limits": "安全監視 - スロットル指令の上下限",
    "Data Integrity Checks - DBW Throttle Duty Desired": "安全監視 - 目標スロットル開度(監視コピー)",
    "Data Integrity Checks - DBW Throttle Duty Desired + Comp to Torque Request": "安全監視 - 目標スロットル開度+補正→トルク要求",
    "Data Integrity Checks - DBW Throttle Duty Desired Comp - Aggregate": "安全監視 - 目標スロットル開度 補正(総合)",
    "Data Integrity Checks - Idle Speed - Base": "安全監視 - 目標アイドル回転(ベース)",
    "Data Integrity Checks - Idle Speed Comp": "安全監視 - アイドル回転 補正",
    "Data Integrity Checks - Spark Idle Load - AC Comp": "安全監視 - アイドル負荷(点火) A/C補正",
    "Data Integrity Checks - Spark Idle Load - Alternator Comp": "安全監視 - アイドル負荷(点火) オルタネータ補正",
    "Data Integrity Checks - Spark Idle Load - Base": "安全監視 - アイドル負荷(点火) ベース",
    "Data Integrity Checks - Spark Idle Load - PSP Comp": "安全監視 - アイドル負荷(点火) パワステ補正",
    "Data Integrity Checks - Spark Idle Load - VSS Comp": "安全監視 - アイドル負荷(点火) 車速補正",
    "Data Integrity Thresholds - DBW Throttle Duty Target": "安全監視しきい値 - スロットル目標",
    "Data Integrity Thresholds - DBW Torque Request": "安全監視しきい値 - トルク要求",
    "Data Integrity Thresholds - DBW Torque Request ": "安全監視しきい値 - トルク要求",
    "Emission System - Catalyst": "排出ガス - 触媒",
    "Emission System - EGR": "排出ガス - EGR(排気再循環)",
    "Emission System - EVAP": "排出ガス - EVAP(蒸発ガス)",
    "Engine Fan Control": "電動ファン制御",
    "Engine Limiters - RPM": "リミッタ - 回転数(レブリミット)",
    "Engine Limiters - VSS": "リミッタ - 車速(スピードリミッタ)",
    "Engine Load - Limits": "エンジン負荷 - 上限",
    "Engine Load - Scaling": "エンジン負荷 - 算出スケーリング",
    "Engine Sensors - AFS": "センサ - 空燃比(A/Fセンサ・AFS)",
    "Engine Sensors - ECT": "センサ - 水温(ECT)",
    "Engine Sensors - IAT": "センサ - 吸気温(IAT)",
    "Engine Sensors - KS": "センサ - ノック(KS)",
    "Engine Sensors - KS - DO NOT MODIFY": "センサ - ノック(KS)〔変更禁止〕",
    "Engine Sensors - MAF": "センサ - エアフロ(MAF)",
    "Engine Sensors - MAP": "センサ - 吸気圧(MAP)",
    "Fuel Comp CL - Decel Recovery": "燃料補正(閉ループ) - 減速からの復帰",
    "Fuel Comp CL - RO2S Emissions Monitor No Activity Check": "燃料補正(閉ループ) - リアO2 排ガス監視(無反応チェック)",
    "Fuel Comp CL - RO2S Trim (ZERO)": "燃料補正(閉ループ) - リアO2トリム(ゼロ)",
    "Fuel Comp CL - STFT Correction Coefficients": "燃料補正(閉ループ) - 短期学習の補正係数",
    "Fuel Comp CL - STFT Transition Delay": "燃料補正(閉ループ) - 短期学習の移行遅延",
    "Fuel Comp CL - Transition to Closed Loop": "燃料補正(閉ループ) - 閉ループへの移行",
    "Fuel Comp CL - Warm Up Cat Efficiency Check RO2S Trim": "燃料補正(閉ループ) - 暖機 触媒効率チェックのリアO2トリム",
    "Fuel Comp CL - Warm-Up Cat Efficency Check": "燃料補正(閉ループ) - 暖機 触媒効率チェック",
    "Fuel Comp OL - Corrective Spark Enrichment": "燃料補正(開ループ) - 点火補正に伴う増量",
    "Fuel Comp OL - Decel Fuel Cut": "燃料補正(開ループ) - 減速燃料カット",
    "Fuel Comp OL - Decel Fuel Restore": "燃料補正(開ループ) - 減速後の燃料復帰",
    "Fuel Comp OL - Decel Fuel Restore Idle Thresholds": "燃料補正(開ループ) - 燃料復帰のアイドル判定",
    "Fuel Comp OL - Power Enleanment": "燃料補正(開ループ) - 高負荷リーン化",
    "Fuel Comp OL - Power Enleanment (OEM Bypassed)": "燃料補正(開ループ) - 高負荷リーン化(純正無効化)",
    "Fuel Comp OL - Start-Up Enrichment (Catalyst)": "燃料補正(開ループ) - 始動時増量(触媒暖機)",
    "Fuel Comp OL/CL - IMRC Transition": "燃料補正(開/閉) - 可変吸気(IMRC)切替時",
    "Fuel Comp OL/CL - Increasing Load Enrichment": "燃料補正(開/閉) - 負荷急増時の増量",
    "Fuel Comp OL/CL - LTFT": "燃料補正(開/閉) - 長期学習(LTFT)",
    "Fuel Comp OL/CL - LTFT MAF Breakpoints": "燃料補正(開/閉) - 長期学習のMAF区切り",
    "Fuel Comp OL/CL - MAF Thresholds WIP": "燃料補正(開/閉) - MAFしきい値(作業中)",
    "Fuel Comp OL/CL - Radiant Intake Heat": "燃料補正(開/閉) - 吸気輻射熱補正(熱間再始動)",
    "Fuel IPW - Base": "噴射時間 - ベース",
    "Fuel IPW - Cranking": "噴射時間 - クランキング(始動)",
    "Fuel IPW - Dynamic Trim Mult A (Large)": "噴射時間 - 動的トリム係数A(大)",
    "Fuel IPW - Dynamic Trim Mult B (Small)": "噴射時間 - 動的トリム係数B(小)",
    "Fuel IPW - Dynamic Trim Mult C": "噴射時間 - 動的トリム係数C",
    "Fuel IPW - Minimum": "噴射時間 - 最小",
    "Fuel IPW - Offset and Scaling": "噴射時間 - デッドタイム/容量(オフセット・スケーリング)",
    "Fuel Status OL (Primary) - APP": "燃料状態(開ループ・一次) - アクセル開度判定",
    "Fuel Status OL (Secondary) - APP": "燃料状態(開ループ・二次) - アクセル開度判定",
    "Fuel Status OL (Secondary) - Load": "燃料状態(開ループ・二次) - 負荷判定",
    "Fuel Status OL - Decel": "燃料状態(開ループ) - 減速",
    "Fuel Status OL Delay Reset (Secondary)": "燃料状態(開ループ・二次) - 遅延リセット",
    "Fuel Status OL Delay Reset (Secondary) - Load": "燃料状態(開ループ・二次) - 遅延リセット(負荷)",
    "Fuel Status OL Delay Reset (Secondary) - RPM": "燃料状態(開ループ・二次) - 遅延リセット(回転数)",
    "Fuel Status OL Delayed (Secondary) - Catalyst Temp": "燃料状態(開ループ・二次) - 遅延(触媒温度)",
    "Fuel Status OL Delayed (Secondary) - RPM": "燃料状態(開ループ・二次) - 遅延(回転数)",
    "Fuel Status OL Delayed (Secondary) - TD": "燃料状態(開ループ・二次) - 遅延(TD)",
    "Fuel Target CL - Base (no patch required)": "目標空燃比(閉ループ) - ベース(パッチ不要)",
    "Fuel Target CL - Base (requires patch)": "目標空燃比(閉ループ) - ベース(要パッチ)",
    "Fuel Target CL - Base Patch": "目標空燃比(閉ループ) - ベース用パッチ",
    "Fuel Target OL - Base": "目標空燃比(開ループ・高負荷) - ベース",
    "Gear Ratio": "ギア比",
    "Idle Speed - Base": "目標アイドル回転 - ベース",
    "Idle Speed Comp": "アイドル回転 - 補正",
    "Idle Transition Delay": "アイドル移行の遅延",
    "Ignition Coil Dwell Time": "点火コイル通電時間(ドウェル)",
    "Intake Manifold Runner Control (AT Only)": "可変吸気ランナー制御 IMRC(AT限定)",
    "Intake Manifold Tuning Valve": "可変吸気バルブ(IMTV)",
    "Patch - Decel Fuel Cutoff": "パッチ - 減速燃料カットの無効化",
    "Patch - Flat Shift": "パッチ - フラットシフト",
    "Patch - Engine Displacement": "パッチ - 排気量設定",
    "Patch - Immobilizer Disable": "パッチ - イモビライザー無効化",
    "Patch - Open Loop Short Term Fuel Trim Fix": "パッチ - 開ループ短期補正の修正",
    "Patch - UDS Read Memory By Address (Mode 23)": "パッチ - メモリ読出し有効化(UDS Mode23)",
    "Spark Base - High Fuel Request": "点火時期ベース - 高燃料要求時",
    "Spark Base - High Fuel Request Transition": "点火時期ベース - 高燃料要求への移行",
    "Spark Base - Low Fuel Request": "点火時期ベース - 低燃料要求時",
    "Spark Base / Idle Transition": "点火時期ベース/アイドル移行",
    "Spark Base Comp - ECT / IAT Combined": "点火時期ベース補正 - 水温/吸気温(複合)",
    "Spark Base Limit": "点火時期ベースの上限",
    "Spark Base Limit Comp - Power": "点火時期ベース上限 補正(高負荷)",
    "Spark Comp - Cold Advance": "点火補正 - 冷間進角",
    "Spark Comp - EGR Advance": "点火補正 - EGR作動時進角",
    "Spark Correction - Feedback WIP (AT)": "点火補正 - フィードバック(作業中/AT)",
    "Spark Correction - High ECT Spark Corection WIP (AT Only)": "点火補正 - 高水温時(作業中/AT限定)",
    "Spark Correction - High RPM and ECT": "点火補正 - 高回転・高水温時の遅角",
    "Spark Correction - Knock Retard": "点火補正 - ノックリタード(ノック時遅角)",
    "Spark Correction - Stumble Recovery": "点火補正 - 息つき/ストール復帰",
    "Spark Correction - Tip-In Anti Lug": "点火補正 - 急開時アンチラグ(低回転保護)",
    "Spark Correction - Tip-In First Gear": "点火補正 - 急開時(1速)",
    "Spark Correction - Tip-In From Stop": "点火補正 - 急開時(発進)",
    "Spark Correction - Tip-In High Speed": "点火補正 - 急開時(高速)",
    "Spark Correction - Tip-In Shared": "点火補正 - 急開時(共通)",
    "Spark Correction - Transition from Decel": "点火補正 - 減速からの復帰",
    "Spark Correction - Transition from In-Gear to Idle": "点火補正 - 走行→アイドル移行",
    "Spark Idle / Base Limit - Transition": "点火 アイドル/ベース上限 - 移行",
    "Spark Idle / Base Limit Correction - Special Warm-Up WIP": "点火 アイドル/ベース上限 補正 - 特殊暖機(作業中)",
    "Spark Idle Limit": "点火 アイドル時の上限",
    "Spark Idle Limit Correction - AC Cycle Transition": "点火 アイドル上限補正 - A/C断続切替",
    "Spark Idle Limit Correction - Idle Error": "点火 アイドル上限補正 - アイドル回転偏差",
    "Spark Idle Limit Correction - PS Cycle Transition": "点火 アイドル上限補正 - パワステ断続切替",
    "Spark Idle Load - Alternator Compensation": "アイドル負荷(点火) - オルタネータ補正",
    "Spark Idle Load - PSP Compensation": "アイドル負荷(点火) - パワステ補正",
    "Spark Limits": "点火時期の上下限(保護)",
    "Spark To Cylinders": "気筒別の点火割り当て",
    "Variable Cam Timing - Base": "可変バルブタイミング(VVT) - ベース",
    "Variable Cam Timing - DO NOT MODIFY": "可変バルブタイミング(VVT)〔変更禁止〕",
    "WIP - Alternator": "作業中(WIP) - オルタネータ",
    "WIP - Torque Model Bank (RE)": "トルクモデル(RE・N·m確認済)",
    "WIP - DBW Torque Coordinator (RE)": "DBWトルク協調(RE)",
    "WIP - Fuel Comp Cut Pattern (RE)": "燃料補正 - カットパターン増量(RE)",
    "Warm-Up Fuel Target OL - Base": "目標空燃比(開ループ) - 暖機時ベース",
}


def translate_category(en: str) -> str:
    """カテゴリ名を現在言語で返す。英語モードは原文(定義の英語)。"""
    if en is None:
        return ""
    s = en.strip()
    if _LANG == "en":
        return s
    if s in CATEGORY_JA_LT:
        return CATEGORY_JA_LT[s]
    if s in CATEGORY_JA:
        return CATEGORY_JA[s]
    return _translate_lt_category(s)


# ---- テーブル名(ツリー小項目)の用語訳。カテゴリ用語+名称固有の語を最長一致で置換 ----
_NAME_EXTRA = {
    # フラットシフト関連の追加項目(ncecu/flatshift.py)
    "Flat Shift": "フラットシフト", "Retard Amount": "遅角量",
    "Method (0 Retard / 1 Cut)": "方式(0遅角/1カット)",
    "Min Advance Floor": "下限(最小進角)", "Debug Test Mode (0 off / 1 clutch-only)": "デバッグ テストモード(0/1クラッチのみ)",
    "Cut Floor": "カット下限",
    "APP Threshold": "アクセルしきい値", "RPM Threshold": "回転しきい値",
    "Vehicle Speed Minimum": "車速下限", "Vehicle Speed": "車速", "Throttle Cut": "スロットルカット",
    # 条件・状態(句を優先)
    "4th, 5th, 6th Gear": "4/5/6速", "First Gear": "1速", "1st Gear": "1速",
    "2nd Gear": "2速", "3rd Gear": "3速", "High-Det": "高ノック検出",
    "Brake On": "ブレーキON", "Brake Off": "ブレーキOFF",
    "CPP set": "クラッチ踏込", "CPP clear": "クラッチ戻し", "CPP Off": "クラッチOFF",
    "CPP On": "クラッチON", "Not In-Gear": "非走行(N)", "In-Gear": "走行中",
    "Not Idle Trans": "非アイドル移行", "Not Idle": "非アイドル", "Idle Trans": "アイドル移行",
    "Timer Active": "タイマ作動中", "Timer Expired": "タイマ満了",
    "Start-Up": "始動時", "Startup": "始動時", "From Stop": "発進時", "High Speed": "高速",
    "Anti Lug": "アンチラグ", "No Activity": "無反応", "Catalyst Temp": "触媒温度",
    "Shuffle Filter Coefficient": "しゃくり振動フィルタ係数", "Torque Request Anti-Jerk": "トルク要求の振動抑制",
    "Band-Pass Coefficient": "帯域フィルタ係数", "Gear x Tip-In Stage": "ギア×踏み込み段階", "Gain": "ゲイン",
    "Cut Pattern Enrichment": "カットパターン増量",
    "Power Enleanment": "高負荷リーン化", "Radiant Intake Heat": "吸気輻射熱",
    "Idle Speed": "アイドル回転", "Idle Load": "アイドル負荷",
    "High Fuel Request": "高燃料要求", "Low Fuel Request": "低燃料要求", "Fuel Request": "燃料要求",
    "Throttle Duty": "スロットルデューティ", "Torque Request": "トルク要求",
    "Runner Control": "ランナー制御", "Tuning Valve": "可変バルブ", "Cam Timing": "カムタイミング",
    "Cruise Control": "クルーズコントロール",
    # 名詞
    "Threshold": "しきい値", "Hysteresis": "ヒステリシス", "Multiplier": "係数", "Mult": "係数",
    "Coefficients": "係数", "Coefficient": "係数", "Breakpoints": "区切り",
    "Enrichment": "増量", "Enleanment": "リーン化", "Recovery": "復帰", "Restore": "復帰",
    "Monitor": "監視", "Efficiency": "効率", "Error": "偏差", "Conversion": "変換",
    "Compensation": "補正", "Correction": "補正", "Transition": "移行", "Aggregate": "総合",
    "Requested": "要求", "Request": "要求", "Desired": "目標", "Commanded": "指令",
    "Displacement": "排気量", "Ratio": "比", "Feedback": "フィードバック", "Limiter": "リミッタ",
    "Offset": "オフセット", "Scaling": "スケーリング", "Delay": "遅延", "Timer": "タイマ",
    "Rate": "レート", "Value": "値", "Stage": "ステージ", "Cylinder": "気筒",
    "Fuel Cut": "燃料カット", "Fuel": "燃料", "Dwell": "ドウェル", "Advance": "進角",
    "Retard": "遅角", "Knock": "ノック", "Stumble": "息つき", "Catalyst": "触媒",
    "Alternator": "オルタネータ", "Immobilizer": "イモビライザー", "Coolant": "冷却水",
    "Voltage": "電圧", "Battery": "バッテリ", "Intake": "吸気", "Cranking": "クランキング",
    # 形容・状態
    "Maximum": "最大", "Minimum": "最小", "Max": "最大", "Min": "最小",
    "Dynamic": "動的", "Large": "大", "Small": "小", "Primary": "一次", "Secondary": "二次",
    "Combined": "複合", "Estimated": "推定", "Special": "特殊", "Shared": "共通",
    "Delayed": "遅延", "Reset": "リセット", "Cycle": "断続", "Starting": "開始",
    "Active": "作動", "Expired": "満了", "Enable": "有効", "Disable": "無効",
    "Above": "以上", "Below": "以下", "Cold": "冷間", "Power": "高負荷", "Heat": "熱",
    "Add": "加算", "Limit": "上限", "Decel": "減速", "Idle": "アイドル", "Spark": "点火",
    "Torque": "トルク", "Speed": "速度", "Load": "負荷", "Fan": "ファン", "Gear": "ギア",
    "Neutral": "ニュートラル", "Trim": "トリム",
    # 略語
    "RO2S": "リアO2", "PSP": "パワステ", "RPM": "回転数", "ECT": "水温", "IAT": "吸気温",
    "MAF": "エアフロ", "MAP": "吸気圧", "BARO": "大気圧", "APP": "アクセル開度", "TP": "スロットル",
    "VSS": "車速", "LTFT": "長期補正", "STFT": "短期補正", "OEM": "純正", "WIP": "作業中",
    # 追加語彙(頻出)
    "Dynamic Trim Mult": "動的トリム係数",
    "Control Module Voltage": "制御モジュール電圧", "Control Mod Voltage": "制御モジュール電圧",
    "Control Module": "制御モジュール", "Catalyst Temp Estimate": "触媒温度推定",
    "Catalytic Temp Estimate": "触媒温度推定", "Throttle Angle": "スロットル開度",
    "Volumetric Flow": "体積流量", "Barometric Multiplier": "大気圧係数",
    "Mid Speed": "中速", "Low Speed": "低速", "Rev Limit": "レブリミット",
    "Engine Off": "エンジン停止", "Proto-Knock": "プロトノック", "Injector Offset": "インジェクタ オフセット",
    "IPW": "噴射時間", "Injector": "インジェクタ", "Throttle": "スロットル", "Angle": "角度",
    "Flow": "流量", "Volumetric": "体積", "Sensitivity": "感度", "Estimate": "推定",
    "Estimated": "推定", "Temp": "温度", "Activation": "作動", "Fault": "故障",
    "CMP": "カム角", "CKP": "クランク角", "Barometric": "大気圧", "Capture": "捕捉",
    "Magnitude": "強度", "Target": "目標", "Engine": "エンジン", "ZEROED": "ゼロ化",
    "ZERO": "ゼロ", "Sub": "副", "Rev": "回転", "Mid": "中", "Non": "非",
    "High": "高", "Low": "低", "to": "→", "with": "/", "or": "/", "and": "かつ",
    "LT": "<", "GT": ">", "GTE": "≥", "LTE": "≤", "kph": "km/h", "kpa": "kPa",
    # さらに頻出
    "Delay Reset": "遅延リセット", "Idle Status": "アイドル状態",
    "Status": "状態", "Hold": "保持", "Highest": "最高", "Lowest": "最低",
    "Cat": "触媒", "Mode": "モード", "OL": "開ループ", "CL": "閉ループ", "Det": "ノック",
    "Enleanment": "リーン化", "Enrichment": "増量", "Coolant": "冷却水",
    "Switchover": "切替", "Switch": "切替", "Enabled": "有効", "Disabled": "無効",
    "Pressure": "圧力", "Barometric Pressure": "大気圧", "Percent": "割合",
    "Factor": "係数", "Duration": "時間", "Count": "カウント", "Number": "番号",
    "Position": "位置", "Current": "現在", "Previous": "前回", "Final": "最終",
    "Initial": "初期", "Output": "出力", "Input": "入力", "Actual": "実", "Raw": "生",
}
# カテゴリ用語 + 名称固有語(名称固有を優先)。長い順で単一パス置換。
_NAME_TERMS_RAW = {**_LT_TERMS_RAW, **_NAME_EXTRA}
_NAME_ITEMS = sorted(_NAME_TERMS_RAW.items(), key=lambda kv: len(kv[0]), reverse=True)


def _build_name_pattern(items):
    parts = []
    asciiish = _re.compile(r"[A-Za-z0-9 /+().,'-]+$")
    for k, _v in items:
        esc = _re.escape(k)
        # 英数字だけの語は単語境界を付け、長い語の中への誤マッチを防ぐ
        if asciiish.match(k):
            parts.append(r"(?<![A-Za-z0-9])" + esc + r"(?![A-Za-z0-9])")
        else:
            parts.append(esc)
    return _re.compile("|".join(parts))


_NAME_PATTERN = _build_name_pattern(_NAME_ITEMS)


def translate_table_name(name: str) -> str:
    """テーブル名を現在言語で返す。英語モードは原文。日本語は用語を最長一致で置換。
    16進フラグ(7E66等)や記号はそのまま残す。"""
    if not name:
        return ""
    if _LANG == "en":
        return name
    return _NAME_PATTERN.sub(lambda m: _NAME_TERMS_RAW[m.group(0)], name)


# カテゴリごとの解説(そのマップ群が何を制御するか)。開いたマップの説明として表示。
CATEGORY_DESC = {
    "CAN - Inputs and Outputs": "CANバス経由で授受する入出力の割り当て。メーターや他ユニットとの通信項目。通常は変更不要。",
    "DBW - Throttle Angle Commanded Conversion": "電子スロットル(DBW)で、目標スロットル角度を内部指令値へ変換する特性。",
    "DBW - Throttle Duty Delta (Data Integrity)": "スロットルデューティの変化量に対する整合性(フェイルセーフ)判定しきい値。安全側の保護。",
    "DBW - Throttle Duty Desired": "アクセル開度(APP)などに対する目標スロットル開度(デューティ)。スロットルの効き・レスポンスに直結。",
    "DBW - Throttle Duty Desired (Data Integrity)": "目標スロットルデューティの整合性(フェイルセーフ)判定。保護用。",
    "DBW - Throttle Duty Limits": "スロットルデューティの上下限。保護・上限設定。",
    "DTC - Activation Flags": "各ダイアグコード(DTC)の有効/無効フラグ。診断の有効化設定。",
    "DTC - Activation Thresholds": "DTCを立てるしきい値。誤検知・不要なチェックランプの調整に関係。",
    "Emission System - EGR": "EGR(排気再循環)制御。排ガス関連のため本ツールでは変更の対象外(参照用)。",
    "Emission System - EVAP": "EVAP(燃料蒸発ガス)制御。パージ等。",
    "Engine Displacement": "排気量など基本定数。燃料計算の基礎。通常は変更不要。",
    "Engine Fan Control": "電動ファンの作動条件(水温・車速・A/C・アフタークーリング)。水温しきい値は℃ではなく水温センサ電圧のA/D値(値が大きいほど低い水温)。",
    "Engine Limiters - RPM": "レブリミット(回転数上限)。燃料カット/点火カットの回転数。",
    "Engine Limiters - VSS": "車速(VSS)に基づくリミッタ。速度リミッター等。",
    "Engine Load - Limits": "エンジン負荷の上限・保護。",
    "Engine Load - Scaling": "負荷(ロード)指標のスケーリング。燃料/点火マップの軸計算に影響する基礎設定。",
    "Engine Sensor - AFS": "空燃比センサ(AFS/A/F)の特性・補正。",
    "Engine Sensor - ECT": "水温センサ(ECT)の特性(抵抗→温度変換など)。",
    "Engine Sensor - Flex Fuel": "フレックス燃料(エタノール濃度)センサ関連。該当装備時のみ。",
    "Engine Sensor - IAT": "吸気温センサ(IAT)の特性。吸気温補正の基礎。",
    "Engine Sensor - KS": "ノックセンサ(KS)関連の設定。ノック検出の基礎。",
    "Engine Sensor - MAF": "エアフロメータ(MAF)の特性(周波数/電圧→空気量)。燃料計算の要。吸気系変更時に調整。",
    "Engine Sensor - MAF Emulation (Alpha-N)": "MAFを使わずスロットル開度と回転数から空気量を推定(Alpha-N)する方式の設定。",
    "Engine Sensor - MAF Emulation (Speed Density)": "MAFの代わりに吸気圧(MAP)と回転数から空気量を推定(スピードデンシティ/VE)する方式の設定。",
    "Engine Sensor - MAP": "吸気圧センサ(MAP)の特性(電圧→圧力)。SD方式や過給で重要。",
    "Fuel Comp - After Start Enrichment": "始動直後の増量補正。始動性・暖機初期の安定に関係。",
    "Fuel Comp - LTFT": "長期燃料補正(ロングターム)。学習による定常のズレ補正。",
    "Fuel Comp - LTFT MAF Breakpoints": "LTFTを学習・適用する領域(MAF)のブレークポイント。",
    "Fuel Comp - Radiant Intake Heat": "吸気の輻射熱による燃料補正。熱間再始動等。",
    "Fuel Comp - Tip-In Enrichment": "加速(アクセル踏み込み=Tip-In)時の増量。加速時のツキ・息つき対策。",
    "Fuel Comp CL - Decel Recovery": "閉ループ時、減速からの復帰での燃料補正。",
    "Fuel Comp CL - RO2S Emissions Monitor No Activity Check": "リアO2センサの無活動監視(排ガス診断)。",
    "Fuel Comp CL - Warm Up Cat Efficiency Check RO2S Trim": "暖機時の触媒効率チェックに伴うリアO2トリム。",
    "Fuel Comp CL - Warm-Up Cat Efficiency Check": "暖機時の触媒効率チェック。排ガス診断系。",
    "Fuel Comp OL - Corrective Spark Enrichment": "開ループ時、点火補正に連動する増量。",
    "Fuel Comp OL - Decel Fuel Cut": "減速時の燃料カット(DFCO)。燃費・エンブレに関係。",
    "Fuel Comp OL - Decel Fuel Restore": "減速燃料カットからの燃料復帰条件。復帰時のショック対策。",
    "Fuel Comp OL - Power Enleanment": "高負荷(パワー)時のリーン化補正。通常はパワー空燃比側に調整。",
    "Fuel IPW - Base": "インジェクタ基本噴射時間(パルス幅)。燃料量の基礎。",
    "Fuel IPW - Cranking": "クランキング(始動)時の噴射時間。始動性。",
    "Fuel IPW - Minimum": "最小噴射時間。インジェクタの下限。大容量インジェクタ化で関係。",
    "Fuel IPW - Offset and Scaling": "インジェクタのオフセット(デッドタイム)とスケーリング。インジェクタ変更時に必須の調整。",
    "Fuel IPW - Transient Fueling (X-Tau)": "過渡時の壁流補正(X-Tau)。加減速時の空燃比安定。",
    "Fuel Status OL - Decel": "開ループ・減速時の燃料状態遷移。",
    "Fuel Status OL - Transition": "開ループ/閉ループの遷移条件。",
    "Fuel Status OL - Transition Delay": "燃料状態遷移のディレイ。",
    "Fuel Target - Warm-Up": "暖機時の目標空燃比。",
    "Fuel Target CL - Base": "閉ループ時の目標空燃比(通常ストイキ=14.7付近)。",
    "Fuel Target OL - Base": "開ループ時の目標空燃比(高負荷のパワー空燃比など)。体感・安全に直結。",
    "Gear Ratio": "各ギアのギア比(推定)。ギア判定・制御に使用。",
    "Idle Speed": "目標アイドル回転数(冷間/温間など)。アイドルの高さ調整。",
    "Idle Status": "アイドル判定の条件。",
    "Ignition Coil Dwell Time": "点火コイルの通電時間(ドウェル)。コイル変更時に関係。",
    "Intake Manifold Runner Control (AT Only)": "可変吸気(ランナー)制御(AT車のみ)。",
    "Intake Manifold Tuning Valve": "可変吸気バルブ(VTCS/VICS等)の制御。切替回転数など。",
    "Patch - Decel Fuel Cut Off": "減速燃料カットに関するパッチ(改変)項目。",
    "Patch - Immobilizer": "イモビライザー関連のパッチ。中古ECU流用時などに関係。取り扱い注意。",
    "Patch - Open Loop Short Term Fuel Trim Fix": "開ループ時の短期燃料補正に関する修正パッチ。",
    "Spark Base": "基本点火時期マップ(回転数×負荷)。パワー・燃費・ノックに直結する最重要マップの一つ。",
    "Spark Base - High Fuel Demand Transition": "高燃料要求時の点火ベース遷移。",
    "Spark Base Comp - ECT / IAT": "水温・吸気温による点火時期補正。温度条件での進角/遅角。",
    "Spark Base Limit": "点火時期の上限(進角側リミット)。安全側の制限。",
    "Spark Base Limit Comp - Power": "パワー域の点火上限補正。",
    "Spark Correction - Cold Advance": "冷間時の進角補正。暖機性能。",
    "Spark Correction - EGR Advance": "EGR作動時の進角補正。",
    "Spark Correction - Knock Retard": "ノック検出時の遅角(リタード)量。ノック保護の効き方。",
    "Spark Base / Idle Transition": "アイドル用の点火とベース点火(走行用)を切り替える条件。回転数しきい値など。",
    "Spark Base - High Fuel Request Transition": "点火マップ『高燃料要求時 / 低燃料要求時』を切り替える境界。燃料要求(ストイキに対する増量%)がしきい値を超えると高燃料要求側を使う。進角値そのものではない。",
    "Spark Idle Limit Correction - AC Cycle Transition": "A/C コンプレッサが切れた直後に、アイドル点火へ一時的に加える補正(量と継続カウント)。",
    "Spark Idle Limit Correction - Idle Error": "アイドル回転の偏差(実回転−目標)に応じた点火補正。アイドルの安定に使う。",
    "Spark Idle Limit Correction - PS Cycle Transition": "パワステ負荷が入り/切りした直後に、アイドル点火へ一時的に加える補正(量と継続カウント)。",
    "WIP - Torque Model Bank (RE)": "点火効率トルクモデルの表(逆解析)。回転×負荷の(係数k・MBT点火・トルク)が4組と、回転×水温の表が1枚。軸と寸法はECU内部の表記述子で確認済み。役割名は値と使われ方からの推定。",
    "WIP - DBW Torque Coordinator (RE)": "電子スロットルのトルク協調まわりの表(逆解析)。アクセル→トルク要求(BMEP)→目標スロットルと、トルク要求の振動抑制(駆動系のしゃくりを帯域フィルタで取り出して差し引く)。名前に (Control) が付く表は、安全監視(Data Integrity)側に同じ値の写しがあり、変えるときは必ず両方を同じ値にする。軸と寸法はECU内部の表記述子で確認済み。",
    "WIP - Fuel Comp Cut Pattern (RE)": "燃料の増量%の1項(RAM 0xFFFF75DC)を回転×負荷で引く表(逆解析)。CAN(ID 0x211)で届くトルク上限が要求トルクを下回り、一部の気筒の燃料を止めてトルクを下げる間だけ使う。気筒パターンの状態で3面を切り替える。",
    "Spark Correction - Tip-In Anti Lug": "急開(踏み込み)直後の駆動系のしゃくり(前後振動)を点火遅角で抑える。ギアごとのしゃくり振動数(回転数÷車速から引く)で振動抽出フィルタの係数を選び、負荷の振動成分に応じて遅角する。",
    "Spark Correction - Launch Control Retard": "ローンチコントロール時の遅角。",
    "Spark Correction - Stumble Recovery Retard": "ストール/息つき復帰時の遅角。",
    "Spark Correction - Tip-In Retard": "加速(Tip-In)時の遅角補正。加速時ノック対策。",
    "Spark Idle Limit": "アイドル時の点火時期リミット。",
    "Spark Idle Load - Base": "アイドル負荷時の基本点火。アイドル安定に関係。",
    "Spark To Cylinders": "各気筒への点火割り当て。通常は変更不要。",
    "Variable Cam Timing - Base": "可変バルブタイミング(VCT)の目標角度マップ。トルク特性に影響。",
    "Vehicle Instrument Cluster - CEL Warning": "メーターのチェックランプ(CEL)警告表示の制御。",
    "Vehicle Instrument Cluster - ECT Gauge": "水温計の表示特性(実温度→針位置)。水温計の張り付き調整等。",
    "Patch - Flat Shift": "フラットシフト・パッチ(第6ドラフト＝スクラッチ無し・読み取り専用)の定数。クラッチ踏込 かつ 回転>しきい値 かつ アクセル>しきい値 かつ 車速>下限 の間だけ発動(RAMに一切書かない。窓時間はクラッチを踏んでいる長さ＝回転しきい値が上限)。方式0=点火遅角(最終進角から遅角量を引く。下限まで深く=大遅角も調整可)、方式1=本物の点火カット(コイル充電ハンドラ0x19D04をケーブで差し替え、発動中は充電スキップ=火花停止)。test_mode=1は車速ゲートだけ無視(クラッチ+回転+アクセルは生かす)=停車確認用。始動/アイドルは低回転で不発(クラッチ始動を妨げない)、停車Nで回転を上げると発動。パッチ適用済みROMでのみ表示。ベンチ検証用ドラフト、点火カットの効き/コイル過熱有無は実車でのみ確認。",
    "Vehicle Instrument Cluster - Speedometer": "スピードメーターの表示特性。タイヤ外径変更時の補正等。",
}


# グループ(カテゴリ先頭トークン)単位の汎用解説。LibreTuner の 124 カテゴリを
# 個別登録しなくても、主要グループには意味のある日本語解説を出すためのフォールバック。
GROUP_DESC = {
    "Spark Base": "基本点火時期(進角)系。回転数×負荷に対する点火時期。パワー・燃費・ノックに直結する最重要マップ群。",
    "Spark Comp": "点火時期の補正項(温度・EGR等の条件による進角/遅角)。",
    "Spark Correction": "点火時期の補正(ノック・加速・冷間など条件ごとの遅角/進角)。",
    "Spark Idle Limit": "アイドル時の点火時期リミット。アイドル安定に関係。",
    "Spark Idle Load": "アイドル負荷に対する点火。アイドル安定に関係。",
    "Spark Idle / Base Limit": "アイドル/ベースの点火上限。",
    "Spark Idle / Base Limit Correction": "アイドル/ベース点火上限の補正。",
    "Spark Base Limit": "点火時期の上限(進角側リミット)。安全側の制限。",
    "Spark Base Limit Comp": "点火ベース上限の補正。",
    "Spark Base Comp": "水温・吸気温などによる点火ベース補正。",
    "Spark Limits": "点火時期の上下限(保護)。",
    "Spark To Cylinders": "各気筒への点火割り当て。通常は変更不要。",
    "Fuel Target CL": "閉ループ時の目標空燃比(通常ストイキ=λ1付近)。基本は変更不要。",
    "Fuel Target OL": "開ループ(高負荷)時の目標空燃比。リッチ=安全・出力寄り/リーン=危険。体感と安全に直結。",
    "Warm-Up Fuel Target OL": "暖機時の目標空燃比(開ループ)。始動・暖機の安定に関係。",
    "Fuel IPW": "インジェクタ噴射パルス幅(燃料量の基礎)。インジェクタ変更時に調整。",
    "Fuel Comp CL": "閉ループ時の燃料補正(短期/長期トリム・触媒診断など)。",
    "Fuel Comp OL": "開ループ時の燃料補正(減速カット・高負荷リーン化・増量など)。",
    "Fuel Comp OL/CL": "開/閉ループ共通の燃料補正(LTFT・過渡増量など)。",
    "Fuel Status OL": "開ループ/閉ループの燃料状態と遷移条件。",
    "Fuel Status OL (Primary)": "一次側の開ループ燃料状態。",
    "Fuel Status OL (Secondary)": "二次側の開ループ燃料状態。",
    "Fuel Status OL Delay Reset (Secondary)": "二次側 開ループ遅延リセット条件。",
    "Fuel Status OL Delayed (Secondary)": "二次側 開ループ遅延条件。",
    "Idle Speed": "目標アイドル回転数。高さ・安定の調整。",
    "Idle Speed Comp": "アイドル回転数の補正(負荷条件など)。",
    "Idle Transition Delay": "アイドルへの移行遅延。",
    "Engine Sensors": "各センサ(水温・吸気温・エアフロ等)の特性・変換。狂うと制御全体がズレる。センサ変更時のみ。",
    "Engine Limiters": "レブリミット・速度リミッタ等の上限。",
    "Engine Load": "負荷(ロード)指標のスケーリング・上限。各マップの軸計算に影響する基礎。",
    "Engine Fan Control": "電動ファンの作動条件(水温・車速・A/C・アフタークーリング)。水温しきい値は℃ではなく水温センサ電圧のA/D値(値が大きいほど低い水温)。",
    "Emission System": "排出ガス関連(触媒温度推定・EGR・EVAP)。本ツールでは変更の対象外(参照用)。",
    "DBW": "電子スロットル(ドライブバイワイヤ)。目標開度・レスポンスに関係。",
    "Data Integrity Checks": "各制御値の整合性(フェイルセーフ)判定。安全側の保護。通常は変更しない。",
    "Data Integrity Thresholds": "整合性判定のしきい値。保護用。通常は変更しない。",
    "DTC Flags B": "ダイアグコード(DTC)の有効/無効フラグ。",
    "DTC Thresholds": "DTC(故障コード)の判定しきい値。診断と保護のための値で、本ツールでは変更の対象外(参照用)。",
    "Variable Cam Timing": "可変バルブタイミング(VVT)の目標角。トルク特性に影響。",
    "Ignition Coil Dwell Time": "点火コイルの通電時間(ドウェル)。コイル変更時に関係。",
    "Gear Ratio": "各ギアのギア比(推定)。ギア判定に使用。",
    "Intake Manifold Runner Control (AT Only)": "可変吸気(ランナー)制御(AT車のみ)。",
    "Intake Manifold Tuning Valve": "可変吸気バルブ(IMTV)の制御。切替回転数など。",
    "Patch": "ROM改変パッチ項目(イモビ無効・排気量・DFCO等)。取り扱い注意。",
    "WIP": "作業中(未確定)の項目。",
}


def _group_of(en: str) -> str:
    return en.split(" - ", 1)[0].strip()


# 英語モード用のグループ解説/効果(主要グループのみ。無ければ空=英語カテゴリ名で十分)。
EN_GROUP_DESC = {
    "Spark Base": "Base ignition timing (advance) vs RPM x load. Key map for power/economy/knock.",
    "Spark Comp": "Ignition timing compensations (temperature, EGR, etc.).",
    "Spark Correction": "Ignition corrections (knock, tip-in, cold, etc.).",
    "Spark Limits": "Upper/lower spark-timing clamps (protection).",
    "Spark Base Limit": "Advance-side spark limit (safety margin).",
    "Fuel Target CL": "Closed-loop target AFR (normally stoich/lambda 1).",
    "Fuel Target OL": "Open-loop (high-load) target AFR. Rich=safe/power, lean=risky.",
    "Fuel IPW": "Injector pulse width (fuel quantity). Set when changing injectors.",
    "Fuel Comp OL": "Open-loop fuel comps (decel cut, power enleanment, enrichment).",
    "Fuel Comp CL": "Closed-loop fuel comps (short/long trims, cat checks).",
    "Fuel Comp OL/CL": "Shared fuel comps (LTFT, transient enrichment).",
    "Idle Speed": "Target idle speed.",
    "Engine Sensors": "Sensor transfer functions. Adjust only when changing sensors/intake.",
    "Engine Limiters": "Rev/speed limiters.",
    "Engine Load": "Load metric scaling/limits (axis of most maps).",
    "Engine Fan Control": "Electric fan control (coolant, vehicle speed, A/C, after-cooling). Coolant thresholds are ECT-sensor A/D counts, not °C (a larger value = a lower temperature).",
    "Variable Cam Timing": "VVT target angle. Affects torque curve.",
    "Ignition Coil Dwell Time": "Coil charge time. Match to coil when changed.",
    "DBW": "Electronic throttle (drive-by-wire) mapping/response.",
    "Data Integrity Checks": "ETC/torque safety-monitor plausibility (fail-safe). Keep in sync with the control maps.",
    "Data Integrity Thresholds": "Fail-safe decision thresholds. Normally leave alone.",
    "Patch": "ROM code patches (immobilizer disable, displacement, DFCO, etc.). Handle with care.",
}
EN_GROUP_EFFECT = {
    "Spark Base": "Advance=more torque/economy but knock risk; retard=safer but less power. Most critical.",
    "Fuel Target OL": "Rich=safe/power, lean=economy but dangerous at high load.",
    "Fuel IPW": "Higher=richer, lower=leaner. Match injector characteristics when changed.",
    "Engine Limiters": "Raises/lowers rev or speed limiter. Mind mechanical limits.",
    "Engine Fan Control": "Coolant thresholds are A/D counts: a higher value starts the fan at a LOWER temperature (earlier), a lower value later. Speed thresholds and timers are plain values.",
    "Idle Speed": "Higher=faster idle, lower=risk of stall.",
    "Data Integrity Checks": "Raise together with the control map or the ETC monitor trips fail-safe.",
    "Patch": "ROM modification; effect varies per item. Self-responsibility.",
}


# 英語モードのカテゴリ個別解説/効果(グループより優先)
EN_CATEGORY_DESC = {
    "Spark Base / Idle Transition": "Conditions that switch between idle spark and base (driving) spark: RPM thresholds etc.",
    "Spark Base - High Fuel Request Transition": "Boundary that selects the high- or low-fuel-request spark maps: the high side is used when the fuel request (enrichment in % over stoich) exceeds the threshold. Not advance values.",
    "Spark Idle Limit Correction - AC Cycle Transition": "Temporary idle-spark correction right after the A/C compressor cycles off (amount and duration count).",
    "Spark Idle Limit Correction - Idle Error": "Spark correction vs idle-speed error (actual minus target), used to stabilise idle.",
    "Spark Idle Limit Correction - PS Cycle Transition": "Temporary idle-spark correction right after the power-steering load cycles on/off (amount and duration count).",
    "WIP - Torque Model Bank (RE)": "Spark-efficiency torque-model tables (reverse-engineered): four sets of (factor k, MBT spark, torque) on RPM x load plus one RPM x coolant table. Axes and dimensions verified against the ECU table descriptors; role names are inferred from values and use.",
    "WIP - DBW Torque Coordinator (RE)": "Tables around the drive-by-wire torque coordination (reverse-engineered): pedal -> torque request (BMEP) -> target throttle, and the torque-request anti-jerk (a band-pass filter picks out the driveline shuffle and it is subtracted). Tables named (Control) have an identical monitor (Data Integrity) copy - always change both to the same values. Axes and dimensions verified against the ECU table descriptors.",
    "WIP - Fuel Comp Cut Pattern (RE)": "RPM x load tables for one fuel-enrichment term in % (RAM 0xFFFF75DC), reverse-engineered. Used only while a torque limit received over CAN (ID 0x211) is below the requested torque and fuel is cut on some cylinders to lower the torque. The cylinder-pattern state selects one of the three tables.",
    "Spark Correction - Tip-In Anti Lug": "Damps the driveline shuffle right after a tip-in with spark retard. The per-gear shuffle frequency (looked up from RPM / vehicle speed) selects the coefficients of a filter that picks the oscillation out of load, and the retard follows that oscillation.",
    "Emission System - Catalyst": "Catalyst temperature estimate. Emissions-related: not a tuning target in this tool (reference only).",
    "Emission System - EGR": "EGR control. Emissions-related: not a tuning target in this tool (reference only).",
    "Emission System - EVAP": "EVAP purge control. Emissions-related: not a tuning target in this tool (reference only).",
    "DTC Thresholds": "DTC decision thresholds. Diagnostic/protective values: not a tuning target in this tool (reference only).",
    "Patch - Flat Shift": (
        "Constants of the flat-shift patch (draft 6: scratch-free, read-only — no stable free RAM exists "
        "on this ECU). Acts while clutch pressed AND RPM>threshold AND APP>threshold AND speed>minimum "
        "(no RAM writes; the clutch dip is the window, RPM threshold caps it). Method 0 = ignition retard "
        "(subtract the retard amount from final advance, down to the floor = also big retard); Method 1 = "
        "true ignition cut (the coil-charge handler 0x19D04 is repointed to a cave that skips charging = "
        "no spark while active). test_mode=1 ignores ONLY the speed gate (clutch+RPM+APP still required) "
        "for a standstill check — won't fire at cranking/idle (low RPM) so starting is unaffected; rev in "
        "neutral to trigger. Shown only for patched ROMs. Draft; the cut effect and coil-overheat safety are "
        "confirmable only on-car."),
}
EN_CATEGORY_EFFECT = {
    "WIP - Fuel Comp Cut Pattern (RE)": "Higher = more fuel (richer) during the cylinder-cut torque reduction. Unused unless a CAN torque-limit request arrives. Leave them stock.",
    "WIP - DBW Torque Coordinator (RE)": "Torque request, target throttle and anti-jerk behaviour. (Control) tables must equal their monitor copies. The band-pass coefficients are a computed set - do not edit them individually.",
    "Spark Base - High Fuel Request Transition": "Higher threshold = switches to the high-fuel-request spark maps less readily; the advance values themselves do not change.",
    "Fuel Target OL - Base": "Values are enrichment in % over stoich (0 = stoich). Higher = richer (safer, power side); lower = leaner (dangerous at high load). Change only with wideband AFR measurements.",
    "Fuel IPW - Dynamic Trim Mult A (Large)": "Transient (wall-wetting) compensation coefficients: they change tip-in/tip-out mixture, not steady-state AFR. Normally stock.",
    "Fuel IPW - Dynamic Trim Mult B (Small)": "Transient (wall-wetting) compensation coefficients: they change tip-in/tip-out mixture, not steady-state AFR. Normally stock.",
    "Fuel IPW - Dynamic Trim Mult C": "Transient (wall-wetting) compensation multiplier: higher = more transient compensation; steady-state AFR unchanged. Normally stock.",
    "Spark Correction - Knock Retard": "Direction differs per table: retard amounts (KR Increment / Maximum) - higher = more protection; restore speed (KR Decrement Rate) - higher = returns to advance sooner = less protection; narrowing the Knock Listen RPM/load window leaves more of the range unmonitored; Delay - higher = slower restore.",
    "Patch - Flat Shift": (
        "Method 0=retard (gentler; more retard = bigger torque drop, lower floor = bigger retard), "
        "1=true cut (no coil charge = no spark; raw fuel to exhaust = backfire/high EGT). Active only "
        "while clutch pressed + gates hold (clutch dip sets the duration). Lower RPM/APP threshold = "
        "triggers earlier / on partial throttle; RPM threshold also acts as a cap. Higher speed minimum "
        "= inactive at low speed. No RAM writes, no window. test_mode=1 ignores only the speed gate "
        "(standstill check: won't fire at idle, rev in neutral to trigger; set 0 to drive)."),
}

# 定義に無い追加項目(ncecu のパッチモジュール)の説明: 番地 -> (日本語, 英語)
EXTRA_DESC = {
    0xC53B8: ("車速がこの値[km/h]未満のときだけ、クラッチ踏込時に『レブリミット スロットルカット | クラッチ踏込』"
              "(@0x0C53BC)が使われる(純正2.0=停車中のみ)。それ以上の車速では CPP clear(10000rpm)側になる。",
              "The 'Rev Limit Throttle Cut | CPP set' (@0x0C53BC) applies with the clutch pressed only "
              "below this vehicle speed [km/h] (stock 2.0 = standstill only). Above it the CPP clear "
              "limit (10000 rpm) is used."),
    0xC53C4: ("スロットルカット成立中は、回転が『リミット−この値』を下回るまで解除しない(純正100rpm)。",
              "Once active, the throttle cut stays until RPM falls below the limit minus this value "
              "(stock 100 rpm)."),
    0xDE300: ("アクセル開度がこの値[%]を超えていること。0〜100。", "APP must exceed this value [%]. 0-100."),
    0xDE304: ("エンジン回転がこの値[rpm]を超えていること。1000〜8000(低回転テストは下げる)。",
              "RPM must exceed this value [rpm]. 1000-8000 (lower for low-RPM testing)."),
    0xDE308: ("車速がこの値[km/h]を超えていること。停車中(ローンチ側)と分ける。0〜250。",
              "Vehicle speed must exceed this value [km/h], to separate from standstill/launch. 0-250."),
    0xDE30C: ("点火遅角方式で最終進角から引く量[°]。下限(@0xDE310)まで深く引ける=大遅角もこれで調整。0〜60。",
              "Retard method: degrees subtracted from final advance, down to the floor (@0xDE310). 0-60."),
    0xDE310: ("点火遅角方式の下限=最小進角[°]。負=ATDC。純正の最大リタードに縛られず深く引ける。-30〜20。",
              "Retard method floor = minimum advance [deg] (neg=ATDC; past the stock max-retard limit). -30..20."),
    0xDE314: ("方式: 0=点火遅角 / 1=本物の点火カット(発動中コイル充電を止めて火花停止)。",
              "Method: 0=ignition retard / 1=true ignition cut (suppress coil charge = no spark while active)."),
    0xDE318: ("デバッグ test_mode: 1=車速ゲートだけ無視し、クラッチ+回転+アクセルで発動(停車確認用)。始動/アイドルは低回転で不発=クラッチ始動を妨げない、停車Nで回転を上げると発動。走行時は0に戻すこと。",
              "Debug test_mode: 1=ignore only the speed gate (clutch+RPM+APP still required); standstill "
              "check — won't fire at cranking/idle (low RPM), rev in neutral to trigger. Set 0 to drive."),
}
# 追加項目の単位(名前からの推定より優先)
EXACT_UNITS = {
    "Rev Limit Throttle Cut | CPP set - Vehicle Speed Threshold": "km/h",
    "Rev Limit Throttle Cut | CPP set - Hysteresis": "rpm",
    "Flat Shift - APP Threshold": "%",
    "Flat Shift - RPM Threshold": "rpm",
    "Flat Shift - Vehicle Speed Minimum": "km/h",
    "Flat Shift - Retard Amount [deg]": "°",
    "Flat Shift - Min Advance Floor [deg]": "°",
}


# 定義(LibreTuner / 逆解析で追加した表)に対する補足: 番地 -> (日本語, 英語)。2026-11-16 の全表監査で、
# 定義名どおりに読めない表・写しのある表・この ROM では無効な定義に付けた。
_CTRL = ("制御側の表。安全監視(Data Integrity)側に同じ値の写し %s がある。変えるときは必ず両方を同じ値にする。",
         "Control-side table. The monitor (Data Integrity) copy at %s holds the same values - always change both together.")
_SET = ("トルクモデルの組 %s(係数k / MBT点火 / トルク)。0x3C7xx で3枚を続けて引く。",
        "Torque-model set %s (factor k / MBT spark / torque): the three are looked up together at 0x3C7xx.")
TABLE_NOTES = {
    0xD4288: ("値は目標λではなく、理論空燃比からの燃料増量(%)。回転×負荷で引いた値(RAM 0xFFFF7844)に条件の補正を足して 0xFFFF7828 とし、"
              "ほかの増量項と合計した Σ%(0xFFFF782C)から閉ループの目標λ = 100 ÷ (100 + Σ%) を作る(0x4B5B0)。ほかの項が 0 なら 0.5 → λ0.995、1.32 → λ0.987。"
              "値↑ = 目標が濃くなる。0xFFFF7346 のビット 2 が立っているときは使わない(0 扱い)。",
              "Not a lambda target: the values are fuel enrichment in % over stoich. The looked-up value (RAM 0xFFFF7844) plus condition offsets becomes 0xFFFF7828; "
              "summed with the other enrichment terms (0xFFFF782C) it gives the closed-loop target lambda = 100 / (100 + sum%) (0x4B5B0). With the other terms at 0, 0.5 -> lambda 0.995, 1.32 -> lambda 0.987. "
              "Higher = richer target. Not used (treated as 0) while bit 2 of 0xFFFF7346 is set."),
    0xBF9F6: ("ファンの段が変わったときに入れ直す待ちカウント(RAM 0xFFFFA002)。25ms ごとに 1 減る(0x9920A)。120 = 3.0 秒。"
              "1 カウントの時間は OS のタスク周期(1ms 割り込み → 5ms → その 5 回に 1 回 = 25ms)。1ms 刻みと 25ms のサブタスクは"
              "実車で確認した(2026-11-17、キーON・エンジン停止で、10ms ごとの CAN フレームと ECU のカウンタを比べた)。"
              "ファンが段を変えるまでの実際の時間は測っていない。",
              "Wait count reloaded when the fan stage changes (RAM 0xFFFFA002); it drops by 1 every 25 ms (0x9920A). 120 = 3.0 s. "
              "The count period is the OS task period (1 ms interrupt -> 5 ms -> every 5th = 25 ms). The 1 ms tick and the 25 ms "
              "sub-task were confirmed on the car (2026-11-17, key on / engine off, ECU counters against the 10 ms CAN frames); "
              "the actual fan stage-change delay has not been timed."),
    0xCE38A: ("この番地は 0xFFFF の詰め物で、コードから参照されていない(この ROM では無効な定義)。編集しても効果はない。隣の 0xCE388 / 0xCE389 は 1 と比較されるモードフラグ。",
              "This address holds 0xFFFF padding and is not referenced by the code (invalid definition for this ROM); editing it has no effect. The neighbours 0xCE388 / 0xCE389 are mode flags compared with 1."),
    0xCE390: ("名前は Lambda だが、比較相手は燃料要求の増量%(RAM 0xFFFF7728)。6.25 は 6.25% の意味。",
              "Named Lambda, but it is compared with the fuel-request enrichment in % (RAM 0xFFFF7728): 6.25 means 6.25 %."),
    0xC49CC: ("横軸は回転数(定義の軸名は LOAD_7004 だったが、表引きの入力は回転数。0x42206 で確認)。",
              "The axis is engine speed (the definition named it LOAD_7004, but the look-up input is RPM; checked at 0x42206)."),
    0xC16D8: (_SET[0] % "1 = 01 / 02 / 03", _SET[1] % "1 = 01 / 02 / 03"),
    0xC1AC4: (_SET[0] % "1 = 01 / 02 / 03", _SET[1] % "1 = 01 / 02 / 03"),
    0xC1EB0: (_SET[0] % "1 = 01 / 02 / 03", _SET[1] % "1 = 01 / 02 / 03"),
    0xC229C: (_SET[0] % "2 = 04 / 07 / 10", _SET[1] % "2 = 04 / 07 / 10"),
    0xC2E60: (_SET[0] % "2 = 04 / 07 / 10", _SET[1] % "2 = 04 / 07 / 10"),
    0xC3A24: (_SET[0] % "2 = 04 / 07 / 10", _SET[1] % "2 = 04 / 07 / 10"),
    0xC2688: (_SET[0] % "3 = 05 / 08 / 11", _SET[1] % "3 = 05 / 08 / 11"),
    0xC324C: (_SET[0] % "3 = 05 / 08 / 11", _SET[1] % "3 = 05 / 08 / 11"),
    0xC3E10: (_SET[0] % "3 = 05 / 08 / 11", _SET[1] % "3 = 05 / 08 / 11"),
    0xC2A74: (_SET[0] % "4 = 06 / 09 / 12", _SET[1] % "4 = 06 / 09 / 12"),
    0xC3638: (_SET[0] % "4 = 06 / 09 / 12", _SET[1] % "4 = 06 / 09 / 12"),
    0xC41FC: (_SET[0] % "4 = 06 / 09 / 12", _SET[1] % "4 = 06 / 09 / 12"),
    0xC45C4: ("回転×水温の表。0x3DB44 で、いまの水温の値と 80℃ の値を続けて引く(差を使う補正と推定)。値の単位は未確認。",
              "RPM x coolant table. At 0x3DB44 it is looked up at the current coolant temperature and again at 80 C (presumably a correction from the difference). Unit unconfirmed."),
}

_AC = ("アフタークーリングのファンタイマ。100ms ごとに 1 減る(0x993D4 / 0x9932C。25ms のサブタスクの 4 回に 1 回)。%s"
       "1 カウントの時間は OS のタスク周期から求めた値(1ms 刻みと 25ms のサブタスクは実車で確認、100ms はその 4 回に 1 回)。"
       "キーOFF後に実際にファンが回る時間は測っていない。",
       "After-cooling fan timer; it drops by 1 every 100 ms (0x993D4 / 0x9932C, every 4th run of the 25 ms sub-task). %s"
       "The count period comes from the OS task period (1 ms tick and 25 ms sub-task confirmed on the car; 100 ms = every 4th run). "
       "The actual after-cooling run time has not been timed.")
TABLE_NOTES.update({
    0xBFA06: (_AC[0] % "225 = 22.5 秒。", _AC[1] % "225 = 22.5 s. "),
    0xBFA08: (_AC[0] % "750 = 75 秒。", _AC[1] % "750 = 75 s. "),
    0xBFB80: (_AC[0] % "大気圧(54〜109kPa)で引く。900 = 90 秒。", _AC[1] % "Looked up by barometric pressure (54-109 kPa). 900 = 90 s. "),
    0xBFBB0: (_AC[0] % "大気圧(54〜109kPa)で引く。0 = 0 秒。", _AC[1] % "Looked up by barometric pressure (54-109 kPa). 0 = 0 s. "),
    0xC045C: ("値はギアごとの駆動系しゃくり(前後振動)の振動数[Hz]:1速 2.55 / 2速 3.75 / 3速 4.44 / 4速 5.4 / 5速 5.6 / 6速 6.29。"
              "回転数÷車速(RAM 0xFFFF7A18)で引いて 0xFFFF7A0C に入れ、しゃくり振動フィルタ係数(0xC0B38 ほか)と、トルク要求の振動抑制の帯域フィルタ(0xC65D4 ほか)の中心周波数に使う。",
              "The values are the per-gear driveline shuffle frequency [Hz]: 1st 2.55 / 2nd 3.75 / 3rd 4.44 / 4th 5.4 / 5th 5.6 / 6th 6.29. "
              "Looked up by RPM / vehicle speed (RAM 0xFFFF7A18) into 0xFFFF7A0C; it selects the shuffle-filter coefficients (0xC0B38 etc.) and the centre frequency of the torque-request anti-jerk band-pass (0xC65D4 etc.)."),
})
_LUG = ("急開時アンチラグ(点火遅角)の振動抽出フィルタの係数 %s。帯域フィルタ H(s)=2ζωs/(s²+2ζωs+ω²) を ζ=1.25、ω=2π×しゃくり振動数(縦軸)、"
        "T=燃焼 1 回の時間(30÷回転数 秒)で離散化した値と一致する(例 2Hz・1000rpm: b0=0.5962 / a1=−1.2987 / a2=0.3897。500rpm と 5000rpm の列、1Hz の行は隣と同じ値)。"
        "入力は負荷(0.1〜2.0 に制限)、振動成分÷入力 × 0.25(0xC0444)を遅角の計算に使う(0x4CC9E)。3 枚で 1 組の計算値なので、個別に変えない。",
        "Coefficient %s of the oscillation filter of the tip-in anti-lug (spark retard). The values match the band-pass H(s)=2*zeta*w*s/(s^2+2*zeta*w*s+w^2) discretised with zeta=1.25, "
        "w=2*pi*shuffle frequency (Y axis) and T = one combustion interval (30/RPM s) (e.g. 2 Hz, 1000 rpm: b0=0.5962 / a1=-1.2987 / a2=0.3897; the 500 / 5000 rpm columns and the 1 Hz row repeat their neighbours). "
        "Input is load (clamped 0.1-2.0); oscillation / input x 0.25 (0xC0444) feeds the retard (0x4CC9E). The three are one computed set - do not edit them individually.")
for _a, _k in ((0xC0B38, "b0"), (0xC0CC0, "a1"), (0xC0E48, "a2")):
    TABLE_NOTES[_a] = (_LUG[0] % _k, _LUG[1] % _k)
_BPF = ("トルク要求の振動抑制: 運転者のトルク要求(RAM 0xFFFF3858)から駆動系しゃくりの振動数の成分を取り出す 2 次の帯域フィルタの係数 %s。"
        "中心周波数 = 横軸(しゃくり振動数 Hz)、Q = 縦軸(使うのは定数 0x%05X = 0.3)。5ms 周期で計算すると中心周波数で利得 1 になる(0x%05X)。"
        "取り出した成分にゲインを掛けてトルク要求から差し引く(0xFFFF382C)。5 枚で 1 組の計算値なので、個別に変えない。",
        "Torque-request anti-jerk: coefficient %s of the 2nd-order band-pass that picks the driveline-shuffle frequency out of the driver torque request (RAM 0xFFFF3858). "
        "Centre frequency = X axis (shuffle Hz), Q = Y axis (the code uses the constant 0x%05X = 0.3). Evaluated every 5 ms it has unity gain at the centre frequency (0x%05X). "
        "The extracted part, times a gain, is subtracted from the torque request (0xFFFF382C). The five are one computed set - do not edit them individually.")
for _c, _m, _k in ((0xC65D4, 0xF9A0C, "b0"), (0xC66CC, 0xF9B04, "b1"), (0xC67C4, 0xF9BFC, "b2"), (0xC68BC, 0xF9CF4, "a1"), (0xC69B4, 0xF9DEC, "a2")):
    TABLE_NOTES[_c] = (_BPF[0] % (_k, 0xC5358, 0x971A8), _BPF[1] % (_k, 0xC5358, 0x971A8))
    TABLE_NOTES[_m] = (_BPF[0] % (_k, 0xF7654, 0xB0578), _BPF[1] % (_k, 0xF7654, 0xB0578))
_GAIN = ("トルク要求の振動抑制のゲイン。横軸 = ギア(RAM 0xFFFF7A04、0 = ギアが入っていない)、縦軸 = 踏み込みの段階(RAM 0xFFFF79FC: 0 = なし、"
         "1 = 踏み込み量 8 以下、2 = 8〜15、3 = 15 以上。しきい値 0xC0428 / 0xC042C)。値↑ = 振動を強く抑える(加速の出だしが鈍くなる方向)。",
         "Torque-request anti-jerk gain. X = gear (RAM 0xFFFF7A04, 0 = not engaged), Y = tip-in stage (RAM 0xFFFF79FC: 0 = none, "
         "1 = pedal step up to 8, 2 = 8-15, 3 = 15 or more; thresholds 0xC0428 / 0xC042C). Higher = stronger damping (a softer initial response).")
TABLE_NOTES[0xC6AA0] = _GAIN
TABLE_NOTES[0xF9ED8] = _GAIN
_CUT = ("燃料の増量%%の 1 項(RAM 0xFFFF75DC)。ほかの増量項と合計して噴射量に掛ける(0x45A3C)。回転×負荷(0xFFFF6EC8)で引き、0xFFFF7064 が立っているときだけ使う(0 なら 0%%)。"
        "0xFFFF7064 が立つのは、CAN(ID 0x211)のフレームの先頭 2 バイト − 10000 のトルク上限(RAM 0xFFFF7024)が要求トルク(0xFFFF7018)を下回り、一部の気筒の燃料を止めてトルクを下げるとき"
        "(0x3D140)。止める段階は上限と 0xFFFF7004 / 7008 / 700C の比較で決まる。フレームが来ない(20 回途切れる)と上限は 0xFFFF − 10000 = 55535 で、使われない。"
        "%s 747D は燃料カットの気筒パターン(0xC4D84〜)から決まる。実車では 0x211 が約 100 回/秒で流れていて、ふだんの値は 0xFFFF(上限なし)(2026-11-17 の読み出し)。送り手は DSC/TCS などと推定(未確認)で、介入したときだけ上限が下がると見られる。",
        "One fuel-enrichment term in %% (RAM 0xFFFF75DC), summed with the others and applied to the injection amount (0x45A3C). Looked up by RPM x load (0xFFFF6EC8), used only while 0xFFFF7064 is set (otherwise 0 %%). "
        "0xFFFF7064 is set when the torque limit (RAM 0xFFFF7024 = first 2 bytes of CAN frame ID 0x211 - 10000) is below the requested torque (0xFFFF7018) and fuel is cut on some cylinders to lower the torque (0x3D140); "
        "the cut stage comes from comparing the limit with 0xFFFF7004 / 7008 / 700C. Without the frame (20 misses) the limit is 0xFFFF - 10000 = 55535 and the tables are unused. "
        "%s 747D comes from the fuel-cut cylinder pattern (0xC4D84...). On the car 0x211 arrives about 100 times/s and normally reads 0xFFFF (no limit) (read on 2026-11-17). The sender is presumably DSC/TCS (not confirmed); the limit should drop only when it intervenes.")
TABLE_NOTES[0xC4DFC] = (_CUT[0] % "A は RAM 0xFFFF747D = 0 のとき(値 38〜56%)。", _CUT[1] % "A: when RAM 0xFFFF747D = 0 (38-56 %).")
TABLE_NOTES[0xC4F98] = (_CUT[0] % "B は 747D ≠ 0 のとき(値 +23〜−9%)。", _CUT[1] % "B: when 747D != 0 (+23 to -9 %).")
TABLE_NOTES[0xC5134] = (_CUT[0] % "C は 747D ≠ 0 かつ RAM 0xFFFF5255 = 1 のとき(値 −4〜−9.5%)。", _CUT[1] % "C: when 747D != 0 and RAM 0xFFFF5255 = 1 (-4 to -9.5 %).")

# 制御側と安全監視(Data Integrity)側の写しの組 (制御, 監視)。寸法・軸・値は ROM 3本(実車純正・ベンチ原本・運用中)とも
# 同じで、読むコードも別(制御=0x40xxx/0x95〜0x97xxx/0xD6xxx 系、監視=0xAF〜0xB1xxx 系)。2026-11-16 確認。
# どちらの表を開いても、説明欄に相方の番地を出す。
CONTROL_MONITOR_PAIRS = (
    (0xC7EE4, 0xF7C90), (0xC81B4, 0xF7F60), (0xC8484, 0xF8230), (0xC8754, 0xF8500), (0xC8A24, 0xF87D0),  # 目標スロットル 1/2/3/4-6速/N
    (0xC5710, 0xF8B48), (0xC5E1C, 0xF9254), (0xC6BC8, 0xFA000), (0xC7400, 0xFA838),                      # 車速倍率・BMEP 3面
    (0xC55B4, 0xF7BDC), (0xC55FC, 0xF7C24), (0xC5644, 0xF7C6C),                                          # スロットル指令 スケーリング/最大/最小
    (0xC7D7C, 0xF7930), (0xC7E0C, 0xF79C0), (0xC7E9C, 0xF78A0),                                          # APP→目標スロットル 最大/最小/WIP
    (0xD6C9C, 0xF4DEC), (0xD6CDC, 0xF4E2C),                                                              # アイドル目標 走行/非走行
    (0xC65D4, 0xF9A0C), (0xC66CC, 0xF9B04), (0xC67C4, 0xF9BFC), (0xC68BC, 0xF9CF4), (0xC69B4, 0xF9DEC),  # 振動抑制 帯域フィルタ係数
    (0xC6AA0, 0xF9ED8),                                                                                  # 振動抑制 ゲイン
)
_MON = ("安全監視(Data Integrity)側の表。制御側に同じ値の写し %s がある。変えるときは必ず両方を同じ値にする"
        "(片方だけだと監視が不一致を検出する)。",
        "Monitor (Data Integrity) table. The control-side copy at %s holds the same values - always change both together "
        "(changing one side only makes the monitor detect a mismatch).")
for _c, _m in CONTROL_MONITOR_PAIRS:
    for _a, _p, _t in ((_c, _m, _CTRL), (_m, _c, _MON)):
        _pj, _pe = _t[0] % ("0x%05X" % _p), _t[1] % ("0x%05X" % _p)
        if _a in TABLE_NOTES:          # 固有の説明があれば、その後ろに相方の番地を足す
            TABLE_NOTES[_a] = (TABLE_NOTES[_a][0] + " " + _pj, TABLE_NOTES[_a][1] + " " + _pe)
        else:
            TABLE_NOTES[_a] = (_pj, _pe)


def table_desc(t) -> str:
    """テーブル固有の説明。逆解析で付けた説明(日英。追加項目・TABLE_NOTES)があればそれを現在の言語で出す。
    定義(LibreTuner)由来の desc は英文なので、英語表示のときだけ後ろに付ける(日本語表示では英文で
    日本語の説明が隠れていた: Idle Speed - Base の制御側 2 表)。"""
    d = EXTRA_DESC.get(getattr(t, "address", None)) or TABLE_NOTES.get(getattr(t, "address", None))
    desc = getattr(t, "desc", "") or ""
    if d:
        txt = d[1] if _LANG == "en" else d[0]
        if desc and _LANG == "en" and desc not in txt:
            txt += " " + desc
        return txt
    return desc


def describe_category(en: str) -> str:
    if en is None:
        return ""
    s = en.strip()
    g = _group_of(s)
    if _LANG == "en":
        return EN_CATEGORY_DESC.get(s) or EN_GROUP_DESC.get(g, "")
    if s in CATEGORY_DESC:
        return CATEGORY_DESC[s]
    if g in GROUP_DESC:
        return GROUP_DESC[g]
    return "(このカテゴリの解説は未登録です)"


# 軸名の接頭辞 → (日本語ラベル, 英語ラベル, 単位)
AXIS = {
    "RPM": ("回転数", "Engine RPM", "rpm"),
    "RPMSUB": ("回転数(副)", "RPM (sub)", "rpm"),
    "ECT": ("水温", "Coolant", "°C"),
    "LOAD": ("エンジン負荷", "Engine Load", ""),
    "APP": ("アクセル開度", "Pedal (APP)", "%"),
    "TP": ("スロットル開度", "Throttle (TP)", "%"),
    "THROTTLE": ("スロットル開度", "Throttle", "%"),
    "TPS": ("スロットル開度", "Throttle (TPS)", "%"),
    "VSS": ("車速", "Vehicle Speed", "km/h"),
    "MAF": ("吸入空気量", "MAF", "g/s"),
    "BARO": ("大気圧", "Baro", "kPa"),
    "MAP": ("吸気圧", "MAP", "kPa"),
    "MANIFOLD": ("吸気(マニホールド)", "Manifold", "kPa"),
    "IAT": ("吸気温", "Intake Air", "°C"),
    "IDLE": ("アイドル", "Idle", ""),
    "ALT": ("オルタネータ", "Alternator", ""),
    "GEAR": ("ギア", "Gear", ""),
    "CTRLMOD": ("制御電圧", "Module V", "V"),
    "VCT": ("カム角", "Cam Angle", "°"),
    "SPARK": ("点火時期", "Spark", "°"),
    "KS": ("ノック", "Knock", ""),
    "CAT": ("触媒温度", "Catalyst", "°C"),
    "EGRP": ("EGR位置", "EGR Pos", ""),
    "OCV": ("OCV", "OCV", ""),
    "EQ": ("当量比", "EQ Ratio", ""),
    "REQ": ("要求", "Request", ""),
    "DIFF": ("差分", "Delta", ""),
    "CONST": ("定数", "Const", ""),
    "COUNTER": ("カウンタ", "Counter", ""),
    "INTERP": ("補間", "Interp", ""),
    "FUEL": ("燃料", "Fuel", ""),
    "O": ("O2", "O2", ""),
    "ETHANOL": ("エタノール濃度", "Ethanol", "%"),
    "ETC": ("電子スロットル", "ETC", ""),
    # 軸名 "FFFF_xxxx" は「入力が RAM 0xFFFFxxxx の変数(名前未特定)」の意味で、未使用ではない。
    # 番地つきの表示は _ffff_axis() が行う(ここは番地が読めない場合の予備)。
    "FFFF": ("RAM変数(未特定)", "RAM variable (unidentified)", ""),
}

# 軸名の接頭辞が物理量と一致しない(LibreTuner命名の都合)軸の明示ラベル。
# 単純な先頭トークン推定(_axis_pref)より先に、接頭辞の前方一致で判定する。
# (キーは大文字。name.upper().startswith(key) で照合)
AXIS_SPECIAL = {
    # 名称は "THROTTLE_DUTY..." だが、値域 0〜23000+ が示す通り実体は推定体積流量(内部値)。
    # 使用テーブル: "Estimated Volumetric Flow to Throttle Duty Aggregate Compensation"
    "THROTTLE_DUTY_COMBINED_COMP_RAW": ("推定体積流量(内部値)", "Est. Volumetric Flow (raw)", ""),
    # 回転数/車速 × 係数 = 算出ギア比。使用テーブル: "...Calculated Gear..."
    "RPM/VSS": ("算出ギア(回転数/車速)", "Calc Gear (RPM/speed)", ""),
    # 名称は "TP_ACT"(スロットル位置)だが、値 500〜7500(step 500)が示す通り実体は回転数。
    # 使用テーブル: "TP factor for Estimated MAF"。他の TP_* 軸(TP_6CF8 等)は本物のスロットル%。
    "TP_ACT": ("回転数", "Engine RPM", "rpm"),
    # センサ変換表(電圧→温度)の入力軸はセンサ電圧。接頭辞 ECT/IAT で温度(°C)に誤判定される。
    # "ECT_V_…"/"IAT_V_…" はこの変換表1本のみで、他の ECT_6D44 等(=水温°C)には一致しない。
    "ECT_V": ("電圧", "Voltage", "V"),
    "IAT_V": ("電圧", "Voltage", "V"),
    "MAF_V": ("電圧", "Voltage", "V"),
    # 定数名だが中身は水温ブレークポイント(-40〜100°C)。安全監視 目標アイドル回転ベース2本専用。
    "CONST_80": ("水温", "Coolant", "°C"),
    # A/Fセンサ変換表(電流→当量比)の入力軸はセンサ電流[mA](当量比ではない)。
    # "EQ_RATIO_ACT_MA_…" はこの2本のみ。他の EQ_* 軸(当量比)には一致しない。
    "EQ_RATIO_ACT_MA": ("電流", "Current", "mA"),
    # 内部名 "2500/IMRC_DIVISOR_82DC" は IMRC 移行アキュムレータを 0〜100 に正規化した移行進捗。
    # 使用テーブル: "IMRC Transition - Interpolation Bias"(0=旧ポート,100=新ポートへ完全移行)。
    "2500/IMRC_DIVISOR": ("IMRC移行進捗", "IMRC transition progress", "%"),
    # IDLE_* 軸は既定だと接頭辞 "IDLE"→"アイドル" で全て同じ表示になり区別できない。
    # 物理量ごとに別ラベルを与える。startswith 判定のため具体的なキーを先に並べる
    # (IDLE_SPEED_TRIM を IDLE_SPEED より前に置く)。
    # 差・偏差・派生量の軸。接頭辞だけで判定すると元の量(車速/回転数/水温…)と同じ表示になり、
    # 値域(負の値や 0〜3 のモード番号)と合わない。名前に書いてある内容で表示する(2026-11-16 監査)。
    "IDLE_SPEED_7044 - RPM": ("目標アイドル−回転数", "Idle target minus RPM", "rpm"),
    "RPM_6DD8 - IDLE_SPEED": ("回転数−目標アイドル", "RPM minus idle target", "rpm"),
    "VSS_DELTA": ("車速偏差(目標との差)", "Speed error", "km/h"),
    "VSS_INTERPOLATED": ("車速系の内部値(単位未確認)", "Speed-related internal value (unit unverified)", ""),
    "BARO - ((IAT": ("空気密度の指標(大気圧と吸気温から)", "Air-density term (baro, IAT)", ""),
    "VCT_ERR_ACCUM": ("VCT誤差の累積", "VCT error (accumulated)", ""),
    "ECT_START": ("始動時水温", "Coolant at start", "°C"),
    "ECT_AT_START": ("始動時水温", "Coolant at start", "°C"),
    "APP_DELTA_MODE": ("アクセル変化モード", "APP delta mode", ""),
    "FUEL_TARGET": ("目標燃料(増量)", "Fuel target (enrichment)", ""),
    "O2S12_V": ("リアO2センサ電圧", "Rear O2 sensor voltage", "V"),
    "REQ_TORQUE": ("要求トルク", "Requested torque", "N·m"),
    "DIFF_FUEL_PRESSURE": ("燃料差圧(単位未確認)", "Differential fuel pressure (unit unverified)", ""),
    "EGRP_STEPS": ("EGR位置(実/目標の比)", "EGR position (actual/target)", ""),
    "ALT_AMPS": ("オルタネータ電流", "Alternator current", "A"),
    "ALT_RPM": ("オルタネータ回転数", "Alternator speed", "rpm"),
    "ALT_TEMP": ("オルタネータ温度(補正後)", "Alternator temp (corrected)", "°C"),
    "ALT_SENSOR_V_DELTA_RATIO": ("オルタ電流センサ電圧の変化比", "Alt sensor-voltage delta ratio", ""),
    "INTERP_ALT_FIELD_CONTROL_DUTY": ("オルタ界磁デューティ(補間)", "Alt field duty (interp.)", "%"),
    "APP_SCALED": ("アクセル開度(スケール後)", "APP (scaled)", "%"),
    "AX_GEN": ("軸(入力未特定)", "Axis (input unidentified)", ""),
    # 2026-11-16 の逆解析で中身が分かった軸(以前は AX_GEN)。
    "SHUFFLE_HZ": ("駆動系のしゃくり振動数", "Driveline shuffle frequency", "Hz"),   # RAM 0xFFFF7A0C(ギア別、0xC045C)
    "BPF_Q": ("帯域フィルタのQ値", "Band-pass Q", ""),                           # 使うのは定数 0xC5358 = 0.3
    "GEAR_ENGAGED": ("ギア(0=未接続)", "Gear (0 = not engaged)", ""),             # RAM 0xFFFF7A04
    "TIPIN_STAGE": ("踏み込みの段階(0〜3)", "Tip-in stage (0-3)", ""),             # RAM 0xFFFF79FC
    "IDLE_ERROR": ("アイドル回転偏差", "Idle Speed Error", "rpm"),      # 実回転−目標(±rpm)
    "IDLE_LOAD": ("アイドル負荷", "Idle Load", ""),                      # 0〜1 正規化負荷
    "IDLE_SPEED_TRIM": ("アイドル回転トリム位置", "Idle Speed Trim Pos", ""),
    "IDLE_SPEED": ("アイドル回転数", "Idle Speed", "rpm"),               # 500〜1500rpm
    # LOAD_DELTA_* は負荷“レベル”ではなく負荷の変化量(ΔLoad)。既定の "LOAD"→"エンジン負荷" だと
    # 絶対負荷と区別できない。減速復帰の踏み直し量判定などに使う。他の LOAD_*(絶対負荷)には不一致。
    "LOAD_DELTA": ("負荷変化量", "Load Delta", ""),
}


# "FFFF_xxxx" 軸。名前の数字は LibreTuner が使った別 ROM の RAM 番地で、この ROM の番地ではない
# (ずれ幅は場所で違う)。2026-11-16 にこの ROM のコードで入力を確かめた(tools/gen_axis_ram.py)。
# 中身が分かったもの(コメントはこの ROM での実番地と根拠):
_FFFF_KNOWN = {
    "6800": ("オルタネータ回転数", "Alternator speed", "rpm"),                  # 0xFFFF67A0 = 回転数 × 0xD81E4(0x2F658)
    "6808": ("オルタネータ温度(補正後)", "Alternator temp (corrected)", "°C"),   # 0xFFFF67A8(= ALT_TEMP_CORRECTED_6808)
    "680C": ("吸気温(オルタ制御用)", "IAT (alternator control)", "°C"),         # 0xFFFF67AC = 吸気温。センサ故障時 0xD81FC(0x2F7D4)
    "67FC": ("電源電圧の最低値", "Minimum supply voltage", "V"),                 # 0xFFFF679C = min(電源電圧 0xFFFF6C60 + 0.11)(0x2EF72)
    "6850": ("アイドルへの到達率(0〜1)", "Idle approach ratio (0-1)", ""),       # 0xFFFF67F0 = (回転数−水温別下限)/(目標アイドル−下限)(0x3019C)
    "8154": ("オルタ界磁デューティ(補間)", "Alt field duty (interp.)", "%"),     # 監視側。= INTERP_ALT_FIELD_CONTROL_DUTY_8154
    "788F": ("MAFステージ(0〜3)", "MAF stage (0-3)", ""),                        # 0xFFFF7861(1 バイト)
    # 2026-11-17 追加
    "6C44": ("パージの立ち上げ量(内部値)", "Purge ramp-in (internal)", ""),        # 0xFFFF6BE0: 1367 ずつ増やし 15039 で止める(0x37526)
    "7530": ("吸気負圧(大気圧−吸気圧)", "Intake vacuum (baro - MAP)", "kPa"),   # 0xFFFF7490 = 大気圧 − 吸気圧 0xFFFF7124(MAP センサ、0x446C8)
    "8104": ("水温の平均(監視側)", "Coolant temp average (monitor)", "°C"),     # 監視側が水温 0xFFFF6CC8 を平均した値(0xB3880)
    "6DB0": ("AT の回転比(推定入力回転÷エンジン回転)", "AT speed ratio (est. input / engine)", ""),  # 0xFFFF6D34(0x38D64)
    "7F74": ("負荷の変化量(負荷と平滑値の差)", "Load change (|load - smoothed|)", ""),  # 0xFFFF7E68(0x52F7A)
}
# 中身は未特定だが、この ROM での実番地は分かったもの(番地, 日本語の前置き, 英語の前置き)。
_FFFF_REAL = {
    "6858": (0xFFFF67F8, "RAM", "RAM"),                                  # 0xFFFF6980 を一次遅れで平滑した値(0x30228)
    # オルタの学習(バックアップ RAM)。表の増減を積算し 0〜200 に制限(既定 95)。この較正では有効化バイト
    # 0xD815B / 0xD815D が 0 で休止している: 実車(2026-11-17 キーON)でも 215C = 216C = 95、2174 = 100 の既定値のまま。
    "2170": (0xFFFF215C, "オルタの学習値(この較正では休止)", "Alternator learned value (dormant in this cal)"),
    "2180": (0xFFFF216C, "オルタの学習値(この較正では休止)", "Alternator learned value (dormant in this cal)"),
    "2188": (0xFFFF2174, "オルタの学習カウント(休止)", "Alternator learned count (dormant)"),  # 16 ビット値(既定 0xD8170)
}
_FFFF_MONITOR = set()


def _ffff_axis(up):
    m = _re.match(r"FFFF_([0-9A-F]{4})", up)
    if not m:
        return None
    k = m.group(1)
    known = _FFFF_KNOWN.get(k)
    if known:
        return known
    if k in _FFFF_REAL:
        a, ja, en = _FFFF_REAL[k]
        return ("%s 0x%08X(未特定)" % (ja, a), "%s 0x%08X (unidentified)" % (en, a), "")
    if k in _FFFF_MONITOR:
        return ("監視側の内部値(未特定)", "Monitor-side internal value (unidentified)", "")
    return ("軸(入力未特定)", "Axis (input unidentified)", "")


def _axis_special(name):
    up = name.upper()
    if up.startswith("FFFF_"):
        e = _ffff_axis(up)
        if e:
            return e
    for k, v in AXIS_SPECIAL.items():
        if up.startswith(k):
            return v
    return None


def _axis_pref(name):
    import re
    return _re.split(r"[_0-9/ ]", name, 1)[0].upper() if name else ""


def axis_label(name: str) -> str:
    """軸名(例 'RPM_6DD8')から現在言語のラベル(単位付き)を返す。未知はそのまま。"""
    if not name:
        return ""
    e = _axis_special(name) or AXIS.get(_axis_pref(name))
    if not e:
        return name
    ja, en, unit = e
    lab = en if _LANG == "en" else ja
    return f"{lab} ({unit})" if unit else lab


def axis_unit(name: str) -> str:
    e = _axis_special(name) or AXIS.get(_axis_pref(name))
    return e[2] if e else ""


# ---- 値(調整値)の単位推定: カテゴリ+名称のキーワードから ----
# 上から順に判定(先に一致したものを採用)。
_UNIT_RULES = [
    ("dwell", "ms"),
    ("gear ratio", ""),
    ("displacement", "cc"),
    ("lambda", "λ"), ("afr", "AFR"), ("fuel target", "λ"), ("equiv", "λ"),
    ("torque", "N·m"),
    ("dynamic trim mult", "×"), ("multiplier", "×"), (" mult", "×"),
    ("duty", "%"), ("throttle", "%"),
    ("cam timing", "°"), ("vvt", "°"), (" vct", "°"), ("cam", "°"),
    ("spark", "°"), ("timing", "°"), ("advance", "°"), ("retard", "°"), ("ign", "°"),
    ("ipw", "ms"), ("pulse", "ms"), ("injector", "ms"), ("offset and scaling", "ms"),
    ("ltft", "%"), ("stft", "%"), ("trim", "%"), ("enrichment", "%"),
    ("enleanment", "%"), ("comp", "%"),
    ("idle speed", "rpm"), ("rev limit", "rpm"), ("rpm", "rpm"),
    ("catalyst temp", "°C"), ("temp", "°C"), ("ect", "°C"), ("iat", "°C"),
    ("vss", "km/h"), ("speed", "km/h"),
    ("baro", "kPa"), ("map", "kPa"), ("pressure", "kPa"),
    ("maf", "g/s"), ("air flow", "g/s"), ("airflow", "g/s"), ("mass air", "g/s"),
    ("voltage", "V"), ("volt", "V"),
    ("flag", ""), ("threshold", ""),
]


def unit_of(category: str, name: str = "") -> str:
    """調整値の単位を推定(定義に単位が無いためキーワードから)。不明は空。"""
    if name in EXACT_UNITS:
        return EXACT_UNITS[name]
    nm = (name or "").lower()
    # 回転数÷車速 のしきい値は比(rpm ÷ km/h)で、車速ではない。カテゴリ側の VSS 判定(km/h)に
    # 先に取られていたので最初に判定する(2026-11-16 監査)。
    if "rpm divided by vss" in nm:
        return ""
    # "Fuel Target CL - Base (Lambda)" の値は目標λではなく、理論空燃比からの燃料増量%。
    # 合計 Σ% から目標λ = 100 / (100 + Σ%) を作る(0x4B5B0。2026-11-16 逆解析)。
    if nm.strip() == "fuel target cl - base (lambda)":
        return "%"
    # 駆動系のしゃくり(振動)を取り出すフィルタの係数・ゲインは無次元。カテゴリの spark→° や
    # 名前の torque→N·m に流さない。ギア別のしゃくり振動数(Calculated Gear Alt WIP)は Hz。
    if "anti-jerk" in nm or "shuffle filter coefficient" in nm:
        return ""
    if "calculated gear alt" in nm:
        return "Hz"
    if "cut pattern enrichment" in nm:
        return "%"
    # 推定体積流量(Estimated Volumetric Flow)系はデータの意味が名前で決まる。
    # カテゴリに "throttle duty" が入り % に誤判定されるため、名前で先に判定する。
    #   ・… Scaler/Scaling(密度スケーラ等) = 倍率 → "×"
    #   ・… to Throttle Duty …(デューティ補正)= "%"
    #   ・それ以外(Default/Max/Min/Threshold 等 = 流量値そのもの)= 単位なし
    if "volumetric flow" in nm:
        if "scaler" in nm or "scaling" in nm:
            return "×"
        if "throttle duty" in nm:
            return "%"
        return ""
    # 推定マスエアフロー(内部推定値。実MAFセンサの g/s ではなく体積流量と同じ内部値)。
    # 実MAFスケーリングは名前が "MAF" で別途 g/s になるため、"estimated mass air" のみ対象。
    if "estimated mass air" in nm:
        return "×" if ("scaler" in nm or "scaling" in nm) else ""
    # 診断フラグ(DTC Flags B): 全テーブルが 1x1 uint8 の有効/無効フラグ(値0/1)。名称に含む
    # センサ種別(ECT/MAP/MAF/O2電圧/VSS/RPM/スロットル/点火 等)で物理単位に誤爆するため、
    # カテゴリ一括で無単位にする(37/126本が °/kPa/°C/V/%/g/s/rpm/km/h に誤判定していた)。
    if "dtc flags" in (category or "").lower():
        return ""
    # 診断しきい値(DTC Thresholds): キーワード規則(torque→N·m, afr→AFR, comp→%, timing→° 等)が
    # 誤爆しやすいので、このカテゴリ限定で名称から個別に確定する(他カテゴリへは波及させない)。
    if "dtc thresholds" in (category or "").lower():
        # Activation Count / Counter Limit / 各種 Timer は発生回数・ループ計数で無単位。
        #   例: "… Req Torque … Activation Count"(uint16=40)、"CMP Timing Over Advanced Timer"
        #   (uint16 84〜1250, timing→° 誤爆)、"… Activation Timer"。
        if "activation count" in nm or "counter limit" in nm or "timer" in nm:
            return ""
        # AFR センサ素子インピーダンス = Ω(値 3万〜8万。afr→AFR 誤爆を回避)。
        if "impedence" in nm or "impedance" in nm:
            return "Ω"
        # CKP↔CMP 同期オフセット = 角度°(VCT の "CKP to CMP Offset" と同一量、値 8.7〜11.2)。
        if "sync offset" in nm:
            return "°"
        # P0638 の "… TP Threshold" はスロットル位置しきい値=%(TP=throttle)。
        if "tp threshold" in nm:
            return "%"
        # 上記以外(Fuel Trim=%, Load Threshold/AFS 境界=無単位, ECT=°C, Req Torque 閾値=N·m,
        # TP factor for Estimated MAF=g/s 等)は後段の既定判定へ流す。
    # トルクモデルバンク(RE): カテゴリに "torque"→N·m が全面に効くため、名称で役割別に単位を決める。
    #   ・"… Spark …" = 最適(MBT)点火進角 → °  ・"… Factor …" = 無次元の補正係数 → 無単位
    #   ・それ以外(Torque / Temp-Corr)= トルク → N·m(BMEP換算で負側-44N·m一致により確定)。
    # DBWトルク協調(RE): BMEPトルク=kPa, スロットル=%, 係数=無単位, その他=無単位。
    if "dbw torque coordinator" in (category or "").lower():
        if "multiplier" in nm:
            return "×"
        if "bmep" in nm:
            return "kPa"
        if "throttle" in nm:
            return "%"
        return ""
    if "torque model bank" in (category or "").lower():
        if "factor" in nm or "coeff" in nm or "sens" in nm:
            return ""      # 無次元/2次係数(spark を名に含んでも係数は無単位 → spark判定より先)
        if "model table" in nm:
            return ""      # 回転×水温の表(13)。値 12〜72 の単位は未確認
        if "spark" in nm:
            return "°"
        return "N·m"
    # 排気量パッチ(Patch - Engine Displacement): "… Patch Address A/B/C" はコードが排気量定数を
    # 参照するROMアドレス(ポインタ)で cc ではない(displacement→cc 誤爆を回避)。unpatched=元定数の
    # アドレス、patched=新しい格納先(=下記 NaN 値テーブルのアドレス)。実排気量値 "… replace NaN …
    # in cc"(float NaN)のみ cc のまま後段へ流す。
    if "engine displacement" in nm and "patch address" in nm:
        return ""
    # WIP オルタネータ(WIP - Alternator): 名称の『| RPM …』条件で rpm→誤爆する項目を補正。
    #   ・"Voltage Desired …"(Base/Add)は発電目標電圧=V(条件の RPM LT 5K 等に惑わされない)。
    #   ・"WIP Limit | RPM …" は 0〜1 の界磁デューティ制限係数(×)で回転数ではない。
    # "WIP Base RPM Threshold[/Hysteresis]"(主語が RPM Threshold=rpm)はここで触れず後段へ流す。
    if "alternator" in (category or "").lower() and "wip" in (category or "").lower():
        if "voltage desired" in nm:
            return "V"
        if "wip limit" in nm:
            return "×"
    # レブリミット: スロットルカットの作動回転数は rpm(throttle→% 誤マッチを回避)。
    # "… ECT Threshold/Hysteresis" は低水温しきい値=°C(rev limit→rpm 誤マッチを回避)。
    # それ以外(燃料カット回転数・RPMヒステリシス)は rpm。
    if "rev limit" in nm:
        if "throttle cut" in nm:
            return "rpm"
        if "ect threshold" in nm or "ect hysteresis" in nm:
            return "°C"
        return "rpm"
    # エンジン負荷 上限/最小: 値は負荷(正規化・無単位)。ただし "… - RPM Threshold[/Hysteresis]"
    # の表自体は回転数しきい値=rpm。"| RPM Below Threshold" は条件ラベルで値は負荷(rpm 誤マッチ回避)。
    if nm.startswith("load limit") or "load minimum" in nm:
        return "rpm" if "rpm threshold" in nm else ""
    # 負荷スケーリング(Load Scaling)は負荷の算出係数/加算で無単位。"… VCT Comp Add" は
    # 条件が VCT>5° なだけで値は角度ではない(vct→° 誤マッチを回避)。
    if "load scaling" in nm:
        return ""
    # MAF 高負荷補正系: "maf"→g/s に誤マッチするが値は係数/遅延/しきい値。
    # MAF Scaling 変換(Default/Alternate/Fault)の出力は g/s なので、それらは汎用判定へ流す。
    if "maf" in nm:
        if "correction factor" in nm:
            return "×"
        if "transition delay" in nm:
            return ""        # 遅延カウント。1カウントの時間は未確認なので秒とは書かない
        if "load threshold" in nm:
            return ""
    # APP(アクセル開度)しきい値は常に %。"IPW…Fuel Cut APP Threshold" が ipw→ms に誤マッチ
    # するのを回避(値はペダル開度%)。他の APP Threshold(無単位・%)も % に統一。
    if "app threshold" in nm:
        return "%"
    # インジェクタ スケーリング(流量倍率)は×。"Injector Offset"(デッドタイム=ms)は別物で、
    # これには一致しない。offset and scaling→ms に誤マッチするのを回避。
    if "injector scaling" in nm:
        return "×"
    # VVT/VCT(Variable Cam Timing)カテゴリは、カテゴリ名の "cam timing"→° が汎用ループで
    # "ect"→°C より先に当たる(hay=カテゴリ+名称)。"… ECT Threshold[/Hysteresis]" は作動水温=°C
    # なので先回りで返す。値がカム角の "VCT Target" 等(ect を含まない)は触れず cam→° に流す。
    if ("ect threshold" in nm or "ect hysteresis" in nm) and "cam timing" in (category or "").lower():
        return "°C"
    # VCT偏差(DO NOT MODIFY)の "VCT Error - RPM Threshold[/Hysteresis]" は切替回転しきい値=rpm。
    # カテゴリ "cam timing"→° 誤爆を回避。Multiplier/Correction(名は "| Above/Below RPM Threshold"
    # の条件で RPM Threshold が主語ではない)は別単位なので除外する。
    if "vct error" in nm and "rpm threshold" in nm and "multiplier" not in nm and "correction" not in nm:
        return "rpm"
    # "VCT Error - Correction to Apply …" は OCV制御器への出力補正(値 -600〜400)で、カム角°ではない
    # (位相器の可動域を大きく超える)。内部制御量のため無単位にする(cam timing→° 誤爆を回避)。
    if "vct error" in nm and "correction to apply" in nm:
        return ""
    # "… Delay … | … Baro …": baro は『|』以降の条件で、値は遅延カウント(気圧ではない)。
    # 一方 "… - BARO Below Threshold"(|無し, baro が主語=気圧しきい値)は kPa のまま残す。
    if "delay" in nm and "baro" in nm and "|" in nm and nm.index("baro") > nm.index("|"):
        return ""
    # "Load Threshold [| 条件]" は負荷しきい値(値は負荷0〜1=無単位)。条件の High ECT/High Det
    # 等に惑わされて °C 等にしない。ただし "… ECT Activation Threshold"(値が気温そのもの)は除外。
    if "load threshold" in nm and "activation threshold" not in nm:
        return ""
    # "… Delay Reset Value | <条件>": 遅延がリセットされる値(カウント)で無単位。条件の
    # ECT/BARO 等に惑わされない。しきい値本体 "Delay Reset - X Threshold" は X の単位のまま。
    if "delay reset value" in nm:
        return ""
    # "… Timer Reset" はタイマ/カウントのリセット値で角度や物理量ではない(spark→° 等の誤爆回避)。
    # 例: "Spark Transition … - Transition Timer Reset"(値≈0)。Fuel 側 "… Timer Reset"(=60)も無単位。
    if "timer reset" in nm:
        return ""
    # "… Count Required …": 判定成立に必要な回数(カウント)で無単位。"RPM Threshold Count…"
    # が rpm に誤マッチするのを回避(値は回数であって回転数ではない)。
    if "count required" in nm:
        return ""
    # 推定アイドル回転(Estimated Idle Speed Add/Limiter)は rpm。カテゴリ "Fuel Comp" の
    # "comp"→% が先に当たるのを回避。"RPM divided by VSS" は比率で無単位。
    # "… Corrective Divisor" は除数(カテゴリ "Comp"→% が誤爆)。無単位。Multiplier は別途 ×。
    if "corrective divisor" in nm:
        return ""
    # STFT 移行遅延(STFT Transition Delay)は遅延カウント/時間で % ではない("comp"→% 回避)。
    if "stft" in nm and "transition delay" in nm:
        return ""
    # STFT 補正係数(STFT Correction … Coefficient)は無次元ゲインで % ではない。
    if "stft" in nm and "coefficient" in nm:
        return ""
    # 閉ループへの移行(Transition to CL): Delay=遅延(無単位)、Eq Ratio Delta=当量比差(無次元)、
    # Fuel Enrich/Enlean Limit=燃料% 。カテゴリ "Comp"→% の誤爆を分岐で正す。
    if "transition to cl" in nm:
        if "delay" in nm:
            return ""
        if "eq ratio" in nm:
            return ""
        return "%"
    # LTFT: Accumulation Timer=タイマ(無単位)、EQ Ratio …Delta=当量比差(無次元)。
    # 最大/最小/STFT Range 等の % は comp→% のまま正しいので触らない。
    if "ltft" in nm:
        if "accumulation timer" in nm:
            return ""
        if "eq ratio" in nm:
            return ""
    # MAF 区切り値(MAF Breakpoint)とそのヒステリシスは吸入空気量 g/s("comp"→% を回避)。
    if "maf breakpoint" in nm:
        return "g/s"
    # "… MAF Threshold" は吸入空気量のしきい値 g/s(comp→% 回避)。
    if "maf threshold" in nm:
        return "g/s"
    # 負荷デルタしきい値は負荷(無次元)、VSSしきい値は車速(km/h)、Activation Delay は遅延。
    # いずれも Fuel Comp の comp→% で誤って % になるのを回避。
    if "load delta threshold" in nm:
        return ""
    # VSSしきい値は車速(km/h)。ただし "… Spark Idle Load - VSS Comp" の
    # "VSS Comp | Above/Below VSS Threshold" は“値”が速度ではない内部カーブなので除外し、
    # 後段の spark idle load - vss 判定(無単位)に委ねる。
    if "vss threshold" in nm and "spark idle load" not in (category or "").lower():
        return "km/h"
    if "activation delay" in nm:
        return ""
    # コードパッチのトグル(名前に "unpatched = X, patched = Y")はコード値で無単位。
    # 例: "Fuel Target CL Patch | unpatched = 36647, patched = 9"(λ 誤表示を回避)。
    if "unpatched" in nm:
        return ""
    if "estimated idle speed" in nm:
        return "rpm"
    # Idle Speed Comp の "Start-up Base / Base Limit" はアイドル回転の加算量/上限=rpm("comp"→%回避)。
    # Multiplier は上の分岐で ×。"Post Start-up …"(減衰レート)は別物なので除外。
    if "idle speed comp" in nm and "start-up base" in nm and "post" not in nm:
        return "rpm"
    # Idle Speed Comp の減衰レート(Decrement Rate)はアイドル回転(rpm)を減らす量/周期。
    if "idle speed comp" in nm and "decrement rate" in nm:
        return "rpm"
    if "rpm divided by vss" in nm:
        return ""
    # スロットル角度(Throttle Angle)は物理ブレード角=度(°)。ただし "…Multiplier" は倍率(×)。
    # 例: Throttle Angle - Maximum=85°、Throttle Percentage to Throttle Angle Multiplier=0.85×。
    if "throttle angle" in nm:
        return "×" if ("multiplier" in nm or " mult" in nm) else "°"
    # スロットルデューティ指令/目標系は常に %。名前に "torque request" を含む
    # "…(Bypass Torque Request)" 行も、実体はデューティ% なのでここで先取りする
    # (汎用ルールでは "torque"→N·m が "duty"→% より先に当たってしまうため)。
    if "throttle duty" in nm:
        return "%"
    # トルク要求(Torque Request)系: この個体では BMEP(平均有効圧 kPa)や倍率で表現され N·m ではない。
    # 定義名に "...in kpa"(Brake Mean Effective Pressure)や "Multiplier" が入る。
    # 別系統の "Requested Torque …"(実トルク N·m しきい値)は語順が違い一致しない。
    if "torque request" in nm:
        if "multiplier" in nm or " mult" in nm:
            return "×"
        if "kpa" in nm or "brake mean effective" in nm or "bmep" in nm:
            return "kPa"
        return "N·m"
    # 「…Multiplier」は倍率(×)。乗算係数に物理単位は無いので、fuel target(λ)/afr/温度 等の
    # キーワードより優先する(例: 触媒温度推定の Multiplier|AFR Lean/Rich、暖機燃料の各 Multiplier)。
    if "multiplier" in nm:
        return "×"
    # 点火アイドル補正(特殊暖機WIP)の "Spark Idle Correction … Target" 一族は、進角補正の
    # 目標値およびその増減レート(°)。"… Warm-Up Fuel Target" も実体は進角補正目標(値0〜18°)で、
    # 直後の warm+fuel target→"" や 汎用 fuel target→λ に誤爆するためここで先取りする。
    # "… Target Multiplier"(倍率×)は除外して後段の multiplier 判定へ流す。
    if "spark idle correction" in nm and "target" in nm and "multiplier" not in nm:
        return "°"
    # 暖機時 目標空燃比(Warm-Up Fuel Target)系の非倍率テーブルは、増量“量”/上限/減衰率で
    # あって絶対λではない(値 0〜60/0〜100/0.27 等=実λ 0.7〜1.4 の範囲外)。λ 誤表示を回避。
    # (倍率 Multiplier は直前の分岐で既に × 判定済み)
    if "warm" in nm and "fuel target" in nm:
        return ""
    # 目標空燃比(開ループ)Fuel Target OL は、絶対λではなく『ストイキに対する増量%』
    # (値 0〜36 等、0=ストイキ)。λ 誤表示を回避。閉ループ CL はベース=実λ/Stoich=AFR で別途正しい。
    if "fuel target ol" in nm:
        return "%"
    # 点火ベース 高燃料要求への移行(Spark Base - High Fuel Request Transition)系:
    # 燃料要求レベルの切替しきい値/ヒステリシス/遅延で、点火進角(°)ではない。
    # カテゴリ名の "spark"→° が誤爆するため名前で先取りする。名前に単位が明記されている:
    #   "(Lambda)"→λ、"(%)"→%。"Transition Delay" は遅延カウントで無単位。
    # 実際の進角マップ(High/Low Fuel Request / Spark Base Limit)は threshold/hysteresis/
    # delay を名前に含まず不一致なので、それらは従来どおり ° のまま。
    if "fuel request" in nm and (
        "threshold" in nm or "hysteresis" in nm or "delay" in nm
    ):
        # "High Fuel Request Threshold (Lambda)" は名前に Lambda とあるが、比較相手は燃料要求の
        # 増量%(RAM 0xFFFF7728。0x4DF38 で比較)で、ヒステリシス(%)と同じ量。値 6.25 も % として
        # 読むのが整合する(Fuel Target OL の表が増量%なのと同じ)。
        if "lambda" in nm or "(%)" in nm or "hysteresis" in nm:
            return "%"
        return ""            # 移行遅延カウント / 単位未明記のしきい値
    # 点火アイドル負荷(Spark Idle Load)系: アイドル制御が狙う“エンジン負荷”の基準/補正で、
    # 値は負荷(0〜1 正規化・無単位)。名前/カテゴリの "spark"→° 誤爆を回避する。
    #   ・"Spark Idle Load - Base"(名前) = 基準負荷(0.135〜0.5)
    #   ・カテゴリ "… Spark Idle Load - AC Comp" = A/Cコンプレッサ分の負荷加算(0.02〜0.085)。
    #     名前は "AC Comp Base | …" で "spark idle load" を含まないためカテゴリで判定する。
    # 他の補正カテゴリ(VSS=km/h, PSP/Alt=× や他単位が混在)はここでは扱わない。
    _cat = (category or "").lower()
    if "spark idle load" in nm or "spark idle load - ac comp" in _cat:
        return ""
    # パワステ補正(Spark Idle Load - PSP Comp/Compensation): 計算用の分子/除数定数は無単位。
    # カテゴリの "spark"→° 誤爆を回避。ただし "… Multiplier"(二次係数)は倍率×なので除外する
    # (Multiplier は後段の "multiplier"→× 判定に流す)。
    if "spark idle load - psp" in _cat and "multiplier" not in nm:
        return ""
    # オルタネータ補正(Spark Idle Load - Alternator Comp/Compensation): カテゴリの "spark"→°、
    # 名前中の "duty"→% が誤爆する。実体は:
    #   ・"Alternator to Estimated MAF Add" = 推定エアフロへの加算(g/s、値0〜2.2=アイドル域airflow)
    #   ・その他(負荷加算 Base、Decrement Rate、Delta Hysteresis)= 無単位
    # Multiplier があれば × に流す(現状このカテゴリに該当なし)。
    if "spark idle load - alt" in _cat and "multiplier" not in nm:
        if "estimated maf" in nm:
            return "g/s"
        return ""
    # 車速補正(Spark Idle Load - VSS Comp): カテゴリの "spark"→°、名前中 "vss"→km/h が誤爆。
    # 実体はアイドル負荷の補正/内部カーブ(値は負荷・内部量で無単位)。X軸が車速(km/h)や回転数で
    # あっても“値”は速度ではない。"… Multiplier"(×)は後段へ流して温存する。
    #   ・"VSS Comp | In-Gear, MT"(X=車速)=停車付近の負荷加算(0.1→0)
    #   ・"VSS Comp Sub | In-Gear, MT"(X=回転数)=微小サブ項
    #   ・"VSS Comp | Above/Below VSS Threshold (5kph), AT"(X=未使用)=内部カーブ(0〜31, 単位未確定)
    if "spark idle load - vss" in _cat and "multiplier" not in nm:
        return ""
    # 点火ベース/アイドル移行(Spark Base / Idle Transition): カテゴリの "spark"→° が誤爆する。
    # 実体は点火マップ(アイドル用/走行ベース)を切替える条件で、進角°ではない。
    #   ・"… RPM Threshold" = 切替回転数(rpm、ヒステリシス 4500↑/4000↓)
    #   ・"… Fuel Start-Up Enrichment Threshold" = 始動時増量(%)の残量しきい値
    if "transition to spark base" in nm or "transition to idle" in nm:
        if "rpm threshold" in nm:
            return "rpm"
        if "enrichment threshold" in nm:
            return "%"
        return ""
    # 点火アイドル補正(AC/PS断続切替)の "… - Duration …" は補正の適用保持時間/カウントで、
    # 角度(°)ではない。カテゴリ "spark"→° 誤爆を回避(単位の確定は不能なので無単位)。
    # 同族の "… - Value …" は進角補正°なので触れない(duration のみ対象)。
    if "spark idle" in nm and "duration" in nm:
        return ""
    # 急開アンチラグ(Tip-In Anti Lug)の "Minimum RPM Threshold …" は作動回転しきい値=rpm。
    # カテゴリ "spark"→° 誤爆を回避。anti lug 限定(他の rpm threshold には波及させない)。
    if "anti lug" in nm and "rpm threshold" in nm:
        return "rpm"
    # 急開(高速)Tip-In Retard High Speed: カテゴリ "spark"→° が誤爆する。実体は混在:
    #   ・"… Delay | Gear …"(uint8)= 遅延カウント(無単位、角度ではない)
    #   ・"… APP Increasing/Decreasing | AT"(float, max1.3, 〜1.0収束)= ペダル増減別の倍率×
    #   ・"… Base Retard …" = ベース遅角°(後段へ流す)/"… Multiplier …" は後段 "multiplier"→×。
    if "tip-in retard high speed" in nm:
        if "delay" in nm:
            return ""
        if "app increasing" in nm or "app decreasing" in nm:
            return "×"
        # Base Retard=°、ZEROED Multiplier=× は後段の既定判定へ流す
    # 冷間進角(Spark Comp - Cold Advance): カテゴリ "spark"→° 誤爆。進角量/加算マップ/レートは
    # ° でよいが、"… Add Timer"(加算進角の保持タイマ)はカウント/時間で角度ではない→無単位。
    # "… Add Retard Rate | Timer Expired" は °/周期のレートなので除外し ° のまま後段へ流す。
    if "cold advance" in nm and "add timer" in nm:
        return ""
    # ノックリタード(Spark Correction - Knock Retard): カテゴリ "spark"→° が誤爆する。
    # KR(Knock Retard=ノック遅角)の量・最大・増減レートは進角°(そのまま後段へ)。一方、
    # Knock Listen のしきい値と各種 Delay は別単位:
    #   ・"… Load …"(Minimum Load / Hysteresis)= 負荷(無単位)
    #   ・"… RPM …"(Min/Max RPM / Hysteresis)= rpm
    #   ・"… Delay …"(Exit Delay / KR Reduction Delay)= 遅延カウント(無単位)
    if "knock retard" in (category or "").lower():
        if "load" in nm:
            return ""
        if "rpm" in nm:
            return "rpm"
        if "delay" in nm:
            return ""
        # それ以外(KR量/最大/増減レート/Minimum KR 等)は ° のまま後段へ流す
    # 点火補正 高回転・高水温遅角(Spark Correction - High RPM and ECT): カテゴリ "spark"→° 誤爆。
    # しきい値は各物理量: RPM Threshold[/Hysteresis]=rpm、ECT Threshold[/Hysteresis]=°C。
    # Retard Rate / Retard Limit / Restore Advance Rate は進角°なので後段へ流す(ここでは触れない)。
    # Activation Delay は手前の "activation delay"→"" で既に処理済み。
    if "high rpm and ect retard" in nm:
        if "rpm threshold" in nm:
            return "rpm"
        if "ect threshold" in nm:
            return "°C"
    # 点火補正増量(Corrective Spark Enrichment)系: カテゴリ名の "spark"→° が誤爆する。
    # しきい値は各物理量(RPM=rpm, Cat Temp=°C, Load=無単位)、増量量(|OL 等)=%。
    if "corrective spark enrichment" in nm:
        if "rpm thre" in nm:                 # "RPM Threshold"/typo "RPM Threhold"
            return "rpm"
        if "temperature" in nm:
            return "°C"
        if "load threshold" in nm:
            return ""
        return "%"
    # 高負荷リーン化(Power Enleanment)系: "enleanment"→% が greedy で、しきい値まで % にする。
    # しきい値は各物理量(VSS=km/h, ECT=°C, RPM=rpm, Load=無単位)、リーン化量/レートは %。
    if "power enleanment" in nm:
        # "Power Comp - … Advance / Retard … | Fuel Power Enleanment Set/Clear"(点火ベース上限
        # 補正・高負荷)は進角°。ここでの "power enleanment" は '|' 以降の条件フラグで、値は点火
        # 進角そのもの。本物の燃料リーン化テーブルは advance/retard を名前に含まず不一致。
        if "advance" in nm or "retard" in nm:
            return "°"
        if "vss" in nm:
            return "km/h"
        if "iat threshold" in nm or "ect threshold" in nm:
            return "°C"
        if "rpm threshold" in nm:
            return "rpm"
        if "load threshold" in nm:
            return ""
        if "timer" in nm:
            return ""                 # タイマ/遅延(カウント・時間で % ではない)
        return "%"                    # リーン化量/レート、TP・APP しきい値(%)
    # EVAPCP(EVAPキャニスタパージ)のベース/加算/マップはパージ量の内部値で物理単位なし。
    # "…Voltage Add" は電圧軸に対する補正量であって電圧値ではない(V 誤表示を防ぐ)。
    if "evapcp" in nm:
        return ""
    # 電動ファン制御: 「… Speed」(低速/中速/高速=ファン段)が "speed"→km/h に誤マッチする。
    # タイマ=秒、選択=リレー選択ビットマスク(無単位)、速度遷移遅延=秒。
    # 水温しきい値 10 表(整数)は ℃ ではなく水温センサ電圧の 10bit A/D 値(ncecu/ectcount.py。
    # 0x98F9E / 0x99278 が RAM 0xFFFF710E と比較する)。"ect"→°C に流さず A/D を返す。
    # VSS しきい値(→km/h)と、浮動小数の "After Cooling Activation - Estimated ECT Threshold"(→°C)は
    # 汎用判定に任せる。
    if "fan" in nm:
        if ectcount.is_count_table(name):
            return ectcount.UNIT
        # タイマ/遅延はカウント値。1 カウントの時間は OS のタスク周期から求めた(2026-11-16 逆解析):
        #   アフタークーリングのタイマ = 100ms ごとに 1 減る(0x993D4 / 0x9932C)
        #   ファン段の切替待ち(Fan Speed Transition - Delay)= 25ms ごとに 1 減る(0x9920A)
        if "timer" in nm:
            return "×0.1s"
        if "selection" in nm:
            return ""
        if ("transition" in nm or "delay" in nm) and "vss" not in nm:
            return "×25ms"
    hay = f"{category or ''} {name or ''}".lower()
    # 短い略語("ect"/"iat")は単語境界で判定する。部分一致だと corrECTion / selECTion /
    # detECTed / corrECTed などに誤マッチして誤って °C になるため(28テーブルで誤判定していた)。
    _boundary = {"ect", "iat"}
    for kw, u in _UNIT_RULES:
        if kw in _boundary:
            if _re.search(r"\b" + kw + r"\b", hay):
                return u
        elif kw in hay:
            return u
    return ""


# ---- UI 文言(日英)----
UI = {
    "open": ("ROMを開く", "Open ROM"),
    "save": ("保存", "Save"),
    "saveas": ("名前を付けて保存", "Save As"),
    "help": ("ヘルプ", "Help"),
    "live_on": ("Live ▶", "Live ▶"),
    "live_off": ("Live ■", "Live ■"),
    "dashboard": ("ダッシュボード", "Dashboard"),
    "dump": ("ECU吸出し", "Read ECU"),
    "cmp_ecu": ("ECUと照合", "Compare ECU"),
    "cmp_rom": ("ROM照合", "Compare ROMs"),
    "search": ("検索(名前/0x番地):", "Search (name / 0x addr):"),
    "lang": ("EN", "日本語"),      # ボタンは「次に切替える言語」を表示
    "unit": ("単位", "unit"),
    "axis_x": ("横軸(X)", "X axis"),
    "axis_y": ("縦軸(Y)", "Y axis"),
    "map3d": ("3Dマップ", "3D map"),
    "map2d": ("2Dテーブル", "2D table"),
    "val1d": ("単一値", "single value"),
    "range": ("目安範囲", "range"),
    "effect": ("値を変えると", "Effect of change"),
    "trusted": ("✓ 定義は LibreTuner(この個体CALID用)。次元・アドレスは検証済み。",
                "✓ LibreTuner definition (this CAL ID). Dimensions/addresses verified."),
    "axis_edit_off": ("軸編集 OFF", "Edit Axes: OFF"),
    "axis_edit_on": ("軸編集 ON", "Edit Axes: ON"),
    "axis_edit_warn_title": ("軸ブレークポイント編集", "Edit axis breakpoints"),
    "axis_edit_warn": (
        "軸(ブレークポイント)の値を編集できるようにします。\n\n"
        "・純正ECUでは点数は固定です。値のみ編集でき、点の増減はできません。\n"
        "・値は昇順(単調増加)を保ってください。逆転・重複は補間を壊します。\n"
        "・保存時にチェックサムは自動補正されます。\n"
        "・実機書き込み前に必ず吸い出しダンプを保管してください。\n\n"
        "軸編集を有効にしますか?",
        "This lets you edit axis (breakpoint) values.\n\n"
        "- On a factory ECU the number of points is fixed. You can edit values only, "
        "not add/remove points.\n"
        "- Keep values strictly ascending. Reversed/duplicate values break interpolation.\n"
        "- Checksums are corrected automatically on save.\n"
        "- Always keep your read-out dump before flashing.\n\n"
        "Enable axis editing?"),
    "fs_patch": ("フラットシフト", "Flat-shift"),
    "al_patch": ("アンチラグ", "Anti-lag"),
    "rd_patch": ("回転落ち高速化（レブハング低減）", "Faster rev drop"),
    "th_patch": ("電スロチューニング", "DBW throttle"),
    "fs_title": ("フラットシフト（点火カット/遅角）", "Flat shift (ignition cut/retard)"),
    "fs_done": ("パッチを適用しました(未保存)。左のツリーの『パッチ - フラットシフト』で値を変更できます。",
                "Patch applied (not saved yet). Edit the values under 'Patch - Flat Shift'."),
    "fs_already": ("このROMには既にパッチが当たっています。左のツリーの『パッチ - フラットシフト』で値を変更できます。",
                   "This ROM already has the patch. Edit the values under 'Patch - Flat Shift'."),
    "fs_unsupported": ("このROMには適用できません(未対応ROM、または別のパッチと衝突しています)。\n{err}",
                       "Cannot apply to this ROM (unsupported, or conflicts with another patch).\n{err}"),
    "menu_settings": ("設定", "Settings"),
    "menu_live_intervals": ("ライブPID間引き…", "Live PID intervals…"),
    "li_title": ("ライブPID間引き設定", "Live PID poll intervals"),
    "li_note": ("信号ごとの読み出し間隔を設定します(毎回 / 0.1s〜10s / 無視＝読まない)。1要求=最大6PID。\n「毎回」の項目を6個以内にすると、回転数など速いPIDの更新が最速になります。",
                "Set how often each signal is read (every cycle / 0.1s-10s / Ignore = not read). Up to 6 PIDs per request.\nKeep the 'every cycle' items within 6 for the fastest RPM update."),
    "li_follow": ("※表示中マップの軸に使う信号(回転・絶対負荷・水温・アクセル等)は、「無視」や遅い設定にしていてもMAP追従のため自動で読みます。ライブRAM(Mode23)は1周期に2ブロックまで、遅れの大きい順に読みます。",
                  "Note: signals used as axes of the open map (RPM, abs load, ECT, pedal...) are read automatically for map following even if set to Ignore or a slow interval. Live RAM (Mode23) reads up to 2 blocks per cycle, most-overdue first."),
    "li_every": ("毎回", "Every cycle"),
    "li_estimate": ("毎回: {n}項目 → 定常 {req} 要求/周期", "Every cycle: {n} PIDs -> {req} request(s)/cycle"),
    "li_apply": ("適用", "Apply"),
    "li_cancel": ("キャンセル", "Cancel"),
    "li_reset": ("既定に戻す", "Reset to defaults"),
    "li_saved": ("保存しました。次回のLive接続から有効です(接続中なら即時反映)。", "Saved. Applies from the next Live connection (immediately if connected)."),
    "range_title": ("入力値エラー", "Value error"),
    "extra_note": ("✓ 追加項目(LibreTuner定義には無い。ncecu のパッチモジュールで定義)。番地と意味は逆アセンブル＋エミュレータで確認済み。範囲外の入力は受け付けません。",
                   "✓ Extra item (not in the LibreTuner definition; defined in an ncecu patch module). Address and meaning verified by disassembly + emulator. Out-of-range input is rejected."),
    "range_msg": ("この項目は {lo:g}〜{hi:g} の範囲で入力してください。入力値 {v:g} は範囲外です。元に戻します。",
                  "This item accepts {lo:g} to {hi:g}. Value {v:g} is out of range. Reverting."),
    "axis_mono_title": ("軸の値エラー", "Axis value error"),
    "axis_mono_msg": ("軸の値は昇順(単調増加)でなければなりません。\n"
                      "隣接値: 左={lo} / 右={hi}\n入力値 {v} は範囲外です。元に戻します。",
                      "Axis values must be strictly ascending.\n"
                      "Neighbors: left={lo} / right={hi}\nValue {v} is out of range. Reverting."),
    "menu_chart": ("ログ分析チャート…", "Log analysis chart…"),
    "menu_patches": ("パッチ適用", "Apply patches"),
    "menu_dtc_clear": ("DTCクリア（故障コード消去）…", "Clear DTCs…"),
    "dtc_title": ("DTCクリア", "Clear DTCs"),
    "dtc_confirm": ("ECUの故障コード(DTC)を消去します。\n未修理の異常があれば再度立ちます。実行しますか?",
                    "Clear the ECU's stored diagnostic trouble codes (DTCs).\n"
                    "Codes for unresolved faults will reappear. Proceed?"),
    "dtc_ok": ("DTCを消去しました(応答 0x44)。", "DTCs cleared (response 0x44)."),
    "dtc_nak": ("消去できませんでした(応答: {resp})。", "Could not clear (response: {resp})."),
    "dtc_err": ("通信エラー: {err}", "Communication error: {err}"),
    "dtc_timeout": ("応答がありませんでした(タイムアウト)。", "No response (timeout)."),
    "dtc_before_after": ("消去前: {before}\n消去後: {after}", "Before: {before}\nAfter: {after}"),
    # CAN接続(WSL2/socketcan 実行時のみ表示)
    "menu_can_connect": ("CAN接続（WSL/socketcan）…", "CAN connection (WSL/socketcan)…"),
    "can_title": ("CAN接続（WSL2 / socketcan）", "CAN connection (WSL2 / socketcan)"),
    "can_reconnect": ("再接続（attach + can0 up）", "Reconnect (attach + can0 up)"),
    "can_refresh": ("状態を更新", "Refresh"),
    "can_close": ("閉じる", "Close"),
    "can_reconnecting": ("再接続中…", "Reconnecting…"),
    "can_hint": ("USBを挿し直した／can0 が落ちたときは［再接続］で復旧できます。",
                 "If you reconnected the USB or can0 went down, use [Reconnect] to recover."),
}


def ui(key: str) -> str:
    v = UI.get(key)
    if not v:
        return key
    return v[1] if _LANG == "en" else v[0]


# カテゴリごとの「値を変えると何が変わるか」(効果)。チューニングの勘所。
CATEGORY_EFFECT = {
    "WIP - Fuel Comp Cut Pattern (RE)": "値↑=気筒カットによるトルク低減中に燃料が増える(濃くなる)。CAN のトルク上限要求が来なければ使われない。変更しない。",
    "WIP - DBW Torque Coordinator (RE)": "トルク要求・目標スロットル・振動抑制の特性。(Control) 付きは監視側の写しと必ず同じ値にする。帯域フィルタの係数は計算で決まる組なので個別に変えない。",
    "DBW - Throttle Duty Desired": "値↑=同じアクセル開度でスロットルを大きく開く(レスポンス敏感・ツキが鋭く)/値↓=穏やかに。踏み量とパワーの出方が変わります。",
    "DBW - Throttle Duty Limits": "スロットル開度の上限が変わります。上げすぎ注意(保護項目)。",
    "Engine Limiters - RPM": "値↑=レブリミット(燃料/点火カット回転数)が上がる/値↓=下がる。上げる場合はエンジンの許容回転に注意。",
    "Engine Limiters - VSS": "速度リミッターの作動車速が変わります。",
    "Engine Sensor - MAF": "エアフロ特性(空気量の読み)。実際とズレると空燃比が全体的にズレます。吸気系・MAF変更時のみ、計測に基づき調整。",
    "Engine Sensor - MAP": "吸気圧の読み。SD方式/過給では空気量推定に直結。センサ変更時に合わせます。",
    "Engine Sensor - ECT": "水温の読み(センサ特性)。狂うと暖機・補正全体が崩れます。センサ変更時のみ。",
    "Engine Sensor - IAT": "吸気温の読み。狂うと吸気温補正が崩れます。センサ変更時のみ。",
    "Fuel Target CL - Base": "閉ループの目標空燃比(通常ストイキ14.7付近)。基本は変更不要。",
    "Fuel Target OL - Base": "開ループ(高負荷)の目標空燃比。リッチ=安全・出力寄り/リーン=燃費だが高負荷では危険。体感と安全に直結。",
    "Fuel Target - Warm-Up": "暖機時の目標空燃比。リッチ=始動/暖機安定、リーン=燃費。",
    "Fuel IPW - Base": "基本噴射時間。値↑=燃料増(リッチ)/値↓=減(リーン)。空燃比に直結。",
    "Fuel IPW - Offset and Scaling": "インジェクタのデッドタイム/容量換算。インジェクタ交換時は必須調整(誤ると低開度で大きくズレる)。",
    "Fuel IPW - Cranking": "始動時噴射。値↑=始動時リッチ(かぶり注意)/値↓=リーン(始動性低下)。",
    "Fuel Comp - Tip-In Enrichment": "加速時の増量。値↑=加速時の息つき対策(濃くなる)/値↓=薄く。",
    "Fuel Comp OL - Decel Fuel Cut": "減速燃料カットの条件。燃費・エンジンブレーキに影響。",
    "Fuel Comp OL - Power Enleanment": "高負荷でのリーン化。通常はパワー空燃比(ややリッチ)側に。リーンは危険。",
    "Fuel Comp - LTFT": "長期燃料学習の範囲/挙動。通常は変更不要。",
    "Spark Base": "基本点火時期。値↑(進角)=トルク/燃費向上だがノックのリスク増/値↓(遅角)=安全側だが出力低下。最重要・慎重に。",
    "Spark Base Comp - ECT / IAT": "温度による点火補正。高温時に遅角を強める等で保護。",
    "Spark Base Limit": "点火進角の上限。安全マージン。上げすぎるとノック保護が効きにくくなる。",
    "Spark Correction - Knock Retard": "表ごとに向きが違う。遅角量(KR Increment / Maximum)は 値↑=保護が強い。復帰の速さ(KR Decrement Rate)は 値↑=早く進角に戻る=保護が弱い。監視範囲(Knock Listen の回転・負荷)は範囲を狭めるほどノックを見ない領域が増える。Delay は値↑=復帰が遅い。",
    "Spark Correction - Cold Advance": "冷間時の進角補正。暖機性能に影響。",
    "Spark Correction - Tip-In Retard": "加速時の遅角。加速時ノック対策。",
    "Idle Speed": "目標アイドル回転数。値↑=アイドル高め/値↓=低め(低すぎるとストール)。",
    "Ignition Coil Dwell Time": "点火コイル通電時間。コイル交換時に合わせる。長すぎはコイル発熱、短すぎは失火。",
    "Variable Cam Timing - Base": "可変バルブタイミングの目標角。トルクの出方(低速/高速寄り)が変わります。",
    "Engine Fan Control": "水温しきい値(A/D値)は 値↑=低い水温で回り始める(早く回る)/値↓=高い水温まで回らない。℃とは向きが逆。車速しきい値・タイマは値そのまま。",
    "Spark Base - High Fuel Request Transition": "しきい値↑=高燃料要求側の点火マップへ切り替わりにくくなる/↓=切り替わりやすくなる。進角量は変わらない。",
    "Fuel Target OL - Base": "値はストイキに対する増量%(0=ストイキ)。値↑=濃い(リッチ)=安全・出力寄り/値↓=薄い(高負荷では危険)。変更はワイドバンドAFRの実測とセットで。",
    "Fuel IPW - Dynamic Trim Mult A (Large)": "加減速時の過渡(壁流れ)補償の係数。定常の空燃比ではなく、アクセルを踏んだ/戻した瞬間の濃い・薄いが変わる。基本は純正のまま。",
    "Fuel IPW - Dynamic Trim Mult B (Small)": "加減速時の過渡(壁流れ)補償の係数。定常の空燃比ではなく、アクセルを踏んだ/戻した瞬間の濃い・薄いが変わる。基本は純正のまま。",
    "Fuel IPW - Dynamic Trim Mult C": "加減速時の過渡(壁流れ)補償の倍率。値↑=過渡の補償量が増える。定常の空燃比は変わらない。基本は純正のまま。",
    "Vehicle Instrument Cluster - Speedometer": "スピードメーターの表示補正。タイヤ外径変更時に実速度へ合わせる(表示のみ・制御には影響小)。",
    "Vehicle Instrument Cluster - ECT Gauge": "水温計の針の表示特性。実際の水温や制御は変わりません(見た目のみ)。",
    "Patch - Immobilizer": "イモビライザー(盗難防止)のバイパス設定。中古ECU流用時に『patched』値へ変えると照合を無効化できます。取扱注意・自己責任。",
    "Patch - Decel Fuel Cut Off": "減速燃料カットの改変。",
    "Patch - Flat Shift": "方式0=点火遅角(穏やか。遅角量↑でトルク低下大・下限↓で大遅角)/1=本物の点火カット(発動中コイル充電停止=火花なし。生ガスで排気バックファイア/高EGT)。発動はクラッチ踏込＋ゲート成立の間だけ(窓時間はクラッチ操作で決まる)。回転/アクセルしきい値↓=早め/浅い踏込でも発動(誤作動リスク↑)。回転しきい値は上限としても働く。車速下限↑=低速では効かない。RAM非書込・窓なし。test_mode=1は車速ゲートだけ無視=停車確認専用(始動/アイドルは不発、停車Nで回転を上げると発動。走行前に0へ)。",
    "Patch - Open Loop Short Term Fuel Trim Fix": "開ループ短期補正の修正パッチ。",
}

_EFFECT_FALLBACK ="このマップの値を変えると上記カテゴリの挙動が変化します。意味が分からない場合は変更しないでください(センサ特性や診断系は特に注意)。"

# グループ単位の効果フォールバック(LibreTuner カテゴリ向け)
GROUP_EFFECT = {
    "Spark Base": "値↑(進角)=トルク/燃費向上だがノックのリスク増/値↓(遅角)=安全側だが出力低下。最重要・慎重に。",
    "Spark Comp": "条件(温度・EGR等)による点火補正。高温時に遅角を強める等で保護。",
    "Spark Correction": "ノック・加速・冷間などでの遅角/進角量。保護を強める=安全、弱める=出力寄りだがリスク。",
    "Spark Base Limit": "点火進角の上限(安全マージン)。上げすぎるとノック保護が効きにくくなる。",
    "Spark Limits": "点火時期の上下限(保護)。むやみに広げない。",
    "Fuel Target CL": "閉ループ目標空燃比(通常λ1付近)。基本は変更不要。",
    "Fuel Target OL": "開ループ(高負荷)目標空燃比。リッチ=安全・出力寄り/リーン=燃費だが高負荷では危険。",
    "Warm-Up Fuel Target OL": "暖機時の目標空燃比。リッチ=始動/暖機安定、リーン=燃費。",
    "Fuel IPW": "値↑=燃料増(リッチ)/値↓=減(リーン)。空燃比に直結。インジェクタ変更時は特性合わせが必須。",
    "Fuel Comp OL": "減速カット・高負荷リーン化・増量など。高負荷のリーン化は危険側、慎重に。",
    "Fuel Comp CL": "短期/長期トリム・触媒診断など。通常は変更不要。",
    "Fuel Comp OL/CL": "LTFTや過渡増量など。通常は変更不要。",
    "Idle Speed": "値↑=アイドル高め/値↓=低め(低すぎるとストール)。",
    "Engine Sensors": "センサの読み(特性)。実際とズレると制御全体がズレる。センサ/吸気系変更時のみ、計測に基づき調整。",
    "Engine Limiters": "レブリミット/速度リミッタ。上げる場合はエンジン・駆動系の許容に注意。",
    "Engine Fan Control": "水温しきい値(A/D値)は 値↑=低い水温で回り始める(早く回る)/値↓=高い水温まで回らない。℃とは向きが逆。車速しきい値・タイマは値そのまま。",
    "Variable Cam Timing": "可変バルブタイミングの目標角。トルクの出方(低速/高速寄り)が変わる。",
    "Ignition Coil Dwell Time": "点火コイル通電時間。長すぎはコイル発熱、短すぎは失火。コイル交換時に合わせる。",
    "Patch": "ROM改変。イモビ無効・排気量変更など効果は項目ごとに大きく異なる。取扱注意・自己責任。",
    "Data Integrity Checks": "フェイルセーフ判定。むやみに変えると保護が誤作動/無効化される恐れ。基本は変更しない。",
    "Data Integrity Thresholds": "保護判定のしきい値。基本は変更しない。",
    "DTC Thresholds": "DTC(故障コード)の判定しきい値。診断と保護のための値なので変更しない。",
}


_EFFECT_FALLBACK_EN = ("Changing these values alters this category's behavior. "
                       "Do not change if unsure (especially sensors and diagnostics).")


def effect_of(en: str) -> str:
    if en is None:
        return _EFFECT_FALLBACK_EN if _LANG == "en" else _EFFECT_FALLBACK
    s = en.strip()
    g = _group_of(s)
    if _LANG == "en":
        return EN_CATEGORY_EFFECT.get(s) or EN_GROUP_EFFECT.get(g, _EFFECT_FALLBACK_EN)
    if s in CATEGORY_EFFECT:
        return CATEGORY_EFFECT[s]
    if g in GROUP_EFFECT:
        return GROUP_EFFECT[g]
    return _EFFECT_FALLBACK
