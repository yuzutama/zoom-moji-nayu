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
        self._folder_owner: str | None = None

    def _get_folder_owner(self) -> str | None:
        """フォルダのオーナーメールアドレスを取得する。"""
        if self._folder_owner:
            return self._folder_owner
        try:
            folder = self.drive_service.files().get(
                fileId=self.folder_id, fields="owners"
            ).execute()
            owners = folder.get("owners", [])
            if owners:
                self._folder_owner = owners[0]["emailAddress"]
                return self._folder_owner
        except Exception as e:
            logger.warning("Could not get folder owner: %s", e)
        return None

    def _transfer_ownership(self, file_id: str) -> None:
        """ファイルの所有権をフォルダオーナーに移転する。"""
        owner_email = self._get_folder_owner()
        if not owner_email:
            return
        try:
            self.drive_service.permissions().create(
                fileId=file_id,
                body={"type": "user", "role": "owner", "emailAddress": owner_email},
                transferOwnership=True,
            ).execute()
            logger.info("Transferred ownership to %s", owner_email)
        except Exception as e:
            logger.warning("Could not transfer ownership: %s", e)

    def create_document(self, title: str, markdown_content: str) -> str:
        """MarkdownコンテンツからGoogle Docsドキュメントを作成し、指定フォルダに配置する。"""
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [self.folder_id],
        }
        file = self.drive_service.files().create(body=file_metadata).execute()
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

        self._transfer_ownership(doc_id)

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
