# セットアップガイド

## 1. Python依存パッケージのインストール

```bash
cd store-traffic-image-collector
pip install -r requirements.txt
```

## 2. ODPT APIキーの取得（駅別モードに必要）

1. [ODPT開発者サイト](https://developer.odpt.org/) にアクセス
2. 「開発者登録」からアカウント作成
3. ログイン後、「アプリケーション登録」から新規アプリを登録
4. 発行されたコンシューマキーをコピー

設定方法（いずれか）:
```bash
# 環境変数
export ODPT_CONSUMER_KEY="あなたのキー"

# または config.py を直接編集
ODPT_CONSUMER_KEY = "あなたのキー"
```

## 3. Google Custom Search APIの設定（画像検索に必要）

### 3-1. Google Cloud プロジェクト作成
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「ライブラリ」
4. 「Custom Search API」を検索して有効化

### 3-2. APIキー発行
1. 「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「APIキー」
3. 発行されたキーをコピー

### 3-3. Programmable Search Engine 作成
1. [Programmable Search Engine](https://programmablesearchengine.google.com/) にアクセス
2. 「新しい検索エンジン」を作成
3. 「検索するサイト」に `*` を入力（ウェブ全体を検索）
4. 「画像検索」をONにする
5. 作成後、「検索エンジンID」をコピー

設定方法:
```bash
# 環境変数
export GOOGLE_API_KEY="あなたのAPIキー"
export GOOGLE_CSE_ID="あなたの検索エンジンID"

# または config.py を直接編集
GOOGLE_API_KEY = "あなたのAPIキー"
GOOGLE_CSE_ID = "あなたの検索エンジンID"
```

### 無料枠について
- Custom Search API: **1日100クエリ無料**
- 超過分: 1,000クエリあたり$5
- 大量実行時は注意

## 4. APIキーなしで使う場合

### 市区別モード（cityモード）
- Overpass API（OpenStreetMap）を使用 → **APIキー不要**
- すぐに使えます

### 画像取得
- Google APIキーが未設定の場合、自動的にWikimedia Commons APIにフォールバック
- Wikimedia Commons → **APIキー不要**
- ただしGoogle検索と比べて駅画像のヒット率は低め

## 5. 使い方

```bash
# 駅別モード（ODPT + Google/Wikimedia）
python main.py --mode station --base 表参道 --transfer 1

# 市区別モード（Overpass + Google/Wikimedia）
python main.py --mode city --pref 東京都 --city 渋谷区
```

## トラブルシューティング

| エラー | 対処法 |
|--------|--------|
| ODPT APIエラー 401 | コンシューマキーを確認 |
| Google APIエラー 403 | APIが有効化されているか確認。無料枠超過の可能性 |
| Overpass APIタイムアウト | 時間を空けて再実行（サーバー混雑時あり） |
| 画像が0枚 | Wikimediaにヒットしない駅名。検索クエリをconfig.pyで調整 |
