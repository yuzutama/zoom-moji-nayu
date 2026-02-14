"""Gemini API要約・議事録生成のテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.summarizer import Summarizer, parse_summary_response
from zoom_moji_nayu.formatter import SummaryData


class TestParseSummaryResponse:
    def test_parse_well_formed_response(self):
        response_text = """## 要約
今日の会議では新機能のリリーススケジュールを議論しました。

## 議題・決定事項
- 新機能Aのリリース日を2月末に決定
- テスト期間を1週間確保する

## TODO / アクションアイテム
- [ ] 田中: デザイン確認（2/20まで）
- [ ] 鈴木: テストケース作成（2/22まで）"""

        result = parse_summary_response(response_text)
        assert isinstance(result, SummaryData)
        assert "新機能のリリーススケジュール" in result.summary
        assert "2月末に決定" in result.agenda_decisions
        assert "田中: デザイン確認" in result.todos

    def test_parse_empty_response(self):
        result = parse_summary_response("")
        assert result is None


class TestSummarizer:
    @patch("zoom_moji_nayu.summarizer.genai")
    def test_summarize(self, mock_genai):
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value = MagicMock(
            text="""## 要約
テスト要約です。

## 議題・決定事項
- テスト議題

## TODO / アクションアイテム
- [ ] テストTODO"""
        )

        summarizer = Summarizer(api_key="test_key")
        result = summarizer.summarize("田中: テスト発言です")
        assert result is not None
        assert "テスト要約" in result.summary

    @patch("zoom_moji_nayu.summarizer.genai")
    def test_summarize_api_failure_returns_none(self, mock_genai):
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.side_effect = Exception("API error")

        summarizer = Summarizer(api_key="test_key")
        result = summarizer.summarize("テスト")
        assert result is None
