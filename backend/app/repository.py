import json
from pathlib import Path
import re
from typing import Any

from .models import Course, Meeting


CATALOG_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "course_catalog.json"
DAY_NAMES = {"MON": "\uc6d4", "TUE": "\ud654", "WED": "\uc218", "THU": "\ubaa9", "FRI": "\uae08"}

COURSES: list[Course] = [
    Course(code="CS201", name="Data Structures", credits=3, category="Major Required", instructor="Kim", meetings=[{"day": "\uc6d4", "start": 13, "end": 15}, {"day": "\uc218", "start": 13, "end": 15}]),
    Course(code="CS203", name="Web Programming", credits=3, category="Major Elective", instructor="Park", meetings=[{"day": "\ud654", "start": 13, "end": 15}, {"day": "\ubaa9", "start": 13, "end": 15}]),
    Course(code="GE101", name="Writing", credits=3, category="General Education", instructor="Choi", meetings=[{"day": "\uc6d4", "start": 10, "end": 12}, {"day": "\uc218", "start": 10, "end": 12}]),
    Course(code="GE102", name="English Conversation", credits=3, category="General Education", instructor="Jung", meetings=[{"day": "\ud654", "start": 15, "end": 17}, {"day": "\ubaa9", "start": 15, "end": 17}]),
]


def list_courses() -> list[Course]:
    """Load each class group as one selectable course with all of its meetings."""
    if not CATALOG_JSON_PATH.exists():
        return COURSES

    try:
        payload = json.loads(CATALOG_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return COURSES

    grouped_courses: dict[str, Course] = {}
    for item in payload.get("classes", []):
        if not isinstance(item, dict):
            continue
        course_id = str(item.get("courseId", "")).strip()
        section = str(item.get("section", "")).strip()
        group_id = str(item.get("classGroupId") or f"{course_id}-{section}")
        day = DAY_NAMES.get(str(item.get("day", "")))
        location = item.get("location")
        if not course_id or not day or not isinstance(location, dict):
            continue
        try:
            start_minutes = _time_to_minutes(str(item["startTime"]))
            end_minutes = _time_to_minutes(str(item["endTime"]))
            credits = int(item["credits"])
        except (KeyError, TypeError, ValueError):
            continue
        if end_minutes <= start_minutes or credits < 1:
            continue

        course = grouped_courses.get(group_id)
        if course is None:
            course = Course(
                code=course_id,
                class_group_id=group_id,
                name=str(item.get("courseName", "")),
                credits=credits,
                category=str(item.get("courseType") or "Unclassified"),
                instructor=str(item.get("instructor", "")),
                meetings=[],
                grade=str(item.get("grade") or "") or None,
                section=section or None,
                department=str(item.get("department") or "") or None,
            )
            grouped_courses[group_id] = course

        course.meetings.append(Meeting(
            day=day,
            start=start_minutes // 60,
            end=(end_minutes + 59) // 60,
            start_minutes=start_minutes,
            duration_minutes=end_minutes - start_minutes,
            building=str(location.get("building") or ""),
            room=str(location.get("room") or ""),
        ))
    return sorted(grouped_courses.values(), key=lambda course: (course.code, course.section or "")) or COURSES


def match_curriculum_courses(curriculum_courses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Attach catalog matches to Document Parse course rows.

    Document OCR can corrupt the numeric portion of a course code.  Prefer a
    match that combines its department prefix (the first two characters) and
    its normalised course name, then expose the catalog's canonical code.
    """
    catalog = list_courses()
    by_code: dict[str, set[str]] = {}
    by_prefix_and_name: dict[tuple[str, str], set[str]] = {}
    for course in catalog:
        by_code.setdefault(course.code.casefold(), set()).add(course.code)
        normalised_name = _normalise_course_name(course.name)
        if len(course.code) >= 2:
            by_prefix_and_name.setdefault((course.code[:2].casefold(), normalised_name), set()).add(course.code)

    matched_rows: list[dict[str, Any]] = []
    available_codes: set[str] = set()
    for course in curriculum_courses:
        row = dict(course)
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        normalised_name = _normalise_course_name(name) if name else ""
        matches: set[str] = set()
        match_type = None
        match_reason = None
        if len(code) >= 2 and normalised_name:
            matches = by_prefix_and_name.get((code[:2].casefold(), normalised_name), set())
            match_type = "prefix_name" if matches else None
            match_reason = "prefix_name" if matches else None
        elif code:
            matches = by_code.get(code.casefold(), set())
            match_type = "code" if matches else None
            match_reason = "code" if matches else None
        matched_codes = sorted(matches)
        if not match_reason:
            match_reason = "catalog_code_not_found" if code else "catalog_name_not_found"
        row["catalog_course_codes"] = matched_codes
        if matched_codes:
            row["document_code"] = code or None
            row["code"] = matched_codes[0]
        row["match_type"] = match_type
        row["match_reason"] = match_reason
        matched_rows.append(row)
        available_codes.update(matched_codes)
    return matched_rows, sorted(available_codes)


def _time_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":", maxsplit=1)
    hour, minute = int(hour_text), int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid time")
    return hour * 60 + minute


def _normalise_course_name(value: str) -> str:
    # Document OCR can append a table cell's next value after an English
    # translation, e.g. "Probabilities and Statistics) 2". Only discard that
    # final standalone number when the source contains an English translation.
    has_ocr_trailing_number = bool(
        re.search(r"\)\s+\d+\s*$", value) and re.search(r"[A-Za-z]{3,}", value)
    )
    if has_ocr_trailing_number:
        value = re.sub(r"\s+\d+\s*$", "", value)
    return re.sub(r"[^0-9a-z가-힣]", "", _without_english_translation(value).casefold())


def _without_english_translation(value: str) -> str:
    """Remove parenthesized English translations from otherwise Korean names.

    Course names such as ``일반물리학(II)(General Physics(II))`` retain their
    Korean name and roman-numeral suffix, while matching the catalog's
    ``일반물리학(II)`` entry.
    """
    if not re.search(r"[가-힣]", value):
        return value

    stack: list[int] = []
    candidates: list[tuple[int, int]] = []
    for index, character in enumerate(value):
        if character == "(":
            stack.append(index)
        elif character == ")" and stack:
            start = stack.pop()
            if re.search(r"[A-Za-z]{3,}", value[start + 1:index]):
                candidates.append((start, index + 1))

    outermost = [
        candidate
        for candidate in candidates
        if not any(other[0] < candidate[0] and candidate[1] < other[1] for other in candidates)
    ]
    for start, end in sorted(outermost, reverse=True):
        value = value[:start] + value[end:]
    return value
