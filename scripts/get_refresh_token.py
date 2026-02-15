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
