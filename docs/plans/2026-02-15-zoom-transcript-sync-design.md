# Zoom文字起こし自動同期ツール 設計書

## 概要

Zoom Cloud APIを使い、クラウド録画の文字起こしデータ（Zoomの自動Audio Transcript機能）を取得。Gemini APIで要約・議事録・TODOを生成し、Markdown形式に整形してGoogle Docsとして保存する自動化ツール。処理完了後にDiscord Webhookで通知する。GitHub Actionsで定期実行する。

## 要件

- Zoom Cloud APIでクラウド録画の文字起こしデータを取得
- Zoom録画URLもドキュメントに記載
- セットアップ以降の新規録画のみを対象
- Gemini APIで要約・議事録（議題・決定事項）・TODOを自動生成
- 話者別・タイムスタンプ付きMarkdown形式に整形
- Google Docsとして指定フォルダに保存
- Discord Webhookで処理完了通知（Google DocsのURL + Zoom録画URL）
- GitHub Actionsで定期自動実行（ポーリングベース）
- 既存のmojiokoshiツールとは完全に独立

## アーキテクチャ

### 処理フロー

1. GitHub Actions（cronスケジュール、毎時実行）がPythonスクリプトを起動
2. Zoom API（Server-to-Server OAuth）で直近の録画一覧を取得
3. processed.jsonと照合し、未処理の録画のみを対象にする
4. 各録画の文字起こしデータ（VTT形式）をダウンロード
5. VTTをパースして話者別・タイムスタンプ付きMarkdownに整形
6. Gemini APIで文字起こしテキストから要約・議事録・TODOを生成
7. 全てを統合したMarkdownをGoogle Docs APIでGoogle Docsとして指定フォルダに保存
8. Discord Webhookで通知（Google DocsのURL + Zoom録画URL）
9. 処理済み録画IDをprocessed.jsonに記録してコミット

### 技術スタック

- Python 3.11+
- requests - Zoom API呼び出し / Discord Webhook
- google-api-python-client / google-auth - Google Docs & Drive API
- google-generativeai - Gemini API
- webvtt-py - VTTパース

### ディレクトリ構成

```
04_Script/zoom_moji_nayu/
  zoom_moji_nayu/
    __init__.py
    __main__.py          # エントリーポイント
    zoom_client.py       # Zoom API操作
    formatter.py         # VTT → Markdown変換
    summarizer.py        # Gemini APIで要約・議事録・TODO生成
    gdocs_client.py      # Google Docs保存
    discord_notifier.py  # Discord Webhook通知
    config.py            # 設定管理
  processed.json         # 処理済み録画ID記録
  requirements.txt
  .github/workflows/
    zoom-transcript.yml  # GitHub Actionsワークフロー
```

## Zoom API連携

### 認証方式

Zoom Server-to-Server OAuthアプリを使用。

必要なsecrets:
- ZOOM_ACCOUNT_ID
- ZOOM_CLIENT_ID
- ZOOM_CLIENT_SECRET

### APIフロー

1. OAuthトークン取得: POST https://zoom.us/oauth/token?grant_type=account_credentials&account_id={account_id}
2. 録画一覧取得: GET /v2/users/me/recordings?from={date}&to={date}
3. 各録画のトランスクリプトファイルURLを取得
4. トランスクリプト（VTT形式）をダウンロード
5. 録画のshare_urlを取得してドキュメントに記載

### 注意点

- Zoomの文字起こし機能（Audio Transcript）がアカウント設定で有効になっている必要がある
- VTTファイルにはダウンロード用のアクセストークンが必要（録画一覧のレスポンスに含まれる）
- API Rate Limitへの対応（リトライ処理）

## VTTパース & Markdown整形

### 入力（Zoom VTT形式の例）

```
WEBVTT

1
00:00:00.000 --> 00:00:05.500
田中太郎: えーと、今日はですね

2
00:00:05.500 --> 00:00:12.000
鈴木花子: はい、よろしくお願いします
```

### 出力（Google Docsに保存するMarkdown形式）

```markdown
# 会議議事録

- 日時: 2026-02-15 10:00
- 会議名: 週次定例ミーティング
- 参加者: 田中太郎、鈴木花子
- 録画URL: https://zoom.us/rec/share/...

---

## 要約

（Gemini APIが生成した要約）

## 議題・決定事項

（Gemini APIが生成した議題と決定事項）

## TODO / アクションアイテム

（Gemini APIが抽出したTODOリスト）

---

## 文字起こし

### 00:00:00 - 00:00:05

**田中太郎**
えーと、今日はですね

### 00:00:05 - 00:00:12

**鈴木花子**
はい、よろしくお願いします
```

### 整形ロジック

- VTTのキュー（字幕ブロック）をパースし、話者名とテキストを抽出
- 同一話者の連続発言はまとめる
- 会議メタデータ（日時・会議名・参加者・録画URL）はZoom APIの録画情報から取得
- タイムスタンプは秒単位に丸める

## Gemini API要約・議事録生成

### 処理内容

文字起こしの全文テキストをGemini APIに渡し、以下の3つを生成する:

1. 要約 - 会議の概要を簡潔にまとめる
2. 議題・決定事項 - 話し合われた議題と、それぞれの決定事項をリスト化
3. TODO / アクションアイテム - 会議で生まれたタスク・次のアクションを担当者付きで抽出

### 必要なsecrets

- GEMINI_API_KEY

## Google Docs保存

### 認証方式

Google Cloudのサービスアカウントを使用。

必要なsecrets:
- GOOGLE_SERVICE_ACCOUNT_JSON - サービスアカウントのJSONキー（Base64エンコード）
- GOOGLE_DRIVE_FOLDER_ID - 保存先フォルダID

### 保存フロー

1. Google Docs APIでドキュメントを新規作成
2. Markdownの内容をGoogle Docsのフォーマット（段落、見出し、太字など）に変換して挿入
3. Google Drive APIで指定フォルダに移動

### ドキュメント命名規則

YYYY-MM-DD_会議名（例: 2026-02-15_週次定例ミーティング）

### Google Docsフォーマット

- H1 → ドキュメントタイトル（見出し1）
- メタデータ → 通常テキスト
- H2 → セクション見出し（要約・議題・TODO・文字起こし）
- H3 → タイムスタンプ区間
- 話者名 → 太字
- 発言テキスト → 通常テキスト

## Discord Webhook通知

### 通知内容

処理完了時にDiscord Webhookで以下を送信:
- 会議名
- Google DocsのURL
- Zoom録画URL

### 必要なsecrets

- DISCORD_WEBHOOK_URL

## GitHub Actionsワークフロー

### ワークフロー設定

- スケジュール: cron: '0 * * * *'（毎時実行）
- 手動実行: workflow_dispatch対応
- Python 3.11使用

### ワークフローの流れ

1. リポジトリをチェックアウト
2. Python環境セットアップ & 依存インストール
3. Pythonスクリプトを実行
4. processed.jsonに変更があればコミット & プッシュ

### 必要なGitHub Secrets

- ZOOM_ACCOUNT_ID
- ZOOM_CLIENT_ID
- ZOOM_CLIENT_SECRET
- GOOGLE_SERVICE_ACCOUNT_JSON
- GOOGLE_DRIVE_FOLDER_ID
- GEMINI_API_KEY
- DISCORD_WEBHOOK_URL

## エラー処理

- Zoom APIエラー: リトライ（最大3回、指数バックオフ）
- Gemini APIエラー: リトライ（最大3回）。失敗した場合は要約なしで文字起こしのみ保存
- Google Docs APIエラー: リトライ（最大3回）
- Discord Webhookエラー: ログ出力のみ（通知失敗は処理全体を止めない）
- VTTパースエラー: エラーログを出力してスキップ、次の録画に進む
- 1つの録画の処理失敗が他の録画の処理を妨げない設計

## テスト

- ユニットテスト: VTTパース・Markdown整形のテスト
- ユニットテスト: Gemini APIレスポンスのパーステスト
- 統合テスト: モックを使ったAPI連携テスト
