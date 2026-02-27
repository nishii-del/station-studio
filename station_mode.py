"""
駅別モード - 指定駅から乗り換えN回以内の駅リストを取得（路線別）
"""
import json
import math
import os
import re
import logging

from transport_api import get_reachable_stations
from config import STATION_OUTPUT_DIR

logger = logging.getLogger("store-traffic")


def _sanitize_filename(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def _haversine_km(lat1, lon1, lat2, lon2):
    """2点間の直線距離（km）をHaversine公式で計算"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_travel_time(base, target, railway_stations, station_to_railways, station_coords):
    """基準駅からターゲット駅までのおおよその移動時間（分）を推定する。

    同一路線: 各駅間の座標距離を合算 → 距離ベースで時間推定
    乗り換えあり: +5分ペナルティ
    座標がない場合: 駅数 × 2.5分（フォールバック）
    """
    base_railways = station_to_railways.get(base, set())
    target_railways = station_to_railways.get(target, set())

    def _route_time(stations, idx_from, idx_to):
        """路線上のidx_fromからidx_toまでの移動時間を座標距離で推定"""
        lo, hi = min(idx_from, idx_to), max(idx_from, idx_to)
        total_km = 0.0
        has_coords = True
        for j in range(lo, hi):
            c1 = station_coords.get(stations[j])
            c2 = station_coords.get(stations[j + 1])
            if c1 and c2:
                total_km += _haversine_km(c1["lat"], c1["lon"], c2["lat"], c2["lon"])
            else:
                has_coords = False
                break
        if has_coords and total_km > 0:
            # 直線距離 × 1.3（線路迂回係数） → 平均速度60km/hで割る
            return max(1, round(total_km * 1.3 / 60 * 60))
        # フォールバック: 駅数ベース
        return max(1, round((hi - lo) * 2.5))

    # 同一路線にある場合
    for rw in base_railways & target_railways:
        stations = railway_stations.get(rw, [])
        if base in stations and target in stations:
            idx_base = stations.index(base)
            idx_target = stations.index(target)
            return _route_time(stations, idx_base, idx_target)

    # 乗り換え1回: 共通の中間駅を探す
    best = None
    for rw_b in base_railways:
        stations_b = railway_stations.get(rw_b, [])
        if base not in stations_b:
            continue
        for s in stations_b:
            if s == base:
                continue
            s_railways = station_to_railways.get(s, set())
            for rw_t in s_railways & target_railways:
                stations_t = railway_stations.get(rw_t, [])
                if s in stations_t and target in stations_t:
                    idx1 = stations_b.index(base)
                    idx2 = stations_b.index(s)
                    idx3 = stations_t.index(s)
                    idx4 = stations_t.index(target)
                    t = _route_time(stations_b, idx1, idx2) + 5 + _route_time(stations_t, idx3, idx4)
                    if best is None or t < best:
                        best = t

    return best


def run_station_mode(base_station, max_transfer):
    logger.info(f"=== 駅別モード開始 ===")
    logger.info(f"基準駅: {base_station}, 最大乗り換え: {max_transfer}回")

    safe_base = _sanitize_filename(base_station)
    os.makedirs(STATION_OUTPUT_DIR, exist_ok=True)

    reachable, by_railway, matched_name, station_coords, railway_stations, station_to_railways = get_reachable_stations(base_station, max_transfer)
    if not reachable and not by_railway:
        logger.warning("到達可能な駅が見つかりませんでした")
        return None

    base = matched_name or base_station
    base_coords = station_coords.get(base)

    # 移動時間の上限（推定不能 or これを超える駅は除外）
    MAX_TRAVEL_MINUTES = 90

    railways_data = []
    seen = set()
    total_count = 0

    for railway_name, stations_on_line in by_railway.items():
        logger.info(f"--- {railway_name} ({len(stations_on_line)}駅) ---")

        stations_data = []
        for station_name in stations_on_line:
            if station_name in seen:
                continue

            travel_time = _estimate_travel_time(base, station_name, railway_stations, station_to_railways, station_coords)
            if travel_time is None or travel_time > MAX_TRAVEL_MINUTES:
                continue

            seen.add(station_name)
            total_count += 1

            coords = station_coords.get(station_name)

            entry = {
                "name": station_name,
                "image_path": [],
                "travel_time": travel_time,
            }
            if coords:
                entry["lat"] = coords["lat"]
                entry["lon"] = coords["lon"]

            stations_data.append(entry)

        if stations_data:
            railways_data.append({
                "railway": railway_name,
                "stations": stations_data,
            })

    result = {
        "base_station": base_station,
        "matched_station": matched_name,
        "max_transfer": max_transfer,
        "total_stations": total_count,
        "railways": railways_data,
        "stations": [s for r in railways_data for s in r["stations"]],
    }

    if base_coords:
        result["base_coords"] = base_coords

    json_filename = f"{safe_base}_{max_transfer}transfer.json"
    json_path = os.path.join(STATION_OUTPUT_DIR, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"JSON保存: {json_path}")
    logger.info(f"=== 駅別モード完了: {total_count}駅 ===")
    return result
