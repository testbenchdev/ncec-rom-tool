# CAN書き込み — 準備完了状態と残作業(SBL入手のみ)

更新: 2026-10-03。対象: 予備ECU(Denso NC / SH7058 / CALID LFG7EG / **世代 NC1**)。
nc-flash 2.20.0 のソース解析と本個体の実機確認に基づき、**SBL以外はすべて実装・検証済み**。

## 確定したフラッシュ手順(ncecu/flash.py `Flasher.flash`)
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

## 検証済み(ECU非接触)
- 認証/鍵計算: 実機で 67 02 成功(複数シードで確認)。
- `B1 00 B2 00` 受理、`34 00008000 000FF800` 受理(74 04 01)を実機確認。
- `ncecu.checksum` == nc-flash `correct_rom_checksums`(編集後出力がbyte一致)。
- `calibration_crc`(= romdrop/nc-flash方式, zlib CRC32 of rom[0x2000:0x100000], 0xFFB00:8クリア):
  既知ROM `lf9veb.bin` → `00808CC3` で一致(アルゴリズム正当)。
- `detect_generation`(@0x2030): 本個体 = **NC1**。
- `verify_readback`: 書込領域[0x2000:]比較、フラッシュカウンタ(0xFFB00:8)とブートローダ(<0x2000)除外。

## 残る唯一の入力 = SBL(0x1800バイト)
- 必要なのは **NC1 / flash_start=0x2000 の SBL 1個**(CALID非依存=どのNC1車でも同じ)。
- 入手: **NC1車のフル書き込みを candump 記録** → `tools/extract_sbl.py` で抽出。
  (SBLはフラッシュ中に 0x36 で平文送信される。入手源は2006–2008頃のNC全般)

## 手順:SBL入手〜書き戻しテスト
1. **キャプチャ**(誰かのNC1実機フラッシュ): RomDrop なら「S｜Sniff CAN」で candump.raw、
   または SocketCAN で `candump -l can0`(500kbps)。フラッシュ全体を記録。
2. **抽出**:
   ```bash
   python tools/extract_sbl.py <capture> --out-dir out
   ```
   → `out/sbl.bin`(0x1800)。ツールが **dl_size=0xFF800 / capture_generation=NC1** を自動確認
   (警告が出たら full-flash か NC1 か要確認=そのSBLは使わない)。
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

## 参考値
- CALID: LFG7EG000.HEX / 世代 NC1(@0x2030=0x35) / VIN NCEC103017 / CVN 74ec05dd。
- romdrop.crc の LFG7EG factory CRC = A2DBA7DA(純正照合用。※中古ダンプは学習値で不一致が正常)。
