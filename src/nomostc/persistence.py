from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import TypedDict, cast

from pymongo.database import Database

from nomostc.parser import EdifactMessage, ParsedEdifactFile

PARSED_EDIFACT_COLLECTION = "parsed_edifact"
REQUESTS_COLLECTION = "requests"


class SegmentDoc(TypedDict):
    tag: str
    elements: list[list[str]]


class MessageDoc(TypedDict):
    message_type: str
    message_id: str
    metering_point_id: str | None
    subscription_id: str | None
    segments: list[SegmentDoc]


class RequestLogDoc(TypedDict):
    method: str
    path: str
    status_code: int
    timestamp: datetime


def log_request(
    db: Database,
    *,
    method: str,
    path: str,
    status_code: int,
    timestamp: datetime | None = None,
) -> None:
    """Persist a request record with timestamp."""
    doc: RequestLogDoc = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "timestamp": timestamp or datetime.now(timezone.utc),
    }
    db[REQUESTS_COLLECTION].insert_one(doc)


def _message_to_doc(msg: EdifactMessage) -> MessageDoc:
    """Serialize an EdifactMessage to a dict (interchange stored at file level)."""
    return {
        "message_type": msg.message_type,
        "message_id": msg.message_id,
        "metering_point_id": msg.metering_point_id,
        "subscription_id": msg.subscription_id,
        "segments": [cast(SegmentDoc, asdict(s)) for s in msg.segments],
    }


def ingest_or_reprocess(db: Database, parsed: ParsedEdifactFile) -> tuple[list[str], int]:
    """Persist parsed EDIFACT file as a versioned document with nested messages.

    Stores file_path, raw_content, and interchange once; messages are nested.
    If documents for this file_path already exist, their valid_to is stamped
    (superseded) and a new document is inserted with an incremented version.
    Returns (inserted_ids, version).
    """
    col = db[PARSED_EDIFACT_COLLECTION]
    now = datetime.now(timezone.utc)

    interchange = asdict(parsed.messages[0].interchange) if parsed.messages else {}

    current_max = col.find_one(
        {"file_path": parsed.file_path, "valid_to": None},
        sort=[("version", -1)],
        projection={"version": 1},
    )
    version = (current_max["version"] + 1) if current_max else 1

    if current_max:
        col.update_many(
            {"file_path": parsed.file_path, "valid_to": None},
            {"$set": {"valid_to": now}},
        )

    doc = {
        "file_path": parsed.file_path,
        "raw_content": parsed.raw_content,
        "interchange": interchange,
        "messages": [_message_to_doc(msg) for msg in parsed.messages],
        "version": version,
        "valid_from": now,
        "valid_to": None,
        "ingested_at": now,
    }

    result = col.insert_one(doc)
    return [str(result.inserted_id)], version
