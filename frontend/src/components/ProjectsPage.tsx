import { useMemo, useState } from "react";
import { BLOG_CLIP_STATUS_LABELS, SCRIPT_TONE_LABELS } from "../constants";
import type {
  BlogClip,
  Clip,
  ClipMetadata,
  Highlight,
  ScriptTone,
  SubtitleStyle,
  Transcript,
  TtsMode,
  Video,
} from "../types";
import { VideoList } from "./VideoList";

const WIZARD_STEP_LABELS = {
  video_style: "스타일",
  edit_mode: "편집",
  quick: "퀵설정",
  ready: "완료",
  boards: "편집",
  voice: "편집",
  style: "편집",
} as const;

type ProjectTab = "shorts" | "videos";

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function ProjectsPage({
  blogClips,
  videos,
  transcripts,
  highlights,
  clips,
  clipMetadata,
  copiedKey,
  creatingClipId,
  downloadingClipId,
  generatingMetadataId,
  narratingClipId,
  subtitleStyles,
  ttsModes,
  subtitlingClipId,
  analyzingId,
  transcribingId,
  highlightingId,
  onOpenBlogClip,
  onCreateNew,
  onAnalyze,
  onTranscript,
  onHighlights,
  onRefreshStatus,
  onApplyNarration,
  onBurnSubtitles,
  onCreateClip,
  onCopyText,
  onDownloadClip,
  onGenerateMetadata,
  onStyleChange,
  onTtsModeChange,
}: {
  blogClips: BlogClip[];
  videos: Video[];
  transcripts: Record<number, Transcript>;
  highlights: Record<number, Highlight[]>;
  clips: Record<number, Clip>;
  clipMetadata: Record<number, ClipMetadata>;
  copiedKey: string | null;
  creatingClipId: number | null;
  downloadingClipId: number | null;
  generatingMetadataId: number | null;
  narratingClipId: number | null;
  subtitleStyles: Record<number, SubtitleStyle>;
  ttsModes: Record<number, TtsMode>;
  subtitlingClipId: number | null;
  analyzingId: number | null;
  transcribingId: number | null;
  highlightingId: number | null;
  onOpenBlogClip: (blogClip: BlogClip) => void;
  onCreateNew: () => void;
  onAnalyze: (videoId: number) => void;
  onTranscript: (videoId: number) => void;
  onHighlights: (videoId: number) => void;
  onRefreshStatus: (videoId: number) => void;
  onApplyNarration: (clip: Clip) => void;
  onBurnSubtitles: (clip: Clip) => void;
  onCreateClip: (highlightId: number) => void;
  onCopyText: (key: string, text: string) => void;
  onDownloadClip: (clip: Clip) => void;
  onGenerateMetadata: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
  onTtsModeChange: (clipId: number, mode: TtsMode) => void;
}) {
  const [tab, setTab] = useState<ProjectTab>("shorts");
  const [query, setQuery] = useState("");

  const filteredBlogClips = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return blogClips;
    return blogClips.filter((clip) => {
      const title = (clip.blog_title ?? "").toLowerCase();
      const url = clip.source_url.toLowerCase();
      return title.includes(q) || url.includes(q);
    });
  }, [blogClips, query]);

  const filteredVideos = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return videos;
    return videos.filter((video) => video.original_filename.toLowerCase().includes(q));
  }, [videos, query]);

  return (
    <section className="projects-page" aria-label="프로젝트">
      <div className="projects-panel">
        <header className="projects-header">
          <div>
            <h1 className="projects-title">프로젝트</h1>
            <p className="projects-lead">만든 쇼츠와 영상 프로젝트를 이어서 편집하세요.</p>
          </div>
          <button className="btn-primary" type="button" onClick={onCreateNew}>
            새 프로젝트
          </button>
        </header>

        <div className="projects-toolbar">
          <div className="projects-tabs" role="tablist" aria-label="프로젝트 종류">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "shorts"}
              className={`projects-tab ${tab === "shorts" ? "is-active" : ""}`}
              onClick={() => setTab("shorts")}
            >
              블로그 쇼츠
              <span className="projects-tab-count">{blogClips.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "videos"}
              className={`projects-tab ${tab === "videos" ? "is-active" : ""}`}
              onClick={() => setTab("videos")}
            >
              영상
              <span className="projects-tab-count">{videos.length}</span>
            </button>
          </div>
          <label className="projects-search">
            <span className="sr-only">프로젝트 검색</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="제목 또는 URL 검색"
            />
          </label>
        </div>

        {tab === "shorts" ? (
          filteredBlogClips.length === 0 ? (
            <div className="projects-empty">
              <p>{blogClips.length === 0 ? "아직 만든 프로젝트가 없습니다." : "검색 결과가 없습니다."}</p>
              {blogClips.length === 0 ? (
                <button className="btn-outline" type="button" onClick={onCreateNew}>
                  새 프로젝트 만들기 →
                </button>
              ) : null}
            </div>
          ) : (
            <ul className="projects-list">
              {filteredBlogClips.map((blogClip) => (
                <li key={blogClip.id}>
                  <button className="projects-row" type="button" onClick={() => onOpenBlogClip(blogClip)}>
                    <div className="projects-row-main">
                      <strong>{blogClip.blog_title ?? "제목 없는 쇼츠"}</strong>
                      <span className="projects-row-meta">
                        {formatDate(blogClip.updated_at || blogClip.created_at)}
                        {blogClip.script_tone ? ` · ${SCRIPT_TONE_LABELS[blogClip.script_tone as ScriptTone]}` : ""}
                        {blogClip.status === "awaiting_boards" && blogClip.wizard_step
                          ? ` · ${WIZARD_STEP_LABELS[blogClip.wizard_step]}`
                          : ""}
                      </span>
                    </div>
                    <div className="projects-row-aside">
                      <span className={`status-badge status-${blogClip.status}`}>
                        {BLOG_CLIP_STATUS_LABELS[blogClip.status]}
                      </span>
                      <span className="projects-row-open">열기</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : filteredVideos.length === 0 ? (
          <div className="projects-empty">
            <p>{videos.length === 0 ? "아직 가져온 영상이 없습니다." : "검색 결과가 없습니다."}</p>
            {videos.length === 0 ? (
              <button className="btn-outline" type="button" onClick={onCreateNew}>
                새 프로젝트 만들기 →
              </button>
            ) : null}
          </div>
        ) : (
          <div className="projects-video-wrap">
            <VideoList
              videos={filteredVideos}
              transcripts={transcripts}
              highlights={highlights}
              clips={clips}
              clipMetadata={clipMetadata}
              copiedKey={copiedKey}
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
              onAnalyze={onAnalyze}
              onTranscript={onTranscript}
              onHighlights={onHighlights}
              onRefreshStatus={onRefreshStatus}
              onApplyNarration={onApplyNarration}
              onBurnSubtitles={onBurnSubtitles}
              onCreateClip={onCreateClip}
              onCopyText={onCopyText}
              onDownloadClip={onDownloadClip}
              onGenerateMetadata={onGenerateMetadata}
              onStyleChange={onStyleChange}
              onTtsModeChange={onTtsModeChange}
            />
          </div>
        )}
      </div>
    </section>
  );
}
