from app.models import ScheduledClass, Location, InefficiencyModeConfig
from app.recovery import calculate_recovery_score, adjust_recommendations


def course(day: str, start: str, end: str) -> ScheduledClass:
    return ScheduledClass(courseId=f"{day}-{start}", classGroupId=f"{day}-{start}", courseName="테스트 수업", day=day, startTime=start, endTime=end, location=Location())


def test_score_is_calculated_from_classes_only():
    result = calculate_recovery_score([
        course("MON", "09:00", "10:30"),
        course("MON", "12:00", "13:30"),
    ])
    assert 0 <= result.score <= 100
    assert result.score_details.recovery_activity_score == 0
    assert result.calculated_from == ["SEMESTER_TIMETABLE"]


def test_empty_timetable_does_not_fail():
    result = calculate_recovery_score([])
    assert result.score == 85
    assert result.grade == 1
