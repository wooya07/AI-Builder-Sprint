import re
from .database import get_connection
from .models import Course, Meeting

COURSES: list[Course] = [
    Course(code="CS201", name="Data Structures", credits=3, category="Major Required", instructor="Kim", meetings=[{"day": "\uc6d4", "start": 13, "end": 15}, {"day": "\uc218", "start": 13, "end": 15}]),
    Course(code="CS203", name="Web Programming", credits=3, category="Major Elective", instructor="Park", meetings=[{"day": "\ud654", "start": 13, "end": 15}, {"day": "\ubaa9", "start": 13, "end": 15}]),
    Course(code="GE101", name="Writing", credits=3, category="General Education", instructor="Choi", meetings=[{"day": "\uc6d4", "start": 10, "end": 12}, {"day": "\uc218", "start": 10, "end": 12}]),
    Course(code="GE102", name="English Conversation", credits=3, category="General Education", instructor="Jung", meetings=[{"day": "\ud654", "start": 15, "end": 17}, {"day": "\ubaa9", "start": 15, "end": 17}]),
]


def parse_meetings(schedule_text: str) -> list[Meeting]:
    pattern = r"([\uc6d4\ud654\uc218\ubaa9\uae08]).*?(\d{1,2})(?::\d{2})?\s*[-~]\s*(\d{1,2})(?::\d{2})?"
    meetings = []
    for day, start, end in re.findall(pattern, schedule_text):
        start_hour, end_hour = int(start), int(end)
        if 9 <= start_hour < end_hour <= 22:
            meetings.append(Meeting(day=day, start=start_hour, end=end_hour))
    return meetings


def list_courses() -> list[Course]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM courses ORDER BY course_code, section").fetchall()
    if not rows:
        return COURSES
    return [
        Course(
            code=row["course_code"], name=row["subject_name"], credits=row["credits"],
            category=row["subject_type"] or "Unclassified", instructor=row["instructor"],
            meetings=parse_meetings(row["schedule_text"]), grade=row["grade"],
            section=row["section"], department=row["department"], schedule_text=row["schedule_text"],
        )
        for row in rows
    ]


def replace_courses(records: list[dict[str, str | int]]) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM courses")
        connection.executemany(
            """INSERT INTO courses (grade, subject_name, subject_type, course_code, section, credits, instructor, schedule_text, department)
               VALUES (:grade, :subject_name, :subject_type, :course_code, :section, :credits, :instructor, :schedule_text, :department)""",
            records,
        )
