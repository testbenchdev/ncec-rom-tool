# NCEC ROM Tool — トピック索引（決定ログ）

長くなった協議内容を**トピックごとに「何を・どこで決めたか」**で引けるようにした地図です。各項目に
**要点／状態／参照**を付けています。状態の凡例：✅実証（実機で確認）・🧪設計/静的検証のみ（未実機）・📋資料/方針・⚠注意。

参照の見方：`CHANGELOG`=`CHANGELOG_ja.md` の該当版、`docs/…`=手順/解析書、`ncecu/…`・`tools/…`=コード、
`mem:…`=自動メモリ（`~/.claude/.../memory/`）。

**※ v2.71 の文書整理での読み替え：** 古い節の「参照」に残る旧ファイル名は次のとおり。`setup_wsl_newpc_ja.md`・`wsl2_socketcan_ja.md` → `setup_wsl_ja.md`／`can_flash_ready_ja.md`・`flash_speed_ja.md` → `flash_ja.md`／`flatshift_oncar_test_ja.md` → `tuning_flatshift_ja.md`／`revdrop_bench_ja.md` → `revdrop_ja.md`／`map_analysis_JA.md` → `map_analysis_JA.html`。`PROJECT_HANDOFF_ja.md`・`sh7058_flash_spec.md`・`self_write_feasibility_ja.md`・`idle_base_ja.md`・`autoblip_*.md` は削除した（`NCEC_ROM_Tool_v2.70_FULL.zip` の中にある。PROJECT_HANDOFF だけは無い）。ROM 名は `ncec_rom_dump.bin` → `rom_data/ecu_readout_yahooauction.bin`。`flatshiftrun.bin` などは現存しない（§19）。

---

## 0. 目次
1. 基盤・対象・安全ルール
2. 診断プロトコル（通信）
3. SecurityAccess（シード鍵）
4. ROM読み出し・照合
5. フラッシュ書込機構・SBL・復旧
6. ROM構造・定義・エディタ
7. チェックサム
8. 学習値・KAM（キープアライブRAM）
9. ライブ計測・Mode23ライブRAM・ダッシュボード・ログ
10. フラットシフト
11. アンチラグ／減速ポップ
12. 電子スロットル1:1化（DBW）
13. オートブリップ（段階B/C/C-FF/C-fast）
14. E-Gas L2監視・DIペア
15. 環境構築（WSL／別PC）
16. 未解決・次にやること
17. 回転落ち高速化（レブハング低減・DFCO強化）
18. アイドル回転補正（目標回転）・定義監査
19. v2.71：ライブ間引き統一・MAP追従の是正・アンチラグA〜D・統合マニュアル・ROM/フォルダ整理
20. v2.80：表の分割表示・ペア同時編集・編集操作と元に戻す・ショートカット・ウィンドウの記憶／11-17 の解析の反映

---

## 1. 基盤・対象・安全ルール 📋⚠
- 対象＝**予備中古ECUのみ**（Denso 279700-4073 / Mazda LFG7 / SH7058, BE）。実車純正PCMには書かない。予備は現在**車載**。
- 開発環境：Windows・Python 3.14・DSD TECH SH-C30L（gs_usb）・CAN 500kbps・要求0x7E0/応答0x7E8。
- 安全ルール：フラッシュは都度ユーザー明示確認／電源を転送中に落とさない／車上は終端を足さない（既に約60Ω）／既知良好フルイメージ常備／排ガス改造は範囲外。
- 参照：`CLAUDE.md`、`docs/SETUP_ja.md`、`docs/PROJECT_HANDOFF_ja.md`、`mem:project-ncec-ecu`、`mem:can-termination`、`mem:feedback-confirm-only-important`、`mem:feedback-japanese-everything`。

## 2. 診断プロトコル（通信） ✅
- KWP2000系over-CAN。TesterPresent=`3E 01`、セッション`10 81/85/87`、SecurityAccess`27 01`→3バイトSeed。
- ライブ受信は応答ID(0x7E8)フィルタ＋ISO-TP条件付きドレインで高速化（机上30–40Hz維持）。
- 参照：`docs/diag_findings.md`、`ncecu/canbus.py`・`ncecu/isotp.py`・`ncecu/diag.py`、`CHANGELOG` v2.60。

## 3. SecurityAccess（シード鍵） ✅
- **解決済・実機で `67 02` 成功**。アルゴリズム＝Seed+固定文字列`MazdA`、初期値0xC541A9の64ラウンドビット混合、level=1。
- 鍵検証ルーチン ROM 0x7DFE0。公開鍵対・自己整合25/25で検証。LibreTuner `generateKey` とも一致（純Python化可）。
- Key送信は1回ずつ（誤送反復でロックアウト NRC 0x36/0x37）。
- 参照：`ncecu/security.py`、`tools/unlock.py`、`mem:project-ncec-ecu`。

## 4. ROM読み出し・照合 ✅
- **読み出し**＝UDS Mode23（`23 <addr> <len>`→`63 …`）。`read_full_rom()` は認証(10 85/27)＋Mode23ループ＋10 81復帰、**消去・書込は一切しない**。
- **ECUと照合**＝`read_full_rom()`→`romdiff.compare()`（純バイト/テーブル比較、ECU非接触）。**ROM書込は発生しない（本セッションで実証）**。
- 申し送り（非書込）：照合は 10 85+27 に入る→車載はエンジンOFF・後に電源入れ直し。中止/失敗時は 10 81 復帰を送らずプログラミングセッション残存（電源入れ直しで復帰）。
- 参照：`ncecu/mode23.py`・`ncecu/romdiff.py`・`ncecu/flash.py`（read系）、`ncec_editor.py`（compare_ecu）、`tools/read_mem.py`、`docs/live_ramread_ja.md`。

## 5. フラッシュ書込機構・SBL・復旧 ✅⚠
- **ハンドシェイク（実証）**：auth(10 85+27)→`B1 00 B2 00`→`34`(addr=0x8000/size=0xFF800)→`36`(TransferData, **0x400固定長**, ブロックカウンタ無)→`37`。※`34`の0x8000はRAM展開先(0xFFFF8000)で、**flash書込先ではない**。
- **SBL必須・入手済**：この個体はSBLアップロード方式。公開ツール(nc-flash等)のSBL本体＋鍵計算は非公開だが、**本プロジェクトはromdrop.exeを自分でREしてNC1用SBL(0x1800)を入手済→CAN実機フラッシュ成功**（予備単体・車載OBD2とも）。LibreTunerの no-SBL(size 0xF8000) は NRC 0x31 で拒否＝不適。
- **ハンドオフ（RE）**：ストリームに8バイト`*SBL_END`が現れた瞬間 RAM 0xFFFF8000 へジャンプ（ECU Reset不要）。リンク0xFFFF8000/SP=0xFFFFBFA0。
- **復旧（本セッションで確定）**：書込失敗は**車載でも電源再投入→CAN再書込で毎回復旧**実績。失敗は全て**SBLハンドオフ後の書換中・進捗バラバラ**で起き、恒久ブリックは未観測。成立理由＝**flash書込は0x2000以降**（SBLが補正ROM[0x2000:]を書く。コード `ROM_FLASH_START_MIN=0x2000`、0x0–0x1FFFは保護）、**先頭8KB（0x0000–0x1FFF＝EB0+EB1＝リセットベクタ0xAAC＋常駐CAN再書込ハンドラ 0x1094/0x1480/0x1A88/0x1BA4）が消去も書込もされず無傷**。→最悪ケースは「再書込するまで非始動」。BDM/JTAG復旧手段は無し。利用者向けの復旧説明は**取扱説明書**（`tools/gen_manual.py`生成PDFの「書き込みに失敗したら(復旧)」）に記載。
- **自作SBL方針（未着手）**：npkern相当（FKEY/FCCS、SH7058 FL_ERASE_BASE=0xFFFF1000/FL_WRITE_BASE=0xFFFF2000、128B書込）。設計上の不変条件＝①先頭8KB(0x0000–0x1FFF)不可侵 ②KAM 0xFFFFBFA0–BFFF不可侵 ③中断しても先頭8KBが残る消去順。通信はK-line→CANへ差替。
- 参照：`ncecu/flash.py`・`tools/flash_writeback.py`・`tools/flash_validate.py`・`tools/probe_download.py`・`tools/extract_sbl*.py`、`docs/sh7058_flash_spec.md`・`docs/can_flash_ready_ja.md`・`docs/self_write_feasibility_ja.md`・`docs/SH7058_hardware_notes.md`、`CHANGELOG` v1.00、`mem:flash-recovery-empirical`、`mem:project-ncec-ecu`。

## 6. ROM構造・定義・エディタ ✅
- エディタ `ncec_editor.py`（tkinter, 日英）。定義は **LibreTuner定義を採用**（`defs/libretuner/main.json`+`LFG7EG.json`、875テーブル・読取0誤り）。旧romdrop XMLは125テーブル疑義。
- 保存時チェックサム自動補正。テーブル寸法は fixed_dims→descriptor補正→def の順。疑義テーブルは⚠表示。
- ROM構造：ROM_ID 0xFFC4C、CAL_ID 0xC0046/0xB8046、GEN_DETECT 0x2030=0x35（前期）。
- 参照：`ncecu/defs.py`・`ncecu/ltdef.py`・`ncecu/rom.py`・`ncecu/corrections.py`・`ncecu/i18n.py`、`docs/table_audit_ja.md`・`docs/map_analysis_JA.md`/`.html`・`docs/editor_help_ja.md`、`mem:project-ncec-ecu`。

## 7. チェックサム ✅
- 表 `0xFF650`（12B/エントリ: start,end,…）＋期待値 `0xFF658`。判定＝区間32bit和 + 格納値 == `0x5AA5A55A`。全35領域。
- 再計算＝`ncecu.checksum.recalculate`、全検証＝`checksum.all_valid`。自作ビルドは必ず通す。
- 実行時にも自己診断（0xEB4E 他、参照3箇所）→結果はRAMフラグ/監視へ（KAMは消さない）。
- 参照：`ncecu/checksum.py`、`mem:ecu-kam-learning`。

## 8. 学習値・KAM（キープアライブRAM） ✅（本セッションRE）
- **学習値（アイドル/全閉点）＝バッテリバックアップSRAM(KAM)**。crt0 0x66c が RAM `0xFFFFBFFC` を固定マジック `0x5AA5A55A` と比較（一致=保持/不一致=コールド初期化）。
- マジックは**固定値でcal/チェックサムと無関係**→**フラッシュ内容変更では再学習は強制されない**。再学習が要るのは **KAMを失った時だけ**（+B/完全電源断・バッテリ外し・KAM領域上書き）。
- 参考（スロットル/アイドル簡易学習の手順は実在するがメーカー正規手順ではない。要点＝全閉点学習＋アイドル学習）。
- 参照：`mem:ecu-kam-learning`、`mem:flash-recovery-empirical`。

## 9. ライブ計測・Mode23ライブRAM・ダッシュボード・ログ ✅
- OBD Mode01多PID（>10Hz）＋Mode03/07 DTC＋AFR。**PID間引き**（`live_intervals.json`、GUI設定）。
- **Mode23ライブRAM**：クラッチ0xFFFF7100・減速ステータス0xFFFF6FCC・排気温0xFFFF777C・ノック=レベル0xFFFF4E20＋KR0xFFFF7C44の2本（イベント/生検出/カウント等は撤去＝ram_readsで追加可）・ゲートAPP0xFFFF56C8・IPW0xFFFF7380・duty派生。※**Mode23有効化パッチはユーザ適用**（@0x84C04→0x10/@0x84C07→0x0F/@0x7F734→nop）。
- ダッシュボード：数値/棒/メーター/グラフ、色・スケール・周期・アラーム（`dashboard_layout.json`）。ログ分析チャート `ncec_chart.py`。
- **★ノック補正の徹底RE（2026-11-14・読み取り＋全ログ照合・確定版）**：「ノック値が不変（全開でも）」の指摘を検証。**結論＝ノック制御は正常で、ログにも3回KRが記録されていた。不変に見えたのはライブ表示の番地/ラベル誤り3件。**①**本物のKR＝`0xFFFF7C44`**（本体`0xFFFF7C20`の1イベント遅れ写し）。ログ実測が cal と一致：+1.7（KR Increment `0xBBCAC`）→−0.17/燃焼（Listen Active `0xBBF98`）、負荷<40%で−0.3515/燃焼（Listen Inactive `0xBC0FC`）。作動3回＝`..211638` t=10.4s/282.7s、`..182622` t=62.0s、いずれも1100–1330rpm・負荷52–67%。②`0xFFFF7C3A` は**始動後の燃焼回数（255飽和）**（コード0x4FE06：状態`0xFFFF7346` bit7で0、以後+1。冷間始動ログで0→255を確認）＝255固定は正常、ノック回数でもセンチネルでもない。③旧KR `0xFFFF7C4C` は表`0xBBDF0`（KR積算の最小KR）の引き値、`0xFFFF7C60` もノック強度ではない（未確認）。④`0xFFFF4E14` は「イネーブル」ではなく**ノックセンサ生検出フラグ**＝`レベル0xFFFF4E20 ≥ 適応しきい値0xFFFF4E58`（気筒別処理0xB32A末尾 0xB61A–0xB62C）。`0xFFFF7E89` はその写し（0x52A40）。イベント `0xFFFF7C3C`＝生検出 かつ 始動後24燃焼以上（`0xBBCA7`）。Knock Listen cal＝1000–5250rpm・負荷≥0.4（5250rpm超は判定対象外）。**同日の途中説明2つ（「低負荷ゲート」「イネーブル4E14が非活性」）は誤りで破棄**（後者の「大半のセッションで0」は実測でなく推測だった）。是正＝`livelog.py`/`ram_reads.json`：ch0x106を role KR に、0x102/0x104/0x105を改名、0x10F=ノック生検出、重複の0x110(4E14)は削除（ch番号↔番地は不変）。`ncec_dashboard.py`：ラベル是正＋**誤警報撤去**（0x104≥24は走行中常時赤だった／0x102≤−3）→ KR(0x106)≥1.5°で赤。`ncec_chart.py` 既定系列を0x106に。`docs/live_ramread_ja.md` 差し替え。未解決＝全開時の余裕度（`0xFFFF4E20` と `0xFFFF4E58` を足して1本記録すれば見える）、`0xFFFF7C60` の正体。教訓＝**番地の意味はコードだけで決めず、ログ値が cal 定数と一致するかで確かめる**。詳細 `docs/knock_re_ja.md`、`mem:knock-re`。RE注意＝ノックcalは0x000BBxxx帯でROMの4バイト一致走査がジャンプ表(`000b b___`)と偽陽性衝突→実`mov.l`ロードのみで確定、FPU命令はcapstone不可でFPU対応逆アセンブラを使用。　**追補（同日・ユーザー指示）**：ライブ監視を**レベル `0xFFFF4E20`（ch0x114,新規）＋KR `0xFFFF7C44`** の2本に集約。0/1フラグ(イベント0x10E/生検出0x10F)・始動後燃焼カウント0x104・未確認0x105・旧KR 0x102 は撤去（ram_readsで随時追加可）。ノックセンサ入力はアナログ＝レベル(float)としきい値`0xFFFF4E58`(float)の比較結果が0/1フラグ。余裕度を見るならレベル＋しきい値。
- **ライブRAM監視を整理（2026-11-12〜13）**：オートブリップ用に増やしたMode23読みch（生ADC56B8-56C4/アイドル目標7140-7144/RPM-RAM 6D5C/L2旗2124/空気8090-80A8）を削除。**クラッチ0xFFFF7100・ブレーキ0xFFFF70EC/70EE は残す**（ユーザー指示）。**ゲートAPP 0xFFFF56C8 も残す**＝フラットシフトのゲート入力（`flatshift.py` RAM_APP＝この番地。当初blip扱いで削ったがユーザー指摘で復活）。**現在ギア0x10D（派生・CAN負荷なし）も残す**（当初削除→ユーザー指摘で復活）。残りはノック/EGT/IPW/開弁率/減速/クラッチ/ブレーキ/ゲートAPP/現在ギア＝Mode23読みグループ 10→6/周期＝ライブ更新が約1.7倍速。`ram_reads.json`＋`livelog.RAM_CHANNELS`両方を整理。削除の過剰を監査済（エディタの共有ヘルパ・フラットシフト/アンチラグ/電スロは無傷、他の誤削除なし）。
- 参照：`ncecu/livelog.py`・`ncecu/mode23.py`・`ncec_dashboard.py`・`ncec_chart.py`、`docs/live_ramread_ja.md`・`docs/dashboard_chart_ja.md`、`CHANGELOG` v1.40–v2.20, v2.60。

## 10. フラットシフト ✅（実車確認）
- 最終設計＝**読み取り専用・ゲートのみ**（RAM/レジスタ非書込＝文鎮化リスク原理ゼロ）。発動＝クラッチ0xFFFF7100=1 ∧ APP>閾 ∧ RPM>閾 ∧ VSS>下限 の間だけ。
- 2ケーブ：cave1 0xDE200＝**点火遅角**（クランプ呼出リテラル@0x4DA98フック）、cave2 0xDE400＝**点火カット**（コイル充電@0x19D04差替）。CAL 0xDE300–0xDE318。
- **実車確認(2026-11-01)**：遅角＝点火時期約20°低下、カット＝λリーン化・レブ頭打ち。
- 履歴：v1.10（CPP連動カットの誤認→停車専用と訂正）→v1.20第3（点火遅角）→v1.30エディタ→v2.40クラッチ番地訂正→v2.50第4（破棄）→v2.60最終。
- 参照：`ncecu/flatshift.py`・`tools/patch_flatshift_retard.py`、`docs/tuning_flatshift_ja.md`・`docs/flatshift_oncar_test_ja.md`、`CHANGELOG` v1.10–v2.60。

## 11. アンチラグ／減速ポップ 🧪⚠
- `ncecu/antilag.py` A/B/C（DFCO無効/RPMゲート/ツキ重視）。番地は純正+実例`ncec_immo_off_na_anti.bin`で確認。触媒・排気熱害注意。実車未検証。
- **逆向き＝シフトアップ回転落ち高速化は §17**（同じ減速カット率を“上げて”速く全カット。両立しない=1ROMにどちらか）。
- 参照：`docs/tuning_overrun_pops_ja.md`、`CHANGELOG` v2.30。

## 12. 電子スロットル1:1化（DBW） 🧪
- `ncecu/dbw_throttle.py`。ペダルマップを1:1寄りに、**制御＋監視を同値更新**（片側のみ＝監視不一致でフェイルセーフ）。指令上限を cap_margin引上。
- 制御@0xC7EE4…/監視@0xF7C90…、指令上限@0xC55FC/F7C24。例`ncec_immo_off_throttle1to1.bin`。実走未検証。
- 参照：`tools/patch_throttle_1to1.py`、`docs/tuning_throttle_ja.md`、`CHANGELOG` v1.60/v2.30。

## 13. オートブリップ（段階B/C/C-FF/C-fast・C-2） 🧪→エディタからは撤去（v2.71 でモジュール・ツール・文書・ROMも撤去。経緯の記録）
- **★エディタから全オートブリップ機能を撤去（2026-11-12, ユーザー指示）**：スポーツ走行前提では緩いブリップ（~500rpm/s天井）は無意味で、ROM編集では監視コヒーレントな高速ブリップが作れないと確定したため。エディタの 設定→パッチ から blip/段階C/C-2/C-FF/C-fast/スルーレート を削除、`_EXTRA_MODS`からも除外（ツリーに出ない）。**モジュール `ncecu/autoblip*.py`・`idle_slew.py`・CLI/解析ツール・docsは記録として残置**（エディタからは呼ばない）。i18nのblip*文言は休眠（未使用・無害）。READMEのオートブリップ行は未更新（リリース時に整理）。高速レブマッチは外部ハードのペダル信号インターポーザが唯一の実路線（mem:autoblip-design）。
- **★最終結論（2026-11-17、実車で確認・読み出しのみ）** ✅実測：P0601 の監視（`0xFFFF2124`）が使う基準値 `0xFFFF55A0` は、SCI1 で届く
  **ECU 基板上の別チップ（監視用 IC）の独立測定**（RDR1 `0xFFFFF00D` → `0xFFFF5072` → `0x1E970`/`0x1EAF6` → `55A0`、補数チェック付き。
  送信 TDR1 `0xFFFFF00B` @`0xE014`、シード `0x5AA5`）。アクセルを煽ると SCI1 の受信フレームの多数バイトと `55A8`/`55AA`（値＋補数）が連動し、
  送信側（`0xFFFF509A`〜）も主CPUのペダル/スロットルを送っている＝**外部チップが自前でペダルを測り、主CPUと双方向で照合**。
  ペダルADの取り込み `0x21A50`（`56B8`/`56BC`）を乗っ取っても監視の基準値には届かない。CAN の外部トルク要求 0x211 は上限（下げる方向）だけ。
  ∴ **ROM 編集では監視と整合する速いブリップは作れない（確定）**。残る筋は配線側でペダル電圧（APP1/APP2 両系統）を持ち上げる外付けハード（未着手）。
  v2.80 で `i18n.py` に休眠していたオートブリップ関連の文言も削除。参照：`mem:autoblip-design`（結果ファイル `read_sci1_pedal_result.txt`）。
- 目的＝レブマッチ自動化。L2監視と**コヒーレント**な方式を模索。
- **段階B/B'**：ペダル注入→L2が乖離で却下（不可）。
- **段階C**：アイドル総目標 0xFFFF7144 を持ち上げ（正規アイドル権限・コヒーレントだが遅い~500rpm/s）。フック0x3EC98/cave0xDF000。
- **段階C-FF**：空気を外部加算（cave 0xFFFF8090）→L2乖離でトリップ。pool転用フック0x57592。
- **段階C-fast（本セッション）**：ガバナIIR(0x54EBE)の極 0.89844(CAL 0xD6FD4, 参照1箇所0x54ED0) を**ブリップ窓だけ差し替え**て収束を速める。既定inert・静的検証合格・未フラッシュ。双子極0xD6FCC→v2候補。
- **段階C-fast ベンチ結果（2026-11-12, logs/0.7・0.5・0.3.jsonl）＝この極は効かない（行き止まり）** ✅実測：極0.7/0.5/0.3 の3本とも L2旗(0xFFFF2124)=0・DTCなしだが、回転上昇は約410/400/360rpm/s（段階C単独の約500rpm/sと同等以下）。差し替えたフィルタの入力 `0xFFFF80A8` がブリップ中 0.24〜0.25 で動いておらず、極を変えても出力が変わらない。スロットルは11.4→14.9%を約2.5秒かけて直線的に開く＝律速は一次遅れでなく積分器/レート制限。※フィルタ内部(7F48/7F54)は未記録で差し替えの実働は未確認だが結論は変わらない。次の候補＝ブリップ中に直線増加するRAM値の実測探索（読み取りのみ）。
- **★律速の正体＝アイドル目標のスルーレート制限を特定（2026-11-12, `tools/ram_ramp.py` 実測＋RE）** ✅実測/🧪RE：`0xFFFF7130` は「7140のコピー」ではなく**レート制限つき目標値**。総目標 `0xFFFF7144` が即2000へ跳んでも、7130 は約26.2ms周期で **+10rpm/周期（≈381rpm/s）** ずつ上がり、下降は **−5rpm/周期（≈191rpm/s）**。実回転はこれに密着追従（logs/ramramp_20261112_224541.jsonl）。処理本体＝関数 `0x3EDCE`–`0x3F072`（上昇 `min(現在+step_up, 目標)`／下降 `max(現在−step_down, 目標)`、書込 `0x3F05E`）。刻みは較正定数：**上昇 `0xD6AA0`/`0xD6AA4`=10、下降 `0xD6AB8`=5**（目標が1周期で156rpm超[`0xD6ACC`]跳んだ「大ジャンプ」モード=フラグ`0xFFFF71D5`のとき。通常は上昇1[`0xD6AA8/AC`]）。LibreTuner定義には無い番地。**監視側に同じ定数ブロックの写しがある**：制御 `0xD6A0C`–`0xD6AFC` ↔ 監視 `0xF4574`–`0xF4664`（240B完全一致、差 0x1DB68。上昇刻みの写し=`0xF4608`/`0xF460C`、下降=`0xF4620`）、監視側コード `0xB33xx`–`0xB35xx` が同じ構造でスルーを再計算。→ 速くするなら**制御側と監視側を同値で変える**のが筋（未実施・未フラッシュ）。旧記述「7130=7140の単純コピー・スルー無し」は誤り。
- **スルー刻み変更パッチ＝実車で却下（2026-11-12）** ❌実証：`ncecu/idle_slew.py`（較正定数のみ・制御`0xD6AA0/A4/B8`＋監視の写し`0xF4608/F460C/F4620`へ同値書込・純正値へ戻すとバイト一致）。rise=30/fall=30（両側同値・チェックサム正常）を実車に書いたら**起動直後にDTC P0606（プロセッサ系）＋スロットルがリンプ（0xFFFF56C8=15.0固定・約1776rpm）にラッチ**（クラッチ未踏＝ブリップ発動前から・0xFFFF2124=0）。**段階Cのみ（刻み変更なし）はDTC無し**＝切り分け決定的。→**アイドル目標の上昇レートは監視プロセッサが保護する安全パラメータ**で、編集は起動時整合チェックで弾かれる（P0601＝主ROMチェックサム、0xFFFF2124＝L2データ整合、のいずれとも別系統の第3の防壁）。復旧＝`flatshiftrun.bin`書き戻し＋電源入れ直し。エディタのダイアログは適用時に却下済み警告を出す。idle_up PoC(0xD6CDC+0xF4E2C)やC-fast(0xD6FD4+cave)はDTC無しだったので「監視領域の編集全般が弾かれる」のではなく**スルーレート定数が特別に保護**されている。
- **段階C-fast のGUI組込（2026-11-12）**：エディタの 設定→パッチ→「オートブリップ段階C-fast」で適用、適用後はツリー『パッチ - オートブリップ(段階C-fast)』で極(pole)等を直接編集。GUI生成＝CLI(`build_stagec_fast.py`)とバイト一致を自動テストで確認。手順＝`docs/autoblip_stagec_fast_bench_ja.md` §2.1。
- **段階C-2（車速×ギア比の目標・予測トリガ）実装（2026-11-12, 未フラッシュ）** 🧪：`ncecu/autoblip_stagec2.py`。段階Cの目標を固定でなく **target=clamp(車速×ratio[速度帯], floor=blip_rpm, ceil=rpm_max)** で演算（クラッチ踏の瞬間の車速で即決＝予測トリガ）。注入点0x3EC98は段階Cと同一＝**排他**、ケーブ/CAL=0xE0000/0xE0400。**状態なし（RAMラッチ不要＝書込リスクなし）**：per-gear の正確なラッチには安定スクラッチRAM（ram_findfree未確保）が要るため、車速帯でratioを選ぶ方式にした。gearspeed_on=0で固定floor＝段階C等価。CAL=ゲート6＋gearspeed_on＋floor/ceil＋vbr[5]＋ratio[6]（計19、ツリー編集可）。検証＝sh2emuでケーブ実行（帯選択・VSS×ratio・上下限クランプ・max(純正,目標)・全ゲート）、GUI結果＝build、段階Cとの排他。エディタ 設定→パッチ→「段階C-2」。**2つの限界明記**：①上昇は~400-500rpm/sのまま（目標を正すだけ・速くならない）②従来ブリップ検証は全て停車＝走行初検証。手順`docs/autoblip_stagec2_bench_ja.md`。
- 共通ゲート：blip_mode ∧ クラッチ(デッドマン) ∧ APP≈0 ∧ RPM<上限 ∧[任意ブレーキ]。
- 参照：`ncecu/autoblip*.py`・`tools/build_stagec*.py`・`tools/patch_autoblip_stageb.py`、`docs/autoblip_*_ja.md`、`mem:autoblip-design`・`mem:reference-nc-flash-autoblip`。

## 14. E-Gas L2監視・DIペア 📋
- L2＝独立に空気/スロットルを再計算し**乖離でトリップ**（P0601=0xFFFF2124）。監視ブロック0xFFFF2000台。
- **監視の基準は外部チップ（2026-11-17 実車で確認）**：ペダルの基準値 `0xFFFF55A0` は SCI1 経由の監視用 IC の独立測定で、主CPUと双方向で照合（§13）。
- **エディタでの扱い（v2.80）**：23 組の写しは ⇔ で並べて表示し、一致/不一致を表示。「ペア同時編集」（既定 ON）で片方の編集が両方に入る（§20）。
- DIペア（制御↔監視の同値要件）：APP→TP Desired、TP Delta閾、アイドル/tip-in複製。片側のみ変更＝フォルト。
- 参照：`mem:reference-nc-flash-autoblip`、`mem:autoblip-design`、`docs/autoblip_stagec_ff_bench_ja.md`。

## 15. 環境構築（WSL／別PC） 📋
- 別PCのgs_usb：`libusb-package`同梱DLLを自動注入（`ncecu/canbus.py`）。WSL2 SocketCAN対応、起動スクリプト。
- WSLgの既知事象：~~ダッシュボードのポップアップ点滅はWSLg/Weston由来（Tkでは直せない・許容）~~ → **v2.81 で解消**（X11 では右クリックメニューをウィンドウ内に描く `ncec_popup.InlineMenu`。§20）、`SystemButtonFace`はWSLgで無効→既定色を捕捉。
- **USB/IP接続切れによるエディタのフリーズ（2026-11-12 発生・対策済）**：Wi-Fi接続イベント→WSL仮想ネットワークのリセット→usbipdのTCPが中断（Windows側`Shared`／WSL側は`can0`残留）。この状態で `ip -details link show can0`（gs_usbがUSB制御転送で berr-counter を問い合わせる）を実行すると `usb_kill_urb` で割り込み不能のまま固まり、RTNLロックも握る。エディタはその終了待ちでフリーズした。対策＝`ncecu/wslcan.py`：状態はsysfsから読む／接続切れ（can0在り∧usbipd≠Attached）を検出して `can0` に触らず復旧手順を出す／タイムアウト後に子の終了を無期限に待たない。復旧は `wsl --shutdown`→起動し直し。予防＝車での作業中はWi-Fiを切る。手順＝`docs/setup_wsl_newpc_ja.md` §6。
- 参照：`docs/setup_wsl_newpc_ja.md`・`docs/wsl2_socketcan_ja.md`、`ncecu/wslcan.py`・`tools/setup_ncec_wsl.*`・`tools/ncec_wsl_launch.ps1`、`mem:wslg-dashboard-menu-flicker`・`mem:wslg-tk-systembuttonface`。

## 16. 未解決・次にやること 📋
- **オートブリップ＝ROM では不可で確定（2026-11-17 実車）**：監視の基準は外部チップの独立測定（§13 最終結論）。以下は 11-12 時点の記録。
- **オートブリップの速度＝頭打ち確定（2026-11-12）**：監視コヒーレントに速くする筋は出尽くした。段階C-fast（極0xD6FD4）＝効果なし（§13）。スルー刻み変更（0xD6AA0系）＝実車でP0606・リンプ却下（§13、レート定数は監視が保護）。ランタイム注入（段階B/B'/C-FF/D）＝L2却下済み。∴**監視コヒーレントなレブマッチの実用上限＝段階C（アイドル総目標持ち上げ、約400〜500rpm/s）**。これ以上速くするにはスロットル権限（監視独立のペダル/トルク源 or 監視プロセッサ）に触れる必要があり、プロジェクト方針（監視を無効化しない）の外＝追わない。残る改善余地は使い勝手（予測トリガ＋ギア×車速の目標演算で段階Cを実用化）＝**段階C-2として実装済（§13・未フラッシュ）**。次＝段階C-2の実車走行検証（停車→低速→と段階的に、L2旗0確認）。per-gear正確版は安定スクラッチRAM確保（ram_findfree）が前提。計測ツール＝`tools/ram_ramp.py`（Mode23読み取り専用・窓ごとに1ブリップ・クラッチ自動検出・L2旗で自動中止、`--selftest`/`--analyze`あり。2026-11-12作成、実機計測は未実施）。
- **回転落ち高速化（§17・2026-11-13 実装）**：レブマッチ＝回転を“上げる”側は監視で頭打ち（上記）だが、
  シフトアップの回転落ち＝回転を“下げる/燃料を減らす”側は監視安全に実現。次＝段階ベンチ（未実機）。
- **自作SBL**：§5の不変条件を満たす実装（先頭8KB=0x0000–0x1FFF/KAM保護・安全消去順）。
- **チェックサム表 0xFF650 のROM改変時ロジック**は概ね解明（§7）だが、大規模改変前は要再確認。
- **リリース文書**：改定時は README(EN/JA)＋docs(md/html)＋VERSION/CHANGELOG/zip（`mem:feedback-release-docs`）。本索引もその対象に含める。
  文書と zip の更新はユーザーが指示したときだけ行う（`mem:feedback-docs-zip-on-request`）。
- **v2.80 の実機確認**：Live 中に分割表示の各ペインで●が動くか、ペア同時編集で書いた ROM を書き込んで DTC が出ないか（制御＝監視なので出ない想定）。
- **まだ未確定**：CAN 0x211 の送り手と介入時の値、`FFFF_6858`（`0xFFFF67F8`）、ファンが実際に回り始める水温とタイマの実時間。

## 17. 回転落ち高速化（レブハング低減・DFCO強化） 🧪（静的/エミュ検証・未実機）
- **目的＝シフトアップ時の回転落ちを速くする**。方式＝**燃料側のみ（減速燃料カット=DFCO を早く・強く）**で
  電子スロットルは不変＝E-Gas L2 と無関係（＝ブリップ＝増やす側が却下されたのと逆の“減らす側”で監視安全）。
- **主レバー＝突入デバウンス `0xC477D`（uint8=30）**。コード `0x42620`–`0x4263E` が `cmp/hs カウンタ, *(0xC477D)`
  → カウンタ≥必要数で減速フラグ(0xFFFF7336)=1。**下げると少ないカウントで DFCO が立つ＝リフトで速くカット**。
  `sh2emu` でこの関数を実行し enter_count=30/8/3 ↔ 立ち上がり閾 30/8/3 を実証。
- 副レバー＝減速カット率（エンリーン率）`0xCC774`(6×5)/`0xCC694`/`0xCC698`/`0xCC6A0`。**上げる＝全カットに速く到達**
  （開始0.6875[0xCC6A4]→しきい0.6[0xCC690]）。高回転列は純正で既に0.05＝突入後は速い→主律速は突入デバウンス。
- **触らない（失速防止）**：維持最低回転 `0xC47FC`=2312.5rpm・ヒス `0xC4800`・`Decel Fuel Restore Idle Thresholds`
  (0xC48xx/49xx)・復帰レート0xCC6A8/AC・全カットしきい0xCC690・開始0xCC6A4。→失速側は純正の保護のまま。
- **レバー2（減速スロットル/ダッシュポット）＝RE済だが未着手**：閉ペダルのスロットル目標は純正で既に0
  （APP→TP Desired の APP=0 列が全RPM行0.0・確認済）。残るハングは過渡の閉じレート＝定義に無いコード定数
  （DBW希望スロットル 制御~0x939xx/監視~0x954xx）。アイドルスルー(0xD6AB8・P0606却下 §13)と同じ監視保護クラスの
  懸念が高く**本件では触らない**。
- 実装：`ncecu/revdrop.py`（`build` 既定inert=純正等価・チェックサム自動補正・範囲ガード・`verify_result` で
  想定番地以外不変）/ CLI `tools/patch_revdrop.py` / エディタ 設定→パッチ→「回転落ち高速化」。プリセット
  off/mild(8,×2)/strong(3,×3)。両ROM(純正/実車搭載)で番地一致・inert==base・mild/strong 差分領域限定を自動確認。
- トレードオフ：速すぎ＝シフトのガクつき/低回転の息つき。`antilag` と同番地を逆向き＝1ROMにどちらか一方。
- 次＝停車→低速の段階的ベンチ（`docs/revdrop_bench_ja.md`、L2旗0・DTCなし・エンストなしを各段で確認）。未フラッシュ・未コミット。
- 参照：`ncecu/revdrop.py`・`tools/patch_revdrop.py`、`docs/revdrop_ja.md`・`docs/revdrop_bench_ja.md`、
  `docs/map_analysis_JA.md`（Fuel Status OL-Decel / Fuel Comp OL-Decel Fuel Cut）、`mem:revdrop-dfco`、§11（アンチラグ）。

## 18. アイドル回転補正（目標回転）・定義監査 🧪（静的検証・未実機）（パッチは v2.71 で廃止＝マップを直接編集。番地と注意は有効）
- **アイドル目標回転＝Idle Speed - Base**（ECT別8点）。**In-Gear/Not In-Gear の2系統**、各 **制御側＋監視側**の
  二重化：In-Gear 制御`0xD6C9C`/監視`0xF4DEC`（1150…720）、Not In-Gear 制御`0xD6CDC`/監視`0xF4E2C`（1750…720）。
  X軸ECT[-40..100]はテーブル直前8点。上限 Idle Speed-Max `0x3E724`=2000。
- 実装：`ncecu/idle_base.py`（`build(offset/ingear/notingear, heal)`・制御側を正に制御+監視を同値更新・[600,2000]
  クランプ・±500ガード・既定inert・チェックサム自動補正・verify_result）/ CLI `tools/patch_idle_base.py` /
  エディタ 設定→パッチ→「アイドル回転補正（目標回転）」。**スルーレート `0xD6AB8` 系は触らない**（監視保護 §13）。
- **★実車 `flatshiftrun.bin` の既存不整合を発見**：監視側 Not In-Gear `0xF4E2C` が非純正[1150,1150,1100,1000,850,850,720,720]
  で制御側 `0xD6CDC`(1750…) と不一致（§13 idle_up PoC `0xD6CDC+0xF4E2C` の残骸と推定）。純正 `ncec_rom_dump.bin` は整合。
  → ツールは heal=False で拒否、`heal=True`（CLI `--heal`/エディタ）で監視を制御に揃え是正しつつ適用。
- **定義(GUI)への追加**：制御側 `0xD6C9C`/`0xD6CDC`（＋ECT軸 `0xD6C7C`/`0xD6CBC`）を `defs/libretuner/*.json`（未追跡）
  に追加＝従来 `0xD6CDC` を検索しても出なかった原因（監視側しか定義が無かった）を解消。
- **定義監査（読み取り）＝パイプラインにバグ無し**：CALID 909テーブル全件 構造あり・全件表示、重複アドレス/キー0・
  欠落軸0。「非表示」はRE番地が定義に無いだけ。制御側指令上限 `0xC55FC` も監視のみ定義（`dbw_throttle.py`がraw直書きで実害なし）。
  既存WIP定義 `RE DBW Table @C8A24` は寸法誤り(本来18×10・表示専用・未修正)。
- 次＝停車中心の段階ベンチ（DTC/L2旗/狙いアイドル確認）。未フラッシュ・未コミット。
- 参照：`ncecu/idle_base.py`・`tools/patch_idle_base.py`、`docs/idle_base_ja.md`、`mem:idle-base-edit`、§8（KAM）/§13（スルー保護）。

## 19. v2.71：ライブ間引き統一・MAP追従の是正・アンチラグA〜D・統合マニュアル・ROM/フォルダ整理 🧪（机上/エミュ/GUI検証・未実機）
- **間引きの選択肢を統一**：`livelog.INTERVAL_CHOICES`＝毎回/0.1/0.2/0.5/1/2/5/10s/**無視(-1)**。エディタの間引きダイアログ（PID＋ライブRAM）と
  ダッシュボード「更新周期」が同じ並び。無視＝読まない。`snap_interval` でリスト外の値を丸める。
- **★MAP追従の負荷＝絶対負荷 PID 0x43**（計算負荷 0x04 ではない）。根拠＝Knock Listen 負荷 0.40(入)/0.353(出＝0.4−ヒス0.0469 `0xBBCB8`) が
  ログの 0x43 の 40%/36% 通過と一致（`logs/livelog_20261102_182622` t=61.9〜63.0）。0x04 は同時刻 52%/44%。軸名 `LOAD_6F44`（この ROM の入力 RAM は `0xFFFF6EC8`。2026-11-16 訂正）。
  以前は両PIDが同じロール LOAD で、毎回読む 0x04 と1秒ごとの 0x43 が上書きし合い●が行ずれしていた。`livelog.roles_from_pids` に集約。
- **アクセル軸の正規化**：PID 0x49 は生値（全閉31.4%/全開72.3%）。`app_normalized`＝(生値−31.4)×2.445。ログ10800点で ECU内部APP `0xFFFF56C8` と直線。近似。
- ~~軸名の末尾＝入力変数のRAM番地~~ → **誤り（2026-11-16 訂正）**。軸名の末尾は LibreTuner が使った別 ROM の番地で、この ROM の入力とは 265 軸すべてで
  一致しない（多くは +0x7C）。実番地は `tools/gen_axis_ram.py` が ROM のコードから求めて `ncecu/axis_ram.py` に書く（回転数 `0xFFFF6D5C`、負荷 `0xFFFF6EC8`、
  水温 `0xFFFF6CC8`、吸気温 `0xFFFF6CE8`、大気圧 `0xFFFF6D6C`、スロットル `0xFFFF6C80`、APP `0xFFFF6CA4`、車速 `0xFFFF6D04`）。Mode23 でこれらを直接読めば
  MAP追従を厳密にできる（未実装の候補）。
- **既定の読み方**：毎回＝回転/絶対負荷/スロットル/APP/点火/MAP（6個＝1要求）。MAF・AFR実測＝0.2s。無視＝0x04・0x4A・ブレーキ2。
  表示中マップの軸ロールは `LiveReader.set_follow_roles` で 0.2秒以内に必ず読む。ライブRAMは `RAM_READS_PER_CYCLE=2`（遅れの大きい順）。
  机上シミュレーション（1往復の時間は仮定値）：PID要求 2.01→1.17 回/周期、ユーザー設定で周期 約8.0→15.1Hz相当。**実機未計測**。
- **MAP検索**：`0x` 始まりは番地検索（本体/軸/範囲内/前方一致、RAM番地は `ncecu/axis_ram.py` の実番地と照合。2026-11-16〜）。`Editor._addr_query/_addr_match`。
- **アイドル回転補正パッチ廃止**：`idle_base.py`・CLI・メニュー撤去。Idle Speed - Base の制御/監視4枚を直接編集（同値にする）。運用中ROMは
  Not In-Gear を制御=監視で編集済み（1150…）。§18 は経緯の記録として残す。
- **アンチラグ A〜D**：旧C→D。新C＝RPMゲート＋ツキ重視（DFCO有効）。**有効回転数（B・C）＝回転軸 `0xCC748` を動かす**（1500〜6000/100刻み、
  既定3000＝純正軸＝旧Bとバイト一致）。軸は表専用（参照は記述子 `0x93E00` の1箇所）。表引き `0x20DC`（r4=記述子 `0x93DFC`, fr4=回転, fr5=ギア）を
  sh2emu で実行して確認。`verify_result` 追加。sh2emu に MACH/MACL 退避命令を追加。**実車未確認**。
- **★認証キー計算の依存**：`ncecu/security.py` は ROM 内の検証ルーチン `0x7DFE0` をエミュレートするため、実行時にROMファイルを読む。
  以前はルートの `ncec_rom_dump.bin` 固定だった → `rom_data/` から探すよう変更（`default_rom()`。無ければ自己検証に通る1MBの .bin）。
  **ROMを動かす/消すときはここを思い出すこと。**
- **ROM**：`rom_data/` の3本のみ＝`ecu_readout_original.bin`（実車純正）/`ecu_readout_yahooauction.bin`（ベンチ原本＝旧 ncec_rom_dump.bin）/
  `decelfuelcutoff_strong.bin`（運用中）。起動時ROM・ツール既定も `rom_data/`。
- **docs**：統合マニュアル `docs/map_analysis_JA.html`・`map_analysis.html`（`tools/build_docs.py`。全マップ解析パートは HTML 内の
  `<!-- MAP-ANALYSIS:BEGIN/END -->` を引き継ぐ＝そこは HTML を直接編集）。原稿を統合（setup_wsl / flash / flatshift / revdrop）、`manual_EN.md` 新設。
  削除＝オートブリップ7本・idle_base・PROJECT_HANDOFF・self_write_feasibility・sh7058_flash_spec・統合元6本・map_analysis の .md 2本。
- **フォルダ整理**：102項目・約1.0GBをごみ箱へ（旧zip17・展開5・NCFlash一式・ルートROM26・autoblip/idle関連コード・RAM調査ツール・定義bak12）。
  `NCEC_ROM_Tool_v2.70_FULL.zip` は残置（撤去物はこの中にもある。PROJECT_HANDOFF だけは含まれない）。事前に整理後構成を別フォルダで再現してテスト。
- 参照：`CHANGELOG` v2.71、`docs/knock_re_ja.md`、`docs/tuning_overrun_pops_ja.md`、`mem:live-follow-load`、`mem:security-rom-dependency`、`mem:antilag-gate-axis`。

## 20. v2.80：表の分割表示・ペア同時編集・編集操作と元に戻す・ショートカット・ウィンドウの記憶／11-17 の解析の反映 🧪（GUI の自動テストのみ・未実機）
- **表のペイン（`ncec_tableview.py`）**：キャンバス描画（セルごとの Entry をやめた）。見出しは 4 枚のキャンバスで固定。レイアウト 1/左右2/上下2/3/4 を
  PanedWindow で組み直し（切り替えのたびにペインを作り直し、表・拡大率・選択は `pane_state` で引き継ぐ）。別ウィンドウ（Toplevel）も同じペイン。
- **書き込みは 1 か所（`Editor.edit_cells` / `edit_axis`）**：範囲チェック（パッチ定数）→ 書き込み → ペア同時編集（相方の同じオフセットへ同じバイト。寸法・型・式が同じ組だけ）
  → 元に戻す の記録（番地・旧バイト・新バイト）→ 全ペインの再描画。パッチ適用は `_set_rom(record=True)` が差分バイトを記録し、元に戻すと追加項目（ツリー）も作り直す。
- **ショートカット（`ncec_shortcuts.py`）**：キーは "Ctrl+Shift+S" 形式。記号キーは Shift を区別しない（JIS 配列対策）、テンキーは本体と同じ。
  Alt のビットは Windows 0x20000 / X11 0x8。ルートの `<KeyPress>` で振り分け、表の操作は表にフォーカスがあるときだけ、入力欄では Ctrl/Alt/F キーだけ。
  移動キー・数字は予約。ECU 書き込みは対象外。設定は `ui_settings.json` に既定からの差分だけ保存。
- **画面の状態（`ncec_uistate.py`・`ui_settings.json`）**：エディタ/ダッシュボードの位置と大きさ（最大化は最大化前の大きさも保持。画面外の位置は捨てる。
  Windows は仮想スクリーン、WSLg は X のスクリーンで判定）、レイアウト・各ペインの表（番地＋名前で保存）・別ウィンドウ・境目の比率、増減幅、表示オプション。
- **11-17 の解析の反映**：ファンのタイマの説明（1ms/25ms は実車で確認）、オルタの学習は休止、EVAP の軸、オートブリップの最終結論（§13）、
  定義の英文が日本語の説明を隠していた 2 表、ノートの「SBL未入手」53 か所と【運用】の記述。
- **検証**：GUI の自動テスト 50 項目（スクラッチパッドのスクリプト。リポジトリには無い）。**Live 中の動作は未確認**。
- **v2.81（2026-11-18）WSL の右クリックメニュー**：① v2.80 の表・ツリーのメニューが `tk_popup` 直後の `grab_release()` のせいで
  外側クリックで閉じず、戻すと再表示（XTest の実クリックで再現）→ 素の `tk_popup` に。② それでも WSLg は別ウィンドウのメニューを
  閉じた後も約 0.9 秒描き続け、押した瞬間にも一度消えて再表示（Windows 側のコマ撮りで確認。窓を destroy しても同じ）
  → X11 ではメニューを親ウィンドウ内の Frame として描く `ncec_popup.InlineMenu`（place＋grab_set で外側クリックを受けて閉じ、
  そのクリックは下に渡さない。place 直後は grab が "not viewable" で失敗するので再試行）。エディタの表・ツリー、ダッシュボードの
  タイルと［項目を追加］に適用。サブメニューは折りたたみ、長い一覧は複数列、収まらないときだけ tk.Menu。Windows は tk.Menu のまま。
  検証方法＝Git Bash から `MSYS_NO_PATHCONV=1 wsl.exe -- python3 …` で WSLg 上の Tk を動かし、ctypes で `libXtst.so.6` を呼ぶ（`mem:wslg-dashboard-menu-flicker`）。
- 参照：`CHANGELOG` v2.80・v2.81、`docs/editor_help_ja.md`（アプリ内ヘルプ）。

---
*このファイルは手動更新の索引です。大きな決定・RE結果が出たら、該当トピックに1–2行追記してください。*
