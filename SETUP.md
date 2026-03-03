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

## 3. Google Places API (New) の設定（画像検索に必要）

### 3-1. Google Cloud プロジェクト作成
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成
3. 「APIとサービス」→「ライブラリ」
4. 「**Places API (New)**」を検索して有効化
   - 注意: 旧「Places API」ではなく「**Places API (New)**」を選択

### 3-2. APIキー発行
1. 「APIとサービス」→「認証情報」
2. 「認証情報を作成」→「APIキー」
3. 発行されたキーをコピー

設定方法:
```bash
# 環境変数
export GOOGLE_API_KEY="あなたのAPIキー"

# または config.py を直接編集
GOOGLE_API_KEY = "あなたのAPIキー"
```

### コストについて
- **$300の無料クレジット**（Google Cloud 新規アカウント、90日間有効）
- Text Search: $32 / 1,000リクエスト → 無料枠で約9,300駅分
- Place Photo: $7 / 1,000リクエスト → 無料枠で約42,800枚
- 1駅あたりの合計コスト: 約$0.039（Text Search 1回 + Photo 1回）
- **$300クレジットで約7,600駅分の画像取得が可能**
- 商用利用OK（Google帰属表示が必要）

## 4. APIキーなしで使う場合

### 市区別モード（cityモード）
- Overpass API（OpenStreetMap）を使用 → **APIキー不要**
- すぐに使えます

### 画像取得
- フォールバック順: Wikipedia記事画像 → Google Places API
- Google APIキーが未設定の場合、Wikipedia記事画像のみ使用
- どちらも商用利用OK

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
| Places APIエラー | Places API (New) が有効化されているか確認。APIキーの制限設定を確認 |
| 画像が0枚 | Places APIに写真がない駅。Wikimediaにもヒットしない場合あり |
