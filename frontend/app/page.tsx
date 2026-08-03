"use client";

import { ChangeEvent, DragEvent, FormEvent, KeyboardEvent, MouseEvent, useEffect, useRef, useState } from "react";

type Day = "MON" | "TUE" | "WED" | "THU" | "FRI";
type View = "semester" | "week" | "all";
type Course = {
  course_id: string; class_group_id: string; course_name: string; day: Day; start_time: string; end_time: string;
  grade?: string; course_type?: string; section?: string; credits?: number; instructor?: string; department?: string;
  location: { building: string; room: string };
};
type Activity = {
  activity_id: string; category: string; activity_name: string; priority: "REQUIRED" | "OPTIONAL";
  schedule_type: "FIXED_DAY" | "FLEXIBLE_DAY"; duration_minutes: number; frequency_per_week: number | null;
  completed_count_this_week: number; preferred_days: Day[];
  preferred_time_range: { start_time: string; end_time: string } | null;
};
type Slot = { day: Day; slot_type: "BETWEEN_CLASSES" | "AFTER_CLASSES"; start_time: string; end_time: string; duration_minutes: number };
type Recommendation = { day: Day; activity_id: string; activity_name: string; category: string; slot_type: string; start_time: string; end_time: string; duration_minutes: number; reason: string; status: string };
type RecoveryBlock = { type: "RECOVERY_BLOCK"; day: Day; start_time: string; end_time: string; duration_minutes: number; reason: string };
type RecoveryAnalysis = { score: number; grade: number; status_message: string; score_details: { rest_time_score: number; schedule_density_score: number; continuous_focus_score: number; recovery_activity_score: number }; total_rest_minutes: number; schedule_density_percent: number; longest_continuous_focus_minutes: number; recovery_activity_minutes: number; calculated_from: string[]; reasons: string[]; suggestions: string[] };
type CatalogMeeting = { day: string; start: number; end: number; start_minutes?: number | null; duration_minutes?: number | null; building?: string | null; room?: string | null };
type CatalogCourse = { code: string; class_group_id?: string; name: string; credits: number; category: string; department?: string | null; instructor: string; meetings: CatalogMeeting[] };
type PendingCatalogAddition = { course: CatalogCourse; conflicting_group_ids: string[]; conflicting_course_names: string[] };
type Timetable = { title: string; score: number; reasons: string[]; courses: CatalogCourse[]; total_credits: number };
type CurriculumCourse = { code: string | null; document_code?: string | null; name: string; credits: number | null; category: string | null; grade?: string | null; semester?: string | null; instructor?: string | null; department?: string | null; catalog_course_codes: string[]; match_type: "code" | "name" | "prefix_name" | null; match_reason: "code" | "name" | "prefix_name" | "catalog_code_not_found" | "catalog_name_not_found" };
type CurriculumParseResult = { source_filename: string; course_count: number; raw_table_count: number; matched_course_count: number; available_course_codes: string[]; courses: CurriculumCourse[] };

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const days: { value: Day; label: string }[] = [
  { value: "MON", label: "월" }, { value: "TUE", label: "화" }, { value: "WED", label: "수" },
  { value: "THU", label: "목" }, { value: "FRI", label: "금" },
];
const koreanDay: Record<string, Day> = { 월: "MON", 화: "TUE", 수: "WED", 목: "THU", 금: "FRI" };
const categories = [
  ["STUDY", "개인 공부", "✎"], ["EXERCISE", "운동", "●"], ["HOBBY", "취미 생활", "✦"],
  ["PART_TIME_JOB", "알바", "₩"], ["REST", "휴식", "☁"], ["SOCIAL", "친구", "☺"], ["OTHER", "기타", "+"],
];
const initialActivityDraft = { category: "", name: "", priority: "REQUIRED" as "REQUIRED" | "OPTIONAL", duration: 60, useWeeklyPlan: false, frequency: 2, fixed: false, preferredDays: ["MON"] as Day[], preferred: false, preferredStart: "17:00", preferredEnd: "21:00" };
const categoryMap = Object.fromEntries(categories.map(([value, label]) => [value, label]));
const iconMap = Object.fromEntries(categories.map(([value, , icon]) => [value, icon]));

const timeToRow = (time: string) => {
  const [hour, minute] = time.split(":").map(Number);
  return 2 + (hour - 8) * 2 + Math.floor(minute / 30);
};
const timeToMinutes = (time: string) => {
  const [hour, minute] = time.split(":").map(Number);
  return hour * 60 + minute;
};
const timetableBlockPosition = (dayIndex: number, startTime: string, endTime: string) => ({
  gridColumn: dayIndex + 2,
  gridRow: timeToRow(startTime),
  height: `${Math.max(1, timeToMinutes(endTime) - timeToMinutes(startTime))}px`,
  marginTop: `${timeToMinutes(startTime) % 30}px`,
});
const durationLabel = (minutes: number) => {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  return `${hours ? `${hours}시간` : ""}${hours && rest ? " " : ""}${rest ? `${rest}분` : ""}` || "0분";
};
const minutesToTime = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
const catalogMeetingTimes = (meeting: CatalogMeeting) => {
  const start = meeting.start_minutes ?? meeting.start * 60;
  const end = meeting.duration_minutes ? start + meeting.duration_minutes : meeting.end * 60;
  return { start: minutesToTime(start), end: minutesToTime(end) };
};
const readableError = (detail: unknown, fallback: string) => {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item?.msg === "string" ? item.msg : JSON.stringify(item)).join(" · ");
  if (detail && typeof detail === "object" && "msg" in detail && typeof detail.msg === "string") return detail.msg;
  return fallback;
};
const koreanCourseName = (name: string) => {
  const stack: number[] = [];
  for (let index = 0; index < name.length; index += 1) {
    if (name[index] === "(") stack.push(index);
    if (name[index] === ")" && stack.length) {
      const start = stack.pop()!;
      if (/[a-z]/.test(name.slice(start + 1, index))) {
        return `${name.slice(0, start)}${name.slice(index + 1)}`.trim();
      }
    }
  }
  return name;
};

export default function Home() {
  const logoClickCount = useRef(0);
  const logoClickTimer = useRef<number | null>(null);
  const [view, setView] = useState<View>("semester");
  const [day, setDay] = useState<Day>("MON");
  const [courses, setCourses] = useState<Course[]>([]);
  const [catalogCredits, setCatalogCredits] = useState<Record<string, number>>({});
  const [activities, setActivities] = useState<Activity[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [draggingRecommendation, setDraggingRecommendation] = useState<Recommendation | null>(null);
  const [recommendationDragPreview, setRecommendationDragPreview] = useState<Recommendation | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<"course" | "activity" | null>(null);
  const [step, setStep] = useState(1);
  const [courseDraft, setCourseDraft] = useState({ name: "", start: "09:00", end: "10:30", building: "", room: "" });
  const [activityDraft, setActivityDraft] = useState({ ...initialActivityDraft });
  const [editingActivityId, setEditingActivityId] = useState<string | null>(null);
  const [freeDay, setFreeDay] = useState("");
  const [avoidMorning, setAvoidMorning] = useState(true);
  const [firstClassStart, setFirstClassStart] = useState("");
  const [wantsLunch, setWantsLunch] = useState(false);
  const [wantsDinner, setWantsDinner] = useState(false);
  const [travelMinutes, setTravelMinutes] = useState("");
  const [maxDailyClasses, setMaxDailyClasses] = useState("");
  const [endTime, setEndTime] = useState("");
  const [studentGrade, setStudentGrade] = useState("1");
  const [semester, setSemester] = useState("1");
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [timetableMessage, setTimetableMessage] = useState("");
  const [timetableLoading, setTimetableLoading] = useState(false);
  const [curriculumFile, setCurriculumFile] = useState<File | null>(null);
  const [curriculumLoading, setCurriculumLoading] = useState(false);
  const [curriculumResult, setCurriculumResult] = useState<CurriculumParseResult | null>(null);
  const [curriculumMessage, setCurriculumMessage] = useState("");
  const [selectedCurriculumCodes, setSelectedCurriculumCodes] = useState<string[]>([]);
  const [courseSearch, setCourseSearch] = useState("");
  const [courseSearchResults, setCourseSearchResults] = useState<CatalogCourse[]>([]);
  const [courseSearchLoading, setCourseSearchLoading] = useState(false);
  const [manualCourses, setManualCourses] = useState<CatalogCourse[]>([]);
  const [plannerCourseSearch, setPlannerCourseSearch] = useState("");
  const [plannerCourseResults, setPlannerCourseResults] = useState<CatalogCourse[]>([]);
  const [plannerCourseLoading, setPlannerCourseLoading] = useState(false);
  const [plannerCoursePickerOpen, setPlannerCoursePickerOpen] = useState(false);
  const [plannerCoursePreview, setPlannerCoursePreview] = useState<CatalogCourse | null>(null);
  const [pendingCatalogAddition, setPendingCatalogAddition] = useState<PendingCatalogAddition | null>(null);
  const [shareCode, setShareCode] = useState("");
  const [importCode, setImportCode] = useState("");
  const [shareMessage, setShareMessage] = useState("");
  const [inefficiencyEnabled, setInefficiencyEnabled] = useState(false);
  const [targetDensity, setTargetDensity] = useState(75);
  const [weeklyCondition, setWeeklyCondition] = useState(50);
  const currentCourseGroupIds = [...new Set(courses.map((course) => course.class_group_id))].sort().join(",");
  const [recoveryBlocks, setRecoveryBlocks] = useState<RecoveryBlock[]>([]);
  const [recoveryAnalysis, setRecoveryAnalysis] = useState<RecoveryAnalysis | null>(null);
  const [showRecoveryDetails, setShowRecoveryDetails] = useState(false);
  const curriculumCandidateGroups = (() => {
    const groups = new Map<string, CurriculumCourse[]>();
    for (const course of curriculumResult?.courses ?? []) {
      if (!course.catalog_course_codes.length) continue;
      const label = course.grade && course.semester ? `${course.grade}학년 ${course.semester}학기` : "학년·학기 정보 없음";
      groups.set(label, [...(groups.get(label) ?? []), course]);
    }
    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right, "ko"))
      .map(([label, courses]) => ({ label, courses }));
  })();
  const courseSearchPanel = <div className="course-search"><label>과목 코드 또는 과목명으로 직접 추가<input value={courseSearch} onChange={(event) => setCourseSearch(event.target.value)} placeholder="예: CB1501012 또는 확률통계"/></label>{courseSearch.trim().length >= 2 && <div className="course-search-results">{courseSearchLoading ? <span>검색 중...</span> : courseSearchResults.length ? courseSearchResults.map((course) => { const selected = selectedCurriculumCodes.includes(course.code); return <div key={course.code}><span><b>{course.name}</b><small>{course.code} · {course.credits}학점 · {course.category}{course.department ? ` · ${course.department}` : ""}</small></span><button type="button" disabled={selected} onClick={() => { setSelectedCurriculumCodes((current) => [...current, course.code]); setManualCourses((current) => current.some((item) => item.code === course.code) ? current : [...current, course]); }}>{selected ? "추가됨" : "추가"}</button></div>; }) : <span>일치하는 개설 과목이 없습니다.</span>}</div>}{manualCourses.length > 0 && <details className="manual-course-list" open><summary>검색으로 추가한 과목 ({manualCourses.length})</summary>{manualCourses.map((course) => <div key={course.code}><span><b>{course.name}</b><small>{course.code} · {course.credits}학점 · {course.category}{course.department ? ` · ${course.department}` : ""}</small></span><button type="button" onClick={() => { setManualCourses((current) => current.filter((item) => item.code !== course.code)); setSelectedCurriculumCodes((current) => current.filter((code) => code !== course.code)); }}>제거</button></div>)}</details>}</div>;

  useEffect(() => {
    setRecoveryAnalysis(null);
  }, [courses, activities, recommendations, recoveryBlocks]);

  useEffect(() => {
    if (!currentCourseGroupIds) {
      setCatalogCredits({});
      return;
    }
    const controller = new AbortController();
    fetch(`${apiBase}/api/v1/courses/credits?class_group_ids=${encodeURIComponent(currentCourseGroupIds)}`, { signal: controller.signal })
      .then(async (response) => response.ok ? await response.json() as { credits: Record<string, number> } : { credits: {} })
      .then((data) => { if (!controller.signal.aborted) setCatalogCredits(data.credits); })
      .catch(() => { if (!controller.signal.aborted) setCatalogCredits({}); });
    return () => controller.abort();
  }, [currentCourseGroupIds]);

  useEffect(() => {
    const query = courseSearch.trim();
    if (query.length < 2) {
      setCourseSearchResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setCourseSearchLoading(true);
      try {
        const response = await fetch(`${apiBase}/api/v1/courses?query=${encodeURIComponent(query)}&limit=12`, { signal: controller.signal });
        if (!response.ok) throw new Error("강의 검색에 실패했습니다.");
        setCourseSearchResults(await response.json() as CatalogCourse[]);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setCourseSearchResults([]);
      } finally {
        if (!controller.signal.aborted) setCourseSearchLoading(false);
      }
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [courseSearch]);

  useEffect(() => {
    const query = plannerCourseSearch.trim();
    if (!plannerCoursePickerOpen || query.length < 2) {
      setPlannerCourseResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setPlannerCourseLoading(true);
      try {
        const response = await fetch(`${apiBase}/api/v1/courses?query=${encodeURIComponent(query)}&limit=100&include_sections=true`, { signal: controller.signal });
        if (!response.ok) throw new Error("강의 검색에 실패했습니다.");
        setPlannerCourseResults(await response.json() as CatalogCourse[]);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) setPlannerCourseResults([]);
      } finally {
        if (!controller.signal.aborted) setPlannerCourseLoading(false);
      }
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [plannerCoursePickerOpen, plannerCourseSearch]);

  async function calculateRecovery() {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/recovery/analyze`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ classes: courses, activities, recommendations, recovery_blocks: recoveryBlocks }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(readableError(data.detail, "회복 점수를 계산하지 못했습니다."));
      setRecoveryAnalysis(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다.");
    } finally { setBusy(false); }
  }

  async function recommend() {
    setBusy(true); setMessage("");
    try {
      const results = await Promise.all(days.map(async ({ value }) => {
        const response = await fetch(`${apiBase}/api/v1/activities/recommend`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), day: value, timezone: "Asia/Seoul", day_end_time: "22:00", classes: courses, activities, inefficiencyMode: { enabled: inefficiencyEnabled, targetScheduleDensity: targetDensity, weeklyCondition, autoRecoveryEnabled: false } }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(readableError(data.detail, "추천을 만들지 못했습니다."));
        return {
          slots: (data.available_slots as Slot[]),
          recommendations: (data.recommendations as Omit<Recommendation, "day">[]).map((item) => ({ ...item, day: value })),
          recoveryBlocks: data.recovery_blocks as RecoveryBlock[],
        };
      }));
      const limits = new Map(activities.map((activity) => [
        activity.activity_id,
        activity.schedule_type === "FIXED_DAY" ? Math.max(1, activity.preferred_days.length) : (activity.frequency_per_week ?? 1),
      ]));
      const counts = new Map<string, number>();
      const combined = results.flatMap((result) => result.recommendations).filter((item) => {
        const used = counts.get(item.activity_id) ?? 0;
        if (used >= (limits.get(item.activity_id) ?? 1)) return false;
        counts.set(item.activity_id, used + 1);
        return true;
      });
      setRecommendations(combined);
      setRecoveryBlocks([]);
      setMessage(combined.length ? `${combined.length}개의 추천을 월–금 시간표에 표시했습니다.` : "조건에 맞는 활동을 찾지 못했습니다.");
      setView("week");
    } catch (error) { setMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
    finally { setBusy(false); }
  }

  function saveCourse(event: FormEvent) {
    event.preventDefault();
    const id = `course-${Date.now()}`;
    setCourses((current) => [...current, { course_id: id, class_group_id: id, course_name: courseDraft.name, day, start_time: courseDraft.start, end_time: courseDraft.end, location: { building: courseDraft.building, room: courseDraft.room } }]);
    setCourseDraft({ name: "", start: "09:00", end: "10:30", building: "", room: "" }); setModal(null);
  }

  function plannerMeetingsFor(course: CatalogCourse): Course[] {
    const classGroupId = course.class_group_id ?? `${course.code}-${course.instructor || "group"}`;
    return course.meetings.flatMap((meeting) => {
      const courseDay = koreanDay[meeting.day];
      if (!courseDay) return [];
      const time = catalogMeetingTimes(meeting);
      return [{
        course_id: course.code, class_group_id: classGroupId, course_name: course.name,
        day: courseDay, start_time: time.start, end_time: time.end, instructor: course.instructor,
        course_type: course.category, credits: course.credits, department: course.department ?? undefined,
        location: { building: meeting.building ?? "", room: meeting.room ?? "" },
      } satisfies Course];
    });
  }

  function finishCatalogCourseAddition(course: CatalogCourse, conflictingGroupIds: string[] = []) {
    const selectedMeetings = plannerMeetingsFor(course);
    if (!selectedMeetings.length) {
      setMessage("강의 시간이 등록되지 않은 분반입니다.");
      return;
    }
    setCourses((current) => [...current.filter((item) => !conflictingGroupIds.includes(item.class_group_id)), ...selectedMeetings]);
    setRecommendations([]); setRecoveryBlocks([]); setPlannerCoursePreview(null); setPendingCatalogAddition(null);
    const section = (course.class_group_id ?? "").split("-").at(-1) ?? "";
    setMessage(`${course.name} ${section}분반을 시간표에 추가했습니다.`);
  }

  function addCatalogCourseToPlanner(course: CatalogCourse) {
    const classGroupId = course.class_group_id ?? `${course.code}-${course.instructor || "group"}`;
    if (courses.some((item) => item.class_group_id === classGroupId)) {
      setMessage("이미 시간표에 추가한 분반입니다.");
      return;
    }
    const selectedMeetings = plannerMeetingsFor(course);
    if (!selectedMeetings.length) {
      setMessage("강의 시간이 등록되지 않은 분반입니다.");
      return;
    }
    const conflicts = courses.filter((existing) => selectedMeetings.some((added) => added.day === existing.day && timeToMinutes(added.start_time) < timeToMinutes(existing.end_time) && timeToMinutes(existing.start_time) < timeToMinutes(added.end_time)));
    if (conflicts.length) {
      const conflictingCourses = [...new Map(conflicts.map((item) => [item.class_group_id, item.course_name])).entries()];
      setPendingCatalogAddition({ course, conflicting_group_ids: conflictingCourses.map(([id]) => id), conflicting_course_names: conflictingCourses.map(([, name]) => name) });
      return;
    }
    finishCatalogCourseAddition(course);
  }

  function recommendationDropTarget(event: DragEvent<HTMLDivElement>, recommendation: Recommendation) {
    const rect = event.currentTarget.getBoundingClientRect();
    const dayWidth = (rect.width - 56) / days.length;
    const dayIndex = Math.floor((event.clientX - rect.left - 56) / dayWidth);
    if (dayIndex < 0 || dayIndex >= days.length) return null;
    const duration = recommendation.duration_minutes;
    const offsetMinutes = Math.round((event.clientY - rect.top - 44) / 30) * 30;
    const startMinutes = Math.max(8 * 60, Math.min(22 * 60 - duration, 8 * 60 + offsetMinutes));
    const endMinutes = startMinutes + duration;
    return { ...recommendation, day: days[dayIndex].value, start_time: minutesToTime(startMinutes), end_time: minutesToTime(endMinutes) };
  }

  function previewRecommendationMove(event: DragEvent<HTMLDivElement>) {
    if (!plannerCoursePickerOpen || !draggingRecommendation) return;
    event.preventDefault();
    setRecommendationDragPreview(recommendationDropTarget(event, draggingRecommendation));
  }

  function moveRecommendation(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const recommendation = draggingRecommendation;
    if (!plannerCoursePickerOpen || !recommendation) return;
    const target = recommendationDropTarget(event, recommendation);
    if (!target) return;
    const startMinutes = timeToMinutes(target.start_time);
    const endMinutes = timeToMinutes(target.end_time);
    const day = target.day;
    const overlaps = (start: string, end: string) => startMinutes < timeToMinutes(end) && timeToMinutes(start) < endMinutes;
    if (courses.some((course) => course.day === day && overlaps(course.start_time, course.end_time))) {
      setMessage("수업 시간과 겹쳐 추천 활동을 옮길 수 없습니다."); setDraggingRecommendation(null); setRecommendationDragPreview(null);
      return;
    }
    if (recommendations.some((item) => item !== recommendation && item.day === day && overlaps(item.start_time, item.end_time))) {
      setMessage("다른 추천 활동과 겹쳐 옮길 수 없습니다."); setDraggingRecommendation(null); setRecommendationDragPreview(null);
      return;
    }
    setRecommendations((current) => current.map((item) => item === recommendation ? target : item));
    setDraggingRecommendation(null); setRecommendationDragPreview(null);
  }

  function saveActivity() {
    const savedActivity: Activity = {
      activity_id: editingActivityId ?? `activity-${Date.now()}`, category: activityDraft.category, activity_name: activityDraft.name,
      priority: activityDraft.priority, schedule_type: activityDraft.useWeeklyPlan && activityDraft.fixed ? "FIXED_DAY" : "FLEXIBLE_DAY",
      duration_minutes: activityDraft.duration, frequency_per_week: activityDraft.useWeeklyPlan && !activityDraft.fixed ? activityDraft.frequency : null,
      completed_count_this_week: 0, preferred_days: activityDraft.useWeeklyPlan && activityDraft.fixed ? activityDraft.preferredDays : [],
      preferred_time_range: activityDraft.preferred ? { start_time: activityDraft.preferredStart, end_time: activityDraft.preferredEnd } : null,
    };
    setActivities((current) => editingActivityId
      ? current.map((item) => item.activity_id === editingActivityId ? savedActivity : item)
      : [...current, savedActivity]);
    if (editingActivityId) setRecommendations((current) => current.filter((item) => item.activity_id !== editingActivityId));
    closeModal();
  }

  function openNewActivity() {
    setActivityDraft({ ...initialActivityDraft, preferredDays: ["MON"] });
    setEditingActivityId(null); setStep(1); setModal("activity");
  }

  function openActivityEditor(activity: Activity) {
    setActivityDraft({
      category: activity.category, name: activity.activity_name, priority: activity.priority,
      duration: activity.duration_minutes, useWeeklyPlan: activity.schedule_type === "FIXED_DAY" || activity.frequency_per_week !== null,
      frequency: activity.frequency_per_week ?? 2, fixed: activity.schedule_type === "FIXED_DAY",
      preferredDays: activity.preferred_days.length ? activity.preferred_days : ["MON"],
      preferred: activity.preferred_time_range !== null,
      preferredStart: activity.preferred_time_range?.start_time ?? "17:00",
      preferredEnd: activity.preferred_time_range?.end_time ?? "21:00",
    });
    setEditingActivityId(activity.activity_id); setStep(1); setModal("activity");
  }

  function closeModal() {
    setModal(null); setStep(1); setEditingActivityId(null);
    setActivityDraft({ ...initialActivityDraft, preferredDays: ["MON"] });
    setPlannerCourseSearch(""); setPlannerCourseResults([]);
  }

  async function generateTimetables(event: FormEvent) {
    event.preventDefault(); setTimetableMessage("");
    if (curriculumResult && !selectedCurriculumCodes.length) {
      setTimetableMessage("교육과정에서 강의 목록과 일치한 과목을 한 개 이상 선택하세요.");
      return;
    }
    setTimetableLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/timetables/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_grade: Number(studentGrade), semester: Number(semester), target_credits: 24, required_course_codes: selectedCurriculumCodes,
          candidate_course_codes: selectedCurriculumCodes.length ? selectedCurriculumCodes : null,
          preferred_free_day: freeDay || null, avoid_morning: avoidMorning,
          preferred_first_class_start: firstClassStart ? Number(firstClassStart) : null,
          wants_lunch: wantsLunch, wants_dinner: wantsDinner,
          minimum_travel_minutes: travelMinutes ? Number(travelMinutes) : null,
          max_daily_classes: maxDailyClasses ? Number(maxDailyClasses) : null,
          preferred_end_time: endTime ? Number(endTime) : null, max_results: 3,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(readableError(data.detail, "시간표를 생성하지 못했습니다."));
      const generated = data.timetables as Timetable[];
      setTimetables(generated);
      if (!generated.length) setTimetableMessage("현재 학점과 조건을 만족하는 시간표가 없습니다. 학점 또는 선택 과목을 조정해 보세요.");
    } catch (error) { setTimetableMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
    finally { setTimetableLoading(false); }
  }

  function selectCurriculumFile(event: ChangeEvent<HTMLInputElement>) {
    setCurriculumFile(event.target.files?.[0] ?? null);
    setCurriculumResult(null); setSelectedCurriculumCodes(manualCourses.map((course) => course.code)); setCurriculumMessage("");
  }

  async function parseCurriculum() {
    if (!curriculumFile) return;
    setCurriculumLoading(true); setCurriculumMessage("");
    try {
      const formData = new FormData();
      formData.append("file", curriculumFile);
      const response = await fetch(`${apiBase}/api/v1/curriculum/parse`, {
        method: "POST", body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(readableError(data.detail, "교육과정을 분석하지 못했습니다."));
      const result = data as CurriculumParseResult;
      setCurriculumResult({ ...result, courses: result.courses.map((course) => ({ ...course, name: koreanCourseName(course.name) })) });
      setSelectedCurriculumCodes(manualCourses.map((course) => course.code));
      setCurriculumMessage(result.available_course_codes.length
        ? `${result.matched_course_count}개 과목을 강의 목록에서 찾았습니다. 추천에 포함할 과목을 확인하세요.`
        : "문서는 분석했지만 강의 목록과 일치한 과목을 찾지 못했습니다.");
    } catch (error) { setCurriculumMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
    finally { setCurriculumLoading(false); }
  }

  function applyTimetable(table: Timetable) {
    const imported: Course[] = table.courses.flatMap((course) => course.meetings.map((meeting) => ({
      course_id: course.code, class_group_id: course.class_group_id ?? `${course.code}-${course.instructor || "group"}`, course_name: course.name, day: koreanDay[meeting.day],
      start_time: catalogMeetingTimes(meeting).start, end_time: catalogMeetingTimes(meeting).end,
      instructor: course.instructor, credits: course.credits, course_type: course.category,
      location: { building: meeting.building ?? "", room: meeting.room ?? "" },
    }))).filter((course) => Boolean(course.day));
    setCourses(imported); setView("week"); setMessage("추천 시간표를 이번 주 시간표에 반영했습니다.");
  }

  async function exportTimetable() {
    setShareMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/saved-timetables`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timezone: "Asia/Seoul", classes: courses, activities, recommendations, recovery_blocks: recoveryBlocks }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "시간표를 저장하지 못했습니다.");
      setShareCode(data.code);
      setShareMessage("시간표를 저장했습니다. 아래 코드를 보관하세요.");
    } catch (error) { setShareMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
  }

  async function importTimetable(event: FormEvent) {
    event.preventDefault();
    setShareMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/saved-timetables/${importCode.trim().toUpperCase()}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "시간표를 불러오지 못했습니다.");
      setCourses((data.classes as (Course & { class_group_id?: string })[]).map((course) => ({
        ...course, class_group_id: course.class_group_id || course.course_id,
      })));
      setActivities((data.activities ?? []) as Activity[]);
      setRecommendations((data.recommendations ?? []) as Recommendation[]);
      setRecoveryBlocks((data.recovery_blocks ?? []) as RecoveryBlock[]);
      setShareMessage("저장된 시간표를 불러왔습니다.");
    } catch (error) { setShareMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
  }

  const curriculumPanel = view === "semester" && <section className="curriculum-panel" aria-labelledby="curriculum-title">
    <div className="curriculum-intro"><p className="eyebrow">COURSE PICKER</p><h2 id="curriculum-title">원하는 수업 추가하기</h2><p>교육과정 파일을 올리거나, 강의 검색으로 원하는 수업을 시간표 후보에 추가하세요.</p></div>
    <div className="curriculum-controls">
      <label className="file-input curriculum-file"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.docx,.pptx,.xlsx,.hwp,.hwpx" onChange={selectCurriculumFile}/><span>{curriculumFile ? curriculumFile.name : "교육과정 파일 선택"}</span></label>
      <button type="button" className="curriculum-upload" onClick={parseCurriculum} disabled={!curriculumFile || curriculumLoading}>{curriculumLoading ? "문서 분석 중..." : "교육과정 분석"}</button>
    </div>
    {curriculumMessage && <p className={curriculumResult?.available_course_codes.length ? "curriculum-message success" : "curriculum-message"}>{curriculumMessage}</p>}
    {courseSearchPanel}
    {curriculumResult && <div className="curriculum-result"><div className="curriculum-summary"><b>{curriculumResult.source_filename}</b><span>인식 과목 {curriculumResult.course_count}개 · 강의 목록 일치 {curriculumResult.matched_course_count}개</span></div>
      {curriculumCandidateGroups.length > 0 && <details className="curriculum-course-list"><summary>시간표 후보에 포함할 과목</summary><p>현재 학기에 개설되지 않은 과목은 표시되지 않습니다.</p>{curriculumCandidateGroups.map((group) => <section className="curriculum-course-group" key={group.label}><h3>{group.label}</h3><div>{group.courses.map((course, index) => {
        const codes = course.catalog_course_codes;
        const checked = codes.every((code) => selectedCurriculumCodes.includes(code));
        return <label key={`${course.code ?? course.name}-${index}`}><input type="checkbox" checked={checked} onChange={(event) => setSelectedCurriculumCodes((current) => event.target.checked ? Array.from(new Set([...current, ...codes])) : current.filter((code) => !codes.includes(code)))}/><span><b>{course.name}</b><small>{codes.join(", ")} · {course.credits ? `${course.credits}학점` : "학점 정보 없음"} · {course.category ?? "이수구분 정보 없음"}{course.match_type === "name" ? " · 과목명으로 매칭" : ""}</small></span></label>;
      })}</div></section>)}</details>}
    </div>}
  </section>;

  const courseColorByGroup = new Map(
    [...new Set(courses.map((course) => course.class_group_id))]
      .sort()
      .map((groupId, index) => [groupId, `hsl(${(index * 137.508) % 360} 48% 94%)`]),
  );
  const totalCredits = [...new Map(courses.map((course) => [course.class_group_id, course])).values()]
    .reduce((total, course) => total + (catalogCredits[course.class_group_id] ?? course.credits ?? 0), 0);
  const plannerBoard = <div className="planner-scroll"><div className="planner-grid" onDragOver={previewRecommendationMove} onDrop={moveRecommendation}>
    <div className="corner"/>{days.map((item, index) => <div key={item.value} className="planner-day" style={{ gridColumn: index + 2, gridRow: 1 }}>{item.label}요일</div>)}
    {Array.from({ length: 15 }, (_, index) => index + 8).map((hour, index) => <div className="time-label" key={hour} style={{ gridColumn: 1, gridRow: `${2 + index * 2} / span 2` }}>{String(hour).padStart(2, "0")}:00</div>)}
    {days.map((item, dayIndex) => <div key={item.value} className="planner-lane" style={{ gridColumn: dayIndex + 2, gridRow: "2 / span 28" }}/>)}
    {courses.map((course) => {
      const dayIndex = days.findIndex((item) => item.value === course.day);
      const searchCourse = () => {
        if (!plannerCoursePickerOpen) return;
        setPlannerCourseSearch(course.course_name);
        setPlannerCoursePreview(null);
      };
      const searchCourseOnKeyDown = (event: KeyboardEvent<HTMLElement>) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); searchCourse(); }
      };
      return <article className={`planner-block course-block${plannerCoursePickerOpen ? " editable" : ""}`} key={`${course.class_group_id}-${course.day}`} role={plannerCoursePickerOpen ? "button" : undefined} tabIndex={plannerCoursePickerOpen ? 0 : undefined} onClick={searchCourse} onKeyDown={searchCourseOnKeyDown} style={{ ...timetableBlockPosition(dayIndex, course.start_time, course.end_time), backgroundColor: courseColorByGroup.get(course.class_group_id) }}><b>{course.course_name}</b><span>{course.start_time}–{course.end_time}{course.instructor ? ` · ${course.instructor}` : ""}</span>{plannerCoursePickerOpen && <button aria-label={`${course.course_name} 삭제`} onClick={(event) => { event.stopPropagation(); setCourses((current) => current.filter((item) => item.class_group_id !== course.class_group_id)); }}>×</button>}</article>;
    })}
    {plannerCoursePreview?.meetings.map((meeting, index) => {
      const day = koreanDay[meeting.day];
      const dayIndex = days.findIndex((item) => item.value === day);
      if (dayIndex < 0) return null;
      const time = catalogMeetingTimes(meeting);
      return <article className="planner-block course-preview-block" aria-hidden="true" key={`${plannerCoursePreview.class_group_id ?? plannerCoursePreview.code}-${index}`} style={timetableBlockPosition(dayIndex, time.start, time.end)}><b>{plannerCoursePreview.name}</b><span>{time.start}–{time.end} · {plannerCoursePreview.instructor || "미리보기"}</span></article>;
    })}
    {recommendations.map((item) => {
      const dayIndex = days.findIndex((entry) => entry.value === item.day);
      const tooltipId = `reason-${item.day}-${item.activity_id}-${item.start_time.replace(":", "")}`;
      const tooltipBelow = Number(item.start_time.slice(0, 2)) < 10;
      return <article className={`planner-block recommendation-block${tooltipBelow ? " tooltip-below" : ""}`} draggable={plannerCoursePickerOpen} tabIndex={0} aria-describedby={tooltipId} key={`${item.day}-${item.activity_id}-${item.start_time}`} style={timetableBlockPosition(dayIndex, item.start_time, item.end_time)} onDragStart={(event) => { if (!plannerCoursePickerOpen) return; event.dataTransfer.effectAllowed = "move"; setDraggingRecommendation(item); setRecommendationDragPreview(null); }} onDragEnd={() => { setDraggingRecommendation(null); setRecommendationDragPreview(null); }}><b>{iconMap[item.category]} {item.activity_name}</b><span>{item.start_time}–{item.end_time}</span><small>추천 활동 · 이유 보기</small><div className="recommendation-tooltip" role="tooltip" id={tooltipId}><b>왜 이 시간에 추천했나요?</b><p>{item.reason}</p></div><button aria-label={`${item.activity_name} 추천 삭제`} onClick={() => setRecommendations((current) => current.filter((entry) => !(entry.day === item.day && entry.activity_id === item.activity_id && entry.start_time === item.start_time && entry.end_time === item.end_time)))}>×</button></article>;
    })}
    {recommendationDragPreview && <article className="planner-block recommendation-preview-block" aria-hidden="true" style={timetableBlockPosition(days.findIndex((item) => item.value === recommendationDragPreview.day), recommendationDragPreview.start_time, recommendationDragPreview.end_time)}><b>{iconMap[recommendationDragPreview.category]} {recommendationDragPreview.activity_name}</b><span>{recommendationDragPreview.start_time}–{recommendationDragPreview.end_time}</span><small>이동 예정</small></article>}
  </div></div>;

  function openAdminAfterFiveLogoClicks(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    logoClickCount.current += 1;
    if (logoClickTimer.current) window.clearTimeout(logoClickTimer.current);
    if (logoClickCount.current === 5) {
      logoClickCount.current = 0;
      window.location.assign("/admin");
      return;
    }
    logoClickTimer.current = window.setTimeout(() => { logoClickCount.current = 0; }, 1200);
  }

  const plannerCoursePicker = plannerCoursePickerOpen && <section className="planner-course-picker" aria-label="시간표 수업 추가">
    <div><p className="eyebrow">TIMETABLE EDIT</p><h3>수업·분반 추가</h3><p>현재 시간표를 보면서 원하는 분반을 선택하세요.</p></div>
    <label>과목 검색<input autoFocus value={plannerCourseSearch} onChange={(event) => { setPlannerCourseSearch(event.target.value); setPlannerCoursePreview(null); }} placeholder="예: 확률통계 또는 CB1501012"/></label>
    {pendingCatalogAddition && <div className="course-conflict-notice" role="alert"><b>시간표가 겹칩니다</b><p>{pendingCatalogAddition.conflicting_course_names.join(", ")} 과목을 제거하고 <strong>{pendingCatalogAddition.course.name}</strong> 분반을 추가할까요?</p><div><button type="button" onClick={() => finishCatalogCourseAddition(pendingCatalogAddition.course, pendingCatalogAddition.conflicting_group_ids)}>확인</button><button type="button" onClick={() => setPendingCatalogAddition(null)}>취소</button></div></div>}
    {plannerCourseSearch.trim().length >= 2 && <div className="catalog-picker-results">{plannerCourseLoading ? <span>검색 중...</span> : plannerCourseResults.length ? plannerCourseResults.map((course) => { const groupId = course.class_group_id ?? `${course.code}-${course.instructor || "group"}`; const selected = courses.some((item) => item.class_group_id === groupId); const meetingTimes = course.meetings.map((meeting) => { const time = catalogMeetingTimes(meeting); return `${meeting.day} ${time.start}–${time.end}`; }); const classrooms = [...new Set(course.meetings.flatMap((meeting) => meeting.building && meeting.room ? [`${meeting.building}-${meeting.room}`] : []))]; return <article key={groupId} onMouseEnter={() => setPlannerCoursePreview(course)} onMouseLeave={() => setPlannerCoursePreview(null)}><div><b>{course.name}</b><small>{course.code} · {groupId.split("-").at(-1) ?? ""}분반 · {course.instructor || "담당 교수 미정"}</small><small className="catalog-meeting-details"><span>{meetingTimes.join("  ")}</span>{classrooms.length > 0 && <span>{classrooms.join(" · ")}</span>}</small></div><button type="button" disabled={selected} onClick={() => addCatalogCourseToPlanner(course)}>{selected ? "추가됨" : "추가"}</button></article>; }) : <span>일치하는 개설 과목이 없습니다.</span>}</div>}
  </section>;

  return <main>
    <header><a className="logo" href="#" onClick={openAdminAfterFiveLogoClicks}><b>틈</b><span>공강을 나답게</span></a><nav className="page-nav"><button className={view === "semester" ? "active" : ""} onClick={() => setView("semester")}>학기 시간표 추천</button><button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>빈 시간 채우기</button><button className={view === "all" ? "active" : ""} onClick={() => setView("all")}>전체 시간표 보기</button></nav></header>

    {view === "week" && <><section className="compact-hero"><div><p className="eyebrow">WEEKLY PLANNER</p><h1>이번 주의 빈틈을<br/><em>한눈에 채워보세요.</em></h1></div></section>
      <section className="week-top"><section className="activity-dock"><div className="section-title"><div><p className="eyebrow">MY ACTIVITIES</p><h2>등록한 활동</h2></div><button className="add" onClick={openNewActivity}>+</button></div>{activities.length ? <div className="activity-row">{activities.map((activity) => <article key={activity.activity_id}><span className="activity-icon">{iconMap[activity.category]}</span><div><b>{activity.activity_name}</b><small>{categoryMap[activity.category]} · {activity.schedule_type === "FIXED_DAY" ? activity.preferred_days.map((value) => days.find((item) => item.value === value)?.label).join("·") + "요일" : activity.frequency_per_week ? `주 ${activity.frequency_per_week}회` : "요일·횟수 자유"} · {durationLabel(activity.duration_minutes)}</small></div><div className="activity-controls"><button className="edit-activity" onClick={() => openActivityEditor(activity)} aria-label={`${activity.activity_name} 수정`}>수정</button><button className="delete-activity" onClick={() => { setActivities((current) => current.filter((item) => item.activity_id !== activity.activity_id)); setRecommendations((current) => current.filter((item) => item.activity_id !== activity.activity_id)); }} aria-label={`${activity.activity_name} 삭제`}>삭제</button></div></article>)}</div> : <p className="empty-result">등록된 활동이 없습니다. + 버튼으로 활동을 추가하세요.</p>}</section>
      <section className="recommend-action"><span>✦</span><p>{courses.length ? "월요일부터 금요일까지" : "시간표 없이도 테스트 가능"}</p><h2>빈 시간을 한 번에<br/>채워드릴게요.</h2><button onClick={recommend} disabled={busy || !activities.length}>{busy ? "추천 중..." : "활동 추천받기"} →</button></section></section>
      {!courses.length && <p className="simulation-notice">현재 적용된 학기 시간표가 없어 월–금 08:00~22:00를 빈 시간으로 사용합니다. 활동을 등록하면 추천·비효율 모드·회복 점수를 모두 시험할 수 있어요.</p>}
      <section className="inefficiency-panel">
        <div className="inefficiency-settings">
          <div className="mode-title"><div><p className="eyebrow">MANUAL SETTINGS</p><h2>비효율 모드</h2></div><label className="mode-switch"><input type="checkbox" checked={inefficiencyEnabled} onChange={(event) => setInefficiencyEnabled(event.target.checked)}/><span/></label></div>
          <p>앞으로 활동을 어떻게 추천할지 직접 설정해요. 점수 계산과는 독립적으로 작동합니다.</p>
          <fieldset disabled={!inefficiencyEnabled}><legend>일정 밀도</legend><div className="percent-buttons">{[100,75,50,25,0].map((value) => <button type="button" className={targetDensity === value ? "active" : ""} key={value} onClick={() => setTargetDensity(value)}>{value}%</button>)}</div><legend>이번 주 컨디션</legend><small>{({100:"매우 좋음",75:"좋음",50:"보통",25:"피곤함",0:"매우 피곤함"} as Record<number,string>)[weeklyCondition]}</small><div className="percent-buttons">{[100,75,50,25,0].map((value) => <button type="button" className={weeklyCondition === value ? "active" : ""} key={value} onClick={() => setWeeklyCondition(value)}>{value}%</button>)}</div></fieldset>
          <button className="reapply-button" onClick={recommend} disabled={!inefficiencyEnabled || busy || !activities.length}>{busy ? "다시 추천 중..." : "비효율 모드 적용하여 다시 추천"}</button>
        </div>
        <div className="recovery-result">
          <p className="eyebrow">AUTOMATIC ANALYSIS</p><h2>회복 점수</h2>
          {recoveryAnalysis ? <><div className="recovery-visual"><img src={`/recovery/grade-${recoveryAnalysis.grade}.png`} alt={`${recoveryAnalysis.grade}등급 회복 상태`}/><div className="score-number"><b>{recoveryAnalysis.score}</b><span>점</span></div></div><button className="close-score-button" onClick={() => { setRecoveryAnalysis(null); setShowRecoveryDetails(false); }}>회복 점수 닫기</button></> : <><p className="recovery-placeholder">현재 플래너를 기준으로 원할 때 회복 점수를 계산할 수 있어요.</p><button className="calculate-score-button" onClick={calculateRecovery} disabled={busy}>{busy ? "계산 중..." : "회복 점수 계산하기"}</button></>}
          <button className="score-detail-button" onClick={() => setShowRecoveryDetails(!showRecoveryDetails)}>{showRecoveryDetails ? "회복 점수 설명 닫기" : "회복 점수란? · 계산 방법 보기"}</button>
          {showRecoveryDetails && <div className="score-details"><h3>회복 점수란?</h3><p>현재 시간표에 수업 사이 여유와 회복 가능한 시간이 얼마나 있는지를 100점으로 보여주는 지표예요. 의료적 판단이나 건강 진단을 의미하지 않습니다.</p><h3>어떻게 계산하나요?</h3><ul><li>휴식·공강 시간 <b>최대 40점</b></li><li>하루 일정 밀도 <b>최대 25점</b></li><li>가장 긴 연속 집중 시간 <b>최대 20점</b></li><li>휴식·취미·친구·회복 시간 <b>최대 15점</b></li></ul>{recoveryAnalysis ? <><h3>현재 점수</h3><ul><li>휴식 시간 <b>{recoveryAnalysis.score_details.rest_time_score} / 40</b></li><li>일정 밀도 <b>{recoveryAnalysis.score_details.schedule_density_score} / 25</b></li><li>연속 집중 시간 <b>{recoveryAnalysis.score_details.continuous_focus_score} / 20</b></li><li>회복 활동 <b>{recoveryAnalysis.score_details.recovery_activity_score} / 15</b></li></ul><p>현재 반영: 공강 {recoveryAnalysis.total_rest_minutes}분 · 일정 밀도 {recoveryAnalysis.schedule_density_percent}% · 최장 연속 일정 {recoveryAnalysis.longest_continuous_focus_minutes}분</p>{recoveryAnalysis.reasons.map((reason) => <small key={reason}>{reason}</small>)}{recoveryAnalysis.suggestions.map((suggestion) => <small className="suggestion" key={suggestion}>{suggestion}</small>)}</> : <small>학기 시간표를 적용하면 여기에 현재 점수의 세부 계산 결과가 표시됩니다.</small>}</div>}
        </div>
      </section>
      <section className="planner-shell"><div className="planner-toolbar"><div><p className="eyebrow">WEEK AT A GLANCE</p><h2>빈 시간 채우기</h2><p className="timetable-credit-total">총 <b>{totalCredits}</b>학점</p></div><button type="button" onClick={() => setPlannerCoursePickerOpen((open) => { if (open) { setPlannerCoursePreview(null); setDraggingRecommendation(null); setRecommendationDragPreview(null); } return !open; })}>{plannerCoursePickerOpen ? "수정 닫기" : "시간표 수정"}</button></div><div className={plannerCoursePickerOpen ? "planner-editor-layout editing" : "planner-editor-layout"}><div>{message && <p className="planner-message">{message}</p>}{plannerBoard}</div>{plannerCoursePicker}</div></section>
    </>}

    {view === "semester" && <section className="standalone-page">
      <div className="section-title"><div><p className="eyebrow">SEMESTER PLANNER</p><h1>학기 시간표 추천</h1></div></div>{curriculumPanel}
      <div className="semester-grid">
        <form className="panel semester-settings" onSubmit={generateTimetables} aria-busy={timetableLoading}>
          <section className="semester-profile" aria-labelledby="semester-profile-title">
            <h2 id="semester-profile-title">수강 정보</h2>
            <label>학년<select value={studentGrade} onChange={(event) => setStudentGrade(event.target.value)}>{[1, 2, 3, 4].map((grade) => <option value={grade} key={grade}>{grade}학년</option>)}</select></label>
            <label>학기<select value={semester} onChange={(event) => setSemester(event.target.value)}>{[1, 2].map((value) => <option value={value} key={value}>{value}학기</option>)}</select></label>
          </section>
          <section className="timetable-checklist" aria-labelledby="timetable-checklist-title">
            <h2 id="timetable-checklist-title">시간표 체크리스트</h2>
            <label>희망 첫 수업 시작 시간<select value={firstClassStart} onChange={(event) => setFirstClassStart(event.target.value)}><option value="">상관없음</option>{[9,10,11,12,13].map((hour) => <option key={hour} value={hour}>{hour}:00 이후</option>)}</select></label>
            <label className="check">점심시간 확보<input type="checkbox" checked={wantsLunch} onChange={(event) => setWantsLunch(event.target.checked)}/></label>
            <label className="check">저녁시간 확보<input type="checkbox" checked={wantsDinner} onChange={(event) => setWantsDinner(event.target.checked)}/></label>
            <label>원하는 공강 요일<select value={freeDay} onChange={(event) => setFreeDay(event.target.value)}><option value="">없음</option>{["월","화","수","목","금"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>이동 시간<select value={travelMinutes} onChange={(event) => setTravelMinutes(event.target.value)}><option value="">상관없음</option>{[10,20,30,60].map((minutes) => <option key={minutes} value={minutes}>{minutes}분</option>)}</select></label>
            <label>하루 최대 수업<select value={maxDailyClasses} onChange={(event) => setMaxDailyClasses(event.target.value)}><option value="">상관없음</option>{[2,3,4,5,6].map((count) => <option key={count} value={count}>{count}개</option>)}</select></label>
            <label>희망 하교 시간<select value={endTime} onChange={(event) => setEndTime(event.target.value)}><option value="">상관없음</option>{[15,16,17,18,19,20].map((hour) => <option key={hour} value={hour}>{hour}:00 이전</option>)}</select></label>
          </section>
          <button className="primary timetable-submit" disabled={timetableLoading}>{timetableLoading ? <><span className="loading-spinner" aria-hidden="true"/>시간표 만드는 중...</> : <>시간표 만들기 <span aria-hidden="true">→</span></>}</button>
        </form>
        <div className="semester-results">
          {timetableLoading && <div className="timetable-loading" role="status"><span className="loading-spinner" aria-hidden="true"/><div><b>조건에 맞는 시간표를 찾고 있어요.</b><p>강좌 조합과 시간 조건을 확인하는 중입니다.</p></div></div>}
          {timetableMessage && <p className="error">{timetableMessage}</p>}
          {!timetableLoading && !timetables.length && !timetableMessage && <p className="empty-result">조건을 설정하면 추천 시간표가 여기에 표시됩니다.</p>}
          {timetables.map((table) => <article className="panel" key={`${table.title}-${table.score}`}>
            <p className="eyebrow">{table.title}</p><h3>{table.total_credits}학점 · 점수 {table.score}</h3>
            {table.courses.map((course) => <div className="catalog-course" key={course.class_group_id ?? `${course.code}-${course.instructor}`}><b>{course.name}</b><span>{course.instructor} · {course.meetings.map((meeting) => { const time = catalogMeetingTimes(meeting); return `${meeting.day} ${time.start}–${time.end}`; }).join(" · ")}</span></div>)}
            <button type="button" className="apply-button" onClick={() => applyTimetable(table)}>이 시간표 적용</button>
          </article>)}
        </div>
      </div>
    </section>}

    {view === "all" && <section className="standalone-page"><div className="section-title"><div><p className="eyebrow">ALL SCHEDULES</p><h1>전체 시간표 보기</h1><p className="timetable-credit-total">총 <b>{totalCredits}</b>학점</p></div></div><div className="share-tools"><section><p className="eyebrow">EXPORT</p><h2>시간표 내보내기</h2><p>현재 시간표를 DB에 저장하고 복원 코드를 발급합니다.</p><button onClick={exportTimetable} disabled={!courses.length}>내보내기</button>{shareCode && <div className="share-code"><span>{shareCode}</span><button onClick={() => navigator.clipboard.writeText(shareCode)}>복사</button></div>}</section><form onSubmit={importTimetable}><p className="eyebrow">IMPORT</p><h2>시간표 불러오기</h2><p>이전에 발급받은 코드를 입력하세요.</p><div><input required maxLength={8} value={importCode} onChange={(event) => setImportCode(event.target.value.toUpperCase())} placeholder="8자리 코드"/><button>불러오기</button></div></form></div>{shareMessage && <p className="planner-message">{shareMessage}</p>}{plannerBoard}</section>}

    {modal && <div className="backdrop" onMouseDown={closeModal}><section className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><button className="close" onClick={closeModal}>×</button>
      {modal === "course" ? <form onSubmit={saveCourse}><p className="eyebrow">새 수업</p><h2>수업 추가하기</h2><label>요일<select value={day} onChange={(event) => setDay(event.target.value as Day)}>{days.map((item) => <option value={item.value} key={item.value}>{item.label}요일</option>)}</select></label><label>수업명<input required value={courseDraft.name} onChange={(event) => setCourseDraft({ ...courseDraft, name: event.target.value })}/></label><div className="two"><label>시작<input type="time" value={courseDraft.start} onChange={(event) => setCourseDraft({ ...courseDraft, start: event.target.value })}/></label><label>종료<input type="time" value={courseDraft.end} onChange={(event) => setCourseDraft({ ...courseDraft, end: event.target.value })}/></label></div><div className="two"><label>건물<input value={courseDraft.building} onChange={(event) => setCourseDraft({ ...courseDraft, building: event.target.value })}/></label><label>강의실<input value={courseDraft.room} onChange={(event) => setCourseDraft({ ...courseDraft, room: event.target.value })}/></label></div><button className="primary">추가하기</button></form>
      : <><p className="eyebrow">{editingActivityId ? "EDIT ACTIVITY" : `STEP ${step} OF 3`}</p><h2>{step === 1 ? editingActivityId ? "활동을 수정할까요?" : "어떤 활동을 하고 싶나요?" : step === 2 ? "얼마나 필요할까요?" : "선호 조건이 있나요?"}</h2><div className="progress"><span style={{ width: `${step * 33.33}%` }}/></div>
        {step === 1 && <><div className="category-grid">{categories.map(([value, label, icon]) => <button key={value} className={activityDraft.category === value ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, category: value })}><span>{icon}</span>{label}</button>)}</div>{activityDraft.category && <label>활동명<input autoFocus value={activityDraft.name} onChange={(event) => setActivityDraft({ ...activityDraft, name: event.target.value })} placeholder="활동명을 입력하세요"/></label>}</>}
        {step === 2 && <><div className="choices"><button className={activityDraft.priority === "REQUIRED" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "REQUIRED" })}><b>꼭 해야 해요</b><small>먼저 자리를 찾아요</small></button><button className={activityDraft.priority === "OPTIONAL" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "OPTIONAL" })}><b>가능하면 하고 싶어요</b><small>여유가 있을 때 추천해요</small></button></div><label>한 번에 필요한 시간 <b>{durationLabel(activityDraft.duration)}</b><input type="range" min="0" max="180" step="15" value={activityDraft.duration} onChange={(event) => setActivityDraft({ ...activityDraft, duration: Number(event.target.value) })}/></label></>}
        {step === 3 && <><label className="switch"><span>요일 또는 주간 횟수를 설정할게요</span><input type="checkbox" checked={activityDraft.useWeeklyPlan} onChange={(event) => setActivityDraft({ ...activityDraft, useWeeklyPlan: event.target.checked })}/></label>{activityDraft.useWeeklyPlan && <><label className="switch"><span>특정 요일을 정할게요</span><input type="checkbox" checked={activityDraft.fixed} onChange={(event) => setActivityDraft({ ...activityDraft, fixed: event.target.checked })}/></label>{activityDraft.fixed ? <div className="day-pills">{days.map((item) => <button key={item.value} className={activityDraft.preferredDays.includes(item.value) ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, preferredDays: activityDraft.preferredDays.includes(item.value) ? activityDraft.preferredDays.filter((value) => value !== item.value) : [...activityDraft.preferredDays, item.value] })}>{item.label}</button>)}</div> : <label>주간 횟수<input type="number" min="1" max="7" value={activityDraft.frequency} onChange={(event) => setActivityDraft({ ...activityDraft, frequency: Number(event.target.value) })}/></label>}</>}<label className="switch"><span>선호 시간대가 있어요</span><input type="checkbox" checked={activityDraft.preferred} onChange={(event) => setActivityDraft({ ...activityDraft, preferred: event.target.checked })}/></label>{activityDraft.preferred && <div className="two"><label>시작<input type="time" value={activityDraft.preferredStart} onChange={(event) => setActivityDraft({ ...activityDraft, preferredStart: event.target.value })}/></label><label>종료<input type="time" value={activityDraft.preferredEnd} onChange={(event) => setActivityDraft({ ...activityDraft, preferredEnd: event.target.value })}/></label></div>}</>}
        <div className="modal-actions">{step > 1 && <button className="secondary" onClick={() => setStep(step - 1)}>이전</button>}<button className="primary" disabled={(step === 1 && (!activityDraft.category || !activityDraft.name)) || (step === 2 && activityDraft.duration < 15) || (step === 3 && activityDraft.useWeeklyPlan && activityDraft.fixed && !activityDraft.preferredDays.length)} onClick={() => step < 3 ? setStep(step + 1) : saveActivity()}>{step < 3 ? "다음" : "저장"}</button></div></>}
    </section></div>}
  </main>;
}
