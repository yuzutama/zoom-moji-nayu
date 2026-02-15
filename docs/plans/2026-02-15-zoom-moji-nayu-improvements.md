# zoom-moji-nayu 改善 実装計画

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 納品品質に向けてgenaiパッケージ移行、エラー通知追加、ドキュメント整備を行う

**Architecture:** 既存のsummarizer.pyを新google-genaiパッケージに書き換え、discord_notifier.pyにエラー通知メソッドを追加し、__main__.pyから呼び出す。READMEをリポジトリルートに作成する。

**Tech Stack:** Python 3.11, google-genai, requests, pytest

---

### Task 1: google-genai パッケージ移行

**Files:**
- Modify: `requirements.txt:4`
- Modify: `zoom_moji_nayu/summarizer.py:1-89`
- Modify: `tests/test_summarizer.py:1-62`

**Step 1: requirements.txtを更新**

`requirements.txt` の4行目を変更する。

```
google-generativeai>=0.8.0
```
↓
```
google-genai>=1.0.0
```

**Step 2: summarizer.pyを書き換え**

`zoom_moji_nayu/summarizer.py` を以下に書き換える。

```python
"""Gemini APIで要約・議事録・TODOを生成するモジュール"""

from __future__ import annotations

import logging
import time

from google import genai

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
        self.client = genai.Client(api_key=api_key)

    def summarize(self, transcript_text: str) -> SummaryData | None:
        """文字起こしテキストから要約・議事録・TODOを生成する。"""
        prompt = PROMPT_TEMPLATE.format(transcript=transcript_text)

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
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

**Step 3: tests/test_summarizer.pyを書き換え**

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
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(
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
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        summarizer = Summarizer(api_key="test_key")
        result = summarizer.summarize("テスト")
        assert result is None
```

**Step 4: テストを実行**

Run: `python -m pytest tests/test_summarizer.py -v`
Expected: 4 tests PASS

**Step 5: コミット**

```bash
git add requirements.txt zoom_moji_nayu/summarizer.py tests/test_summarizer.py
git commit -m "refactor: google-generativeaiからgoogle-genaiに移行"
```

---

### Task 2: Discordエラー通知追加

**Files:**
- Modify: `zoom_moji_nayu/discord_notifier.py:1-41`
- Modify: `zoom_moji_nayu/__main__.py:113-115`
- Modify: `tests/test_discord_notifier.py:1-34`

**Step 1: discord_notifier.pyにnotify_errorメソッドを追加**

`zoom_moji_nayu/discord_notifier.py` を以下に書き換える。

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
```

**Step 2: __main__.pyのexceptブロックを修正**

`zoom_moji_nayu/__main__.py` の113-115行目を以下に変更する。

変更前:
```python
        except Exception:
            logger.exception("Failed to process meeting: %s", meeting_id)
            continue
```

変更後:
```python
        except Exception as e:
            logger.exception("Failed to process meeting: %s", meeting_id)
            discord.notify_error(
                meeting_topic=meeting.get("topic", meeting_id),
                error_message=str(e),
            )
            continue
```

**Step 3: tests/test_discord_notifier.pyにエラー通知テストを追加**

既存テストの末尾に以下を追加する。

```python
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
```

**Step 4: テストを実行**

Run: `python -m pytest tests/test_discord_notifier.py tests/test_main.py -v`
Expected: ALL PASS

**Step 5: コミット**

```bash
git add zoom_moji_nayu/discord_notifier.py zoom_moji_nayu/__main__.py tests/test_discord_notifier.py
git commit -m "feat: Discord経由のエラー通知を追加"
```

---

### Task 3: README.md作成

**Files:**
- Create: `README.md`

**Step 1: README.mdを作成**

リポジトリルート（`/Users/tamaki/cursor_v2/04_Script/zoom_moji_nayu/README.md`）に以下の内容で作成する。

```markdown
# zoom-moji-nayu

Zoom Cloud録画の文字起こし（VTT）を自動取得し、AIで要約・議事録・TODOを生成してGoogle Docsに保存するツールです。処理完了時にDiscordへ通知します。GitHub Actionsで毎時自動実行されます。

## 処理フロー

1. Zoom APIで直近24時間の録画一覧を取得
2. 文字起こし（VTT）をダウンロードしてパース
3. Gemini APIで要約・議題/決定事項・TODOを生成
4. Google Docsにフォーマットして保存
5. Discordに通知（成功時は議事録URL、失敗時はエラー内容）
6. 処理済みIDをprocessed.jsonに記録

## 必要な外部サービス

- Zoom（有料プラン + Cloud録画 + 文字起こし有効）
- Google Cloud（Docs API, Drive API）
- Gemini API
- Discord（Webhook）
- GitHub（Actions）

## セットアップ手順

### 1. Zoom Server-to-Server OAuthアプリの作成

1. https://marketplace.zoom.us/ にアクセス
2. Develop → Build App → サーバー間OAuthアプリを選択
3. アプリ名を入力して作成
4. App Credentialsページで以下をメモ
   - Account ID
   - Client ID
   - Client Secret
5. Scopesタブで以下を追加
   - cloud_recording:read:list_account_recordings:admin
   - cloud_recording:read:recording:admin
6. Activationタブでアプリを有効化

### 2. Google Cloudプロジェクトの設定

1. Google Cloud Consoleでプロジェクトを作成（または既存のものを使用）
2. 以下のAPIを有効化
   - Google Docs API
   - Google Drive API
   - Generative Language API（Gemini）
3. サービスアカウントを作成
4. サービスアカウントのJSONキーを生成してダウンロード
5. Gemini用のAPIキーを作成（API制限: Generative Language API）

### 3. Google Driveフォルダの準備

1. Google Driveで議事録保存用のフォルダを作成（または既存のものを使用）
2. フォルダを開き、URLからフォルダIDを取得（https://drive.google.com/drive/folders/XXXXXX のXXXXXX部分）
3. フォルダをサービスアカウントのメールアドレスに「編集者」権限で共有

### 4. Discord Webhookの作成

1. Discordで通知先チャンネルの設定を開く
2. 連携サービス → ウェブフック → 新しいウェブフック
3. Webhook URLをコピー

### 5. GitHub Secretsの設定

リポジトリのSettings → Secrets and variables → Actionsで以下を登録

- ZOOM_ACCOUNT_ID: ZoomアプリのAccount ID
- ZOOM_CLIENT_ID: ZoomアプリのClient ID
- ZOOM_CLIENT_SECRET: ZoomアプリのClient Secret
- GOOGLE_SERVICE_ACCOUNT_JSON: サービスアカウントJSONキーをBase64エンコードした値
- GOOGLE_DRIVE_FOLDER_ID: 保存先Google DriveフォルダのID
- GEMINI_API_KEY: Gemini APIキー
- DISCORD_WEBHOOK_URL: Discord Webhook URL

Base64エンコードの方法:
```bash
cat サービスアカウントキー.json | base64
```

## 動作確認

リポジトリのActionsタブ → Zoom Transcript Sync → Run workflowで手動実行できます。

## 自動実行

GitHub Actionsにより毎時0分に自動実行されます。直近24時間のZoom録画から未処理のものを検出して処理します。
```

**Step 2: コミット**

```bash
git add README.md
git commit -m "docs: README.mdを追加"
```

---

### Task 4: 全テスト実行とpush

**Step 1: 全テスト実行**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: GitHubにpush**

```bash
git push zoom-moji-nayu HEAD:main
```
