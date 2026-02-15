"""VTTパース・Markdown整形モジュール"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class MeetingMetadata:
    date: str
    topic: str
    participants: list[str]
    recording_url: str = ""


@dataclass
class SummaryData:
    summary: str
    chapters: str


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
        ])
        if summary.chapters:
            lines.extend([
                "## トピック",
                "",
                summary.chapters,
                "",
            ])
        lines.extend(["---", ""])

    lines.extend([
        "## 文字起こし",
        "",
        format_transcript_markdown(segments),
    ])

    return "\n".join(lines)
