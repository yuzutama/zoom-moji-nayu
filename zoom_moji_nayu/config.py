"""設定管理モジュール"""

import os


def get_zoom_config() -> dict:
    """Zoom API設定を環境変数から取得する。"""
    return {
        "account_id": os.environ["ZOOM_ACCOUNT_ID"],
        "client_id": os.environ["ZOOM_CLIENT_ID"],
        "client_secret": os.environ["ZOOM_CLIENT_SECRET"],
    }


def get_google_config() -> dict:
    """Google API設定を環境変数から取得する。"""
    return {
        "service_account_json": os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        "drive_folder_id": os.environ["GOOGLE_DRIVE_FOLDER_ID"],
        "impersonate_email": os.environ.get("GOOGLE_IMPERSONATE_EMAIL", ""),
    }



def get_discord_config() -> dict:
    """Discord Webhook設定を環境変数から取得する。"""
    return {
        "webhook_url": os.environ["DISCORD_WEBHOOK_URL"],
    }
