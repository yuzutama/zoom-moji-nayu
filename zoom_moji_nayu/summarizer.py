"""Gemini APIで要約・議事録・TODOを生成するモジュール"""

from __future__ import annotations

import logging
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
