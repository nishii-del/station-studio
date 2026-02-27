"""
市区別モード - 指定市区内の主要駅リストと画像を取得
Overpass API (OpenStreetMap) を使用
"""
import json
import os
import re
import logging

import requests

from image_fetcher import fetch_station_images
from config import OVERPASS_API_URL, CITY_OUTPUT_DIR
from transport_api import fetch_rail_graph

logger = logging.getLogger("store-traffic")


def _sanitize_filename(name):
    """ファイル名として安全な文字列に変換"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def fetch_stations_in_city(prefecture, city):
    """
    Overpass API で指定市区内の鉄道駅を取得

    Args:
        prefecture: 都道府県名（例: "東京都"）
        city: 市区町村名（例: "渋谷区"）

    Returns:
        list[str]: 駅名リスト
    """
    logger.info(f"Overpass APIで {prefecture}{city} の駅を検索中...")

    # Overpass QL クエリ
    query = f"""
    [out:json][timeout:60];
    area["name"="{city}"]["admin_level"~"[78]"]->.a;
    (
      node["railway"="station"](area.a);
      node["railway"="halt"](area.a);
    );
    out body;
    """

    try:
        resp = requests.post(
            OVERPASS_API_URL,
            data={"data": query},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"Overpass APIエラー: {e}")
        # フォールバック: 都道府県名も含めて再検索
        return _fetch_stations_fallback(prefecture, city)

    elements = data.get("elements", [])
    if not elements:
        logger.info("結果なし。フォールバック検索を試行...")
        return _fetch_stations_fallback(prefecture, city)

    # 駅名を抽出（重複排除）
    stations = []
    seen = set()
    for elem in elements:
        tags = elem.get("tags", {})
        name = tags.get("name", "")
        if name and name not in seen:
            # 「駅」が付いていたら除去（統一のため）
            clean_name = name.rstrip("駅")
            if clean_name not in seen:
                stations.append(clean_name)
                seen.add(clean_name)

    logger.info(f"{prefecture}{city}: {len(stations)}駅 検出")
    return stations


def _fetch_stations_fallback(prefecture, city):
    """
    フォールバック: 都道府県+市区名で検索
    """
    logger.info(f"フォールバック検索: {prefecture} {city}")

    query = f"""
    [out:json][timeout:60];
    area["name"="{prefecture}"]->.pref;
    area["name"="{city}"](area.pref)->.a;
    (
      node["railway"="station"](area.a);
      node["railway"="halt"](area.a);
    );
    out body;
    """

    try:
        resp = requests.post(
            OVERPASS_API_URL,
            data={"data": query},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error(f"フォールバック検索エラー: {e}")
        return []

    elements = data.get("elements", [])
    stations = []
    seen = set()
    for elem in elements:
        tags = elem.get("tags", {})
        name = tags.get("name", "")
        if name and name not in seen:
            clean_name = name.rstrip("駅")
            if clean_name not in seen:
                stations.append(clean_name)
                seen.add(clean_name)

    logger.info(f"フォールバック結果: {len(stations)}駅")
    return stations


def _find_stations_by_bbox(prefecture, city):
    """
    Nominatim + 鉄道グラフキャッシュで市区内の駅を取得（Overpass不要）
    """
    logger.info(f"Nominatim + キャッシュで {prefecture}{city} の駅を検索中...")
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{prefecture}{city}", "format": "json", "limit": 1},
            headers={"User-Agent": "StationStudio/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        logger.error(f"Nominatimエラー: {e}")
        return []

    if not results:
        logger.warning(f"Nominatimで {prefecture}{city} が見つかりません")
        return []

    bbox = results[0]["boundingbox"]  # [lat_min, lat_max, lon_min, lon_max]
    lat_min, lat_max = float(bbox[0]), float(bbox[1])
    lon_min, lon_max = float(bbox[2]), float(bbox[3])

    _, _, station_coords = fetch_rail_graph()

    stations = []
    seen = set()
    for name, coords in station_coords.items():
        if name in seen:
            continue
        lat, lon = coords.get("lat", 0), coords.get("lon", 0)
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            stations.append(name)
            seen.add(name)

    logger.info(f"Nominatim+キャッシュ結果: {len(stations)}駅")
    return stations


def fetch_passenger_count(station_name):
    """
    Wikipedia日本語版から駅の乗降客数を全社合算で取得。
    乗降人員はそのまま、乗車人員は×2して乗降換算。

    Args:
        station_name: 駅名（「駅」なし）

    Returns:
        dict: {"passengers": int|None, "passenger_label": str|None}
    """
    page_title = f"{station_name}駅"
    try:
        resp = requests.get(
            "https://ja.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": page_title,
                "prop": "revisions",
                "rvprop": "content",
                "rvlimit": 1,
                "format": "json",
            },
            headers={"User-Agent": "StationStudio/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.debug(f"Wikipedia取得失敗 ({page_title}): {e}")
        return {"passengers": None, "passenger_label": None}

    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1":
            break
        revs = page.get("revisions", [])
        if not revs:
            break
        wikitext = revs[0].get("*", "")

        total = 0
        found = False
        for label in ("乗降人員", "乗車人員"):
            multiplier = 1 if label == "乗降人員" else 2
            for m in re.finditer(rf"\|\s*{label}\s*=\s*(.+)", wikitext):
                line = m.group(1)
                pipe_pos = line.find("|")
                if pipe_pos >= 0:
                    line = line[:pipe_pos]
                # refタグ・マークアップ除去
                line = re.sub(r"<ref[^>]*/>", "", line)
                line = re.sub(r"<ref[^>]*>.*?</ref>", "", line, flags=re.DOTALL)
                line = re.sub(r"<br\s*/?>", " ", line)
                line = line.replace("'''", "")
                line = re.sub(r"（[^）]*）", " ", line)
                line = re.sub(r"\{\{[^}]*\}\}", "", line)
                # 「数字+人」パターン
                numbers = re.findall(r"([\d,]+)\s*人", line)
                if numbers:
                    for n in numbers:
                        v = int(n.replace(",", ""))
                        if v > 100:
                            total += v * multiplier
                            found = True
                    continue
                # 「人」なし — 3桁以上の数字
                numbers2 = re.findall(r"([\d,]{3,})", line)
                for n in numbers2:
                    v = int(n.replace(",", ""))
                    if v > 100:
                        total += v * multiplier
                        found = True

        if found:
            logger.info(f"{page_title}: 全社合算乗降人員 = {total:,}")
            return {"passengers": total, "passenger_label": "乗降人員（全社合算）"}

    logger.debug(f"{page_title}: 乗降客数データなし")
    return {"passengers": None, "passenger_label": None}


def _rank_stations_by_popularity(station_names, top_n=3):
    """
    鉄道グラフの乗り入れ路線数で駅をランキングし上位N件を返す

    Args:
        station_names: Overpassで取得した駅名リスト
        top_n: 上位何件を返すか

    Returns:
        list[dict]: [{"name": str, "line_count": int, "lat": float|None, "lon": float|None}, ...]
    """
    station_to_railways, _railway_stations, station_coords = fetch_rail_graph()

    ranked = []
    for name in station_names:
        railways_list = sorted(station_to_railways.get(name, set()))
        line_count = len(railways_list)
        coords = station_coords.get(name, {})
        ranked.append({
            "name": name,
            "line_count": line_count,
            "railways": railways_list,
            "lat": coords.get("lat"),
            "lon": coords.get("lon"),
        })

    # 路線数で降順ソート（同数なら元の順序を維持）
    ranked.sort(key=lambda x: x["line_count"], reverse=True)

    top = ranked[:top_n]
    logger.info(f"上位{top_n}駅: {[(s['name'], s['line_count']) for s in top]}")
    return top


def run_city_mode(prefecture, city):
    """
    市区別モード実行

    Args:
        prefecture: 都道府県名（例: "東京都"）
        city: 市区町村名（例: "渋谷区"）

    Returns:
        dict: 結果データ
    """
    logger.info(f"=== 市区別モード開始 ===")
    logger.info(f"対象: {prefecture} {city}")

    # 出力ディレクトリ準備
    safe_pref = _sanitize_filename(prefecture)
    safe_city = _sanitize_filename(city)
    output_subdir = os.path.join(CITY_OUTPUT_DIR, f"{safe_pref}_{safe_city}")
    os.makedirs(output_subdir, exist_ok=True)

    # 1. 市区内の全駅リストを取得
    station_names = fetch_stations_in_city(prefecture, city)
    if not station_names:
        # Overpass失敗時: Nominatim + 鉄道グラフキャッシュで検索
        station_names = _find_stations_by_bbox(prefecture, city)
    if not station_names:
        logger.warning("駅が見つかりませんでした")
        return None

    total_found = len(station_names)
    logger.info(f"取得駅数: {total_found}駅")

    # 2. 乗り入れ路線数で上位5駅を選定
    top_stations = _rank_stations_by_popularity(station_names, top_n=5)

    # 3. 上位5駅の画像を取得
    stations_data = []

    for i, st_info in enumerate(top_stations):
        station_name = st_info["name"]
        logger.info(f"[{i+1}/{len(top_stations)}] {station_name} の画像を取得中...")

        image_paths = fetch_station_images(station_name, output_subdir)

        # 相対パスに変換
        rel_paths = [os.path.relpath(p, os.path.dirname(output_subdir)) for p in image_paths]

        # Wikipedia乗降客数を取得
        pax = fetch_passenger_count(station_name)

        station_entry = {
            "name": f"{station_name}駅",
            "line_count": st_info["line_count"],
            "railways": st_info.get("railways", []),
            "lat": st_info["lat"],
            "lon": st_info["lon"],
            "image_path": rel_paths,
            "passengers": pax["passengers"],
            "passenger_label": pax["passenger_label"],
        }
        stations_data.append(station_entry)

    # 4. JSON保存
    result = {
        "prefecture": prefecture,
        "city": city,
        "total_stations_found": total_found,
        "total_stations": len(stations_data),
        "stations": stations_data,
    }

    json_filename = f"{safe_pref}_{safe_city}.json"
    json_path = os.path.join(CITY_OUTPUT_DIR, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON保存: {json_path}")
    logger.info(f"=== 市区別モード完了: {len(stations_data)}駅 ===")

    return result
