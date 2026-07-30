from app.activity_service import calculate_available_slots, make_local_recommendations
from app.models import Activity, InefficiencyModeConfig, ScheduledClass
from app.recovery import apply_inefficiency_mode


def test_inefficiency_mode_reserves_recovery_and_calculates_stable_score():
    classes = [ScheduledClass(
        course_id="TEST", class_group_id="TEST-001", course_name="테스트",
        day="MON", start_time="10:00", end_time="12:00",
    )]
    activities = [
        Activity(
            activity_id="required", category="STUDY", activity_name="필수",
            priority="REQUIRED", schedule_type="FLEXIBLE_DAY",
            duration_minutes=60, frequency_per_week=1,
        ),
        Activity(
            activity_id="optional", category="HOBBY", activity_name="선택",
            priority="OPTIONAL", schedule_type="FLEXIBLE_DAY",
            duration_minutes=120, frequency_per_week=1,
        ),
    ]
    slots = calculate_available_slots(classes, "MON")
    recommendations, _ = make_local_recommendations(activities, slots, "MON")
    config = InefficiencyModeConfig(
        enabled=True, target_schedule_density=25, weekly_condition=25,
        auto_recovery_enabled=True,
    )
    first = apply_inefficiency_mode(recommendations, activities, classes, slots, config)
    second = apply_inefficiency_mode(recommendations, activities, classes, slots, config)

    assert [item.activity_id for item in first[0]] == ["required"]
    assert first[1][0].type == "RECOVERY_BLOCK"
    assert first[2].score == second[2].score
    assert 0 <= first[2].score <= 100
