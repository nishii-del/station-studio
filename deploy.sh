#!/bin/bash
# ============================================
# STATION STUDIO — GCE VM デプロイスクリプト
# ============================================
# 前提:
#   1. gcloud CLI インストール済み
#   2. gcloud auth login 済み
#   3. Google Cloud プロジェクト作成済み
#
# 使い方:
#   gcloud config set project YOUR_PROJECT_ID
#   bash deploy.sh
# ============================================

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
    echo "エラー: gcloud config set project YOUR_PROJECT_ID を先に実行してください"
    exit 1
fi

ZONE="us-central1-a"
VM_NAME="station-studio"
MACHINE_TYPE="e2-small"

echo "=== プロジェクト: $PROJECT_ID ==="
echo "=== VM: $VM_NAME ($MACHINE_TYPE) in $ZONE ==="
echo ""

# 1. ファイアウォール（8501ポート開放）
echo ">>> ファイアウォール設定..."
gcloud compute firewall-rules create allow-streamlit \
    --allow tcp:8501 \
    --target-tags streamlit-server \
    --description "Streamlit app port" \
    2>/dev/null || echo "  (既に存在)"

# 2. VM作成（Ubuntu + 起動スクリプト）
echo ">>> VM作成..."
gcloud compute instances create $VM_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --tags=streamlit-server \
    --metadata-from-file=startup-script=startup.sh

echo ""
echo "=== VM作成完了 ==="
sleep 5
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo ""
echo "  URL: http://$EXTERNAL_IP:8501"
echo ""
echo "  ※ 初回起動に3〜5分かかります"
echo "  ※ ログ確認:"
echo "    gcloud compute ssh $VM_NAME --zone=$ZONE -- 'sudo journalctl -u station-studio -f'"
echo "  ※ コード更新:"
echo "    gcloud compute ssh $VM_NAME --zone=$ZONE -- 'cd /opt/station-studio && sudo git pull && sudo systemctl restart station-studio'"
