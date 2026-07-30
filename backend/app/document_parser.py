"""Upstage Document Parse integration for curriculum documents.

The parser deliberately returns a stable, application-owned schema.  This keeps
the timetable builder independent from the (richer and occasionally changing)
Upstage response schema.
"""

from __future__ import annotations

import html
import os
import re
from html.parser import HTMLParser
from io import BytesIO
from typing import Any

import requests


UPSTAGE_DOCUMENT_PARSE_URL = "https://api.upstage.ai/v1/document-digitization"
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024

_MEETING_PATTERN = re.compile(
    r"(?P<day_of_week>[월화수목금])(?:요일)?\s*"
    r"(?P<start_time>(?:[01]?\d|2[0-3]):[0-5]\d)\s*"
    r"\(\s*(?P<duration_minutes>\d+)\s*(?:분)?\)\s*"
    r"(?P<classroom>[A-Za-z0-9가-힣]+\s*-\s*[A-Za-z0-9-]+)"
)

_RANGE_MEETING_PATTERN = re.compile(
    r"(?P<day_of_week>[월화수목금])(?:요일)?\s*"
    r"(?P<start_time>(?:[01]?\d|2[0-3]):[0-5]\d)\s*[-~]\s*"
    r"(?P<end_time>(?:[01]?\d|2[0-3]):[0-5]\d)\s*"
    r"(?P<classroom>[A-Za-z0-9가-힣]+\s*-\s*[A-Za-z0-9-]+)"
)

_HEADER_ALIASES = {
    "code": ("교과목번호", "과목코드", "교과목코드", "course code", "code"),
    "name": ("교과목명", "과목명", "subject name", "course name", "name", "title"),
    "credits": ("학점", "credit", "credits"),
    "category": ("이수구분", "구분", "교과구분", "subject type", "category","교과목구분"),
    "instructor": ("교수명", "담당교수", "교수", "instructor", "professor"),
    "grade": ("학년", "권장학년", "grade", "year"),
    "semester": ("학기", "권장학기", "semester", "term"),
    "prerequisites": ("선수과목", "선수", "prerequisite", "prerequisites"),
    "schedule_text": ("시간/강의실", "시간", "수업시간", "강의시간", "schedule", "time"),
    "section": ("분반", "section", "class"),
    "department": ("개설학과", "개설부서", "department"),
}


class UpstageDocumentError(RuntimeError):
    """Raised when Upstage cannot process a submitted document."""


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            # A timetable cell commonly contains one meeting per line.  Keep
            # that boundary so it can be serialised without merging meetings.
            self._cell.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_normalise_cell_text("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


def parse_curriculum_document(
    *, filename: str, content: bytes, content_type: str | None = None
) -> dict[str, Any]:
    """Send a document to Upstage and return timetable-ready course records."""
    if not content:
        raise ValueError("업로드된 파일이 비어 있습니다.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("파일은 20MB 이하여야 합니다.")

    api_key = os.getenv("UPSTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY 환경 변수가 설정되지 않았습니다.")

    try:
        response = requests.post(
            UPSTAGE_DOCUMENT_PARSE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "document": (
                    filename,
                    BytesIO(content),
                    content_type or "application/octet-stream",
                )
            },
            data={"ocr": "force", "base64_encoding": "['table']", "model": "document-parse"},
            timeout=(10, 120),
        )
    except requests.RequestException as exc:
        raise UpstageDocumentError("문서 분석 서비스에 연결하지 못했습니다.") from exc

    if not response.ok:
        try:
            detail = response.json().get("message") or response.json().get("error")
        except ValueError:
            detail = None
        raise UpstageDocumentError(detail or "문서 분석 서비스가 요청을 처리하지 못했습니다.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstageDocumentError("문서 분석 서비스가 올바른 응답을 반환하지 않았습니다.") from exc

    rows = _extract_rows(payload)
    courses = _rows_to_courses(rows)
    return {
        "source_filename": filename,
        "courses": courses,
        "course_count": len(courses),
        "raw_table_count": len(rows),
    }


def _extract_rows(payload: dict[str, Any]) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    for element in payload.get("elements", []):
        if not isinstance(element, dict):
            continue
        content = element.get("content") or {}
        if not isinstance(content, dict):
            continue
        html_table = content.get("html")
        if isinstance(html_table, str) and "<tr" in html_table.lower():
            parser = _TableHTMLParser()
            parser.feed(html_table)
            if parser.rows:
                tables.append(parser.rows)
                continue
        markdown = content.get("markdown")
        if isinstance(markdown, str):
            markdown_rows = _markdown_table_rows(markdown)
            if markdown_rows:
                tables.append(markdown_rows)
    return tables


def _markdown_table_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        line = line.strip()
        if "|" not in line or re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line):
            continue
        cells = [html.unescape(cell.strip()) for cell in line.strip("|").split("|")]
        if any(cells):
            rows.append(cells)
    return rows


def _normalise_cell_text(value: str) -> str:
    """Collapse whitespace in each visual line while preserving line breaks."""
    return "\n".join(" ".join(line.split()) for line in value.splitlines() if line.strip())


def _rows_to_courses(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    courses: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str]] = set()
    for table in tables:
        if len(table) < 2:
            continue
        header = [_normalise_header(cell) for cell in table[0]]
        field_indices = _field_indices(header)
        if "name" not in field_indices:
            continue
        for row in table[1:]:
            record = _course_from_row(row, field_indices)
            if not record:
                continue
            identity = (record["code"], record["name"])
            if identity not in seen:
                courses.append(record)
                seen.add(identity)
    return courses


def _normalise_header(value: str) -> str:
    return re.sub(r"\s+", "", value).lower().replace("(미확정)", "")


def _field_indices(headers: list[str]) -> dict[str, int]:
    indices: dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for index, header in enumerate(headers):
            if any(_normalise_header(alias) in header for alias in aliases):
                indices[field] = index
                break
    return indices


def _course_from_row(row: list[str], indices: dict[str, int]) -> dict[str, Any] | None:
    def value(field: str) -> str | None:
        index = indices.get(field)
        return row[index].strip() if index is not None and index < len(row) and row[index].strip() else None

    name = value("name")
    if not name or name in {"계", "합계", "total"}:
        return None
    credit_text = value("credits")
    credit_match = re.search(r"\d+(?:\.\d+)?", credit_text or "")
    prerequisites = value("prerequisites")
    schedule_text = _normalise_schedule_text(value("schedule_text"))
    return {
        "code": value("code"),
        "name": name,
        "credits": float(credit_match.group()) if credit_match else None,
        "category": value("category"),
        "instructor": value("instructor"),
        "grade": value("grade"),
        "semester": value("semester"),
        "section": value("section"),
        "department": _normalise_department(value("department")),
        "prerequisites": _split_prerequisites(prerequisites),
        "schedule_text": schedule_text,
        "meetings": _parse_meetings(schedule_text),
    }


def _split_prerequisites(value: str | None) -> list[str]:
    if not value or value.lower() in {"없음", "none", "-"}:
        return []
    return [item.strip() for item in re.split(r"[,/;\n]+", value) if item.strip()]


def _normalise_schedule_text(value: str | None) -> str | None:
    """Return only valid meetings in the canonical timetable format.

    The source workbook uses both ``월 09:00(75) 405-2103`` and
    ``월 09:00-10:15 405-2103``.  Persist the former form for both so that
    time and classroom data are consistent regardless of the source notation.
    """
    if not value:
        return None

    text = html.unescape(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = text.translate(str.maketrans({"（": "(", "）": ")", "：": ":", "－": "-", "～": "~"}))

    meetings = _parse_meetings_from_text(text)
    return ", ".join(
        f"{meeting['day_of_week']} {meeting['start_time']}({meeting['duration_minutes']}) {meeting['classroom']}"
        for meeting in meetings
    ) or None


def _normalise_department(value: str | None) -> str | None:
    """Keep the department name, excluding the contact line in source cells."""
    if not value:
        return None

    text = html.unescape(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    name = next((" ".join(line.split()) for line in text.splitlines() if line.strip()), "")
    # Some OCR results keep the phone number on the same line as the department.
    name = re.sub(r"\s*\([^)]*\d{2,4}\s*[-|]\s*\d{3,4}\s*[-|]\s*\d{4}[^)]*\)\s*$", "", name)
    return name or None


def _parse_meetings(schedule_text: str | None) -> list[dict[str, str | int]]:
    """Extract individually persistable meeting data from a timetable cell.

    Unrecognised text remains available in ``schedule_text`` rather than being
    guessed or discarded.
    """
    return _parse_meetings_from_text(schedule_text or "")


def _parse_meetings_from_text(value: str) -> list[dict[str, str | int]]:
    meetings: list[dict[str, str | int]] = []
    for match in _MEETING_PATTERN.finditer(value):
        meetings.append({
            "day_of_week": match.group("day_of_week"),
            "start_time": match.group("start_time").zfill(5),
            "duration_minutes": int(match.group("duration_minutes")),
            "classroom": re.sub(r"\s*[-]\s*", "-", match.group("classroom")),
        })
    for match in _RANGE_MEETING_PATTERN.finditer(value):
        start_hour, start_minute = map(int, match.group("start_time").split(":"))
        end_hour, end_minute = map(int, match.group("end_time").split(":"))
        duration_minutes = end_hour * 60 + end_minute - start_hour * 60 - start_minute
        if duration_minutes > 0:
            meetings.append({
                "day_of_week": match.group("day_of_week"),
                "start_time": match.group("start_time").zfill(5),
                "duration_minutes": duration_minutes,
                "classroom": re.sub(r"\s*[-]\s*", "-", match.group("classroom")),
            })
    return meetings
