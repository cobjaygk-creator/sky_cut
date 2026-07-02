import React, { FormEvent, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type View = "login" | "register" | "dashboard";
type VideoStatus = "uploaded" | "extracting_audio" | "audio_extracted" | "failed";

type User = {
  id: number;
  email: string;
  created_at: string;
};

type Video = {
  id: number;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  file_size: number;
  status: VideoStatus;
  audio_path: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

type VideoStatusResponse = Pick<Video, "id" | "status" | "audio_path" | "error_message" | "updated_at">;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "new_cut_access_token";

function App() {
  const [view, setView] = useState<View>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    loadCurrentUser(token);
  }, []);

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Request failed.";
      throw new Error(detail);
    }
    return data as T;
  }

  async function authorizedRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) throw new Error("Login is required.");
    return request<T>(path, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
  }

  async function uploadRequest<T>(path: string, body: FormData): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) throw new Error("Login is required.");
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "Upload failed.";
      throw new Error(detail);
    }
    return data as T;
  }

  async function loadVideos() {
    const list = await authorizedRequest<Video[]>("/videos");
    setVideos(list);
  }

  async function loadCurrentUser(token: string) {
    try {
      const me = await request<User>("/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUser(me);
      setView("dashboard");
      setMessage("");
      await loadVideos();
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
      setVideos([]);
      setView("login");
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setMessage("");
    try {
      const data = await request<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      await loadCurrentUser(data.access_token);
      setEmail("");
      setPassword("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setMessage("");
    try {
      await request<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setMessage("Account created. Please log in.");
      setView("login");
      setPassword("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setUploadMessage("Choose an MP4 file first.");
      return;
    }
    setIsUploading(true);
    setUploadMessage("");
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      await uploadRequest<Video>("/videos/upload", formData);
      setSelectedFile(null);
      setUploadMessage("Upload complete.");
      await loadVideos();
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAnalyze(videoId: number) {
    setAnalyzingId(videoId);
    try {
      const status = await authorizedRequest<VideoStatusResponse>(`/videos/${videoId}/analyze`, {
        method: "POST",
      });
      mergeVideoStatus(status);
    } catch (error) {
      await loadVideos();
      setUploadMessage(error instanceof Error ? error.message : "Audio extraction failed.");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleRefreshStatus(videoId: number) {
    const status = await authorizedRequest<VideoStatusResponse>(`/videos/${videoId}/status`);
    mergeVideoStatus(status);
  }

  function mergeVideoStatus(status: VideoStatusResponse) {
    setVideos((currentVideos) =>
      currentVideos.map((video) => (video.id === status.id ? { ...video, ...status } : video)),
    );
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setVideos([]);
    setSelectedFile(null);
    setView("login");
    setMessage("");
    setUploadMessage("");
  }

  return (
    <main className="app-shell">
      <section className="intro">
        <p className="eyebrow">AI Shorts Creation SaaS</p>
        <h1>New Cut</h1>
        <p>
          Upload long MP4 videos locally, then extract audio for the AI
          transcription workflow that comes next.
        </p>
      </section>

      {view === "dashboard" && user ? (
        <section className="panel dashboard-panel" aria-label="Dashboard">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Dashboard</p>
              <h2>My Videos</h2>
            </div>
            <button className="ghost-button" type="button" onClick={handleLogout}>
              Logout
            </button>
          </div>

          <p className="account-line">Signed in as {user.email}</p>

          <form className="upload-form" onSubmit={handleUpload}>
            <label>
              MP4 video
              <input
                type="file"
                accept="video/mp4,.mp4"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
            {selectedFile ? (
              <p className="file-note">
                Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})
              </p>
            ) : null}
            {uploadMessage ? <p className="form-message">{uploadMessage}</p> : null}
            <button className="primary-button" type="submit" disabled={isUploading}>
              {isUploading ? "Uploading" : "Upload video"}
            </button>
          </form>

          <div className="video-list" aria-label="Uploaded videos">
            {videos.length === 0 ? (
              <p className="muted">No videos uploaded yet.</p>
            ) : (
              videos.map((video) => (
                <article className="video-item" key={video.id}>
                  <div className="video-copy">
                    <h3>{video.original_filename}</h3>
                    <p>{formatBytes(video.file_size)} · {video.created_at}</p>
                    {video.audio_path ? <p>Audio extracted</p> : null}
                    {video.error_message ? <p className="error-text">{video.error_message}</p> : null}
                  </div>
                  <div className="video-actions">
                    <span className={`status-badge status-${video.status}`}>{video.status}</span>
                    <button
                      className="small-button"
                      type="button"
                      onClick={() => handleAnalyze(video.id)}
                      disabled={analyzingId === video.id || video.status === "extracting_audio"}
                    >
                      {analyzingId === video.id ? "Analyzing" : "Analyze"}
                    </button>
                    <button className="small-button ghost-small" type="button" onClick={() => handleRefreshStatus(video.id)}>
                      Refresh
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      ) : (
        <section className="panel" aria-label={view === "login" ? "Login" : "Register"}>
          <p className="eyebrow">{view === "login" ? "Login" : "Register"}</p>
          <h2>{view === "login" ? "Sign in" : "Create account"}</h2>
          <form className="auth-form" onSubmit={view === "login" ? handleLogin : handleRegister}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={view === "login" ? "current-password" : "new-password"}
                minLength={view === "register" ? 8 : 1}
                required
              />
            </label>
            {message ? <p className="form-message">{message}</p> : null}
            <button className="primary-button" type="submit" disabled={isLoading}>
              {isLoading ? "Please wait" : view === "login" ? "Login" : "Register"}
            </button>
          </form>
          <button
            className="link-button"
            type="button"
            onClick={() => {
              setView(view === "login" ? "register" : "login");
              setMessage("");
            }}
          >
            {view === "login" ? "Create an account" : "Already have an account"}
          </button>
        </section>
      )}
    </main>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
