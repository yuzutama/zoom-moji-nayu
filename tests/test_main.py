"""メイン処理のテスト"""

import json
from unittest.mock import patch, MagicMock

from zoom_moji_nayu.__main__ import load_processed, save_processed, process_recordings


class TestProcessedManagement:
    def test_load_processed_empty(self, tmp_path):
        path = tmp_path / "processed.json"
        path.write_text('{"processed_ids": []}')
        ids = load_processed(str(path))
        assert ids == []

    def test_load_processed_with_ids(self, tmp_path):
        path = tmp_path / "processed.json"
        path.write_text('{"processed_ids": ["id1", "id2"]}')
        ids = load_processed(str(path))
        assert ids == ["id1", "id2"]

    def test_save_processed(self, tmp_path):
        path = tmp_path / "processed.json"
        save_processed(str(path), ["id1", "id2", "id3"])
        data = json.loads(path.read_text())
        assert data["processed_ids"] == ["id1", "id2", "id3"]


class TestProcessRecordings:
    @patch("zoom_moji_nayu.__main__.DiscordNotifier")
    @patch("zoom_moji_nayu.__main__.Summarizer")
    @patch("zoom_moji_nayu.__main__.GDocsClient")
    @patch("zoom_moji_nayu.__main__.ZoomClient")
    def test_skip_already_processed(self, MockZoom, MockGDocs, MockSummarizer, MockDiscord):
        mock_zoom = MockZoom.return_value
        mock_zoom.get_recordings.return_value = [
            {
                "uuid": "meeting_123",
                "topic": "テスト会議",
                "start_time": "2026-02-15T10:00:00Z",
                "share_url": "https://zoom.us/rec/share/abc",
                "recording_files": [
                    {
                        "recording_type": "audio_transcript",
                        "download_url": "https://zoom.us/download",
                    }
                ],
            }
        ]
        processed_ids = ["meeting_123"]
        new_ids = process_recordings(
            mock_zoom, MockGDocs.return_value, MockSummarizer.return_value,
            MockDiscord.return_value, processed_ids,
        )
        assert new_ids == []
        mock_zoom.download_transcript.assert_not_called()

    @patch("zoom_moji_nayu.__main__.DiscordNotifier")
    @patch("zoom_moji_nayu.__main__.Summarizer")
    @patch("zoom_moji_nayu.__main__.GDocsClient")
    @patch("zoom_moji_nayu.__main__.ZoomClient")
    def test_process_new_recording(self, MockZoom, MockGDocs, MockSummarizer, MockDiscord):
        mock_zoom = MockZoom.return_value
        mock_zoom.get_recordings.return_value = [
            {
                "uuid": "meeting_456",
                "topic": "新しい会議",
                "start_time": "2026-02-15T14:00:00Z",
                "share_url": "https://zoom.us/rec/share/xyz",
                "recording_files": [
                    {
                        "recording_type": "audio_transcript",
                        "download_url": "https://zoom.us/download",
                    }
                ],
            }
        ]
        mock_zoom.get_transcript_url.return_value = "https://zoom.us/download"
        mock_zoom.download_transcript.return_value = (
            "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\n田中: テスト\n"
        )
        mock_gdocs = MockGDocs.return_value
        mock_gdocs.create_document.return_value = "doc_abc"
        mock_gdocs.get_document_url.return_value = "https://docs.google.com/document/d/doc_abc/edit"

        from zoom_moji_nayu.formatter import SummaryData
        mock_summarizer = MockSummarizer.return_value
        mock_summarizer.summarize.return_value = SummaryData(
            summary="テスト要約", agenda_decisions="テスト議題", todos="テストTODO"
        )

        mock_discord = MockDiscord.return_value

        new_ids = process_recordings(
            mock_zoom, mock_gdocs, mock_summarizer, mock_discord, [],
        )
        assert new_ids == ["meeting_456"]
        mock_gdocs.create_document.assert_called_once()
        mock_discord.notify.assert_called_once()
