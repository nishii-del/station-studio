"""
設定ファイル - APIキーと各種パラメータを管理
"""
import os
import logging

# =============================================
# APIキー設定（環境変数 or 直接入力）
# =============================================

# ODPT（公共交通オープンデータ）コンシューマキー
# 取得先: https://developer.odpt.org/
ODPT_CONSUMER_KEY = os.environ.get("ODPT_CONSUMER_KEY", "YOUR_ODPT_KEY_HERE")

# Google Custom Search API キー
# 取得先: https://console.cloud.google.com/
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "YOUR_GOOGLE_API_KEY_HERE")

# Google Programmable Search Engine ID
# 取得先: https://programmablesearchengine.google.com/
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "YOUR_CSE_ID_HERE")

# =============================================
# 画像設定
# =============================================

# 最小画像幅（px）
MIN_IMAGE_WIDTH = 400

# 1駅あたりの取得画像数
IMAGES_PER_STATION = 1

# 画像検索クエリテンプレート
# メインクエリ（駅舎外観 — 建物+駅名が写る）
IMAGE_SEARCH_QUERY = '"{station_name}駅" 駅舎 外観 -ナンバリング -路線図 -アイコン'
# フォールバッククエリ（入口 — 地下鉄向け）
IMAGE_SEARCH_QUERY_FALLBACK = '"{station_name}駅" 入口 外観 -ナンバリング -路線図'

# =============================================
# API エンドポイント
# =============================================

ODPT_BASE_URL = "https://api.odpt.org/api/v4"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"

# =============================================
# 出力ディレクトリ
# =============================================

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
STATION_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "station")
CITY_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "city")
IMAGE_CACHE_DIR = os.path.join(OUTPUT_DIR, "image_cache")

# =============================================
# ログ設定
# =============================================

LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# =============================================
# パスワード設定
# =============================================

APP_DELETE_PASSWORD = os.environ.get("STATION_STUDIO_DELETE_PW", "delete2024")

# ユーザーアカウント {ID: パスワード}
APP_USERS = {
    "ishii":      "St@ishii2024",
    "obuchi":     "St@obuchi2024",
    "takeuchi":   "St@takeuchi2024",
    "hirayama":   "St@hirayama2024",
    "horii":      "St@horii2024",
    "izumi":      "St@izumi2024",
    "wada":       "St@wada2024",
    "hashimoto":  "St@hashimoto2024",
    "takahashi":  "St@takahashi2024",
    "hamada":     "St@hamada2024",
    "morimoto":   "St@morimoto2024",
    "fujita":     "St@fujita2024",
    "kanbu":      "St@kanbu2024",
}


def setup_logging():
    """ログ設定を初期化"""
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    return logging.getLogger("store-traffic")


def validate_keys():
    """APIキーが設定されているか確認"""
    warnings = []
    if ODPT_CONSUMER_KEY == "YOUR_ODPT_KEY_HERE":
        warnings.append("ODPT_CONSUMER_KEY が未設定です（駅別モードに必要）")
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        warnings.append("GOOGLE_API_KEY が未設定です（画像検索に必要）")
    if GOOGLE_CSE_ID == "YOUR_CSE_ID_HERE":
        warnings.append("GOOGLE_CSE_ID が未設定です（画像検索に必要）")
    return warnings
