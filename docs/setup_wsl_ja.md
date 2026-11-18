# NCEC ROM Map Editor — WSL2 / socketcan 導入ガイド（新PCセットアップ）

最終更新: 2026-11-06

## 0. これは何 / なぜ
NCEC ROM Map Editor を **WSL2(Ubuntu) 上で socketcan 経由**で動かすための導入手順です。
これにより ECU 書き込みが **約4.7倍**高速になります（実機: フル書込 273秒 → **約58秒**）。

- 原因: Windows の gs_usb(SH-C30L) はフレーム毎に ~1.3ms のユーザ空間USB往復があり、これが書込の壁。
  Linux の socketcan はカーネル送信でこの往復が無く、ほぼ CANバス帯域の限界(0.32ms/フレーム)で送れる。
- **GUI操作だけで完結**: 面倒な CLI(usbipd / ip link / 環境変数)は、初回セットアップ1本と
  起動ランチャー(ダブルクリック)が自動で行います。
- 技術的な背景の詳細は この文書の末尾「付録: 技術背景と手動手順」 / [flash_ja.md](flash_ja.md)。

## 1. 前提
- Windows 11（WSL2 が使えること）。
- CANアダプタ **DSD TECH SH-C30L**（candleLight / VID:PID `1d50:606f`）。
- 本プロジェクト一式（このフォルダ）。置き場所は任意（スクリプトはパスをハードコードしません）。
- インターネット接続（WSL/Ubuntu/usbipd の導入に使用）。

## 2. 初回セットアップ（新PCで一度だけ・4ステップ）

### 2-1. WSL2 + Ubuntu を導入
管理者 PowerShell で:
```powershell
wsl --install -d Ubuntu-24.04
```
- 再起動後、Ubuntu が自動で開くので **ユーザー名とパスワード**を設定します。
- 既に WSL がある場合はカーネルを新しくしておきます（CAN/gs_usb は 6.x カーネルに同梱）:
```powershell
wsl --update
```
- 確認: `wsl -l -v` で対象 distro が **VERSION 2** であること。

### 2-2. usbipd-win を導入
管理者 PowerShell で:
```powershell
winget install usbipd
```
- winget が無ければ https://github.com/dorssel/usbipd-win/releases から .msi を導入。
- （この手順は次の 2-3 スクリプトが自動で行うので、省略しても構いません。）

### 2-3. セットアップスクリプトを1回実行（これが本体）
SH-C30L を USB に挿した状態で、`tools\setup_ncec_wsl.ps1` を**右クリック →「PowerShell で実行」**
（自動で管理者に昇格します）。これ1本で次を自動実行します:
- WSL2 / distro(v2) の確認、`wsl --update`
- usbipd-win の確認・無ければ winget 導入
- SH-C30L（`1d50:606f`）の BUSID を自動検出 → `usbipd bind`（共有登録・1回だけ）
- WSL 側に **python3-tk / python3-can**（＋can-utils/ethtool）導入、`can0` 起動ラッパと
  NOPASSWD sudoers 設定

成功すると「以後は NCEC_Editor_WSL.bat をダブルクリック」と表示されます。

### 2-4. 動作確認（任意）
```powershell
powershell -ExecutionPolicy Bypass -File tools\ncec_wsl_launch.ps1 -Check
```
BUSID / attach 状態 / can0 の状態が表示されれば準備完了です（`-Check` は起動しません）。

## 3. 通常の使い方（CLIレス）
**`NCEC_Editor_WSL.bat` をダブルクリック**するだけ。ランチャーが自動で:
1. SH-C30L を WSL へ attach（挿し直した後も毎回自動）
2. `can0` を 500kbps で起動
3. エディタを WSL(WSLg) で起動（`NCEC_CAN=socketcan:can0`）

エディタの見た目・操作は従来と同一です。ROM を開いて編集し、**［ECU書き込み］ボタン**で書込。
socketcan 検出時は自動で最速設定（STmin下限=0）になり、gs_usb 向けの「高速転送？」確認は出ません。

- USBを挿し直した／`can0` が落ちた等で通信できないときは、エディタの
  **［設定］→［CAN接続（WSL/socketcan）］→［再接続］** で、端末に戻らず GUI だけで復旧できます。

## 4. 別PCでの再現
同じ4ステップだけです（**ユーザー名・配置に依存しません**）:
1. `wsl --install -d Ubuntu-24.04`（＋必要なら `wsl --update`）
2. `winget install usbipd`（2-3 が自動で入れるので省略可）
3. プロジェクト一式をそのPCへコピーし、`tools\setup_ncec_wsl.ps1` を1回実行
4. `NCEC_Editor_WSL.bat` をダブルクリック

スクリプトは BUSID を VID:PID で検索し、プロジェクトパスを `wslpath` で導出、WSL ユーザーを
`whoami` で取得するため、別ユーザー名・別ドライブ・別フォルダでも無改変で動きます。

## 5. 仕組み（内部で何をしているか）
- `NCEC_Editor_WSL.bat` → `tools/ncec_wsl_launch.ps1`（起動のたび・冪等）
  - `usbipd attach --wsl --busid <自動>`（管理者不要＝bind 済み前提）
  - `wsl -u root -- /usr/local/sbin/ncec-can0-up`（can0 を 500k で up）
  - `wsl -- bash -lc "cd <proj> && NCEC_CAN=socketcan:can0 python3 ncec_editor.py"`
- `tools/setup_ncec_wsl.ps1`（1回・管理者）→ 内部で `tools/setup_ncec_wsl.sh`（root）
  - apt 依存、`/usr/local/sbin/ncec-can0-up` 設置、`/etc/sudoers.d/ncec-can0`（NOPASSWD）
- エディタ側: `ncecu/canbus.py` が `NCEC_CAN=socketcan:can0` を解釈。`ncecu/wslcan.py` が
  状態確認と再接続（attach + can0 up）を担当。書込/ライブ/Mode23/DTC すべてが socketcan で高速化。

## 6. トラブルシュート
- **SH-C30L が見つからない**: USB を挿し直し、`usbipd list` に `1d50:606f` が出るか確認。
- **`can0` が出ない / 通信できない**: エディタの［CAN接続→再接続］。それでも駄目なら管理者PowerShellで
  `usbipd attach --wsl --busid <id>`、WSLで `sudo /usr/local/sbin/ncec-can0-up`。
- **通信が突然止まる / ［CAN接続］に「USB/IP 接続が切れています」と出る**: Wi-Fi やネットワークの切替、
  スリープ復帰で WSL の仮想ネットワークがリセットされ、アダプタを WSL へ渡している USB/IP 接続が切れた状態
  （Windows の `usbipd list` は `Shared`、WSL 側には `can0` が残る）。この状態の `can0` は操作すると固まるため、
  ［再接続］では直らない。**エディタを閉じる → PowerShell で `wsl --shutdown` → `NCEC_Editor_WSL.bat` で起動し直す。**
  予防: **車での作業中（特に書き込み中）は Wi-Fi を切る**／PC をスリープさせない。
  （2026-11-12 に実際に発生。当時のエディタは状態確認の `ip` コマンドを待ったままフリーズした。現在は接続切れを
  検出して上記の案内を出し、`can0` には触らない。）
- **「未 bind」と出る**: 初回の `tools\setup_ncec_wsl.ps1`（管理者）を実行していない。実行する。
- **WSLg の画面が出ない**: `wsl --update` でカーネル/WSLg を最新化し、PowerShellで `wsl --shutdown` 後に再試行。
- **古い WSL2 カーネルで can0 が出ない**: 6.x 未満だと CAN/gs_usb が無い場合がある。`wsl --update`。
  それでも駄目なら 下の「付録」の「2'. WSL2 カーネルに CAN + gs_usb を入れる」。
- **Windows の gs_usb から見えない**: USB は排他。WSL へ attach 中は Windows からは見えない（正常）。
  Windows 版を使うときは `usbipd detach --busid <id>`。

## 7. フォールバック（従来の Windows / gs_usb 起動）
WSL を使わず、従来どおり Windows 上で動かすこともできます（書込は遅い＝gs_usb）:
```powershell
python ncec_editor.py
```
この場合 CANアダプタは Windows に attach された状態（WSL に attach していない状態）にします。

## 関連資料
- この文書の末尾「付録: 技術背景と手動手順」 — socketcan 化の技術背景・ベンチ・カーネル事情。
- [flash_ja.md](flash_ja.md) — 書き込み時間のモデルと実測（gs_usb vs socketcan）。

---

## 付録: 技術背景と手動手順（WSL2 + socketcan で SH-C30L を使い、書き込みを高速化する手順）

> ここから下は、上の導入スクリプトが内部でやっていることの背景と、手動で行う場合の手順です。通常は読まなくて構いません。

最終更新: 2026-11-06

### ★結論（2026-11-06 実機確認済み）
**成功。約5倍速。しかもカーネル自前ビルドは不要だった。**
- WSL2 の既定カーネル **6.18.54.1-microsoft-standard-WSL2 は CAN + gs_usb を標準搭載**。
  `usbipd attach` した時点で `can0` が自動生成された（＝下記 **手順2 のカーネルビルドは丸ごと不要**）。
- `tx_test.py --floor 0` 実測：**47ms/メッセージ・21.5KiB/s・8/8成功**（Windows gs_usb の最速 233ms の約5倍）。
- **実フラッシュも実機で確認済**（当時の運用ROMをフル書込, `--tx-floor 0 --confirm`）：**ROM転送 41.1s
  (40.5ms/ブロック,24.7KiB/s)＋SBL/消去 17.3s＝全体 58.4s**。従来 Windows ~273s の **約4.7倍**。途中失敗0。
- フレーム単価 ~0.32ms は CANバス物理下限 0.26ms にほぼ肉薄＝**もうドライバ律速でなくバス帯域の限界**。
- → まず `ip link show can0` を確認。**can0 が出るならビルド不要**。出ない旧カーネルのときだけ手順2。
- **通常運用は GUI だけで完結**（新PC導入〜起動の手順書＝この文書の前半）:
  初回 `tools/setup_ncec_wsl.ps1`(管理者・1回) → 以後 `NCEC_Editor_WSL.bat` をダブルクリックで
  「attach → can0 起動 → エディタ(WSLg)起動」まで自動。本書の CLI 手順は仕組み理解・手動復旧用。

### 目的と効果
Windows の python-can(gs_usb) はフレーム毎に**ユーザ空間のUSB往復 ~1.3ms**がかかり、これが
書き込みの主ボトルネック（実測：送信だけで ~233〜266ms/ブロック、フル書込 ~254秒）。
Linux の **socketcan（カーネルの gs_usb ドライバ）** なら送信がカーネルレベルで、USB往復も
TXエコー処理も無いため、同じ 500kbps でも**フレーム毎のオーバーヘッドが桁違いに小さい**。
WSL2 に USB を渡して socketcan で焼けば、**大幅短縮**が見込める（CANバス上限 0.26ms/フレーム＝
理論 ~40秒/フル に近づく余地）。プロトコルや本プロジェクトのコードは無改造で動く
（`NCEC_CAN=socketcan:can0` を設定するだけ。`ncecu/canbus.py` 対応済み）。

### 全体像（最短2ステップ・6.x カーネルの場合）
1. **usbipd-win** で SH-C30L を WSL2 に渡す（bind→attach）。
2. WSL2(Ubuntu) で can0 を 500k で立ち上げ、`NCEC_CAN=socketcan:can0` で既存ツールを実行。

> 実機(6.18 カーネル)では attach した時点で `can0` が自動で現れた＝**カーネルビルドは不要**。
> **旧カーネル(5.15 等)で can0 が出ない場合だけ**、下記「2'. カーネル自前ビルド」を行う。

---

### 0. 前提のインストール（この機は未導入。最初にこれ）
※ 管理者 PowerShell。`wsl --install` は再起動と、Ubuntu 初回起動時のユーザー名/パスワード設定を伴う。

```powershell
# (1) WSL2 + Ubuntu を導入（Windowsの機能有効化→要再起動）
wsl --install -d Ubuntu
#  → 再起動後、Ubuntu が自動で開く。ユーザー名とパスワードを設定する。
#  → 既定で WSL2。念のため: wsl --set-default-version 2

# (2) usbipd-win を導入
winget install usbipd
#  winget が無ければ https://github.com/dorssel/usbipd-win/releases から .msi を入れる
```
導入後に新しい管理者 PowerShell を開き直し、`usbipd --version` と `wsl -l -v`（VERSION=2）を確認。

> 補足：**最近の WSL2 カーネル(6.x 系)は CAN/gs_usb を標準搭載**しており、本機(6.18)では
> attach 後に `can0` が自動で出た＝ビルド不要。古い WSL2 カーネル(5.15 等)で `can0` が
> 出ないときだけ後述 **2' の自前ビルド**を行う（または Live USB / 予備PC / Raspberry Pi を使う）。

### 1. usbipd-win（USBパススルー）
Windows(管理者 PowerShell)で:
```powershell
winget install usbipd
usbipd list                                  # SH-C30L の BUSID を確認(例 1-4)
usbipd bind --busid 1-4                       # 一度だけ(共有登録)
usbipd attach --wsl --busid 1-4               # WSL2 へ接続(再接続の度に実行)
```
WSL2(Ubuntu)側で `lsusb` に candleLight / OpenMoko 等として見えればOK。
（抜き差しや再起動の度に `usbipd attach` が必要。`--auto-attach` を使うスクリプトでも可。）

### 2'. WSL2 カーネルに CAN + gs_usb を入れる（旧カーネルで can0 が出ないときだけ）
**本機(6.18)では不要だった。** `ip link show can0` で can0 が既に出ているならこの節はスキップ。
古い WSL2 カーネル(5.15 等)で CAN サブシステムと gs_usb が**入っていない**場合だけ、一度自前ビルドする。

WSL2(Ubuntu)で:
```bash
sudo apt update
sudo apt install -y build-essential flex bison libssl-dev libelf-dev bc dwarves git \
                    libncurses-dev pahole
uname -r                                      # 例 5.15.167.4-microsoft-standard-WSL2
git clone --depth 1 -b linux-msft-wsl-$(uname -r | sed 's/-microsoft.*//') \
    https://github.com/microsoft/WSL2-Linux-Kernel.git
cd WSL2-Linux-Kernel
cp Microsoft/config-wsl .config                # 既定configを土台に
```
`.config` に以下を有効化（`scripts/config` が簡単）:
```bash
scripts/config --enable CONFIG_CAN
scripts/config --enable CONFIG_CAN_RAW
scripts/config --enable CONFIG_CAN_DEV
scripts/config --module CONFIG_CAN_GS_USB      # candleLight(SH-C30L)のドライバ
# usbip クライアント(usbipd-winの受け)が無ければ:
scripts/config --enable CONFIG_USBIP_CORE
scripts/config --enable CONFIG_USBIP_VHCI_HCD
```
ビルドしてWindowsへ配置:
```bash
make -j$(nproc)                                # bzImage 生成(数分〜)
cp arch/x86/boot/bzImage /mnt/c/Users/<ユーザー名>/wsl-kernel-can
```
Windows の `C:\Users\<ユーザー名>\.wslconfig` に:
```ini
[wsl2]
kernel=C:\\Users\\<ユーザー名>\\wsl-kernel-can
```
PowerShell で `wsl --shutdown` → 再起動。`uname -r` が自前カーネルになり、`modprobe gs_usb`
が通ればOK。
（※バージョン文字列はお使いの `uname -r` に合わせる。tag が無ければ近いブランチで可。）

### 3. can0 を立ち上げて実行
WSL2(Ubuntu):
```bash
# Ubuntu 24.04 は PEP668 で pip 直入れが弾かれるので python-can は apt で入れるのが楽。
# socketcan では gs_usb/pyusb は不要(=Windowsの candleLight 専用)。python-can だけでよい。
sudo apt install -y can-utils python3-can ethtool
ethtool -i can0                  # driver: gs_usb なら確定(6.xは自動ロード済み)
ip link show can0                # attach済みなら can0 が出ている(6.xは自動生成)
sudo ip link set can0 type can bitrate 500000
sudo ip link set up can0
ip -details link show can0       # state UP / can state ERROR-ACTIVE を確認
# 疎通確認(別端末で candump can0、こちらで cansend など)
candump can0 &
```
本プロジェクトを実行（/mnt/c から直接でも可）:
```bash
cd /mnt/c/Users/<ユーザー名>/<置いた場所>/NECEECU
export NCEC_CAN=socketcan:can0            # ★これで全ツールが socketcan を使う
python3 tools/tx_test.py --floor 0        # まず送信ベンチ(socketcanはfloor 0でも安全)
python3 tools/flash_writeback.py --sbl Decryption_sbl/sbl_nc1_flash_0x2000.bin --rom rom_data/<書き込むROM>.bin --confirm
```
実測(2026-11-06)：`tx_test --floor 0` が **47ms/メッセージ・21.5KiB/s・8/8成功**（Windows の 233ms
から約5倍改善）。フル書込TX推定 ~48s（従来 ~254s）。実フラッシュも同様に短縮する見込み。

### 4. 補足・トラブル
- **floor は socketcan では 0 でよい**（USB FIFO 溢れの心配が無い＝gs_usb固有の問題だった）。
  `--floor 0`／`--tx-floor 0` で最速。`realtime_guard` は Windows 専用処理なので Linux では無害に no-op。
- `lsusb` に出ない → `usbipd attach` やり直し / `usbipd bind` 済みか確認。
- `can0` が出ない → `dmesg | grep -i gs_usb` でドライバロード確認。カーネルに CONFIG_CAN_GS_USB が
  入っていなければ 2 をやり直し。
- 権限 → `ip link` 系は sudo。python 実行は sudo 不要（can0 が up なら一般ユーザで送受信可）。
- **書き込みは予備ECUのみ・停車・電源安定**（方式が変わっても安全ルールは同じ）。
- どうしてもカーネルビルドが手間なら、**ネイティブLinux機 / Raspberry Pi / ライブUSB** に
  SH-C30L を挿せばカーネルビルド不要で socketcan が即使える（WSL2に拘らない場合の近道）。

### 5. コード側の対応（実装済み）
- `ncecu/canbus.py`：`NCEC_CAN=socketcan:can0`（または `socketcan`）で socketcan を開く。
  bitrate は OS 側(ip link)設定前提でコードからは渡さない。既定(gs_usb)呼び出しだけを上書きするので
  Windows 側の動作は不変。`close_bus` は socketcan でも `shutdown()` のみで安全。
- 既存の全ツール（flash_writeback / tx_test / dashboard / editor のライブ等）は open_bus 経由なので、環境変数だけで切替わる。
