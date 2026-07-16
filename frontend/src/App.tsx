import { FormEvent, useEffect, useState } from "react";
import { API_BASE_URL, authorizedRequest, request, uploadRequest } from "./api/client";
import { AuthPanel } from "./components/AuthPanel";
import { BlogClipFlow } from "./components/BlogClipFlow";
import { BoardEditor } from "./components/board/BoardEditor";
import { Dashboard } from "./components/Dashboard";
import {
  BLOG_CLIP_POLL_INTERVAL_MS,
  CLIP_STATUS_LABELS,
  TOKEN_KEY,
} from "./constants";
import type {
  BlogClip,
  Board,
  Clip,
  ClipMetadata,
  Highlight,
  Plan,
  NarrationLanguage,
  ScriptModel,
  ScriptTone,
  SubtitleStyle,
  TargetLength,
  Transcript,
  TtsMode,
  Usage,
  User,
  Video,
  VideoStatusResponse,
  View,
  WizardBoardsStep,
} from "./types";

export function App() {
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
  const [blogTargetLength, setBlogTargetLength] = useState<TargetLength>("short");
  const [blogNarrationLanguage, setBlogNarrationLanguage] = useState<NarrationLanguage>("original");
  const [blogScriptModel, setBlogScriptModel] = useState<ScriptModel>("gpt-4o-mini");
  const [blogClips, setBlogClips] = useState<BlogClip[]>([]);
  const [isCreatingBlogShort, setIsCreatingBlogShort] = useState(false);
  const [selectingBlogScriptId, setSelectingBlogScriptId] = useState<number | null>(null);
  const [confirmingImageSelectionId, setConfirmingImageSelectionId] = useState<number | null>(null);
  const [savingVoiceId, setSavingVoiceId] = useState<number | null>(null);
  const [savingStyleId, setSavingStyleId] = useState<number | null>(null);
  const [savingVisualStyleId, setSavingVisualStyleId] = useState<number | null>(null);
  const [renderingFromFlowId, setRenderingFromFlowId] = useState<number | null>(null);
  const [editingBlogClipId, setEditingBlogClipId] = useState<number | null>(null);
  const [focusBlogClipId, setFocusBlogClipId] = useState<number | null>(null);
  const [blogBoardCounts, setBlogBoardCounts] = useState<Record<number, number>>({});
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

  const editingBlogClip = blogClips.find((clip) => clip.id === editingBlogClipId) ?? null;
  const focusBlogClip = blogClips.find((clip) => clip.id === focusBlogClipId) ?? null;

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    loadCurrentUser(token);
  }, []);

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
    loaded.filter((clip) => clip.status === "pending" || clip.status === "processing").forEach((clip) => pollBlogClip(clip.id));

    const awaitingBoards = loaded.filter((clip) => clip.status === "awaiting_boards");
    if (awaitingBoards.length > 0) {
      const counts = await Promise.all(
        awaitingBoards.map(async (clip) => {
          try {
            const boards = await authorizedRequest<Board[]>(`/blog-clips/${clip.id}/boards`);
            return [clip.id, boards.length] as const;
          } catch {
            return [clip.id, 0] as const;
          }
        }),
      );
      setBlogBoardCounts((current) => {
        const next = { ...current };
        for (const [id, count] of counts) next[id] = count;
        return next;
      });
    }
  }

  function pollBlogClip(blogClipId: number) {
    if (editingBlogClipId === blogClipId) return;
    const intervalId = window.setInterval(async () => {
      try {
        const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClipId}`);
        setBlogClips((current) => {
          const exists = current.some((item) => item.id === updated.id);
          return exists
            ? current.map((item) => (item.id === updated.id ? updated : item))
            : [updated, ...current];
        });
        if (
          updated.status === "completed" ||
          updated.status === "failed" ||
          updated.status === "awaiting_images" ||
          updated.status === "awaiting_script" ||
          updated.status === "awaiting_boards"
        ) {
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
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
      setVideos([]);
      setUsage(null);
      setPlans([]);
      setView("login");
      return;
    }

    try {
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
    setUploadMessage("");
    try {
      const blogClip = await authorizedRequest<BlogClip>("/blog-clips", {
        method: "POST",
        body: JSON.stringify({
          url: blogUrl.trim(),
          style: blogSubtitleStyle,
          target_length: blogTargetLength,
          narration_language: blogNarrationLanguage,
          script_model: blogScriptModel,
        }),
      });
      setBlogClips((current) => [blogClip, ...current.filter((item) => item.id !== blogClip.id)]);
      setBlogUrl("");
      setFocusBlogClipId(blogClip.id);
      pollBlogClip(blogClip.id);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "블로그 쇼츠 생성에 실패했습니다.");
    } finally {
      setIsCreatingBlogShort(false);
    }
  }

  async function handleConfirmBlogImages(blogClip: BlogClip, imageIds: number[]) {
    setConfirmingImageSelectionId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/images/selection`, {
        method: "PUT",
        body: JSON.stringify({ image_ids: imageIds }),
      });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setFocusBlogClipId(updated.id);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "이미지 선택에 실패했습니다.");
    } finally {
      setConfirmingImageSelectionId(null);
    }
  }

  async function handleSaveDefaultVoice(blogClip: BlogClip, voiceId: string, ttsSpeed: number) {
    setSavingVoiceId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/default-voice`, {
        method: "PATCH",
        body: JSON.stringify({ voice_id: voiceId, tts_speed: ttsSpeed, apply_to_all_boards: true }),
      });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "보이스 저장에 실패했습니다.");
      throw error;
    } finally {
      setSavingVoiceId(null);
    }
  }

  async function handleApplyVisualStyle(
    blogClip: BlogClip,
    visualStyle: string,
    copy?: { style_title?: string; style_subtitle?: string },
  ) {
    setSavingVisualStyleId(blogClip.id);
    setUploadMessage("");
    try {
      let updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/visual-style`, {
        method: "PATCH",
        body: JSON.stringify({ visual_style: visualStyle }),
      });
      if (copy && (copy.style_title !== undefined || copy.style_subtitle !== undefined)) {
        updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/style-copy`, {
          method: "PATCH",
          body: JSON.stringify(copy),
        });
      }
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "영상 스타일 저장에 실패했습니다.");
      throw error;
    } finally {
      setSavingVisualStyleId(null);
    }
  }

  async function handleAudioSettings(
    blogClip: BlogClip,
    body: { auto_bgm?: boolean; auto_sfx?: boolean; bgm_asset_id?: number | null },
  ) {
    setSavingStyleId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/audio-settings`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "오디오 설정에 실패했습니다.");
      throw error;
    } finally {
      setSavingStyleId(null);
    }
  }

  function handleWizardStepChange(blogClip: BlogClip, step: WizardBoardsStep) {
    setBlogClips((current) =>
      current.map((item) => (item.id === blogClip.id ? { ...item, wizard_step: step } : item)),
    );
    void authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/wizard-step`, {
      method: "PATCH",
      body: JSON.stringify({ wizard_step: step }),
    })
      .then((updated) => {
        setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      })
      .catch((error) => {
        setUploadMessage(error instanceof Error ? error.message : "단계 저장에 실패했습니다.");
      });
  }

  async function handleRenderFromFlow(blogClip: BlogClip) {
    setRenderingFromFlowId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/render`, { method: "POST" });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setFocusBlogClipId(updated.id);
      pollBlogClip(updated.id);
      setUploadMessage("렌더링을 시작했습니다.");
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "렌더링 시작에 실패했습니다.");
    } finally {
      setRenderingFromFlowId(null);
    }
  }

  async function handleSelectBlogScript(blogClip: BlogClip, tone: ScriptTone) {
    setSelectingBlogScriptId(blogClip.id);
    setUploadMessage("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/select-script`, {
        method: "POST",
        body: JSON.stringify({ tone }),
      });
      setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setFocusBlogClipId(updated.id);
      const boards = await authorizedRequest<Board[]>(`/blog-clips/${updated.id}/boards`);
      setBlogBoardCounts((current) => ({ ...current, [updated.id]: boards.length }));
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "대본 선택에 실패했습니다.");
    } finally {
      setSelectingBlogScriptId(null);
    }
  }

  function handleOpenBoardEditor(blogClip: BlogClip) {
    if (blogClip.status !== "awaiting_boards") return;
    setFocusBlogClipId(blogClip.id);
    setEditingBlogClipId(blogClip.id);
  }

  function handleOpenBlogClip(blogClip: BlogClip) {
    setFocusBlogClipId(blogClip.id);
    setUploadMessage("");
    if (blogClip.status === "pending" || blogClip.status === "processing") {
      pollBlogClip(blogClip.id);
    }
  }

  function handleBackToStudio() {
    setFocusBlogClipId(null);
    setUploadMessage("");
  }

  function handleCloseBoardEditor() {
    const clipId = editingBlogClipId;
    setEditingBlogClipId(null);
    if (clipId == null) return;
    setFocusBlogClipId(clipId);
    setBlogClips((current) =>
      current.map((item) => (item.id === clipId ? { ...item, wizard_step: "ready" } : item)),
    );
    void authorizedRequest<Board[]>(`/blog-clips/${clipId}/boards`)
      .then((boards) => {
        setBlogBoardCounts((current) => ({ ...current, [clipId]: boards.length }));
      })
      .catch(() => {
        /* keep previous count */
      });
    void authorizedRequest<BlogClip>(`/blog-clips/${clipId}/wizard-step`, {
      method: "PATCH",
      body: JSON.stringify({ wizard_step: "ready" }),
    })
      .then((updated) => {
        setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      })
      .catch((error) => {
        setUploadMessage(error instanceof Error ? error.message : "단계 저장에 실패했습니다.");
      });
  }

  function handleBoardEditorRendered(updated: BlogClip) {
    setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setEditingBlogClipId(null);
    setFocusBlogClipId(updated.id);
    pollBlogClip(updated.id);
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
    setBlogBoardCounts({});
    setSelectingBlogScriptId(null);
    setEditingBlogClipId(null);
    setFocusBlogClipId(null);
    setView("login");
    setMessage("");
    setUploadMessage("");
  }

  if (editingBlogClip && editingBlogClip.status === "awaiting_boards") {
    return (
      <BoardEditor
        blogClip={editingBlogClip}
        onClose={handleCloseBoardEditor}
        onRendered={handleBoardEditorRendered}
        onClipUpdated={(updated) => {
          setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        }}
        onMessage={setUploadMessage}
      />
    );
  }

  if (view === "dashboard" && user && focusBlogClip) {
    return (
      <main className="app-root">
        <BlogClipFlow
          blogClip={focusBlogClip}
          boardCount={blogBoardCounts[focusBlogClip.id]}
          copiedKey={copiedKey}
          downloadingBlogClipId={downloadingBlogClipId}
          generatingBlogMetadataId={generatingBlogMetadataId}
          selectingBlogScriptId={selectingBlogScriptId}
          confirmingImageSelection={confirmingImageSelectionId === focusBlogClip.id}
          savingVoice={savingVoiceId === focusBlogClip.id}
          savingStyle={savingStyleId === focusBlogClip.id}
          savingVisualStyle={savingVisualStyleId === focusBlogClip.id}
          renderingFromFlow={renderingFromFlowId === focusBlogClip.id}
          onBackToStudio={handleBackToStudio}
          onCopyText={handleCopyText}
          onDownloadBlogClip={handleDownloadBlogClip}
          onGenerateMetadata={handleGenerateBlogMetadata}
          onSelectScript={handleSelectBlogScript}
          onConfirmImages={handleConfirmBlogImages}
          onSaveDefaultVoice={handleSaveDefaultVoice}
          onApplyVisualStyle={handleApplyVisualStyle}
          onAudioSettings={handleAudioSettings}
          onWizardStepChange={handleWizardStepChange}
          onRender={handleRenderFromFlow}
          onOpenBoardEditor={handleOpenBoardEditor}
          onBlogClipUpdated={(updated) => {
            setBlogClips((current) => current.map((item) => (item.id === updated.id ? updated : item)));
          }}
          onMessage={setUploadMessage}
        />
      </main>
    );
  }

  if (view === "dashboard" && user) {
    return (
      <main className="app-root">
        <Dashboard
          user={user}
          usage={usage}
          plans={plans}
          uploadMessage={uploadMessage}
          selectedFile={selectedFile}
          isUploading={isUploading}
          youtubeUrl={youtubeUrl}
          isImportingYoutube={isImportingYoutube}
          blogUrl={blogUrl}
          blogSubtitleStyle={blogSubtitleStyle}
          blogTargetLength={blogTargetLength}
          blogNarrationLanguage={blogNarrationLanguage}
          blogScriptModel={blogScriptModel}
          isCreatingBlogShort={isCreatingBlogShort}
          blogClips={blogClips}
          copiedKey={copiedKey}
          videos={videos}
          transcripts={transcripts}
          highlights={highlights}
          clips={clips}
          clipMetadata={clipMetadata}
          creatingClipId={creatingClipId}
          downloadingClipId={downloadingClipId}
          generatingMetadataId={generatingMetadataId}
          narratingClipId={narratingClipId}
          subtitleStyles={subtitleStyles}
          ttsModes={ttsModes}
          subtitlingClipId={subtitlingClipId}
          analyzingId={analyzingId}
          transcribingId={transcribingId}
          highlightingId={highlightingId}
          onLogout={handleLogout}
          onUpload={handleUpload}
          onSelectedFileChange={setSelectedFile}
          onImportYoutube={handleImportYoutube}
          onYoutubeUrlChange={setYoutubeUrl}
          onCreateBlogShort={handleCreateBlogShort}
          onBlogUrlChange={setBlogUrl}
          onBlogSubtitleStyleChange={setBlogSubtitleStyle}
          onBlogTargetLengthChange={setBlogTargetLength}
          onBlogNarrationLanguageChange={setBlogNarrationLanguage}
          onBlogScriptModelChange={setBlogScriptModel}
          onCopyText={handleCopyText}
          onOpenBlogClip={handleOpenBlogClip}
          onAnalyze={handleAnalyze}
          onTranscript={handleTranscript}
          onHighlights={handleHighlights}
          onRefreshStatus={handleRefreshStatus}
          onApplyNarration={handleApplyNarration}
          onBurnSubtitles={handleBurnSubtitles}
          onCreateClip={handleCreateClip}
          onDownloadClip={handleDownloadClip}
          onGenerateMetadata={handleGenerateMetadata}
          onStyleChange={(clipId, style) => setSubtitleStyles((current) => ({ ...current, [clipId]: style }))}
          onTtsModeChange={(clipId, mode) => setTtsModes((current) => ({ ...current, [clipId]: mode }))}
        />
      </main>
    );
  }

  return (
    <main className="app-root landing-shell">
      <div className="landing-atmosphere" aria-hidden="true" />
      <section className="landing-hero">
        <p className="create-kicker">AI 쇼츠 스튜디오</p>
        <h1 className="landing-brand">New Cut</h1>
        <p className="landing-tagline">블로그·유튜브·MP4로 쇼츠를 만들고, 대본부터 자막까지 한 흐름으로.</p>
        <ul className="landing-points">
          <li>소스 선택 → 생성 → 편집</li>
          <li>톤별 대본 · 보드 에디터</li>
          <li>버전 다운로드 · 메타데이터</li>
        </ul>
      </section>
      <AuthPanel
        view={view}
        email={email}
        password={password}
        message={message}
        isLoading={isLoading}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSubmit={view === "login" ? handleLogin : handleRegister}
        onToggleView={() => {
          setView(view === "login" ? "register" : "login");
          setMessage("");
        }}
      />
    </main>
  );
}
