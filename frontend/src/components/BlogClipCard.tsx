import { useEffect, useState } from "react";
import { API_BASE_URL, authorizedRequest } from "../api/client";
import {
  BLOG_CLIP_POLL_INTERVAL_MS,
  BLOG_CLIP_STATUS_LABELS,
  BLOG_PROGRESS_STAGE_LABELS,
  SCRIPT_TONE_HINTS,
  SCRIPT_TONE_LABELS,
  SCRIPT_TONES,
  SUBTITLE_STYLE_LABELS,
  TOKEN_KEY,
} from "../constants";
import type { BlogClip, BlogClipVersion, ScriptTone, SubtitleStyle } from "../types";
import { MetadataBox } from "./MetadataBox";
import { RenderSpecFooter } from "./RenderSpecFooter";

export function BlogClipCard({
  blogClip,
  copiedKey,
  downloadingBlogClipId,
  generatingBlogMetadataId,
  selectingBlogScriptId,
  blogBoardCounts,
  onCopyText,
  onDownloadBlogClip,
  onGenerateMetadata,
  onSelectScript,
  onOpenBoardEditor,
  onBlogClipUpdated,
  onMessage,
}: {
  blogClip: BlogClip;
  copiedKey: string | null;
  downloadingBlogClipId: number | null;
  generatingBlogMetadataId: number | null;
  selectingBlogScriptId: number | null;
  blogBoardCounts: Record<number, number>;
  onCopyText: (key: string, text: string) => void;
  onDownloadBlogClip: (blogClip: BlogClip) => void;
  onGenerateMetadata: (blogClip: BlogClip) => void;
  onSelectScript: (blogClip: BlogClip, tone: ScriptTone) => void;
  onOpenBoardEditor: (blogClip: BlogClip) => void;
  onBlogClipUpdated?: (blogClip: BlogClip) => void;
  onMessage?: (message: string) => void;
}) {
  const [versions, setVersions] = useState<BlogClipVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [creatingVersions, setCreatingVersions] = useState(false);
  const [downloadingVersionId, setDownloadingVersionId] = useState<number | null>(null);
  const [generatingVersionMetadataId, setGeneratingVersionMetadataId] = useState<number | null>(null);
  const [expandedVersionId, setExpandedVersionId] = useState<number | null>(null);
  const [versionPollToken, setVersionPollToken] = useState(0);

  const canDownload = Boolean(blogClip.subtitled_video_path || blogClip.video_path);
  const hasMetadata = blogClip.title_candidates.length > 0;
  const isInProgress = blogClip.status === "pending" || blogClip.status === "processing";
  const isAwaitingScript = blogClip.status === "awaiting_script";
  const isAwaitingBoards = blogClip.status === "awaiting_boards";
  const isCompleted = blogClip.status === "completed";
  const boardCount = blogBoardCounts[blogClip.id];
  const stageLabel = BLOG_PROGRESS_STAGE_LABELS[blogClip.progress_stage] ?? blogClip.progress_stage;
  const availableTones = SCRIPT_TONES.filter((tone) => Boolean(blogClip.script_candidates[tone]));

  useEffect(() => {
    if (!isCompleted) {
      setVersions([]);
      return;
    }

    let cancelled = false;
    let timer: number | undefined;

    async function loadVersions() {
      try {
        const loaded = await authorizedRequest<BlogClipVersion[]>(`/blog-clips/${blogClip.id}/versions`);
        if (cancelled) return;
        setVersions(loaded);
        const busy = loaded.some((version) => version.status === "pending" || version.status === "processing");
        if (busy) {
          timer = window.setTimeout(() => {
            void loadVersions();
          }, BLOG_CLIP_POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) setVersions([]);
      }
    }

    setVersionsLoading(true);
    void loadVersions().finally(() => {
      if (!cancelled) setVersionsLoading(false);
    });

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [blogClip.id, isCompleted, blogClip.active_version_id, blogClip.updated_at, versionPollToken]);

  async function handleCreateVersions(mode: "all_tones" | "boards") {
    setCreatingVersions(true);
    try {
      const created = await authorizedRequest<BlogClipVersion[]>(`/blog-clips/${blogClip.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      setVersions((current) => {
        const byId = new Map(current.map((item) => [item.id, item]));
        for (const item of created) byId.set(item.id, item);
        return Array.from(byId.values()).sort((a, b) => a.id - b.id);
      });
      setVersionPollToken((token) => token + 1);
      onMessage?.(mode === "all_tones" ? "다른 톤 버전 생성을 시작했습니다." : "보드 재생성 버전을 시작했습니다.");
    } catch (error) {
      onMessage?.(error instanceof Error ? error.message : "버전 생성에 실패했습니다.");
    } finally {
      setCreatingVersions(false);
    }
  }

  async function handleDownloadVersion(version: BlogClipVersion) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      onMessage?.("로그인이 필요합니다.");
      return;
    }
    setDownloadingVersionId(version.id);
    try {
      const response = await fetch(`${API_BASE_URL}/blog-clips/${blogClip.id}/versions/${version.id}/download`, {
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
      link.download = `new-cut-blog-${blogClip.id}-v${version.id}.mp4`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      onMessage?.(error instanceof Error ? error.message : "다운로드에 실패했습니다.");
    } finally {
      setDownloadingVersionId(null);
    }
  }

  async function handleSetActive(version: BlogClipVersion) {
    try {
      await authorizedRequest<BlogClipVersion>(`/blog-clips/${blogClip.id}/versions/${version.id}/set-active`, {
        method: "POST",
      });
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}`);
      onBlogClipUpdated?.(updated);
      setVersions((current) =>
        current.map((item) => ({
          ...item,
          is_active: item.id === version.id,
        })),
      );
      onMessage?.(`활성 버전을 ${version.label}(으)로 바꿨습니다.`);
    } catch (error) {
      onMessage?.(error instanceof Error ? error.message : "활성 버전 변경에 실패했습니다.");
    }
  }

  async function handleGenerateVersionMetadata(version: BlogClipVersion) {
    setGeneratingVersionMetadataId(version.id);
    try {
      const updated = await authorizedRequest<BlogClipVersion>(
        `/blog-clips/${blogClip.id}/versions/${version.id}/metadata`,
        { method: "POST" },
      );
      setVersions((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setExpandedVersionId(updated.id);
      if (updated.is_active) {
        const parent = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}`);
        onBlogClipUpdated?.(parent);
      }
      onMessage?.("버전 메타데이터가 생성되었습니다.");
    } catch (error) {
      onMessage?.(error instanceof Error ? error.message : "버전 메타데이터 생성에 실패했습니다.");
    } finally {
      setGeneratingVersionMetadataId(null);
    }
  }

  return (
    <article className={`blog-clip-item clip-${blogClip.status}`}>
      <h4>{blogClip.blog_title ?? "블로그 쇼츠"}</h4>
      <p className="muted">{blogClip.source_url}</p>
      <div className="highlight-meta">
        <span className={`status-badge status-${blogClip.status}`}>{BLOG_CLIP_STATUS_LABELS[blogClip.status]}</span>
        <span>자막: {SUBTITLE_STYLE_LABELS[blogClip.subtitle_style as SubtitleStyle] ?? blogClip.subtitle_style}</span>
        {blogClip.script_tone ? <span>톤: {SCRIPT_TONE_LABELS[blogClip.script_tone]}</span> : null}
      </div>
      {isInProgress ? (
        <div className="blog-progress" aria-live="polite">
          <div className="blog-progress-track">
            <div className="blog-progress-fill" style={{ width: `${blogClip.progress_percent}%` }} />
          </div>
          <span className="blog-progress-label">
            {stageLabel} ({blogClip.progress_percent}%)
          </span>
        </div>
      ) : null}
      {isAwaitingScript ? (
        <div className="script-tone-picker" aria-label="나레이션 대본 톤 선택">
          <p className="script-tone-intro">나레이션 톤을 선택하면 이미지별 보드가 자동 생성됩니다.</p>
          <div className="script-tone-list">
            {availableTones.map((tone) => (
              <div className="script-tone-option" key={tone}>
                <div className="script-tone-header">
                  <strong>{SCRIPT_TONE_LABELS[tone]}</strong>
                  <span className="muted">{SCRIPT_TONE_HINTS[tone]}</span>
                </div>
                <p className="narration-script">{blogClip.script_candidates[tone]}</p>
                <button
                  className="small-button"
                  type="button"
                  onClick={() => onSelectScript(blogClip, tone)}
                  disabled={selectingBlogScriptId === blogClip.id}
                >
                  {selectingBlogScriptId === blogClip.id ? "선택 중" : "이 대본으로 만들기"}
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {isAwaitingBoards ? (
        <div className="board-render-shim" aria-label="보드 편집">
          <p className="script-tone-intro">
            {boardCount ? `보드 ${boardCount}개 준비됨` : "보드가 준비되었습니다"} — 편집 후 렌더링을 시작하세요.
          </p>
          <button className="small-button" type="button" onClick={() => onOpenBoardEditor(blogClip)}>
            보드 편집
          </button>
        </div>
      ) : null}
      {!isAwaitingScript && !isAwaitingBoards && blogClip.narration_script ? (
        <p className="narration-script">{blogClip.narration_script}</p>
      ) : null}
      {blogClip.error_message ? <p className="error-text">{blogClip.error_message}</p> : null}
      {canDownload ? (
        <div className="subtitle-controls">
          <button
            className="small-button ghost-small"
            type="button"
            onClick={() => onDownloadBlogClip(blogClip)}
            disabled={downloadingBlogClipId === blogClip.id}
          >
            {downloadingBlogClipId === blogClip.id ? "다운로드 중" : "활성 버전 다운로드"}
          </button>
          <button
            className="small-button metadata-button"
            type="button"
            onClick={() => onGenerateMetadata(blogClip)}
            disabled={generatingBlogMetadataId === blogClip.id || hasMetadata}
          >
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

      {isCompleted ? (
        <div className="blog-version-panel" aria-label="버전 목록">
          <div className="blog-version-header">
            <strong>버전</strong>
            <div className="blog-version-actions">
              <button
                className="small-button ghost-small"
                type="button"
                onClick={() => void handleCreateVersions("all_tones")}
                disabled={creatingVersions}
              >
                {creatingVersions ? "생성 중" : "다른 톤 만들기"}
              </button>
              <button
                className="small-button ghost-small"
                type="button"
                onClick={() => void handleCreateVersions("boards")}
                disabled={creatingVersions}
              >
                보드 재생성
              </button>
            </div>
          </div>
          {versionsLoading && versions.length === 0 ? <p className="muted">버전 불러오는 중…</p> : null}
          {versions.length === 0 && !versionsLoading ? <p className="muted">아직 버전이 없습니다.</p> : null}
          <ul className="blog-version-list">
            {versions.map((version) => {
              const versionCanDownload = Boolean(version.subtitled_video_path || version.video_path);
              const versionBusy = version.status === "pending" || version.status === "processing";
              const versionHasMetadata = version.title_candidates.length > 0;
              const versionStage = BLOG_PROGRESS_STAGE_LABELS[version.progress_stage] ?? version.progress_stage;
              return (
                <li className="blog-version-item" key={version.id}>
                  <div className="blog-version-row">
                    <div>
                      <span className="blog-version-label">
                        {version.label}
                        {version.is_active ? " · 활성" : ""}
                      </span>
                      <span className="muted">
                        {" "}
                        · {BLOG_CLIP_STATUS_LABELS[version.status] ?? version.status}
                        {versionBusy ? ` (${versionStage} ${version.progress_percent}%)` : ""}
                      </span>
                    </div>
                    <div className="blog-version-row-actions">
                      {versionCanDownload ? (
                        <button
                          className="small-button ghost-small"
                          type="button"
                          onClick={() => void handleDownloadVersion(version)}
                          disabled={downloadingVersionId === version.id}
                        >
                          {downloadingVersionId === version.id ? "다운로드 중" : "다운로드"}
                        </button>
                      ) : null}
                      {version.status === "completed" && !version.is_active ? (
                        <button className="small-button ghost-small" type="button" onClick={() => void handleSetActive(version)}>
                          활성으로
                        </button>
                      ) : null}
                      {version.status === "completed" ? (
                        <button
                          className="small-button metadata-button"
                          type="button"
                          onClick={() => void handleGenerateVersionMetadata(version)}
                          disabled={generatingVersionMetadataId === version.id || versionHasMetadata}
                        >
                          {generatingVersionMetadataId === version.id
                            ? "작성 중"
                            : versionHasMetadata
                              ? "메타 준비됨"
                              : "메타데이터"}
                        </button>
                      ) : null}
                      {versionHasMetadata ? (
                        <button
                          className="small-button ghost-small"
                          type="button"
                          onClick={() => setExpandedVersionId((current) => (current === version.id ? null : version.id))}
                        >
                          {expandedVersionId === version.id ? "메타 접기" : "메타 보기"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  {version.error_message ? <p className="error-text">{version.error_message}</p> : null}
                  {version.metadata_error ? <p className="error-text">{version.metadata_error}</p> : null}
                  {expandedVersionId === version.id && versionHasMetadata ? (
                    <MetadataBox
                      copiedKey={copiedKey}
                      idPrefix={`blog-${blogClip.id}-v${version.id}`}
                      titleCandidates={version.title_candidates}
                      description={version.description ?? ""}
                      hashtags={version.hashtags}
                      onCopyText={onCopyText}
                    />
                  ) : null}
                  {version.status === "completed" ? (
                    <RenderSpecFooter spec={version.render_spec} title={`버전 #${version.id} 스펙 (임시)`} />
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {isCompleted || canDownload ? (
        <RenderSpecFooter spec={blogClip.render_spec} title="활성 결과 스펙 (임시)" />
      ) : null}
    </article>
  );
}
