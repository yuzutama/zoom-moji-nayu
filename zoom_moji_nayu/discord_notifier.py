"""Discord Webhook通知モジュール"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(
        self,
        meeting_topic: str,
        gdocs_url: str,
        recording_url: str,
    ) -> None:
        """Discord Webhookで会議の処理完了を通知する。"""
        lines = [
            f"**会議文字起こし完了: {meeting_topic}**",
            f"議事録: {gdocs_url}",
        ]
        if recording_url:
            lines.append(f"録画: {recording_url}")

        content = "\n".join(lines)

        try:
            resp = requests.post(
                self.webhook_url,
                json={"content": content},
            )
            resp.raise_for_status()
            logger.info("Discord notification sent for: %s", meeting_topic)
        except Exception as e:
            logger.error("Failed to send Discord notification: %s", e)

    def notify_error(
        self,
        meeting_topic: str,
        error_message: str,
    ) -> None:
        """Discord Webhookで処理エラーを通知する。"""
        payload = {
            "embeds": [
                {
                    "title": f"処理エラー: {meeting_topic}",
                    "description": error_message,
                    "color": 0xFF0000,
                }
            ]
        }

        try:
            resp = requests.post(self.webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Discord error notification sent for: %s", meeting_topic)
        except Exception as e:
            logger.error("Failed to send Discord error notification: %s", e)
