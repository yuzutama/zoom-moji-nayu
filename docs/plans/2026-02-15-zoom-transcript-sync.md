# Zoom文字起こし自動同期ツール 実装計画

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Zoom Cloud APIで録画の文字起こし（VTT）を取得し、Gemini APIで要約・議事録・TODOを生成、Markdown整形してGoogle Docsに自動保存し、Discord Webhookで通知するツールを作る。

**Architecture:** GitHub Actionsで毎時ポーリング実行。Zoom Server-to-Server OAuthで認証し、録画一覧から未処理の文字起こしVTTをダウンロード。VTTをパースしてMarkdownに変換後、Gemini APIで要約・議事録・TODOを生成。全てを統合してGoogle Docs APIでドキュメント作成・フォルダ配置。Discord Webhookで通知。処理済みIDはprocessed.jsonで管理。

**Tech Stack:** Python 3.11+, requests, google-api-python-client, google-auth, google-generativeai, webvtt-py

---

### Task 1: プロジェクト基盤セットアップ

**Files:**
- Create: `zoom_moji_nayu/__init__.py`
- Create: `zoom_moji_nayu/config.py`
- Create: `requirements.txt`
- Create: `processed.json`
- Create: `.gitignore`

**Step 1: requirements.txtを作成**

```
requests>=2.31.0
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-generativeai>=0.8.0
webvtt-py>=0.5.0
```

**Step 2: .gitignoreを作成**

```
__pycache__/
*.pyc
.env
venv/
.venv/
```

**Step 3: processed.jsonを作成**

```json
{
  "processed_ids": []
}
```

**Step 4: __init__.pyを作成**

```python
"""Zoom文字起こし自動同期ツール"""
```

**Step 5: config.pyを作成**

```python
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
    }


def get_gemini_config() -> dict:
    """Gemini API設定を環境変数から取得する。"""
    return {
        "api_key": os.environ["GEMINI_API_KEY"],
    }


def get_discord_config() -> dict:
    """Discord Webhook設定を環境変数から取得する。"""
    return {
        "webhook_url": os.environ["DISCORD_WEBHOOK_URL"],
    }
```

**Step 6: コミット**

```bash
git add zoom_moji_nayu/__init__.py zoom_moji_nayu/config.py requirements.txt processed.json .gitignore
git commit -m "feat: プロジェクト基盤セットアップ"
```

---

### Task 2: VTTパーサー & Markdown整形（TDD）

**Files:**
- Create: `zoom_moji_nayu/formatter.py`
- Create: `tests/__init__.py`
- Create: `tests/test_formatter.py`

**Step 1: テストファイルを作成**

```python
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
            agenda_decisions="- 議題1: 新機能のリリース日 → 2月末に決定",
            todos="- [ ] 田中: デザイン確認（2/20まで）",
        )
        md = format_full_document(segments, metadata, summary)
        assert "# 会議議事録" in md
        assert "週次定例ミーティング" in md
        assert "https://zoom.us/rec/share/abc123" in md
        assert "## 要約" in md
        assert "今日の定例会議の概要です。" in md
        assert "## 議題・決定事項" in md
        assert "## TODO / アクションアイテム" in md
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
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_formatter.py -v`
Expected: FAIL (ImportError)

**Step 3: formatter.pyを実装**

```python
"""VTTパース・Markdown整形モジュール"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MeetingMetadata:
    date: str
    topic: str
    participants: list[str]
    recording_url: str = ""


@dataclass
class SummaryData:
    summary: str
    agenda_decisions: str
    todos: str


@dataclass
class Segment:
    speaker: str
    text: str
    start: str
    end: str


def _truncate_timestamp(ts: str) -> str:
    """00:00:05.500 → 00:00:05 のように秒単位に丸める。"""
    match = re.match(r"(\d{2}:\d{2}:\d{2})", ts)
    return match.group(1) if match else ts


def _parse_speaker_text(line: str) -> tuple[str, str]:
    """'田中太郎: テキスト' → ('田中太郎', 'テキスト') にパースする。"""
    match = re.match(r"^(.+?):\s+(.+)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", line.strip()


def parse_vtt(vtt_text: str) -> list[Segment]:
    """VTTテキストをパースしてSegmentリストを返す。同一話者の連続発言はマージする。"""
    segments: list[Segment] = []
    lines = vtt_text.strip().split("\n")

    i = 0
    while i < len(lines) and not re.match(r"^\d+$", lines[i].strip()):
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        if not re.match(r"^\d+$", line):
            i += 1
            continue
        i += 1

        if i >= len(lines):
            break
        ts_line = lines[i].strip()
        ts_match = re.match(r"([\d:.]+)\s*-->\s*([\d:.]+)", ts_line)
        if not ts_match:
            i += 1
            continue
        start = _truncate_timestamp(ts_match.group(1))
        end = _truncate_timestamp(ts_match.group(2))
        i += 1

        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        full_text = " ".join(text_lines)
        speaker, text = _parse_speaker_text(full_text)

        if segments and segments[-1].speaker == speaker:
            segments[-1].text += "\n" + text
            segments[-1].end = end
        else:
            segments.append(Segment(speaker=speaker, text=text, start=start, end=end))

        i += 1

    return segments


def segments_to_plain_text(segments: list[Segment]) -> str:
    """SegmentリストからAI要約用のプレーンテキストを生成する。"""
    lines = []
    for seg in segments:
        if seg.speaker:
            lines.append(f"{seg.speaker}: {seg.text}")
        else:
            lines.append(seg.text)
    return "\n".join(lines)


def format_transcript_markdown(segments: list[Segment]) -> str:
    """Segmentリストから文字起こしセクションのMarkdownを生成する。"""
    lines = []
    for seg in segments:
        lines.append(f"### {seg.start} - {seg.end}")
        lines.append("")
        if seg.speaker:
            lines.append(f"**{seg.speaker}**")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def format_full_document(
    segments: list[Segment],
    metadata: MeetingMetadata,
    summary: SummaryData | None,
) -> str:
    """全体のMarkdownドキュメントを生成する。"""
    lines = [
        "# 会議議事録",
        "",
        f"- 日時: {metadata.date}",
        f"- 会議名: {metadata.topic}",
        f"- 参加者: {'、'.join(metadata.participants)}",
    ]
    if metadata.recording_url:
        lines.append(f"- 録画URL: {metadata.recording_url}")

    lines.extend(["", "---", ""])

    if summary:
        lines.extend([
            "## 要約",
            "",
            summary.summary,
            "",
            "## 議題・決定事項",
            "",
            summary.agenda_decisions,
            "",
            "## TODO / アクションアイテム",
            "",
            summary.todos,
            "",
            "---",
            "",
        ])

    lines.extend([
        "## 文字起こし",
        "",
        format_transcript_markdown(segments),
    ])

    return "\n".join(lines)
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_formatter.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/formatter.py tests/__init__.py tests/test_formatter.py
git commit -m "feat: VTTパーサーとMarkdown整形を実装"
```

---

### Task 3: Zoom APIクライアント（TDD）

**Files:**
- Create: `zoom_moji_nayu/zoom_client.py`
- Create: `tests/test_zoom_client.py`

**Step 1: テストファイルを作成**

```python
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

    def test_get_transcript_url_found(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {"recording_type": "shared_screen", "download_url": "https://zoom.us/video"},
                {"recording_type": "audio_transcript", "download_url": "https://zoom.us/transcript"},
            ]
        }
        assert client.get_transcript_url(meeting) == "https://zoom.us/transcript"

    def test_get_transcript_url_not_found(self):
        client = self._make_client()
        meeting = {
            "recording_files": [
                {"recording_type": "shared_screen", "download_url": "https://zoom.us/video"},
            ]
        }
        assert client.get_transcript_url(meeting) is None
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_zoom_client.py -v`
Expected: FAIL (ImportError)

**Step 3: zoom_client.pyを実装**

```python
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
        url = f"{ZOOM_API_BASE}/users/me/recordings"
        resp = self._api_get(url, params={"from": from_date, "to": to_date})
        data = resp.json()
        return data.get("meetings", [])

    def download_transcript(self, download_url: str) -> str:
        """VTTファイルをダウンロードする。"""
        token = self._ensure_token()
        resp = self._api_get(download_url, params={"access_token": token})
        return resp.text

    def get_transcript_url(self, meeting: dict) -> str | None:
        """録画情報からtranscriptのダウンロードURLを取得する。"""
        for f in meeting.get("recording_files", []):
            if f.get("recording_type") == "audio_transcript":
                return f.get("download_url")
        return None
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_zoom_client.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/zoom_client.py tests/test_zoom_client.py
git commit -m "feat: Zoom APIクライアントを実装"
```

---

### Task 4: Gemini API要約・議事録生成（TDD）

**Files:**
- Create: `zoom_moji_nayu/summarizer.py`
- Create: `tests/test_summarizer.py`

**Step 1: テストファイルを作成**

```python
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
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_summarizer.py -v`
Expected: FAIL (ImportError)

**Step 3: summarizer.pyを実装**

```python
"""Gemini APIで要約・議事録・TODOを生成するモジュール"""

from __future__ import annotations

import logging
import re
import time

import google.generativeai as genai

from zoom_moji_nayu.formatter import SummaryData

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

PROMPT_TEMPLATE = """以下の会議の文字起こしテキストを分析し、次の3つのセクションを日本語で生成してください。

## 要約
会議の概要を3〜5文で簡潔にまとめてください。

## 議題・決定事項
話し合われた議題と、それぞれの決定事項を箇条書きでリスト化してください。

## TODO / アクションアイテム
会議で生まれたタスクや次のアクションを、可能な限り担当者と期限を付けて箇条書きで抽出してください。チェックボックス形式（- [ ]）で記載してください。

---

文字起こしテキスト:

{transcript}"""


def parse_summary_response(text: str) -> SummaryData | None:
    """Gemini APIのレスポンステキストをパースしてSummaryDataを返す。"""
    if not text.strip():
        return None

    sections = {"要約": "", "議題・決定事項": "", "TODO / アクションアイテム": ""}
    current_section = None

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            header = stripped[3:].strip()
            for key in sections:
                if key in header:
                    current_section = key
                    break
            else:
                current_section = None
        elif current_section is not None:
            sections[current_section] += line + "\n"

    summary = sections["要約"].strip()
    agenda = sections["議題・決定事項"].strip()
    todos = sections["TODO / アクションアイテム"].strip()

    if not summary and not agenda and not todos:
        return None

    return SummaryData(
        summary=summary,
        agenda_decisions=agenda,
        todos=todos,
    )


class Summarizer:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def summarize(self, transcript_text: str) -> SummaryData | None:
        """文字起こしテキストから要約・議事録・TODOを生成する。"""
        prompt = PROMPT_TEMPLATE.format(transcript=transcript_text)

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                return parse_summary_response(response.text)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("Gemini API error, retrying in %ds: %s", wait, e)
                    time.sleep(wait)
                else:
                    logger.error("Gemini API failed after %d retries: %s", MAX_RETRIES, e)
                    return None
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_summarizer.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/summarizer.py tests/test_summarizer.py
git commit -m "feat: Gemini API要約・議事録生成を実装"
```

---

### Task 5: Google Docsクライアント（TDD）

**Files:**
- Create: `zoom_moji_nayu/gdocs_client.py`
- Create: `tests/test_gdocs_client.py`

**Step 1: テストファイルを作成**

```python
"""Google Docsクライアントのテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.gdocs_client import GDocsClient


class TestGDocsClient:
    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials.from_service_account_info")
    def test_create_document(self, mock_creds, mock_build):
        mock_docs = MagicMock()
        mock_drive = MagicMock()
        mock_build.side_effect = lambda service, version, credentials: (
            mock_docs if service == "docs" else mock_drive
        )
        mock_docs.documents().create().execute.return_value = {
            "documentId": "doc_123"
        }
        mock_drive.files().get().execute.return_value = {"parents": ["root"]}

        client = GDocsClient(
            service_account_info={"type": "service_account"},
            folder_id="folder_abc",
        )
        doc_id = client.create_document(
            title="テストドキュメント",
            markdown_content="# テスト\n\nコンテンツ",
        )
        assert doc_id == "doc_123"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials.from_service_account_info")
    def test_get_document_url(self, mock_creds, mock_build):
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            service_account_info={"type": "service_account"},
            folder_id="folder_abc",
        )
        url = client.get_document_url("doc_123")
        assert url == "https://docs.google.com/document/d/doc_123/edit"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials.from_service_account_info")
    def test_build_requests_heading(self, mock_creds, mock_build):
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            service_account_info={"type": "service_account"},
            folder_id="folder_abc",
        )
        requests = client._markdown_to_docs_requests("# 見出し\n\n本文テキスト\n")
        insert_texts = [r for r in requests if "insertText" in r]
        assert len(insert_texts) >= 2
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_gdocs_client.py -v`
Expected: FAIL (ImportError)

**Step 3: gdocs_client.pyを実装**

```python
"""Google Docsクライアントモジュール"""

from __future__ import annotations

import logging
import re
import time

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
MAX_RETRIES = 3


class GDocsClient:
    def __init__(self, service_account_info: dict, folder_id: str):
        creds = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        self.docs_service = build("docs", "v1", credentials=creds)
        self.drive_service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id

    def create_document(self, title: str, markdown_content: str) -> str:
        """MarkdownコンテンツからGoogle Docsドキュメントを作成し、指定フォルダに配置する。"""
        doc = (
            self.docs_service.documents()
            .create(body={"title": title})
            .execute()
        )
        doc_id = doc["documentId"]

        requests = self._markdown_to_docs_requests(markdown_content)
        if requests:
            for attempt in range(MAX_RETRIES):
                try:
                    self.docs_service.documents().batchUpdate(
                        documentId=doc_id, body={"requests": requests}
                    ).execute()
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** attempt
                        logger.warning("Google Docs API error, retrying in %ds: %s", wait, e)
                        time.sleep(wait)
                    else:
                        raise

        file_info = (
            self.drive_service.files()
            .get(fileId=doc_id, fields="parents")
            .execute()
        )
        prev_parents = ",".join(file_info.get("parents", []))
        self.drive_service.files().update(
            fileId=doc_id,
            addParents=self.folder_id,
            removeParents=prev_parents,
            fields="id, parents",
        ).execute()

        logger.info("Created document: %s (ID: %s)", title, doc_id)
        return doc_id

    def get_document_url(self, doc_id: str) -> str:
        """ドキュメントIDからURLを生成する。"""
        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def _markdown_to_docs_requests(self, md: str) -> list[dict]:
        """Markdownを解析してGoogle Docs batchUpdateリクエストのリストを生成する。"""
        lines = md.split("\n")
        elements: list[tuple[str, str]] = []

        for line in lines:
            if line.startswith("### "):
                elements.append((line[4:] + "\n", "HEADING_3"))
            elif line.startswith("## "):
                elements.append((line[3:] + "\n", "HEADING_2"))
            elif line.startswith("# "):
                elements.append((line[2:] + "\n", "HEADING_1"))
            elif line.startswith("---"):
                elements.append(("───────────────────\n", "NORMAL_TEXT"))
            elif line.startswith("- "):
                elements.append(("  " + line + "\n", "NORMAL_TEXT"))
            elif re.match(r"^\*\*(.+)\*\*$", line):
                elements.append((re.match(r"^\*\*(.+)\*\*$", line).group(1) + "\n", "BOLD"))
            elif line.strip() == "":
                elements.append(("\n", "NORMAL_TEXT"))
            else:
                elements.append((line + "\n", "NORMAL_TEXT"))

        requests = []
        index = 1

        for text, style in elements:
            requests.append({
                "insertText": {
                    "location": {"index": index},
                    "text": text,
                }
            })
            end_index = index + len(text)

            if style in ("HEADING_1", "HEADING_2", "HEADING_3"):
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": index, "endIndex": end_index},
                        "paragraphStyle": {"namedStyleType": style},
                        "fields": "namedStyleType",
                    }
                })
            elif style == "BOLD":
                requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": index, "endIndex": end_index - 1},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                })

            index = end_index

        return requests
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_gdocs_client.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/gdocs_client.py tests/test_gdocs_client.py
git commit -m "feat: Google Docsクライアントを実装"
```

---

### Task 6: Discord Webhook通知（TDD）

**Files:**
- Create: `zoom_moji_nayu/discord_notifier.py`
- Create: `tests/test_discord_notifier.py`

**Step 1: テストファイルを作成**

```python
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
        # 例外が発生しないことを確認
        notifier.notify(
            meeting_topic="テスト",
            gdocs_url="https://docs.google.com/test",
            recording_url="",
        )
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_discord_notifier.py -v`
Expected: FAIL (ImportError)

**Step 3: discord_notifier.pyを実装**

```python
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
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_discord_notifier.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/discord_notifier.py tests/test_discord_notifier.py
git commit -m "feat: Discord Webhook通知を実装"
```

---

### Task 7: メイン処理（エントリーポイント）

**Files:**
- Create: `zoom_moji_nayu/__main__.py`
- Create: `tests/test_main.py`

**Step 1: テストファイルを作成**

```python
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
```

**Step 2: テストを実行して失敗を確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_main.py -v`
Expected: FAIL (ImportError)

**Step 3: __main__.pyを実装**

```python
"""Zoom文字起こし自動同期 メイン処理"""

from __future__ import annotations

import base64
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoom_moji_nayu.config import get_zoom_config, get_google_config, get_gemini_config, get_discord_config
from zoom_moji_nayu.zoom_client import ZoomClient
from zoom_moji_nayu.formatter import (
    parse_vtt, segments_to_plain_text, format_full_document,
    MeetingMetadata, SummaryData,
)
from zoom_moji_nayu.gdocs_client import GDocsClient
from zoom_moji_nayu.summarizer import Summarizer
from zoom_moji_nayu.discord_notifier import DiscordNotifier

logger = logging.getLogger(__name__)

PROCESSED_FILE = str(Path(__file__).parent.parent / "processed.json")


def load_processed(path: str) -> list[str]:
    """処理済みIDリストを読み込む。"""
    with open(path) as f:
        data = json.load(f)
    return data.get("processed_ids", [])


def save_processed(path: str, ids: list[str]) -> None:
    """処理済みIDリストを保存する。"""
    with open(path, "w") as f:
        json.dump({"processed_ids": ids}, f, ensure_ascii=False, indent=2)


def _extract_participants(segments) -> list[str]:
    """Segmentリストからユニークな話者名を抽出する。"""
    seen = set()
    participants = []
    for seg in segments:
        if seg.speaker and seg.speaker not in seen:
            seen.add(seg.speaker)
            participants.append(seg.speaker)
    return participants


def process_recordings(
    zoom: ZoomClient,
    gdocs: GDocsClient,
    summarizer: Summarizer,
    discord: DiscordNotifier,
    processed_ids: list[str],
) -> list[str]:
    """未処理の録画を処理し、新たに処理したIDのリストを返す。"""
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    recordings = zoom.get_recordings(from_date=from_date, to_date=to_date)
    new_ids: list[str] = []

    for meeting in recordings:
        meeting_id = meeting["uuid"]
        if meeting_id in processed_ids:
            logger.info("Skipping already processed: %s", meeting_id)
            continue

        transcript_url = zoom.get_transcript_url(meeting)
        if not transcript_url:
            logger.info("No transcript for: %s", meeting.get("topic", meeting_id))
            continue

        try:
            vtt_text = zoom.download_transcript(transcript_url)
            segments = parse_vtt(vtt_text)
            participants = _extract_participants(segments)
            plain_text = segments_to_plain_text(segments)

            start_time = meeting.get("start_time", "")
            date_str = start_time[:10] + " " + start_time[11:16] if start_time else ""
            recording_url = meeting.get("share_url", "")

            metadata = MeetingMetadata(
                date=date_str,
                topic=meeting.get("topic", "無題の会議"),
                participants=participants,
                recording_url=recording_url,
            )

            # Gemini APIで要約生成（失敗してもNoneで続行）
            summary = summarizer.summarize(plain_text)

            markdown = format_full_document(segments, metadata, summary)

            doc_title = f"{date_str[:10]}_{metadata.topic}"
            doc_id = gdocs.create_document(title=doc_title, markdown_content=markdown)
            gdocs_url = gdocs.get_document_url(doc_id)

            # Discord通知
            discord.notify(
                meeting_topic=metadata.topic,
                gdocs_url=gdocs_url,
                recording_url=recording_url,
            )

            new_ids.append(meeting_id)
            logger.info("Processed: %s", metadata.topic)

        except Exception:
            logger.exception("Failed to process meeting: %s", meeting_id)
            continue

    return new_ids


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    zoom_config = get_zoom_config()
    google_config = get_google_config()
    gemini_config = get_gemini_config()
    discord_config = get_discord_config()

    sa_info = json.loads(base64.b64decode(google_config["service_account_json"]))

    zoom = ZoomClient(**zoom_config)
    gdocs = GDocsClient(
        service_account_info=sa_info,
        folder_id=google_config["drive_folder_id"],
    )
    summarizer = Summarizer(api_key=gemini_config["api_key"])
    discord = DiscordNotifier(webhook_url=discord_config["webhook_url"])

    processed_ids = load_processed(PROCESSED_FILE)
    new_ids = process_recordings(zoom, gdocs, summarizer, discord, processed_ids)

    if new_ids:
        all_ids = processed_ids + new_ids
        save_processed(PROCESSED_FILE, all_ids)
        logger.info("Processed %d new recordings", len(new_ids))
    else:
        logger.info("No new recordings to process")


if __name__ == "__main__":
    main()
```

**Step 4: テストを実行してパスを確認**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/test_main.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/__main__.py tests/test_main.py
git commit -m "feat: メイン処理を実装（要約・Discord通知対応）"
```

---

### Task 8: GitHub Actionsワークフロー

**Files:**
- Create: `.github/workflows/zoom-transcript.yml`

**Step 1: ワークフローファイルを作成**

```yaml
name: Zoom Transcript Sync

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: 04_Script/zoom_moji_nayu

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run sync
        env:
          ZOOM_ACCOUNT_ID: ${{ secrets.ZOOM_ACCOUNT_ID }}
          ZOOM_CLIENT_ID: ${{ secrets.ZOOM_CLIENT_ID }}
          ZOOM_CLIENT_SECRET: ${{ secrets.ZOOM_CLIENT_SECRET }}
          GOOGLE_SERVICE_ACCOUNT_JSON: ${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python -m zoom_moji_nayu

      - name: Commit processed.json
        run: |
          cd ${{ github.workspace }}
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add 04_Script/zoom_moji_nayu/processed.json
          git diff --staged --quiet || git commit -m "auto: update processed recordings"
          git push
```

**Step 2: コミット**

```bash
git add .github/workflows/zoom-transcript.yml
git commit -m "feat: GitHub Actionsワークフローを追加"
```

---

### Task 9: 全テスト実行 & 最終確認

**Step 1: 依存パッケージをインストール**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && pip install -r requirements.txt && pip install pytest`

**Step 2: 全テストを実行**

Run: `cd /Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 3: 最終コミット（必要に応じて）**

テストで問題があれば修正してコミット。
