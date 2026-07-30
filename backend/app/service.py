from itertools import combinations
from .models import TimetableOption, TimetableRequest
from .repository import list_courses


def conflicts(left, right) -> bool:
    def interval(meeting):
        start = meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60
        duration = meeting.duration_minutes if meeting.duration_minutes is not None else (meeting.end - meeting.start) * 60
        return start, start + duration

    return any(a.day == b.day and interval(a)[0] < interval(b)[1] and interval(b)[0] < interval(a)[1] for a in left.meetings for b in right.meetings)


def meeting_interval(meeting):
    start = meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60
    duration = meeting.duration_minutes if meeting.duration_minutes is not None else (meeting.end - meeting.start) * 60
    return start, start + duration


def meets_preferences(courses, request: TimetableRequest) -> bool:
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


def generate_timetables(request: TimetableRequest) -> list[TimetableOption]:
    eligible = [course for course in list_courses() if set(course.prerequisites).issubset(request.completed_course_codes)]
    required = [course for course in eligible if course.code in request.required_course_codes]
    if len(required) != len(request.required_course_codes) or any(conflicts(a, b) for a, b in combinations(required, 2)):
        return []
    options = []
    for count in range(len(eligible) + 1):
        for selection in combinations([course for course in eligible if course not in required], count):
            courses = [*required, *selection]
            if sum(course.credits for course in courses) != request.target_credits or any(conflicts(a, b) for a, b in combinations(courses, 2)):
                continue
            if not meets_preferences(courses, request):
                continue
            used_days = {meeting.day for course in courses for meeting in course.meetings}
            morning_count = sum((meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60) < 12 * 60 for course in courses for meeting in course.meetings)
            score = 70 + (20 if request.preferred_free_day and request.preferred_free_day not in used_days else 0) + (10 if request.avoid_morning and morning_count == 0 else 0)
            reasons = ["Graduation requirement courses are included."]
            if request.preferred_free_day and request.preferred_free_day not in used_days:
                reasons.append("Your preferred free day is preserved.")
            if request.avoid_morning and morning_count == 0:
                reasons.append("No morning classes are included.")
            options.append(TimetableOption(title="Balanced schedule", score=score, reasons=reasons, courses=courses, total_credits=sum(course.credits for course in courses)))
    return sorted(options, key=lambda option: option.score, reverse=True)[:request.max_results]
