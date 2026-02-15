# zoom-moji-nayu 改善デザイン

## 目的

クライアント納品品質に向けて、安定性・運用性・ドキュメントを整備する。

## 改善項目

### 1. google-genai パッケージ移行

現在使用中の `google-generativeai` パッケージはGoogleが非推奨（サポート終了）にしている。後継の `google-genai` に移行する。

- 変更対象: `requirements.txt`, `summarizer.py`, `tests/test_summarizer.py`
- `import google.generativeai as genai` → `from google import genai`
- `genai.configure(api_key=...)` → `client = genai.Client(api_key=...)`
- `GenerativeModel("gemini-2.0-flash").generate_content(prompt)` → `client.models.generate_content(model="gemini-2.0-flash", contents=prompt)`
- プロンプトや出力パース部分は変更なし

### 2. エラー通知追加

処理失敗時にDiscordへエラー通知を送信する。現状は成功時のみ通知。

- 変更対象: `discord_notifier.py`, `__main__.py`, `tests/test_discord_notifier.py`
- `DiscordNotifier` に `notify_error(meeting_topic, error_message)` メソッドを追加
- Discord embed形式、赤色（color=0xFF0000）でエラー内容を通知
- `process_recordings` のexceptブロックでエラー通知を呼び出す

### 3. ドキュメント整備（README.md）

クライアントがセットアップ・運用できるようにREADMEを作成する。

- 作成ファイル: `README.md`（リポジトリルート）
- 内容: 概要、必要な外部サービス、セットアップ手順（Zoom/GCP/Discord/GitHub Secrets）、動作確認方法、自動実行の説明

## 優先順位

1. google-genai移行（将来の動作保証）
2. エラー通知追加（運用監視）
3. ドキュメント整備（納品物）
