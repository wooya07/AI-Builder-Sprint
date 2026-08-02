from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .catalog_import import import_catalog
from .document_parser import UpstageDocumentError, parse_curriculum_document
from .activity_service import (
    calculate_available_slots,
    make_local_recommendations,
    validate_recommendations,
)
from .models import (
    ActivityRecommendationRequest,
    ActivityRecommendationResponse,
    CatalogImportResult,
    Course,
    RecoveryAnalysis,
    RecoveryAnalysisRequest,
    SavedTimetable,
    TimetableRequest,
    TimetableResponse,
)
from .repository import list_courses, match_curriculum_courses
from .service import generate_timetables
from .solar import request_solar_recommendations
from .recovery import adjust_recommendations, calculate_recovery_score
from .saved_timetable_store import load_timetable, save_timetable

app = FastAPI(title="Personal Semester Planner API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPPORTED_CURRICULUM_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".pptx", ".xlsx", ".hwp", ".hwpx"}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/courses", response_model=list[Course])
def courses(query: str = "", limit: int = 20, include_sections: bool = False) -> list[Course]:
    catalog = list_courses()
    search = query.strip().casefold()
    if not search:
        return catalog

    matches = [
        course for course in catalog
        if search in course.code.casefold() or search in course.name.casefold()
    ]
    if include_sections:
        return matches[:max(1, min(limit, 100))]

    unique_by_code: dict[str, Course] = {}
    for course in matches:
        unique_by_code.setdefault(course.code, course)
    return list(unique_by_code.values())[:max(1, min(limit, 100))]


@app.get("/api/v1/courses/credits")
def course_credits(class_group_ids: str = "") -> dict[str, dict[str, int]]:
    requested_ids = {value.strip() for value in class_group_ids.split(",") if value.strip()}
    if not requested_ids:
        return {"credits": {}}
    return {
        "credits": {
            course.class_group_id: course.credits
            for course in list_courses()
            if course.class_group_id and course.class_group_id in requested_ids
        }
    }


@app.post("/api/v1/admin/course-catalog/import", response_model=CatalogImportResult)
async def import_course_catalog(file: UploadFile = File(...)) -> CatalogImportResult:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size must not exceed 10MB.")
    try:
        imported_count, duplicate_count, skipped_rows = import_catalog(content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return CatalogImportResult(
        imported_count=imported_count,
        duplicate_count=duplicate_count,
        skipped_rows=skipped_rows,
        message="새 강좌만 수강편람에 추가했습니다.",
    )


@app.post("/api/v1/curriculum/parse")
async def parse_curriculum(
    file: UploadFile = File(...),
) -> dict:
    """Parse a curriculum and expose only the courses present in the catalog.

    The Upstage key is loaded from ``backend/.env`` as ``UPSTAGE_API_KEY`` and
    is never returned by this endpoint.
    """
    filename = file.filename or ""
    if not filename or Path(filename).suffix.lower() not in SUPPORTED_CURRICULUM_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_CURRICULUM_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {supported}")

    content = await file.read()
    try:
        parsed = parse_curriculum_document(
            filename=filename,
            content=content,
            content_type=file.content_type,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except UpstageDocumentError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    courses, available_codes = match_curriculum_courses(parsed["courses"])
    return {
        **parsed,
        "courses": courses,
        "available_course_codes": available_codes,
        "matched_course_count": sum(bool(course["catalog_course_codes"]) for course in courses),
    }


@app.post("/api/v1/timetables/generate", response_model=TimetableResponse)
def generate(request: TimetableRequest) -> TimetableResponse:
    return TimetableResponse(timetables=generate_timetables(request))


@app.post("/api/v1/saved-timetables")
def export_timetable(timetable: SavedTimetable) -> dict[str, str]:
    return {"code": save_timetable(timetable)}


@app.get("/api/v1/saved-timetables/{code}", response_model=SavedTimetable)
def import_timetable(code: str) -> SavedTimetable:
    timetable = load_timetable(code)
    if timetable is None:
        raise HTTPException(status_code=404, detail="저장된 시간표를 찾을 수 없습니다.")
    return timetable


@app.post("/api/v1/recovery/analyze", response_model=RecoveryAnalysis)
def analyze_recovery(request: RecoveryAnalysisRequest) -> RecoveryAnalysis:
    return calculate_recovery_score(request.classes, request.activities, request.recommendations, request.recovery_blocks)


@app.post("/api/v1/activities/recommend", response_model=ActivityRecommendationResponse)
async def recommend_activities(request: ActivityRecommendationRequest) -> ActivityRecommendationResponse:
    try:
        slots = calculate_available_slots(request.classes, request.day, request.day_end_time)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    classes = [
        {
            "courseId": item.course_id,
            "classGroupId": item.class_group_id or item.course_id,
            "courseName": item.course_name,
            "day": item.day,
            "startTime": item.start_time,
            "endTime": item.end_time,
            "grade": item.grade,
            "courseType": item.course_type,
            "section": item.section,
            "credits": item.credits,
            "instructor": item.instructor,
            "department": item.department,
            "location": {
                "building": item.location.building,
                "room": item.location.room,
            },
        }
        for item in request.classes if item.day == request.day
    ]
    source = "LOCAL"
    recommendations = None
    try:
        recommendations = await request_solar_recommendations(
            request.date, request.day, classes, slots, request.activities
        )
    except Exception:
        recommendations = None
    if recommendations is None:
        recommendations, unassigned = make_local_recommendations(request.activities, slots, request.day)
    else:
        recommendations = validate_recommendations(recommendations, request.activities, slots, request.day)
        fallback_recommendations, unassigned = make_local_recommendations(
            [item for item in request.activities if item.activity_id not in {rec.activity_id for rec in recommendations}],
            slots, request.day,
        )
        recommendations = validate_recommendations(
            [*recommendations, *fallback_recommendations], request.activities, slots, request.day
        )
        source = "SOLAR"
    recommendations, recovery_blocks = adjust_recommendations(
        recommendations, request.activities, slots, request.inefficiency_mode
    )
    return ActivityRecommendationResponse(
        available_slots=slots, recommendations=recommendations,
        unassigned_activities=unassigned, source=source,
        recovery_blocks=recovery_blocks,
    )
