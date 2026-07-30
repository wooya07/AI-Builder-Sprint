"use client";

import { FormEvent, useState } from "react";

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
  const [activityDraft, setActivityDraft] = useState({ category: "", name: "", priority: "REQUIRED" as "REQUIRED" | "OPTIONAL", duration: 60, useWeeklyPlan: false, frequency: 2, fixed: false, preferredDays: ["MON"] as Day[], preferred: false, preferredStart: "17:00", preferredEnd: "21:00" });
  const [freeDay, setFreeDay] = useState("금");
  const [avoidMorning, setAvoidMorning] = useState(true);
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [timetableMessage, setTimetableMessage] = useState("");

  async function recommend() {
    setBusy(true); setMessage("");
    try {
      const results = await Promise.all(days.map(async ({ value }) => {
        const response = await fetch(`${apiBase}/api/v1/activities/recommend`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), day: value, timezone: "Asia/Seoul", day_end_time: "22:00", classes: courses, activities }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail ?? "추천을 만들지 못했습니다.");
        return {
          slots: (data.available_slots as Slot[]),
          recommendations: (data.recommendations as Omit<Recommendation, "day">[]).map((item) => ({ ...item, day: value })),
        };
      }));
      const limits = new Map(activities.map((activity) => [activity.activity_id, activity.frequency_per_week ?? 1]));
      const counts = new Map<string, number>();
      const combined = results.flatMap((result) => result.recommendations).filter((item) => {
        const used = counts.get(item.activity_id) ?? 0;
        if (used >= (limits.get(item.activity_id) ?? 1)) return false;
        counts.set(item.activity_id, used + 1);
        return true;
      });
      setRecommendations(combined);
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
    setActivities((current) => [...current, {
      activity_id: `activity-${Date.now()}`, category: activityDraft.category, activity_name: activityDraft.name,
      priority: activityDraft.priority, schedule_type: activityDraft.useWeeklyPlan && activityDraft.fixed ? "FIXED_DAY" : "FLEXIBLE_DAY",
      duration_minutes: activityDraft.duration, frequency_per_week: activityDraft.useWeeklyPlan ? activityDraft.frequency : null,
      completed_count_this_week: 0, preferred_days: activityDraft.useWeeklyPlan && activityDraft.fixed ? activityDraft.preferredDays : [],
      preferred_time_range: activityDraft.preferred ? { start_time: activityDraft.preferredStart, end_time: activityDraft.preferredEnd } : null,
    }]);
    setModal(null); setStep(1);
  }

  async function generateTimetables(event: FormEvent) {
    event.preventDefault(); setTimetableMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/timetables/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_credits: 12, required_course_codes: [], preferred_free_day: freeDay, avoid_morning: avoidMorning, max_results: 3 }),
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
  </div></div>;

  return <main>
    <header><a className="logo" href="#"><b>틈</b><span>공강을 나답게</span></a><nav className="page-nav"><button className={view === "semester" ? "active" : ""} onClick={() => setView("semester")}>학기 시간표 추천</button><button className={view === "week" ? "active" : ""} onClick={() => setView("week")}>이번 주 시간표</button><button className={view === "all" ? "active" : ""} onClick={() => setView("all")}>전체 시간표 보기</button></nav><div className="profile" aria-label="사용자">●</div></header>

    {view === "week" && <><section className="compact-hero"><div><p className="eyebrow">WEEKLY PLANNER</p><h1>이번 주의 빈틈을<br/><em>한눈에 채워보세요.</em></h1></div></section>
      <section className="week-top"><section className="activity-dock"><div className="section-title"><div><p className="eyebrow">MY ACTIVITIES</p><h2>등록한 활동</h2></div><button className="add" onClick={() => setModal("activity")}>+</button></div>{activities.length ? <div className="activity-row">{activities.map((activity) => <article key={activity.activity_id}><span className="activity-icon">{iconMap[activity.category]}</span><div><b>{activity.activity_name}</b><small>{categoryMap[activity.category]} · {activity.frequency_per_week ? `주 ${activity.frequency_per_week}회` : "요일·횟수 자유"} · {durationLabel(activity.duration_minutes)}</small></div><button className="delete-activity" onClick={() => { setActivities((current) => current.filter((item) => item.activity_id !== activity.activity_id)); setRecommendations((current) => current.filter((item) => item.activity_id !== activity.activity_id)); }} aria-label={`${activity.activity_name} 삭제`}>삭제</button></article>)}</div> : <p className="empty-result">등록된 활동이 없습니다. + 버튼으로 활동을 추가하세요.</p>}</section>
      <section className="recommend-action"><span>✦</span><p>월요일부터 금요일까지</p><h2>빈 시간을 한 번에<br/>채워드릴게요.</h2><button onClick={recommend} disabled={busy || !courses.length || !activities.length}>{busy ? "추천 중..." : "활동 추천받기"} →</button></section></section>
      <section className="planner-shell"><div className="planner-toolbar"><div><p className="eyebrow">WEEK AT A GLANCE</p><h2>주간 시간표</h2></div><button onClick={() => setModal("course")}>+ 수업 추가</button></div>{message && <p className="planner-message">{message}</p>}{plannerBoard}</section>
    </>}

    {view === "semester" && <section className="standalone-page"><div className="section-title"><div><p className="eyebrow">SEMESTER PLANNER</p><h1>학기 시간표 추천</h1></div><a href="/admin">강의 목록 가져오기 →</a></div><div className="semester-grid"><form className="panel" onSubmit={generateTimetables}><label>선호 공강 요일<select value={freeDay} onChange={(event) => setFreeDay(event.target.value)}>{["월","화","수","목","금"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="check"><input type="checkbox" checked={avoidMorning} onChange={(event) => setAvoidMorning(event.target.checked)}/> 오전 수업 피하기</label><button className="primary">12학점 시간표 만들기</button></form><div className="semester-results">{timetableMessage && <p className="error">{timetableMessage}</p>}{!timetables.length && !timetableMessage && <p className="empty-result">조건을 설정하면 추천 시간표가 여기에 표시됩니다.</p>}{timetables.map((table) => <article className="panel" key={`${table.title}-${table.score}`}><p className="eyebrow">{table.title}</p><h3>{table.total_credits}학점 · 점수 {table.score}</h3>{table.courses.map((course) => <div className="catalog-course" key={`${course.code}-${course.instructor}`}><b>{course.name}</b><span>{course.meetings.map((meeting) => `${meeting.day} ${meeting.start}:00–${meeting.end}:00`).join(" · ")}</span></div>)}<button className="apply-button" onClick={() => applyTimetable(table)}>이 시간표 적용</button></article>)}</div></div></section>}

    {view === "all" && <section className="standalone-page"><div className="section-title"><div><p className="eyebrow">ALL SCHEDULES</p><h1>전체 시간표 보기</h1></div><button className="link-button" onClick={() => setModal("course")}>+ 수업 추가</button></div>{plannerBoard}</section>}

    {modal && <div className="backdrop" onMouseDown={() => setModal(null)}><section className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><button className="close" onClick={() => setModal(null)}>×</button>
      {modal === "course" ? <form onSubmit={saveCourse}><p className="eyebrow">새 수업</p><h2>수업 추가하기</h2><label>요일<select value={day} onChange={(event) => setDay(event.target.value as Day)}>{days.map((item) => <option value={item.value} key={item.value}>{item.label}요일</option>)}</select></label><label>수업명<input required value={courseDraft.name} onChange={(event) => setCourseDraft({ ...courseDraft, name: event.target.value })}/></label><div className="two"><label>시작<input type="time" value={courseDraft.start} onChange={(event) => setCourseDraft({ ...courseDraft, start: event.target.value })}/></label><label>종료<input type="time" value={courseDraft.end} onChange={(event) => setCourseDraft({ ...courseDraft, end: event.target.value })}/></label></div><div className="two"><label>건물<input value={courseDraft.building} onChange={(event) => setCourseDraft({ ...courseDraft, building: event.target.value })}/></label><label>강의실<input value={courseDraft.room} onChange={(event) => setCourseDraft({ ...courseDraft, room: event.target.value })}/></label></div><button className="primary">추가하기</button></form>
      : <><p className="eyebrow">STEP {step} OF 3</p><h2>{step === 1 ? "어떤 활동을 하고 싶나요?" : step === 2 ? "얼마나 필요할까요?" : "선호 조건이 있나요?"}</h2><div className="progress"><span style={{ width: `${step * 33.33}%` }}/></div>
        {step === 1 && <><div className="category-grid">{categories.map(([value, label, icon]) => <button key={value} className={activityDraft.category === value ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, category: value })}><span>{icon}</span>{label}</button>)}</div>{activityDraft.category && <label>활동명<input autoFocus value={activityDraft.name} onChange={(event) => setActivityDraft({ ...activityDraft, name: event.target.value })} placeholder="활동명을 입력하세요"/></label>}</>}
        {step === 2 && <><div className="choices"><button className={activityDraft.priority === "REQUIRED" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "REQUIRED" })}><b>꼭 해야 해요</b><small>먼저 자리를 찾아요</small></button><button className={activityDraft.priority === "OPTIONAL" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "OPTIONAL" })}><b>가능하면 하고 싶어요</b><small>여유가 있을 때 추천해요</small></button></div><label>한 번에 필요한 시간 <b>{durationLabel(activityDraft.duration)}</b><input type="range" min="0" max="180" step="15" value={activityDraft.duration} onChange={(event) => setActivityDraft({ ...activityDraft, duration: Number(event.target.value) })}/></label></>}
        {step === 3 && <><label className="switch"><span>요일과 주간 횟수를 설정할게요</span><input type="checkbox" checked={activityDraft.useWeeklyPlan} onChange={(event) => setActivityDraft({ ...activityDraft, useWeeklyPlan: event.target.checked })}/></label>{activityDraft.useWeeklyPlan && <><label>주간 횟수<input type="number" min="1" max="7" value={activityDraft.frequency} onChange={(event) => setActivityDraft({ ...activityDraft, frequency: Number(event.target.value) })}/></label><label className="switch"><span>특정 요일을 정할게요</span><input type="checkbox" checked={activityDraft.fixed} onChange={(event) => setActivityDraft({ ...activityDraft, fixed: event.target.checked })}/></label>{activityDraft.fixed && <div className="day-pills">{days.map((item) => <button key={item.value} className={activityDraft.preferredDays.includes(item.value) ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, preferredDays: activityDraft.preferredDays.includes(item.value) ? activityDraft.preferredDays.filter((value) => value !== item.value) : [...activityDraft.preferredDays, item.value] })}>{item.label}</button>)}</div>}</>}<label className="switch"><span>선호 시간대가 있어요</span><input type="checkbox" checked={activityDraft.preferred} onChange={(event) => setActivityDraft({ ...activityDraft, preferred: event.target.checked })}/></label>{activityDraft.preferred && <div className="two"><label>시작<input type="time" value={activityDraft.preferredStart} onChange={(event) => setActivityDraft({ ...activityDraft, preferredStart: event.target.value })}/></label><label>종료<input type="time" value={activityDraft.preferredEnd} onChange={(event) => setActivityDraft({ ...activityDraft, preferredEnd: event.target.value })}/></label></div>}</>}
        <div className="modal-actions">{step > 1 && <button className="secondary" onClick={() => setStep(step - 1)}>이전</button>}<button className="primary" disabled={(step === 1 && (!activityDraft.category || !activityDraft.name)) || (step === 2 && activityDraft.duration < 15)} onClick={() => step < 3 ? setStep(step + 1) : saveActivity()}>{step < 3 ? "다음" : "저장"}</button></div></>}
    </section></div>}
  </main>;
}
