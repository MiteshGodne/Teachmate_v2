import { useEffect, useRef, useState } from "react";
import axios from "axios";
import "../css/Upload.css";
import VideoPlayer from "./VideoPlayer";
import { API_URL } from "../config";

const MAX_MB = 50;
const ALLOWED = [".pptx", ".ppt", ".ppsx", ".odp", ".pdf"];
const LANGUAGES = [
  ["en", "English"], ["hi", "Hindi"], ["mr", "Marathi"],
  ["es", "Spanish"], ["fr", "French"], ["de", "German"],
];
const SCRIPT_MODES = [
  ["auto", "Speaker notes, else slide text"],
  ["notes", "Speaker notes only"],
  ["slide", "Slide text only"],
];
const STAGES = {
  queued: "Waiting in queue…", validating: "Checking your file…",
  converting: "Converting format…", parsing: "Reading slides…",
  rendering: "Rendering slides…", narrating: "Generating narration…",
  encoding: "Encoding video…", done: "Done!",
};

const Upload = () => {
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState("en");
  const [scriptMode, setScriptMode] = useState("auto");
  const [dragActive, setDragActive] = useState(false);
  const [phase, setPhase] = useState("idle"); // idle | uploading | processing | done | error
  const [uploadPct, setUploadPct] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  const busy = phase === "uploading" || phase === "processing";

  const pickFile = (f) => {
    if (!f) return;
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ALLOWED.includes(ext)) return setError(`Unsupported file type. Use ${ALLOWED.join(", ")}`);
    if (f.size > MAX_MB * 1024 * 1024) return setError(`File is too large (max ${MAX_MB} MB).`);
    setError("");
    setFile(f);
    setPhase("idle");
    setJobId(null);
    setJob(null);
  };

  // Poll job status; the cleanup function stops polling on unmount or new job
  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${API_URL}/api/jobs/${jobId}`);
        if (stopped) return;
        setJob(data);
        if (data.status === "done") return setPhase("done");
        if (data.status === "failed") {
          setError(data.error || "Processing failed.");
          return setPhase("error");
        }
      } catch (e) {
        if (stopped) return;
        if (e.response?.status === 404) {
          setError("This job expired or the server restarted. Please upload again.");
          return setPhase("error");
        }
        // transient network error: keep polling
      }
      timer = setTimeout(poll, 1500);
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [jobId]);

  const handleSubmit = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("language", language);
    form.append("script_mode", scriptMode);

    abortRef.current = new AbortController();
    setPhase("uploading");
    setUploadPct(0);
    setError("");
    try {
      // Don't set Content-Type manually: the browser must add the multipart boundary
      const { data } = await axios.post(`${API_URL}/api/jobs`, form, {
        signal: abortRef.current.signal,
        onUploadProgress: (e) => e.total && setUploadPct(Math.round((e.loaded * 100) / e.total)),
      });
      setPhase("processing");
      setJobId(data.job_id);
    } catch (e) {
      if (axios.isCancel(e)) return setPhase("idle");
      setError(e.response?.data?.detail || "Could not reach the server. Please try again.");
      setPhase("error");
    }
  };

  const reset = () => {
    abortRef.current?.abort();
    if (jobId) axios.delete(`${API_URL}/api/jobs/${jobId}`).catch(() => {});
    setFile(null); setJobId(null); setJob(null); setError(""); setPhase("idle"); setUploadPct(0);
  };

  const progress = phase === "uploading" ? uploadPct : job?.progress ?? 0;
  const label = phase === "uploading" ? `Uploading… ${uploadPct}%` : STAGES[job?.stage] ?? "Starting…";
  const base = `${API_URL}/api/jobs/${jobId}`;

  return (
    <div className="upload-page">
      <h1 className="upload-heading">Upload Your Slides</h1>

      <div
        className={`drag-drop-area ${dragActive ? "active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
        onDrop={(e) => { e.preventDefault(); setDragActive(false); pickFile(e.dataTransfer.files?.[0]); }}
      >
        <p>{file ? `Selected: ${file.name}` : `Drag and drop a presentation here, or click to browse (${ALLOWED.join(", ")})`}</p>
        <input
          type="file"
          accept={ALLOWED.join(",")}
          className="file-input"
          disabled={busy}
          onChange={(e) => { pickFile(e.target.files[0]); e.target.value = ""; }}
        />
      </div>

      <div className="options">
        <label>Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={busy}>
            {LANGUAGES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
        <label>Narration source
          <select value={scriptMode} onChange={(e) => setScriptMode(e.target.value)} disabled={busy}>
            {SCRIPT_MODES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
      </div>

      {error && <div className="error-box" role="alert">{error}</div>}

      {file && (
        <div className="action-buttons">
          <button className="upload-button" onClick={handleSubmit} disabled={busy || phase === "done"}>
            {busy ? "Working…" : "Create video"}
          </button>
          <button className="remove-button" onClick={reset}>{busy ? "Cancel" : "Remove file"}</button>
        </div>
      )}

      {busy && (
        <>
          <div className="progress-bar"><div className="progress" style={{ width: `${progress}%` }} /></div>
          <p className="status-text">{label}</p>
        </>
      )}

      {phase === "done" && (
        <div className="result">
          <h2>Your lecture is ready</h2>
          <p className="status-text">{job.slides} slides · {Math.round(job.duration)}s. Files are deleted after about an hour.</p>
          <VideoPlayer videoUrl={`${base}/video`} />
          <div className="action-buttons">
            <a className="upload-button" href={`${base}/video?download=1`}>Download MP4</a>
            {job.has_subtitles && <a className="upload-button" href={`${base}/subtitles`}>Download subtitles (.srt)</a>}
          </div>
        </div>
      )}
    </div>
  );
};

export default Upload;