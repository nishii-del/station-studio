#!/bin/bash
# GCE VM 初回起動スクリプト (Ubuntu)
set -e

APP_DIR="/opt/station-studio"
REPO="https://github.com/nishii-del/station-studio.git"

# 既にセットアップ済みなら起動のみ
if [ -f "$APP_DIR/app.py" ]; then
    cd $APP_DIR
    sudo systemctl start station-studio
    exit 0
fi

# 初回セットアップ
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# リポジトリ取得
git clone $REPO $APP_DIR
cd $APP_DIR

# Python仮想環境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# outputディレクトリ作成
mkdir -p output/station output/city output/image_cache

# systemdサービス登録
cat > /etc/systemd/system/station-studio.service << 'EOF'
[Unit]
Description=Station Studio Streamlit App
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/station-studio
ExecStart=/opt/station-studio/venv/bin/streamlit run app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable station-studio
systemctl start station-studio
