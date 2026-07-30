"use client";

import { ChangeEvent, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const requiredColumns = ["\ud559\ub144", "\uad50\uacfc\ubaa9\uba85(\ubbf8\ud655\uc815\uad6c\ubd84)", "\uad50\uacfc\ubaa9\ubc88\ud638", "\ubd84\ubc18", "\ud559\uc810", "\uad50\uc218\uba85", "\uc2dc\uac04", "\uac1c\uc124\ud559\uacfc"];
type ImportResult = { imported_count: number; skipped_rows: number[]; message: string };

export default function AdminCatalogPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  function selectFile(event: ChangeEvent<HTMLInputElement>) { setFile(event.target.files?.[0] ?? null); setResult(null); setError(""); }
  async function upload() {
    if (!file) return;
    setLoading(true); setError("");
    try {
      const formData = new FormData(); formData.append("file", file);
      const response = await fetch(`${apiBase}/api/v1/admin/course-catalog/import`, { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Import failed.");
      setResult(data);
    } catch (uploadError) { setError(uploadError instanceof Error ? uploadError.message : "Unable to upload the file."); } finally { setLoading(false); }
  }
  return <main className="admin-page"><a className="back-link" href="/">← Back to timetable</a><section className="admin-heading"><p className="eyebrow">ADMIN · COURSE CATALOG</p><h1>Import course catalog</h1><p>Validate an Excel file and replace the course catalog used by the timetable generator.</p></section><section className="admin-grid"><article className="card upload-card"><h2>Excel upload</h2><label className="file-input"><input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={selectFile} /><span>{file ? file.name : "Choose .xlsx file"}</span></label><p className="hint">Only .xlsx files up to 10MB are supported.</p><button type="button" disabled={!file || loading} onClick={upload}>{loading ? "Saving data..." : "Save to course catalog DB"}</button>{error && <p className="error">{error}</p>}{result && <div className="import-result"><strong>{result.message}</strong><p>{result.imported_count} courses saved.</p>{result.skipped_rows.length > 0 && <p>Skipped rows: {result.skipped_rows.join(", ")}</p>}</div>}</article><article className="card"><h2>Required column names</h2><p className="hint">The first row is read as headers; column order does not matter.</p><ul className="column-list">{requiredColumns.map((column) => <li key={column}>{column}</li>)}</ul><p className="hint">Optional: `이수구분` or `교과구분` is stored as the course category.</p></article></section></main>;
}
