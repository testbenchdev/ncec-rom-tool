# ECU書き込み（CANフラッシュ）— 手順と高速化

この章は2部構成です。**第1部＝書き込みの手順と確定事項**、**第2部＝書き込み/読み出しの所要時間と高速化**。

## 第1部: CAN書き込み — 書き込み成功済み(SBL入手済)と手順

更新: 2026-11。対象: 予備ECU(Denso NC / SH7058 / CALID LFG7EG / **世代 NC1**)。
nc-flash 2.20.0 のソース解析と本個体の実機確認に基づき実装。**SBLは入手済み(①自前キャプチャ=romdrop.exe を自分でRE)で、
CAN経由フラッシュは予備ECU単体でも車載(OBD2ポート)でも成功済み。** 以下はその入手〜書き戻し手順(実施済み)と確定したフラッシュ手順。
`tools/extract_sbl.py` は実戦フォーマット対応・破損検知まで強化済み。

### 確定したフラッシュ手順(ncecu/flash.py `Flasher.flash`)
```
認証(10 85 → 27 01/02)
 → B1 00 B2 00                      RoutineControl(前提条件)
 → 34 00008000 000FF800            RequestDownload(RAM 0x8000 / 総サイズ 0xFF800)
 → 36 <data> を 0x400バイト毎:      ① SBL(0x1800) → ② 補正ROM[0x2000:](0xFE000)
 → 37                               TransferExit
 → 11 01                            ECUリセット
```
- **0x1800(SBL) + 0xFE000(本体) = 0xFF800**(実機が受理する唯一のサイズ)。
- チェックサムは `ncecu.checksum` で自動補正(nc-flash と**byte単位一致を検証済み**)。
- 書き込みは **sbl_data があり、かつ confirm=True の時だけ**実行(既定ドライラン)。

### 検証済み(ECU非接触)
- 認証/鍵計算: 実機で 67 02 成功(複数シードで確認)。
- `B1 00 B2 00` 受理、`34 00008000 000FF800` 受理(74 04 01)を実機確認。
- `ncecu.checksum` == nc-flash `correct_rom_checksums`(編集後出力がbyte一致)。
- `calibration_crc`(= romdrop/nc-flash方式, zlib CRC32 of rom[0x2000:0x100000], 0xFFB00:8クリア):
  既知ROM `lf9veb.bin` → `00808CC3` で一致(アルゴリズム正当)。
- `detect_generation`(@0x2030): 本個体 = **NC1**。
- `verify_readback`: 書込領域[0x2000:]比較、フラッシュカウンタ(0xFFB00:8)とブートローダ(<0x2000)除外。

### SBLの入手(0x1800バイト) — 実施済み
- 必要なのは **NC1 / flash_start=0x2000 の SBL 1個**(CALID非依存=どのNC1車でも同じ)。
- SBLはフラッシュ中に 0x36 で**平文送信**されるので、**フル書き込みを1回キャプチャ**すれば抽出できる。
- **①自前キャプチャ(推奨・他人に依存しない)**: SBLを内蔵する既存ツールで予備ECUを**1回だけ**
  フル書き込み(**同一内容の無害な再書込みでも可**)しつつ CAN を記録する。
  入手源ツール例: nc-flash の**配布バイナリ**(ソースはSBLを隠すが実行形式は内蔵)/ mx5studio /
  EcuFlash + SHリフラッシュkernel。どれか1つを動かせる環境があれば完結する。
- ②他人のNC1フル書き込みキャプチャ(candump)を貰う、でも可(世代共通なので流用できる)。

### 手順:SBL入手〜書き戻しテスト
1. **キャプチャ**(NC1のフルフラッシュを1回・500kbps CAN): SBL内蔵ツール(nc-flash配布バイナリ /
   mx5studio / EcuFlash+kernel)で予備ECUを**フル書き込み**しつつ、以下のいずれかで記録。
   **full-flash(flash_start=0x2000)にすること**(部分/動的書込みのキャプチャはSBLが別物で使えない)。
   - SocketCAN: `candump -l can0`(`-L`ログ)/ 既定出力 / `ID#DATA` テキスト
   - Vector・SavvyCAN: `.asc`(Rx/Tx両対応)/ `.csv`(SavvyCAN/GVRET)
   - RomDrop「S｜Sniff CAN」などの生バイナリ `candump.raw`
   - → `tools/extract_sbl.py` がこれらを**自動判定**(生バイナリで外す場合は `--inspect` で診断、
     `--bin-record-len/--bin-id-off/--bin-data-off` で手動指定)。
2. **抽出**:
   ```bash
   python tools/extract_sbl.py <capture> --out-dir out
   ```
   → `out/sbl.bin`(0x1800)。ツールが **dl_addr=0x8000 / dl_size=0xFF800 / block=0x400 /
   capture_generation=NC1** を自動検証。さらに **ISO-TP連結フレームの欠落・順序乱れ**を検知する。
   - **警告ゼロ(終了コード0)= そのまま次へ**。
   - **警告あり(終了コード2)= 使わない**。`★致命`(SN不整合/未完)はフレーム欠落で**SBL破損**=
     ブリック要因なので、**full-flash / NC1 / 無欠落**で**再キャプチャ**する(壊れたSBLは絶対に流さない)。
3. **ドライラン**(ECUに接続・書き込まない):
   ```bash
   python tools/flash_writeback.py --sbl out/sbl.bin
   ```
   計画(flash_start=0x2000 / 合計0xFF800 / 0x400ブロック×約1022)を確認。
4. **本番(無改変の書き戻しテスト)** — 消去を伴う不可逆・ブリック覚悟・電源入れっぱなし:
   ```bash
   python tools/flash_writeback.py --sbl out/sbl.bin --confirm
   ```
   → 認証→消去→SBL+本体転送→リセット→**前後の CALID/CVN 一致で成功**(内容同一・健全)。
5. 成功後は、エディタ(`ncec_editor.py`)で編集した `.bin` を同じ手順で書き込む
   (チェックサムは保存・書込時に自動補正)。

### 書き込みに失敗したとき
- これまでに起きた書き込み失敗は、**すべて「電源を入れ直す → もう一度 CAN で書き込む」で復旧**できています。
- 復旧できる理由：書き込むのは `0x2000` 以降だけで、**先頭のブート領域（CAN のハンドラを含むブロック0）には一切書かない**ため、
  途中で失敗してもECUは書き込みを受け付ける状態で立ち上がります。**ブロック0には書かない**ことがこの前提です。
- 電源の入れ直しは **+12V 側を切る**（GND だけ抜くのは不十分）。
- WSL2 で作業中に通信が止まったら、エディタの［設定］→［CAN接続］で状態を確認し、「USB/IP 接続が切れています」と出たら
  `wsl --shutdown` のあと `NCEC_Editor_WSL.bat` で起動し直します（[setup_wsl_ja.md](setup_wsl_ja.md)）。**書き込み中は Wi-Fi を切る。**
- 最後の手段はシリアルのブートモード（基板のモード端子へのアクセスと 1MB の完全なバックアップが必要。「SH7058 ハードウェア要点」）。

### 参考値
- CALID: LFG7EG000.HEX / 世代 NC1(@0x2030=0x35) / VIN NCEC-REDACTED / CVN CVN-REDACTED。
- romdrop.crc の LFG7EG factory CRC = A2DBA7DA(純正照合用。※中古ダンプは学習値で不一致が正常)。

---

## 第2部: フラッシュ書き込みの高速化（検討メモ）

最終更新: 2026-11-07（書込＝socketcanで約4.7倍を実測／読出＝ECU送信律速で約206sと判明）

### 1. 所要時間のモデル
フル書込（`0xFF800` = SBL 0x1800 + ROM 0xFE000）を `0x400`/ブロック（≒1022ブロック）で転送。
1ブロックの時間 ≈ **(A) 送信時間**（0x400 を ISO-TP で送る＝FF1本＋約146連続フレーム）
＋ **(B) ECU のフラッシュ書込待ち**（128B×8 の書込＋0x76 応答）。

- (A) は `tx_st_min_floor` と、**gs_usb(SH-C30L)のUSB往復**に比例。
- (B) はチップ物理時間（SBL依存・固定）。

### 1.5 実測と結論（2026-11-06）
| 計測 | 条件 | 結果 |
|---|---|---|
| 実フラッシュ ROM転送 | Win/gs_usb・guard有・floor0.5ms | **250ms/ブロック**（253.9s/1016ブロック、4.00KiB/s） |
| 実フラッシュ SBL転送 | 同上 | 19.4s（うち**約18sは消去**＝最終ブロックに計上） |
| tx_test（送信のみ・焼込ゼロ） | Win/gs_usb・guard無・floor0.5ms | 400ms/msg |
| tx_test（送信のみ・焼込ゼロ） | Win/gs_usb・**guard有**・floor0.5ms | **266ms/msg**（3.76KiB/s） |
| tx_test（送信のみ・焼込ゼロ） | Win/gs_usb・guard有・floor0.5ms・**drain-every32** | **233ms/msg**（4.29KiB/s, 8/8安定）＝266から約12%短縮 |
| tx_test（送信のみ・焼込ゼロ） | **WSL2/socketcan**・floor0 | **47ms/msg**（21.5KiB/s, 8/8安定, ~0.32ms/フレーム）＝233から**約5倍** |
| **実フラッシュ ROM転送** | **WSL2/socketcan**・floor0 | **41.1s**（40.5ms/ブロック, 24.7KiB/s, 1016ブロック）＝Win実フラッシュ254sの**約6.2倍** |
| 実フラッシュ SBL転送 | 同上 | 17.3s（消去込み・ほぼ物理固定） |
| **実フラッシュ 全体** | 同上 | **58.4s**（準備0+SBL17.3+ROM41.1+Exit/Reset0）＝Win ~273sの**約4.7倍**。途中失敗0 |

**結論＝ほぼ100%が送信(TX)コスト（SH-C30L/gs_usbのUSB往復）。ROMの焼き込みは実質ゼロ。**
**→ 打ち手はただ一つ「USB往復を減らす」。Windows(gs_usb)から WSL2(socketcan)へ移すのが本命で、実測で確定した。**
- guard有の純送信(266ms) ≒ 焼き込み込みの実フラッシュ(250ms) → **ECU焼き込み待ちは無視できる**。
- フル書込273s の内訳 ≒ **消去~18s（ROM/固定）＋ ROM-TX ~254s（ホスト/USB）＋ 焼込~0**。
- 266ms ÷ 148フレーム ≒ **1.8ms/フレーム**。うち floor は 0.5ms、残り ~1.3ms が gs_usb の
  USB送信＋エコー吸い出し往復（＝Windowsユーザ空間ドライバ経路）。CANバス上は0.26ms/フレームで
  余裕 → **ハード限界でなくドライバ経路が壁**。
- guard で 400→266ms（約34%短縮）＝ホスト側のタイマ/優先度が効く＝ホスト律速の裏付け。
- ∴ **Windowsでは floor をさらに下げても頭打ち**（0.3msで1.8→1.6ms/フレーム≒1割）。
- **socketcan(WSL2)実測 47ms/msg = 0.32ms/フレーム**＝CANバス物理下限 0.26ms にほぼ肉薄（OH約22%）。
  gs_usb のユーザ空間USB往復(~1.3ms/フレーム)がカーネル送信で消え、**ドライバ律速→バス帯域律速へ**。
  フル書込TX ~254s → **~48s**。消去~18s 込みでも全体 ~66s（従来~273s＝約4倍）。**これ以上は帯域限界**。
  導入手順＝[setup_wsl_ja.md](setup_wsl_ja.md)（6.x カーネルはビルド不要、`NCEC_CAN=socketcan:can0` のみ）。

### 1.6 読み出し（吸出し/照合）の実測と結論（2026-11-07）
フル吸出し（1MB を Mode23 `23 <addr> 0x400` で 1024 ブロック読み・socketcan）:
| 計測 | 条件 | 結果 |
|---|---|---|
| ECU吸出し（全1MB） | WSL2/socketcan・FC BS=0x10 | **220.1s**（4.7KiB/s, 215ms/ブロック, ~1.46ms/フレーム） |
| ECU吸出し（全1MB） | WSL2/socketcan・**FC BS=0**（CF連続送信） | **206.0s**（5.0KiB/s, 201ms/ブロック, ~1.37ms/フレーム）＝BS0x10比 −6% |

**結論＝読み出しは書き込みと真逆で「ECUの送信(TX)律速」。ホスト側では詰められない。**
- 書込＝ホストが連射＝バス限界0.27ms/フレーム（58s）。読出＝ECUが送信側で、**CF間に約1.1msのギャップ**を入れる（1.37ms/フレーム）＝ECUファームのHCAN送信ルーチンの素の速度。
- **FCペーシング(BS)はほぼ無関係**：BS0x10→0（1ブロック約147CFで約9回のFC往復を除去）でも **14sしか縮まない(6%)**。残りは全部ECUの送信ギャップ。
- socketcan は gs_usb のUSB往復(~1.3ms/フレーム)を消したので gs_usb時代（推定~400s/~2.6ms/フレーム）比で**約2倍**にはなっているが、書込ほど劇的には速くならない。
- ブロック長0x400は Mode23 ハンドラ上限で固定（`mode23.MAX_SIZE`）。per-frame律速なので大きく要求しても無意味（そもそも要求できない）。
- **ホスト側に打ち手なし。** 根本的に速くするには常駐SBLで独自の読み出し（バス速度でストリーム）を実装するしかない＝Stage-C以降の大仕事。吸出しは基盤ROM取得の一度きり＋節目のみなので費用対効果は低い。
- 実装：socketcan時のみ FC BS=0（`_ecu_read_rom_async` in `ncec_editor.py`）。害は無いが効果は6%。
- **通常の書込後照合は全1MB読み戻しでなく、数箇所の抜き取り照合（7箇所・計7KB＝数秒。初期の検証スクリプト `check_rom_integrity.py` の方式で、本ツールには入っていない）で十分**（§3-4）。全照合が要る節目だけ 206s を払う。

### 2. 計測（実装済み）
- **TXのみ**：`tools/tx_test.py`（非破壊。ECUはNRCで弾くだけ＝書込みしない）。
  末尾に「1メッセージ平均ms／KiB/s／フル書込TX推定秒」を表示（2026-11-05追加）。
  `--floor` を変えて送信レートの下限を安全に探せる。
  ```
  python tools/tx_test.py --floor 0.001
  python tools/tx_test.py --floor 0.0005
  python tools/tx_test.py --floor 0.0003   # OKを保てる最小を探す
  ```
- **実フラッシュ**：`ncecu/flash.py` が転送後に「準備/SBL転送/ROM転送/Exit+Reset」の内訳と
  各転送の KiB/s・ms/ブロックを表示（2026-11-05追加）。
- **見分け方**：tx_test の TX推定 ≈ 実フラッシュの転送時間 なら **TX律速**（floorを下げれば効く）。
  実フラッシュの転送時間 ≫ TX推定 なら **ECU書込待ち律速**（floorを下げても効果薄）。
- **読み出し（吸出し/照合）**：GUIの「ECU吸出し」「ECUと照合」が読み出しの KiB/s・経過秒を、
  進捗ラベル／吸出し完了ダイアログ／照合ヘッダ、およびランチャー窓コンソールの
  `[ECU read] … via socketcan` に表示（2026-11-07追加）。§1.6 の実測はこれで取得。

### 3. 打ち手
> **本命は socketcan(WSL2)＝実測で確定（約5倍）。** 下記 Windows 向けの小技(guard/floor/drain)は
> gs_usb に留まる場合の緩和策。socketcan へ移れば帯域限界(0.32ms/フレーム)に達し、これ以上の
> ホスト側最適化（バーストTX等）はほぼ無意味になる。
> **通常運用は GUI だけで完結**（`NCEC_Editor_WSL.bat` ダブルクリック）。導入と技術背景＝[setup_wsl_ja.md](setup_wsl_ja.md)。

#### 実装済み
1. **`tx_st_min_floor` 可変**（既定1ms）。GUI書込に「高速転送(0.5ms)」opt-in、CLI `--tx-floor`。
2. **`realtime_guard`**（Windows: timeBeginPeriod(1)+高優先度+スリープ抑止）。背景化でも転送が
   崩れず、かつ 400→266ms（約34%）短縮。tx_test もこれで実フラッシュと同条件計測が可能。
3. **`drain_every` 間引き**：8→32 で 266→233ms（約12%・実測で安定）。**GUIの「高速転送」は
   floor0.5ms＋drain32 を束ねる**ようにした。CLI は `flash_writeback.py --drain-every 32`、
   `tx_test.py --drain-every 32`。長い本フラッシュに使う前に tx_test で OK 全成功を確認すること。

#### 未実装（候補・効果/リスク順）
3. **バーストTX送信**（TX律速なら本命）：連続フレームを1本ずつ sleep せず、gs_usb(candleLight)の
   送信FIFO深さ分までまとめて投入→エコー吸い出し→少し待つ、を繰り返す。per-frame sleep を
   なくせるので TX を 2〜4倍にできる可能性。**要実機チューニング**（FIFO溢れ=Errno10060 の
   境界を tx_test で詰める）。`ncecu/isotp.py send()` にバーストモードを追加し opt-in で。
4. **検証の部分化**：デバッグ反復では全1MB読み戻しをやめ、数箇所の抜き取り照合（7箇所・計7KB。初期の検証スクリプト `check_rom_integrity.py` の方式）
   や変更領域だけ照合。全ダンプは節目のみ。読み出しも Mode23 0x400ブロックなので、範囲を絞れば
   数秒。
5. **部分（領域）フラッシュ**：CAL数バイトだけ変える debug では桁違いに速くできるが、**現状の
   nc-flash SBL は addr=0x8000/size=0xFF800 のフル書込のみ受理**（`flash.py` が強制）。領域指定・
   小ブロック消去は**自作SBL（npkern 系, CLAUDE.md §3.7）側の将来機能**。要実装だが、idle系CAL
   検証の反復には最も効く。
6. **CAN速度/ブロック長**：500kbps・0x400 は ECU 固定。変更不可。

### 4. 推奨手順
1. `tx_test.py` で floor を 1.0 → 0.5 → 0.3ms と下げ、**OK全成功を保てる最小**を特定（KiB/s を記録）。
2. 実フラッシュを一度流し、`flash.py` の内訳で **転送 vs 書込待ち**の比率を確認。
3. TX律速なら：最小 floor を常用（GUI高速転送 or `--tx-floor`）＋（効果大なら）バーストTXを実装。
   書込待ち律速なら：floor 据え置き、**検証の部分化**で反復時間を詰める。将来の自作SBLで部分
   フラッシュを狙う。
