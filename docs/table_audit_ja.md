# テーブル監査レポート(定義 vs 実ROM / ECU記述子補正後)

ROM: ncec_rom_dump.bin (CALID LFG7EG000) / 定義: defs/lfg7eg.xml

- 正常(clean): **398**
- ECU記述子から自動補正済み(検証OK, エディタで✓): **33**
- 要注意(残・未補正, エディタで⚠, 編集非推奨): **92**
- 合計: 523

## 背景
汎用定義 lfg7eg.xml はこの個体ROMの一部テーブルの軸点数と一致せず桁ずれが生じる。
ECU内部のテーブル記述子([Y,X,data,0,(rows,cols)])から真次元を取得し、値が妥当範囲に
収まることを検証できたものは自動補正(ncecu/_corrections_data.py)。検証を通らないものは⚠のまま。

## 自動補正済みテーブル(✓)

- @0xBCCB4 KS Capture Start | Cylinder 1 → 14×8
- @0xBCDEC KS Capture Start | Cylinder 2 → 14×8
- @0xBCF24 KS Capture Start | Cylinder 3 → 14×8
- @0xBD05C KS Capture Start | Cylinder 4 → 14×8
- @0xBD194 KS Capture End | Cylinder 1 → 14×8
- @0xBD2CC KS Capture End | Cylinder 2 → 14×8
- @0xBD404 KS Capture End | Cylinder 3 → 14×8
- @0xBD53C KS Capture End | Cylinder 4 → 14×8
- @0xBDAA4 KS Historic to Safe Magnitude - Scaling | Cylinder 1 → 14×8
- @0xBDCBC KS Historic to Safe Magnitude - Scaling | Cylinder 2 → 14×8
- @0xBDED4 KS Historic to Safe Magnitude - Scaling | Cylinder 3 → 14×8
- @0xBE0EC KS Historic to Safe Magnitude - Scaling | Cylinder 4 → 14×5
- @0xBE2F8 KS Historic Magnitude - Max | Cylinder 1 → 14×5
- @0xBE45C KS Historic Magnitude - Max | Cylinder 2 → 14×5
- @0xBE5C0 KS Historic Magnitude - Max | Cylinder 3 → 14×5
- @0xBE724 KS Historic Magnitude - Max | Cylinder 4 → 14×5
- @0xBEE18 KS Historic Magnitude - Fold | Cylinder 1 → 14×5
- @0xBEF7C KS Historic Magnitude - Fold | Cylinder 2 → 14×5
- @0xBF0E0 KS Historic Magnitude - Fold | Cylinder 3 → 14×5
- @0xCA1F0 Load Scaling - VE Correction Mult → 14×15
- @0xCD13C Fuel Target OL (Lambda) | APP Above WOT Threshold, H → 13×8
- @0xCD53C Fuel Target OL (Lambda) | APP Below WOT Threshold, L → 14×13
- @0xCD880 Fuel Target OL (Lambda) | APP Below WOT Threshold, H → 14×13
- @0xCE7E4 Spark Base | High Fuel Demand, High-Det → 8×15
- @0xCEDDC Spark Base | Low Fuel Demand, High-Det → 8×15
- @0xCF3D4 Spark Base | High Fuel Demand, Low-Det → 8×15
- @0xCF9CC Spark Base | Low Fuel Demand, Low-Det  → 14×7
- @0xCFD68 Spark Base - ECT / IAT Comp - RPM x Load Multiplier → 9×9
- @0xD0494 Spark Base Limit | OL → 14×15
- @0xD0850 Spark Base Limit | CL → 8×15
- @0xD1AAC Spark Cold Advance | Not Idle → 13×17
- @0xD1E98 Spark Cold Advance | Not Idle, IMRC → 9×9
- @0xF6084 Throttle Duty Delta - Maximum Change in Duty Before  → 12×29

## 要注意(残)テーブル — 編集非推奨

- @0xB8854 [エンジンセンサ - 吸気圧(MAP)] Manifold Vacuum (estimated) | MAP Fault 
- @0xBADC4 [可変バルブタイミング(VCT) - ベース] VCT Target
- @0xBBAD0 [点火コイル通電時間(ドウェル)] Ignition Coil - Dwell Time | Speed Limiter Ina
- @0xBBDF0 [点火補正 - ノックリタード] KR Accumulator - Minimum KR for Accumulation
- @0xBBF98 [点火補正 - ノックリタード] Timing Restoration - KR Decrement Rate | Knock
- @0xBC0FC [点火補正 - ノックリタード] Timing Restoration - KR Decrement Rate | Knock
- @0xBE888 [エンジンセンサ - ノックセンサ(KS)] KS Historic Magnitude - Min | Cylinder 1
- @0xBE9EC [エンジンセンサ - ノックセンサ(KS)] KS Historic Magnitude - Min | Cylinder 2
- @0xBEB50 [エンジンセンサ - ノックセンサ(KS)] KS Historic Magnitude - Min | Cylinder 3
- @0xBECB4 [エンジンセンサ - ノックセンサ(KS)] KS Historic Magnitude - Min | Cylinder 4
- @0xBF244 [エンジンセンサ - ノックセンサ(KS)] KS Historic Magnitude - Fold | Cylinder 4
- @0xBF600 [エンジンセンサ - 空燃比(AFS)] AFS (Lambda) Scaling - Interpolated Current to
- @0xBF658 [エンジンセンサ - 空燃比(AFS)] AFS (Lambda) Scaling - Non-Interpolated Curren
- @0xC01A8 [点火補正 - 加速時リタード(Tip-In)] Tip-In Retard First Gear - RPM Multiplier | MT
- @0xC02F0 [点火補正 - 加速時リタード(Tip-In)] Tip-In Retard Shared - ECT Multiplier | MT
- @0xC048C [ギア比] Gear (Estimated) | Decel, Cruise Control, Tip-
- @0xC04EC [点火補正 - 加速時リタード(Tip-In)] Tip-In Retard Wrong Gear - Retard Multiplier |
- @0xC0578 [点火補正 - 加速時リタード(Tip-In)] Tip-In Retard Wrong Gear - Retard Limit
- @0xC49CC [燃料状態(開ループ) - 減速] OL Decel Transition - Load Threshold (Maximum 
- @0xC4BFC [燃料状態(開ループ) - 遷移] OL Transition - Load Threshold | High Det
- @0xC4C6C [燃料状態(開ループ) - 遷移] OL Transition - Load Threshold | Normal
- @0xC4CDC [燃料状態(開ループ) - 遷移ディレイ] OL Transition B Delay Disable - Throttle Duty 
- @0xC7D7C [DBW - 目標スロットルデューティ] APP to Throttle Duty Desired - Max
- @0xC8A24 [DBW - 目標スロットルデューティ] APP to Throttle Duty Desired - Neutral
- @0xC8D7C [吸気マニホールド ランナー制御(AT限定)] IMRC Cold Exit - Throttle Duty Threshold
- @0xC94F4 [エンジン負荷 - 上限] Load Limit | CMP Fault
- @0xC955C [エンジン負荷 - 上限] Load Limit | No Fault
- @0xCA61C [エンジン負荷 - スケーリング] Load Scaling - VE Correction Mult - VCT Comp A
- @0xCADC4 [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool  | AT with Timer Active
- @0xCB678 [燃料噴射時間 - オフセット/スケーリング] Injector Scaling
- @0xCB71C [燃料噴射時間 - オフセット/スケーリング] Injector Battery Offset
- @0xCBA04 [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | IMRC, RPM @
- @0xCBAD8 [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | IMRC, RPM @
- @0xCBBAC [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | IMRC, RPM @
- @0xCBC80 [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | RPM @ 900
- @0xCBD54 [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | RPM @ 1500
- @0xCBE28 [燃料噴射時間 - 過渡補正(X-Tau)] Injected Fuel (%) To Intake Pool | RPM @ 2300
- @0xCBEFC [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | IMRC, RPM @ 900
- @0xCBFD0 [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | IMRC, RPM @ 150
- @0xCC0A4 [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | IMRC, RPM @ 230
- @0xCC178 [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | RPM @ 900
- @0xCC24C [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | RPM @ 1500
- @0xCC320 [燃料噴射時間 - 過渡補正(X-Tau)] Intake Pool Evaporation Rate | RPM @ 2300
- @0xCC774 [燃料補正(開ループ) - 減速燃料カット] Fuel Cut Multiplier - Enleanment Rate | Idle, 
- @0xCCE00 [燃料補正(開ループ) - 減速燃料復帰] Decel Enrichment | Decel Mode 8, Brake Off, EC
- @0xCD0B4 [燃料補正(開ループ) - パワー時リーン化] Power Enleanment Reset Delay Bypass - Load Thr
- @0xCD330 [目標空燃比(開ループ) - ベース] Fuel Target OL (Lambda) | APP Above WOT Thresh
- @0xCDBC4 [燃料補正(開ループ) - パワー時リーン化] Power Enleanment - Base (Lambda) | OL
- @0xCDEF0 [燃料補正 - 吸気輻射熱] Radiant Intake Heat Enrichment
- @0xCE2C8 [点火補正 - ストール復帰リタード] Stumble Recovery Retard | MT, Not In-Gear, Idl
- @0xCE590 [点火 - ベース] Spark Base | High Fuel Demand, High-Det, IMRC
- @0xCEB88 [点火 - ベース] Spark Base | Low Fuel Demand, High-Det, IMRC
- @0xCF180 [点火 - ベース] Spark Base | High Fuel Demand, Low-Det, IMRC
- @0xCF778 [点火 - ベース] Spark Base | Low Fuel Demand, Low-Det, IMRC
- @0xCFF38 [点火ベース補正 - 水温/吸気温] Spark Base - ECT / IAT Comp - IMRC
- @0xD00C4 [点火ベース補正 - 水温/吸気温] Spark Base - ECT / IAT Comp - Base
- @0xD0250 [点火ベース補正 - 水温/吸気温] Spark Base - ECT / IAT Comp - Power
- @0xD0BF4 [点火ベース上限] Spark Base Limit | IMRC
- @0xD0E44 [点火ベース上限] Spark Base Limit - VCT Add | VCT GT 5
- @0xD11C4 [点火ベース上限補正 - パワー] Power Comp - Maximum Advance | Fuel Power Enle
- @0xD4024 [燃料補正(閉ループ) - 暖機触媒効率チェック リアO2トリム] Warm-Up Cat Efficiency RO2S Trim - Base
- @0xD49D8 [燃料補正(閉ループ) - 暖機触媒効率チェック] Warm-Up Cat Efficiency Check - CL Oscillation 
- @0xD5760 [排ガス - EVAP(蒸発ガス)] EVAPCP Base - IAT Multiplier
- @0xD6604 [点火 - アイドル上限] Spark Idle Limit | IMRC
- @0xD759C [点火アイドル負荷 - ベース] Spark Idle Load - Base
- @0xDA734 [DTC - 有効化しきい値] DTC P0421 Monitor Warm Up CAT Load Threshold -
- @0xDA79C [DTC - 有効化しきい値] DTC P0421 Monitor Warm Up CAT Load Threshold -
- @0xDC460 [DTC - 有効化しきい値] DTC P0016 - CPK-CMP Sync Offset
- @0xED874 [目標空燃比(開ループ) - ベース] [Flex] Fuel Target OL (Lambda) | APP Above WOT
- @0xEDA68 [目標空燃比(開ループ) - ベース] [Flex] Fuel Target OL (Lambda) | APP Above WOT
- @0xEDC74 [目標空燃比(開ループ) - ベース] [Flex] Fuel Target OL (Lambda) | APP Below WOT
- @0xEDFB8 [目標空燃比(開ループ) - ベース] [Flex] Fuel Target OL (Lambda) | APP Below WOT
- @0xEE2EC [点火 - ベース] [Flex] Spark Base | High Fuel Demand, High-Det
- @0xEE540 [点火 - ベース] [Flex] Spark Base | High Fuel Demand, High-Det
- @0xEE8E4 [点火 - ベース] [Flex] Spark Base | High Fuel Demand, Low-Det,
- @0xEEB38 [点火 - ベース] [Flex] Spark Base | High Fuel Demand, Low-Det
- @0xEEEDC [点火 - ベース] [Flex] Spark Base | Low Fuel Demand, High-Det,
- @0xEF130 [点火 - ベース] [Flex] Spark Base | Low Fuel Demand, High-Det
- @0xEF4D4 [点火 - ベース] [Flex] Spark Base | Low Fuel Demand, Low-Det, 
- @0xEF728 [点火 - ベース] [Flex] Spark Base | Low Fuel Demand, Low-Det 
- @0xEFAE4 [点火ベース上限] [Flex] Spark Base Limit | OL
- @0xEFEA0 [点火ベース上限] [Flex] Spark Base Limit | CL
- @0xF0244 [点火ベース上限] [Flex] Spark Base Limit | IMRC
- @0xF0494 [点火ベース上限] [Flex] Spark Base Limit - VCT Add | VCT GT 5
- @0xF0810 [可変バルブタイミング(VCT) - ベース] [Flex] VCT Target
- @0xF0E54 [目標空燃比(閉ループ) - ベース] Fuel Target CL - Base (Lambda)
- @0xF1250 [目標空燃比(閉ループ) - ベース] [Flex] Fuel Target CL - Base (Lambda)
- @0xF17CC [エンジンセンサ - MAFエミュ(スピードデンシティ)] Speed Density - Volumetric Efficiency
- @0xF2380 [燃料補正 - 加速増量(Tip-In)] Tip-In Fuel Enrichment
- @0xF255C [エンジンセンサ - MAFエミュ(Alpha-N)] Alpha-N - Volumetric Flow
- @0xF4A1C [DTC - 有効化しきい値] DTC P0601 Requested Torque Delta Threshold
- @0xF4A7C [DTC - 有効化しきい値] DTC P0601 Requested Torque Delta Threshold DUP