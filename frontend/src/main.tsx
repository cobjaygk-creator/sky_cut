import React, { FormEvent, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type View = "login" | "register" | "dashboard";
type VideoStatus = "uploaded" | "extracting_audio" | "audio_extracted" | "transcribing" | "transcribed" | "failed";
type ClipStatus = "pending" | "processing" | "completed" | "failed";
type SubtitleStyle = "basic" | "bold" | "shorts";
type TtsMode = "original_audio" | "ai_narration";

type User = { id: number; email: string; plan: string; monthly_usage: number; usage_limit: number; usage_month: string; created_at: string };

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
type Usage = {
  plan: string;
  plan_name: string;
  monthly_usage: number;
  usage_limit: number;
  remaining: number;
  usage_month: string;
  max_video_minutes: number;
};
type Plan = {
  id: string;
  name: string;
  monthly_video_limit: number;
  max_video_minutes: number;
  description: string;
};
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
  tts_mode: string;
  narration_script: string | null;
  narration_audio_path: string | null;
  narrated_output_path: string | null;
  status: ClipStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

type ClipMetadata = {
  id: number;
  clip_id: number;
  title_candidates: string[];
  description: string;
  hashtags: string[];
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

type BlogClip = {
  id: number;
  source_url: string;
  blog_title: string | null;
  narration_script: string | null;
  subtitle_style: string;
  video_path: string | null;
  subtitled_video_path: string | null;
  status: ClipStatus;
  progress_stage: string;
  progress_percent: number;
  error_message: string | null;
  title_candidates: string[];
  description: string | null;
  hashtags: string[];
  metadata_error: string | null;
  created_at: string;
  updated_at: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "new_cut_access_token";
const SUBTITLE_STYLES: SubtitleStyle[] = ["basic", "bold", "shorts"];
const TTS_MODES: TtsMode[] = ["original_audio", "ai_narration"];

const VIDEO_STATUS_LABELS: Record<VideoStatus, string> = {
  uploaded: "업로드됨",
  extracting_audio: "오디오 추출 중",
  audio_extracted: "오디오 추출 완료",
  transcribing: "음성 인식 중",
  transcribed: "음성 인식 완료",
  failed: "실패",
};

const CLIP_STATUS_LABELS: Record<ClipStatus, string> = {
  pending: "대기 중",
  processing: "처리 중",
  completed: "완료",
  failed: "실패",
};

const SUBTITLE_STYLE_LABELS: Record<SubtitleStyle, string> = {
  basic: "기본",
  bold: "볼드",
  shorts: "쇼츠",
};

const TTS_MODE_LABELS: Record<TtsMode, string> = {
  original_audio: "원본 음성",
  ai_narration: "AI 나레이션",
};

const BLOG_PROGRESS_STAGE_LABELS: Record<string, string> = {
  queued: "대기 중",
  scraping: "블로그 글 읽는 중",
  downloading_images: "이미지 다운로드 중",
  generating_script: "나레이션 대본 작성 중",
  synthesizing_audio: "음성 합성 중",
  rendering_video: "영상 합성 중",
  burning_subtitles: "자막 입히는 중",
  done: "완료",
};
const BLOG_CLIP_POLL_INTERVAL_MS = 2000;

function App() {
  const [view, setView] = useState<View>("login");
  const [email, setEmail] = useState("stage2-test@example.com");
  const [password, setPassword] = useState("Password123!");
  const [user, setUser] = useState<User | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [transcripts, setTranscripts] = useState<Record<number, Transcript>>({});
  const [highlights, setHighlights] = useState<Record<number, Highlight[]>>({});
  const [clips, setClips] = useState<Record<number, Clip>>({});
  const [clipMetadata, setClipMetadata] = useState<Record<number, ClipMetadata>>({});
  const [subtitleStyles, setSubtitleStyles] = useState<Record<number, SubtitleStyle>>({});
  const [ttsModes, setTtsModes] = useState<Record<number, TtsMode>>({});
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [blogUrl, setBlogUrl] = useState("");
  const [blogSubtitleStyle, setBlogSubtitleStyle] = useState<SubtitleStyle>("shorts");
  const [blogClips, setBlogClips] = useState<BlogClip[]>([]);
  const [isCreatingBlogShort, setIsCreatingBlogShort] = useState(false);
  const [generatingBlogMetadataId, setGeneratingBlogMetadataId] = useState<number | null>(null);
  const [downloadingBlogClipId, setDownloadingBlogClipId] = useState<number | null>(null);
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
  const [narratingClipId, setNarratingClipId] = useState<number | null>(null);
  const [generatingMetadataId, setGeneratingMetadataId] = useState<number | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

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
      const detail = typeof data.detail === "string" ? data.detail : "요청에 실패했습니다.";
      throw new Error(detail);
    }
    return data as T;
  }

  async function authorizedRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) throw new Error("로그인이 필요합니다.");
    return request<T>(path, { ...options, headers: { Authorization: `Bearer ${token}`, ...options.headers } });
  }

  async function uploadRequest<T>(path: string, body: FormData): Promise<T> {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) throw new Error("로그인이 필요합니다.");
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "업로드에 실패했습니다.";
      throw new Error(detail);
    }
    return data as T;
  }

  async function loadVideos() {
    setVideos(await authorizedRequest<Video[]>("/videos"));
  }

  async function loadUsage() {
    setUsage(await authorizedRequest<Usage>("/usage"));
  }

  async function loadPlans() {
    setPlans(await request<Plan[]>("/plans"));
  }

  async function loadBlogClips() {
    const loaded = await authorizedRequest<BlogClip[]>("/blog-clips");
    setBlogClips(loaded);
    loaded
      .filter((clip) => clip.status === "pending" || clip.status === "processing")
      .forEach((clip) => pollBlogClip(clip.id));
  }

  function pollBlogClip(blogClipId: number) {
    const intervalId = window.setInterval(async () => {
      try {
        const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClipId}`);
        setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        if (updated.status === "completed" || updated.status === "failed") {
          window.clearInterval(intervalId);
        }
      } catch {
        window.clearInterval(intervalId);
      }
    }, BLOG_CLIP_POLL_INTERVAL_MS);
  }

  async function loadCurrentUser(token: string) {
    try {
      const me = await request<User>("/me", { headers: { Authorization: `Bearer ${token}` } });
      setUser(me);
      setView("dashboard");
      setMessage("");
    } catch {
      // Only a failed /me means the session itself is invalid (missing/expired token).
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
      setVideos([]);
      setUsage(null);
      setPlans([]);
      setView("login");
      return;
    }

    try {
      // The user is already authenticated at this point, so a failure here
      // (e.g. a transient backend error) should show a message on the
      // dashboard instead of silently logging the user back out.
      await Promise.all([loadVideos(), loadUsage(), loadPlans(), loadBlogClips()]);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "대시보드 데이터를 불러오지 못했습니다. 새로고침을 눌러보세요.");
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
      setMessage(error instanceof Error ? error.message : "로그인에 실패했습니다.");
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
      setMessage("계정이 생성되었습니다. 로그인해주세요.");
      setView("login");
      setPassword("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "회원가입에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setUploadMessage("먼저 MP4 파일을 선택해주세요.");
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
      setUploadMessage("업로드가 완료되었습니다.");
      await Promise.all([loadVideos(), loadUsage(), loadPlans()]);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "업로드에 실패했습니다.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleImportYoutube(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!youtubeUrl.trim()) {
      setUploadMessage("먼저 유튜브 URL을 입력해주세요.");
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
      setUploadMessage("유튜브 영상을 가져왔습니다.");
      await Promise.all([loadVideos(), loadUsage(), loadPlans()]);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "유튜브 영상 가져오기에 실패했습니다.");
    } finally {
      setIsImportingYoutube(false);
    }
  }

  async function handleCreateBlogShort(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!blogUrl.trim()) {
      setUploadMessage("먼저 블로그 글 URL을 입력해주세요.");
      return;
    }
    setIsCreatingBlogShort(true);
    setUploadMessage("블로그 쇼츠 생성을 시작했습니다. 아래 목록에서 진행 상태를 확인할 수 있어요.");
    try {
      const blogClip = await authorizedRequest<BlogClip>("/blog-clips", {
        method: "POST",
        body: JSON.stringify({ url: blogUrl.trim(), style: blogSubtitleStyle }),
      });
      setBlogClips((current) => [blogClip, ...current]);
      setBlogUrl("");
      pollBlogClip(blogClip.id);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "블로그 쇼츠 생성에 실패했습니다.");
    } finally {
      setIsCreatingBlogShort(false);
    }
  }

  async function handleGenerateBlogMetadata(blogClip: BlogClip) {
    setGeneratingBlogMetadataId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/metadata`, { method: "POST" });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setUploadMessage("업로드용 메타데이터가 생성되었습니다.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "메타데이터 생성에 실패했습니다.");
    } finally {
      setGeneratingBlogMetadataId(null);
    }
  }

  async function handleDownloadBlogClip(blogClip: BlogClip) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUploadMessage("로그인이 필요합니다.");
      return;
    }
    setDownloadingBlogClipId(blogClip.id);
    setUploadMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/blog-clips/${blogClip.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === "string" ? data.detail : "다운로드에 실패했습니다.";
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `new-cut-blog-${blogClip.id}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "다운로드에 실패했습니다.");
    } finally {
      setDownloadingBlogClipId(null);
    }
  }

  async function handleAnalyze(videoId: number) {
    setAnalyzingId(videoId);
    try {
      mergeVideoStatus(await authorizedRequest<VideoStatusResponse>(`/videos/${videoId}/analyze`, { method: "POST" }));
      await loadUsage();
} catch (error) {
      await Promise.all([loadVideos(), loadUsage(), loadPlans()]);
      setUploadMessage(error instanceof Error ? error.message : "오디오 추출에 실패했습니다.");
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleTranscript(videoId: number) {
    setTranscribingId(videoId);
    try {
      const transcript = await authorizedRequest<Transcript>(`/videos/${videoId}/transcript`);
      setTranscripts((current) => ({ ...current, [videoId]: transcript }));
      await Promise.all([loadVideos(), loadUsage(), loadPlans()]);
    } catch (error) {
      await Promise.all([loadVideos(), loadUsage(), loadPlans()]);
      setUploadMessage(error instanceof Error ? error.message : "음성 인식에 실패했습니다.");
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
      setUploadMessage(error instanceof Error ? error.message : "하이라이트 추천에 실패했습니다.");
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
      setClipMetadata((current) => {
        const next = { ...current };
        delete next[clip.id];
        return next;
      });
      setSubtitleStyles((current) => ({ ...current, [clip.id]: "basic" }));
      setTtsModes((current) => ({ ...current, [clip.id]: "original_audio" }));
      setUploadMessage(clip.status === "completed" ? "클립이 생성되었습니다." : `클립 상태: ${CLIP_STATUS_LABELS[clip.status]}`);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "클립 생성에 실패했습니다.");
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
      setUploadMessage("자막이 삽입된 클립이 생성되었습니다.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "자막 삽입에 실패했습니다.");
    } finally {
      setSubtitlingClipId(null);
    }
  }

  async function handleApplyNarration(clip: Clip) {
    const mode = ttsModes[clip.id] ?? "original_audio";
    setNarratingClipId(clip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<Clip>(`/clips/${clip.id}/narration`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      setClips((current) => ({ ...current, [updated.highlight_id]: updated }));
      setUploadMessage(mode === "ai_narration" ? "AI 나레이션이 적용되었습니다." : "원본 음성이 선택되었습니다.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "나레이션 적용에 실패했습니다.");
    } finally {
      setNarratingClipId(null);
    }
  }

  async function handleGenerateMetadata(clip: Clip) {
    setGeneratingMetadataId(clip.id);
    setUploadMessage("");
    try {
      const metadata = await authorizedRequest<ClipMetadata>(`/clips/${clip.id}/metadata`, { method: "POST" });
      setClipMetadata((current) => ({ ...current, [clip.id]: metadata }));
      setUploadMessage("업로드용 메타데이터가 생성되었습니다.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "메타데이터 생성에 실패했습니다.");
    } finally {
      setGeneratingMetadataId(null);
    }
  }

  async function handleCopyText(key: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey(null), 1400);
    } catch {
      setUploadMessage("복사에 실패했습니다.");
    }
  }

  async function handleDownloadClip(clip: Clip) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setUploadMessage("로그인이 필요합니다.");
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
        const detail = typeof data.detail === "string" ? data.detail : "다운로드에 실패했습니다.";
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
      setUploadMessage(error instanceof Error ? error.message : "다운로드에 실패했습니다.");
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
    setClipMetadata({});
    setSubtitleStyles({});
    setTtsModes({});
    setSelectedFile(null);
    setYoutubeUrl("");
    setBlogUrl("");
    setBlogClips([]);
    setView("login");
    setMessage("");
    setUploadMessage("");
  }

  return (
    <main className="app-shell">
      <section className="intro">
        <p className="eyebrow">AI 쇼츠 제작 SaaS</p>
        <h1>New Cut</h1>
        <p>MP4 영상을 업로드하고, 음성을 텍스트로 변환하고, 하이라이트를 추천받고, 세로형 클립을 만들고, 자막을 삽입하세요.</p>
      </section>

      {view === "dashboard" && user ? (
        <section className="panel dashboard-panel" aria-label="대시보드">
          <div className="panel-header">
            <div>
              <p className="eyebrow">대시보드</p>
              <h2>내 영상</h2>
            </div>
            <button className="ghost-button" type="button" onClick={handleLogout}>로그아웃</button>
          </div>

          <p className="account-line">{user.email}로 로그인 중</p>
          <UsagePanel usage={usage} plans={plans} />

          {uploadMessage ? <p className="form-message dashboard-message">{uploadMessage}</p> : null}

<form className="upload-form" onSubmit={handleUpload}>
            <label>
              MP4 영상
              <input type="file" accept="video/mp4,.mp4" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            </label>
            {selectedFile ? <p className="file-note">선택됨: {selectedFile.name} ({formatBytes(selectedFile.size)})</p> : null}
            <button className="primary-button" type="submit" disabled={isUploading}>{isUploading ? "업로드 중" : "영상 업로드"}</button>
          </form>

          <form className="upload-form youtube-form" onSubmit={handleImportYoutube}>
            <label>
              유튜브 URL
              <input type="url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=..." />
            </label>
            <p className="file-note">본인이 소유했거나 처리 권한이 있는 영상만 사용하세요.</p>
            <button className="primary-button" type="submit" disabled={isImportingYoutube}>{isImportingYoutube ? "가져오는 중" : "유튜브 영상 가져오기"}</button>
          </form>

          <form className="upload-form blog-form" onSubmit={handleCreateBlogShort}>
            <label>
              블로그/글 URL
              <input type="url" value={blogUrl} onChange={(event) => setBlogUrl(event.target.value)} placeholder="https://blog.naver.com/... 또는 티스토리, 브런치 등" />
            </label>
            <label>
              자막 스타일
              <select value={blogSubtitleStyle} onChange={(event) => setBlogSubtitleStyle(event.target.value as SubtitleStyle)}>
                {SUBTITLE_STYLES.map((style) => <option value={style} key={style}>{SUBTITLE_STYLE_LABELS[style]}</option>)}
              </select>
            </label>
            <p className="file-note">네이버 블로그는 물론 티스토리, 브런치 등 대부분의 블로그/기사 URL을 지원합니다. 본문 텍스트와 이미지를 바탕으로 AI 나레이션 쇼츠를 만듭니다. 최대 1분 정도 걸릴 수 있어요.</p>
            <button className="primary-button" type="submit" disabled={isCreatingBlogShort}>{isCreatingBlogShort ? "생성 중" : "블로그로 쇼츠 만들기"}</button>
          </form>

          <div className="blog-clip-list" aria-label="블로그 쇼츠">
            {blogClips.length === 0 ? null : (
              <>
                <h3 className="section-title">블로그 쇼츠</h3>
                {blogClips.map((blogClip) => (
                  <BlogClipCard
                    key={blogClip.id}
                    blogClip={blogClip}
                    copiedKey={copiedKey}
                    downloadingBlogClipId={downloadingBlogClipId}
                    generatingBlogMetadataId={generatingBlogMetadataId}
                    onCopyText={handleCopyText}
                    onDownloadBlogClip={handleDownloadBlogClip}
                    onGenerateMetadata={handleGenerateBlogMetadata}
                  />
                ))}
              </>
            )}
          </div>

          <div className="video-list" aria-label="업로드된 영상">
            {videos.length === 0 ? <p className="muted">아직 업로드된 영상이 없습니다.</p> : videos.map((video) => (
              <article className="video-item" key={video.id}>
                <div className="video-copy">
                  <h3>{video.original_filename}</h3>
                  <p>{formatBytes(video.file_size)} · {video.created_at}</p>
                  {video.audio_path ? <p>오디오 추출 완료</p> : null}
                  {video.error_message ? <p className="error-text">{video.error_message}</p> : null}
                  {transcripts[video.id]?.text ? <p className="transcript-preview">{transcripts[video.id].text}</p> : null}
                  {highlights[video.id]?.length ? (
                    <HighlightList
                      clips={clips}
                      clipMetadata={clipMetadata}
                      copiedKey={copiedKey}
                      creatingClipId={creatingClipId}
                      downloadingClipId={downloadingClipId}
                      generatingMetadataId={generatingMetadataId}
                      highlights={highlights[video.id]}
                      narratingClipId={narratingClipId}
                      subtitleStyles={subtitleStyles}
                      ttsModes={ttsModes}
                      subtitlingClipId={subtitlingClipId}
                      onApplyNarration={handleApplyNarration}
                      onBurnSubtitles={handleBurnSubtitles}
                      onCreateClip={handleCreateClip}
                      onCopyText={handleCopyText}
                      onDownloadClip={handleDownloadClip}
                      onGenerateMetadata={handleGenerateMetadata}
                      onStyleChange={(clipId, style) => setSubtitleStyles((current) => ({ ...current, [clipId]: style }))}
                      onTtsModeChange={(clipId, mode) => setTtsModes((current) => ({ ...current, [clipId]: mode }))}
                    />
                  ) : null}
                </div>
                <div className="video-actions">
                  <span className={`status-badge status-${video.status}`}>{VIDEO_STATUS_LABELS[video.status]}</span>
                  <button className="small-button" type="button" onClick={() => handleAnalyze(video.id)} disabled={analyzingId === video.id || video.status === "extracting_audio"}>{analyzingId === video.id ? "분석 중" : "분석"}</button>
                  <button className="small-button" type="button" onClick={() => handleTranscript(video.id)} disabled={transcribingId === video.id || video.status === "transcribing"}>{transcribingId === video.id ? "인식 중" : "음성 인식"}</button>
                  <button className="small-button" type="button" onClick={() => handleHighlights(video.id)} disabled={highlightingId === video.id}>{highlightingId === video.id ? "추천 중" : "하이라이트 추천"}</button>
                  <button className="small-button ghost-small" type="button" onClick={() => handleRefreshStatus(video.id)}>새로고침</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="panel" aria-label={view === "login" ? "로그인" : "회원가입"}>
          <p className="eyebrow">{view === "login" ? "로그인" : "회원가입"}</p>
          <h2>{view === "login" ? "로그인" : "계정 만들기"}</h2>
          <form className="auth-form" onSubmit={view === "login" ? handleLogin : handleRegister}>
            <label>이메일<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
            <label>비밀번호<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={view === "login" ? "current-password" : "new-password"} minLength={view === "register" ? 8 : 1} required /></label>
            {message ? <p className="form-message">{message}</p> : null}
            <button className="primary-button" type="submit" disabled={isLoading}>{isLoading ? "잠시만요" : view === "login" ? "로그인" : "회원가입"}</button>
          </form>
          <button className="link-button" type="button" onClick={() => { setView(view === "login" ? "register" : "login"); setMessage(""); }}>{view === "login" ? "계정 만들기" : "이미 계정이 있어요"}</button>
        </section>
      )}
    </main>
  );
}

function UsagePanel({ usage, plans }: { usage: Usage | null; plans: Plan[] }) {
  return (
    <section className="usage-panel" aria-label="사용량 및 요금제">
      <div className="usage-summary">
        <div>
          <span>현재 요금제</span>
          <strong>{usage ? usage.plan_name : "불러오는 중"}</strong>
        </div>
        <div>
          <span>이번 달 사용량</span>
          <strong>{usage ? `${usage.monthly_usage}/${usage.usage_limit}` : "-"}</strong>
        </div>
        <div>
          <span>최대 영상 길이</span>
          <strong>{usage ? `${usage.max_video_minutes}분` : "-"}</strong>
        </div>
      </div>
      <div className="plans-grid">
        {plans.map((plan) => (
          <article className={`plan-tile ${usage?.plan === plan.id ? "active-plan" : ""}`} key={plan.id}>
            <div>
              <strong>{plan.name}</strong>
              <span>월 {plan.monthly_video_limit}개</span>
            </div>
            <p>영상당 최대 {plan.max_video_minutes}분</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function HighlightList({
  clips,
  clipMetadata,
  copiedKey,
  creatingClipId,
  downloadingClipId,
  generatingMetadataId,
  narratingClipId,
  highlights,
  subtitleStyles,
  ttsModes,
  subtitlingClipId,
  onApplyNarration,
  onBurnSubtitles,
  onCopyText,
  onCreateClip,
  onDownloadClip,
  onGenerateMetadata,
  onStyleChange,
  onTtsModeChange,
}: {
  clips: Record<number, Clip>;
  clipMetadata: Record<number, ClipMetadata>;
  copiedKey: string | null;
  creatingClipId: number | null;
  downloadingClipId: number | null;
  generatingMetadataId: number | null;
  narratingClipId: number | null;
  highlights: Highlight[];
  subtitleStyles: Record<number, SubtitleStyle>;
  ttsModes: Record<number, TtsMode>;
  subtitlingClipId: number | null;
  onApplyNarration: (clip: Clip) => void;
  onBurnSubtitles: (clip: Clip) => void;
  onCopyText: (key: string, text: string) => void;
  onCreateClip: (highlightId: number) => void;
  onDownloadClip: (clip: Clip) => void;
  onGenerateMetadata: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
  onTtsModeChange: (clipId: number, mode: TtsMode) => void;
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
                copiedKey={copiedKey}
                downloadingClipId={downloadingClipId}
                generatingMetadataId={generatingMetadataId}
                metadata={clipMetadata[clip.id]}
                narratingClipId={narratingClipId}
                selectedStyle={subtitleStyles[clip.id] ?? "basic"}
                selectedTtsMode={ttsModes[clip.id] ?? (clip.tts_mode as TtsMode) ?? "original_audio"}
                subtitlingClipId={subtitlingClipId}
                onApplyNarration={onApplyNarration}
                onBurnSubtitles={onBurnSubtitles}
                onCopyText={onCopyText}
                onDownloadClip={onDownloadClip}
                onGenerateMetadata={onGenerateMetadata}
                onStyleChange={onStyleChange}
                onTtsModeChange={onTtsModeChange}
              />
            ) : null}
            <button className="small-button clip-button" type="button" onClick={() => onCreateClip(highlight.id)} disabled={creatingClipId === highlight.id}>
              {creatingClipId === highlight.id ? "생성 중" : clip?.status === "completed" ? "다시 생성" : "클립 생성"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ClipSummary({
  clip,
  copiedKey,
  downloadingClipId,
  generatingMetadataId,
  metadata,
  narratingClipId,
  selectedStyle,
  selectedTtsMode,
  subtitlingClipId,
  onApplyNarration,
  onBurnSubtitles,
  onCopyText,
  onDownloadClip,
  onGenerateMetadata,
  onStyleChange,
  onTtsModeChange,
}: {
  clip: Clip;
  copiedKey: string | null;
  downloadingClipId: number | null;
  generatingMetadataId: number | null;
  metadata?: ClipMetadata;
  narratingClipId: number | null;
  selectedStyle: SubtitleStyle;
  selectedTtsMode: TtsMode;
  subtitlingClipId: number | null;
  onApplyNarration: (clip: Clip) => void;
  onBurnSubtitles: (clip: Clip) => void;
  onCopyText: (key: string, text: string) => void;
  onDownloadClip: (clip: Clip) => void;
  onGenerateMetadata: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
  onTtsModeChange: (clipId: number, mode: TtsMode) => void;
}) {
  const canUseClip = Boolean(clip.output_path);
  return (
    <div className={`clip-summary clip-${clip.status}`}>
      <span>클립 #{clip.id}</span>
      <span>{CLIP_STATUS_LABELS[clip.status]}</span>
      {clip.subtitle_style ? <span>자막: {SUBTITLE_STYLE_LABELS[clip.subtitle_style as SubtitleStyle] ?? clip.subtitle_style}</span> : null}
      {clip.tts_mode ? <span>음성: {TTS_MODE_LABELS[clip.tts_mode as TtsMode] ?? clip.tts_mode}</span> : null}
      {clip.narrated_output_path ? <span>{clip.narrated_output_path}</span> : clip.subtitled_output_path ? <span>{clip.subtitled_output_path}</span> : clip.output_path ? <span>{clip.output_path}</span> : null}
      {clip.error_message ? <span className="error-text">{clip.error_message}</span> : null}
      {canUseClip ? (
        <>
          <div className="subtitle-controls">
            <label>
              자막 스타일
              <select value={selectedStyle} onChange={(event) => onStyleChange(clip.id, event.target.value as SubtitleStyle)}>
                {SUBTITLE_STYLES.map((style) => <option value={style} key={style}>{SUBTITLE_STYLE_LABELS[style]}</option>)}
              </select>
            </label>
            <button className="small-button" type="button" onClick={() => onBurnSubtitles(clip)} disabled={subtitlingClipId === clip.id}>
              {subtitlingClipId === clip.id ? "삽입 중" : "자막 삽입"}
            </button>
            <button className="small-button ghost-small" type="button" onClick={() => onDownloadClip(clip)} disabled={downloadingClipId === clip.id}>
              {downloadingClipId === clip.id ? "다운로드 중" : "다운로드"}
            </button>
          </div>
          <div className="subtitle-controls tts-controls">
            <label>
              음성 모드
              <select value={selectedTtsMode} onChange={(event) => onTtsModeChange(clip.id, event.target.value as TtsMode)}>
                {TTS_MODES.map((mode) => <option value={mode} key={mode}>{TTS_MODE_LABELS[mode]}</option>)}
              </select>
            </label>
            <button className="small-button" type="button" onClick={() => onApplyNarration(clip)} disabled={narratingClipId === clip.id}>
              {narratingClipId === clip.id ? "적용 중" : "음성 적용"}
            </button>
          </div>
          {clip.narration_script ? <p className="narration-script">{clip.narration_script}</p> : null}
          <button className="small-button metadata-button" type="button" onClick={() => onGenerateMetadata(clip)} disabled={generatingMetadataId === clip.id || Boolean(metadata)}>
            {generatingMetadataId === clip.id ? "작성 중" : metadata ? "메타데이터 준비됨" : "메타데이터 생성"}
          </button>
          {metadata ? (
            <MetadataBox
              copiedKey={copiedKey}
              idPrefix={`clip-${metadata.id}`}
              titleCandidates={metadata.title_candidates}
              description={metadata.description}
              hashtags={metadata.hashtags}
              onCopyText={onCopyText}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function MetadataBox({
  copiedKey,
  idPrefix,
  titleCandidates,
  description,
  hashtags,
  onCopyText,
}: {
  copiedKey: string | null;
  idPrefix: string;
  titleCandidates: string[];
  description: string;
  hashtags: string[];
  onCopyText: (key: string, text: string) => void;
}) {
  const hashtagText = hashtags.join(" ");
  return (
    <div className="metadata-box">
      <div className="metadata-section">
        <span>제목</span>
        {titleCandidates.map((title, index) => (
          <div className="copy-row" key={`${idPrefix}-title-${index}`}>
            <p>{title}</p>
            <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-title-${index}`, title)}>{copiedKey === `${idPrefix}-title-${index}` ? "복사됨" : "복사"}</button>
          </div>
        ))}
      </div>
      <div className="metadata-section">
        <span>설명</span>
        <div className="copy-row">
          <p>{description}</p>
          <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-description`, description)}>{copiedKey === `${idPrefix}-description` ? "복사됨" : "복사"}</button>
        </div>
      </div>
      <div className="metadata-section">
        <span>해시태그</span>
        <div className="copy-row">
          <p>{hashtagText}</p>
          <button className="copy-button" type="button" onClick={() => onCopyText(`${idPrefix}-hashtags`, hashtagText)}>{copiedKey === `${idPrefix}-hashtags` ? "복사됨" : "복사"}</button>
        </div>
      </div>
    </div>
  );
}

function BlogClipCard({
  blogClip,
  copiedKey,
  downloadingBlogClipId,
  generatingBlogMetadataId,
  onCopyText,
  onDownloadBlogClip,
  onGenerateMetadata,
}: {
  blogClip: BlogClip;
  copiedKey: string | null;
  downloadingBlogClipId: number | null;
  generatingBlogMetadataId: number | null;
  onCopyText: (key: string, text: string) => void;
  onDownloadBlogClip: (blogClip: BlogClip) => void;
  onGenerateMetadata: (blogClip: BlogClip) => void;
}) {
  const canDownload = Boolean(blogClip.subtitled_video_path || blogClip.video_path);
  const hasMetadata = blogClip.title_candidates.length > 0;
  const isInProgress = blogClip.status === "pending" || blogClip.status === "processing";
  const stageLabel = BLOG_PROGRESS_STAGE_LABELS[blogClip.progress_stage] ?? blogClip.progress_stage;
  return (
    <article className={`blog-clip-item clip-${blogClip.status}`}>
      <h4>{blogClip.blog_title ?? "블로그 쇼츠"}</h4>
      <p className="muted">{blogClip.source_url}</p>
      <div className="highlight-meta">
        <span className={`status-badge status-${blogClip.status}`}>{CLIP_STATUS_LABELS[blogClip.status]}</span>
        <span>자막: {SUBTITLE_STYLE_LABELS[blogClip.subtitle_style as SubtitleStyle] ?? blogClip.subtitle_style}</span>
      </div>
      {isInProgress ? (
        <div className="blog-progress" aria-live="polite">
          <div className="blog-progress-track">
            <div className="blog-progress-fill" style={{ width: `${blogClip.progress_percent}%` }} />
          </div>
          <span className="blog-progress-label">{stageLabel} ({blogClip.progress_percent}%)</span>
        </div>
      ) : null}
      {blogClip.narration_script ? <p className="narration-script">{blogClip.narration_script}</p> : null}
      {blogClip.error_message ? <p className="error-text">{blogClip.error_message}</p> : null}
      {canDownload ? (
        <div className="subtitle-controls">
          <button className="small-button ghost-small" type="button" onClick={() => onDownloadBlogClip(blogClip)} disabled={downloadingBlogClipId === blogClip.id}>
            {downloadingBlogClipId === blogClip.id ? "다운로드 중" : "다운로드"}
          </button>
          <button className="small-button metadata-button" type="button" onClick={() => onGenerateMetadata(blogClip)} disabled={generatingBlogMetadataId === blogClip.id || hasMetadata}>
            {generatingBlogMetadataId === blogClip.id ? "작성 중" : hasMetadata ? "메타데이터 준비됨" : "메타데이터 생성"}
          </button>
        </div>
      ) : null}
      {blogClip.metadata_error ? <p className="error-text">{blogClip.metadata_error}</p> : null}
      {hasMetadata ? (
        <MetadataBox
          copiedKey={copiedKey}
          idPrefix={`blog-${blogClip.id}`}
          titleCandidates={blogClip.title_candidates}
          description={blogClip.description ?? ""}
          hashtags={blogClip.hashtags}
          onCopyText={onCopyText}
        />
      ) : null}
    </article>
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












