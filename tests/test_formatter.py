"""VTTパース・Markdown整形のテスト"""

import textwrap

from zoom_moji_nayu.formatter import parse_vtt, format_transcript_markdown, format_full_document, MeetingMetadata, SummaryData


class TestParseVtt:
    def test_basic_vtt_with_speakers(self):
        vtt_text = textwrap.dedent("""\
            WEBVTT

            1
            00:00:00.000 --> 00:00:05.500
            田中太郎: えーと、今日はですね

            2
            00:00:05.500 --> 00:00:12.000
            鈴木花子: はい、よろしくお願いします
        """)
        segments = parse_vtt(vtt_text)
        assert len(segments) == 2
        assert segments[0].speaker == "田中太郎"
        assert segments[0].text == "えーと、今日はですね"
        assert segments[0].start == "00:00:00"
        assert segments[0].end == "00:00:05"
        assert segments[1].speaker == "鈴木花子"
        assert segments[1].text == "はい、よろしくお願いします"

    def test_vtt_without_speakers(self):
        vtt_text = textwrap.dedent("""\
            WEBVTT

            1
            00:00:00.000 --> 00:00:05.500
            えーと、今日はですね
        """)
        segments = parse_vtt(vtt_text)
        assert len(segments) == 1
        assert segments[0].speaker == ""
        assert segments[0].text == "えーと、今日はですね"

    def test_merge_consecutive_same_speaker(self):
        vtt_text = textwrap.dedent("""\
            WEBVTT

            1
            00:00:00.000 --> 00:00:03.000
            田中太郎: 今日は

            2
            00:00:03.000 --> 00:00:06.000
            田中太郎: よろしくお願いします

            3
            00:00:06.000 --> 00:00:10.000
            鈴木花子: こちらこそ
        """)
        segments = parse_vtt(vtt_text)
        assert len(segments) == 2
        assert segments[0].speaker == "田中太郎"
        assert segments[0].text == "今日は\nよろしくお願いします"
        assert segments[0].start == "00:00:00"
        assert segments[0].end == "00:00:06"


class TestFormatFullDocument:
    def test_full_document_with_summary(self):
        vtt_text = textwrap.dedent("""\
            WEBVTT

            1
            00:00:00.000 --> 00:00:05.500
            田中太郎: えーと、今日はですね

            2
            00:00:05.500 --> 00:00:12.000
            鈴木花子: はい、よろしくお願いします
        """)
        segments = parse_vtt(vtt_text)
        metadata = MeetingMetadata(
            date="2026-02-15 10:00",
            topic="週次定例ミーティング",
            participants=["田中太郎", "鈴木花子"],
            recording_url="https://zoom.us/rec/share/abc123",
        )
        summary = SummaryData(
            summary="今日の定例会議の概要です。",
            chapters="- 議題A: 新機能のリリース日について議論",
        )
        md = format_full_document(segments, metadata, summary)
        assert "# 会議議事録" in md
        assert "週次定例ミーティング" in md
        assert "https://zoom.us/rec/share/abc123" in md
        assert "## 要約" in md
        assert "今日の定例会議の概要です。" in md
        assert "## トピック" in md
        assert "## 文字起こし" in md
        assert "### 00:00:00 - 00:00:05" in md
        assert "**田中太郎**" in md

    def test_full_document_without_summary(self):
        vtt_text = textwrap.dedent("""\
            WEBVTT

            1
            00:00:00.000 --> 00:00:05.500
            田中太郎: テスト
        """)
        segments = parse_vtt(vtt_text)
        metadata = MeetingMetadata(
            date="2026-02-15 10:00",
            topic="テスト会議",
            participants=["田中太郎"],
            recording_url="",
        )
        md = format_full_document(segments, metadata, summary=None)
        assert "# 会議議事録" in md
        assert "## 文字起こし" in md
        assert "## 要約" not in md
