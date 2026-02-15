# OAuth 2.0 ユーザー認証への移行 設計書

## 背景

サービスアカウント + ドメイン全体委任によるGoogle Docs/Drive API呼び出しが以下のエラーで失敗している

- Docs API `documents().create()` → 403 PERMISSION_DENIED
- Drive API `files().create()` → storageQuotaExceeded

nagase@amasato.co.jp のアカウントではブラウザからGoogle Docsを作成可能であるため、ユーザー権限自体には問題がない。サービスアカウント経由のAPI呼び出しがGWSの制限に引っかかっていると推定。

## 方針

サービスアカウント + ドメイン委任を廃止し、OAuth 2.0 ユーザー認証（リフレッシュトークン方式）に切り替える。

## 認証フロー

### 初回セットアップ（手動、1回のみ）

1. GCPプロジェクト（zoom-487417）でOAuth同意画面を設定
2. OAuthクライアントID（デスクトップアプリ）を作成
3. ローカルで `scripts/get_refresh_token.py` を実行
4. nagaseさんがブラウザでGoogleログイン＆スコープ同意
5. 取得したリフレッシュトークンをGitHub Secretsに保存

### 自動実行時（GitHub Actions、毎時）

1. 環境変数からclient_id、client_secret、refresh_tokenを取得
2. google.oauth2.credentials.Credentialsでアクセストークンを自動更新
3. Docs API / Drive APIを通常通り呼び出し

## 変更対象ファイル

### 変更

- `zoom_moji_nayu/gdocs_client.py` - 認証方式をサービスアカウントからOAuthに変更
- `zoom_moji_nayu/config.py` - 環境変数をOAuth用に変更
- `zoom_moji_nayu/__main__.py` - GDocsClient初期化を新しい引数に変更
- `.github/workflows/zoom-transcript.yml` - GitHub Secrets変更
- `tests/test_gdocs_client.py` - モック対象と引数の更新
- `tests/test_main.py` - GDocsClient初期化部分のモック更新

### 新規作成

- `scripts/get_refresh_token.py` - 初回リフレッシュトークン取得スクリプト

### 削除される環境変数

- GOOGLE_SERVICE_ACCOUNT_JSON
- GOOGLE_IMPERSONATE_EMAIL

### 追加される環境変数

- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- GOOGLE_REFRESH_TOKEN

## gdocs_client.py 認証部分の変更

変更前

```python
from google.oauth2.service_account import Credentials
creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
if impersonate_email:
    creds = creds.with_subject(impersonate_email)
```

変更後

```python
from google.oauth2.credentials import Credentials
creds = Credentials(
    token=None,
    refresh_token=refresh_token,
    client_id=client_id,
    client_secret=client_secret,
    token_uri="https://oauth2.googleapis.com/token",
    scopes=SCOPES,
)
```

コンストラクタの引数変更

```python
# 変更前
GDocsClient(service_account_info=dict, folder_id=str, impersonate_email=str)

# 変更後
GDocsClient(client_id=str, client_secret=str, refresh_token=str, folder_id=str)
```

## ドキュメント作成ロジック

変更なし。以下はそのまま維持

- `create_document()` - Docs API create + Drive APIでフォルダ移動
- `_markdown_to_docs_requests()` - Markdown→Docs APIリクエスト変換
- `get_document_url()` - URL生成

## エラーハンドリング

- リフレッシュトークンが無効化された場合 → 401エラー → Discord通知 → スクリプト再実行でトークン再取得
- 既存のリトライロジック（MAX_RETRIES=3、指数バックオフ）は維持

## 依存パッケージ

- 本番コード: `google-auth` のみ（既存、追加不要）
- トークン取得スクリプト: `google-auth-oauthlib`（ローカル実行のみ）
