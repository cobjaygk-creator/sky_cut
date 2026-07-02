import React, { FormEvent, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type View = "login" | "register" | "dashboard";
type VideoStatus = "uploaded" | "extracting_audio" | "audio_extracted" | "transcribing" | "transcribed" | "failed";
type ClipStatus = "pending" | "processing" | "completed" | "failed";
type SubtitleStyle = "basic" | "bold" | "shorts";

type User = { id: number; email: string; created_at: string };

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
type TranscriptSegment = { index: number; start: number; end: number; text: string };
type Transcript = {
  id: number;
  video_id: number;
  status: "transcribing" | "transcribed" | "failed";
  text: string | null;
  segments: TranscriptSegment[];
  error_message: string | null;
  created_at: string;
  updated_at: string;
};
type Highlight = {
  id: number;
  video_id: number;
  start_time: number;
  end_time: number;
  title: string;
  reason: string;
  content_type: string;
  score: number;
  created_at: string;
};
type Clip = {
  id: number;
  video_id: number;
  highlight_id: number;
  output_path: string | null;
  subtitle_style: string | null;
  subtitle_path: string | null;
  subtitled_output_path: string | null;
  status: ClipStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "new_cut_access_token";
const SUBTITLE_STYLES: SubtitleStyle[] = ["basic", "bold", "shorts"];

function App() {
  const [view, setView] = useState<View>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [transcripts, setTranscripts] = useState<Record<number, Transcript>>({});
  const [highlights, setHighlights] = useState<Record<number, Highlight[]>>({});
  const [clips, setClips] = useState<Record<number, Clip>>({});
  const [subtitleStyles, setSubtitleStyles] = useState<Record<number, SubtitleStyle>>({});
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [message, setMessage] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isImportingYoutube, setIsImportingYoutube] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const [transcribingId, setTranscribingId] = useState<number | null>(null);
  const [highlightingId, setHighlightingId] = useState<number | null>(null);
  const [creatingClipId, setCreatingClipId] = useState<number | null>(null);
  const [subtitlingClipId, setSubtitlingClipId] = useState<number | null>(null);
  const [downloadingClipId, setDownloadingClipId] = useState<number | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    loadCurrentUser(token);
  }, []);

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
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
    return request<T>(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
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
    setVideos(await authorizedRequest<Video[]>("/videos"));
  }

  async function loadCurrentUser(token: string) {
    try {
      const me = await request<User>("/me", { headers: { Authorization: `Bearer ${token}` } });
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
      await request<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
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
    setYoutubeUrl("");
      setUploadMessage("Upload complete.");
      await loadVideos();
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleImportYoutube(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!youtubeUrl.trim()) {
      setUploadMessage("Enter a YouTube URL first.");
      return;
    }
    setIsImportingYoutube(true);
    setUploadMessage("");
    try {
      await authorizedRequest<Video>("/videos/import-youtube", {
        method: "POST",
        body: JSON.stringify({ url: youtubeUrl.trim() }),
      });
      setYoutubeUrl("");
      setUploadMessage("YouTube video imported.");
      await loadVideos();
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "YouTube import failed.");
    } finally {
      setIsImportingYoutube(false);
    }
  }

  async function handleAnalyze(videoId: number) {
    setAnalyzingId(videoId);
    try {
      mergeVideoStatus(await authorizedRequest<VideoStatusResponse>(`/videos/${videoId}/analyze`, { method: "POST" }));
    } catch (error) {
      await loadVideos();
      setUploadMessage(error instanceof Error ? error.message : "Audio extraction failed.");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleTranscript(videoId: number) {
    setTranscribingId(videoId);
    try {
      const transcript = await authorizedRequest<Transcript>(`/videos/${videoId}/transcript`);
      setTranscripts((current) => ({ ...current, [videoId]: transcript }));
      await loadVideos();
    } catch (error) {
      await loadVideos();
      setUploadMessage(error instanceof Error ? error.message : "Transcription failed.");
    } finally {
      setTranscribingId(null);
    }
  }

  async function handleHighlights(videoId: number) {
    setHighlightingId(videoId);
    try {
      const candidates = await authorizedRequest<Highlight[]>(`/videos/${videoId}/highlights`);
      setHighlights((current) => ({ ...current, [videoId]: candidates }));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Highlight recommendation failed.");
    } finally {
      setHighlightingId(null);
    }
  }

  async function handleCreateClip(highlightId: number) {
    setCreatingClipId(highlightId);
    setUploadMessage("");
    try {
      const clip = await authorizedRequest<Clip>("/clips/create", {
        method: "POST",
        body: JSON.stringify({ highlight_id: highlightId }),
      });
      setClips((current) => ({ ...current, [highlightId]: clip }));
      setSubtitleStyles((current) => ({ ...current, [clip.id]: "basic" }));
      setUploadMessage(clip.status === "completed" ? "Clip created." : `Clip status: ${clip.status}`);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Clip generation failed.");
    } finally {
      setCreatingClipId(null);
    }
  }

  async function handleBurnSubtitles(clip: Clip) {
    const style = subtitleStyles[clip.id] ?? "basic";
    setSubtitlingClipId(clip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<Clip>(`/clips/${clip.id}/subtitles`, {
        method: "POST",
        body: JSON.stringify({ style }),
      });
      setClips((current) => ({ ...current, [updated.highlight_id]: updated }));
      setUploadMessage("Subtitled clip created.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Subtitle burn-in failed.");
    } finally {
      setSubtitlingClipId(null);
    }
  }

  async function handleDownloadClip(clip: Clip) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUploadMessage("Login is required.");
      return;
    }
    setDownloadingClipId(clip.id);
    setUploadMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/clips/${clip.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === "string" ? data.detail : "Download failed.";
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = clip.subtitled_output_path ? `new-cut-subtitled-${clip.id}.mp4` : `new-cut-clip-${clip.id}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "Download failed.");
    } finally {
      setDownloadingClipId(null);
    }
  }

  async function handleRefreshStatus(videoId: number) {
    mergeVideoStatus(await authorizedRequest<VideoStatusResponse>(`/videos/${videoId}/status`));
  }

  function mergeVideoStatus(status: VideoStatusResponse) {
    setVideos((currentVideos) => currentVideos.map((video) => (video.id === status.id ? { ...video, ...status } : video)));
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setVideos([]);
    setTranscripts({});
    setHighlights({});
    setClips({});
    setSubtitleStyles({});
    setSelectedFile(null);
    setYoutubeUrl("");
    setView("login");
    setMessage("");
    setUploadMessage("");
  }

  return (
    <main className="app-shell">
      <section className="intro">
        <p className="eyebrow">AI Shorts Creation SaaS</p>
        <h1>New Cut</h1>
        <p>Upload MP4 videos, transcribe speech, recommend highlights, render vertical clips, and burn in captions.</p>
      </section>

      {view === "dashboard" && user ? (
        <section className="panel dashboard-panel" aria-label="Dashboard">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Dashboard</p>
              <h2>My Videos</h2>
            </div>
            <button className="ghost-button" type="button" onClick={handleLogout}>Logout</button>
          </div>

          <p className="account-line">Signed in as {user.email}</p>

          <form className="upload-form" onSubmit={handleUpload}>
            <label>
              MP4 video
              <input type="file" accept="video/mp4,.mp4" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            </label>
            {selectedFile ? <p className="file-note">Selected: {selectedFile.name} ({formatBytes(selectedFile.size)})</p> : null}
            {uploadMessage ? <p className="form-message">{uploadMessage}</p> : null}
            <button className="primary-button" type="submit" disabled={isUploading}>{isUploading ? "Uploading" : "Upload video"}</button>
          </form>

          <form className="upload-form youtube-form" onSubmit={handleImportYoutube}>
            <label>
              YouTube URL
              <input type="url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
            </label>
            <p className="file-note">Use videos you own or have permission to process.</p>
            <button className="primary-button" type="submit" disabled={isImportingYoutube}>{isImportingYoutube ? "Importing" : "Import YouTube video"}</button>
          </form>

          <div className="video-list" aria-label="Uploaded videos">
            {videos.length === 0 ? <p className="muted">No videos uploaded yet.</p> : videos.map((video) => (
              <article className="video-item" key={video.id}>
                <div className="video-copy">
                  <h3>{video.original_filename}</h3>
                  <p>{formatBytes(video.file_size)} · {video.created_at}</p>
                  {video.audio_path ? <p>Audio extracted</p> : null}
                  {video.error_message ? <p className="error-text">{video.error_message}</p> : null}
                  {transcripts[video.id]?.text ? <p className="transcript-preview">{transcripts[video.id].text}</p> : null}
                  {highlights[video.id]?.length ? (
                    <HighlightList
                      clips={clips}
                      creatingClipId={creatingClipId}
                      downloadingClipId={downloadingClipId}
                      highlights={highlights[video.id]}
                      subtitleStyles={subtitleStyles}
                      subtitlingClipId={subtitlingClipId}
                      onBurnSubtitles={handleBurnSubtitles}
                      onCreateClip={handleCreateClip}
                      onDownloadClip={handleDownloadClip}
                      onStyleChange={(clipId, style) => setSubtitleStyles((current) => ({ ...current, [clipId]: style }))}
                    />
                  ) : null}
                </div>
                <div className="video-actions">
                  <span className={`status-badge status-${video.status}`}>{video.status}</span>
                  <button className="small-button" type="button" onClick={() => handleAnalyze(video.id)} disabled={analyzingId === video.id || video.status === "extracting_audio"}>{analyzingId === video.id ? "Analyzing" : "Analyze"}</button>
                  <button className="small-button" type="button" onClick={() => handleTranscript(video.id)} disabled={transcribingId === video.id || video.status === "transcribing"}>{transcribingId === video.id ? "Transcribing" : "Transcript"}</button>
                  <button className="small-button" type="button" onClick={() => handleHighlights(video.id)} disabled={highlightingId === video.id}>{highlightingId === video.id ? "Thinking" : "Highlights"}</button>
                  <button className="small-button ghost-small" type="button" onClick={() => handleRefreshStatus(video.id)}>Refresh</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="panel" aria-label={view === "login" ? "Login" : "Register"}>
          <p className="eyebrow">{view === "login" ? "Login" : "Register"}</p>
          <h2>{view === "login" ? "Sign in" : "Create account"}</h2>
          <form className="auth-form" onSubmit={view === "login" ? handleLogin : handleRegister}>
            <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
            <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={view === "login" ? "current-password" : "new-password"} minLength={view === "register" ? 8 : 1} required /></label>
            {message ? <p className="form-message">{message}</p> : null}
            <button className="primary-button" type="submit" disabled={isLoading}>{isLoading ? "Please wait" : view === "login" ? "Login" : "Register"}</button>
          </form>
          <button className="link-button" type="button" onClick={() => { setView(view === "login" ? "register" : "login"); setMessage(""); }}>{view === "login" ? "Create an account" : "Already have an account"}</button>
        </section>
      )}
    </main>
  );
}

function HighlightList({
  clips,
  creatingClipId,
  downloadingClipId,
  highlights,
  subtitleStyles,
  subtitlingClipId,
  onBurnSubtitles,
  onCreateClip,
  onDownloadClip,
  onStyleChange,
}: {
  clips: Record<number, Clip>;
  creatingClipId: number | null;
  downloadingClipId: number | null;
  highlights: Highlight[];
  subtitleStyles: Record<number, SubtitleStyle>;
  subtitlingClipId: number | null;
  onBurnSubtitles: (clip: Clip) => void;
  onCreateClip: (highlightId: number) => void;
  onDownloadClip: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
}) {
  return (
    <div className="highlight-list">
      {highlights.map((highlight) => {
        const clip = clips[highlight.id];
        return (
          <div className="highlight-card" key={highlight.id}>
            <div className="highlight-meta">
              <span>{formatTime(highlight.start_time)}-{formatTime(highlight.end_time)}</span>
              <span>{highlight.content_type}</span>
              <span>{Math.round(highlight.score)}점</span>
            </div>
            <strong>{highlight.title}</strong>
            <p>{highlight.reason}</p>
            {clip ? (
              <ClipSummary
                clip={clip}
                downloadingClipId={downloadingClipId}
                selectedStyle={subtitleStyles[clip.id] ?? "basic"}
                subtitlingClipId={subtitlingClipId}
                onBurnSubtitles={onBurnSubtitles}
                onDownloadClip={onDownloadClip}
                onStyleChange={onStyleChange}
              />
            ) : null}
            <button className="small-button clip-button" type="button" onClick={() => onCreateClip(highlight.id)} disabled={creatingClipId === highlight.id}>
              {creatingClipId === highlight.id ? "Creating" : clip?.status === "completed" ? "Create again" : "Create clip"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ClipSummary({
  clip,
  downloadingClipId,
  selectedStyle,
  subtitlingClipId,
  onBurnSubtitles,
  onDownloadClip,
  onStyleChange,
}: {
  clip: Clip;
  downloadingClipId: number | null;
  selectedStyle: SubtitleStyle;
  subtitlingClipId: number | null;
  onBurnSubtitles: (clip: Clip) => void;
  onDownloadClip: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
}) {
  const canUseClip = Boolean(clip.output_path);
  return (
    <div className={`clip-summary clip-${clip.status}`}>
      <span>Clip #{clip.id}</span>
      <span>{clip.status}</span>
      {clip.subtitle_style ? <span>subtitle: {clip.subtitle_style}</span> : null}
      {clip.subtitled_output_path ? <span>{clip.subtitled_output_path}</span> : clip.output_path ? <span>{clip.output_path}</span> : null}
      {clip.error_message ? <span className="error-text">{clip.error_message}</span> : null}
      {canUseClip ? (
        <div className="subtitle-controls">
          <label>
            Subtitle style
            <select value={selectedStyle} onChange={(event) => onStyleChange(clip.id, event.target.value as SubtitleStyle)}>
              {SUBTITLE_STYLES.map((style) => <option value={style} key={style}>{style}</option>)}
            </select>
          </label>
          <button className="small-button" type="button" onClick={() => onBurnSubtitles(clip)} disabled={subtitlingClipId === clip.id}>
            {subtitlingClipId === clip.id ? "Burning" : "Burn subtitles"}
          </button>
          <button className="small-button ghost-small" type="button" onClick={() => onDownloadClip(clip)} disabled={downloadingClipId === clip.id}>
            {downloadingClipId === clip.id ? "Downloading" : "Download"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remain = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remain}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);

