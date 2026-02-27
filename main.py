#!/usr/bin/env python3
"""
store-traffic-image-collector
駅別 / 市区別で駅名リストと駅画像を自動取得・保存するCLIツール
"""
import argparse
import sys

from config import setup_logging, validate_keys


def main():
    parser = argparse.ArgumentParser(
        description="駅別/市区別 駅画像コレクター",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --mode station --base 表参道 --transfer 1
  python main.py --mode city --pref 東京都 --city 渋谷区
        """,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["station", "city"],
        help="実行モード: station（駅別）/ city（市区別）",
    )
    parser.add_argument(
        "--base",
        help="基準駅名（stationモード用）",
    )
    parser.add_argument(
        "--transfer",
        type=int,
        default=1,
        help="最大乗り換え回数（stationモード用、デフォルト: 1）",
    )
    parser.add_argument(
        "--pref",
        help="都道府県名（cityモード用）",
    )
    parser.add_argument(
        "--city",
        help="市区町村名（cityモード用）",
    )

    args = parser.parse_args()
    logger = setup_logging()

    # APIキー検証
    warnings = validate_keys()
    for w in warnings:
        logger.warning(w)

    # モード別実行
    if args.mode == "station":
        if not args.base:
            parser.error("stationモードには --base が必要です")

        from station_mode import run_station_mode

        result = run_station_mode(args.base, args.transfer)
        if result:
            print(f"\n完了: {result['total_stations']}駅の情報を取得しました")
            print(f"基準駅: {result['base_station']}")
            print(f"乗り換え: {result['max_transfer']}回以内")
        else:
            print("\n駅情報の取得に失敗しました")
            sys.exit(1)

    elif args.mode == "city":
        if not args.pref or not args.city:
            parser.error("cityモードには --pref と --city が必要です")

        from city_mode import run_city_mode

        result = run_city_mode(args.pref, args.city)
        if result:
            print(f"\n完了: {result['total_stations']}駅の情報を取得しました")
            print(f"対象: {result['prefecture']} {result['city']}")
        else:
            print("\n駅情報の取得に失敗しました")
            sys.exit(1)


if __name__ == "__main__":
    main()
