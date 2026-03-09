"""
画像取得モジュール - Wikipedia + Wikimedia Commons + Flickr（商用利用可能ライセンスのみ）
"""
import io
import json
import os
import re
import logging
import shutil
import time

import requests
from PIL import Image

from config import (
    GOOGLE_API_KEY,
    FLICKR_API_KEY,
    PLACES_TEXT_SEARCH_URL,
    PLACES_PHOTO_URL_TEMPLATE,
    PLACES_PHOTO_MAX_WIDTH,
    PLACES_PHOTO_CANDIDATES,
    MIN_IMAGE_WIDTH,
    IMAGES_PER_STATION,
    IMAGE_CACHE_DIR,
)

logger = logging.getLogger("store-traffic")

# リクエスト間隔（秒）
REQUEST_DELAY = 2.0

# 商用利用可能なライセンス
_COMMERCIAL_OK_LICENSES = {
    "cc0", "cc-zero", "pd", "public domain",
    "cc-by", "cc-by-1.0", "cc-by-2.0", "cc-by-2.5", "cc-by-3.0", "cc-by-4.0",
    "cc-by-sa", "cc-by-sa-1.0", "cc-by-sa-2.0", "cc-by-sa-2.5", "cc-by-sa-3.0", "cc-by-sa-4.0",
}


def _is_commercial_license(file_title):
    """
    Wikimedia Commonsのファイルが商用利用可能なライセンスかチェック。
    CC BY-NC など非商用ライセンスの画像を除外する。
    """
    try:
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": file_title,
                "prop": "imageinfo",
                "iiprop": "extmetadata",
                "format": "json",
            },
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            metadata = page.get("imageinfo", [{}])[0].get("extmetadata", {})
            license_short = metadata.get("LicenseShortName", {}).get("value", "").lower().strip()
            license_url = metadata.get("LicenseUrl", {}).get("value", "").lower()
            # 正規化: スペースをハイフンに変換して統一
            license_normalized = license_short.replace(" ", "-")
            # NC（非商用）を含むライセンスは除外
            if "nc" in license_normalized or "nc" in license_url:
                logger.debug(f"Commons: 非商用ライセンス除外: {file_title} ({license_short})")
                return False
            # 既知の商用OKライセンスにマッチするか確認
            for ok in _COMMERCIAL_OK_LICENSES:
                if ok in license_normalized or ok in license_url:
                    logger.debug(f"Commons: 商用利用可: {file_title} ({license_short})")
                    return True
            # 不明なライセンスは安全側で除外
            logger.debug(f"Commons: 不明ライセンス除外: {file_title} ({license_short})")
            return False
    except Exception as e:
        logger.debug(f"Commons: ライセンス確認エラー: {file_title} ({e})")
        return False


# Flickr 商用利用可能ライセンスID
# 4=CC BY, 5=CC BY-SA, 7=PDM, 8=US Gov, 9=CC0, 10=PDM
_FLICKR_COMMERCIAL_LICENSES = "4,5,7,8,9,10"


def _flickr_search_station(station_name, output_dir, safe_name, station_type=None):
    """
    Flickr APIで駅画像を検索（商用利用可能ライセンスのみ）。
    """
    if FLICKR_API_KEY == "YOUR_FLICKR_API_KEY_HERE":
        logger.debug("Flickr APIキーが未設定です。スキップします。")
        return []

    if station_type == "terminal":
        queries = [
            f"{station_name} ランドマーク",
            f"{station_name} 風景",
            f"{station_name} landmark",
        ]
    else:
        queries = [
            f"{station_name}駅 駅舎",
            f"{station_name}駅 外観",
            f"{station_name} station building",
        ]

    for query in queries:
        try:
            resp = requests.get(
                "https://api.flickr.com/services/rest/",
                params={
                    "method": "flickr.photos.search",
                    "api_key": FLICKR_API_KEY,
                    "text": query,
                    "license": _FLICKR_COMMERCIAL_LICENSES,
                    "sort": "relevance",
                    "content_type": 1,
                    "media": "photos",
                    "per_page": 10,
                    "format": "json",
                    "nojsoncallback": 1,
                    "extras": "url_l,url_o,url_c,url_z",
                },
                headers=_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.debug(f"Flickr検索エラー: {e}")
            continue

        photos = data.get("photos", {}).get("photo", [])
        if not photos:
            continue

        for photo in photos:
            image_url = (
                photo.get("url_o")
                or photo.get("url_l")
                or photo.get("url_c")
                or photo.get("url_z")
            )
            if not image_url:
                continue

            save_path = os.path.join(output_dir, f"{safe_name}_1.jpg")

            if _download_image(image_url, save_path):
                if not _is_outdoor_photo(save_path):
                    os.remove(save_path)
                    continue
                if _is_aerial_photo(save_path):
                    os.remove(save_path)
                    continue
                if _is_train_or_platform_photo(save_path):
                    os.remove(save_path)
                    continue

                logger.info(f"Flickr: 駅舎外観取得成功 (商用利用可): {station_name}駅")
                return [save_path]

            time.sleep(REQUEST_DELAY)

    logger.info(f"Flickr: 駅舎外観写真なし: {station_name}駅")
    return []


# ターミナル駅リスト（乗降者数が多く、象徴的な建物がある駅）
_TERMINAL_STATIONS = {
    "渋谷", "新宿", "池袋", "東京", "品川", "上野", "秋葉原",
    "横浜", "川崎", "大宮", "千葉", "立川", "町田", "吉祥寺",
    "大阪", "梅田", "難波", "天王寺", "京都", "三ノ宮", "神戸",
    "名古屋", "栄", "金山", "札幌", "仙台", "広島", "博多",
    "天神", "小倉", "新横浜", "武蔵小杉", "自由が丘", "中目黒",
    "恵比寿", "目黒", "五反田", "大崎", "浜松町", "新橋", "有楽町",
    "神田", "御茶ノ水", "水道橋", "飯田橋", "四ツ谷", "市ヶ谷",
    "高田馬場", "中野", "荻窪", "三鷹", "国分寺", "八王子",
    "藤沢", "戸塚", "鶴見", "蒲田", "錦糸町", "北千住",
}

# 地下鉄路線名キーワード（この路線の駅は地下鉄タイプ）
_SUBWAY_KEYWORDS = [
    "東京メトロ", "都営", "横浜市営地下鉄", "大阪メトロ",
    "名古屋市営地下鉄", "札幌市営地下鉄", "仙台市地下鉄",
    "福岡市地下鉄", "京都市営地下鉄", "神戸市営地下鉄",
]


def _classify_station_type(station_name, railways=None):
    """
    駅タイプを分類: terminal / subway / local
    """
    if station_name in _TERMINAL_STATIONS:
        return "terminal"

    if railways:
        for rw in railways:
            for kw in _SUBWAY_KEYWORDS:
                if kw in rw:
                    return "subway"

    return "local"


# ターミナル駅ごとの象徴的なランドマーク（Commonsで検索しやすいキーワード）
_TERMINAL_LANDMARKS = {
    "渋谷": ["Shibuya Crossing", "渋谷スクランブル交差点", "Shibuya scramble"],
    "新宿": ["Shinjuku skyscrapers", "新宿高層ビル", "Shinjuku skyline"],
    "池袋": ["Ikebukuro Sunshine", "池袋サンシャイン", "Ikebukuro east exit"],
    "東京": ["Tokyo Station Marunouchi", "東京駅丸の内", "Tokyo Station red brick"],
    "品川": ["Shinagawa skyline", "品川 高層ビル"],
    "上野": ["Ueno Park", "上野公園", "Ueno Ameyoko"],
    "秋葉原": ["Akihabara electric town", "秋葉原 電気街"],
    "横浜": ["Yokohama Minato Mirai", "横浜みなとみらい", "Yokohama landmark tower"],
    "大阪": ["Osaka Dotonbori", "大阪道頓堀", "Osaka cityscape"],
    "梅田": ["Umeda Sky Building", "梅田スカイビル"],
    "京都": ["Kyoto Tower", "京都タワー"],
    "名古屋": ["Nagoya Station towers", "名古屋駅前 高層ビル"],
    "博多": ["Hakata Canal City", "博多キャナルシティ"],
    "仙台": ["Sendai arcade", "仙台アーケード"],
    "札幌": ["Sapporo TV Tower", "札幌テレビ塔"],
}


def _generate_search_queries(station_name, station_type):
    """
    駅タイプに応じた最適な検索クエリを生成。
    Returns: dict with commons_queries, places_query, exclude_keywords
    """
    if station_type == "terminal":
        # 駅固有のランドマーク検索があればそれを使う
        landmarks = _TERMINAL_LANDMARKS.get(station_name)
        if landmarks:
            commons = landmarks[:3]
            places = landmarks[0]
        else:
            commons = [
                f"{station_name} cityscape",
                f"{station_name} 街並み 風景",
                f"{station_name} skyline",
            ]
            places = f"{station_name} 街並み ランドマーク"
        exclude = ['platform', 'interior', 'map', 'diagram', '改札',
                   'ticket', 'concourse', 'train', '電車', 'ホーム']

    elif station_type == "subway":
        commons = [
            f"{station_name}駅 入口",
            f"{station_name}駅 地上 出入口",
            f"{station_name} station entrance ground level",
        ]
        places = f"{station_name}駅 入口 地上"
        exclude = ['platform', 'underground', 'map', 'route']

    else:  # local
        commons = [
            f"{station_name}駅 駅舎",
            f"{station_name}駅 外観",
            f"{station_name} station building exterior",
        ]
        places = f"{station_name}駅 駅舎 外観"
        exclude = ['platform', 'track', 'interior', 'map']

    logger.info(f"駅タイプ判定: {station_name}駅 → {station_type}")
    return {
        "type": station_type,
        "commons_queries": commons,
        "places_query": places,
        "exclude_keywords": exclude,
    }

# 共通ヘッダー（Wikimediaポリシー準拠）
_HEADERS = {
    "User-Agent": "StationStudio/1.0 (https://github.com/station-studio; station.studio.app@gmail.com)"
}


def _sanitize_filename(name):
    """ファイル名として安全な文字列に変換"""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


def _get_cached_images(station_name):
    """キャッシュディレクトリから画像パスリストを返す。なければ空リスト。"""
    cache_dir = os.path.join(IMAGE_CACHE_DIR, _sanitize_filename(station_name))
    if not os.path.isdir(cache_dir):
        return []
    images = sorted(
        f for f in os.listdir(cache_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )
    if not images:
        return []
    return [os.path.join(cache_dir, f) for f in images]


def _save_to_cache(station_name, image_paths):
    """保管庫に全画像を上書き保存する。"""
    cache_dir = os.path.join(IMAGE_CACHE_DIR, _sanitize_filename(station_name))
    os.makedirs(cache_dir, exist_ok=True)
    # 古い画像を全削除（meta.jsonは保持）
    for old in os.listdir(cache_dir):
        if old == "meta.json":
            continue
        old_path = os.path.join(cache_dir, old)
        if os.path.isfile(old_path):
            os.remove(old_path)
    # 全枚保存
    safe_name = _sanitize_filename(station_name)
    for i, src in enumerate(image_paths):
        ext = os.path.splitext(src)[1] or ".jpg"
        dst = os.path.join(cache_dir, f"{safe_name}_{i+1}{ext}")
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)


def save_cache_meta(station_name, meta):
    """保管庫にメタデータを保存"""
    cache_dir = os.path.join(IMAGE_CACHE_DIR, _sanitize_filename(station_name))
    os.makedirs(cache_dir, exist_ok=True)
    meta_path = os.path.join(cache_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_all_cache_meta():
    """保管庫の全駅メタデータを読み込む"""
    entries = []
    if not os.path.isdir(IMAGE_CACHE_DIR):
        return entries
    for d in sorted(os.listdir(IMAGE_CACHE_DIR)):
        dir_path = os.path.join(IMAGE_CACHE_DIR, d)
        if not os.path.isdir(dir_path):
            continue
        has_img = any(
            f.lower().endswith(('.jpg', '.jpeg', '.png'))
            for f in os.listdir(dir_path)
        )
        if not has_img:
            continue
        meta_path = os.path.join(dir_path, "meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, IOError):
                meta = {"name": d}
        else:
            meta = {"name": d}
        meta["_dir"] = dir_path
        entries.append(meta)
    return entries


def _copy_from_cache(station_name, cached_paths, output_dir):
    """キャッシュからoutput_dirにコピーして新パスリストを返す。"""
    os.makedirs(output_dir, exist_ok=True)
    safe_name = _sanitize_filename(station_name)
    result = []
    for i, src in enumerate(cached_paths):
        ext = os.path.splitext(src)[1] or ".jpg"
        dst = os.path.join(output_dir, f"{safe_name}_{i + 1}{ext}")
        shutil.copy2(src, dst)
        result.append(dst)
    return result


def has_cached_images(station_name):
    """保管庫に画像があるか"""
    cache_dir = os.path.join(IMAGE_CACHE_DIR, _sanitize_filename(station_name))
    if not os.path.isdir(cache_dir):
        return False
    return any(f.lower().endswith(('.jpg', '.jpeg', '.png')) for f in os.listdir(cache_dir))


def _validate_image_size(image_data):
    """画像が最小幅を満たしているか検証"""
    try:
        img = Image.open(io.BytesIO(image_data))
        width = img.size[0]
        if width >= MIN_IMAGE_WIDTH:
            return True
        logger.debug(f"画像幅不足: {width}px < {MIN_IMAGE_WIDTH}px")
        return False
    except Exception as e:
        logger.debug(f"画像検証エラー: {e}")
        return False


def _download_image(url, save_path, retries=2):
    """画像をダウンロードして保存。サイズ検証・429リトライ付き。"""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=30, stream=True)

            if resp.status_code == 429:
                wait = min(5 * (attempt + 1), 15)
                logger.info(f"429レート制限。{wait}秒待機... (試行{attempt+1})")
                time.sleep(wait)
                continue

            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                logger.debug(f"画像でないコンテンツ: {content_type}")
                return False

            image_data = resp.content
            if not _validate_image_size(image_data):
                return False

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(image_data)
            logger.info(f"画像保存: {save_path}")
            return True
        except requests.RequestException as e:
            logger.debug(f"画像ダウンロード失敗: {e}")
            return False
    return False


def _is_outdoor_photo(image_path):
    """
    画像が屋外写真かどうかを判定。
    画像上部1/4に「青い空」ピクセルがあるかで判定。
    蛍光灯の白い光（室内）を空と誤判定しないよう、青色優位のピクセルのみカウント。
    """
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        # 大きい画像はリサイズして高速化
        if w > 800:
            ratio = 800 / w
            img = img.resize((800, int(h * ratio)))
            w, h = img.size
        # 上部1/4を分析
        top_region = img.crop((0, 0, w, h // 4))
        pixels = list(top_region.getdata())
        total = len(pixels)
        if total == 0:
            return True

        blue_sky = 0
        white_sky = 0
        for r, g, b in pixels:
            # 青空: 青が赤・緑より明確に高い（暗い青空も検出）
            if b > 80 and b > r + 20 and b > g:
                blue_sky += 1
            # 白い空/曇り空: 全体的に非常に明るく均一
            elif r > 210 and g > 210 and b > 210:
                white_sky += 1

        blue_ratio = blue_sky / total
        white_ratio = white_sky / total

        # 青空ピクセルがある場合は白い空も加算
        # 青空がごく少量の場合、白い天井の誤検出を防止
        # ただし白が圧倒的に多い（>60%）場合は曇り空と判定
        if blue_ratio >= 0.05:
            sky_ratio = blue_ratio + white_ratio * 0.3
        elif blue_ratio >= 0.02:
            sky_ratio = blue_ratio + white_ratio * 0.15
        elif white_ratio > 0.6:
            sky_ratio = white_ratio * 0.15
        else:
            sky_ratio = blue_ratio

        is_outdoor = sky_ratio > 0.05
        logger.debug(f"屋外判定: blue={blue_ratio:.2f} white={white_ratio:.2f} sky={sky_ratio:.2f} → {'屋外' if is_outdoor else '屋内'}")
        return is_outdoor
    except Exception as e:
        logger.debug(f"屋外判定エラー: {e}")
        return True  # エラー時は許可


def _is_aerial_photo(image_path):
    """
    空撮・俯瞰写真かどうかを判定。
    地上写真: 下部は道路・地面（暗め、低コントラスト）
    空撮写真: 下部にも建物の屋根や線路が密集（高コントラスト + 構造物の色）
    """
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if w < 200 or h < 200:
            return False
        # リサイズして高速化
        if w > 600:
            ratio = 600 / w
            img = img.resize((600, int(h * ratio)))
            w, h = img.size

        # まず上部に空があるかチェック（空撮は俯瞰なので上部に空が少ない）
        top = img.crop((0, 0, w, h // 4))
        top_pixels = list(top.getdata())
        top_total = len(top_pixels)
        sky_in_top = 0
        for r, g, b in top_pixels:
            if (b > 80 and b > r + 20 and b > g) or (r > 200 and g > 200 and b > 200):
                sky_in_top += 1
        sky_top_ratio = sky_in_top / top_total if top_total else 0
        if sky_top_ratio > 0.3:
            # 上部に空が多い → 地上撮影であり空撮ではない
            logger.debug(f"空撮判定: 上部に空あり({sky_top_ratio:.2f}) → 地上撮影")
            return False

        # 中央1/3の分析（空撮なら建物屋根が見える、地上なら建物の壁面）
        mid = img.crop((0, h // 3, w, h * 2 // 3))
        mid_pixels = list(mid.getdata())
        mid_total = len(mid_pixels)

        # 中央部に空（青）が含まれているか → 空撮は俯瞰なので中央に空はない
        # 地上写真の場合、中央は建物壁面（グレー/茶系）
        # 空撮の場合、中央は建物屋根（グレー系）+ 線路（細い線）

        # グレー系屋根ピクセル（R≒G≒B、暗め）の割合
        roof_count = 0
        for r, g, b in mid_pixels:
            diff = max(r, g, b) - min(r, g, b)
            brightness = (r + g + b) / 3
            if diff < 30 and 60 < brightness < 180:
                roof_count += 1
        roof_ratio = roof_count / mid_total

        # 下部1/4に道路/地面があるか（地上写真の特徴）
        bottom = img.crop((0, h * 3 // 4, w, h))
        bottom_pixels = list(bottom.getdata())
        bottom_total = len(bottom_pixels)
        dark_ground = sum(1 for r, g, b in bottom_pixels if (r + g + b) / 3 < 100)
        ground_ratio = dark_ground / bottom_total

        # 空撮: 中央にグレー屋根が非常に多い
        is_aerial = roof_ratio > 0.4
        logger.debug(f"空撮判定: roof={roof_ratio:.2f} ground={ground_ratio:.2f} → {'空撮' if is_aerial else '地上'}")
        return is_aerial
    except Exception as e:
        logger.debug(f"空撮判定エラー: {e}")
        return False


def _is_train_or_platform_photo(image_path):
    """
    電車やホームの写真かどうかを判定。
    複数チェック:
      1. 水平均一帯（電車車体）
      2. ホーム（暗い線路 + 黄色安全線）
      3. 金属的なグレー帯（電車のステンレス車体）
      4. 架線・パンタグラフ（上部の細い水平線構造）
    """
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if w > 800:
            ratio = 800 / w
            img = img.resize((800, int(h * ratio)))
            w, h = img.size

        sample_step = max(1, w // 30)

        # Check 1: 中央60%の水平均一性（電車車体は横に均一な色）
        y_start = h // 5
        y_end = h * 4 // 5
        uniform_rows = 0
        total_rows = 0

        for y in range(y_start, y_end, max(1, (y_end - y_start) // 40)):
            samples = []
            for x in range(0, w, sample_step):
                samples.append(img.getpixel((min(x, w - 1), y)))
            if len(samples) < 5:
                continue
            total_rows += 1
            r_vals = [p[0] for p in samples]
            g_vals = [p[1] for p in samples]
            b_vals = [p[2] for p in samples]
            avg_range = (max(r_vals) - min(r_vals) + max(g_vals) - min(g_vals) + max(b_vals) - min(b_vals)) / 3
            if avg_range < 35:
                uniform_rows += 1

        if total_rows == 0:
            return False

        uniform_ratio = uniform_rows / total_rows
        if uniform_ratio > 0.55:
            logger.debug(f"電車判定: uniform={uniform_ratio:.2f} → 電車(均一帯)")
            return True

        # Check 2: ホーム検出 - 下部に暗い線路 + 黄色い安全線
        bottom_third = img.crop((0, h * 2 // 3, w, h))
        bt_pixels = list(bottom_third.getdata())
        dark_bottom = sum(1 for r, g, b in bt_pixels if (r + g + b) / 3 < 70) / len(bt_pixels)

        yellow_rows = 0
        for y in range(h // 4, h * 4 // 5, max(1, h // 25)):
            row_samples = [img.getpixel((min(x, w - 1), y)) for x in range(0, w, sample_step)]
            yellow = sum(1 for r, g, b in row_samples if r > 140 and g > 100 and b < 80)
            if len(row_samples) > 0 and yellow / len(row_samples) > 0.05:
                yellow_rows += 1

        if dark_bottom > 0.25 and yellow_rows >= 1:
            logger.debug(f"電車判定: dark_bt={dark_bottom:.2f} yellow={yellow_rows}rows → ホーム(線路+黄線)")
            return True

        logger.debug(f"電車判定: uniform={uniform_ratio:.2f} dark_bt={dark_bottom:.2f} yellow={yellow_rows} → OK")
        return False
    except Exception as e:
        logger.debug(f"電車判定エラー: {e}")
        return False


def _score_image_filename(title, station_name):
    """
    Wikipedia画像のファイル名をスコアリング。
    Noneを返したら完全拒否（ダウンロードしない）。
    """
    lower = title.lower()

    # 画像ファイルのみ
    if not any(ext in lower for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return None
    if '.svg' in lower or '.gif' in lower:
        return None

    # 完全拒否キーワード（電車・ホーム・地図等）
    reject = [
        'platform', 'ホーム', 'track', '線路', '軌道',
        'train', '電車', '列車', '車両', '系電車', '系気動車',
        'series',
        'interior', '改札', 'concourse', '構内', 'ticket', '券売',
        'fare gate', 'ticket gate',
        'map', 'diagram', 'logo', 'symbol', 'banner', 'icon', 'pictogram',
        'route', '路線', 'linemap',
        'aerial', 'panorama', 'skyline',
        'hotel', 'shrine', 'temple', 'department', 'museum',
        'ward office', 'city hall',
        'bus_', 'バス停', 'taxi', 'buswait',
        'familymart', 'lawson', 'seven-eleven', '7-eleven',
        'convenience', 'コンビニ', 'starbucks', 'mcdonalds',
        'disambig', 'commons-logo',
    ]
    if any(kw in lower for kw in reject):
        return None

    score = 0

    # 高スコアキーワード（駅舎外観の可能性が高い）
    prefer = [
        ('駅舎', 50), ('ekisha', 50), ('外観', 50),
        ('exterior', 40), ('facade', 40),
        ('entrance', 35), ('入口', 35), ('入り口', 35),
        ('南口', 30), ('北口', 30), ('東口', 30), ('西口', 30),
        ('south', 25), ('north', 25), ('east', 25), ('west', 25),
        ('exit', 25),
    ]
    for kw, pts in prefer:
        if kw in lower:
            score += pts

    # building は駅関連コンテキストがある場合のみ加点
    if 'building' in lower and ('station' in lower or 'sta' in lower or '駅' in lower):
        score += 40

    # 駅名がファイル名に含まれる → 関連性高い
    clean_name = re.sub(r'[\(（].+?[\)）]', '', station_name).strip()
    if clean_name in title:
        score += 20

    # "station", "sta", or "駅" in filename
    if 'station' in lower or '駅' in title:
        score += 10
    elif any(p in lower for p in [' sta ', ' sta.', '-sta-', '-sta.', '-sta_', '_sta-', '_sta.']):
        score += 8

    # 周辺エリア・商店街等の写真は減点（駅そのものでない可能性）
    area_keywords = [
        'area', 'dori', 'street', 'avenue', 'shopping', 'around', 'near',
        'bus terminal', 'bus center', 'busrotary', '商店', '通り', '周辺',
    ]
    for kw in area_keywords:
        if kw in lower:
            score -= 20
            break

    return score


def _get_wikipedia_image_urls(file_titles):
    """Wikipedia画像タイトルのリストからURLを一括取得"""
    if not file_titles:
        return {}

    results = {}
    for i in range(0, len(file_titles), 50):
        batch = file_titles[i:i + 50]
        params = {
            "action": "query",
            "format": "json",
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url",
        }
        try:
            resp = requests.get(
                "https://ja.wikipedia.org/w/api.php",
                params=params, headers=_HEADERS, timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                title = page.get("title", "")
                imageinfo = page.get("imageinfo", [])
                if imageinfo:
                    url = imageinfo[0].get("url", "")
                    if url:
                        results[title] = url
        except requests.RequestException as e:
            logger.debug(f"Wikipedia imageinfo APIエラー: {e}")
    return results


def _wikipedia_find_station_page(station_name):
    """
    Wikipedia日本語版で駅記事のページタイトルを特定。
    曖昧さ回避ページの場合、リンクから正しいページを探す。
    """
    base_title = f"{station_name}駅"

    # まず基本タイトルで画像一覧を取得
    params = {
        "action": "query",
        "format": "json",
        "titles": base_title,
        "prop": "images|links",
        "imlimit": "50",
        "pllimit": "50",
    }
    try:
        resp = requests.get(
            "https://ja.wikipedia.org/w/api.php",
            params=params, headers=_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Wikipedia APIエラー: {e}")
        return base_title, []

    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            return base_title, []

        images = page.get("images", [])
        image_titles = [img.get("title", "") for img in images if img.get("title", "")]

        # 画像が3枚以上あれば通常の記事ページ
        real_images = [t for t in image_titles
                       if not any(kw in t.lower() for kw in ['disambig', 'commons-logo', '.svg'])]
        if len(real_images) >= 2:
            return base_title, image_titles

        # 画像が少ない → 曖昧さ回避の可能性 → リンクから駅記事を探す
        logger.info(f"Wikipedia: {base_title} は曖昧さ回避の可能性、リンクを確認")
        links = page.get("links", [])
        candidates = []
        for link in links:
            link_title = link.get("title", "")
            if link_title.startswith(f"{station_name}駅") and "(" in link_title:
                candidates.append(link_title)

        if candidates:
            # 全候補の画像を一括取得し、最も画像が多いページを選択
            sub_params = {
                "action": "query",
                "format": "json",
                "titles": "|".join(candidates[:5]),
                "prop": "images",
                "imlimit": "50",
            }
            try:
                sub_resp = requests.get(
                    "https://ja.wikipedia.org/w/api.php",
                    params=sub_params, headers=_HEADERS, timeout=30,
                )
                sub_resp.raise_for_status()
                sub_data = sub_resp.json()
                sub_pages = sub_data.get("query", {}).get("pages", {})

                best_title = None
                best_images = []
                for sub_pid, sub_page in sub_pages.items():
                    if sub_pid == "-1":
                        continue
                    sub_title = sub_page.get("title", "")
                    sub_imgs = [img.get("title", "") for img in sub_page.get("images", [])
                                if img.get("title", "")]
                    if len(sub_imgs) > len(best_images):
                        best_title = sub_title
                        best_images = sub_imgs

                if best_title:
                    logger.info(f"Wikipedia: 曖昧さ回避 → {best_title} ({len(best_images)}画像)")
                    return best_title, best_images
            except requests.RequestException:
                pass

    return base_title, []


def _wikipedia_station_image(station_name, output_dir, safe_name):
    """
    Wikipedia日本語版の駅記事から駅舎外観写真を取得。
    記事内の全画像をファイル名でスコアリングし、最適な1枚を選択。
    曖昧さ回避ページにも対応。
    """
    # Step 1: 駅記事ページの特定と全画像ファイル名を取得
    page_title, all_images = _wikipedia_find_station_page(station_name)
    image_titles = [t for t in all_images if t]

    if not image_titles:
        logger.info(f"Wikipedia: 画像なし: {station_name}駅")
        return []

    # Step 2: ファイル名でスコアリング
    scored_images = []
    for title in image_titles:
        score = _score_image_filename(title, station_name)
        if score is not None:
            scored_images.append((title, score))

    if not scored_images:
        logger.info(f"Wikipedia: 適切な画像候補なし: {station_name}駅")
        return []

    scored_images.sort(key=lambda x: x[1], reverse=True)
    logger.info(f"Wikipedia: {station_name}駅 上位候補: {[(t.split(':')[-1][:30], s) for t, s in scored_images[:5]]}")

    # Step 3: 上位候補のURLを一括取得
    top_titles = [t for t, s in scored_images[:8]]
    url_map = _get_wikipedia_image_urls(top_titles)

    # Step 4: スコア順にダウンロード・品質チェック（スコア>0のみ）
    for title, filename_score in scored_images[:8]:
        if filename_score <= 0:
            logger.info(f"Wikipedia: 残り候補は低スコア(≤0)、Places APIにフォールバック")
            break
        image_url = url_map.get(title, "")
        if not image_url:
            continue

        lower_url = image_url.lower()
        if '.svg' in lower_url or '.gif' in lower_url:
            continue

        ext = ".png" if ".png" in lower_url else ".jpg"
        save_path = os.path.join(output_dir, f"{safe_name}_1{ext}")

        if _download_image(image_url, save_path):
            # 屋外判定
            if not _is_outdoor_photo(save_path):
                logger.info(f"Wikipedia: 屋内写真スキップ: {title}")
                os.remove(save_path)
                continue
            # 空撮判定
            if _is_aerial_photo(save_path):
                logger.info(f"Wikipedia: 空撮写真スキップ: {title}")
                os.remove(save_path)
                continue
            # 電車/ホーム判定
            if _is_train_or_platform_photo(save_path):
                logger.info(f"Wikipedia: 電車/ホーム写真スキップ: {title}")
                os.remove(save_path)
                continue

            logger.info(f"Wikipedia: 駅舎外観取得成功: {station_name}駅 ({title})")
            return [save_path]

        time.sleep(REQUEST_DELAY)

    logger.info(f"Wikipedia: 駅舎外観写真なし: {station_name}駅")
    return []


def _wikimedia_commons_search(station_name, output_dir, safe_name,
                              search_queries=None, station_type=None):
    """
    Wikimedia Commons検索で写真を探す。
    station_type="terminal" の場合、駅関連の写真を追加で拒否する。
    """
    if search_queries is None:
        search_queries = [
            f"{station_name}駅 駅舎",
            f"{station_name}駅 外観",
            f"{station_name} station building",
        ]

    # ターミナル駅: 駅の写真ではなくランドマーク写真が欲しい → 駅関連を追加拒否
    terminal_reject = [
        'station', '駅', 'eki', 'gate', '改札', '駅舎', 'platform', 'ホーム',
        'concourse', '構内', 'ticket', 'train', '電車', '列車',
    ] if station_type == "terminal" else []

    for query in search_queries:
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srnamespace": 6,
                    "srlimit": 15,
                    "format": "json",
                },
                headers=_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.debug(f"Commons検索エラー: {e}")
            continue

        results = data.get("query", {}).get("search", [])
        if not results:
            continue

        # スコアリングして最適な候補を選択
        scored = []
        for r in results:
            title = r.get("title", "")
            # ターミナル駅: 駅関連ファイル名を拒否
            if terminal_reject:
                lower_title = title.lower()
                if any(kw in lower_title for kw in terminal_reject):
                    logger.debug(f"Commons: ターミナル駅 駅関連拒否: {title}")
                    continue
            score = _score_image_filename(title, station_name)
            if score is not None and score >= 0:
                scored.append((title, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            continue

        # URL取得してダウンロード
        top_titles = [t for t, s in scored[:5]]
        url_map = _get_wikipedia_image_urls(top_titles)

        for title, filename_score in scored[:5]:
            # 商用利用可能なライセンスかチェック
            if not _is_commercial_license(title):
                continue

            image_url = url_map.get(title, "")
            if not image_url:
                continue
            lower_url = image_url.lower()
            if '.svg' in lower_url or '.gif' in lower_url:
                continue

            ext = ".png" if ".png" in lower_url else ".jpg"
            save_path = os.path.join(output_dir, f"{safe_name}_1{ext}")

            if _download_image(image_url, save_path):
                if not _is_outdoor_photo(save_path):
                    os.remove(save_path)
                    continue
                if _is_aerial_photo(save_path):
                    os.remove(save_path)
                    continue
                if _is_train_or_platform_photo(save_path):
                    os.remove(save_path)
                    continue

                logger.info(f"Commons: 駅舎外観取得成功 (商用利用可): {station_name}駅 ({title})")
                return [save_path]

            time.sleep(REQUEST_DELAY)

    logger.info(f"Commons: 駅舎外観写真なし: {station_name}駅")
    return []


def _places_search_station(station_name, places_query=None):
    """
    Google Places API (New) Text Search で駅を検索し、写真リファレンスを取得。

    Returns:
        list[dict]: 写真メタデータのリスト。各要素は
            {"name": "places/.../photos/...", "widthPx": int, "heightPx": int}
    """
    if places_query is None:
        places_query = f"{station_name}駅 駅舎 外観"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.photos",
    }
    body = {
        "textQuery": places_query,
        "languageCode": "ja",
        "maxResultCount": 1,
    }

    try:
        resp = requests.post(
            PLACES_TEXT_SEARCH_URL,
            json=body,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Places Text Search APIエラー: {e}")
        return []

    places = data.get("places", [])
    if not places:
        logger.info(f"Places API: 駅が見つかりません: {station_name}")
        return []

    photos = places[0].get("photos", [])
    logger.info(f"Places API: {station_name}駅 → {len(photos)}枚の写真候補")
    return photos[:PLACES_PHOTO_CANDIDATES]


def _score_places_photo(photo_meta, rank):
    """
    写真メタデータにスコアを付ける。横長・高解像度・上位を優先。

    Args:
        photo_meta: {"widthPx": int, "heightPx": int, ...}
        rank: Google推薦順位 (0始まり)

    Returns:
        int: スコア（高いほど良い）
    """
    score = 0
    w = photo_meta.get("widthPx", 0)
    h = photo_meta.get("heightPx", 0)

    # アスペクト比スコア
    if h > 0:
        aspect = w / h
        if 1.2 <= aspect <= 2.5:
            score += 30   # 横長（駅舎外観に多い）
        elif 1.0 <= aspect < 1.2:
            score += 10   # ほぼ正方形
        else:
            score -= 10   # 縦長

    # 解像度スコア
    if w >= 1200:
        score += 15
    elif w >= 800:
        score += 10

    # Google推薦順位スコア（上位ほど高い）
    rank_bonus = max(0, 20 - rank * 5)
    score += rank_bonus

    return score


def _download_places_photo(photo_name, save_path):
    """
    Places API (New) から写真をダウンロードして保存。

    Args:
        photo_name: 写真リソース名 (e.g. "places/.../photos/...")
        save_path: 保存先パス

    Returns:
        bool: 成功したらTrue
    """
    url = PLACES_PHOTO_URL_TEMPLATE.format(photo_name=photo_name)
    params = {
        "maxWidthPx": PLACES_PHOTO_MAX_WIDTH,
        "key": GOOGLE_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type:
            logger.debug(f"Places Photo: 画像でないコンテンツ: {content_type}")
            return False

        image_data = resp.content
        if not _validate_image_size(image_data):
            return False

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(image_data)
        logger.info(f"Places Photo 保存: {save_path}")
        return True
    except requests.RequestException as e:
        logger.debug(f"Places Photo ダウンロード失敗: {e}")
        return False


def search_places_images(station_name, output_dir, max_images=IMAGES_PER_STATION, places_query=None):
    """
    Google Places API (New) で駅画像を取得。
    写真候補をスコアリングして最適な写真を選択。

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数
        places_query: 検索クエリ（駅タイプ別）

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        logger.warning("Google API キーが未設定です。Places APIをスキップします。")
        return []

    photos = _places_search_station(station_name, places_query=places_query)
    if not photos:
        return []

    # スコアリングでソート（高スコア順）
    scored = [(photo, _score_places_photo(photo, i)) for i, photo in enumerate(photos)]
    scored.sort(key=lambda x: x[1], reverse=True)

    safe_name = _sanitize_filename(station_name)
    saved_paths = []

    # 候補をダウンロードして品質判定し、最良の1枚を選ぶ
    best_path = None
    best_score = -999
    temp_idx = 0
    tried = 0

    for photo, meta_score in scored:
        if best_path and best_score > 80 and tried >= 5:
            break  # 十分良い写真が見つかり、5枚以上試した

        photo_name = photo.get("name", "")
        if not photo_name:
            continue

        temp_idx += 1
        filename = f"{safe_name}_tmp_{temp_idx}.jpg"
        save_path = os.path.join(output_dir, filename)

        if not _download_places_photo(photo_name, save_path):
            continue

        tried += 1
        # 電車/ホーム判定（屋内外問わず最優先で拒否）
        if _is_train_or_platform_photo(save_path):
            logger.info(f"Places Photo: 電車/ホーム写真スキップ: {photo_name}")
            os.remove(save_path)
            continue
        # 屋外判定
        outdoor = _is_outdoor_photo(save_path)
        if not outdoor:
            logger.info(f"Places Photo: 屋内写真スキップ: {photo_name}")
            os.remove(save_path)
            continue
        # 空撮判定
        if _is_aerial_photo(save_path):
            logger.info(f"Places Photo: 空撮写真スキップ: {photo_name}")
            os.remove(save_path)
            continue
        final_score = meta_score + 40
        logger.debug(f"Places Photo スコア={meta_score}→{final_score}: {photo_name}")

        if final_score > best_score:
            # 前の候補を削除
            if best_path and os.path.exists(best_path):
                os.remove(best_path)
            best_path = save_path
            best_score = final_score
        else:
            os.remove(save_path)

        time.sleep(REQUEST_DELAY)

    saved_paths = []
    if best_path:
        # 最終ファイル名にリネーム
        final_path = os.path.join(output_dir, f"{safe_name}_1.jpg")
        if best_path != final_path:
            os.rename(best_path, final_path)
        saved_paths.append(final_path)

    logger.info(f"Places API: {station_name} → {len(saved_paths)}枚取得 (スコア={best_score})")
    return saved_paths


def fetch_station_images(station_name, output_dir, max_images=IMAGES_PER_STATION,
                         lat=None, lon=None, railways=None):
    """
    駅画像を取得するメインエントリポイント

    駅タイプ（terminal/subway/local）を判定し、最適な検索クエリを生成。
    フォールバック順序（すべて商用利用可能）:
      1. Wikipedia記事画像（ファイル名スコアリング＋品質チェック）
      2. Wikimedia Commons検索（商用利用可ライセンスのみ）
      3. Flickr検索（商用利用可ライセンスのみ）

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数
        lat: 駅の緯度（未使用、互換性のため残す）
        lon: 駅の経度（未使用、互換性のため残す）
        railways: 路線名リスト（地下鉄判定用）

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    # 駅名の正規化（「駅」の二重付加を防止）
    if station_name.endswith("駅"):
        station_name = station_name[:-1]

    safe_name = _sanitize_filename(station_name)

    # 駅タイプ判定 → 検索クエリ生成
    station_type = _classify_station_type(station_name, railways=railways)
    queries = _generate_search_queries(station_name, station_type)

    if station_type == "terminal":
        # ターミナル駅: 街のランドマーク・象徴的風景を優先
        # Wikipedia駅記事には駅舎・改札等の写真しかないのでスキップ
        logger.info(f"ターミナル駅: ランドマーク検索: {station_name} (Wikipedia駅記事スキップ)")

        # 1. Wikimedia Commonsでランドマーク検索
        paths = _wikimedia_commons_search(
            station_name, output_dir, safe_name,
            search_queries=queries["commons_queries"],
            station_type="terminal",
        )
        if paths:
            return paths

        # 2. Flickr検索（商用利用可能ライセンスのみ）
        logger.info(f"Flickrでランドマーク検索: {station_name}")
        paths = _flickr_search_station(
            station_name, output_dir, safe_name,
            station_type="terminal",
        )
        if paths:
            return paths
    else:
        # subway / local: Wikipedia駅記事 → Commons → Flickr
        # 1. Wikipedia記事の画像（ファイル名スコアリング＋品質チェック）
        logger.info(f"Wikipedia記事画像を検索: {station_name}駅")
        paths = _wikipedia_station_image(station_name, output_dir, safe_name)
        if paths:
            return paths

        # 2. Wikimedia Commons検索（駅タイプ別クエリ）
        logger.info(f"Wikimedia Commonsで画像検索: {station_name}駅 (type={station_type})")
        paths = _wikimedia_commons_search(
            station_name, output_dir, safe_name,
            search_queries=queries["commons_queries"],
        )
        if paths:
            return paths

        # 3. Flickr検索（商用利用可能ライセンスのみ）
        logger.info(f"Flickrで画像検索: {station_name}駅 (type={station_type})")
        paths = _flickr_search_station(
            station_name, output_dir, safe_name,
            station_type=station_type,
        )
        if paths:
            return paths

    logger.info(f"画像取得失敗: {station_name}駅")
    return []
