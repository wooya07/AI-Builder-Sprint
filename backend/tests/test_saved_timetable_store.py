import json

from app.models import Course, SavedTimetable
from app import saved_timetable_store


def test_saved_timetable_round_trips_complete_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(saved_timetable_store, "SAVED_TIMETABLES_PATH", tmp_path / "saved_timetables.json")
    timetable = SavedTimetable.model_validate({
        "timezone": "Asia/Seoul",
        "classes": [{
            "course_id": "CB1501012", "class_group_id": "CB1501012-001",
            "course_name": "확률통계", "day": "MON", "start_time": "09:00", "end_time": "10:15",
            "instructor": "김교수", "location": {"building": "101", "room": "201"},
        }],
        "activities": [{
            "activity_id": "study-1", "category": "STUDY", "activity_name": "복습", "priority": "OPTIONAL",
            "schedule_type": "FLEXIBLE_DAY", "duration_minutes": 60, "frequency_per_week": 2,
            "completed_count_this_week": 0, "preferred_days": [], "preferred_time_range": None,
        }],
        "recommendations": [{
            "day": "MON", "activity_id": "study-1", "activity_name": "복습", "category": "STUDY",
            "slot_type": "BETWEEN_CLASSES", "start_time": "11:00", "end_time": "12:00",
            "duration_minutes": 60, "reason": "빈 시간", "status": "AVAILABLE",
        }],
        "recovery_blocks": [{
            "day": "MON", "start_time": "12:00", "end_time": "12:30", "duration_minutes": 30,
            "reason": "HIGH_SCHEDULE_DENSITY",
        }],
    })

    code = saved_timetable_store.save_timetable(timetable)
    restored = saved_timetable_store.load_timetable(code)

    assert len(code) == 8
    assert restored == timetable


def test_catalog_classes_are_saved_as_compact_references(tmp_path, monkeypatch):
    path = tmp_path / "saved_timetables.json"
    monkeypatch.setattr(saved_timetable_store, "SAVED_TIMETABLES_PATH", path)
    monkeypatch.setattr(saved_timetable_store, "list_courses", lambda: [Course(
        code="CB1501012", class_group_id="CB1501012-001", name="확률통계", credits=3,
        category="전공기초", instructor="김교수", section="001",
        meetings=[{"day": "월", "start": 9, "end": 10, "start_minutes": 540, "duration_minutes": 75, "building": "108", "room": "9306"}],
    )])
    timetable = SavedTimetable.model_validate({
        "classes": [{"course_id": "CB1501012", "class_group_id": "CB1501012-001", "course_name": "확률통계", "day": "MON", "start_time": "09:00", "end_time": "10:15", "location": {}}],
    })

    code = saved_timetable_store.save_timetable(timetable)
    stored = json.loads(path.read_text(encoding="utf-8"))[code]
    restored = saved_timetable_store.load_timetable(code)

    assert stored["course_refs"] == [{"course_id": "CB1501012", "class_group_id": "CB1501012-001"}]
    assert "classes" not in stored
    assert restored is not None
    assert restored.classes[0].credits == 3
    assert restored.classes[0].location.building == "108"
