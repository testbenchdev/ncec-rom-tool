# i18n.py 単位修正一覧 / i18n.py Unit-Label Fix List

NCEC ECU マップエディタ(`ncecu/i18n.py` の `unit_of()`)に追加した単位推定ルールの一覧。
List of unit-inference rules added to `unit_of()` in `ncecu/i18n.py` for the NCEC ECU map editor.

- 背景 / Background: `unit_of()` は定義に単位が無いためキーワードから単位を推定する。キーワードは `category + name` を結合して判定するため、カテゴリ名(例 `spark`, `cam timing`)や条件節(例 `| RPM …`)が本来の単位を上書きする誤爆が起きていた。
  Because the LibreTuner definitions carry no units, `unit_of()` infers them from keywords in `category + name`. Category words (e.g. `spark`, `cam timing`) and condition clauses (e.g. `| RPM …`) were overriding the true unit.
- 方針 / Policy: 各修正は **カテゴリ/名称でスコープを限定**し、毎回 ROM 全体で**他カテゴリへの波及が無いこと**を回帰確認した。明確な誤りのみ修正し、曖昧なものは推測で書き換えず保留(無単位)とした。
  Every fix is **scoped by category/name** and regression-checked ROM-wide for **no leakage**. Only clear mislabels were changed; ambiguous cases were left unitless rather than guessed.
- ⚠️ 値はベンチ ECU 1 台の実測確認のみ(この一覧は表示上の単位ラベルの修正で、ROM の値は変えない)。
  Values verified on one bench ECU only (these are display-label fixes; ROM values are not changed).

---

## サマリ / Summary

- 単位ルールを追加/是正した項目: **28**(+ 軸ラベル是正 4)
  Unit-rule fix entries: **28** (+ 4 axis-label fixes)
- 是正されたテーブル数: 約 **114**(内 DTC Flags B の 37、DTC Thresholds の 9、電動ファンの水温しきい値 10 を含む。逆解析34表の作り直しは別)
  Tables corrected: ~**114** (incl. 37 in DTC Flags B, 9 in DTC Thresholds, 10 fan coolant thresholds; the 34 rebuilt RE tables not counted)

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
| 23 | Engine Fan Control | 10 | `°C`→ `A/D` | 2026-11-15。水温しきい値(中速/高速の作動・停止4表＋アフタークーリングの有効・無効6表、いずれも uint16)は ℃ ではなく水温センサ電圧の 10bit A/D 値(電圧=値×5/1024、値が大きいほど低い水温)。`ectcount.is_count_table`(表名の完全一致)で判定。浮動小数の `After Cooling Activation - Estimated ECT Threshold` は °C のまま。エディタは説明欄に ℃ 換算を表示。 / Coolant thresholds are ECT-sensor A/D counts, not °C; exact-name match; the editor shows the °C conversion. |
| 24 | Engine Fan Control / Engine Sensors - MAF | 6 | `s`→ `""` →(ファン5) `×0.1s` / `×25ms` | 2026-11-16。ファンのタイマ4・遅延1と、MAF の `Transition Delay`。いったん無単位にしたが、同日の逆解析で OS のタスク周期から 1 カウントの時間が分かった: アフタークーリングのタイマ=100ms、遷移遅延=25ms(エディタに秒の換算)。MAF の遅延は無単位のまま。 / Counts; the fan count periods were then derived from the OS task periods (after-cooling timers 100 ms, transition delay 25 ms). The MAF delay stays unitless. |
| 25 | Fuel Comp OL - Decel Fuel Restore Idle Thresholds | 1 | `km/h`→ `""` | 2026-11-16。`RPM divided by VSS Threshold` は回転数÷車速の比。無単位にする規則が後ろにあり、カテゴリ側の VSS 判定(km/h)に先に取られていた→先頭へ移動。 / A ratio; the existing rule was shadowed and has been moved to the top. |
| 26 | Spark Base - High Fuel Request Transition | 1 | `λ`→ `%` | 2026-11-16。`High Fuel Request Threshold (Lambda)`=6.25 の比較相手は燃料要求の増量%(RAM `0xFFFF7728`。`0x4DF38`)。ヒステリシス(%)と同じ量。 / Compared with the fuel-request enrichment in %. |
| 27 | Fuel Target CL - Base (no patch required) | 1 | `λ`→ `""` | 2026-11-16。値 0.02〜1.32 で高負荷ほど大きく、目標λとして成り立たない(意味未確定)。 / The values cannot be a lambda target; meaning unconfirmed. |
| 28 | WIP - Torque Model Bank (RE) / WIP - DBW Torque Coordinator (RE) | 34 | 定義を作り直し / rebuilt | 2026-11-16。表記述子の読み違い(12バイトずれ)で、各表に次の表の軸・寸法が付いていた。新しい名称に合わせ `multiplier`→×、`model table`→無単位 を追加(BMEP=kPa / Throttle=% / Torque=N·m / Spark=° は従来どおり)。 / Rebuilt from the ECU descriptors; unit rules follow the new names. |

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
| (全カテゴリ) `FFFF_xxxx` 軸 | 2026-11-16。「(未使用)」→「RAM 0xFFFFxxxx(未特定)」。この軸名は「入力が RAM 変数(名前未特定)」の意味で、未使用ではない。同じ番地を別の軸名で持つ表から分かるもの(`6800`=オルタ回転数、`6808`=オルタ温度、`8154`=界磁デューティ、`788F`=MAFステージ)はその名前で表示。 / `FFFF_xxxx` axes are RAM variables with no name yet, not unused. |
| 差・派生量の軸 | 2026-11-16。接頭辞だけで判定すると元の量と同じ表示になり値域と合わなかった軸を、名前の内容で表示: `VSS_DELTA`→車速偏差、`RPM_6DD8 - IDLE_SPEED`→回転数−目標アイドル、`IDLE_SPEED_7044 - RPM`→目標アイドル−回転数、`BARO - ((IAT…`→空気密度の指標、`VCT_ERR_ACCUM`→VCT誤差の累積、`ECT_START` / `ECT_AT_START`→始動時水温、`APP_DELTA_MODE`→アクセル変化モード、`ALT_AMPS` / `ALT_RPM` / `ALT_TEMP`→オルタ電流(A)・回転数(rpm)・温度(°C)、`O2S12_V`→リアO2電圧(V)、`REQ_TORQUE`→要求トルク(N·m)、`AX_GEN`→軸(入力未特定。2026-11-16 の逆解析後は使う軸なし: `SHUFFLE_HZ`→駆動系のしゃくり振動数(Hz)、`BPF_Q`→帯域フィルタのQ値、`GEAR_ENGAGED`→ギア(0=未接続)、`TIPIN_STAGE`→踏み込みの段階、12×7 の 3 面は `LOAD_6F44`)。`FFFF_xxxx` の数字は別 ROM の番地なので、分かったものは中身(オルタの吸気温・電源電圧の最低値・アイドル到達率、2026-11-17 に EVAP のパージ立ち上げ量・吸気負圧(kPa)、監視側の水温の平均・AT の回転比、ノックの負荷の変化量)、残りはこの ROM の実番地を表示。 / Difference and derived axes are labelled by what their name says. |
| Fuel Status OL - Decel | 2026-11-16。`Decel Transition - Load Threshold … | In-Gear` の軸は回転数(500〜7000)。定義の軸名 `LOAD_7004` を `RPM_6DD8` に直した(表引きの入力が回転数であることを `0x42206` で確認)。 / The axis is RPM; the definition's axis name was corrected. |

---

## データ衛生メモ / Data-hygiene notes (元定義ファイル由来 / from source defs)

- 末尾スペース付き重複カテゴリ / trailing-space duplicate categories: `Data Integrity Thresholds - DBW Torque Request ` (1本 BYPASSED-WIP), `Patch - Decel Fuel Cutoff ` (1本).
- 定義名の typo / typos in definition names: `Corection`(=Correction), `Detla`(=Delta), `Sarpk`(=Spark), `Multipier`(=Multiplier), `displacment`(=displacement).
- これらは解析上そのまま温存(定義ファイルを書き換えていない)。 / Left as-is in analysis (source defs not modified).
