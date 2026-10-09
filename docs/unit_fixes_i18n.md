# i18n.py 単位修正一覧 / i18n.py Unit-Label Fix List

NCEC ECU マップエディタ(`ncecu/i18n.py` の `unit_of()`)に追加した単位推定ルールの一覧。
List of unit-inference rules added to `unit_of()` in `ncecu/i18n.py` for the NCEC ECU map editor.

- 背景 / Background: `unit_of()` は定義に単位が無いためキーワードから単位を推定する。キーワードは `category + name` を結合して判定するため、カテゴリ名(例 `spark`, `cam timing`)や条件節(例 `| RPM …`)が本来の単位を上書きする誤爆が起きていた。
  Because the LibreTuner definitions carry no units, `unit_of()` infers them from keywords in `category + name`. Category words (e.g. `spark`, `cam timing`) and condition clauses (e.g. `| RPM …`) were overriding the true unit.
- 方針 / Policy: 各修正は **カテゴリ/名称でスコープを限定**し、毎回 ROM 全体で**他カテゴリへの波及が無いこと**を回帰確認した。明確な誤りのみ修正し、曖昧なものは推測で書き換えず保留(無単位)とした。
  Every fix is **scoped by category/name** and regression-checked ROM-wide for **no leakage**. Only clear mislabels were changed; ambiguous cases were left unitless rather than guessed.
- ⚠️ 値はベンチ ECU 1 台の実測確認のみ。実機書込みは未実施(SBL 未入手)。
  Values verified on one bench ECU only; no flashing performed (no SBL).

---

## サマリ / Summary

- 単位ルールを追加/是正したカテゴリ: **22**(+ 軸ラベル是正 1)
  Categories with unit-rule fixes: **22** (+ 1 axis-label fix)
- 是正されたテーブル数: 約 **95**(内 DTC Flags B の 37、DTC Thresholds の 9 を含む)
  Tables corrected: ~**95** (incl. 37 in DTC Flags B, 9 in DTC Thresholds)

---

## 修正テーブル / Fix Table

| # | カテゴリ / Category | 対象 / Affected | 変更 / Change (before→after) | 根拠・スコープ / Reason & scope |
|---|---|---|---|---|
| 1 | Spark Base - High Fuel Request Transition | #2,#3 (of 3) | `°`→ `%` / `""`(無単位) | `spark`→° 誤爆。`fuel request`+threshold/hysteresis/delay のとき (Lambda)→λ, (%)/hysteresis→%, delay→無単位。進角12本は不一致で°維持。 / `spark`→° misfire; name-priority block for fuel-request thresholds. |
| 2 | Spark Base Limit Comp - Power | 3 | `%`→ `°` | `| Fuel Power Enleanment …` は条件節。power-enleanment→% が先に当たっていた。ブロック先頭に「advance/retard を含むなら °」ガード追加。 / condition clause misfired into % block; added advance/retard guard. |
| 3 | Spark Base / Idle Transition | 3 | `°`→ `rpm`×2 / `%`×1 | `transition to spark base`/`to idle`: RPM Threshold→rpm, Enrichment Threshold→%(始動時増量=%を別表で確認)。 |
| 4 | Data Integrity Checks - Spark Idle Load - Base | 2 | `°`→ `""`(負荷/load) | `spark idle load` を含むなら無単位(値0.135〜0.5=負荷)。 |
| 5 | Data Integrity Checks - Spark Idle Load - AC Comp | 4 | `°`→ `""`(負荷/load) | 名が `AC Comp Base |…` で `spark idle load` 無し→カテゴリ判定 `spark idle load - ac comp` に拡張。 |
| 6 | Spark Idle Load - PSP Compensation | 2 (of 6) | `°`→ `""`(無次元定数/dimensionless) | Numerator/Divisor/Divisor Sub。`spark idle load - psp`+not multiplier→無単位。Multiplier 5本は × 維持。 |
| 7 | Data Integrity Checks - Spark Idle Load - Alternator Comp | 6 (+2) | `°`/`%`→ `g/s`(Estimated MAF Add 2) / `""`(他) | `spark idle load - alt`+not multiplier: `estimated maf`→g/s, 他→無単位。非DIの Decrement Rate 2本も無単位。 |
| 8 | Data Integrity Checks - Spark Idle Load - VSS Comp | 4 (of 5) | `°`/`km/h`→ `""` | `spark idle load - vss`+not multiplier→無単位。`vss threshold`→km/h 判定に「spark idle load は除外」ガード追加。Multiplier(×)1本維持。 |
| 9 | Spark Idle Limit Correction - AC Cycle Transition | 1 (+2) | `°`→ `""`(保持時間/カウント) | `spark idle`+`duration`→無単位。PS Cycle Transition の Duration 2本も是正。`… - Value`(進角°,8本)は対象外。 |
| 10 | Spark Idle / Base Limit Correction - Special Warm-Up WIP | 1 | `""`→ `°` | `Warm-Up Fuel Target` が warm+fuel target→無単位に誤爆。実体は進角目標(18°)。`spark idle correction`+`target`+not multiplier→°。 |
| 11 | Spark Correction - Transition from In-Gear to Idle | 1 | `°`→ `""`(タイマリセット値) | `timer reset`→無単位。Fuel の `Load Threshold Timer Reset`(=60)も整合。 |
| 12 | Spark Correction - High RPM and ECT | 4 | `°`→ `rpm`×2 / `°C`×2 | `high rpm and ect retard`: rpm threshold→rpm, ect threshold→°C。Rate/Limit/Restore(°)は不変。 |
| 13 | Spark Correction - Knock Retard | 9 | `°`→ `""`(load 2) / `rpm`(4) / `""`(delay 3) | `knock retard` カテゴリ: load→無単位, rpm→rpm, delay→無単位。KR量/最大/レート(°)は維持。 |
| 14 | Spark Correction - Tip-In Anti Lug | 1 | `°`→ `rpm` | `anti lug`+`rpm threshold`→rpm(限定)。グローバル化は VCT 等を巻き込むため不可と判断。 |
| 15 | Spark Correction - Tip-In High Speed | 5 | `°`→ `""`(delay 3) / `×`(APP Inc/Dec 2) | `tip-in retard high speed`: delay→無単位, app increasing/decreasing→×。Base Retard=°, Multiplier=× 温存。 |
| 16 | Spark Comp - Cold Advance | 1 | `°`→ `""`(タイマ) | `cold advance`+`add timer`→無単位。`Add Retard Rate | Timer Expired`(°/周期)は除外し ° 維持。 |
| 17 | Variable Cam Timing - Base | 2 | `°`→ `°C` | `ect threshold`/`ect hysteresis`+category `cam timing`→°C。VCT Target(カム角°)は温存。 |
| 18 | Variable Cam Timing - DO NOT MODIFY | 4 | `°`→ `rpm`×2 / `""`×2 | `vct error`+`rpm threshold`(not multiplier/correction)→rpm。`correction to apply`→無単位(値-600〜400はカム角でない)。 |
| 19 | DTC Thresholds | 9 | 下記参照 / see below | カテゴリ `dtc thresholds` 限定スコープ。 |
| 20 | DTC Flags B | 37 | `°`/`kPa`/`°C`/`V`/`%`/`g/s`/`rpm`/`km/h`→ `""` | 全126本が 0/1 の有効/無効フラグ。`dtc flags` カテゴリ一括で無単位。 |
| 21 | Patch - Engine Displacement | 3 | `cc`→ `""`(ROMアドレス/pointer) | `engine displacement`+`patch address`→無単位。実排気量値(replace NaN…in cc)は cc 温存。 |
| 22 | WIP - Alternator | 2 | `rpm`→ `V`(Voltage Desired Add) / `×`(WIP Limit) | `alternator`+`wip`: `voltage desired`→V, `wip limit`→×。条件節 `| RPM …` の誤爆是正。Base RPM Threshold=rpm 維持。 |

### #19 DTC Thresholds の内訳 / breakdown (9 tables)

| 対象 / Table | before→after | 根拠 / Reason |
|---|---|---|
| P0011 … Over Advanced **Timer** | `°`→`""` | uint16 のタイマ計数(`timing`→° 誤爆) / timer count, not angle |
| P0134 AFR Element **Impedence** Threshold | `AFR`→`Ω` | 素子インピーダンス 3万〜8万Ω(`afr`→AFR 誤爆) / sensor impedance |
| P0016 CPK-CMP **Sync Offset** | `""`→`°` | VCT の CKP→CMP オフセットと同一量 / crank-cam phase offset |
| P0638 … **TP Threshold** | `""`→`%` | スロットル位置しきい値 / throttle position threshold |
| P0601 Req Torque 20C6 **Activation Count** A/B | `N·m`→`""` | 発生回数カウント / occurrence count |
| P0601 TP Comp 20C8 **Activation Count** | `%`→`""` | 回数カウント / count |
| P0601 Req Torque 20CA **Activation Count** A/B | `N·m`→`""` | 回数カウント / count |

維持 / Kept: Fuel Trim=%, Load/AFS=無単位, ECT Threshold=°C, Requested Torque (Min/Delta)=N·m, TP factor for Estimated MAF=g/s.

---

## 付録: 軸ラベルの是正(非単位) / Appendix: Axis-label fixes (non-unit)

| カテゴリ / Category | 変更 / Change |
|---|---|
| Intake Manifold Runner Control (AT Only) | X軸内部名 `2500/IMRC_DIVISOR_82DC` を「IMRC移行進捗(%)」へ別名化(`AXIS_SPECIAL` 追加、Interpolation Bias 専用、他軸誤爆なし)。`unit_of` は変更なし。 / Aliased X-axis to "IMRC transition progress (%)" via a dedicated `AXIS_SPECIAL`; `unit_of` unchanged. |
| Spark Correction - Tip-In Anti Lug 他 | 算出ギア軸 `RPM/VSS*36.37` を「算出ギア(回転数/車速)」へ別名化(`AXIS_SPECIAL`)。 / Aliased calc-gear axis `RPM/VSS` to "Calc Gear (RPM/speed)". |

---

## データ衛生メモ / Data-hygiene notes (元定義ファイル由来 / from source defs)

- 末尾スペース付き重複カテゴリ / trailing-space duplicate categories: `Data Integrity Thresholds - DBW Torque Request ` (1本 BYPASSED-WIP), `Patch - Decel Fuel Cutoff ` (1本).
- 定義名の typo / typos in definition names: `Corection`(=Correction), `Detla`(=Delta), `Sarpk`(=Spark), `Multipier`(=Multiplier), `displacment`(=displacement).
- これらは解析上そのまま温存(定義ファイルを書き換えていない)。 / Left as-is in analysis (source defs not modified).
