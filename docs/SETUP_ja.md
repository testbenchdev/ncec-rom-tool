# NCEC ROM Map Editor — 導入手順(他PCセットアップ)

Mazda MX-5 **NC(NCEC / LF-VE / Denso・Renesas SH7058 PCM)** の純正ECUを
**読み取り / 編集 / 比較 / ライブ監視 / 書き込み** するツール一式の導入手順です。

> ⚠ **免責・安全(必読)**:本ソフトは無保証・自己責任。ECUのブリック・エンジン破損・
> 車両故障・法令違反の責任は負いません。**作業は予備/ベンチECUで**。実車の排ガス規制回避は
> 多くの地域で違法です。点火・燃調・リミッタ・電子スロットル/トルクは理解せず変更しないこと。

> 📦 **このパッケージが「完全版」(ファイル名 `..._full_...`)の場合**:ROMダンプ・LibreTuner定義・
> SBL も**すべて同梱済み**です。→ **第4節(各自用意)はスキップ**して、第2節(pip)→第3節(ドライバ)→
> 第5節(`python ncec_editor.py`)だけで、起動時に `ncec_rom_dump.bin` と `defs/libretuner/` を自動読込します。
> (個人利用・自分の別PCへの移行用。第三者への再配布時は著作権/ライセンスに注意)

---

## 1. 必要なもの

- **Windows 10 / 11**
- **Python 3.10 以上**(開発環境は 3.14)
- **USB-CAN アダプタ(gs_usb 系)**:DSD TECH SH-C30L(candleLight)等
- CAN配線(500kbps、要求 0x7E0 / 応答 0x7E8)、ECUの安定化電源
- (書き込みする場合のみ)予備/ベンチECU・**SBLファイル(0x1800, NC1)**

## 2. 依存パッケージのインストール

展開したフォルダで:

```bash
pip install -r requirements.txt
```

(`python-can` / `gs_usb` / `pyusb` / `capstone` / `PyMuPDF` / `Pillow`。GUIの `tkinter` はPython標準=追加不要)

## 3. CANアダプタのドライバ設定(Windowsで重要)

gs_usb は **libusb** 経由で動くため、SH-C30L に **WinUSB(libusb)** ドライバを割り当てます。

1. **Zadig**(https://zadig.akeo.ie)を入手して起動
2. アダプタをUSB接続
3. Zadig の **Options → List All Devices** にチェック
4. リストから **"gs_usb" / "candleLight"** を選択
5. ドライバを **WinUSB** にして **Install / Replace Driver**
6. 確認:ECUをCAN接続・通電し、`python tools/probe.py` を実行 → `[1] passive sniff` にフレーム、`[5] Mode09` で CALID/VIN が読めれば認識OK

## 4. 同梱していないもの(各自で用意・配置)

著作権・ライセンス・機密のため**同梱していません**。以下を自分で用意してください。

| もの | 置き場所 | 入手 |
|---|---|---|
| **LibreTuner mx5_nc 定義** | `defs/libretuner/main.json`<br>`defs/libretuner/LFG7EG.json` | github.com/LibreTuner/LibreTuner の `ui/resources/definitions/mx5_nc/`(**GPL。ライセンス順守**) |
| **ECUダンプ** | ルートの `ncec_rom_dump.bin` | 自分のECUをエディタ「ECU吸出し」でダンプ、または手持ちの吸い出し |
| **SBL(書込み用, 0x1800)** | 任意の場所(書込み時に選択) | 自分の環境で用意 |

- `defs/libretuner/` が無い場合、エディタは古いXML定義にフォールバックしますが、
  **LibreTuner定義のほうがこの個体の表レイアウトが正確**です(推奨)。
- `ncec_rom_dump.bin` が無くても起動はできますが、ROMを[開く]から読み込むか「ECU吸出し」で作成してください。

## 5. 起動と基本操作

### ダブルクリック起動(ターミナル不要・推奨)

同梱の **`.bat`** をダブルクリックするだけで起動できます。

- **初回のみ**:`setup_install.bat` をダブルクリック → 依存パッケージを自動インストール。
- **起動**:`NCEC_ROM_Editor.bat` をダブルクリック(コンソール表示あり=エラーが見える)。
- **コンソールを出さずに起動したい**:`NCEC_ROM_Editor_quiet.bat`(動作確認済み環境向け。エラーは画面に出ません)。
- デスクトップに置きたい場合は、`NCEC_ROM_Editor.bat` を右クリック →「ショートカットの作成」→ ショートカットをデスクトップへ。

> `.bat` は Python を自動検出(`python`→`py`)し、未導入なら案内を表示します。

### 端末から起動する場合

```bash
python ncec_editor.py
```

- 左ツリーでマップ選択 → 右のセルをクリックして数値入力 → **Enter で確定** → **[保存]**(チェックサム自動補正)
- **[Live ▶]** ライブ監視(マルチPID対応ECUなら **10Hz+**)。開いているマップ上に運転点を **●** で重ね描き
- **[ダッシュボード]** タイル表示(項目を追加で AFR実測/目標 なども追加可)
- **[記録 ●]** Live中のロギング(`logs/*.jsonl`、ポーリング周期ごとの高精度)→ **[リプレイ]** で再生(ダッシュ+●が動く)
- **[ECU吸出し] / [ECUと照合] / [ROM照合]** 比較系
- **[ECU書き込み]** 編集ROMを実機へ(※下記の注意)
- 操作ヘルプは **[ヘルプ]** ボタン(`docs/editor_help_ja.md`)

## 6. 付属ドキュメント(docs/)

- `map_analysis.html` / `map_analysis_JA.html` … 全マップ解析(フローチャート付き・そのままブラウザで開ける)
- `ecu_diff_report.html` … 実車 vs ベンチ の差分レポート
- `map_editor_manual.pdf` / `map_editor_manual_EN.pdf` … 取扱説明(PDF)
- `can_flash_ready_ja.md` … CAN書き込みの前提と手順
- `editor_help_ja.md` … エディタ操作(アプリ内ヘルプと同じ)
- `unit_fixes_i18n.md` / `table_audit_ja.md` / `SH7058_hardware_notes.md` / `diag_findings.md` ほか

## 7. 書き込み(フラッシュ)の注意

- **消去を伴う不可逆操作・ブリックの実リスク**。必ず**予備/ベンチECU**で。
- 電源を安定させ、**書き込み中(約10分)は抜線・電源断をしない**。
- 書込みには **SBL(0x1800, NC1)** が必要([ECU書き込み]でファイル選択)。
- **最初は無改変の読み戻し**(同じROMを書いて CALID/CVN が前後一致)で健全性を確認してから、編集ROMへ。
- 編集ROMを焼くと **CVNは変化するのが正常**(校正が変わった証拠)。純正に戻すには元の `ncec_rom_dump.bin` を焼く。

## 8. トラブルシュート

- **`USBError: [Errno 13] Access denied`**:アダプタが他プロセスに掴まれている/解放ラグ。
  → **SH-C30L のUSBを抜き挿し**、Liveを停止、端末で動作中のCAN系ツール(probe/tx_test/flash_writeback)や2つ目のエディタを終了、エディタ再起動。
- **Live 接続失敗**:WinUSBドライバ(手順3)・ECU電源・通常セッションを確認。
- **値が全部 `--` / 反応なし**:ECU電源、500kbps、配線、要求0x7E0/応答0x7E8。
- **Live更新が遅い**:Liveパネル1行目の `● X.X Hz` を確認。二桁なら正常(マルチPID対応)。数Hzなら非対応ECU。

---

本ソフトは **GPL-3.0**(同梱 `LICENSE`)。定義データ(LibreTuner / RomRaider XML)はそれぞれの
ライセンスに従って各自取得してください。ECUファームウェア(ROM)・SBLは本パッケージに含みません。
