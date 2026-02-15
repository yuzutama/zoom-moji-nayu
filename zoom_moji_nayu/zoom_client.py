"""Zoom APIクライアントモジュール"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

ZOOM_OAUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE = "https://api.zoom.us/v2"
MAX_RETRIES = 3


class ZoomClient:
    def __init__(self, account_id: str, client_id: str, client_secret: str):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    def _get_access_token(self) -> str:
        """Server-to-Server OAuthでアクセストークンを取得する。"""
        resp = requests.post(
            ZOOM_OAUTH_URL,
            params={
                "grant_type": "account_credentials",
                "account_id": self.account_id,
            },
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def _ensure_token(self) -> str:
        if not self._token:
            return self._get_access_token()
        return self._token

    def _api_get(self, url: str, **kwargs) -> requests.Response:
        """リトライ付きGETリクエスト。"""
        token = self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}

        for attempt in range(MAX_RETRIES):
            resp = requests.get(url, headers=headers, **kwargs)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Rate limited, waiting %d seconds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp

        resp.raise_for_status()
        return resp

    def get_recordings(self, from_date: str, to_date: str) -> list[dict]:
        """指定期間の録画一覧を取得する。"""
        url = f"{ZOOM_API_BASE}/accounts/me/recordings"
        resp = self._api_get(url, params={"from": from_date, "to": to_date})
        data = resp.json()
        return data.get("meetings", [])

    def download_transcript(self, download_url: str) -> str:
        """VTTファイルをダウンロードする。Bearerヘッダーでリダイレクトを手動処理。"""
        token = self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(download_url, headers=headers, allow_redirects=False)
        if resp.status_code in (301, 302):
            redirect_url = resp.headers["Location"]
            resp = requests.get(redirect_url)
        resp.raise_for_status()
        return resp.text

    def get_transcript_url(self, meeting: dict) -> str | None:
        """録画情報からtranscriptのダウンロードURLを取得する。"""
        for f in meeting.get("recording_files", []):
            if f.get("recording_type") == "audio_transcript":
                return f.get("download_url")
        return None
