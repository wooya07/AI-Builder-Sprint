"use client";

import { FormEvent, useEffect, useState } from "react";

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
type CatalogCourse = { code: string; name: string; credits: number; instructor: string; meetings: { day: string; start: number; end: number }[] };
type Timetable = { title: string; score: number; reasons: string[]; courses: CatalogCourse[]; total_credits: number };

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
const durationLabel = (minutes: number) => {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  return `${hours ? `${hours}시간` : ""}${hours && rest ? " " : ""}${rest ? `${rest}분` : ""}` || "0분";
};
const readableError = (detail: unknown, fallback: string) => {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => typeof item?.msg === "string" ? item.msg : JSON.stringify(item)).join(" · ");
  if (detail && typeof detail === "object" && "msg" in detail && typeof detail.msg === "string") return detail.msg;
  return fallback;
};

export default function Home() {
  const [view, setView] = useState<View>("semester");
  const [day, setDay] = useState<Day>("MON");
  const [courses, setCourses] = useState<Course[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<"course" | "activity" | null>(null);
  const [step, setStep] = useState(1);
  const [courseDraft, setCourseDraft] = useState({ name: "", start: "09:00", end: "10:30", building: "", room: "" });
  const [activityDraft, setActivityDraft] = useState({ ...initialActivityDraft });
  const [editingActivityId, setEditingActivityId] = useState<string | null>(null);
  const [freeDay, setFreeDay] = useState("금");
  const [avoidMorning, setAvoidMorning] = useState(true);
  const [firstClassStart, setFirstClassStart] = useState("");
  const [wantsLunch, setWantsLunch] = useState(false);
  const [wantsDinner, setWantsDinner] = useState(false);
  const [maxConsecutiveClasses, setMaxConsecutiveClasses] = useState("");
  const [travelMinutes, setTravelMinutes] = useState("");
  const [maxDailyClasses, setMaxDailyClasses] = useState("");
  const [endTime, setEndTime] = useState("");
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [timetableMessage, setTimetableMessage] = useState("");
  const [shareCode, setShareCode] = useState("");
  const [importCode, setImportCode] = useState("");
  const [shareMessage, setShareMessage] = useState("");
  const [inefficiencyEnabled, setInefficiencyEnabled] = useState(false);
  const [targetDensity, setTargetDensity] = useState(75);
  const [weeklyCondition, setWeeklyCondition] = useState(50);
  const [autoRecovery, setAutoRecovery] = useState(true);
  const [recoveryBlocks, setRecoveryBlocks] = useState<RecoveryBlock[]>([]);
  const [recoveryAnalysis, setRecoveryAnalysis] = useState<RecoveryAnalysis | null>(null);
  const [showRecoveryDetails, setShowRecoveryDetails] = useState(false);

  useEffect(() => {
    setRecoveryAnalysis(null);
  }, [courses, activities, recommendations, recoveryBlocks]);

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
          body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), day: value, timezone: "Asia/Seoul", day_end_time: "22:00", classes: courses, activities, inefficiencyMode: { enabled: inefficiencyEnabled, targetScheduleDensity: targetDensity, weeklyCondition, autoRecoveryEnabled: autoRecovery } }),
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
      setRecoveryBlocks(results.flatMap((result) => result.recoveryBlocks));
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
  }

  async function generateTimetables(event: FormEvent) {
    event.preventDefault(); setTimetableMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/timetables/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_credits: 12, required_course_codes: [], preferred_free_day: freeDay, avoid_morning: avoidMorning, preferred_first_class_start: firstClassStart ? Number(firstClassStart) : null, wants_lunch: wantsLunch, wants_dinner: wantsDinner, max_consecutive_classes: maxConsecutiveClasses ? Number(maxConsecutiveClasses) : null, minimum_travel_minutes: travelMinutes ? Number(travelMinutes) : null, max_daily_classes: maxDailyClasses ? Number(maxDailyClasses) : null, preferred_end_time: endTime ? Number(endTime) : null, max_results: 3 }),
      });
      if (!response.ok) throw new Error("시간표를 생성하지 못했습니다.");
      setTimetables((await response.json()).timetables);
    } catch (error) { setTimetableMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
  }

  function applyTimetable(table: Timetable) {
    const imported: Course[] = table.courses.flatMap((course) => course.meetings.map((meeting, index) => ({
      course_id: course.code, class_group_id: `${course.code}-${course.instructor || "group"}`, course_name: course.name, day: koreanDay[meeting.day],
      start_time: `${String(meeting.start).padStart(2, "0")}:00`, end_time: `${String(meeting.end).padStart(2, "0")}:00`,
      location: { building: "", room: "" },
    }))).filter((course) => Boolean(course.day));
    setCourses(imported); setView("week"); setMessage("추천 시간표를 이번 주 시간표에 반영했습니다.");
  }

  async function exportTimetable() {
    setShareMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/saved-timetables`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timezone: "Asia/Seoul", classes: courses }),
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
      setRecommendations([]);
      setShareMessage("저장된 시간표를 불러왔습니다.");
    } catch (error) { setShareMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
  }

  const plannerBoard = <div className="planner-scroll"><div className="planner-grid">
    <div className="corner"/>{days.map((item, index) => <div key={item.value} className="planner-day" style={{ gridColumn: index + 2, gridRow: 1 }}>{item.label}요일</div>)}
    {Array.from({ length: 15 }, (_, index) => index + 8).map((hour, index) => <div className="time-label" key={hour} style={{ gridColumn: 1, gridRow: `${2 + index * 2} / span 2` }}>{String(hour).padStart(2, "0")}:00</div>)}
    {days.map((item, dayIndex) => <div key={item.value} className="planner-lane" style={{ gridColumn: dayIndex + 2, gridRow: "2 / span 28" }}/>)}
    {courses.map((course) => {
      const dayIndex = days.findIndex((item) => item.value === course.day);
      return <article className="planner-block course-block" key={`${course.class_group_id}-${course.day}`} style={{ gridColumn: dayIndex + 2, gridRow: `${timeToRow(course.start_time)} / ${timeToRow(course.end_time)}` }}><b>{course.course_name}</b><span>{course.start_time}–{course.end_time}</span><button aria-label={`${course.course_name} 삭제`} onClick={() => setCourses((current) => current.filter((item) => !(item.class_group_id === course.class_group_id && item.day === course.day)))}>×</button></article>;
    })}
    {recommendations.map((item) => {
      const dayIndex = days.findIndex((entry) => entry.value === item.day);
      return <article className="planner-block recommendation-block" key={`${item.day}-${item.activity_id}-${item.start_time}`} style={{ gridColumn: dayIndex + 2, gridRow: `${timeToRow(item.start_time)} / ${timeToRow(item.end_time)}` }}><b>{iconMap[item.category]} {item.activity_name}</b><span>{item.start_time}–{item.end_time}</span><small>추천 활동</small></article>;
    })}
    {recoveryBlocks.map((item) => {
      const dayIndex = days.findIndex((entry) => entry.value === item.day);
      return <article className="planner-block recovery-block" key={`${item.day}-${item.start_time}`} style={{ gridColumn: dayIndex + 2, gridRow: `${timeToRow(item.start_time)} / ${timeToRow(item.end_time)}` }}><b>☁ 회복 시간</b><span>{item.start_time}–{item.end_time}</span><small>다음 일정을 위해 비워 둔 시간</small></article>;
    })}
  </div></div>;

  return <main>
    <header><a className="logo" href="#"><b>틈</b><span>공강을 나답게</span></a><nav className="page-nav"><button className={view === "semester" ? "active" : ""} onClick={() => setView("semester")}>학기 시간표 추천</button><button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>빈 시간 채우기</button><button className={view === "all" ? "active" : ""} onClick={() => setView("all")}>전체 시간표 보기</button></nav></header>

    {view === "week" && <><section className="compact-hero"><div><p className="eyebrow">WEEKLY PLANNER</p><h1>이번 주의 빈틈을<br/><em>한눈에 채워보세요.</em></h1></div></section>
      <section className="week-top"><section className="activity-dock"><div className="section-title"><div><p className="eyebrow">MY ACTIVITIES</p><h2>등록한 활동</h2></div><button className="add" onClick={openNewActivity}>+</button></div>{activities.length ? <div className="activity-row">{activities.map((activity) => <article key={activity.activity_id}><span className="activity-icon">{iconMap[activity.category]}</span><div><b>{activity.activity_name}</b><small>{categoryMap[activity.category]} · {activity.schedule_type === "FIXED_DAY" ? activity.preferred_days.map((value) => days.find((item) => item.value === value)?.label).join("·") + "요일" : activity.frequency_per_week ? `주 ${activity.frequency_per_week}회` : "요일·횟수 자유"} · {durationLabel(activity.duration_minutes)}</small></div><div className="activity-controls"><button className="edit-activity" onClick={() => openActivityEditor(activity)} aria-label={`${activity.activity_name} 수정`}>수정</button><button className="delete-activity" onClick={() => { setActivities((current) => current.filter((item) => item.activity_id !== activity.activity_id)); setRecommendations((current) => current.filter((item) => item.activity_id !== activity.activity_id)); }} aria-label={`${activity.activity_name} 삭제`}>삭제</button></div></article>)}</div> : <p className="empty-result">등록된 활동이 없습니다. + 버튼으로 활동을 추가하세요.</p>}</section>
      <section className="recommend-action"><span>✦</span><p>{courses.length ? "월요일부터 금요일까지" : "시간표 없이도 테스트 가능"}</p><h2>빈 시간을 한 번에<br/>채워드릴게요.</h2><button onClick={recommend} disabled={busy || !activities.length}>{busy ? "추천 중..." : "활동 추천받기"} →</button></section></section>
      {!courses.length && <p className="simulation-notice">현재 적용된 학기 시간표가 없어 월–금 08:00~22:00를 빈 시간으로 사용합니다. 활동을 등록하면 추천·비효율 모드·회복 점수를 모두 시험할 수 있어요.</p>}
      <section className="inefficiency-panel">
        <div className="inefficiency-settings">
          <div className="mode-title"><div><p className="eyebrow">MANUAL SETTINGS</p><h2>비효율 모드</h2></div><label className="mode-switch"><input type="checkbox" checked={inefficiencyEnabled} onChange={(event) => setInefficiencyEnabled(event.target.checked)}/><span/></label></div>
          <p>앞으로 활동을 어떻게 추천할지 직접 설정해요. 점수 계산과는 독립적으로 작동합니다.</p>
          <fieldset disabled={!inefficiencyEnabled}><legend>일정 밀도</legend><div className="percent-buttons">{[100,75,50,25,0].map((value) => <button type="button" className={targetDensity === value ? "active" : ""} key={value} onClick={() => setTargetDensity(value)}>{value}%</button>)}</div><legend>이번 주 컨디션</legend><small>{({100:"매우 좋음",75:"좋음",50:"보통",25:"피곤함",0:"매우 피곤함"} as Record<number,string>)[weeklyCondition]}</small><div className="percent-buttons">{[100,75,50,25,0].map((value) => <button type="button" className={weeklyCondition === value ? "active" : ""} key={value} onClick={() => setWeeklyCondition(value)}>{value}%</button>)}</div><label className="recovery-check"><input type="checkbox" checked={autoRecovery} onChange={(event) => setAutoRecovery(event.target.checked)}/> 회복 시간 자동 확보</label></fieldset>
          <button className="reapply-button" onClick={recommend} disabled={!inefficiencyEnabled || busy || !activities.length}>{busy ? "다시 추천 중..." : "비효율 모드 적용하여 다시 추천"}</button>
        </div>
        <div className="recovery-result">
          <p className="eyebrow">AUTOMATIC ANALYSIS</p><h2>회복 점수</h2>
          {recoveryAnalysis ? <><div className="recovery-visual"><img src={`/recovery/grade-${recoveryAnalysis.grade}.png`} alt={`${recoveryAnalysis.grade}등급 회복 상태`}/><div className="score-number"><b>{recoveryAnalysis.score}</b><span>점</span></div></div><button className="close-score-button" onClick={() => { setRecoveryAnalysis(null); setShowRecoveryDetails(false); }}>회복 점수 닫기</button></> : <><p className="recovery-placeholder">현재 플래너를 기준으로 원할 때 회복 점수를 계산할 수 있어요.</p><button className="calculate-score-button" onClick={calculateRecovery} disabled={busy}>{busy ? "계산 중..." : "회복 점수 계산하기"}</button></>}
          <button className="score-detail-button" onClick={() => setShowRecoveryDetails(!showRecoveryDetails)}>{showRecoveryDetails ? "회복 점수 설명 닫기" : "회복 점수란? · 계산 방법 보기"}</button>
          {showRecoveryDetails && <div className="score-details"><h3>회복 점수란?</h3><p>현재 시간표에 수업 사이 여유와 회복 가능한 시간이 얼마나 있는지를 100점으로 보여주는 지표예요. 의료적 판단이나 건강 진단을 의미하지 않습니다.</p><h3>어떻게 계산하나요?</h3><ul><li>휴식·공강 시간 <b>최대 40점</b></li><li>하루 일정 밀도 <b>최대 25점</b></li><li>가장 긴 연속 집중 시간 <b>최대 20점</b></li><li>휴식·취미·친구·회복 시간 <b>최대 15점</b></li></ul>{recoveryAnalysis ? <><h3>현재 점수</h3><ul><li>휴식 시간 <b>{recoveryAnalysis.score_details.rest_time_score} / 40</b></li><li>일정 밀도 <b>{recoveryAnalysis.score_details.schedule_density_score} / 25</b></li><li>연속 집중 시간 <b>{recoveryAnalysis.score_details.continuous_focus_score} / 20</b></li><li>회복 활동 <b>{recoveryAnalysis.score_details.recovery_activity_score} / 15</b></li></ul><p>현재 반영: 공강 {recoveryAnalysis.total_rest_minutes}분 · 일정 밀도 {recoveryAnalysis.schedule_density_percent}% · 최장 연속 일정 {recoveryAnalysis.longest_continuous_focus_minutes}분</p>{recoveryAnalysis.reasons.map((reason) => <small key={reason}>{reason}</small>)}{recoveryAnalysis.suggestions.map((suggestion) => <small className="suggestion" key={suggestion}>{suggestion}</small>)}</> : <small>학기 시간표를 적용하면 여기에 현재 점수의 세부 계산 결과가 표시됩니다.</small>}</div>}
        </div>
      </section>
      <section className="planner-shell"><div className="planner-toolbar"><div><p className="eyebrow">WEEK AT A GLANCE</p><h2>빈 시간 채우기</h2></div></div>{message && <p className="planner-message">{message}</p>}{plannerBoard}</section>
    </>}

    {view === "semester" && <section className="standalone-page"><div className="section-title"><div><p className="eyebrow">SEMESTER PLANNER</p><h1>학기 시간표 추천</h1></div><a href="/admin">강의 목록 가져오기 →</a></div><div className="semester-grid"><form className="panel" onSubmit={generateTimetables}><fieldset className="timetable-checklist"><legend>시간표 체크리스트</legend><label>희망 첫 수업 시작 시간<select value={firstClassStart} onChange={(event) => setFirstClassStart(event.target.value)}><option value="">상관없음</option>{[9,10,11,12,13].map((hour) => <option key={hour} value={hour}>{hour}:00 이후</option>)}</select></label><label className="check">점심시간 확보<input type="checkbox" checked={wantsLunch} onChange={(event) => setWantsLunch(event.target.checked)}/></label><label className="check">저녁시간 확보<input type="checkbox" checked={wantsDinner} onChange={(event) => setWantsDinner(event.target.checked)}/></label><label>원하는 공강 요일<select value={freeDay} onChange={(event) => setFreeDay(event.target.value)}>{["월","화","수","목","금"].map((item) => <option key={item}>{item}</option>)}</select></label><label>최대 연강<select value={maxConsecutiveClasses} onChange={(event) => setMaxConsecutiveClasses(event.target.value)}><option value="">상관없음</option>{[1,2,3,4].map((count) => <option key={count} value={count}>{count}연강</option>)}</select></label><label>이동 시간<select value={travelMinutes} onChange={(event) => setTravelMinutes(event.target.value)}><option value="">상관없음</option>{[10,20,30,60].map((minutes) => <option key={minutes} value={minutes}>{minutes}분</option>)}</select></label><label>하루 최대 수업<select value={maxDailyClasses} onChange={(event) => setMaxDailyClasses(event.target.value)}><option value="">상관없음</option>{[2,3,4,5,6].map((count) => <option key={count} value={count}>{count}개</option>)}</select></label><label>희망 하교 시간<select value={endTime} onChange={(event) => setEndTime(event.target.value)}><option value="">상관없음</option>{[15,16,17,18,19,20].map((hour) => <option key={hour} value={hour}>{hour}:00 이전</option>)}</select></label></fieldset><button className="primary">12학점 시간표 만들기</button></form><div className="semester-results">{timetableMessage && <p className="error">{timetableMessage}</p>}{!timetables.length && !timetableMessage && <p className="empty-result">조건을 설정하면 추천 시간표가 여기에 표시됩니다.</p>}{timetables.map((table) => <article className="panel" key={`${table.title}-${table.score}`}><p className="eyebrow">{table.title}</p><h3>{table.total_credits}학점 · 점수 {table.score}</h3>{table.courses.map((course) => <div className="catalog-course" key={`${course.code}-${course.instructor}`}><b>{course.name}</b><span>{course.meetings.map((meeting) => `${meeting.day} ${meeting.start}:00–${meeting.end}:00`).join(" · ")}</span></div>)}<button className="apply-button" onClick={() => applyTimetable(table)}>이 시간표 적용</button></article>)}</div></div></section>}

    {view === "all" && <section className="standalone-page"><div className="section-title"><div><p className="eyebrow">ALL SCHEDULES</p><h1>전체 시간표 보기</h1></div></div><div className="share-tools"><section><p className="eyebrow">EXPORT</p><h2>시간표 내보내기</h2><p>현재 시간표를 DB에 저장하고 복원 코드를 발급합니다.</p><button onClick={exportTimetable} disabled={!courses.length}>내보내기</button>{shareCode && <div className="share-code"><span>{shareCode}</span><button onClick={() => navigator.clipboard.writeText(shareCode)}>복사</button></div>}</section><form onSubmit={importTimetable}><p className="eyebrow">IMPORT</p><h2>시간표 불러오기</h2><p>이전에 발급받은 코드를 입력하세요.</p><div><input required maxLength={8} value={importCode} onChange={(event) => setImportCode(event.target.value.toUpperCase())} placeholder="8자리 코드"/><button>불러오기</button></div></form></div>{shareMessage && <p className="planner-message">{shareMessage}</p>}{plannerBoard}</section>}

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
