"""
交通API - Overpass API (OpenStreetMap) を使った駅・路線データ取得とBFS乗り換え探索
APIキー不要で全国対応
"""
import difflib
import json
import math
import os
import logging
from collections import defaultdict, deque

import requests

from config import OVERPASS_API_URL, OUTPUT_DIR

logger = logging.getLogger("store-traffic")

CACHE_DIR = os.path.join(OUTPUT_DIR, ".cache")
GRAPH_CACHE = os.path.join(CACHE_DIR, "osm_rail_graph.json")


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _fetch_rail_data_from_overpass():
    """
    Overpass APIから関東エリアの鉄道路線・駅データを取得
    route=train/subway/light_rail/monorail の relation を取得し、
    メンバーの stop ノードから駅名を収集する
    """
    logger.info("Overpass APIから鉄道データを取得中...")

    # 日本全国
    bbox = "24.0,122.0,46.0,146.0"

    query = f"""
    [out:json][timeout:300][bbox:{bbox}];
    (
      relation["type"="route"]["route"="train"];
      relation["type"="route"]["route"="subway"];
      relation["type"="route"]["route"="light_rail"];
      relation["type"="route"]["route"="monorail"];
      relation["type"="route"]["route"="railway"];
    );
    out body;
    >;
    out body qt;
    """

    try:
        resp = requests.post(
            OVERPASS_API_URL,
            data={"data": query},
            timeout=240,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Overpass APIエラー: {e}")
        raise


def _build_graph_from_overpass(data):
    """
    Overpassレスポンスからグラフを構築
    同名駅（座標が50km以上離れている）は地域名を付加して区別する

    Returns:
        station_to_railways: dict[駅名] -> set[路線名]
        railway_stations: dict[路線名] -> list[駅名]（順序付き）
        station_coords: dict[駅名] -> {"lat": float, "lon": float}
    """
    # node ID → 駅名マッピング（railway=stop/station/halt すべて対象）
    node_names_raw = {}  # node_id -> clean_name (元の名前)
    node_coords = {}  # node ID → {lat, lon}
    for elem in data.get("elements", []):
        if elem.get("type") == "node":
            tags = elem.get("tags", {})
            name = tags.get("name", "")
            railway = tags.get("railway", "")
            if name and railway in ("station", "halt", "stop"):
                clean = name.rstrip("駅")
                node_names_raw[elem["id"]] = clean
                if "lat" in elem and "lon" in elem:
                    node_coords[elem["id"]] = {"lat": elem["lat"], "lon": elem["lon"]}

    # --- 同名駅の分離: 座標が50km以上離れた同名ノードに地域サフィックスを付加 ---
    SAME_NAME_THRESHOLD_KM = 50
    # 駅名ごとにノードをグループ化
    name_to_nodes = defaultdict(list)  # clean_name -> [(node_id, lat, lon), ...]
    for nid, cname in node_names_raw.items():
        coord = node_coords.get(nid)
        if coord:
            name_to_nodes[cname].append((nid, coord["lat"], coord["lon"]))
        else:
            name_to_nodes[cname].append((nid, None, None))

    # 地域判定用テーブル (lat, lon の範囲 → 地域名)  ※先頭から順にマッチ、狭い範囲を先に
    _REGION_TABLE = [
        ((33.45, 33.75, 130.2, 130.6), "福岡"),
        ((34.6, 34.8, 135.3, 135.6), "大阪"),
        ((34.9, 35.1, 136.8, 137.0), "名古屋"),
        ((35.6, 35.82, 139.5, 140.0), "東京"),
        ((35.35, 35.6, 139.3, 139.8), "神奈川"),
        ((35.8, 36.1, 139.5, 140.2), "埼玉"),
        ((35.5, 35.9, 139.9, 140.3), "千葉"),
        ((35.0, 35.6, 138.5, 139.3), "山梨"),
        ((42.5, 46.0, 139.0, 146.0), "北海道"),
        ((38.5, 42.5, 139.0, 141.5), "東北"),
        ((36.0, 37.5, 139.0, 140.5), "北関東"),
        ((35.0, 36.5, 136.5, 138.5), "中部"),
        ((34.5, 35.5, 134.5, 136.5), "関西"),
        ((33.5, 35.0, 130.5, 135.0), "中国"),
        ((33.0, 34.5, 132.0, 134.5), "四国"),
        ((31.0, 34.0, 129.5, 132.0), "九州"),
    ]

    def _get_region(lat, lon):
        if lat is None or lon is None:
            return ""
        for (lat_min, lat_max, lon_min, lon_max), region in _REGION_TABLE:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return region
        return ""

    def _cluster_nodes(nodes):
        """座標が近いノードをクラスタにまとめる"""
        clusters = []  # [(representative_lat, representative_lon, [node_ids])]
        for nid, lat, lon in nodes:
            if lat is None:
                # 座標なしは最初のクラスタに入れる
                if clusters:
                    clusters[0][2].append(nid)
                else:
                    clusters.append((None, None, [nid]))
                continue
            placed = False
            for ci, (clat, clon, members) in enumerate(clusters):
                if clat is not None and _haversine_km(lat, lon, clat, clon) < SAME_NAME_THRESHOLD_KM:
                    members.append(nid)
                    placed = True
                    break
            if not placed:
                clusters.append((lat, lon, [nid]))
        return clusters

    # 同名駅を分離してnode_namesを再構築
    node_names = {}  # node_id -> display_name（地域サフィックス付き）
    for cname, nodes in name_to_nodes.items():
        clusters = _cluster_nodes(nodes)
        if len(clusters) <= 1:
            # 同一エリア内 → そのまま
            for nid, _lat, _lon in nodes:
                node_names[nid] = cname
        else:
            # 複数クラスタ → 地域名を付加
            # 同じ地域名が重複する場合は連番で区別
            used_names = {}
            for clat, clon, member_nids in clusters:
                region = _get_region(clat, clon)
                base_suffix = f"{cname}({region})" if region else cname
                if base_suffix in used_names:
                    used_names[base_suffix] += 1
                    suffix_name = f"{cname}({region}{used_names[base_suffix]})"
                else:
                    used_names[base_suffix] = 1
                    suffix_name = base_suffix
                for nid in member_nids:
                    node_names[nid] = suffix_name

    # 路線(relation)から駅順序を構築
    railway_stations = {}
    station_to_railways = defaultdict(set)

    for elem in data.get("elements", []):
        if elem.get("type") != "relation":
            continue

        tags = elem.get("tags", {})
        route_type = tags.get("route", "")
        if route_type not in ("train", "subway", "light_rail", "monorail", "railway"):
            continue

        route_name = tags.get("name", "")
        if not route_name:
            ref = tags.get("ref", "")
            operator = tags.get("operator", "")
            route_name = f"{operator} {ref}".strip() or f"route_{elem['id']}"

        # 上り/下りで重複するのでユニーク化
        # "東京メトロ銀座線 : 浅草→渋谷" → "東京メトロ銀座線"
        base_name = route_name.split(" : ")[0].split("：")[0].strip()

        members = elem.get("members", [])
        # まず路線のメンバーノードIDと座標を収集
        member_nids = []
        for m in members:
            role = m.get("role", "")
            is_stop_role = role in ("stop", "stop_entry_only", "stop_exit_only", "platform", "platform_entry_only", "platform_exit_only")
            is_railway_member = route_type == "railway" and m.get("type") == "node"
            if m.get("type") == "node" and (is_stop_role or is_railway_member):
                nid = m.get("ref")
                if nid in node_names:
                    member_nids.append(nid)

        # 路線の重心を計算し、重心から150km以上離れたノードを除外（OSMデータ誤り対策）
        route_coords = [node_coords[nid] for nid in member_nids if nid in node_coords]
        route_valid_nids = set(member_nids)
        if len(route_coords) >= 3:
            med_lat = sorted(c["lat"] for c in route_coords)[len(route_coords) // 2]
            med_lon = sorted(c["lon"] for c in route_coords)[len(route_coords) // 2]
            route_valid_nids = set()
            for nid in member_nids:
                c = node_coords.get(nid)
                if c and _haversine_km(c["lat"], c["lon"], med_lat, med_lon) > 150:
                    continue
                route_valid_nids.add(nid)

        ordered = []
        for nid in member_nids:
            if nid in route_valid_nids:
                sname = node_names[nid]
                if not ordered or ordered[-1] != sname:
                    ordered.append(sname)

        if len(ordered) >= 2:
            # 上下線をマージ
            if base_name in railway_stations:
                existing = railway_stations[base_name]
                # 長い方を採用
                if len(ordered) > len(existing):
                    railway_stations[base_name] = ordered
                # 既存にない駅を追加
                existing_set = set(existing)
                for s in ordered:
                    if s not in existing_set:
                        railway_stations[base_name].append(s)
                        existing_set.add(s)
            else:
                railway_stations[base_name] = ordered

            for s in ordered:
                station_to_railways[s].add(base_name)

    # 駅名 → 座標マッピング（同名駅は最初に見つかったものを採用）
    station_coords = {}
    for nid, sname in node_names.items():
        if sname not in station_coords and nid in node_coords:
            station_coords[sname] = node_coords[nid]

    return station_to_railways, railway_stations, station_coords


def fetch_rail_graph(use_cache=True):
    """鉄道グラフを取得（キャッシュ付き）

    Returns:
        (station_to_railways, railway_stations, station_coords)
    """
    _ensure_cache_dir()

    if use_cache and os.path.exists(GRAPH_CACHE):
        logger.info("鉄道グラフをキャッシュから読み込み")
        with open(GRAPH_CACHE, "r", encoding="utf-8") as f:
            cached = json.load(f)

        # 座標データがないキャッシュは再取得
        if "station_coords" not in cached:
            logger.info("キャッシュに座標データがないため再取得します")
            return fetch_rail_graph(use_cache=False)

        station_to_railways = defaultdict(set)
        for k, v in cached["station_to_railways"].items():
            station_to_railways[k] = set(v)
        return station_to_railways, cached["railway_stations"], cached["station_coords"]

    data = _fetch_rail_data_from_overpass()
    station_to_railways, railway_stations, station_coords = _build_graph_from_overpass(data)

    cache_data = {
        "station_to_railways": {k: list(v) for k, v in station_to_railways.items()},
        "railway_stations": railway_stations,
        "station_coords": station_coords,
    }
    with open(GRAPH_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

    logger.info(f"グラフ構築完了: {len(station_to_railways)}駅, {len(railway_stations)}路線")
    return station_to_railways, railway_stations, station_coords


def _haversine_km(lat1, lon1, lat2, lon2):
    """2点間の距離(km)を概算"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


def find_reachable_stations(base_station, max_transfer, station_to_railways, railway_stations, station_coords=None):
    """
    BFS探索：指定駅からmax_transfer回以内の乗り換えで到達できる駅を返す
    路線情報付きで返す

    Returns:
        (reachable, station_railway_map, matched_name)
        matched_name: マッチした正式駅名（入力と同じ場合もそのまま返す）
    """
    matched_name = base_station
    if base_station not in station_to_railways:
        # 1. 部分文字列マッチ
        candidates = [s for s in station_to_railways if base_station in s]
        if not candidates:
            # 2. difflibあいまいマッチ
            all_names = list(station_to_railways.keys())
            close = difflib.get_close_matches(base_station, all_names, n=3, cutoff=0.5)
            if close:
                candidates = close
        if candidates:
            exact = [s for s in candidates if s == base_station]
            matched = exact[0] if exact else candidates[0]
            logger.info(f"'{base_station}' → '{matched}' にマッチ")
            base_station = matched
            matched_name = matched
        else:
            logger.error(f"駅 '{base_station}' が見つかりません")
            return [], {}, None

    # 同名駅チェック: 同じ駅名が複数路線グループに属し、座標が遠い場合は候補を返す
    # （呼び出し元で選択UIを表示するため）

    # 基準駅の座標（距離制限に使用）
    MAX_DISTANCE_KM = 80
    base_coord = (station_coords or {}).get(base_station)

    visited = {base_station: 0}
    station_railway_map = defaultdict(set)
    queue = deque()

    for rw_id in station_to_railways[base_station]:
        queue.append((base_station, rw_id, 0))
        station_railway_map[base_station].add(rw_id)

    processed = set()

    while queue:
        current_station, current_railway, transfers = queue.popleft()

        if (current_station, current_railway) in processed:
            continue
        processed.add((current_station, current_railway))

        if transfers > max_transfer:
            continue

        if current_railway in railway_stations:
            for station in railway_stations[current_railway]:
                # 座標距離で制限（同名別駅・遠距離路線を除外）
                if base_coord and station_coords:
                    sc = station_coords.get(station)
                    if sc:
                        dist = _haversine_km(base_coord["lat"], base_coord["lon"], sc["lat"], sc["lon"])
                        if dist > MAX_DISTANCE_KM:
                            continue

                if station not in visited or visited[station] > transfers:
                    visited[station] = transfers
                station_railway_map[station].add(current_railway)

                if transfers + 1 <= max_transfer:
                    for rw_id in station_to_railways.get(station, set()):
                        if rw_id != current_railway:
                            if (station, rw_id) not in processed:
                                queue.append((station, rw_id, transfers + 1))

    reachable = sorted(
        [s for s in visited if s != base_station],
        key=lambda s: visited[s]
    )
    logger.info(
        f"'{base_station}' から乗り換え{max_transfer}回以内: "
        f"{len(reachable)}駅"
    )
    return reachable, station_railway_map, matched_name


def get_reachable_stations(base_station, max_transfer):
    """
    メインエントリポイント：基準駅から到達可能な駅リストを取得（路線情報付き）

    Returns:
        (reachable, merged, matched_name, station_coords, railway_stations, station_to_railways)
    """
    station_to_railways, railway_stations, station_coords = fetch_rail_graph()

    reachable, station_railway_map, matched_name = find_reachable_stations(
        base_station, max_transfer, station_to_railways, railway_stations, station_coords
    )

    base = matched_name or base_station
    reachable_set = set(reachable)

    # reachable な駅が属する全路線を収集し、路線ごとにグルーピング
    relevant_railways = set()
    for s in reachable:
        for rw in station_to_railways.get(s, set()):
            relevant_railways.add(rw)

    by_railway = {}
    for rw in relevant_railways:
        if rw not in railway_stations:
            continue
        # 路線上の駅順序を保持しつつ、reachable な駅のみ抽出
        seen_in_line = set()
        unique_stations = []
        for s in railway_stations[rw]:
            if s != base and s in reachable_set and s not in seen_in_line:
                seen_in_line.add(s)
                unique_stations.append(s)
        if unique_stations:
            by_railway[rw] = unique_stations

    # 上り/下り・直通運転の重複路線を統合
    # 駅リストの集合が他路線の部分集合なら除去
    merged = {}
    rw_items = sorted(by_railway.items(), key=lambda x: len(x[1]), reverse=True)
    for rw_name, stations in rw_items:
        station_set = set(stations)
        is_subset = False
        for existing_name, existing_stations in merged.items():
            if station_set <= set(existing_stations):
                is_subset = True
                break
        if not is_subset:
            merged[rw_name] = stations

    return reachable, merged, matched_name, station_coords, railway_stations, station_to_railways


def find_station_candidates(input_name):
    """
    入力駅名に対する候補を路線情報付きで返す。
    同名駅や部分一致が複数ある場合にUIで選択させるために使用。

    Returns:
        list[dict]: [{"name": str, "railways": list[str], "label": str}, ...]
        空リスト = 候補なし
    """
    station_to_railways, _railway_stations, station_coords = fetch_rail_graph()

    # 完全一致があるかチェック
    if input_name in station_to_railways:
        candidates_names = [input_name]
    else:
        # 部分文字列マッチ
        candidates_names = [s for s in station_to_railways if input_name in s]
        if not candidates_names:
            # あいまいマッチ
            all_names = list(station_to_railways.keys())
            close = difflib.get_close_matches(input_name, all_names, n=5, cutoff=0.5)
            candidates_names = close if close else []

    if not candidates_names:
        return []

    # 各候補に路線情報を付加
    results = []
    for name in candidates_names:
        rws = sorted(station_to_railways.get(name, set()))
        label = f"{name}（{' / '.join(rws)}）" if rws else name
        results.append({"name": name, "railways": rws, "label": label})

    return results
