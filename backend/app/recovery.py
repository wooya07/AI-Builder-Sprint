from .activity_service import to_minutes, to_time
from .models import (
    Activity, AvailableSlot, InefficiencyModeConfig, Recommendation,
    RecoveryAnalysis, RecoveryBlock, RecoveryScoreDetails, ScheduledClass,
)

RECOVERY_CATEGORIES = {"REST", "HOBBY", "SOCIAL"}
FOCUS_CATEGORIES = {"STUDY", "PART_TIME_JOB"}


def apply_inefficiency_mode(
    recommendations: list[Recommendation],
    activities: list[Activity],
    classes: list[ScheduledClass],
    slots: list[AvailableSlot],
    config: InefficiencyModeConfig,
) -> tuple[list[Recommendation], list[RecoveryBlock], RecoveryAnalysis, list[str]]:
    condition = config.weekly_condition if config.weekly_condition is not None else 50
    warnings: list[str] = []
    total_available = sum(slot.duration_minutes for slot in slots)
    density_budget = round(total_available * config.target_schedule_density / 100)
    condition_factor = {100: 1.0, 75: .9, 50: .75, 25: .5, 0: .25}[condition]
    optional_budget = round(density_budget * condition_factor)
    activity_map = {activity.activity_id: activity for activity in activities}
    required = [item for item in recommendations if activity_map[item.activity_id].priority == "REQUIRED"]
    optional = [item for item in recommendations if activity_map[item.activity_id].priority != "REQUIRED"]
    required_minutes = sum(item.duration_minutes for item in required)
    if required_minutes > density_budget:
        warnings.append(
            f"필수 활동을 모두 배치하려면 설정한 일정 밀도 {config.target_schedule_density}%를 초과해야 합니다."
        )
    kept = list(required)
    used = required_minutes
    for item in optional:
        if used + item.duration_minutes <= max(optional_budget, required_minutes):
            kept.append(item)
            used += item.duration_minutes

    recovery_blocks: list[RecoveryBlock] = []
    if config.auto_recovery_enabled and config.enabled:
        occupied = [(to_minutes(item.start_time), to_minutes(item.end_time)) for item in kept]
        reason = (
            "LOW_CONDITION" if condition <= 25 else
            "USER_DENSITY_SETTING" if config.target_schedule_density <= 50 else
            "HIGH_SCHEDULE_DENSITY"
        )
        for slot in slots:
            start, end = to_minutes(slot.start_time), to_minutes(slot.end_time)
            cursor = start
            for busy_start, busy_end in sorted(occupied):
                if busy_end <= cursor or busy_start >= end:
                    continue
                if busy_start - cursor >= config.minimum_recovery_minutes:
                    break
                cursor = max(cursor, busy_end)
            if end - cursor >= config.minimum_recovery_minutes:
                recovery_blocks.append(RecoveryBlock(
                    start_time=to_time(cursor),
                    end_time=to_time(cursor + config.minimum_recovery_minutes),
                    duration_minutes=config.minimum_recovery_minutes,
                    reason=reason,
                ))
                break

    analysis = calculate_recovery_score(classes, kept, activities, slots, recovery_blocks, config)
    return kept, recovery_blocks, analysis, warnings


def calculate_recovery_score(
    classes: list[ScheduledClass], recommendations: list[Recommendation],
    activities: list[Activity], slots: list[AvailableSlot],
    recovery_blocks: list[RecoveryBlock], config: InefficiencyModeConfig,
) -> RecoveryAnalysis:
    activity_map = {activity.activity_id: activity for activity in activities}
    placed_minutes = sum(item.duration_minutes for item in recommendations)
    total_slot_minutes = sum(item.duration_minutes for item in slots)
    recovery_minutes = sum(item.duration_minutes for item in recovery_blocks)
    intentional_free = max(0, total_slot_minutes - placed_minutes)
    total_rest = recovery_minutes + intentional_free
    rest_score = 40 if total_rest >= 120 else 30 if total_rest >= 60 else 15 if total_rest >= 30 else 0

    day_minutes = max(1, to_minutes(config.daily_end_time) - to_minutes(config.daily_start_time))
    class_minutes = sum(to_minutes(item.end_time) - to_minutes(item.start_time) for item in classes)
    density = round((class_minutes + placed_minutes) / day_minutes * 100)
    density_score = 25 if density <= 60 else 20 if density <= 75 else 10 if density <= 85 else 0

    focus_ranges = [
        (to_minutes(item.start_time), to_minutes(item.end_time)) for item in classes
    ] + [
        (to_minutes(item.start_time), to_minutes(item.end_time))
        for item in recommendations
        if activity_map[item.activity_id].category in FOCUS_CATEGORIES
    ]
    longest = _longest_continuous(focus_ranges)
    focus_score = 20 if longest <= 120 else 15 if longest <= 180 else 5 if longest <= 240 else 0

    recovery_items = [
        item for item in recommendations
        if activity_map[item.activity_id].category in RECOVERY_CATEGORIES
    ]
    recovery_activity_minutes = sum(item.duration_minutes for item in recovery_items) + recovery_minutes
    kinds = {activity_map[item.activity_id].category for item in recovery_items}
    if recovery_blocks:
        kinds.add("RECOVERY_BLOCK")
    recovery_score = (
        15 if len(kinds) >= 2 and recovery_activity_minutes >= 60 else
        10 if kinds and recovery_activity_minutes >= 30 else
        5 if kinds else 0
    )
    score = max(0, min(100, rest_score + density_score + focus_score + recovery_score))
    grade = 1 if score >= 80 else 2 if score >= 60 else 3 if score >= 40 else 4
    messages = {
        1: "회복이 충분한 일정이에요.", 2: "비교적 균형 잡힌 일정이에요.",
        3: "휴식이 조금 부족해요.", 4: "회복 시간을 더 확보하는 것이 좋아요.",
    }
    return RecoveryAnalysis(
        score=score, grade=grade, status_message=messages[grade],
        details=RecoveryScoreDetails(
            rest_time_score=rest_score, schedule_density_score=density_score,
            continuous_focus_score=focus_score, recovery_activity_score=recovery_score,
        ),
        total_rest_minutes=total_rest, schedule_density_percent=density,
        longest_continuous_focus_minutes=longest,
        recovery_activity_minutes=recovery_activity_minutes,
        explanation=messages[grade],
    )


def _longest_continuous(ranges: list[tuple[int, int]]) -> int:
    if not ranges:
        return 0
    ordered = sorted(ranges)
    longest = 0
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start - end < 15:
            end = max(end, next_end)
        else:
            longest = max(longest, end - start)
            start, end = next_start, next_end
    return max(longest, end - start)
