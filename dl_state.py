"""
ダウンロード進捗 & オンラインユーザーの共有状態（importキャッシュで永続化）
"""
progress = {}

# オンラインユーザー {session_id: {"user_id": str, "last_seen": float}}
online_users = {}
