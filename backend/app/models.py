from typing import Literal
from pydantic import BaseModel, Field

Day = Literal["\uc6d4", "\ud654", "\uc218", "\ubaa9", "\uae08"]


class Meeting(BaseModel):
    day: Day
    start: int = Field(ge=0, le=23)
    end: int = Field(ge=1, le=24)
    start_minutes: int | None = Field(default=None, ge=0, le=1439)
    duration_minutes: int | None = Field(default=None, ge=1)
    building: str | None = None
    room: str | None = None


class Course(BaseModel):
    code: str
    class_group_id: str | None = None
    name: str
    credits: int = Field(ge=1, le=6)
    category: str
    instructor: str
    meetings: list[Meeting]
    prerequisites: list[str] = Field(default_factory=list)
    grade: str | None = None
    section: str | None = None
    department: str | None = None
    schedule_text: str | None = None


class TimetableRequest(BaseModel):
    target_credits: int = Field(default=12, ge=1, le=24)
    required_course_codes: list[str] = Field(default_factory=list)
    completed_course_codes: list[str] = Field(default_factory=list)
    preferred_free_day: Day | None = None
    avoid_morning: bool = False
    max_results: int = Field(default=3, ge=1, le=10)


class TimetableOption(BaseModel):
    title: str
    score: int
    reasons: list[str]
    courses: list[Course]
    total_credits: int


class TimetableResponse(BaseModel):
    timetables: list[TimetableOption]


class CatalogImportResult(BaseModel):
    imported_count: int
    skipped_rows: list[int] = Field(default_factory=list)
    message: str
