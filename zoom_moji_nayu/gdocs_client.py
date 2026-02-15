"""Google Docsクライアントモジュール"""

from __future__ import annotations

import logging
import re
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
MAX_RETRIES = 3


class GDocsClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, folder_id: str):
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        self.docs_service = build("docs", "v1", credentials=creds)
        self.drive_service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id

    def create_document(self, title: str, markdown_content: str) -> str:
        """MarkdownコンテンツからGoogle Docsドキュメントを作成し、指定フォルダに配置する。"""
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [self.folder_id],
        }
        file = (
            self.drive_service.files()
            .create(body=file_metadata, fields="id", supportsAllDrives=True)
            .execute()
        )
        doc_id = file["id"]

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
