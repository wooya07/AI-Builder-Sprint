"""Small JSON-backed storage for timetable export and restoration codes."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from .models import SavedCourseReference, SavedTimetable, ScheduledClass, StoredTimetable
from .repository import list_courses


SAVED_TIMETABLES_PATH = Path(__file__).resolve().parent.parent / "data" / "saved_timetables.json"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def save_timetable(timetable: SavedTimetable) -> str:
    """Persist catalog references only, retaining full data just for custom classes."""
    saved = _load_saved_timetables()
    code = _new_code(saved)
    saved[code] = _compact_timetable(timetable).model_dump(mode="json")
    _write_saved_timetables(saved)
    return code


def load_timetable(code: str) -> SavedTimetable | None:
    payload = _load_saved_timetables().get(code.upper())
    if not isinstance(payload, dict):
        return None
    # Preserve restore compatibility for exports made before compact storage.
    if "classes" in payload:
        return SavedTimetable.model_validate(payload)
    return _restore_timetable(StoredTimetable.model_validate(payload))


def _compact_timetable(timetable: SavedTimetable) -> StoredTimetable:
    catalog_group_ids = {course.class_group_id for course in list_courses() if course.class_group_id}
    refs: dict[str, SavedCourseReference] = {}
    custom_classes: list[ScheduledClass] = []
    for scheduled_class in timetable.classes:
        group_id = scheduled_class.class_group_id
        if group_id and group_id in catalog_group_ids:
            refs.setdefault(group_id, SavedCourseReference(course_id=scheduled_class.course_id, class_group_id=group_id))
        else:
            custom_classes.append(scheduled_class)
    return StoredTimetable(
        timezone=timetable.timezone,
        course_refs=list(refs.values()),
        custom_classes=custom_classes,
        activities=timetable.activities,
        recommendations=timetable.recommendations,
        recovery_blocks=timetable.recovery_blocks,
    )


def _restore_timetable(stored: StoredTimetable) -> SavedTimetable:
    catalog_by_group = {course.class_group_id: course for course in list_courses() if course.class_group_id}
    classes = [
        scheduled_class
        for reference in stored.course_refs
        for scheduled_class in _catalog_classes(reference, catalog_by_group.get(reference.class_group_id))
    ]
    return SavedTimetable(
        timezone=stored.timezone,
        classes=[*classes, *stored.custom_classes],
        activities=stored.activities,
        recommendations=stored.recommendations,
        recovery_blocks=stored.recovery_blocks,
    )


def _catalog_classes(reference: SavedCourseReference, course: object) -> list[ScheduledClass]:
    if course is None:
        return []
    day_codes = {"월": "MON", "화": "TUE", "수": "WED", "목": "THU", "금": "FRI"}
    classes: list[ScheduledClass] = []
    for meeting in course.meetings:
        day = day_codes.get(meeting.day)
        if day is None:
            continue
        start_minutes = meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60
        duration = meeting.duration_minutes if meeting.duration_minutes is not None else (meeting.end - meeting.start) * 60
        end_minutes = start_minutes + duration
        classes.append(ScheduledClass(
            course_id=course.code,
            class_group_id=reference.class_group_id,
            course_name=course.name,
            day=day,
            start_time=_time_label(start_minutes),
            end_time=_time_label(end_minutes),
            grade=course.grade,
            course_type=course.category,
            section=course.section,
            credits=course.credits,
            instructor=course.instructor,
            department=course.department,
            location={"building": meeting.building or "", "room": meeting.room or ""},
        ))
    return classes


def _time_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _new_code(saved: dict[str, object]) -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if code not in saved:
            return code


def _load_saved_timetables() -> dict[str, object]:
    if not SAVED_TIMETABLES_PATH.exists():
        return {}
    try:
        payload = json.loads(SAVED_TIMETABLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_saved_timetables(saved: dict[str, object]) -> None:
    SAVED_TIMETABLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SAVED_TIMETABLES_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(saved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(SAVED_TIMETABLES_PATH)
