"use client";

import { FormEvent, useState } from "react";

type Course = { code: string; name: string; credits: number; instructor: string; meetings: { day: string; start: number; end: number }[] };
type Timetable = { title: string; score: number; reasons: string[]; courses: Course[]; total_credits: number };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const dayOptions = ["\uc6d4", "\ud654", "\uc218", "\ubaa9", "\uae08"];

export default function Home() {
  const [freeDay, setFreeDay] = useState("\uae08");
  const [avoidMorning, setAvoidMorning] = useState(true);
  const [result, setResult] = useState<Timetable[]>([]);
  const [message, setMessage] = useState("");

  async function generate(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/v1/timetables/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_credits: 12, required_course_codes: ["CS201"], preferred_free_day: freeDay, avoid_morning: avoidMorning, max_results: 3 }) });
      if (!response.ok) throw new Error("Unable to generate a timetable.");
      setResult((await response.json()).timetables);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to connect to the server."); }
  }

  return <main>
    <section className="hero"><p className="eyebrow">PERSONAL SEMESTER PLANNER</p><h1>Design your semester,<br />around your life.</h1><p>Build a timetable that considers graduation requirements and personal preferences.</p><a className="back-link" href="/admin">Admin: Import course catalog</a></section>
    <section className="workspace"><form onSubmit={generate} className="card"><h2>Semester preferences</h2><label>Preferred free day<select value={freeDay} onChange={(event) => setFreeDay(event.target.value)}>{dayOptions.map((day) => <option key={day}>{day}</option>)}</select></label><label className="check"><input type="checkbox" checked={avoidMorning} onChange={(event) => setAvoidMorning(event.target.checked)} /> Avoid morning classes</label><button>Generate timetable</button></form><div className="results"><h2>Recommendations</h2>{message && <p className="error">{message}</p>}{!result.length && !message && <p className="empty">Set your preferences to generate a timetable.</p>}{result.map((table) => <article className="card timetable" key={`${table.title}-${table.score}`}><div className="result-title"><span>{table.title}</span><h3>{table.total_credits} credits · Score {table.score}</h3></div><ul>{table.courses.map((course) => <li key={`${course.code}-${course.instructor}`}><strong>{course.name}</strong><span>{course.meetings.map((meeting) => `${meeting.day} ${meeting.start}:00-${meeting.end}:00`).join(" · ")} · {course.instructor}</span></li>)}</ul><div className="reasons">{table.reasons.map((reason) => <p key={reason}>✓ {reason}</p>)}</div></article>)}</div></section>
  </main>;
}
