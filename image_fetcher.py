"""
画像取得モジュール - Wikipedia記事画像 + Google Custom Search API + Wikimediaフォールバック
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
    GOOGLE_CSE_ID,
    WIKIMEDIA_API_URL,
    MIN_IMAGE_WIDTH,
    IMAGES_PER_STATION,
    IMAGE_SEARCH_QUERY,
    IMAGE_SEARCH_QUERY_FALLBACK,
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
    """保管庫に最新の1枚だけ上書き保存する。"""
    cache_dir = os.path.join(IMAGE_CACHE_DIR, _sanitize_filename(station_name))
    os.makedirs(cache_dir, exist_ok=True)
    # 古い画像を全削除（meta.jsonは保持）
    for old in os.listdir(cache_dir):
        if old == "meta.json":
            continue
        old_path = os.path.join(cache_dir, old)
        if os.path.isfile(old_path):
            os.remove(old_path)
    # 1枚だけ保存
    if image_paths:
        safe_name = _sanitize_filename(station_name)
        src = image_paths[0]
        ext = os.path.splitext(src)[1] or ".jpg"
        dst = os.path.join(cache_dir, f"{safe_name}_1{ext}")
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


def _wikipedia_station_image(station_name, output_dir, safe_name):
    """
    Wikipedia日本語版の駅記事からメイン画像（infobox画像）を取得。
    駅記事のリード画像は駅舎外観写真であることが多い。
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

        ext = ".png" if ".png" in lower_url else ".jpg"
        filename = f"{safe_name}_1{ext}"
        save_path = os.path.join(output_dir, filename)

        if _download_image(image_url, save_path):
            logger.info(f"Wikipedia記事画像取得成功: {station_name}駅")
            return [save_path]

    logger.info(f"Wikipedia記事画像なし: {station_name}駅")
    return []


def _is_relevant_result(item, station_name):
    """検索結果が駅に関連しているか判定"""
    import re
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    context = item.get("image", {}).get("contextLink", "")
    text = f"{title} {snippet} {context}"

    # カッコ除去した駅名でもチェック
    clean_name = re.sub(r'[\(（〈\[【].+?[\)）〉\]】]', '', station_name).strip()
    names_to_check = {station_name, clean_name, f"{station_name}駅", f"{clean_name}駅"}

    # 駅名が含まれていればOK
    name_found = any(n in text for n in names_to_check if n)
    if name_found:
        return True

    # 駅名がテキストにない場合は不採用（汎用キーワードだけでは通さない）
    return False


def _google_search_once(query, station_name, output_dir, max_images):
    """Google Custom Search APIで1クエリ分を検索・保存"""
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "searchType": "image",
        "imgType": "photo",
        "lr": "lang_ja",
        "num": 10,
    }

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        logger.error(f"Google検索APIエラー: {e}")
        return []

    items = results.get("items", [])
    if not items:
        return []

    saved_paths = []
    safe_name = _sanitize_filename(station_name)

    for i, item in enumerate(items):
        if len(saved_paths) >= max_images:
            break

        # 関連性チェック: 駅名がタイトル/スニペットに含まれない画像はスキップ
        if not _is_relevant_result(item, station_name):
            logger.debug(f"関連性低: {item.get('title', '')}")
            continue

        # サイズチェック: アイコン/ロゴ等の小さい画像やアスペクト比が極端な画像を除外
        img_meta = item.get("image", {})
        img_w = int(img_meta.get("width", 0))
        img_h = int(img_meta.get("height", 0))
        if img_w > 0 and img_h > 0:
            aspect = max(img_w, img_h) / min(img_w, img_h) if min(img_w, img_h) > 0 else 99
            # 正方形すぎる画像（アイコン/ロゴ）かつ小さい → スキップ
            if img_w < 500 and img_h < 500 and aspect < 1.3:
                logger.debug(f"アイコン除外 ({img_w}x{img_h}): {item.get('title', '')}")
                continue
            # 極端に小さい画像はスキップ
            if max(img_w, img_h) < 300:
                logger.debug(f"小画像除外 ({img_w}x{img_h}): {item.get('title', '')}")
                continue

        image_url = item.get("link", "")
        if not image_url:
            continue

        ext = ".jpg"
        if ".png" in image_url.lower():
            ext = ".png"

        filename = f"{safe_name}_{len(saved_paths) + 1}{ext}"
        save_path = os.path.join(output_dir, filename)

        if _download_image(image_url, save_path):
            saved_paths.append(save_path)

        time.sleep(REQUEST_DELAY)

    return saved_paths


def search_google_images(station_name, output_dir, max_images=IMAGES_PER_STATION):
    """
    Google Custom Search APIで駅画像を検索・保存
    メインクエリ → フォールバッククエリ → Wikimedia の順で試行

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    if GOOGLE_API_KEY == "YOUR_GOOGLE_API_KEY_HERE":
        logger.warning("Google API キーが未設定です。Wikimediaにフォールバックします。")
        return search_wikimedia_images(station_name, output_dir, max_images)

    # 駅名からカッコ付きサフィックスを除去（検索精度向上）
    # 例: "二重橋前〈丸の内〉" → "二重橋前", "赤坂(東京)" → "赤坂"
    import re
    clean_name = re.sub(r'[\(（〈\[【].+?[\)）〉\]】]', '', station_name).strip()
    search_name = clean_name if clean_name else station_name

    # 1. メインクエリ: 駅舎外観
    query1 = IMAGE_SEARCH_QUERY.format(station_name=search_name)
    logger.info(f"Google画像検索（メイン）: {query1}")
    paths = _google_search_once(query1, search_name, output_dir, max_images)
    if paths:
        return paths

    # 2. フォールバッククエリ: 入口
    query2 = IMAGE_SEARCH_QUERY_FALLBACK.format(station_name=search_name)
    logger.info(f"Google画像検索（フォールバック）: {query2}")
    paths = _google_search_once(query2, search_name, output_dir, max_images)
    if paths:
        return paths

    # 3. 駅名のみのシンプルクエリ
    query3 = f'"{search_name}駅"'
    logger.info(f"Google画像検索（シンプル）: {query3}")
    paths = _google_search_once(query3, search_name, output_dir, max_images)
    if paths:
        return paths

    # 4. Wikimedia
    logger.info(f"Google検索結果なし。Wikimediaにフォールバック: {search_name}")
    return search_wikimedia_images(search_name, output_dir, max_images)


def _wikimedia_search(query, max_images, output_dir, safe_name, start_idx=0):
    """Wikimedia Commons APIで1クエリ分の画像検索・保存"""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": query,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
    }

    try:
        resp = requests.get(WIKIMEDIA_API_URL, params=params, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Wikimedia APIエラー: {e}")
        return []

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return []

    saved_paths = []
    for page_id, page in pages.items():
        if len(saved_paths) >= max_images:
            break

        imageinfo = page.get("imageinfo", [{}])
        if not imageinfo:
            continue
        info = imageinfo[0]

        width = info.get("width", 0)
        if width < MIN_IMAGE_WIDTH:
            continue

        mime = info.get("mime", "")
        if mime not in ("image/jpeg", "image/png"):
            continue

        image_url = info.get("url", "")
        if not image_url:
            continue

        ext = ".jpg" if "jpeg" in mime else ".png"
        filename = f"{safe_name}_{start_idx + len(saved_paths) + 1}{ext}"
        save_path = os.path.join(output_dir, filename)

        if _download_image(image_url, save_path):
            saved_paths.append(save_path)

        time.sleep(REQUEST_DELAY)

    return saved_paths


def search_wikimedia_images(station_name, output_dir, max_images=IMAGES_PER_STATION):
    """
    Wikimedia Commons APIで駅画像を検索・保存（フォールバック）
    日本語名 → 「駅名 station」の順でフォールバック検索
    """
    safe_name = _sanitize_filename(station_name)

    # 1. 「駅名+駅」で検索
    queries = [f"{station_name}駅", f"{station_name} station", station_name]
    saved_paths = []

    for query in queries:
        if len(saved_paths) >= max_images:
            break
        logger.info(f"Wikimedia画像検索: {query}")
        remaining = max_images - len(saved_paths)
        paths = _wikimedia_search(query, remaining, output_dir, safe_name, len(saved_paths))
        saved_paths.extend(paths)

    logger.info(f"Wikimedia: {station_name} → {len(saved_paths)}枚取得")
    return saved_paths


def fetch_station_images(station_name, output_dir, max_images=IMAGES_PER_STATION):
    """
    駅画像を取得するメインエントリポイント
    Google Custom Search → Wikipedia記事画像 → Wikimedia の順で試行

    Args:
        station_name: 駅名
        output_dir: 保存先ディレクトリ
        max_images: 最大取得枚数

    Returns:
        list[str]: 保存された画像パスのリスト
    """
    safe_name = _sanitize_filename(station_name)

    # 1. Google Custom Search（高品質・最新の写真が多い）
    if GOOGLE_API_KEY != "YOUR_GOOGLE_API_KEY_HERE":
        paths = search_google_images(station_name, output_dir, max_images)
        if paths:
            return paths

    # 2. Wikipedia記事のメイン画像
    logger.info(f"Wikipedia記事画像を検索: {station_name}駅")
    paths = _wikipedia_station_image(station_name, output_dir, safe_name)
    if paths:
        return paths

    # 3. Wikimedia Commons
    return search_wikimedia_images(station_name, output_dir, max_images)
