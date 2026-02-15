"""Zoom文字起こし自動同期 メイン処理"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoom_moji_nayu.config import get_zoom_config, get_google_config, get_discord_config
from zoom_moji_nayu.zoom_client import ZoomClient
from zoom_moji_nayu.formatter import (
    parse_vtt, format_full_document,
    MeetingMetadata, SummaryData,
)
from zoom_moji_nayu.gdocs_client import GDocsClient
from zoom_moji_nayu.discord_notifier import DiscordNotifier

logger = logging.getLogger(__name__)

PROCESSED_FILE = str(Path(__file__).parent.parent / "processed.json")


def load_processed(path: str) -> list[str]:
    """処理済みIDリストを読み込む。"""
    with open(path) as f:
        data = json.load(f)
    return data.get("processed_ids", [])


def save_processed(path: str, ids: list[str]) -> None:
    """処理済みIDリストを保存する。"""
    with open(path, "w") as f:
        json.dump({"processed_ids": ids}, f, ensure_ascii=False, indent=2)


def _extract_participants(segments) -> list[str]:
    """Segmentリストからユニークな話者名を抽出する。"""
    seen = set()
    participants = []
    for seg in segments:
        if seg.speaker and seg.speaker not in seen:
            seen.add(seg.speaker)
            participants.append(seg.speaker)
    return participants


def _parse_zoom_summary(summary_data: dict) -> SummaryData | None:
    """Zoom AI Companionの要約JSONをSummaryDataに変換する。"""
    overall = summary_data.get("overall_summary", "")
    items = summary_data.get("items", [])

    chapter_lines = []
    for item in items:
        label = item.get("label", "")
        summary = item.get("summary", "")
        if label and summary:
            chapter_lines.append(f"- {label}: {summary}")
        elif label:
            chapter_lines.append(f"- {label}")
        elif summary:
            chapter_lines.append(f"- {summary}")

    if not overall and not chapter_lines:
        return None

    return SummaryData(
        summary=overall,
        chapters="\n".join(chapter_lines),
    )


def process_recordings(
    zoom: ZoomClient,
    gdocs: GDocsClient,
    discord: DiscordNotifier,
    processed_ids: set[str],
) -> list[str]:
    """未処理の録画を処理し、新たに処理したIDのリストを返す。"""
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    recordings = zoom.get_recordings(from_date=from_date, to_date=to_date)
    new_ids: list[str] = []

    for meeting in recordings:
        meeting_id = meeting["uuid"]
        if meeting_id in processed_ids:
            logger.info("Skipping already processed: %s", meeting_id)
            continue

        transcript_url = zoom.get_recording_url(meeting, "audio_transcript")
        if not transcript_url:
            logger.info("No transcript for: %s", meeting.get("topic", meeting_id))
            continue

        try:
            vtt_text = zoom.download_transcript(transcript_url)
            segments = parse_vtt(vtt_text)
            participants = _extract_participants(segments)

            start_time = meeting.get("start_time", "")
            date_str = start_time[:10] + " " + start_time[11:16] if start_time else ""
            recording_url = meeting.get("share_url", "")

            metadata = MeetingMetadata(
                date=date_str,
                topic=meeting.get("topic", "無題の会議"),
                participants=participants,
                recording_url=recording_url,
            )

            # Zoom AI Companion要約を取得（なければNoneで続行）
            summary = None
            summary_url = zoom.get_recording_url(meeting, "summary")
            if summary_url:
                summary_json = zoom.download_summary(summary_url)
                summary = _parse_zoom_summary(summary_json)
            else:
                logger.info("No summary available for: %s", metadata.topic)

            markdown = format_full_document(segments, metadata, summary)

            participants_str = "、".join(participants[:5]) if participants else ""
            if participants_str:
                doc_title = f"{date_str[:10]}_{participants_str}_{metadata.topic}"
            else:
                doc_title = f"{date_str[:10]}_{metadata.topic}"
            doc_id = gdocs.create_document(title=doc_title, markdown_content=markdown)
            gdocs_url = gdocs.get_document_url(doc_id)

            # Discord通知
            discord.notify(
                meeting_topic=metadata.topic,
                gdocs_url=gdocs_url,
                recording_url=recording_url,
            )

            new_ids.append(meeting_id)
            logger.info("Processed: %s", metadata.topic)

        except Exception as e:
            logger.exception("Failed to process meeting: %s", meeting_id)
            discord.notify_error(
                meeting_topic=meeting.get("topic", meeting_id),
                error_message=str(e),
            )
            continue

    return new_ids


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    zoom_config = get_zoom_config()
    google_config = get_google_config()
    discord_config = get_discord_config()

    zoom = ZoomClient(**zoom_config)
    gdocs = GDocsClient(
        client_id=google_config["client_id"],
        client_secret=google_config["client_secret"],
        refresh_token=google_config["refresh_token"],
        folder_id=google_config["drive_folder_id"],
    )
    discord = DiscordNotifier(webhook_url=discord_config["webhook_url"])

    processed_ids = set(load_processed(PROCESSED_FILE))
    new_ids = process_recordings(zoom, gdocs, discord, processed_ids)

    if new_ids:
        all_ids = list(processed_ids) + new_ids
        save_processed(PROCESSED_FILE, all_ids)
        logger.info("Processed %d new recordings", len(new_ids))
    else:
        logger.info("No new recordings to process")


if __name__ == "__main__":
    main()
