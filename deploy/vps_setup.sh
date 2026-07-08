#!/usr/bin/env bash
# Nest Egg VPS初期セットアップ（Ubuntu 22.04/24.04想定）
# 使い方: bash deploy/vps_setup.sh
# 環境変数で上書き可能: APP_DIR, REPO_URL, BRANCH
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nestegg}"
REPO_URL="${REPO_URL:-https://github.com/kanipan0611/Kabu.git}"
BRANCH="${BRANCH:-main}"

echo "=== 1/5 パッケージのインストール ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv git

echo "=== 2/5 タイムゾーンをJSTに設定（タイマーの15:40が日本時間になるように）==="
sudo timedatectl set-timezone Asia/Tokyo

echo "=== 3/5 アプリの配置 ==="
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    sudo mkdir -p "$APP_DIR"
    sudo chown "$(whoami)" "$APP_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "=== 4/5 Python環境の構築 ==="
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== 5/5 systemdユニットの登録 ==="
RUN_USER="$(whoami)"
for unit in nestegg-ui.service nestegg-signals.service nestegg-signals.timer; do
    sed "s|__APP_DIR__|$APP_DIR|g; s|__USER__|$RUN_USER|g" "deploy/$unit" | sudo tee "/etc/systemd/system/$unit" > /dev/null
done
sudo systemctl daemon-reload

cat <<MSG

セットアップ完了。有効化するには:

  sudo systemctl enable --now nestegg-ui.service       # ブラウザUI（localhost:8501）
  sudo systemctl enable --now nestegg-signals.timer    # 平日15:40の自動シグナル実行

UIへは手元のPCから:  ssh -L 8501:localhost:8501 $RUN_USER@<VPSのIP>
その後ブラウザで http://localhost:8501 を開く。

状態確認:
  systemctl status nestegg-ui
  systemctl list-timers nestegg-signals.timer
  journalctl -u nestegg-signals -n 50
MSG
