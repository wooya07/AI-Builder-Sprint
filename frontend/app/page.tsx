"use client";

import { FormEvent, useMemo, useState } from "react";

type Day = "MON" | "TUE" | "WED" | "THU" | "FRI";
type Course = { course_id: string; course_name: string; day: Day; start_time: string; end_time: string; location: { building: string; room: string } };
type Activity = {
  activity_id: string; category: string; activity_name: string; priority: "REQUIRED" | "OPTIONAL";
  schedule_type: "FIXED_DAY" | "FLEXIBLE_DAY"; duration_minutes: number; frequency_per_week: number | null;
  completed_count_this_week: number; preferred_days: Day[];
  preferred_time_range: { start_time: string; end_time: string } | null;
};
type Slot = { day: Day; slot_type: "BETWEEN_CLASSES" | "AFTER_CLASSES"; start_time: string; end_time: string; duration_minutes: number };
type Recommendation = { activity_id: string; activity_name: string; category: string; slot_type: string; start_time: string; end_time: string; duration_minutes: number; reason: string; status: string };
type CatalogCourse = { code: string; name: string; credits: number; instructor: string; meetings: { day: string; start: number; end: number }[] };
type Timetable = { title: string; score: number; reasons: string[]; courses: CatalogCourse[]; total_credits: number };

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const days: { value: Day; label: string; date: number }[] = [
  { value: "MON", label: "월", date: 7 }, { value: "TUE", label: "화", date: 8 },
  { value: "WED", label: "수", date: 9 }, { value: "THU", label: "목", date: 10 },
  { value: "FRI", label: "금", date: 11 },
];
const categories = [
  ["STUDY", "개인 공부", "✎"], ["EXERCISE", "운동", "●"], ["HOBBY", "취미 생활", "✦"],
  ["PART_TIME_JOB", "알바", "₩"], ["REST", "휴식", "☁"], ["SOCIAL", "친구", "☺"], ["OTHER", "기타", "+"],
];
const categoryMap = Object.fromEntries(categories.map(([value, label]) => [value, label]));
const iconMap = Object.fromEntries(categories.map(([value, , icon]) => [value, icon]));
const initialCourses: Course[] = [];
const initialActivities: Activity[] = [];

function durationLabel(minutes: number) {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  return `${hours ? `${hours}시간` : ""}${hours && rest ? " " : ""}${rest ? `${rest}분` : ""}` || "0분";
}

export default function Home() {
  const [day, setDay] = useState<Day>("MON");
  const [courses, setCourses] = useState(initialCourses);
  const [activities, setActivities] = useState(initialActivities);
  const [dayEnd, setDayEnd] = useState("22:00");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<"course" | "activity" | null>(null);
  const [step, setStep] = useState(1);
  const [courseDraft, setCourseDraft] = useState({ name: "", start: "09:00", end: "10:30", building: "", room: "" });
  const [activityDraft, setActivityDraft] = useState({ category: "", name: "", priority: "REQUIRED" as "REQUIRED" | "OPTIONAL", duration: 60, useWeeklyPlan: true, frequency: 2, fixed: true, preferredDays: ["MON"] as Day[], preferred: true, preferredStart: "17:00", preferredEnd: "21:00" });
  const [freeDay, setFreeDay] = useState("금");
  const [avoidMorning, setAvoidMorning] = useState(true);
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [timetableMessage, setTimetableMessage] = useState("");

  const dayCourses = useMemo(() => courses.filter((item) => item.day === day).sort((a, b) => a.start_time.localeCompare(b.start_time)), [courses, day]);

  async function recommend() {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/activities/recommend`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), day, timezone: "Asia/Seoul", day_end_time: dayEnd, classes: courses, activities }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "추천을 만들지 못했습니다.");
      setSlots(data.available_slots); setRecommendations(data.recommendations);
      setMessage(`${data.source === "SOLAR" ? "Solar" : "스마트 배치"}가 ${data.recommendations.length}개의 일정을 찾았습니다.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
    finally { setBusy(false); }
  }

  function saveCourse(event: FormEvent) {
    event.preventDefault();
    setCourses((current) => [...current, { course_id: `course-${Date.now()}`, course_name: courseDraft.name, day, start_time: courseDraft.start, end_time: courseDraft.end, location: { building: courseDraft.building, room: courseDraft.room } }]);
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
    setModal(null); setStep(1); setActivityDraft({ category: "", name: "", priority: "REQUIRED", duration: 60, useWeeklyPlan: true, frequency: 2, fixed: true, preferredDays: ["MON"], preferred: true, preferredStart: "17:00", preferredEnd: "21:00" });
  }

  async function generateTimetables(event: FormEvent) {
    event.preventDefault();
    setTimetableMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/timetables/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_credits: 12, required_course_codes: [], preferred_free_day: freeDay, avoid_morning: avoidMorning, max_results: 3 }),
      });
      if (!response.ok) throw new Error("시간표를 생성하지 못했습니다.");
      setTimetables((await response.json()).timetables);
    } catch (error) { setTimetableMessage(error instanceof Error ? error.message : "서버에 연결할 수 없습니다."); }
  }

  return <main>
    <header><a className="logo" href="#"><b>틈</b><span>공강을 나답게</span></a><nav><a className="active">오늘</a><a href="#schedule">시간표</a><a href="#activities">활동</a></nav><div className="profile" aria-label="사용자">●</div></header>
    <section className="hero"><div><p className="eyebrow">TODAY</p><h1>오늘의 빈틈,<br/><em>어떻게 채워볼까요?</em></h1><p>수업 사이와 하교 후 시간을 살펴보고<br/>꼭 맞는 활동만 골라 추천해 드릴게요.</p></div><div className="orbit"><span>☀</span><small>등록한 활동<br/><b>{activities.length}개</b></small></div></section>
    <section className="weekly-wrap" aria-label="주간 시간표">
      <div className="weekly-heading"><div><p className="eyebrow">WEEK AT A GLANCE</p><h2>이번 주 시간표</h2></div><p>추천받을 요일의 머리글을 눌러 선택하세요.</p></div>
      <div className="weekly-scroll"><div className="weekly-board">{days.map((item) => {
        const columnCourses = courses.filter((course) => course.day === item.value).sort((a, b) => a.start_time.localeCompare(b.start_time));
        return <section className={`day-column ${day === item.value ? "current" : ""}`} key={item.value}>
          <button className="day-header" onClick={() => { setDay(item.value); setSlots([]); setRecommendations([]); }}><span>{item.label}요일</span><b>{item.date}</b>{day === item.value && <i>추천 기준</i>}</button>
          <div className="day-classes">{columnCourses.length ? columnCourses.map((course) => <article key={course.course_id}><time>{course.start_time}<small>{course.end_time}</small></time><div><b>{course.course_name}</b><span>{course.location.building} {course.location.room}</span></div></article>) : <p>수업 없음</p>}</div>
        </section>;
      })}</div></div>
    </section>

    <section className="dashboard">
      <section id="schedule" className="panel schedule">
        <div className="section-title"><div><p className="eyebrow">TODAY&apos;S FLOW</p><h2>오늘의 흐름</h2></div><button className="link-button" onClick={() => setModal("course")}>+ 수업 추가</button></div>
        <div className="timeline">{dayCourses.length ? dayCourses.map((course) => {
          const gap = slots.find((item) => item.start_time === course.end_time);
          return <div key={course.course_id}><article className="course"><time>{course.start_time}</time><div><b>{course.course_name}</b><small>{course.location.building} {course.location.room}</small></div><button aria-label="수업 삭제" onClick={() => setCourses((current) => current.filter((item) => item.course_id !== course.course_id))}>×</button></article>{gap && <div className={`gap ${gap.slot_type === "AFTER_CLASSES" ? "after" : ""}`}><span>{gap.slot_type === "AFTER_CLASSES" ? "하교 후" : "공강"}</span><b>{gap.start_time} — {gap.end_time}</b><small>{durationLabel(gap.duration_minutes)}의 여유</small></div>}</div>;
        }) : <div className="empty"><b>수업이 없는 날이에요</b><span>수업을 추가하면 빈 시간을 계산해 드려요.</span></div>}</div>
        <label className="day-end">하루 마감 시간 <input type="time" value={dayEnd} onChange={(event) => setDayEnd(event.target.value)}/></label>
      </section>

      <aside>
        <section className="recommend-card"><i>✦</i><p>오늘의 빈틈에 맞춰</p><h2>나만의 활동을<br/>추천받아 보세요</h2><button onClick={recommend} disabled={busy || !dayCourses.length}>{busy ? "찾는 중..." : "활동 추천받기"} <span>→</span></button></section>
        <section id="activities" className="panel activities"><div className="section-title"><div><p className="eyebrow">MY ACTIVITIES</p><h3>등록한 활동</h3></div><button className="add" onClick={() => setModal("activity")}>+</button></div>{activities.map((activity) => <article key={activity.activity_id}><span className="activity-icon">{iconMap[activity.category]}</span><div><b>{activity.activity_name}</b><small>{categoryMap[activity.category]} · {activity.frequency_per_week ? `주 ${activity.frequency_per_week}회` : "요일·횟수 자유"} · {durationLabel(activity.duration_minutes)}</small></div><i>{activity.priority === "REQUIRED" ? "꼭" : "선택"}</i></article>)}</section>
      </aside>
    </section>

    {(message || recommendations.length > 0) && <section className="recommendations"><div className="section-title"><div><p className="eyebrow">SMART PICKS</p><h2>추천 일정</h2></div><span>{message}</span></div><div className="recommend-grid">{recommendations.map((item) => <article key={`${item.activity_id}-${item.start_time}`}><div><span className="activity-icon">{iconMap[item.category]}</span><i>{item.slot_type === "AFTER_CLASSES" ? "하교 후 추천" : "공강 추천"}</i></div><h3>{item.activity_name}</h3><strong>{item.start_time} — {item.end_time}</strong><p>{item.reason}</p><button onClick={() => setMessage(`${item.activity_name} 일정을 선택했습니다.`)}>이 일정 선택</button></article>)}</div></section>}

    <section className="semester-builder">
      <div className="section-title"><div><p className="eyebrow">SEMESTER PLANNER</p><h2>학기 시간표 추천</h2></div><a href="/admin">강의 목록 가져오기 →</a></div>
      <div className="semester-grid"><form className="panel" onSubmit={generateTimetables}><label>선호 공강 요일<select value={freeDay} onChange={(event) => setFreeDay(event.target.value)}>{["월","화","수","목","금"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="check"><input type="checkbox" checked={avoidMorning} onChange={(event) => setAvoidMorning(event.target.checked)}/> 오전 수업 피하기</label><button className="primary">12학점 시간표 만들기</button></form><div className="semester-results">{timetableMessage && <p className="error">{timetableMessage}</p>}{!timetables.length && !timetableMessage && <p className="empty-result">기존 시간표 생성 기능도 이곳에서 계속 사용할 수 있습니다.</p>}{timetables.map((table) => <article className="panel" key={`${table.title}-${table.score}`}><p className="eyebrow">{table.title}</p><h3>{table.total_credits}학점 · 점수 {table.score}</h3>{table.courses.map((course) => <div className="catalog-course" key={`${course.code}-${course.instructor}`}><b>{course.name}</b><span>{course.meetings.map((meeting) => `${meeting.day} ${meeting.start}:00–${meeting.end}:00`).join(" · ")}</span></div>)}</article>)}</div></div>
    </section>

    {modal && <div className="backdrop" onMouseDown={() => setModal(null)}><section className="modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><button className="close" onClick={() => setModal(null)}>×</button>
      {modal === "course" ? <form onSubmit={saveCourse}><p className="eyebrow">{days.find((item) => item.value === day)?.label}요일</p><h2>수업 추가하기</h2><label>수업명<input required value={courseDraft.name} onChange={(event) => setCourseDraft({ ...courseDraft, name: event.target.value })}/></label><div className="two"><label>시작<input type="time" value={courseDraft.start} onChange={(event) => setCourseDraft({ ...courseDraft, start: event.target.value })}/></label><label>종료<input type="time" value={courseDraft.end} onChange={(event) => setCourseDraft({ ...courseDraft, end: event.target.value })}/></label></div><div className="two"><label>건물<input value={courseDraft.building} onChange={(event) => setCourseDraft({ ...courseDraft, building: event.target.value })}/></label><label>강의실<input value={courseDraft.room} onChange={(event) => setCourseDraft({ ...courseDraft, room: event.target.value })}/></label></div><button className="primary">추가하기</button></form>
      : <><p className="eyebrow">STEP {step} OF 3</p><h2>{step === 1 ? "어떤 활동을 하고 싶나요?" : step === 2 ? "얼마나 자주 할까요?" : "언제가 가장 좋나요?"}</h2><div className="progress"><span style={{ width: `${step * 33.33}%` }}/></div>
        {step === 1 && <><div className="category-grid">{categories.map(([value, label, icon]) => <button key={value} className={activityDraft.category === value ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, category: value })}><span>{icon}</span>{label}</button>)}</div>{activityDraft.category && <label>활동명<input autoFocus value={activityDraft.name} onChange={(event) => setActivityDraft({ ...activityDraft, name: event.target.value })} placeholder="활동명을 입력하세요"/></label>}</>}
        {step === 2 && <><div className="choices"><button className={activityDraft.priority === "REQUIRED" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "REQUIRED" })}><b>꼭 해야 해요</b><small>먼저 자리를 찾아요</small></button><button className={activityDraft.priority === "OPTIONAL" ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, priority: "OPTIONAL" })}><b>가능하면 하고 싶어요</b><small>여유가 있을 때 추천해요</small></button></div><label>한 번에 필요한 시간 <b>{durationLabel(activityDraft.duration)}</b><input type="range" min="0" max="180" step="15" value={activityDraft.duration} onChange={(event) => setActivityDraft({ ...activityDraft, duration: Number(event.target.value) })}/></label></>}
        {step === 3 && <><label className="switch"><span>요일과 주간 횟수를 설정할게요</span><input type="checkbox" checked={activityDraft.useWeeklyPlan} onChange={(event) => setActivityDraft({ ...activityDraft, useWeeklyPlan: event.target.checked })}/></label>{activityDraft.useWeeklyPlan && <><label>주간 횟수<input type="number" min="1" max="7" value={activityDraft.frequency} onChange={(event) => setActivityDraft({ ...activityDraft, frequency: Number(event.target.value) })}/></label><label className="switch"><span>특정 요일을 정할게요</span><input type="checkbox" checked={activityDraft.fixed} onChange={(event) => setActivityDraft({ ...activityDraft, fixed: event.target.checked })}/></label>{activityDraft.fixed && <div className="day-pills">{days.map((item) => <button key={item.value} className={activityDraft.preferredDays.includes(item.value) ? "selected" : ""} onClick={() => setActivityDraft({ ...activityDraft, preferredDays: activityDraft.preferredDays.includes(item.value) ? activityDraft.preferredDays.filter((value) => value !== item.value) : [...activityDraft.preferredDays, item.value] })}>{item.label}</button>)}</div>}</>}<label className="switch"><span>선호 시간대가 있어요</span><input type="checkbox" checked={activityDraft.preferred} onChange={(event) => setActivityDraft({ ...activityDraft, preferred: event.target.checked })}/></label>{activityDraft.preferred && <div className="two"><label>시작<input type="time" value={activityDraft.preferredStart} onChange={(event) => setActivityDraft({ ...activityDraft, preferredStart: event.target.value })}/></label><label>종료<input type="time" value={activityDraft.preferredEnd} onChange={(event) => setActivityDraft({ ...activityDraft, preferredEnd: event.target.value })}/></label></div>}</>}
        <div className="modal-actions">{step > 1 && <button className="secondary" onClick={() => setStep(step - 1)}>이전</button>}<button className="primary" disabled={(step === 1 && (!activityDraft.category || !activityDraft.name)) || (step === 2 && activityDraft.duration < 15)} onClick={() => step < 3 ? setStep(step + 1) : saveActivity()}>{step < 3 ? "다음" : "저장"}</button></div></>}
    </section></div>}
  </main>;
}
