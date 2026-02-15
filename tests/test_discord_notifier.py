"""Discord Webhook通知のテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.discord_notifier import DiscordNotifier


class TestDiscordNotifier:
    @patch("zoom_moji_nayu.discord_notifier.requests.post")
    def test_notify_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        notifier.notify(
            meeting_topic="週次定例ミーティング",
            gdocs_url="https://docs.google.com/document/d/abc/edit",
            recording_url="https://zoom.us/rec/share/xyz",
        )
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert "週次定例ミーティング" in payload["content"]
        assert "https://docs.google.com/document/d/abc/edit" in payload["content"]
        assert "https://zoom.us/rec/share/xyz" in payload["content"]

    @patch("zoom_moji_nayu.discord_notifier.requests.post")
    def test_notify_failure_does_not_raise(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        notifier.notify(
            meeting_topic="テスト",
            gdocs_url="https://docs.google.com/test",
            recording_url="",
        )

    @patch("zoom_moji_nayu.discord_notifier.requests.post")
    def test_notify_error_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        notifier.notify_error(
            meeting_topic="エラー会議",
            error_message="API接続タイムアウト",
        )
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["embeds"][0]["title"] == "処理エラー: エラー会議"
        assert payload["embeds"][0]["color"] == 0xFF0000

    @patch("zoom_moji_nayu.discord_notifier.requests.post")
    def test_notify_error_failure_does_not_raise(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        notifier.notify_error(
            meeting_topic="テスト",
            error_message="エラー",
        )
