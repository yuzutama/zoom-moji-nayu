"""Google Docsクライアントのテスト"""

from unittest.mock import patch, MagicMock

from zoom_moji_nayu.gdocs_client import GDocsClient


class TestGDocsClient:
    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_create_document(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_docs = MagicMock()
        mock_drive = MagicMock()
        mock_build.side_effect = lambda service, version, credentials: (
            mock_docs if service == "docs" else mock_drive
        )
        mock_drive.files().create().execute.return_value = {"id": "doc_123"}

        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        doc_id = client.create_document(
            title="テストドキュメント",
            markdown_content="# テスト\n\nコンテンツ",
        )
        assert doc_id == "doc_123"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_get_document_url(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        url = client.get_document_url("doc_123")
        assert url == "https://docs.google.com/document/d/doc_123/edit"

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_build_requests_heading(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        client = GDocsClient(
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
            folder_id="folder_abc",
        )
        requests = client._markdown_to_docs_requests("# 見出し\n\n本文テキスト\n")
        insert_texts = [r for r in requests if "insertText" in r]
        assert len(insert_texts) >= 2

    @patch("zoom_moji_nayu.gdocs_client.build")
    @patch("zoom_moji_nayu.gdocs_client.Credentials")
    def test_credentials_created_with_refresh_token(self, mock_creds_cls, mock_build):
        mock_creds_cls.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        GDocsClient(
            client_id="my_client_id",
            client_secret="my_secret",
            refresh_token="my_token",
            folder_id="folder_abc",
        )
        mock_creds_cls.assert_called_once_with(
            token=None,
            refresh_token="my_token",
            client_id="my_client_id",
            client_secret="my_secret",
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive",
            ],
        )
