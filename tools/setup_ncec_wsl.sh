#!/bin/sh
# NCEC: WSL2(Ubuntu)側の一度きりセットアップ。root で実行する。
#   引数1 = GUI/一般ユーザー名(sudoers NOPASSWD の対象)。省略時は SUDO_USER→UID1000 を推定。
# 通常は tools/setup_ncec_wsl.ps1 から自動で呼ばれる(CR除去済みの一時コピーを bash 実行)。
# 冪等: 二重実行・既導入で壊れない。
# 出力は ASCII(Windows PowerShell コンソールの文字化け回避)。
set -e

TARGET_USER="${1:-${SUDO_USER:-}}"
if [ -z "$TARGET_USER" ]; then
    TARGET_USER="$(id -un 1000 2>/dev/null || true)"
fi
# ncec-can0-up の在りか。/tmp のCR除去コピーから実行される場合は PS1 が NCEC_SRC_DIR を渡す。
SELF_DIR="${NCEC_SRC_DIR:-$(cd "$(dirname "$0")" && pwd)}"

echo "== NCEC WSL setup =="
echo "target user = ${TARGET_USER:-'(unknown)'}"
echo "script dir  = $SELF_DIR"

# 1) 依存パッケージ。エディタ本体が要るのは python3-tk + python3-can の2つ。
#    can-utils/ethtool/iproute2 は診断・can0 操作用。
#    fonts-noto-cjk は WSLg(Tk) で日本語を表示するため(無いと GUI が □□□ の豆腐になる)。
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-tk python3-can can-utils ethtool iproute2 fonts-noto-cjk
# 追加ツール(PDF取説生成/逆アセンブル)は任意。失敗しても続行。
apt-get install -y python3-pil python3-capstone 2>/dev/null \
    || echo "  (optional python3-pil/python3-capstone skipped)"

# 2) can0 起動ラッパを /usr/local/sbin へ(CR除去して複製)。
if [ -f "$SELF_DIR/ncec-can0-up" ]; then
    tr -d '\r' < "$SELF_DIR/ncec-can0-up" > /usr/local/sbin/ncec-can0-up
    chmod 0755 /usr/local/sbin/ncec-can0-up
    echo "installed /usr/local/sbin/ncec-can0-up"
else
    echo "!! $SELF_DIR/ncec-can0-up not found"
    exit 1
fi

# 3) sudoers NOPASSWD ドロップイン(GUIが一般ユーザーのまま can0 up 可能に)。
if [ -n "$TARGET_USER" ]; then
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/ncec-can0-up\n' "$TARGET_USER" \
        > /etc/sudoers.d/ncec-can0
    chmod 0440 /etc/sudoers.d/ncec-can0
    if visudo -cf /etc/sudoers.d/ncec-can0 >/dev/null 2>&1; then
        echo "installed /etc/sudoers.d/ncec-can0 (user=$TARGET_USER)"
    else
        echo "!! sudoers validation failed; removing /etc/sudoers.d/ncec-can0"
        rm -f /etc/sudoers.d/ncec-can0
    fi
else
    echo "!! target user unknown; skipped sudoers (pass it as arg 1)"
fi

# 4) 検証
if python3 -c "import tkinter, can" 2>/dev/null; then
    echo "OK: python3 can import tkinter / can"
else
    echo "!! python3 failed to import tkinter/can (check python3-tk / python3-can)"
fi
echo "== done =="
