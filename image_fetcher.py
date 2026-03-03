"""
画像取得モジュール - Wikipedia記事画像 + Google Places API (New)
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
    画像上部1/4の明るさと青/白の割合で空の有無を推定する。
    屋内写真（改札・コンコース等）を除外するために使用。
    """
    try:
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        # 上部1/4を分析
        top_region = img.crop((0, 0, w, h // 4))
        pixels = list(top_region.getdata())
        total = len(pixels)
        if total == 0:
            return True

        sky_count = 0
        bright_count = 0
        for r, g, b in pixels:
            brightness = (r + g + b) / 3
            # 空っぽい色: 青系 or 明るい白/グレー
            if (b > 150 and b > r and b > g - 20) or brightness > 200:
                sky_count += 1
            if brightness > 120:
                bright_count += 1

        sky_ratio = sky_count / total
        bright_ratio = bright_count / total

        is_outdoor = sky_ratio > 0.3 or bright_ratio > 0.6
        logger.debug(f"屋外判定: sky={sky_ratio:.2f} bright={bright_ratio:.2f} → {'屋外' if is_outdoor else '屋内'}")
        return is_outdoor
    except Exception as e:
        logger.debug(f"屋外判定エラー: {e}")
        return True  # エラー時は許可


def _is_station_image_filename(filename, station_name):
    """
    Wikipediaの画像ファイル名が駅舎写真らしいか判定。
    駅名・Station・Sta・駅 等を含むファイル名はOK。
    周辺施設名のみのファイル名はNG。
    """
    lower = filename.lower()
    clean_name = re.sub(r'[\(（〈\[【].+?[\)）〉\]】]', '', station_name).strip()

    # 駅関連キーワードが含まれていればOK
    station_keywords = ['station', 'sta.', 'sta-', 'sta_', 'eki', '駅']
    if any(kw in lower for kw in station_keywords):
        return True

    # 駅名のローマ字がファイル名に含まれる場合もOK（例: Higashikanagawa）
    # ただし station キーワードも一緒にあるべき → 上で処理済み

    # 明らかに駅でない画像の除外キーワード
    reject_keywords = [
        'aerial', 'panorama', 'skyline', 'rise', 'tower', 'building',
        'mitsukoshi', 'department', 'hotel', 'shrine', 'temple',
        'map', 'diagram', 'logo', 'symbol', 'banner',
    ]
    if any(kw in lower for kw in reject_keywords):
        logger.info(f"Wikipedia: 駅舎外観でない画像をスキップ: {filename}")
        return False

    # キーワードなしでも、判定不能な場合は許可（多くの駅画像はファイル名が曖昧）
    return True


def _wikipedia_station_image(station_name, output_dir, safe_name):
    """
    Wikipedia日本語版の駅記事からメイン画像（infobox画像）を取得。
    ファイル名で駅舎外観かどうかをフィルタリングする。
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": f"{station_name}駅",
        "prop": "pageimages",
        "piprop": "original",
    }
    try:
        resp = requests.get(
            "https://ja.wikipedia.org/w/api.php",
            params=params,
            headers=_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Wikipedia APIエラー: {e}")
        return []

    pages = data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            continue
        original = page.get("original", {})
        image_url = original.get("source", "")
        if not image_url:
            continue

        # SVG/GIFを除外
        lower_url = image_url.lower()
        if ".svg" in lower_url or ".gif" in lower_url:
            logger.debug(f"Wikipedia: SVG/GIFスキップ: {image_url}")
            continue

        # ファイル名で駅舎外観写真かフィルタリング
        img_filename = image_url.split("/")[-1]
        if not _is_station_image_filename(img_filename, station_name):
            continue

        ext = ".png" if ".png" in lower_url else ".jpg"
        filename = f"{safe_name}_1{ext}"
        save_path = os.path.join(output_dir, filename)

        if _download_image(image_url, save_path):
            logger.info(f"Wikipedia記事画像取得成功: {station_name}駅")
            return [save_path]

    logger.info(f"Wikipedia記事画像なし（外観写真なし）: {station_name}駅")
    return []


def _places_search_station(station_name):
    """
    Google Places API (New) Text Search で駅を検索し、写真リファレンスを取得。

    Returns:
        list[dict]: 写真メタデータのリスト。各要素は
            {"name": "places/.../photos/...", "widthPx": int, "heightPx": int}
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.photos",
    }
    body = {
        "textQuery": f"{station_name}駅",
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


def search_places_images(station_name, output_dir, max_images=IMAGES_PER_STATION):
    """
    Google Places API (New) で駅画像を取得。
    写真候補をスコアリングして最適な写真を選択。

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        logger.warning("Google API キーが未設定です。Places APIをスキップします。")
        return []

    photos = _places_search_station(station_name)
    if not photos:
        return []

    # スコアリングでソート（高スコア順）
    scored = [(photo, _score_places_photo(photo, i)) for i, photo in enumerate(photos)]
    scored.sort(key=lambda x: x[1], reverse=True)

    safe_name = _sanitize_filename(station_name)
    saved_paths = []

    # 候補をダウンロードして屋外判定し、最良の1枚を選ぶ
    best_path = None
    best_score = -999
    temp_idx = 0

    for photo, meta_score in scored:
        if best_path and best_score > 50:
            break  # 十分良い写真が見つかった

        photo_name = photo.get("name", "")
        if not photo_name:
            continue

        temp_idx += 1
        filename = f"{safe_name}_tmp_{temp_idx}.jpg"
        save_path = os.path.join(output_dir, filename)

        if not _download_places_photo(photo_name, save_path):
            continue

        # 屋外判定でスコア補正
        outdoor = _is_outdoor_photo(save_path)
        final_score = meta_score + (40 if outdoor else -30)
        logger.debug(f"Places Photo スコア={meta_score}→{final_score} ({'屋外' if outdoor else '屋内'}): {photo_name}")

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


def fetch_station_images(station_name, output_dir, max_images=IMAGES_PER_STATION):
    """
    駅画像を取得するメインエントリポイント

    フォールバック順序（商用利用OKのソースのみ）:
      1. Wikipedia記事画像（無料・CC BY-SA）
      2. Google Places API New（商用OK・スコアリングで外観優先）

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    safe_name = _sanitize_filename(station_name)

    # 1. Wikipedia記事のメイン画像（無料・駅舎外観が多い）
    logger.info(f"Wikipedia記事画像を検索: {station_name}駅")
    paths = _wikipedia_station_image(station_name, output_dir, safe_name)
    if paths:
        return paths

    # 2. Google Places API (New)（商用利用OK）
    logger.info(f"Places APIで画像検索: {station_name}駅")
    paths = search_places_images(station_name, output_dir, max_images)
    if paths:
        return paths

    logger.info(f"画像取得失敗: {station_name}駅（Wikipedia・Places API ともに取得できず）")
    return []
