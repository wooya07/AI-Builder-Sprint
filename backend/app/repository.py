import json
from pathlib import Path

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


def _time_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":", maxsplit=1)
    hour, minute = int(hour_text), int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Invalid time")
    return hour * 60 + minute
