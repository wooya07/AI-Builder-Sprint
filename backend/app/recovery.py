from .activity_service import to_minutes, to_time
from .models import (
    Activity, AvailableSlot, InefficiencyModeConfig, Recommendation,
    RecoveryAnalysis, RecoveryBlock, RecoveryScoreDetails, ScheduledClass,
)

RECOVERY_CATEGORIES = {"REST", "HOBBY", "SOCIAL"}


def adjust_recommendations(
    recommendations: list[Recommendation], activities: list[Activity],
    slots: list[AvailableSlot], config: InefficiencyModeConfig,
) -> tuple[list[Recommendation], list[RecoveryBlock]]:
    if not config.enabled:
        return recommendations, []
    activity_map = {item.activity_id: item for item in activities}
    required = [item for item in recommendations if activity_map[item.activity_id].priority == "REQUIRED"]
    optional = sorted(
        [item for item in recommendations if activity_map[item.activity_id].priority != "REQUIRED"],
        key=lambda item: item.duration_minutes,
    )
    available = sum(item.duration_minutes for item in slots)
    condition_factor = {100: 1, 75: .85, 50: .65, 25: .4, 0: .15}[config.weekly_condition]
    budget = round(available * config.target_schedule_density / 100 * condition_factor)
    kept, used = list(required), sum(item.duration_minutes for item in required)
    for item in optional:
        if used + item.duration_minutes <= max(budget, used):
            kept.append(item)
            used += item.duration_minutes

    blocks: list[RecoveryBlock] = []
    if config.auto_recovery_enabled:
        minimum = 30 if config.weekly_condition >= 50 else 60
        minimum = min(120, max(15, round(minimum / 15) * 15))
        occupied = sorted((to_minutes(item.start_time), to_minutes(item.end_time)) for item in kept)
        for slot in slots:
            cursor, end = to_minutes(slot.start_time), to_minutes(slot.end_time)
            for busy_start, busy_end in occupied:
                if busy_end <= cursor or busy_start >= end:
                    continue
                if busy_start - cursor >= minimum:
                    break
                cursor = max(cursor, busy_end)
            if end - cursor >= minimum:
                reason = "LOW_CONDITION" if config.weekly_condition <= 25 else "LOW_TARGET_DENSITY" if config.target_schedule_density <= 50 else "HIGH_SCHEDULE_DENSITY"
                blocks.append(RecoveryBlock(day=slot.day, start_time=to_time(cursor), end_time=to_time(cursor + minimum), duration_minutes=minimum, reason=reason))
                break
    return kept, blocks


def calculate_recovery_score(
    classes: list[ScheduledClass], activities: list[Activity] | None = None,
    recommendations: list[Recommendation] | None = None,
    recovery_blocks: list[RecoveryBlock] | None = None,
) -> RecoveryAnalysis:
    activities, recommendations, recovery_blocks = activities or [], recommendations or [], recovery_blocks or []
    by_day = {day: [] for day in ("MON", "TUE", "WED", "THU", "FRI")}
    for item in classes:
        if item.day in by_day:
            by_day[item.day].append((to_minutes(item.start_time), to_minutes(item.end_time)))

    gaps, densities, longest, class_minutes = [], [], 0, 0
    for ranges in by_day.values():
        ranges.sort()
        if not ranges:
            continue
        daily_minutes = sum(end - start for start, end in ranges)
        class_minutes += daily_minutes
        if len(ranges) == 1:
            density = min(60, round(daily_minutes / 180 * 60)) if daily_minutes <= 180 else round(daily_minutes / 480 * 100)
        else:
            density = round(daily_minutes / max(1, ranges[-1][1] - ranges[0][0]) * 100)
        densities.append(density)
        chain_start, chain_end = ranges[0]
        for start, end in ranges[1:]:
            gap = start - chain_end
            if gap >= 15:
                gaps.append(gap)
                longest = max(longest, chain_end - chain_start)
                chain_start = start
            chain_end = max(chain_end, end)
        longest = max(longest, chain_end - chain_start)

    total_rest = (
        sum(gaps) + sum(item.duration_minutes for item in recovery_blocks)
        if classes else 5 * 14 * 60
    )
    rest_score = 40 if total_rest >= 120 else 30 if total_rest >= 60 else 15 if total_rest >= 30 else 0
    density = round(sum(densities) / len(densities)) if densities else 0
    density_score = 25 if density <= 60 else 20 if density <= 75 else 10 if density <= 85 else 0
    focus_score = 20 if longest <= 120 else 15 if longest <= 180 else 5 if longest <= 240 else 0

    activity_map = {item.activity_id: item for item in activities}
    recovery_items = [item for item in recommendations if item.activity_id in activity_map and activity_map[item.activity_id].category in RECOVERY_CATEGORIES]
    recovery_minutes = sum(item.duration_minutes for item in recovery_items) + sum(item.duration_minutes for item in recovery_blocks)
    kinds = {activity_map[item.activity_id].category for item in recovery_items}
    if recovery_blocks:
        kinds.add("RECOVERY_BLOCK")
    recovery_score = 15 if len(kinds) >= 2 and recovery_minutes >= 60 else 10 if kinds and recovery_minutes >= 30 else 5 if kinds else 0
    score = rest_score + density_score + focus_score + recovery_score
    grade = 1 if score >= 80 else 2 if score >= 60 else 3 if score >= 40 else 4
    messages = {1: "여유와 회복 시간이 충분한 시간표예요.", 2: "비교적 균형 잡힌 시간표예요.", 3: "일부 요일에 휴식이 부족할 수 있어요.", 4: "회복 시간을 조금 더 확보하는 것이 좋아요."}
    reasons, suggestions = [], []
    if rest_score < 30:
        reasons.append("수업 사이 30분 이상의 공강이 적어요.")
        suggestions.append("긴 수업 전후에 30분 이상의 여유를 확보해 보세요.")
    if focus_score < 20:
        reasons.append("쉬는 시간 없이 이어지는 수업 시간이 길어요.")
        suggestions.append("15분 이상의 공강이나 회복 시간을 연속 수업 사이에 두어 보세요.")
    if recovery_score == 0:
        reasons.append("등록된 회복 활동이 없어 이 항목은 아직 반영되지 않았어요.")
        suggestions.append("휴식·취미·친구 활동을 30분 이상 추가하면 회복 활동 점수에 반영돼요.")
    calculated_from = ["SEMESTER_TIMETABLE"]
    if activities:
        calculated_from.append("REGISTERED_ACTIVITIES")
    if recommendations:
        calculated_from.append("RECOMMENDED_ACTIVITIES")
    if recovery_blocks:
        calculated_from.append("RECOVERY_BLOCKS")
    return RecoveryAnalysis(
        score=score, grade=grade, status_message=messages[grade],
        score_details=RecoveryScoreDetails(rest_time_score=rest_score, schedule_density_score=density_score, continuous_focus_score=focus_score, recovery_activity_score=recovery_score),
        total_rest_minutes=total_rest, schedule_density_percent=density,
        longest_continuous_focus_minutes=longest, recovery_activity_minutes=recovery_minutes,
        calculated_from=calculated_from, reasons=reasons, suggestions=suggestions,
    )
