from itertools import combinations
from .models import TimetableOption, TimetableRequest
from .repository import list_courses


def conflicts(left, right) -> bool:
    def interval(meeting):
        start = meeting.start_minutes if meeting.start_minutes is not None else meeting.start * 60
        duration = meeting.duration_minutes if meeting.duration_minutes is not None else (meeting.end - meeting.start) * 60
        return start, start + duration

    return any(a.day == b.day and interval(a)[0] < interval(b)[1] and interval(b)[0] < interval(a)[1] for a in left.meetings for b in right.meetings)


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
