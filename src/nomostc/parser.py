from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from nomostc.exceptions import EdifactParsingError


@dataclass(frozen=True)
class Delimiters:
    component_separator: str = ":"
    element_separator: str = "+"
    decimal_notation: str = "."
    release_character: str = "?"
    segment_terminator: str = "'"


@dataclass
class Segment:
    tag: str
    elements: list[list[str]]

    def element(self, index: int, component: int = 0, default: str | None = None) -> str | None:
        if index < len(self.elements) and component < len(self.elements[index]):
            return self.elements[index][component] or default
        return default


@dataclass
class InterchangeHeader:
    syntax_identifier: str
    syntax_version: str
    sender_id: str
    sender_qualifier: str
    recipient_id: str
    recipient_qualifier: str
    date: str
    time: str
    control_reference: str
    application_reference: str | None = None


@dataclass
class EdifactMessage:
    message_type: str
    message_id: str
    interchange: InterchangeHeader
    metering_point_id: str | None = None
    subscription_id: str | None = None
    segments: list[Segment] = field(default_factory=list)


@dataclass
class ParsedEdifactFile:
    file_path: str
    raw_content: str
    messages: list[EdifactMessage]


def _split(text: str, delimiter: str, release: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == release and i + 1 < len(text):
            buf.append(text[i + 1])
            i += 2
        elif ch == delimiter:
            parts.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    parts.append("".join(buf))
    return parts


def _parse_delimiters(raw: str) -> tuple[Delimiters, str]:
    stripped = raw.lstrip()
    if stripped.startswith("UNA"):
        una_body = stripped[3:9]
        delimiters = Delimiters(
            component_separator=una_body[0],
            element_separator=una_body[1],
            decimal_notation=una_body[2],
            release_character=una_body[3],
            segment_terminator=una_body[5],
        )
        return delimiters, stripped[9:]
    return Delimiters(), stripped


def _tokenize_segments(text: str, d: Delimiters) -> list[Segment]:
    raw_segments = _split(text, d.segment_terminator, d.release_character)
    segments: list[Segment] = []
    for raw_seg in raw_segments:
        raw_seg = raw_seg.strip()
        if not raw_seg:
            continue
        raw_elements = _split(raw_seg, d.element_separator, d.release_character)
        tag = raw_elements[0].strip()
        elements: list[list[str]] = []
        for raw_el in raw_elements[1:]:
            components = _split(raw_el, d.component_separator, d.release_character)
            elements.append(components)
        segments.append(Segment(tag=tag, elements=elements))
    return segments


def _parse_interchange_header(seg: Segment) -> InterchangeHeader:
    return InterchangeHeader(
        syntax_identifier=seg.element(0, 0, ""),
        syntax_version=seg.element(0, 1, ""),
        sender_id=seg.element(1, 0, ""),
        sender_qualifier=seg.element(1, 1, ""),
        recipient_id=seg.element(2, 0, ""),
        recipient_qualifier=seg.element(2, 1, ""),
        date=seg.element(3, 0, ""),
        time=seg.element(3, 1, ""),
        control_reference=seg.element(4, 0, ""),
        application_reference=seg.element(6, 0),
    )


def parse_edifact_file(path: str | PathLike) -> ParsedEdifactFile:
    """Parse an EDIFACT interchange file into a ParsedEdifactFile.

    A single interchange (UNB…UNZ) may contain multiple messages (UNH…UNT).
    """
    resolved = Path(path)
    raw = resolved.read_text()
    delimiters, body = _parse_delimiters(raw)
    segments = _tokenize_segments(body, delimiters)

    if not segments:
        raise EdifactParsingError("No segments found in input")

    if segments[0].tag != "UNB":
        raise EdifactParsingError("UNB interchange header must be the first segment")
    unb_seg = segments[0]

    if segments[-1].tag != "UNZ":
        raise EdifactParsingError("UNZ interchange trailer must be the last segment")

    for seg in segments[1:-1]:
        if seg.tag in ("UNB", "UNZ"):
            raise EdifactParsingError(f"Unexpected {seg.tag} segment in middle of interchange")

    interchange = _parse_interchange_header(unb_seg)

    messages: list[EdifactMessage] = []
    current_msg: EdifactMessage | None = None

    for seg in segments:
        match seg:
            case Segment("UNH", [[msg_id, *_], [msg_type, *_], *_]):
                current_msg = EdifactMessage(
                    message_type=msg_type,
                    message_id=msg_id,
                    interchange=interchange,
                )
            case Segment("UNT", _):
                if current_msg is None:
                    raise EdifactParsingError("UNT without matching UNH")
                messages.append(current_msg)
                current_msg = None
            case Segment("RFF", [["Z13", sub_id, *_], *_]) if current_msg is not None:
                current_msg.subscription_id = current_msg.subscription_id or sub_id
                current_msg.segments.append(seg)
            case Segment("LOC", [["172", *_], [metering_point, *_], *_]) if current_msg is not None:
                current_msg.metering_point_id = current_msg.metering_point_id or metering_point
                current_msg.segments.append(seg)
            case _ if current_msg is not None:
                current_msg.segments.append(seg)

    if current_msg is not None:
        raise EdifactParsingError("UNH without closing UNT")

    if not messages:
        raise EdifactParsingError("No messages found in interchange")

    return ParsedEdifactFile(
        file_path=str(resolved),
        raw_content=raw,
        messages=messages,
    )
