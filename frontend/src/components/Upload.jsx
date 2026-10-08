import { useEffect, useRef, useState } from "react";
import axios from "axios";
import "../css/Upload.css";
import VideoPlayer from "./VideoPlayer";
import useJobEvents from "../hooks/useJobEvents";
import { API_URL } from "../config";

const DEFAULT_CFG = {
  max_upload_mb: 50,
  extensions: [".pptx", ".ppt", ".ppsx", ".odp", ".pdf"],
  languages: [["en", "English"], ["hi", "Hindi"], ["mr", "Marathi"],
              ["es", "Spanish"], ["fr", "French"], ["de", "German"]],
};
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
  const [cfg, setCfg] = useState(DEFAULT_CFG);
  const [file, setFile] = useState(null);
  const [language, setLanguage] = useState("en");
  const [scriptMode, setScriptMode] = useState("auto");
  const [dragActive, setDragActive] = useState(false);
  const [phase, setPhase] = useState("idle"); // idle | uploading | processing | done | error
  const [uploadPct, setUploadPct] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  const { job, connectionError } = useJobEvents(jobId);
  const busy = phase === "uploading" || phase === "processing";

  // Ask the backend for its limits so the UI never disagrees with the server
  useEffect(() => {
    axios.get(`${API_URL}/api/config`).then(({ data }) => setCfg(data)).catch(() => {});
  }, []);

  // React to live job updates
  useEffect(() => {
    if (!job) return;
    if (job.status === "done") setPhase("done");
    else if (job.status === "failed") {
      setError(job.error || "Processing failed.");
      setPhase("error");
    }
  }, [job]);

  useEffect(() => {
    if (connectionError) {
      setError(connectionError);
      setPhase("error");
    }
  }, [connectionError]);

  const pickFile = (f) => {
    if (!f || busy) return;
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!cfg.extensions.includes(ext)) return setError(`Unsupported file type. Use ${cfg.extensions.join(", ")}`);
    if (f.size > cfg.max_upload_mb * 1024 * 1024) return setError(`File is too large (max ${cfg.max_upload_mb} MB).`);
    setError("");
    setFile(f);
    setPhase("idle");
    setJobId(null);
  };

  const handleSubmit = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("language", language);
    form.append("script_mode", scriptMode);

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("uploading");
    setUploadPct(0);
    setError("");
    try {
      // Don't set Content-Type manually: the browser must add the multipart boundary
      const { data } = await axios.post(`${API_URL}/api/jobs`, form, {
        signal: controller.signal,
        onUploadProgress: (e) => e.total && setUploadPct(Math.round((e.loaded * 100) / e.total)),
      });
      if (controller.signal.aborted) {
        // User hit Cancel just as the server accepted the file: cancel that job too
        axios.delete(`${API_URL}/api/jobs/${data.job_id}`).catch(() => {});
        return;
      }
      setPhase("processing");
      setJobId(data.job_id);
    } catch (e) {
      if (axios.isCancel(e)) return;           // reset() already cleaned the screen
      setError(e.response?.data?.detail || "Could not reach the server. Please try again.");
      setPhase("error");
    }
  };

  const reset = () => {
    abortRef.current?.abort();
    if (jobId) axios.delete(`${API_URL}/api/jobs/${jobId}`).catch(() => {});
    setFile(null); setJobId(null); setError(""); setPhase("idle"); setUploadPct(0);
  };

  const progress = phase === "uploading" ? uploadPct : job?.progress ?? 0;
  let label;
  if (phase === "uploading") label = uploadPct >= 100 ? "Finishing upload…" : `Uploading… ${uploadPct}%`;
  else if (job?.status === "queued")
    label = job.queue_position > 1 ? `Waiting in queue (position ${job.queue_position})…` : STAGES.queued;
  else label = STAGES[job?.stage] ?? "Starting…";
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
        <p>{file ? `Selected: ${file.name}` : `Drag and drop a presentation here, or click to browse (${cfg.extensions.join(", ")})`}</p>
        <input
          type="file"
          aria-label="Choose a presentation file"
          accept={cfg.extensions.join(",")}
          className="file-input"
          disabled={busy}
          onChange={(e) => { pickFile(e.target.files[0]); e.target.value = ""; }}
        />
      </div>

      <div className="options">
        <label>Language
          <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={busy}>
            {cfg.languages.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
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
          <div className="progress-bar" role="progressbar"
               aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress" style={{ width: `${progress}%` }} />
          </div>
          <p className="status-text">{label}</p>
        </>
      )}

      {phase === "done" && job && (
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