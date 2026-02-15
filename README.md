# zoom-moji-nayu

Zoom Cloud録画の文字起こし（VTT）とZoom AI Companion要約を自動取得し、Google Docsに保存するツールです。処理完了時にDiscordへ通知します。GitHub Actionsで毎時自動実行されます。

## 処理フロー

1. Zoom APIで直近24時間の録画一覧を取得
2. 文字起こし（VTT）をダウンロードしてパース
3. Zoom AI Companionの要約を取得
4. Google Docsにフォーマットして保存
5. Discordに通知（成功時は議事録URL、失敗時はエラー内容）
6. 処理済みIDをprocessed.jsonに記録

## 必要な外部サービス

- Zoom（有料プラン + Cloud録画 + 文字起こし有効 + AI Companion）
- Google Cloud（Docs API, Drive API + OAuth 2.0）
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
3. OAuth同意画面を設定（内部ユーザータイプ）
4. OAuthクライアントID（デスクトップアプリ）を作成
5. Client IDとClient Secretをメモ
6. `scripts/get_refresh_token.py` を実行してリフレッシュトークンを取得

### 3. Google Driveフォルダの準備

1. Google Driveで議事録保存用のフォルダを作成（または既存のものを使用）
2. フォルダを開き、URLからフォルダIDを取得（`https://drive.google.com/drive/folders/XXXXXX` のXXXXXX部分）

### 4. Discord Webhookの作成

1. Discordで通知先チャンネルの設定を開く
2. 連携サービス → ウェブフック → 新しいウェブフック
3. Webhook URLをコピー

### 5. GitHub Secretsの設定

リポジトリのSettings → Secrets and variables → Actionsで以下を登録

- ZOOM_ACCOUNT_ID
- ZOOM_CLIENT_ID
- ZOOM_CLIENT_SECRET
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- GOOGLE_REFRESH_TOKEN
- GOOGLE_DRIVE_FOLDER_ID
- DISCORD_WEBHOOK_URL

## 動作確認

リポジトリのActionsタブ → Zoom Transcript Sync → Run workflowで手動実行できます。

## 自動実行

GitHub Actionsにより毎時0分に自動実行されます。直近24時間のZoom録画から未処理のものを検出して処理します。
