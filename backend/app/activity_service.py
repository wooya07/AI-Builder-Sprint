from .models import (
    Activity,
    ActivityDay,
    AvailableSlot,
    Recommendation,
    ScheduledClass,
    UnassignedActivity,
)


def to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def to_time(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def sort_and_validate_classes(classes: list[ScheduledClass]) -> list[ScheduledClass]:
    ordered = sorted(classes, key=lambda item: to_minutes(item.start_time))
    seen: set[tuple[str, str, str, str]] = set()
    previous: ScheduledClass | None = None
    for item in ordered:
        if to_minutes(item.end_time) <= to_minutes(item.start_time):
            raise ValueError(f"{item.course_name}: 종료 시간은 시작 시간보다 늦어야 합니다.")
        class_identity = item.class_group_id or item.course_id
        key = (class_identity, item.day, item.start_time, item.end_time)
        if key in seen:
            raise ValueError(f"{item.course_name}: 같은 수업이 중복 저장되어 있습니다.")
        seen.add(key)
        if previous and to_minutes(previous.end_time) > to_minutes(item.start_time):
            raise ValueError(f"{previous.course_name} 수업과 {item.course_name} 수업이 겹칩니다.")
        previous = item
    return ordered


def calculate_available_slots(
    classes: list[ScheduledClass], day: ActivityDay, day_end_time: str = "22:00"
) -> list[AvailableSlot]:
    ordered = sort_and_validate_classes([item for item in classes if item.day == day])
    if not ordered:
        start, end = to_minutes("08:00"), to_minutes(day_end_time)
        if end - start < 15:
            return []
        return [AvailableSlot(
            day=day, slot_type="NO_CLASS_DAY", start_time=to_time(start),
            end_time=to_time(end), duration_minutes=end - start,
        )]
    slots: list[AvailableSlot] = []
    for previous, following in zip(ordered, ordered[1:]):
        start, end = to_minutes(previous.end_time), to_minutes(following.start_time)
        if end - start >= 15:
            slots.append(AvailableSlot(
                day=day, slot_type="BETWEEN_CLASSES", start_time=to_time(start),
                end_time=to_time(end), duration_minutes=end - start,
            ))
    start, end = to_minutes(ordered[-1].end_time), to_minutes(day_end_time)
    if end - start >= 15:
        slots.append(AvailableSlot(
            day=day, slot_type="AFTER_CLASSES", start_time=to_time(start),
            end_time=to_time(end), duration_minutes=end - start,
        ))
    return slots


def _priority(activity: Activity) -> tuple[int, int]:
    return (
        1 if activity.schedule_type == "FIXED_DAY" else 0,
        1 if activity.priority == "REQUIRED" else 0,
    )


def make_local_recommendations(
    activities: list[Activity], slots: list[AvailableSlot], day: ActivityDay
) -> tuple[list[Recommendation], list[UnassignedActivity]]:
    recommendations: list[Recommendation] = []
    unassigned: list[UnassignedActivity] = []
    occupied: list[tuple[int, int]] = []
    for activity in sorted(activities, key=_priority, reverse=True):
        if (
            activity.frequency_per_week is not None
            and activity.completed_count_this_week >= activity.frequency_per_week
        ):
            unassigned.append(UnassignedActivity(
                activity_id=activity.activity_id, status="ALREADY_COMPLETED",
                reason="이번 주 필요한 횟수를 이미 채웠습니다.",
            ))
            continue
        if activity.schedule_type == "FIXED_DAY" and day not in activity.preferred_days:
            continue
        placed = False
        for slot in slots:
            start, slot_end = to_minutes(slot.start_time), to_minutes(slot.end_time)
            if activity.preferred_time_range:
                start = max(start, to_minutes(activity.preferred_time_range.start_time))
            start = ((start + 14) // 15) * 15
            while start + activity.duration_minutes <= slot_end:
                end = start + activity.duration_minutes
                conflicts = [
                    (busy_start, busy_end) for busy_start, busy_end in occupied
                    if start < busy_end and end > busy_start
                ]
                if conflicts:
                    start = ((max(busy_end for _, busy_end in conflicts) + 14) // 15) * 15
                    continue
                outside = bool(
                    activity.preferred_time_range
                    and end > to_minutes(activity.preferred_time_range.end_time)
                )
                recommendations.append(Recommendation(
                    activity_id=activity.activity_id, activity_name=activity.activity_name,
                    category=activity.category, slot_type=slot.slot_type,
                    start_time=to_time(start), end_time=to_time(end),
                    duration_minutes=activity.duration_minutes,
                    reason=(
                        f"{'필수 활동이라 먼저 배치했고' if activity.priority == 'REQUIRED' else '빈 시간을 알차게 쓸 수 있고'}, "
                        f"{'하교 후' if slot.slot_type == 'AFTER_CLASSES' else '수업이 없는 시간에' if slot.slot_type == 'NO_CLASS_DAY' else '다음 수업 전'} 여유 있게 할 수 있습니다."
                    ),
                    status="OUTSIDE_PREFERRED_TIME" if outside else "AVAILABLE",
                ))
                occupied.append((start, end))
                placed = True
                break
            if placed:
                break
        if not placed:
            unassigned.append(UnassignedActivity(
                activity_id=activity.activity_id, status="INSUFFICIENT_TIME",
                reason="필요한 시간을 담을 수 있는 빈 시간이 없습니다.",
            ))
    return recommendations, unassigned


def validate_recommendations(
    items: list[Recommendation], activities: list[Activity],
    slots: list[AvailableSlot], day: ActivityDay,
) -> list[Recommendation]:
    activity_map = {item.activity_id: item for item in activities}
    accepted: list[Recommendation] = []
    for item in items:
        activity = activity_map.get(item.activity_id)
        start, end = to_minutes(item.start_time), to_minutes(item.end_time)
        inside_slot = any(
            item.slot_type == slot.slot_type
            and start >= to_minutes(slot.start_time)
            and end <= to_minutes(slot.end_time)
            for slot in slots
        )
        conflict = any(
            start < to_minutes(other.end_time) and end > to_minutes(other.start_time)
            for other in accepted
        )
        if (
            activity and start < end and end - start == activity.duration_minutes
            and inside_slot and not conflict
            and (activity.schedule_type == "FLEXIBLE_DAY" or day in activity.preferred_days)
            and (
                activity.frequency_per_week is None
                or activity.completed_count_this_week < activity.frequency_per_week
            )
        ):
            accepted.append(item)
    return accepted
