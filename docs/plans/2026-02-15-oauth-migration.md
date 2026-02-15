# OAuth 2.0 ユーザー認証移行 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Google Docsクライアントの認証をサービスアカウント+ドメイン委任からOAuth 2.0リフレッシュトークン方式に切り替え、storageQuotaExceeded / PERMISSION_DENIEDエラーを解消する

**Architecture:** gdocs_client.pyの認証部分のみを変更する。google.oauth2.service_account.Credentialsをgoogle.oauth2.credentials.Credentialsに差し替え、リフレッシュトークンからアクセストークンを自動更新する方式にする。ドキュメント作成ロジック（create_document, _markdown_to_docs_requests）は変更しない。初回トークン取得用のスクリプトを別途作成する。

**Tech Stack:** google-auth, google-api-python-client, google-auth-oauthlib（トークン取得スクリプトのみ）

---

### Task 1: gdocs_client.pyのテストをOAuth認証に更新

**Files:**
- Modify: `tests/test_gdocs_client.py`

**Step 1: テストをOAuth認証用に書き換え**

`tests/test_gdocs_client.py` の全内容を以下に置き換える。

```python
"""Google Docsクライアントのテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.gdocs_client import GDocsClient


class TestGDocsClient:
    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_create_document(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_docs = MagicMock()
        mock_drive = MagicMock()
        mock_build.side_effect = lambda service, version, credentials: (
            mock_docs if service == "docs" else mock_drive
        )
        mock_docs.documents().create().execute.return_value = {
            "documentId": "doc_123"
        }
        mock_drive.files().get().execute.return_value = {"parents": ["root"]}

        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        doc_id = client.create_document(
            title="テストドキュメント",
            markdown_content="# テスト\n\nコンテンツ",
        )
        assert doc_id == "doc_123"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_get_document_url(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        url = client.get_document_url("doc_123")
        assert url == "https://docs.google.com/document/d/doc_123/edit"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_build_requests_heading(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        requests = client._markdown_to_docs_requests("# 見出し\n\n本文テキスト\n")
        insert_texts = [r for r in requests if "insertText" in r]
        assert len(insert_texts) >= 2

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_credentials_created_with_refresh_token(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        GDocsClient(
            client_id="my_client_id",
            client_secret="my_secret",
            refresh_token="my_token",
            folder_id="folder_abc",
        )
        mock_creds_cls.assert_called_once_with(
            token=None,
            refresh_token="my_token",
            client_id="my_client_id",
            client_secret="my_secret",
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ],
        )
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_gdocs_client.py -v`
Expected: FAIL（GDocsClientのコンストラクタが古い引数のため）

**Step 3: gdocs_client.pyの認証部分を変更**

`zoom_moji_nayu/gdocs_client.py` の変更箇所

import文を変更（9行目）:
```python
# 変更前
from google.oauth2.service_account import Credentials

# 変更後
from google.oauth2.credentials import Credentials
```

コンストラクタを変更（22-30行目）:
```python
# 変更前
class GDocsClient:
    def __init__(self, service_account_info: dict, folder_id: str, impersonate_email: str = ""):
        creds = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        if impersonate_email:
            creds = creds.with_subject(impersonate_email)
        self.docs_service = build("docs", "v1", credentials=creds)
        self.drive_service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id

# 変更後
class GDocsClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, folder_id: str):
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        self.docs_service = build("docs", "v1", credentials=creds)
        self.drive_service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id
```

**Step 4: テストを実行して成功を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_gdocs_client.py -v`
Expected: 4 passed

**Step 5: コミット**

```bash
git add tests/test_gdocs_client.py zoom_moji_nayu/gdocs_client.py
git commit -m "feat: GDocsClientの認証をOAuthリフレッシュトークン方式に変更"
```

---

### Task 2: config.pyをOAuth用環境変数に更新

**Files:**
- Modify: `zoom_moji_nayu/config.py:15-21`

**Step 1: config.pyのget_google_configを変更**

```python
# 変更前（15-21行目）
def get_google_config() -> dict:
    """Google API設定を環境変数から取得する。"""
    return {
        "service_account_json": os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        "drive_folder_id": os.environ["GOOGLE_DRIVE_FOLDER_ID"],
        "impersonate_email": os.environ.get("GOOGLE_IMPERSONATE_EMAIL", ""),
    }

# 変更後
def get_google_config() -> dict:
    """Google API設定を環境変数から取得する。"""
    return {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "drive_folder_id": os.environ["GOOGLE_DRIVE_FOLDER_ID"],
    }
```

**Step 2: テストを実行**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_gdocs_client.py -v`
Expected: 4 passed（config.pyの変更はテストに影響しない）

**Step 3: コミット**

```bash
git add zoom_moji_nayu/config.py
git commit -m "feat: Google API設定をOAuth用環境変数に変更"
```

---

### Task 3: __main__.pyのGDocsClient初期化を更新

**Files:**
- Modify: `zoom_moji_nayu/__main__.py:5-6,159-166`

**Step 1: __main__.pyを変更**

import部分（5-6行目）から不要なimportを削除:
```python
# 変更前
import base64
import json

# 変更後
import json
```

main()関数のGDocsClient初期化部分（159-166行目）を変更:
```python
# 変更前
    sa_info = json.loads(base64.b64decode(google_config["service_account_json"]))

    zoom = ZoomClient(**zoom_config)
    gdocs = GDocsClient(
        service_account_info=sa_info,
        folder_id=google_config["drive_folder_id"],
        impersonate_email=google_config["impersonate_email"],
    )

# 変更後
    zoom = ZoomClient(**zoom_config)
    gdocs = GDocsClient(
        client_id=google_config["client_id"],
        client_secret=google_config["client_secret"],
        refresh_token=google_config["refresh_token"],
        folder_id=google_config["drive_folder_id"],
    )
```

**Step 2: 全テストを実行**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/ -v`
Expected: ALL passed（test_main.pyはGDocsClientをMagicMockで渡しているため影響なし）

**Step 3: コミット**

```bash
git add zoom_moji_nayu/__main__.py
git commit -m "feat: __main__.pyのGDocsClient初期化をOAuth方式に更新"
```

---

### Task 4: GitHub Actionsワークフローの環境変数を更新

**Files:**
- Modify: `.github/workflows/zoom-transcript.yml:30-36`

**Step 1: ワークフローの環境変数を変更**

Run syncステップのenv部分（30-36行目）を変更:
```yaml
# 変更前
        env:
          ZOOM_ACCOUNT_ID: ${{ secrets.ZOOM_ACCOUNT_ID }}
          ZOOM_CLIENT_ID: ${{ secrets.ZOOM_CLIENT_ID }}
          ZOOM_CLIENT_SECRET: ${{ secrets.ZOOM_CLIENT_SECRET }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
          GOOGLE_IMPERSONATE_EMAIL: ${{ secrets.GOOGLE_IMPERSONATE_EMAIL }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}

# 変更後
        env:
          ZOOM_ACCOUNT_ID: ${{ secrets.ZOOM_ACCOUNT_ID }}
          ZOOM_CLIENT_ID: ${{ secrets.ZOOM_CLIENT_ID }}
          ZOOM_CLIENT_SECRET: ${{ secrets.ZOOM_CLIENT_SECRET }}
          GOOGLE_CLIENT_ID: ${{ secrets.GOOGLE_CLIENT_ID }}
          GOOGLE_CLIENT_SECRET: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          GOOGLE_REFRESH_TOKEN: ${{ secrets.GOOGLE_REFRESH_TOKEN }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
```

**Step 2: 全テストを実行（ワークフロー変更がコードに影響しないことを確認）**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/ -v`
Expected: ALL passed

**Step 3: コミット**

```bash
git add .github/workflows/zoom-transcript.yml
git commit -m "feat: GitHub Actionsの環境変数をOAuth方式に更新"
```

---

### Task 5: リフレッシュトークン取得スクリプトを作成

**Files:**
- Create: `scripts/get_refresh_token.py`

**Step 1: スクリプトを作成**

`scripts/get_refresh_token.py`:
```python
"""Google OAuth 2.0 リフレッシュトークン取得スクリプト

使い方:
    1. GCPコンソールで OAuth クライアントID（デスクトップアプリ）を作成
    2. クライアントIDとシークレットをメモ
    3. このスクリプトを実行:
       pip install google-auth-oauthlib
       python scripts/get_refresh_token.py
    4. ブラウザでGoogleログイン＆同意
    5. 表示されたリフレッシュトークンをGitHub Secretsに設定
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def main():
    client_id = input("OAuth Client ID: ").strip()
    client_secret = input("OAuth Client Secret: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print()
    print("=== リフレッシュトークン ===")
    print(creds.refresh_token)
    print()
    print("このトークンをGitHub Secretsの GOOGLE_REFRESH_TOKEN に設定してください。")
    print("GOOGLE_CLIENT_ID と GOOGLE_CLIENT_SECRET も同様に設定してください。")


if __name__ == "__main__":
    main()
```

**Step 2: コミット**

```bash
git add scripts/get_refresh_token.py
git commit -m "feat: OAuthリフレッシュトークン取得スクリプトを追加"
```

---

### Task 6: GCPセットアップとトークン取得（手動）

**この作業はコード変更ではなく、手動で行うGCPの設定です。**

**Step 1: GCPでOAuth同意画面を設定**

1. https://console.cloud.google.com/apis/credentials/consent?project=zoom-487417 を開く
2. User Type: 内部（Internal）を選択（amasato.co.jpドメイン内のみ）
3. アプリ名: zoom-moji-nayu
4. スコープを追加: Google Docs API, Google Drive API

**Step 2: OAuthクライアントIDを作成**

1. https://console.cloud.google.com/apis/credentials?project=zoom-487417 を開く
2. 「認証情報を作成」→「OAuthクライアントID」
3. アプリケーションの種類: デスクトップアプリ
4. 名前: zoom-moji-nayu-oauth
5. クライアントIDとシークレットをメモ

**Step 3: リフレッシュトークンを取得**

```bash
cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu
pip install google-auth-oauthlib
python scripts/get_refresh_token.py
```

nagase@amasato.co.jpでログインし、スコープに同意する。表示されたリフレッシュトークンをコピー。

**Step 4: GitHub Secretsを設定**

```bash
gh secret set GOOGLE_CLIENT_ID --body "（コピーしたクライアントID）"
gh secret set GOOGLE_CLIENT_SECRET --body "（コピーしたクライアントシークレット）"
gh secret set GOOGLE_REFRESH_TOKEN --body "（コピーしたリフレッシュトークン）"
```

不要になったSecretsを削除:
```bash
gh secret delete GOOGLE_SERVICE_ACCOUNT_JSON
gh secret delete GOOGLE_IMPERSONATE_EMAIL
```

**Step 5: ワークフローを手動実行してテスト**

```bash
gh workflow run "Zoom Transcript Sync"
gh run list --workflow="Zoom Transcript Sync" --limit 1
```
