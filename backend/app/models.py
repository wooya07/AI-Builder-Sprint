from typing import Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

Day = Literal["\uc6d4", "\ud654", "\uc218", "\ubaa9", "\uae08"]


class Meeting(BaseModel):
    day: Day
    start: int = Field(ge=9, le=21)
    end: int = Field(ge=10, le=22)


class Course(BaseModel):
    code: str
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


ActivityDay = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
SlotType = Literal["BETWEEN_CLASSES", "AFTER_CLASSES", "BEFORE_CLASSES", "NO_CLASS_DAY"]
Category = Literal["STUDY", "EXERCISE", "HOBBY", "PART_TIME_JOB", "REST", "SOCIAL", "OTHER"]
RecommendationStatus = Literal["AVAILABLE", "CONFLICT", "INSUFFICIENT_TIME", "OUTSIDE_PREFERRED_TIME", "ALREADY_COMPLETED"]


class Location(BaseModel):
    building: str = ""
    room: str = ""


class ScheduledClass(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    course_id: str = Field(validation_alias=AliasChoices("course_id", "courseId"))
    class_group_id: str | None = Field(default=None, validation_alias=AliasChoices("class_group_id", "classGroupId"))
    course_name: str = Field(validation_alias=AliasChoices("course_name", "courseName"))
    day: ActivityDay
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$", validation_alias=AliasChoices("start_time", "startTime"))
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$", validation_alias=AliasChoices("end_time", "endTime"))
    grade: str | None = None
    course_type: str | None = Field(default=None, validation_alias=AliasChoices("course_type", "courseType"))
    section: str | None = None
    credits: int | None = None
    instructor: str | None = None
    department: str | None = None
    location: Location = Field(default_factory=Location)


class PreferredTimeRange(BaseModel):
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class Activity(BaseModel):
    activity_id: str
    category: Category
    activity_name: str = Field(min_length=1, max_length=80)
    priority: Literal["REQUIRED", "OPTIONAL"]
    schedule_type: Literal["FIXED_DAY", "FLEXIBLE_DAY"]
    duration_minutes: int = Field(ge=15, le=180, multiple_of=15)
    frequency_per_week: int | None = Field(default=None, ge=1, le=7)
    completed_count_this_week: int = Field(default=0, ge=0, le=7)
    preferred_days: list[ActivityDay] = Field(default_factory=list)
    preferred_time_range: PreferredTimeRange | None = None


class AvailableSlot(BaseModel):
    day: ActivityDay
    slot_type: SlotType
    start_time: str
    end_time: str
    duration_minutes: int


class Recommendation(BaseModel):
    activity_id: str
    activity_name: str
    category: Category
    slot_type: SlotType
    start_time: str
    end_time: str
    duration_minutes: int
    reason: str
    status: RecommendationStatus


class UnassignedActivity(BaseModel):
    activity_id: str
    status: RecommendationStatus
    reason: str


class ActivityRecommendationRequest(BaseModel):
    date: str
    day: ActivityDay
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    day_end_time: str = Field(default="22:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    classes: list[ScheduledClass]
    activities: list[Activity]


class ActivityRecommendationResponse(BaseModel):
    available_slots: list[AvailableSlot]
    recommendations: list[Recommendation]
    unassigned_activities: list[UnassignedActivity]
    source: Literal["SOLAR", "LOCAL"]


class SavedTimetableRequest(BaseModel):
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    classes: list[ScheduledClass]


class SavedTimetableResponse(BaseModel):
    code: str
    timezone: Literal["Asia/Seoul"]
    classes: list[ScheduledClass]
