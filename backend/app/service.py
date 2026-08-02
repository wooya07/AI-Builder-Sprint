from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import Course, TimetableOption, TimetableRequest
from .repository import list_courses


# A catalog may contain hundreds of lecture sections.  Keeping a small,
# high-quality beam for each credit total avoids the exponential combinations
# produced by enumerating every subset while still returning varied schedules.
_MAX_STATES_PER_CREDIT = 80


def conflicts(left: Course, right: Course) -> bool:
    return any(
        a.day == b.day
        and meeting_interval(a)[0] < meeting_interval(b)[1]
        and meeting_interval(b)[0] < meeting_interval(a)[1]
        for a in left.meetings
        for b in right.meetings
    )


def meeting_interval(meeting) -> tuple[int, int]:
    start = meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60
    duration = meeting.duration_minutes if meeting.duration_minutes is not None else (meeting.end - meeting.start) * 60
    return start, start + duration


def meets_preferences(courses: list[Course], request: TimetableRequest) -> bool:
    by_day = {}
    for course in courses:
        for meeting in course.meetings:
            by_day.setdefault(meeting.day, []).append(meeting_interval(meeting))
    for meetings in by_day.values():
        meetings.sort()
        if request.preferred_first_class_start is not None and meetings[0][0] < request.preferred_first_class_start * 60:
            return False
        if request.preferred_end_time is not None and meetings[-1][1] > request.preferred_end_time * 60:
            return False
        if request.max_daily_classes is not None and len(meetings) > request.max_daily_classes:
            return False
        if request.wants_lunch and any(start < 13 * 60 and end > 12 * 60 for start, end in meetings):
            return False
        if request.wants_dinner and any(start < 19 * 60 and end > 18 * 60 for start, end in meetings):
            return False
        consecutive = 1
        for previous, current in zip(meetings, meetings[1:]):
            gap = current[0] - previous[1]
            if request.minimum_travel_minutes is not None and gap < request.minimum_travel_minutes:
                return False
            consecutive = consecutive + 1 if gap == 0 else 1
            if request.max_consecutive_classes is not None and consecutive > request.max_consecutive_classes:
                return False
    return True


@dataclass(frozen=True)
class _ScheduleState:
    courses: tuple[Course, ...]
    credits: int


def generate_timetables(request: TimetableRequest) -> list[TimetableOption]:
    """Generate schedules from the catalog, optionally limited by curriculum matches."""
    eligible = [
        course
        for course in list_courses()
        if set(course.prerequisites).issubset(request.completed_course_codes)
        and course.grade in (None, "", "0", str(request.student_grade))
    ]
    requested_codes = _normalise_codes(request.candidate_course_codes)
    required_codes = _normalise_codes(request.required_course_codes)
    if request.candidate_course_codes is not None:
        requested_codes.update(required_codes)
        eligible = [course for course in eligible if course.code.casefold() in requested_codes]

    by_code: dict[str, list[Course]] = defaultdict(list)
    for course in eligible:
        by_code[course.code.casefold()].append(course)

    # A required course means "take this course", while its lecture section is
    # still chosen automatically to avoid conflicts with the other courses.
    if any(code not in by_code for code in required_codes):
        return []

    code_order = sorted(by_code, key=lambda code: (code not in required_codes, code))
    states = [_ScheduleState(courses=(), credits=0)]
    for code in code_order:
        next_states: list[_ScheduleState] = []
        must_take = code in required_codes
        for state in states:
            if not must_take:
                next_states.append(state)
            for section in by_code[code]:
                next_credits = state.credits + section.credits
                if next_credits > request.target_credits:
                    continue
                candidate_courses = [*state.courses, section]
                if any(conflicts(section, existing) for existing in state.courses):
                    continue
                # Every current constraint is monotonic: adding another class
                # cannot undo an already-invalid partial timetable.
                if not meets_preferences(candidate_courses, request):
                    continue
                next_states.append(_ScheduleState(tuple(candidate_courses), next_credits))
        states = _trim_states(next_states, request)
        if not states:
            return []

    # A hand-picked candidate list often cannot add up to the requested
    # credits exactly (for example, one selected 3-credit course with a
    # 12-credit target).  Return the fullest valid timetable within the target
    # instead of showing an empty result solely because exact arithmetic is
    # impossible.
    target_states = [state for state in states if state.credits == request.target_credits]
    if not target_states:
        highest_credit_total = max((state.credits for state in states if state.credits > 0), default=0)
        target_states = [state for state in states if state.credits == highest_credit_total]

    options = [_build_option(state.courses, request) for state in target_states]
    options.sort(key=lambda option: (-option.score, _schedule_key(option.courses)))
    options = _select_diverse_options(options, request.max_results)
    return [
        option.model_copy(update={"title": f"{request.student_grade}학년 {request.semester}학기 추천 시간표 {index}"})
        for index, option in enumerate(options, start=1)
    ]


def _trim_states(states: list[_ScheduleState], request: TimetableRequest) -> list[_ScheduleState]:
    """Deduplicate and retain the strongest schedule states at each credit total."""
    unique: dict[tuple[str, ...], _ScheduleState] = {}
    for state in states:
        key = tuple(sorted(course.class_group_id or f"{course.code}-{course.section or ''}" for course in state.courses))
        unique[key] = state

    by_credits: dict[int, list[_ScheduleState]] = defaultdict(list)
    for state in unique.values():
        by_credits[state.credits].append(state)

    trimmed: list[_ScheduleState] = []
    for credit_total, bucket in by_credits.items():
        bucket.sort(key=lambda state: (-_partial_score(state.courses, request), _schedule_key(state.courses)))
        trimmed.extend(bucket[:_MAX_STATES_PER_CREDIT])
    return trimmed


def _partial_score(courses: tuple[Course, ...], request: TimetableRequest) -> int:
    used_days = {meeting.day for course in courses for meeting in course.meetings}
    morning_count = sum(
        meeting_interval(meeting)[0] < 12 * 60
        for course in courses
        for meeting in course.meetings
    )
    score = 0
    if request.preferred_free_day and request.preferred_free_day not in used_days:
        score += 20
    if request.avoid_morning and morning_count == 0:
        score += 10
    # Fewer occupied days is a useful tie breaker before a full schedule has
    # reached the requested credits.
    return score - len(used_days)


def _build_option(courses: tuple[Course, ...], request: TimetableRequest) -> TimetableOption:
    used_days = {meeting.day for course in courses for meeting in course.meetings}
    morning_count = sum(
        meeting_interval(meeting)[0] < 12 * 60
        for course in courses
        for meeting in course.meetings
    )
    score = 70
    reasons = ["선택한 교육과정 과목과 강의 목록을 함께 반영했습니다."]
    if request.preferred_free_day and request.preferred_free_day not in used_days:
        score += 20
        reasons.append("희망 공강 요일을 지켰습니다.")
    if request.avoid_morning and morning_count == 0:
        score += 10
        reasons.append("오전 수업을 피했습니다.")
    return TimetableOption(
        title="균형 시간표",
        score=score,
        reasons=reasons,
        courses=list(courses),
        total_credits=sum(course.credits for course in courses),
    )


def _normalise_codes(codes: list[str] | None) -> set[str]:
    return {str(code).strip().casefold() for code in codes or [] if str(code).strip()}


def _schedule_key(courses: tuple[Course, ...] | list[Course]) -> tuple[str, ...]:
    return tuple(sorted(course.class_group_id or f"{course.code}-{course.section or ''}" for course in courses))


def _select_diverse_options(options: list[TimetableOption], max_results: int) -> list[TimetableOption]:
    """Keep the best result, then prefer alternatives with different sections.

    Scores can tie when several sections meet the same time preferences.  A
    simple score sort then returns near-duplicate schedules (often the same
    professor with only another course's section changed).  Select the
    remaining results by their minimum section difference from what is already
    shown so a student can compare meaningful professor/section choices.
    """
    if len(options) <= 1 or max_results <= 1:
        return options[:max_results]

    selected = [options[0]]
    remaining = options[1:]
    while remaining and len(selected) < max_results:
        best_index = max(
            range(len(remaining)),
            key=lambda index: (
                _minimum_section_difference(remaining[index], selected),
                remaining[index].score,
                -index,
            ),
        )
        selected.append(remaining.pop(best_index))
    return selected


def _minimum_section_difference(candidate: TimetableOption, selected: list[TimetableOption]) -> int:
    return min(_section_difference(candidate.courses, option.courses) for option in selected)


def _section_difference(left: list[Course], right: list[Course]) -> int:
    left_sections = {course.code.casefold(): course.class_group_id or f"{course.code}-{course.section or ''}" for course in left}
    right_sections = {course.code.casefold(): course.class_group_id or f"{course.code}-{course.section or ''}" for course in right}
    codes = set(left_sections) | set(right_sections)
    return sum(left_sections.get(code) != right_sections.get(code) for code in codes)
