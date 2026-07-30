from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .catalog_import import import_catalog
from .database import initialize_database
from .activity_service import calculate_available_slots, make_local_recommendations, validate_recommendations
from .models import ActivityRecommendationRequest, ActivityRecommendationResponse, CatalogImportResult, Course, TimetableRequest, TimetableResponse
from .repository import list_courses
from .service import generate_timetables
from .solar import request_solar_recommendations

app = FastAPI(title="Personal Semester Planner API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/courses", response_model=list[Course])
def courses() -> list[Course]:
    return list_courses()


@app.post("/api/v1/admin/course-catalog/import", response_model=CatalogImportResult)
async def import_course_catalog(file: UploadFile = File(...)) -> CatalogImportResult:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size must not exceed 10MB.")
    try:
        imported_count, skipped_rows = import_catalog(content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return CatalogImportResult(imported_count=imported_count, skipped_rows=skipped_rows, message="Course catalog saved.")


@app.post("/api/v1/timetables/generate", response_model=TimetableResponse)
def generate(request: TimetableRequest) -> TimetableResponse:
    return TimetableResponse(timetables=generate_timetables(request))


@app.post("/api/v1/activities/recommend", response_model=ActivityRecommendationResponse)
async def recommend_activities(request: ActivityRecommendationRequest) -> ActivityRecommendationResponse:
    try:
        slots = calculate_available_slots(request.classes, request.day, request.day_end_time)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    classes = [
        {
            "courseName": item.course_name, "startTime": item.start_time,
            "endTime": item.end_time, "building": item.location.building,
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
        _, unassigned = make_local_recommendations(
            [item for item in request.activities if item.activity_id not in {rec.activity_id for rec in recommendations}],
            slots, request.day,
        )
        source = "SOLAR"
    return ActivityRecommendationResponse(
        available_slots=slots, recommendations=recommendations,
        unassigned_activities=unassigned, source=source,
    )
