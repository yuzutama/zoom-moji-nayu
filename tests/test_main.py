"""メイン処理のテスト"""

import json
from unittest.mock import patch, MagicMock

from zoom_moji_nayu.__main__ import (
    load_processed, save_processed, process_recordings, _parse_zoom_summary,
)
from zoom_moji_nayu.formatter import SummaryData


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


class TestParseZoomSummary:
    def test_parse_with_overall_and_items(self):
        data = {
            "overall_summary": "会議の概要です。",
            "items": [
                {"label": "議題A", "summary": "Aについて議論", "start_time": "00:00:00", "end_time": "00:05:00"},
                {"label": "議題B", "summary": "Bを決定", "start_time": "00:05:00", "end_time": "00:10:00"},
            ],
        }
        result = _parse_zoom_summary(data)
        assert isinstance(result, SummaryData)
        assert result.summary == "会議の概要です。"
        assert "議題A: Aについて議論" in result.chapters
        assert "議題B: Bを決定" in result.chapters

    def test_parse_empty_returns_none(self):
        data = {"overall_summary": "", "items": []}
        result = _parse_zoom_summary(data)
        assert result is None

    def test_parse_overall_only(self):
        data = {"overall_summary": "要約のみ", "items": []}
        result = _parse_zoom_summary(data)
        assert result is not None
        assert result.summary == "要約のみ"
        assert result.chapters == ""


class TestProcessRecordings:
    def test_skip_already_processed(self):
        mock_zoom = MagicMock()
        mock_zoom.get_recordings.return_value = [
            {
                "uuid": "meeting_123",
                "topic": "テスト会議",
                "start_time": "2026-02-15T10:00:00Z",
                "share_url": "https://zoom.us/rec/share/abc",
                "recording_files": [
                    {"recording_type": "audio_transcript", "download_url": "https://zoom.us/download"},
                ],
            }
        ]
        processed_ids = ["meeting_123"]
        new_ids = process_recordings(
            mock_zoom, MagicMock(), MagicMock(), processed_ids,
        )
        assert new_ids == []
        mock_zoom.download_transcript.assert_not_called()

    def test_process_new_recording(self):
        mock_zoom = MagicMock()
        mock_zoom.get_recordings.return_value = [
            {
                "uuid": "meeting_456",
                "topic": "新しい会議",
                "start_time": "2026-02-15T14:00:00Z",
                "share_url": "https://zoom.us/rec/share/xyz",
                "recording_files": [
                    {"recording_type": "audio_transcript", "download_url": "https://zoom.us/download/vtt"},
                    {"recording_type": "summary", "download_url": "https://zoom.us/download/summary"},
                ],
            }
        ]
        mock_zoom.get_recording_url.side_effect = lambda m, t: {
            "audio_transcript": "https://zoom.us/download/vtt",
            "summary": "https://zoom.us/download/summary",
        }.get(t)
        mock_zoom.download_transcript.return_value = (
            "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\n田中: テスト\n"
        )
        mock_zoom.download_summary.return_value = {
            "overall_summary": "テスト要約",
            "items": [{"label": "トピック", "summary": "内容", "start_time": "00:00:00", "end_time": "00:05:00"}],
        }

        mock_gdocs = MagicMock()
        mock_gdocs.create_document.return_value = "doc_abc"
        mock_gdocs.get_document_url.return_value = "https://docs.google.com/document/d/doc_abc/edit"

        mock_discord = MagicMock()

        new_ids = process_recordings(
            mock_zoom, mock_gdocs, mock_discord, [],
        )
        assert new_ids == ["meeting_456"]
        mock_gdocs.create_document.assert_called_once()
        mock_discord.notify.assert_called_once()
