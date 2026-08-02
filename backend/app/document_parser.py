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
_COURSE_CODE_PATTERN = re.compile(r"^[A-Za-z]{2,5}\d{5,9}$")
_COURSE_CODE_FRAGMENT_PATTERN = re.compile(r"[A-Za-z]{2,5}\s*\d[\d\s]{4,8}")

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
        self._raw_rows: list[list[tuple[str, int, int]]] = []
        self._row: list[tuple[str, int, int]] | None = None
        self._cell: list[str] | None = None
        self._rowspan = 1
        self._colspan = 1

    @property
    def rows(self) -> list[list[str]]:
        return _expand_table_cells(self._raw_rows)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            attributes = dict(attrs)
            self._rowspan = _span_value(attributes.get("rowspan"))
            self._colspan = _span_value(attributes.get("colspan"))
        elif tag == "br" and self._cell is not None:
            # A timetable cell commonly contains one meeting per line.  Keep
            # that boundary so it can be serialised without merging meetings.
            self._cell.append("\n")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append((_normalise_cell_text("".join(self._cell)), self._rowspan, self._colspan))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self._raw_rows.append(self._row)
            self._row = None


def _span_value(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _expand_table_cells(rows: list[list[tuple[str, int, int]]]) -> list[list[str]]:
    """Expand HTML rowspan/colspan cells into a rectangular value matrix."""
    expanded: list[list[str]] = []
    active_spans: dict[int, tuple[str, int]] = {}

    for source_row in rows:
        row: list[str] = []
        column = 0

        def fill_active_spans() -> None:
            nonlocal column
            while column in active_spans:
                value, remaining = active_spans[column]
                row.append(value)
                if remaining == 1:
                    del active_spans[column]
                else:
                    active_spans[column] = (value, remaining - 1)
                column += 1

        for value, rowspan, colspan in source_row:
            fill_active_spans()
            for offset in range(colspan):
                row.append(value)
                if rowspan > 1:
                    active_spans[column + offset] = (value, rowspan - 1)
            column += colspan
        fill_active_spans()
        expanded.append(row)

    width = max((len(row) for row in expanded), default=0)
    return [row + [""] * (width - len(row)) for row in expanded]


def parse_curriculum_document(
    *,
    filename: str,
    content: bytes,
    content_type: str | None = None,
    include_upstage_debug: bool = False,
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

    extracted = _extract_rows(payload, include_debug=include_upstage_debug)
    rows, upstage_debug = extracted if include_upstage_debug else (extracted, [])
    courses = _rows_to_courses(rows)
    result: dict[str, Any] = {
        "source_filename": filename,
        "courses": courses,
        "course_count": len(courses),
        "raw_table_count": len(rows),
    }
    if include_upstage_debug:
        result["upstage_debug"] = upstage_debug
    return result


def _extract_rows(
    payload: dict[str, Any], *, include_debug: bool = False,
) -> list[list[list[str]]] | tuple[list[list[list[str]]], list[dict[str, Any]]]:
    tables: list[list[list[str]]] = []
    debug_tables: list[dict[str, Any]] = []
    for element_index, element in enumerate(payload.get("elements", [])):
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
                if include_debug:
                    debug_tables.append({
                        "element_index": element_index,
                        "source": "html",
                        "raw_content": html_table,
                        "rows": parser.rows,
                    })
                continue
        markdown = content.get("markdown")
        if isinstance(markdown, str):
            markdown_rows = _markdown_table_rows(markdown)
            if markdown_rows:
                tables.append(markdown_rows)
                if include_debug:
                    debug_tables.append({
                        "element_index": element_index,
                        "source": "markdown",
                        "raw_content": markdown,
                        "rows": markdown_rows,
                    })
    return (tables, debug_tables) if include_debug else tables


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
        # A continuation element may contain only one compact row with several
        # course codes, names, credit values, and semesters.
        if not table:
            continue
        header_end, field_indices = _find_header(table)
        if header_end is None or "name" not in field_indices:
            for record in _rows_from_headerless_curriculum_table(table):
                identity = (record["code"], record["name"])
                if identity not in seen:
                    courses.append(record)
                    seen.add(identity)
            continue
        for row in table[header_end:]:
            record = _course_from_row(row, field_indices)
            if not record:
                continue
            identity = (record["code"], record["name"])
            if identity not in seen:
                courses.append(record)
                seen.add(identity)
    return courses


def _rows_from_headerless_curriculum_table(table: list[list[str]]) -> list[dict[str, Any]]:
    """Parse continuation tables whose merged header is returned separately.

    Upstage can return a curriculum section without its header.  In that form,
    columns are ``major category, detailed category, course code, course name,
    credits, grade-semester, note``.  A rowspan course-code cell may contain a
    sequence of codes intended for the following course-name rows.
    """
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(table):
        row = table[index]
        raw_code = _cell_at(row, 2)
        name = _cell_at(row, 3)
        codes = _extract_course_codes(raw_code)
        if not codes or _is_summary_row(raw_code, name):
            index += 1
            continue

        repeated_rows = [row]
        next_index = index + 1
        while next_index < len(table) and _cell_at(table[next_index], 2) == raw_code:
            repeated_rows.append(table[next_index])
            next_index += 1

        if len(codes) == len(repeated_rows):
            for course_code, course_row in zip(codes, repeated_rows):
                record = _course_from_headerless_row(course_row, course_code)
                if record:
                    records.append(record)
            index = next_index
            continue

        if len(codes) == 1:
            record = _course_from_headerless_row(row, codes[0])
            if record:
                records.append(record)
        else:
            names = _split_course_names(name)
            credits = re.findall(r"\d+(?:-\d+){2}", _cell_at(row, 4))
            terms = re.findall(r"\d+(?:-\d+(?:,\d+)?)?", _cell_at(row, 5))
            if len(names) == len(credits) == len(terms) == len(codes):
                category = _cell_at(row, 1) or _cell_at(row, 0)
                for course_code, course_name, credit, term in zip(codes, names, credits, terms):
                    record = _course_from_headerless_values(category, course_code, course_name, credit, term)
                    if record:
                        records.append(record)
        index += 1
    return records


def _cell_at(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def _extract_course_codes(value: str) -> list[str]:
    return [
        code
        for code in (_normalise_course_code(fragment) for fragment in _COURSE_CODE_FRAGMENT_PATTERN.findall(value))
        if code and _COURSE_CODE_PATTERN.fullmatch(code)
    ]


def _course_from_headerless_row(row: list[str], code: str) -> dict[str, Any] | None:
    category = _cell_at(row, 1) or _cell_at(row, 0)
    return _course_from_headerless_values(
        category, code, _cell_at(row, 3), _cell_at(row, 4), _cell_at(row, 5)
    )


def _course_from_headerless_values(
    category: str, code: str, name: str, credits: str, term: str,
) -> dict[str, Any] | None:
    return _course_from_row(
        [category, code, name, credits, term],
        {"category": 0, "code": 1, "name": 2, "credits": 3, "grade": 4, "semester": 4},
    )


def _split_course_names(value: str) -> list[str]:
    """Split Korean course names that are followed by parenthesized English names."""
    return [
        name.strip()
        for name in re.split(r"(?<=\))\s+(?=[가-힣◎♤])", value)
        if name.strip()
    ]


def _find_header(table: list[list[str]]) -> tuple[int | None, dict[str, int]]:
    """Locate a one- or two-row header and preserve columns from merged headers."""
    best_end: int | None = None
    best_indices: dict[str, int] = {}
    best_score = 0
    scan_limit = min(5, len(table))
    for start in range(scan_limit):
        for height in (1, 2):
            end = start + height
            if end > len(table):
                continue
            width = max(len(row) for row in table[start:end])
            headers = [
                _normalise_header(" ".join(row[column] for row in table[start:end] if column < len(row)))
                for column in range(width)
            ]
            indices = _field_indices(headers)
            year_semester_index = next(
                (index for index, header in enumerate(headers) if "학년" in header and "학기" in header),
                None,
            )
            if year_semester_index is not None:
                indices["grade"] = year_semester_index
                indices["semester"] = year_semester_index
            category_indices = [
                index
                for index, header in enumerate(headers)
                if "이수구분" in header or "교과목구분" in header
            ]
            if len(category_indices) > 1:
                indices["category_detail"] = category_indices[-1]
            score = len(indices) + (3 if "name" in indices else 0) + (2 if "code" in indices else 0)
            if "name" in indices and score > best_score:
                best_end, best_indices, best_score = end, indices, score
    return best_end, best_indices


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

    raw_code = value("code")
    name = value("name")
    if not name or _is_summary_row(raw_code, name):
        return None
    if raw_code and len(_COURSE_CODE_FRAGMENT_PATTERN.findall(raw_code)) > 1:
        return None
    code = _normalise_course_code(raw_code)
    credit_text = value("credits")
    credit_match = re.search(r"\d+(?:\.\d+)?", credit_text or "")
    prerequisites = value("prerequisites")
    schedule_text = _normalise_schedule_text(value("schedule_text"))
    grade = value("grade")
    semester = value("semester")
    if grade and grade == semester:
        year_term = re.fullmatch(r"\s*(\d+)\s*[-/]\s*([\d,\s]+)\s*", grade)
        if year_term:
            grade, semester = year_term.groups()
    return {
        "code": code,
        "name": name,
        "credits": float(credit_match.group()) if credit_match else None,
        "category": _normalise_category(value("category_detail") or value("category")),
        "instructor": value("instructor"),
        "grade": grade,
        "semester": semester,
        "section": value("section"),
        "department": _normalise_department(value("department")),
        "prerequisites": _split_prerequisites(prerequisites),
        "schedule_text": schedule_text,
        "meetings": _parse_meetings(schedule_text),
    }


def _is_summary_row(code: str | None, name: str) -> bool:
    combined = f"{code or ''} {name}".casefold()
    return any(marker in combined for marker in ("소계", "합계", "total"))


def _normalise_category(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", "", value)
    if "효원핵심교양" in compact:
        return "효원핵심교양"
    return value.strip()


def _normalise_course_code(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return compact if _COURSE_CODE_PATTERN.fullmatch(compact) else value.strip()


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
