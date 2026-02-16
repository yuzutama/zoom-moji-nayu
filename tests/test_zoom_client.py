"""Zoom APIクライアントのテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.zoom_client import ZoomClient


class TestZoomClient:
    def _make_client(self):
        return ZoomClient(
            account_id="test_account",
            client_id="test_client",
            client_secret="test_secret",
        )

    @patch("zoom_moji_nayu.zoom_client.requests.post")
    def test_get_access_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "test_token", "expires_in": 3600},
        )
        client = self._make_client()
        token = client._get_access_token()
        assert token == "test_token"
        mock_post.assert_called_once()

    @patch("zoom_moji_nayu.zoom_client.requests.get")
    @patch("zoom_moji_nayu.zoom_client.requests.post")
    def test_get_recordings(self, mock_post, mock_get):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "test_token", "expires_in": 3600},
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "meetings": [
                    {
                        "uuid": "meeting_123",
                        "topic": "テスト会議",
                        "start_time": "2026-02-15T10:00:00Z",
                        "share_url": "https://zoom.us/rec/share/abc123",
                        "recording_files": [
                            {
                                "id": "file_1",
                                "recording_type": "audio_transcript",
                                "download_url": "https://zoom.us/download/transcript",
                            }
                        ],
                    }
                ]
            },
        )
        client = self._make_client()
        recordings = client.get_recordings(from_date="2026-02-15", to_date="2026-02-15")
        assert len(recordings) == 1
        assert recordings[0]["topic"] == "テスト会議"
        assert recordings[0]["share_url"] == "https://zoom.us/rec/share/abc123"

    @patch("zoom_moji_nayu.zoom_client.requests.get")
    @patch("zoom_moji_nayu.zoom_client.requests.post")
    def test_download_transcript(self, mock_post, mock_get):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "test_token", "expires_in": 3600},
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            text="WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\nテスト",
        )
        client = self._make_client()
        vtt = client.download_transcript("https://zoom.us/download/transcript")
        assert "WEBVTT" in vtt
        assert "テスト" in vtt

    def test_get_recording_url_found(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {"recording_type": "shared_screen", "download_url": "https://zoom.us/video"},
                {"recording_type": "audio_transcript", "download_url": "https://zoom.us/transcript"},
            ]
        }
        assert client.get_recording_url(meeting, "audio_transcript") == "https://zoom.us/transcript"

    def test_get_recording_url_prefers_japanese_transcript(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {
                    "recording_type": "audio_transcript",
                    "language": "en-US",
                    "download_url": "https://zoom.us/transcript-en",
                },
                {
                    "recording_type": "audio_transcript",
                    "language": "ja-JP",
                    "download_url": "https://zoom.us/transcript-ja",
                },
            ]
        }
        assert client.get_recording_url(meeting, "audio_transcript") == "https://zoom.us/transcript-ja"

    def test_get_recording_url_falls_back_when_no_japanese(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {
                    "recording_type": "audio_transcript",
                    "language": "en-US",
                    "download_url": "https://zoom.us/transcript-en",
                },
            ]
        }
        assert client.get_recording_url(meeting, "audio_transcript") == "https://zoom.us/transcript-en"

    def test_get_recording_url_not_found(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {"recording_type": "shared_screen", "download_url": "https://zoom.us/video"},
            ]
        }
        assert client.get_recording_url(meeting, "audio_transcript") is None
