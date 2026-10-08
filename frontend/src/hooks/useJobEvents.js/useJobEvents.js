import { useEffect, useState } from "react";
import { API_URL } from "../config";

const TERMINAL = ["done", "failed", "cancelled"];

// Opens a Server-Sent Events connection for a job and returns its live state.
export default function useJobEvents(jobId) {
  const [job, setJob] = useState(null);
  const [connectionError, setConnectionError] = useState("");

  useEffect(() => {
    setJob(null);
    setConnectionError("");
    if (!jobId) return;

    const es = new EventSource(`${API_URL}/api/jobs/${jobId}/events`);

    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setJob(data);
      if (TERMINAL.includes(data.status)) es.close();   // otherwise the browser would reconnect
    };
    es.addEventListener("gone", () => {
      setConnectionError("This job expired or was removed. Please upload again.");
      es.close();
    });
    es.onerror = () => {
      // CONNECTING = the browser is retrying by itself. CLOSED = it gave up (e.g. a 404).
      if (es.readyState === EventSource.CLOSED) {
        setConnectionError("Lost connection to the server, or the job expired. Please try again.");
      }
    };

    return () => es.close();   // runs on unmount or when jobId changes
  }, [jobId]);

  return { job, connectionError };
}