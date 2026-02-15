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

        self.drive_service.permissions().create(
            fileId=doc_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
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
                elements.append((line[4:] + "\n", "TIMESTAMP"))
            elif line.startswith("## "):
                elements.append((line[3:] + "\n", "HEADING_2"))
            elif line.startswith("# "):
                elements.append((line[2:] + "\n", "HEADING_1"))
            elif line.startswith("---"):
                elements.append(("\n", "SEPARATOR"))
            elif line.startswith("- "):
                elements.append((line[2:] + "\n", "BULLET"))
            elif re.match(r"^\*\*(.+)\*\*$", line):
                elements.append((re.match(r"^\*\*(.+)\*\*$", line).group(1) + "\n", "SPEAKER"))
            elif line.strip() == "":
                elements.append(("\n", "EMPTY"))
            else:
                elements.append((line + "\n", "NORMAL_TEXT"))

        NAVY = {"red": 0.1, "green": 0.14, "blue": 0.49}
        BLUE = {"red": 0.08, "green": 0.4, "blue": 0.75}
        GRAY = {"red": 0.6, "green": 0.6, "blue": 0.6}
        LIGHT_GRAY = {"red": 0.9, "green": 0.9, "blue": 0.9}

        requests: list[dict] = []
        index = 1
        ranges: list[tuple[int, int, str, str]] = []

        for text, style in elements:
            requests.append({
                "insertText": {
                    "location": {"index": index},
                    "text": text,
                }
            })
            end_index = index + len(text)
            ranges.append((index, end_index, text, style))
            index = end_index

        for start, end, text, style in ranges:
            has_content = end - 1 > start

            if style == "HEADING_1":
                requests.append({"updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "namedStyleType": "HEADING_1",
                        "spaceBelow": {"magnitude": 8, "unit": "PT"},
                        "borderBottom": {
                            "color": {"color": {"rgbColor": NAVY}},
                            "width": {"magnitude": 1.5, "unit": "PT"},
                            "padding": {"magnitude": 6, "unit": "PT"},
                            "dashStyle": "SOLID",
                        },
                    },
                    "fields": "namedStyleType,spaceBelow,borderBottom",
                }})
                if has_content:
                    requests.append({"updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end - 1},
                        "textStyle": {
                            "foregroundColor": {"color": {"rgbColor": NAVY}},
                        },
                        "fields": "foregroundColor",
                    }})

            elif style == "HEADING_2":
                requests.append({"updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "namedStyleType": "HEADING_2",
                        "spaceAbove": {"magnitude": 18, "unit": "PT"},
                        "spaceBelow": {"magnitude": 6, "unit": "PT"},
                        "borderLeft": {
                            "color": {"color": {"rgbColor": NAVY}},
                            "width": {"magnitude": 3, "unit": "PT"},
                            "padding": {"magnitude": 8, "unit": "PT"},
                            "dashStyle": "SOLID",
                        },
                    },
                    "fields": "namedStyleType,spaceAbove,spaceBelow,borderLeft",
                }})
                if has_content:
                    requests.append({"updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end - 1},
                        "textStyle": {
                            "foregroundColor": {"color": {"rgbColor": NAVY}},
                        },
                        "fields": "foregroundColor",
                    }})

            elif style == "TIMESTAMP":
                requests.append({"updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "spaceAbove": {"magnitude": 16, "unit": "PT"},
                        "spaceBelow": {"magnitude": 2, "unit": "PT"},
                        "borderTop": {
                            "color": {"color": {"rgbColor": LIGHT_GRAY}},
                            "width": {"magnitude": 0.5, "unit": "PT"},
                            "padding": {"magnitude": 6, "unit": "PT"},
                            "dashStyle": "SOLID",
                        },
                    },
                    "fields": "spaceAbove,spaceBelow,borderTop",
                }})
                if has_content:
                    requests.append({"updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end - 1},
                        "textStyle": {
                            "fontSize": {"magnitude": 8, "unit": "PT"},
                            "foregroundColor": {"color": {"rgbColor": GRAY}},
                        },
                        "fields": "fontSize,foregroundColor",
                    }})

            elif style == "SPEAKER":
                requests.append({"updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "spaceAbove": {"magnitude": 0, "unit": "PT"},
                        "spaceBelow": {"magnitude": 2, "unit": "PT"},
                    },
                    "fields": "spaceAbove,spaceBelow",
                }})
                if has_content:
                    requests.append({"updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": end - 1},
                        "textStyle": {
                            "bold": True,
                            "foregroundColor": {"color": {"rgbColor": BLUE}},
                            "fontSize": {"magnitude": 10, "unit": "PT"},
                        },
                        "fields": "bold,foregroundColor,fontSize",
                    }})

            elif style == "SEPARATOR":
                requests.append({"updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "borderBottom": {
                            "color": {"color": {"rgbColor": LIGHT_GRAY}},
                            "width": {"magnitude": 0.5, "unit": "PT"},
                            "padding": {"magnitude": 4, "unit": "PT"},
                            "dashStyle": "SOLID",
                        },
                        "spaceAbove": {"magnitude": 8, "unit": "PT"},
                        "spaceBelow": {"magnitude": 8, "unit": "PT"},
                    },
                    "fields": "borderBottom,spaceAbove,spaceBelow",
                }})

            elif style == "BULLET":
                requests.append({"createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }})
                kv_match = re.match(r"^(.+?): ", text)
                if kv_match:
                    key_end = start + len(kv_match.group(1)) + 1
                    requests.append({"updateTextStyle": {
                        "range": {"startIndex": start, "endIndex": key_end},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }})
                url_match = re.search(r"(https?://\S+)", text)
                if url_match:
                    requests.append({"updateTextStyle": {
                        "range": {
                            "startIndex": start + url_match.start(),
                            "endIndex": start + url_match.end(),
                        },
                        "textStyle": {"link": {"url": url_match.group(1)}},
                        "fields": "link",
                    }})

        if index > 1:
            requests.append({"updateTextStyle": {
                "range": {"startIndex": 1, "endIndex": index},
                "textStyle": {
                    "weightedFontFamily": {"fontFamily": "Noto Sans JP"},
                },
                "fields": "weightedFontFamily",
            }})

        return requests
