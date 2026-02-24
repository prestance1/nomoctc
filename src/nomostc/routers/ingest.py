import logging

from fastapi import APIRouter, status
from pydantic import BaseModel

from nomostc.db import get_db
from nomostc.parser import parse_edifact_file
from nomostc.repository import ingest_or_reprocess

logging.basicConfig(level="DEBUG")
logger = logging.getLogger("nomostc")

router = APIRouter(prefix="/ingest")


class IngestRequest(BaseModel):
    file_path: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def ingest(request: IngestRequest) -> dict[str, str | int | list[str]]:
    parsed = parse_edifact_file(request.file_path)
    db = get_db()
    ids, version = ingest_or_reprocess(db, parsed)
    action = "reprocessed" if version > 1 else "ingested"
    for msg in parsed.messages:
        logger.info(
            "%s message: type=%s id=%s metering_point=%s subscription=%s version=%d",
            action,
            msg.message_type,
            msg.message_id,
            msg.metering_point_id,
            msg.subscription_id,
            version,
        )
    return {
        "status": action,
        "file_path": parsed.file_path,
        "message_count": len(parsed.messages),
        "version": version,
        "ids": ids,
    }
