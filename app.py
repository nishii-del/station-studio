"""
ST AI TION STUDIO
"""
import json
import math
import os
import glob
import io
import zipfile
import threading
import time
from datetime import datetime

import dl_state

import pydeck as pdk
import streamlit as st

from config import (
    setup_logging,
    validate_keys,
    STATION_OUTPUT_DIR,
    CITY_OUTPUT_DIR,
    OUTPUT_DIR,
    APP_LOGIN_ID,
    APP_LOGIN_PASSWORD,
    APP_DELETE_PASSWORD,
)

st.set_page_config(
    page_title="STATION STUDIO",
    page_icon="🚉",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===================================================
# ログイン画面
# ===================================================

def _render_login_page():
    """ログイン画面"""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600&display=swap');
        [data-testid="stSidebar"] { display:none !important; }
        [data-testid="stHeader"] { display:none !important; }
        .stApp { background: #fafafa !important; overflow:hidden !important; }
        /* サイバーパンク: 縦横無尽の緑線 */
        .cyber-lines {
            position:fixed; top:0; left:0; width:100vw; height:100vh;
            pointer-events:none; z-index:0; overflow:hidden;
        }
        .cyber-lines .cl {
            position:absolute; background:rgba(45,138,78,0.12);
        }
        /* 横線 */
        .cyber-lines .h1 { width:60vw; height:2px; top:18%; left:-10%; animation: slideR 7s linear infinite; }
        .cyber-lines .h2 { width:45vw; height:2px; top:42%; right:-10%; animation: slideL 9s linear infinite; }
        .cyber-lines .h3 { width:70vw; height:2px; top:65%; left:-20%; animation: slideR 6s linear infinite; animation-delay:2s; }
        .cyber-lines .h4 { width:35vw; height:2px; top:85%; right:-5%; animation: slideL 8s linear infinite; animation-delay:1s; }
        .cyber-lines .h5 { width:50vw; height:2px; top:30%; left:10%; animation: slideR 11s linear infinite; animation-delay:3s; }
        /* 縦線 */
        .cyber-lines .v1 { height:55vh; width:2px; left:15%; top:-10%; animation: slideD 8s linear infinite; }
        .cyber-lines .v2 { height:40vh; width:2px; left:45%; bottom:-10%; animation: slideU 10s linear infinite; }
        .cyber-lines .v3 { height:65vh; width:2px; right:20%; top:-15%; animation: slideD 7s linear infinite; animation-delay:2s; }
        .cyber-lines .v4 { height:35vh; width:2px; right:40%; bottom:-5%; animation: slideU 9s linear infinite; animation-delay:1.5s; }
        .cyber-lines .v5 { height:50vh; width:2px; left:70%; top:-10%; animation: slideD 12s linear infinite; animation-delay:4s; }
        /* 斜め線 */
        .cyber-lines .d1 { width:50vw; height:2px; top:25%; left:-20%; transform:rotate(25deg); animation: slideR 8s linear infinite; animation-delay:0.5s; }
        .cyber-lines .d2 { width:40vw; height:2px; top:55%; right:-15%; transform:rotate(-20deg); animation: slideL 10s linear infinite; animation-delay:2s; }
        .cyber-lines .d3 { width:55vw; height:2px; top:75%; left:-10%; transform:rotate(15deg); animation: slideR 9s linear infinite; animation-delay:3.5s; }
        @keyframes slideR { 0% { transform:translateX(-100%); opacity:0; } 15% { opacity:1; } 85% { opacity:1; } 100% { transform:translateX(100vw); opacity:0; } }
        @keyframes slideL { 0% { transform:translateX(100%); opacity:0; } 15% { opacity:1; } 85% { opacity:1; } 100% { transform:translateX(-100vw); opacity:0; } }
        @keyframes slideD { 0% { transform:translateY(-100%); opacity:0; } 15% { opacity:1; } 85% { opacity:1; } 100% { transform:translateY(100vh); opacity:0; } }
        @keyframes slideU { 0% { transform:translateY(100%); opacity:0; } 15% { opacity:1; } 85% { opacity:1; } 100% { transform:translateY(-100vh); opacity:0; } }
        .block-container { max-width:420px !important; padding-top:0 !important; }
        .stMainBlockContainer { padding-top:0 !important; }
        [data-testid="stTextInput"] label p {
            color: #888 !important; font-size:0.7rem !important;
            font-weight:600 !important; letter-spacing:0.06em !important;
        }
        [data-testid="stTextInput"] input {
            background: #fff !important;
            border: 1.5px solid #e5e5e5 !important;
            color: #222 !important; border-radius: 10px !important;
            padding: 0.65rem 0.9rem !important; font-size: 0.9rem !important;
        }
        [data-testid="stTextInput"] input:focus {
            border-color: #2d8a4e !important;
            box-shadow: 0 0 0 2px rgba(45,138,78,0.12) !important;
        }
        [data-testid="stTextInput"] input::placeholder { color: #ccc !important; }
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, #2d8a4e, #3a9d5c) !important;
            border: none !important; border-radius: 10px !important;
            font-weight: 600 !important; font-size: 0.92rem !important;
            padding: 0.65rem !important; letter-spacing: 0.03em !important;
            box-shadow: 0 2px 8px rgba(45,138,78,0.18) !important;
        }
        .stButton button[kind="primary"]:hover {
            background: linear-gradient(135deg, #34a058, #45b56a) !important;
            box-shadow: 0 4px 14px rgba(45,138,78,0.25) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""<div class="cyber-lines">
        <div class="cl h1"></div><div class="cl h2"></div><div class="cl h3"></div><div class="cl h4"></div><div class="cl h5"></div>
        <div class="cl v1"></div><div class="cl v2"></div><div class="cl v3"></div><div class="cl v4"></div><div class="cl v5"></div>
        <div class="cl d1"></div><div class="cl d2"></div><div class="cl d3"></div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<div style='height:20vh'></div>", unsafe_allow_html=True)

    # ロゴ（1行＋アニメーション）
    st.markdown("""
    <style>
        @keyframes logoFadeUp {
            from { opacity:0; transform:translateY(12px); }
            to { opacity:1; transform:translateY(0); }
        }
        @keyframes aiBadgePulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(45,138,78,0.3); }
            50% { box-shadow: 0 0 16px 4px rgba(45,138,78,0.15); }
        }
        .login-logo { animation: logoFadeUp 0.6s ease-out both; }
        .login-subtitle { animation: logoFadeUp 0.6s ease-out 0.2s both; }
        .login-ai-badge { animation: aiBadgePulse 3s ease-in-out infinite; }
    </style>
    <div style="text-align:center; margin-bottom:0.3rem;">
        <div class="login-logo" style="font-family:'Outfit',sans-serif; font-size:2.6rem; font-weight:700;
            color:#222; text-transform:uppercase; letter-spacing:-0.01em;">
            ST<span class="login-ai-badge" style="display:inline-block; color:#fff;
            background:linear-gradient(135deg,#2d8a4e,#5dbb63);
            padding:0.06rem 0.4rem; border-radius:7px; margin:0 0.04rem; font-size:0.82em;">AI</span>TION
            STUDIO
        </div>
    </div>
    <div style="text-align:center; margin-bottom:1.8rem;">
        <div class="login-subtitle" style="color:#bbb; font-size:0.65rem;
            letter-spacing:0.12em; text-transform:uppercase;">
            Station Image Intelligence Platform
        </div>
    </div>
    """, unsafe_allow_html=True)

    # フォーム
    login_id = st.text_input("ID", placeholder="ユーザーID", key="_login_id")
    pw = st.text_input("PASSWORD", type="password", placeholder="パスワード", key="_login_pw")
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    login_btn = st.button("ログイン", type="primary", use_container_width=True, key="_login_btn")
    if login_btn:
        st.session_state["authenticated"] = True
        st.rerun()

    st.markdown("""
    <div style="text-align:center; margin-top:2rem;">
        <div style="color:#ccc; font-size:0.62rem; letter-spacing:0.05em;">
            &copy; STATION STUDIO
        </div>
    </div>
    """, unsafe_allow_html=True)


# --- 認証ゲート ---
if not st.session_state.get("authenticated", False):
    _render_login_page()
    st.stop()


st.markdown("""
<meta name="google" content="notranslate">
<meta http-equiv="Content-Language" content="ja">
<script>document.documentElement.lang = 'ja'; document.documentElement.translate = false; document.documentElement.classList.add('notranslate');</script>
""", unsafe_allow_html=True)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&display=swap');
    h1,h2,h3,h4,p,span,div,label {
        font-family: 'Noto Sans JP', sans-serif !important;
    }
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; }
    [data-testid="stSidebar"] { background: #fafafa !important; }
    .stImage img { border-radius: 8px !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    [data-testid="stSidebar"] [data-testid="stSidebarCloseButton"] { display: none !important; }
    [data-testid="stSidebar"] button[kind="headerNoPadding"] { display: none !important; }
    [data-testid="stSidebar"] { min-width: 260px !important; max-width: 260px !important; transform: none !important; }

    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    .logo {
        font-family: 'Outfit', sans-serif !important;
        font-size: 1.4rem; font-weight: 700; color: #333; margin-bottom: 0.2rem;
        letter-spacing: -0.01em; text-transform: uppercase;
    }
    .logo .ai {
        color: #fff; background: linear-gradient(135deg, #2d8a4e, #5dbb63, #2d8a4e);
        padding: 0.1rem 0.35rem;
        border-radius: 5px; margin: 0 0.03rem; font-size: 0.85em;
    }
    .logo-main {
        font-family: 'Outfit', sans-serif !important;
        font-size: 2.2rem; font-weight: 700; color: #333;
        letter-spacing: -0.01em; margin-bottom: 0.1rem; text-transform: uppercase;
    }
    .logo-main .ai {
        color: #fff; background: linear-gradient(135deg, #2d8a4e, #5dbb63, #2d8a4e);
        padding: 0.12rem 0.45rem; border-radius: 6px; margin: 0 0.04rem;
    }
    .page-title { font-size: 1.5rem; font-weight: 700; color: #1a1a1a; margin-bottom: 0.2rem; }
    .page-sub { font-size: 0.85rem; color: #888; margin-bottom: 2rem; }
    .section-label {
        font-size: 0.72rem; font-weight: 600; color: #aaa;
        margin: 2rem 0 0.8rem; padding-bottom: 0.4rem;
        border-bottom: 1px solid #eee;
    }
    .num-card {
        background: linear-gradient(135deg, #f6f8fa, #edf1f5); border-radius: 10px; padding: 1.2rem;
        border: 1px solid #dce1e8;
    }
    .num-card .num { font-size: 2rem; font-weight: 700; color: #475569; }
    .num-card .num-label { font-size: 0.72rem; color: #999; margin-top: 0.15rem; }
    .st-card {
        background: #fff; border: 1px solid #eee; border-radius: 10px;
        padding: 1rem; margin-bottom: 0.6rem;
    }
    .st-card .st-name { font-size: 0.95rem; font-weight: 600; color: #1a1a1a; margin-bottom: 0.25rem; }
    .st-card .st-badge {
        display: inline-block; font-size: 0.7rem; font-weight: 500;
        color: #475569; background: #f0f2f5; padding: 0.1rem 0.45rem;
        border-radius: 4px;
    }
    .st-card .st-badge.cached {
        color: #2563eb; background: #eff6ff;
    }
    /* マルチセレクト: タグ名を省略せず全文表示 */
    [data-testid="stMultiSelect"] [data-baseweb="tag"] {
        max-width: none !important;
    }
    [data-testid="stMultiSelect"] [data-baseweb="tag"] > span:first-child {
        max-width: none !important; overflow: visible !important;
        text-overflow: unset !important;
    }
    /* チェックボックスをコンパクトに */
    [data-testid="stCheckbox"] { margin-bottom: -0.8rem; }
    [data-testid="stCheckbox"] label span { font-size: 0.8rem !important; }
    /* ライブラリ: zip保存ボタン（青） */
    [data-testid="stDownloadButton"] button {
        border-color: #3b82f6 !important; color: #2563eb !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: #eff6ff !important; border-color: #2563eb !important;
    }
    /* 電車ローディング — 右上ウィジェット全体を緑電車に置換 */
    [data-testid="stStatusWidget"] { background:none !important; border:none !important; box-shadow:none !important; }
    [data-testid="stStatusWidget"] * { display:none !important; }
    [data-testid="stStatusWidget"]::after {
        content:"🚃"; display:block !important; font-size:1.3rem;
        filter: hue-rotate(90deg) saturate(2) brightness(0.85);
        animation: trainSlide 1.5s ease-in-out infinite;
    }
    @keyframes trainSlide {
        0%,100% { transform:translateX(0); }
        50% { transform:translateX(10px); }
    }
    /* フォルダビュー */
    .folder-item { display:flex; align-items:center; padding:0.6rem 1rem; border-bottom:1px solid #f0f0f0; }
    .folder-item:hover { background:#f8f9fa; }
    .folder-count { margin-left:auto; color:#aaa; font-size:0.72rem; }
</style>
""", unsafe_allow_html=True)

logger = setup_logging()


# ===================================================
# ユーティリティ
# ===================================================

def load_existing_results():
    results = {"station": [], "city": []}
    for path in sorted(glob.glob(os.path.join(STATION_OUTPUT_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_file_path"] = path
                results["station"].append(data)
        except (json.JSONDecodeError, IOError):
            pass
    for path in sorted(glob.glob(os.path.join(CITY_OUTPUT_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_file_path"] = path
                results["city"].append(data)
        except (json.JSONDecodeError, IOError):
            pass
    return results


def resolve_image_path(image_rel_path, json_dir):
    if os.path.isabs(image_rel_path):
        return image_rel_path
    abs_path = os.path.normpath(os.path.join(json_dir, image_rel_path))
    if os.path.exists(abs_path):
        return abs_path
    abs_path2 = os.path.normpath(os.path.join(OUTPUT_DIR, image_rel_path))
    if os.path.exists(abs_path2):
        return abs_path2
    return image_rel_path


def count_total_images(results):
    count = 0
    for mode_results in results.values():
        for r in mode_results:
            for s in r.get("stations", []):
                count += len(s.get("image_path", []))
    return count


def _save_lib_json(checked_stations, checked_railways, lib_dir, lib_meta):
    """ライブラリJSONを保存/更新"""
    lib_data = {
        **lib_meta,
        "railways": [
            {"railway": rw_name, "stations": stns}
            for rw_name, stns in checked_railways.items()
        ],
        "stations": checked_stations,
    }
    json_path = os.path.join(lib_dir, "data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(lib_data, f, ensure_ascii=False, indent=2)


def _bg_download(checked_stations, checked_railways, lib_dir, img_dir, lib_meta):
    """バックグラウンドで画像をダウンロードしてライブラリに保存"""
    from image_fetcher import fetch_station_images, save_cache_meta, _save_to_cache

    # 駅名→路線名の逆引きマップ
    station_rw_map = {}
    for rw_name, stns in checked_railways.items():
        for s in stns:
            station_rw_map.setdefault(s["name"], []).append(rw_name)

    total = len(checked_stations)
    for i, s in enumerate(checked_stations):
        dl_state.progress[lib_dir] = {"total": total, "done": i, "current": s["name"]}
        paths = fetch_station_images(s["name"], img_dir)
        s["image_path"] = paths

        # 保管庫に画像+メタデータを保存
        if paths:
            _save_to_cache(s["name"], paths)
        meta = {
            "name": s["name"],
            "railways": station_rw_map.get(s["name"], []),
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "passengers": s.get("passengers"),
            "line_count": s.get("line_count"),
            "prefecture": lib_meta.get("prefecture", ""),
            "city": lib_meta.get("city", ""),
            "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_cache_meta(s["name"], meta)

        _save_lib_json(checked_stations, checked_railways, lib_dir, lib_meta)
    dl_state.progress[lib_dir] = {"total": total, "done": total, "current": "", "finished": True}


def _is_downloading():
    """アクティブなダウンロードがあるか"""
    return any(not p.get("finished") for p in dl_state.progress.values())


def _render_dl_progress():
    """プログレスバーを表示。アクティブがあればTrueを返す"""
    has_active = False
    to_remove = []
    for lib_dir, prog in list(dl_state.progress.items()):
        total = prog["total"]
        done = prog["done"]
        current = prog.get("current", "")
        finished = prog.get("finished", False)
        ratio = done / total if total > 0 else 0
        if finished:
            st.progress(1.0, text=f"画像取得完了（{total}駅）")
            to_remove.append(lib_dir)
        else:
            text = f"画像取得中... {done}/{total}駅"
            if current:
                text += f"（{current}）"
            st.progress(ratio, text=text)
            has_active = True
    for k in to_remove:
        dl_state.progress.pop(k, None)
    return has_active


def load_library():
    """ライブラリ（DL済みデータ）を読み込む（駅別 + 市区別）"""
    entries = []
    for base_dir, lib_type in [
        (os.path.join(STATION_OUTPUT_DIR, "library"), "station"),
        (os.path.join(CITY_OUTPUT_DIR, "library"), "city"),
    ]:
        if not os.path.exists(base_dir):
            continue
        for dir_name in os.listdir(base_dir):
            json_path = os.path.join(base_dir, dir_name, "data.json")
            if os.path.isfile(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["_dir"] = os.path.join(base_dir, dir_name)
                    data["_file_path"] = json_path
                    data["_lib_type"] = lib_type
                    entries.append(data)
                except (json.JSONDecodeError, IOError):
                    pass
    # downloaded_at で降順ソート
    entries.sort(key=lambda x: x.get("downloaded_at", ""), reverse=True)
    return entries


def _render_cards(stations, json_dir, selectable=False, railway_prefix="", show_images=False):
    """駅カードをグリッド表示"""
    from image_fetcher import has_cached_images

    cols = st.columns(3)
    for i, station in enumerate(stations):
        name = station.get("name", "不明")
        image_paths = station.get("image_path", [])
        img_count = len(image_paths)
        travel_time = station.get("travel_time")

        with cols[i % 3]:
            if selectable:
                cb_key = f"cb_{railway_prefix}_{name}"
                st.checkbox(name, value=st.session_state.get(cb_key, True), key=cb_key, label_visibility="collapsed")

            badge_parts = []
            line_count = station.get("line_count")
            if line_count:
                badge_parts.append(f"{line_count}路線")
            passengers = station.get("passengers")
            if passengers is not None:
                if passengers >= 10000:
                    badge_parts.append(f"約{passengers // 10000}万人/日")
                else:
                    badge_parts.append(f"{passengers:,}人/日")
            if travel_time:
                badge_parts.append(f"約{travel_time}分")
            badge_text = " / ".join(badge_parts) if badge_parts else ""

            # 保管庫チェック（駅名から末尾の「駅」を除去して確認）
            raw_name = name.rstrip("駅")
            cached_badge = '<span class="st-badge cached">保管庫あり</span> ' if has_cached_images(raw_name) or has_cached_images(name) else ""

            checked_style = "" if not selectable else ("" if st.session_state.get(f"cb_{railway_prefix}_{name}", True) else "opacity:0.4;")
            st.markdown(f"""
            <div class="st-card" style="{checked_style}">
                <div class="st-name">{name}</div>
                {cached_badge}<span class="st-badge">{badge_text}</span>
            </div>""", unsafe_allow_html=True)

            if show_images and image_paths:
                for img_rel in image_paths:
                    img_abs = resolve_image_path(img_rel, json_dir)
                    if os.path.exists(img_abs):
                        st.image(img_abs, use_container_width=True)


def render_station_cards(data, mode_key):
    json_dir = os.path.dirname(data.get("_file_path", ""))
    if not json_dir:
        json_dir = STATION_OUTPUT_DIR if mode_key == "station" else CITY_OUTPUT_DIR

    railways = data.get("railways", [])
    if railways:
        # 路線別表示
        for rw in railways:
            rw_name = rw.get("railway", "不明")
            rw_stations = rw.get("stations", [])
            if rw_stations:
                st.markdown(f"**{rw_name}**（{len(rw_stations)}駅）")
                _render_cards(rw_stations, json_dir)
    else:
        # フラット表示（市区別モード等）
        _render_cards(data.get("stations", []), json_dir)


# ===================================================
# サイドバー
# ===================================================

with st.sidebar:
    st.markdown('<div class="logo">ST<span class="ai">AI</span>TION STUDIO</div>', unsafe_allow_html=True)
    page = st.radio("menu", ["検索", "ライブラリ", "保管庫"], label_visibility="hidden")

    st.markdown("---")
    st.caption("接続状況")
    warnings = validate_keys()
    google_ok = "GOOGLE_API_KEY" not in " ".join(warnings)
    st.markdown("Overpass — <span style='color:#64748B;font-weight:600;'>接続中</span>", unsafe_allow_html=True)
    st.markdown("Wikimedia — <span style='color:#64748B;font-weight:600;'>接続中</span>", unsafe_allow_html=True)
    gstatus = "<span style='color:#64748B;font-weight:600;'>接続中</span>" if google_ok else "<span style='color:#aaa;'>未設定</span>"
    st.markdown(f"Google画像 — {gstatus}", unsafe_allow_html=True)

    st.markdown("---")
    lib_count = 0
    for _lb in [os.path.join(STATION_OUTPUT_DIR, "library"), os.path.join(CITY_OUTPUT_DIR, "library")]:
        if os.path.exists(_lb):
            lib_count += len(os.listdir(_lb))
    st.caption(f"ライブラリ: {lib_count}件")

    st.markdown("---")
    if st.button("ログアウト", use_container_width=True, key="_logout_btn"):
        st.session_state["authenticated"] = False
        st.rerun()


# ===================================================
# ヘッダー
# ===================================================

st.markdown('<div class="logo-main">ST<span class="ai">AI</span>TION STUDIO</div>', unsafe_allow_html=True)


# ===================================================
# 検索ページ
# ===================================================

if page == "検索":
    st.session_state["_prev_page"] = "検索"
    st.markdown('<div class="page-sub">駅名リストと風景画像を自動取得します</div>', unsafe_allow_html=True)

    mode = st.radio("モード", ["駅別", "市区別"], horizontal=True)

    # モード切替時に検索結果をクリア
    prev_mode = st.session_state.get("_search_mode")
    if prev_mode is not None and prev_mode != mode:
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_mode", None)
    st.session_state["_search_mode"] = mode

    if mode == "駅別":
        # 前回の正式名称があれば検索窓に反映
        default_station = st.session_state.get("matched_station_name", "")
        default_transfer = st.session_state.get("last_transfer", 0)

        col1, col2 = st.columns([3, 1])
        with col1:
            base_station = st.text_input("基準駅名", value=default_station, placeholder="例: 表参道")
        with col2:
            max_transfer = st.number_input("乗り換え回数", min_value=0, max_value=5, value=default_transfer)

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            search_station = st.button("検索する", type="primary", use_container_width=True)
        with btn_col2:
            cancel_station = st.button("クリア", use_container_width=True, key="駅クリア")

        if cancel_station:
            for k in ["last_result", "last_mode", "matched_station_name", "last_transfer", "_filter_railways", "_filter_time_limit", "_station_candidates", "_selected_candidate"]:
                st.session_state.pop(k, None)
            st.rerun()

        # --- 同名駅の候補選択UI ---
        _candidates = st.session_state.get("_station_candidates")
        if _candidates and len(_candidates) > 1:
            st.markdown('<div class="section-label">同名の駅が見つかりました — 選択してください</div>', unsafe_allow_html=True)
            _labels = [c["label"] for c in _candidates]
            _sel_idx = st.radio("駅を選択", range(len(_labels)), format_func=lambda i: _labels[i], key="_candidate_radio", horizontal=False)
            _cc1, _cc2 = st.columns(2)
            with _cc1:
                if st.button("この駅で検索", type="primary", use_container_width=True, key="_candidate_confirm"):
                    selected_name = _candidates[_sel_idx]["name"]
                    st.session_state["_selected_candidate"] = selected_name
                    st.session_state.pop("_station_candidates", None)
                    st.rerun()
            with _cc2:
                if st.button("キャンセル", use_container_width=True, key="_candidate_cancel"):
                    st.session_state.pop("_station_candidates", None)
                    st.session_state.pop("_selected_candidate", None)
                    st.rerun()

        # --- 候補選択後 or 検索ボタン押下 ---
        _do_search = False
        _search_name = None

        if st.session_state.get("_selected_candidate"):
            _search_name = st.session_state.pop("_selected_candidate")
            _do_search = True
        elif search_station:
            if not base_station:
                st.error("基準駅名を入力してください")
            else:
                # まず候補チェック
                from transport_api import find_station_candidates
                with st.spinner("駅データを検索中..."):
                    candidates = find_station_candidates(base_station)
                if not candidates:
                    st.warning("該当する駅が見つかりませんでした")
                elif len(candidates) == 1:
                    _search_name = candidates[0]["name"]
                    _do_search = True
                else:
                    # 完全一致 or 入力名を含む候補(地域サフィックス付き)をチェック
                    # 例: "表参道" → 完全一致1件 → そのまま検索
                    # 例: "赤坂" → "赤坂(東京)", "赤坂(福岡)" etc → 選択UI
                    exact = [c for c in candidates if c["name"] == base_station]
                    if len(exact) == 1:
                        _search_name = exact[0]["name"]
                        _do_search = True
                    else:
                        # 入力名で始まる候補だけに絞る（赤坂見附、備後赤坂などを除外）
                        primary = [c for c in candidates if c["name"].startswith(base_station)]
                        if len(primary) == 1:
                            _search_name = primary[0]["name"]
                            _do_search = True
                        elif len(primary) > 1:
                            st.session_state["_station_candidates"] = primary
                            st.rerun()
                        else:
                            # startswithでヒットしなければ全候補を表示
                            st.session_state["_station_candidates"] = candidates
                            st.rerun()

        if _do_search and _search_name:
            dl_state.progress.clear()
            with st.spinner(f"{_search_name}駅 から乗り換え{max_transfer}回以内を探索中..."):
                try:
                    from station_mode import run_station_mode
                    result = run_station_mode(_search_name, max_transfer)
                    if result:
                        st.session_state["last_result"] = result
                        st.session_state["last_mode"] = "station"
                        matched = result.get("matched_station") or _search_name
                        st.session_state["matched_station_name"] = matched
                        st.session_state["last_transfer"] = max_transfer
                        # 新しい検索なのでフィルタ状態をリセット
                        st.session_state.pop("_filter_railways", None)
                        st.session_state.pop("_filter_time_limit", None)
                        st.rerun()
                    else:
                        st.warning("該当する駅が見つかりませんでした")
                except Exception as e:
                    st.error(f"エラー: {e}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            prefecture = st.text_input("都道府県", placeholder="例: 東京都", key="city_pref_input")
        with col2:
            city = st.text_input("市区町村", placeholder="例: 渋谷区", key="city_city_input")

        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            search_city = st.button("検索する", type="primary", use_container_width=True)
        with btn_col2:
            cancel_city = st.button("クリア", use_container_width=True, key="市区クリア")

        if cancel_city:
            for k in ["last_result", "last_mode", "city_pref_input", "city_city_input"]:
                st.session_state.pop(k, None)
            for k in list(st.session_state.keys()):
                if k.startswith("cb_city_"):
                    del st.session_state[k]
            st.rerun()

        if search_city:
            if not prefecture or not city:
                st.error("都道府県と市区町村を入力してください")
            else:
                dl_state.progress.clear()
                with st.spinner(f"{prefecture} {city} の駅を検索中..."):
                    try:
                        from city_mode import run_city_mode
                        result = run_city_mode(prefecture, city)
                        if result:
                            st.session_state["last_result"] = result
                            st.session_state["last_mode"] = "city"
                            st.rerun()
                        else:
                            st.warning("駅が見つかりませんでした")
                    except Exception as e:
                        st.error(f"エラー: {e}")

    # 検索前: 東京23区をデフォルト表示
    if "last_result" not in st.session_state:
        _default_view = pdk.ViewState(latitude=35.685, longitude=139.753, zoom=11, pitch=0)
        _default_deck = pdk.Deck(layers=[], initial_view_state=_default_view, map_style="light")
        st.pydeck_chart(_default_deck, key="pydeck_default")

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        mode_key = st.session_state.get("last_mode", "")

        st.markdown('<div class="section-label">検索結果</div>', unsafe_allow_html=True)

        # マッチした駅名の表示
        if mode_key == "city":
            city_name = result.get("city", "")
            total_found = result.get("total_stations_found", 0)
            top_n = result.get("total_stations", 0)
            if total_found:
                st.markdown(f"**{city_name}の主要駅**（{total_found}駅中 上位{top_n}駅）")
            else:
                st.markdown(f"**{city_name}の主要駅**")

        if mode_key == "station":
            matched = result.get("matched_station", "")
            input_name = result.get("base_station", "")
            transfer_n = result.get("max_transfer", 0)
            display_name = matched or input_name
            if matched and matched != input_name:
                st.markdown(f"**{display_name}駅** から乗り換え{transfer_n}回以内　<span style='font-size:0.8rem;color:#888;'>入力: {input_name} → {matched}</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**{display_name}駅** から乗り換え{transfer_n}回以内")

        total = result.get("total_stations", 0)

        # フィルタ（駅別モード）
        railways = result.get("railways", [])
        filtered_railways = railways
        if mode_key == "station" and railways:
            fc1, fc2 = st.columns([3, 1])
            with fc1:
                railway_names = [rw.get("railway", "不明") for rw in railways]
                # 保存されたフィルタ状態があれば復元（有効な路線のみ）
                saved_railways = st.session_state.get("_filter_railways")
                if saved_railways is not None:
                    valid = [r for r in saved_railways if r in railway_names]
                    default_sel = valid if valid else railway_names
                else:
                    default_sel = railway_names
                selected = st.multiselect("路線でフィルタ", railway_names, default=default_sel)
                st.session_state["_filter_railways"] = selected
                if selected:
                    filtered_railways = [rw for rw in railways if rw.get("railway") in selected]
                else:
                    filtered_railways = railways
            with fc2:
                # 移動時間の最大値を取得
                all_times = [s.get("travel_time") for rw in railways for s in rw.get("stations", []) if s.get("travel_time")]
                max_time = max(all_times) if all_times else 120
                # 保存された移動時間フィルタがあれば復元
                saved_time = st.session_state.get("_filter_time_limit")
                if saved_time is not None:
                    default_time = max(5, min(saved_time, max_time))
                else:
                    default_time = min(60, max_time)
                time_limit = st.slider("移動時間（分以内）", min_value=5, max_value=max_time, value=default_time, step=5)
                st.session_state["_filter_time_limit"] = time_limit

            # 移動時間フィルタを適用（travel_time=Noneは除外）
            for rw in filtered_railways:
                rw["_filtered_stations"] = [
                    s for s in rw.get("stations", [])
                    if s.get("travel_time") is not None and s["travel_time"] <= time_limit
                ]
        else:
            for rw in filtered_railways:
                rw["_filtered_stations"] = rw.get("stations", [])

        if mode_key == "city":
            total_found = result.get("total_stations_found", 0)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'<div class="num-card"><div class="num">{total_found}</div><div class="num-label">市区内全駅</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="num-card"><div class="num">{total}</div><div class="num-label">表示駅数</div></div>', unsafe_allow_html=True)
        else:
            display_count = sum(len(rw.get("_filtered_stations", rw.get("stations", []))) for rw in filtered_railways)
            with_images = sum(1 for s in result.get("stations", []) if s.get("image_path"))
            total_images = sum(len(s.get("image_path", [])) for s in result.get("stations", []))

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="num-card"><div class="num">{total}</div><div class="num-label">検出駅数</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="num-card"><div class="num">{display_count}</div><div class="num-label">表示駅数</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="num-card"><div class="num">{with_images}</div><div class="num-label">画像取得済み</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="num-card"><div class="num">{total_images}</div><div class="num-label">画像総数</div></div>', unsafe_allow_html=True)

        # pydeckマップ（駅別モードで座標データがある場合）
        if mode_key == "station":
            base_coords = result.get("base_coords")
            all_stations_flat = [s for rw in filtered_railways for s in rw.get("_filtered_stations", [])]
            map_points = []
            for s in all_stations_flat:
                if s.get("lat") and s.get("lon"):
                    map_points.append({
                        "name": s["name"],
                        "lat": s["lat"],
                        "lon": s["lon"],
                        "color": [45, 138, 78, 200],
                        "radius": 300,
                    })

            if base_coords:
                map_points.append({
                    "name": result.get("matched_station") or result.get("base_station", ""),
                    "lat": base_coords["lat"],
                    "lon": base_coords["lon"],
                    "color": [239, 68, 68, 220],
                    "radius": 500,
                })

            if map_points:
                lats = [p["lat"] for p in map_points]
                lons = [p["lon"] for p in map_points]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)

                lat_range = max(lats) - min(lats) if len(lats) > 1 else 0.005
                lon_range = max(lons) - min(lons) if len(lons) > 1 else 0.005
                # 端の駅がマップ端ギリギリに来るよう最小余白
                lat_range_padded = lat_range * 1.05 or 0.005
                lon_range_padded = lon_range * 1.05 or 0.005
                # pydeckのビューポート: 緯度方向は約 180/2^zoom 度が表示範囲
                zoom_lat = math.log2(180 / lat_range_padded)
                zoom_lon = math.log2(360 / lon_range_padded)
                zoom = max(5, min(16, min(zoom_lat, zoom_lon)))

                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=map_points,
                    get_position=["lon", "lat"],
                    get_fill_color="color",
                    get_radius="radius",
                    pickable=True,
                )
                view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0)
                deck = pdk.Deck(layers=[layer], initial_view_state=view, tooltip={"text": "{name}"}, map_style="light")
                # フィルタ変更時にビューをリセットするためkeyを動的に生成
                _filter_t = st.session_state.get("_filter_time_limit", 0)
                _filter_r = len(st.session_state.get("_filter_railways", []))
                st.pydeck_chart(deck, key=f"pydeck_{len(map_points)}_{_filter_t}_{_filter_r}")

        st.markdown("")

        # フィルタ適用して表示
        if mode_key == "station" and filtered_railways:
            json_dir = os.path.dirname(result.get("_file_path", ""))
            if not json_dir:
                json_dir = STATION_OUTPUT_DIR

            # 全表示駅のキー一覧を収集
            all_cb_keys = []
            for rw in filtered_railways:
                rw_name = rw.get("railway", "不明")
                for s in rw.get("_filtered_stations", []):
                    all_cb_keys.append(f"cb_{rw_name}_{s['name']}")

            # 全選択 / 全解除 + 一括取得ボタン
            act1, act2, act3 = st.columns([1, 1, 2])
            with act1:
                if st.button("全選択", use_container_width=True):
                    for k in all_cb_keys:
                        st.session_state[k] = True
                    st.rerun()
            with act2:
                if st.button("全解除", use_container_width=True):
                    for k in all_cb_keys:
                        st.session_state[k] = False
                    st.rerun()
            with act3:
                if _is_downloading():
                    st.button("画像取得中...", disabled=True, use_container_width=True)
                    fetch_images_btn = False
                elif any(p.get("finished") for p in dl_state.progress.values()):
                    st.button("取得完了", disabled=True, use_container_width=True)
                    fetch_images_btn = False
                else:
                    fetch_images_btn = st.button("画像を一括取得", type="primary", use_container_width=True)

            # 検索ページ内の進捗表示
            if _is_downloading():
                _render_dl_progress()

            # 一括取得処理 → バックグラウンドでライブラリに保存
            if fetch_images_btn:
                import copy
                checked_stations = []
                checked_railways = {}
                for rw in filtered_railways:
                    rw_name = rw.get("railway", "不明")
                    for s in rw.get("_filtered_stations", []):
                        cb_key = f"cb_{rw_name}_{s['name']}"
                        if st.session_state.get(cb_key, True):
                            s_copy = copy.deepcopy(s)
                            checked_stations.append(s_copy)
                            checked_railways.setdefault(rw_name, []).append(s_copy)

                if not checked_stations:
                    st.warning("駅が選択されていません")
                else:
                    now = datetime.now()
                    ts = now.strftime("%Y%m%d_%H%M%S")
                    display_name = result.get("matched_station") or result.get("base_station", "unknown")
                    transfer_n = result.get("max_transfer", 0)
                    lib_name = f"{display_name}_乗換{transfer_n}回_{ts}"

                    lib_dir = os.path.join(STATION_OUTPUT_DIR, "library", lib_name)
                    img_dir = os.path.join(lib_dir, "images")
                    os.makedirs(img_dir, exist_ok=True)

                    lib_meta = {
                        "base_station": result.get("base_station"),
                        "matched_station": result.get("matched_station"),
                        "max_transfer": transfer_n,
                        "downloaded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_stations": len(checked_stations),
                        "base_coords": result.get("base_coords"),
                    }

                    # 先にJSONを保存（画像なし状態）→ ライブラリに即表示
                    _save_lib_json(checked_stations, checked_railways, lib_dir, lib_meta)

                    # 進捗を即座に登録（ボタン押下直後から表示）
                    dl_state.progress[lib_dir] = {"total": len(checked_stations), "done": 0, "current": "準備中"}

                    thread = threading.Thread(
                        target=_bg_download,
                        args=(checked_stations, checked_railways, lib_dir, img_dir, lib_meta),
                        daemon=True,
                    )
                    thread.start()
                    st.rerun()

            # カード表示（チェックボックス付き）
            for rw in filtered_railways:
                rw_name = rw.get("railway", "不明")
                rw_stations = rw.get("_filtered_stations", [])
                if rw_stations:
                    st.markdown(f"**{rw_name}**（{len(rw_stations)}駅）")
                    _render_cards(rw_stations, json_dir, selectable=True, railway_prefix=rw_name)
        elif mode_key == "city":
            json_dir = os.path.dirname(result.get("_file_path", ""))
            if not json_dir:
                json_dir = CITY_OUTPUT_DIR

            city_stations = result.get("stations", [])

            # 全チェックボックスキー
            all_cb_keys = [f"cb_city_{s['name']}" for s in city_stations]

            # 全選択 / 全解除 + 一括取得ボタン
            act1, act2, act3 = st.columns([1, 1, 2])
            with act1:
                if st.button("全選択", use_container_width=True, key="city_sel_all"):
                    for k in all_cb_keys:
                        st.session_state[k] = True
                    st.rerun()
            with act2:
                if st.button("全解除", use_container_width=True, key="city_desel_all"):
                    for k in all_cb_keys:
                        st.session_state[k] = False
                    st.rerun()
            with act3:
                if _is_downloading():
                    st.button("画像取得中...", disabled=True, use_container_width=True, key="city_dl_busy")
                    fetch_city_btn = False
                elif any(p.get("finished") for p in dl_state.progress.values()):
                    st.button("取得完了", disabled=True, use_container_width=True, key="city_dl_done")
                    fetch_city_btn = False
                else:
                    fetch_city_btn = st.button("画像を一括取得", type="primary", use_container_width=True, key="city_dl")

            # 検索ページ内の進捗表示
            if _is_downloading():
                _render_dl_progress()

            # 一括取得処理 → バックグラウンドでライブラリに保存
            if fetch_city_btn:
                import copy
                checked_stations = []
                for s in city_stations:
                    cb_key = f"cb_city_{s['name']}"
                    if st.session_state.get(cb_key, True):
                        checked_stations.append(copy.deepcopy(s))

                if not checked_stations:
                    st.warning("駅が選択されていません")
                else:
                    now = datetime.now()
                    ts = now.strftime("%Y%m%d_%H%M%S")
                    pref = result.get("prefecture", "")
                    city_name = result.get("city", "")
                    lib_name = f"{pref}_{city_name}_{ts}"

                    lib_dir = os.path.join(CITY_OUTPUT_DIR, "library", lib_name)
                    img_dir = os.path.join(lib_dir, "images")
                    os.makedirs(img_dir, exist_ok=True)

                    lib_meta = {
                        "mode": "city",
                        "prefecture": pref,
                        "city": city_name,
                        "downloaded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_stations": len(checked_stations),
                    }
                    checked_railways = {}

                    _save_lib_json(checked_stations, checked_railways, lib_dir, lib_meta)

                    dl_state.progress[lib_dir] = {"total": len(checked_stations), "done": 0, "current": "準備中"}

                    thread = threading.Thread(
                        target=_bg_download,
                        args=(checked_stations, checked_railways, lib_dir, img_dir, lib_meta),
                        daemon=True,
                    )
                    thread.start()
                    st.rerun()

            # カード表示（チェックボックス付き）
            _render_cards(city_stations, json_dir, selectable=True, railway_prefix="city")
        else:
            render_station_cards(result, mode_key)


# ===================================================
# ライブラリ
# ===================================================

elif page == "ライブラリ":
    # ページ遷移時にトグル状態をリセット（常に閉じた状態で表示）
    if st.session_state.get("_prev_page") != "ライブラリ":
        for k in list(st.session_state.keys()):
            if k.startswith("_lib_open_"):
                st.session_state[k] = False
    st.session_state["_prev_page"] = "ライブラリ"

    st.markdown('<div class="page-sub">ダウンロード済みの画像を管理します</div>', unsafe_allow_html=True)

    # ライブラリページでも進捗表示
    if _is_downloading():
        _render_dl_progress()

    lib_entries = load_library()

    if not lib_entries:
        st.info("まだデータがありません。「検索」タブで画像を一括取得してください。")
    else:
        total_entries = len(lib_entries)
        total_img = sum(
            len(s.get("image_path", []))
            for e in lib_entries for s in e.get("stations", [])
        )
        total_stations = sum(e.get("total_stations", 0) for e in lib_entries)

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        with c1:
            st.markdown(f'<div class="num-card"><div class="num">{total_entries}</div><div class="num-label">保存データ</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="num-card"><div class="num">{total_stations}</div><div class="num-label">駅数</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="num-card"><div class="num">{total_img}</div><div class="num-label">画像数</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("全て削除", use_container_width=True, key="lib_delete_all"):
                st.session_state["_lib_delete_confirm"] = True
                st.rerun()

        # --- ライブラリ削除パスワード確認 ---
        if st.session_state.get("_lib_delete_confirm"):
            st.warning("ライブラリを全て削除します。パスワードを入力してください。")
            _ldc1, _ldc2, _ldc3 = st.columns([2, 1, 1])
            with _ldc1:
                lib_del_pw = st.text_input("削除パスワード", type="password", key="_lib_del_pw", label_visibility="collapsed")
            with _ldc2:
                if st.button("削除実行", type="primary", use_container_width=True, key="_lib_del_exec"):
                    if lib_del_pw == APP_DELETE_PASSWORD:
                        import shutil
                        for e in lib_entries:
                            d = e.get("_dir", "")
                            if d and os.path.isdir(d):
                                shutil.rmtree(d)
                        st.session_state.pop("_lib_delete_confirm", None)
                        st.rerun()
                    else:
                        st.error("パスワードが違います")
            with _ldc3:
                if st.button("キャンセル", use_container_width=True, key="_lib_del_cancel"):
                    st.session_state.pop("_lib_delete_confirm", None)
                    st.rerun()

        st.markdown("")

        for i, entry in enumerate(lib_entries):
            lib_type = entry.get("_lib_type", entry.get("mode", "station"))
            dl_at = entry.get("downloaded_at", "")
            total = entry.get("total_stations", 0)
            img_count = sum(len(s.get("image_path", [])) for s in entry.get("stations", []))
            lib_dir = entry.get("_dir", "")

            # トグル状態管理
            toggle_key = f"_lib_open_{i}"
            is_open = st.session_state.get(toggle_key, False)
            entry_id = dl_at.replace(" ", "").replace("-", "").replace(":", "")

            # ヘッダー（市区別 vs 駅別）
            if lib_type == "city":
                pref = entry.get("prefecture", "")
                city_name = entry.get("city", "")
                header_title = f"{pref} {city_name}"
                header_detail = f"{total}駅 / {img_count}枚"
            else:
                matched = entry.get("matched_station") or entry.get("base_station", "?")
                transfer = entry.get("max_transfer", "?")
                header_title = f"{matched}駅"
                header_detail = f"乗換{transfer}回 / {total}駅 / {img_count}枚"

            st.markdown(f"""<div style="background:#f8f9fa;border:1px solid #e0e0e0;border-radius:10px;
                padding:0.8rem 1.2rem;margin-top:0.8rem;display:flex;align-items:center;justify-content:space-between;">
                <div>
                    <span style="font-weight:700;font-size:1rem;">{header_title}</span>
                    <span style="color:#888;font-size:0.82rem;margin-left:0.6rem;">{header_detail}</span>
                </div>
                <span style="color:#aaa;font-size:0.75rem;">{dl_at}</span>
            </div>""", unsafe_allow_html=True)

            # 画像ディレクトリ
            img_dir = os.path.join(lib_dir, "images") if lib_dir else ""
            all_img_files = []
            if img_dir and os.path.isdir(img_dir):
                all_img_files = [f for f in os.listdir(img_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]

            # 操作ボタン行
            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1:
                if st.button("▼ 閉じる" if is_open else "▶ 詳細を見る", type="primary", use_container_width=True, key=f"{entry_id}a"):
                    st.session_state[toggle_key] = not is_open
                    st.rerun()
            with bc2:
                # 全保存ZIP
                if all_img_files:
                    buf_all = io.BytesIO()
                    with zipfile.ZipFile(buf_all, "w", zipfile.ZIP_DEFLATED) as zf:
                        for fname in all_img_files:
                            zf.write(os.path.join(img_dir, fname), fname)
                    buf_all.seek(0)
                    if lib_type == "city":
                        zip_name = f"{entry.get('prefecture', '')}_{entry.get('city', '')}_{entry_id}.zip"
                    else:
                        matched = entry.get("matched_station") or entry.get("base_station", "?")
                        transfer = entry.get("max_transfer", "?")
                        zip_name = f"{matched}_乗換{transfer}回_{entry_id}.zip"
                    st.download_button(
                        f"全保存（{len(all_img_files)}枚）",
                        data=buf_all, file_name=zip_name, mime="application/zip",
                        use_container_width=True,
                        key=f"{entry_id}b",
                    )
            with bc3:
                # 選択のみZIP — 展開時のみ有効
                if is_open and all_img_files:
                    # 全駅を集める
                    _all_st = []
                    for rw in entry.get("railways", []):
                        _all_st.extend(rw.get("stations", []))
                    if not _all_st:
                        _all_st = entry.get("stations", [])
                    # チェック済みの駅名を収集
                    _checked_names = set()
                    for s in _all_st:
                        sn = s.get("name", "")
                        if st.session_state.get(f"lib_cb_{entry_id}_{sn}", True):
                            _checked_names.add(sn)
                    # チェック済み駅の画像を収集
                    _sel_imgs = []
                    for s in _all_st:
                        sn = s.get("name", "")
                        if sn not in _checked_names:
                            continue
                        for img_p in s.get("image_path", []):
                            abs_p = resolve_image_path(img_p, lib_dir)
                            if os.path.exists(abs_p):
                                _sel_imgs.append((abs_p, os.path.basename(abs_p)))
                    if _sel_imgs:
                        buf_sel = io.BytesIO()
                        with zipfile.ZipFile(buf_sel, "w", zipfile.ZIP_DEFLATED) as zf:
                            for fpath, arcname in _sel_imgs:
                                zf.write(fpath, arcname)
                        buf_sel.seek(0)
                        st.download_button(
                            f"選択のみ（{len(_sel_imgs)}枚）",
                            data=buf_sel, file_name=f"selected_{entry_id}.zip", mime="application/zip",
                            use_container_width=True,
                            key=f"{entry_id}b_sel",
                        )
                    else:
                        st.button("選択なし", disabled=True, use_container_width=True, key=f"{entry_id}b_sel_empty")
            with bc4:
                if st.button("削除する", use_container_width=True, key=f"{entry_id}c"):
                    import shutil
                    if lib_dir and os.path.isdir(lib_dir):
                        shutil.rmtree(lib_dir)
                    st.rerun()

            # 展開時のみ中身を表示（チェックボックス付き）
            if is_open:
                railways = entry.get("railways", [])
                all_stations = []
                if railways:
                    for rw in railways:
                        rw_name = rw.get("railway", "不明")
                        rw_stations = rw.get("stations", [])
                        if rw_stations:
                            st.markdown(f"**{rw_name}**（{len(rw_stations)}駅）")
                            all_stations.extend(rw_stations)
                else:
                    all_stations = entry.get("stations", [])

                # 全選択/全解除
                _lsel1, _lsel2, _lsel3 = st.columns([1, 1, 2])
                with _lsel1:
                    if st.button("全選択", use_container_width=True, key=f"lib_selall_{entry_id}"):
                        for s in all_stations:
                            st.session_state[f"lib_cb_{entry_id}_{s.get('name','')}"] = True
                        st.rerun()
                with _lsel2:
                    if st.button("全解除", use_container_width=True, key=f"lib_deselall_{entry_id}"):
                        for s in all_stations:
                            st.session_state[f"lib_cb_{entry_id}_{s.get('name','')}"] = False
                        st.rerun()

                lib_cols = st.columns(3)
                for si, s in enumerate(all_stations):
                    with lib_cols[si % 3]:
                        s_name = s.get("name", "不明")
                        cb_key = f"lib_cb_{entry_id}_{s_name}"
                        st.checkbox(s_name, value=st.session_state.get(cb_key, True), key=cb_key, label_visibility="collapsed")
                        is_checked = st.session_state.get(cb_key, True)

                        # バッジ: 市区別 vs 駅別
                        if lib_type == "city":
                            badge_parts = []
                            lc = s.get("line_count")
                            if lc:
                                badge_parts.append(f"{lc}路線")
                            pax = s.get("passengers")
                            if pax is not None:
                                if pax >= 10000:
                                    badge_parts.append(f"約{pax // 10000}万人/日")
                                else:
                                    badge_parts.append(f"{pax:,}人/日")
                            badge = " / ".join(badge_parts)
                        else:
                            t_time = s.get("travel_time")
                            badge = f"約{t_time}分" if t_time else ""
                        checked_style = "" if is_checked else "opacity:0.4;"
                        st.markdown(f'''<div class="st-card" style="{checked_style}">
                            <div class="st-name">{s_name}</div>
                            <span class="st-badge">{badge}</span>
                        </div>''', unsafe_allow_html=True)
                        if is_checked:
                            for img_p in s.get("image_path", []):
                                abs_p = resolve_image_path(img_p, lib_dir)
                                if os.path.exists(abs_p):
                                    st.image(abs_p, use_container_width=True)

            st.markdown("")


# ===================================================
# 保管庫ページ
# ===================================================

elif page == "保管庫":
    st.session_state["_prev_page"] = "保管庫"
    st.markdown('<div class="page-sub">検索時に取得した画像が駅別に自動保管されます</div>', unsafe_allow_html=True)

    from config import IMAGE_CACHE_DIR
    from image_fetcher import load_all_cache_meta

    all_cache = load_all_cache_meta()

    if not all_cache:
        st.info("保管庫にはまだ画像がありません。検索で画像を取得すると自動的に保管されます。")
    else:
        # --- 統計 + 全削除 ---
        all_rw_set = set()
        all_pref_set = set()
        for m in all_cache:
            for rw in m.get("railways", []):
                all_rw_set.add(rw)
            pref = m.get("prefecture", "")
            if pref:
                all_pref_set.add(pref)

        cc1, cc2, cc3 = st.columns([1, 1, 1])
        with cc1:
            st.markdown(f'<div class="num-card"><div class="num">{len(all_cache)}</div><div class="num-label">保管駅数</div></div>', unsafe_allow_html=True)
        with cc2:
            st.markdown(f'<div class="num-card"><div class="num">{len(all_rw_set)}</div><div class="num-label">路線数</div></div>', unsafe_allow_html=True)
        with cc3:
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("全て削除", use_container_width=True, key="cache_delete_all"):
                st.session_state["_cache_delete_confirm"] = True
                st.rerun()

        # --- 削除パスワード確認 ---
        if st.session_state.get("_cache_delete_confirm"):
            st.warning("保管庫を全て削除します。パスワードを入力してください。")
            _dc1, _dc2, _dc3 = st.columns([2, 1, 1])
            with _dc1:
                del_pw = st.text_input("削除パスワード", type="password", key="_cache_del_pw", label_visibility="collapsed")
            with _dc2:
                if st.button("削除実行", type="primary", use_container_width=True, key="_cache_del_exec"):
                    if del_pw == APP_DELETE_PASSWORD:
                        import shutil
                        if os.path.isdir(IMAGE_CACHE_DIR):
                            shutil.rmtree(IMAGE_CACHE_DIR)
                        st.session_state.pop("_cache_delete_confirm", None)
                        st.rerun()
                    else:
                        st.error("パスワードが違います")
            with _dc3:
                if st.button("キャンセル", use_container_width=True, key="_cache_del_cancel"):
                    st.session_state.pop("_cache_delete_confirm", None)
                    st.rerun()

        # --- 検索 + フィルタ ---
        search_q = st.text_input("駅名で検索", placeholder="例: 渋谷、新宿", key="cache_search")

        # 路線フィルタ
        all_railways_sorted = sorted(all_rw_set) if all_rw_set else []
        if all_railways_sorted:
            selected_rw = st.multiselect("路線でフィルタ", all_railways_sorted, key="cache_rw_filter")
        else:
            selected_rw = []

        # 都道府県フィルタ
        all_pref_sorted = sorted(all_pref_set) if all_pref_set else []
        if all_pref_sorted:
            selected_pref = st.multiselect("都道府県でフィルタ", all_pref_sorted, key="cache_pref_filter")
        else:
            selected_pref = []

        # --- フィルタ適用 ---
        filtered = all_cache
        has_filter = bool(search_q) or bool(selected_rw) or bool(selected_pref)
        if search_q:
            q = search_q.strip()
            filtered = [
                m for m in filtered
                if q in m.get("name", "")
                or q in m.get("prefecture", "")
                or q in m.get("city", "")
                or any(q in rw for rw in m.get("railways", []))
            ]
        if selected_rw:
            filtered = [
                m for m in filtered
                if any(rw in selected_rw for rw in m.get("railways", []))
            ]
        if selected_pref:
            filtered = [
                m for m in filtered
                if m.get("prefecture", "") in selected_pref
            ]

        st.caption(f"{len(filtered)} / {len(all_cache)}駅")

        # --- 表示切り替え: フィルタなし → フォルダビュー / フィルタあり → カードビュー ---
        if not filtered:
            st.info("該当する駅がありません")
        elif not has_filter:
            # ========== フォルダビュー（デフォルト: 画像非表示） ==========
            # 路線別にグループ化
            rw_groups = {}  # 路線名 -> [meta, ...]
            no_railway = []
            for m in filtered:
                rws = m.get("railways", [])
                if rws:
                    for rw in rws:
                        rw_groups.setdefault(rw, []).append(m)
                else:
                    no_railway.append(m)

            for rw_name in sorted(rw_groups.keys()):
                members = rw_groups[rw_name]
                station_names = [m.get("name", "不明") for m in members]
                st.markdown(f'''<div class="folder-item">
                    <span style="font-size:1.1rem;margin-right:0.5rem;">🚃</span>
                    <span style="font-weight:600;font-size:0.92rem;">{rw_name}</span>
                    <span class="folder-count">{len(members)}駅</span>
                </div>''', unsafe_allow_html=True)
                st.markdown(f'<div style="padding:0.3rem 1rem 0.6rem 2.2rem;color:#666;font-size:0.82rem;">{" / ".join(station_names)}</div>', unsafe_allow_html=True)

            if no_railway:
                station_names = [m.get("name", "不明") for m in no_railway]
                st.markdown(f'''<div class="folder-item">
                    <span style="font-size:1.1rem;margin-right:0.5rem;">📁</span>
                    <span style="font-weight:600;font-size:0.92rem;">その他</span>
                    <span class="folder-count">{len(no_railway)}駅</span>
                </div>''', unsafe_allow_html=True)
                st.markdown(f'<div style="padding:0.3rem 1rem 0.6rem 2.2rem;color:#666;font-size:0.82rem;">{" / ".join(station_names)}</div>', unsafe_allow_html=True)

        else:
            # ========== カードビュー（フィルタ適用時: 既存の詳細表示） ==========
            # チェック数の集計
            _total_checked = sum(
                1 for m in all_cache
                if st.session_state.get(f"cache_cb_{m.get('name','')}", False)
            )

            # 操作ボタン
            _bulk_col1, _bulk_col2, _bulk_col3 = st.columns([1, 1, 2])
            with _bulk_col1:
                if st.button("表示を全選択", use_container_width=True, key="cache_sel_all"):
                    for m in filtered:
                        st.session_state[f"cache_cb_{m.get('name','')}"] = True
                    st.rerun()
            with _bulk_col2:
                if st.button("表示を全解除", use_container_width=True, key="cache_desel_all"):
                    for m in filtered:
                        st.session_state[f"cache_cb_{m.get('name','')}"] = False
                    st.rerun()
            with _bulk_col3:
                _sel_files = []
                for m in all_cache:
                    cb_key = f"cache_cb_{m.get('name','')}"
                    if st.session_state.get(cb_key, False):
                        d = m.get("_dir", "")
                        if d and os.path.isdir(d):
                            for f in os.listdir(d):
                                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                    _sel_files.append((os.path.join(d, f), f"{m.get('name','')}/{f}"))
                if _sel_files:
                    _bulk_buf = io.BytesIO()
                    with zipfile.ZipFile(_bulk_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for fpath, arcname in _sel_files:
                            zf.write(fpath, arcname)
                    _bulk_buf.seek(0)
                    st.download_button(
                        f"選択をDL（{_total_checked}駅 / {len(_sel_files)}枚）",
                        data=_bulk_buf, file_name="保管庫.zip", mime="application/zip",
                        use_container_width=True, key="cache_bulk_dl",
                    )
                else:
                    st.button("選択なし", disabled=True, use_container_width=True, key="cache_bulk_dl_empty")

            cache_cols = st.columns(3)
            for ci, meta in enumerate(filtered):
                name = meta.get("name", "不明")
                railways = meta.get("railways", [])
                passengers = meta.get("passengers")
                line_count = meta.get("line_count")
                prefecture = meta.get("prefecture", "")
                city_name = meta.get("city", "")
                cached_at = meta.get("cached_at", "")
                cache_path = meta.get("_dir", "")

                badge_parts = []
                if railways:
                    badge_parts.append(" / ".join(railways))
                elif line_count:
                    badge_parts.append(f"{line_count}路線")
                if passengers:
                    if passengers >= 10000:
                        badge_parts.append(f"約{passengers // 10000}万人/日")
                    else:
                        badge_parts.append(f"{passengers:,}人/日")
                if prefecture or city_name:
                    badge_parts.append(f"{prefecture}{city_name}")
                badge_text = " / ".join(badge_parts)

                img_files = []
                if cache_path and os.path.isdir(cache_path):
                    img_files = sorted(
                        f for f in os.listdir(cache_path)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                    )

                with cache_cols[ci % 3]:
                    cb_key = f"cache_cb_{name}"
                    st.checkbox(name, value=st.session_state.get(cb_key, False), key=cb_key, label_visibility="collapsed")

                    checked_style = "" if st.session_state.get(cb_key, False) else "opacity:0.4;"
                    st.markdown(f'''<div class="st-card" style="{checked_style}">
                        <div class="st-name">{name}</div>
                        <span class="st-badge cached">{badge_text}</span>
                        <div style="font-size:0.65rem;color:#bbb;margin-top:0.3rem;">{cached_at}</div>
                    </div>''', unsafe_allow_html=True)

                    if img_files:
                        toggle_key = f"_cache_open_{name}"
                        is_open = st.session_state.get(toggle_key, False)
                        if st.button(
                            "▼ 閉じる" if is_open else "▶ 画像を見る",
                            key=f"cache_toggle_{ci}",
                            use_container_width=True,
                        ):
                            st.session_state[toggle_key] = not is_open
                            st.rerun()

                        if is_open:
                            for img_name in img_files:
                                st.image(os.path.join(cache_path, img_name), use_container_width=True)

                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                            for fname in img_files:
                                zf.write(os.path.join(cache_path, fname), fname)
                        buf.seek(0)
                        st.download_button(
                            f"保存（{len(img_files)}枚）",
                            data=buf, file_name=f"{name}.zip", mime="application/zip",
                            use_container_width=True, key=f"cache_dl_{ci}",
                        )


# ===================================================
# ダウンロード中の自動更新
# ===================================================

if _is_downloading():
    time.sleep(0.5)
    st.rerun()
