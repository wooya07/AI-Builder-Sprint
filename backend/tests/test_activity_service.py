import pytest
from app.activity_service import calculate_available_slots, make_local_recommendations
from app.models import Activity, ScheduledClass


def scheduled_class(course_id: str, start: str, end: str) -> ScheduledClass:
    return ScheduledClass(
        course_id=course_id, course_name=course_id, day="MON",
        start_time=start, end_time=end,
    )


def test_calculates_between_classes_and_after_classes():
    slots = calculate_available_slots(
        [scheduled_class("CSE101", "10:30", "12:00"), scheduled_class("MATH101", "15:00", "16:30")],
        "MON", "22:00",
    )
    assert [(slot.slot_type, slot.start_time, slot.end_time, slot.duration_minutes) for slot in slots] == [
        ("BETWEEN_CLASSES", "12:00", "15:00", 180),
        ("AFTER_CLASSES", "16:30", "22:00", 330),
    ]


def test_rejects_overlapping_classes():
    with pytest.raises(ValueError, match="겹칩니다"):
        calculate_available_slots(
            [scheduled_class("A", "10:00", "12:00"), scheduled_class("B", "11:30", "13:00")],
            "MON",
        )


def test_ignores_gaps_shorter_than_fifteen_minutes():
    slots = calculate_available_slots(
        [scheduled_class("A", "10:00", "12:00"), scheduled_class("B", "12:10", "13:00")],
        "MON", "13:10",
    )
    assert slots == []


def test_required_fixed_day_activity_is_placed_in_preferred_time():
    slots = calculate_available_slots([scheduled_class("A", "10:00", "16:30")], "MON")
    activity = Activity(
        activity_id="activity-1", category="EXERCISE", activity_name="테스트 활동",
        priority="REQUIRED", schedule_type="FIXED_DAY", duration_minutes=60,
        frequency_per_week=2, preferred_days=["MON"],
        preferred_time_range={"start_time": "17:00", "end_time": "21:00"},
    )
    recommendations, unassigned = make_local_recommendations([activity], slots, "MON")
    assert recommendations[0].start_time == "17:00"
    assert recommendations[0].end_time == "18:00"
    assert recommendations[0].status == "AVAILABLE"
    assert unassigned == []


def test_accepts_camel_case_class_json_and_deduplicates_by_class_group():
    payload = {
        "courseId": "TEST101",
        "classGroupId": "TEST101-001",
        "courseName": "테스트 과목",
        "day": "TUE",
        "startTime": "10:00",
        "endTime": "11:40",
        "grade": "1",
        "courseType": "일반선택",
        "section": "001",
        "credits": 2,
        "instructor": "테스트 강사",
        "department": "테스트 학과",
        "location": {"building": "100", "room": "200"},
    }
    parsed = ScheduledClass.model_validate(payload)
    assert parsed.class_group_id == "TEST101-001"
    with pytest.raises(ValueError, match="중복"):
        calculate_available_slots([parsed, parsed], "TUE")
