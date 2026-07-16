import { useState, type FormEvent } from "react";
import type {
  BlogClip,
  Clip,
  ClipMetadata,
  Highlight,
  Plan,
  NarrationLanguage,
  ScriptModel,
  SubtitleStyle,
  TargetLength,
  Transcript,
  TtsMode,
  Usage,
  User,
  Video,
} from "../types";
import { CreateStudio, type CreateSource } from "./CreateStudio";
import { ProjectsPage } from "./ProjectsPage";

type StudioNav = "create" | "projects";

export function Dashboard({
  user,
  usage,
  plans,
  uploadMessage,
  selectedFile,
  isUploading,
  youtubeUrl,
  isImportingYoutube,
  blogUrl,
  blogSubtitleStyle,
  blogTargetLength,
  blogNarrationLanguage,
  blogScriptModel,
  isCreatingBlogShort,
  blogClips,
  copiedKey,
  videos,
  transcripts,
  highlights,
  clips,
  clipMetadata,
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
  onLogout,
  onUpload,
  onSelectedFileChange,
  onImportYoutube,
  onYoutubeUrlChange,
  onCreateBlogShort,
  onBlogUrlChange,
  onBlogSubtitleStyleChange,
  onBlogTargetLengthChange,
  onBlogNarrationLanguageChange,
  onBlogScriptModelChange,
  onCopyText,
  onOpenBlogClip,
  onAnalyze,
  onTranscript,
  onHighlights,
  onRefreshStatus,
  onApplyNarration,
  onBurnSubtitles,
  onCreateClip,
  onDownloadClip,
  onGenerateMetadata,
  onStyleChange,
  onTtsModeChange,
}: {
  user: User;
  usage: Usage | null;
  plans: Plan[];
  uploadMessage: string;
  selectedFile: File | null;
  isUploading: boolean;
  youtubeUrl: string;
  isImportingYoutube: boolean;
  blogUrl: string;
  blogSubtitleStyle: SubtitleStyle;
  blogTargetLength: TargetLength;
  blogNarrationLanguage: NarrationLanguage;
  blogScriptModel: ScriptModel;
  isCreatingBlogShort: boolean;
  blogClips: BlogClip[];
  copiedKey: string | null;
  videos: Video[];
  transcripts: Record<number, Transcript>;
  highlights: Record<number, Highlight[]>;
  clips: Record<number, Clip>;
  clipMetadata: Record<number, ClipMetadata>;
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
  onLogout: () => void;
  onUpload: (event: FormEvent<HTMLFormElement>) => void;
  onSelectedFileChange: (file: File | null) => void;
  onImportYoutube: (event: FormEvent<HTMLFormElement>) => void;
  onYoutubeUrlChange: (value: string) => void;
  onCreateBlogShort: (event: FormEvent<HTMLFormElement>) => void;
  onBlogUrlChange: (value: string) => void;
  onBlogSubtitleStyleChange: (value: SubtitleStyle) => void;
  onBlogTargetLengthChange: (value: TargetLength) => void;
  onBlogNarrationLanguageChange: (value: NarrationLanguage) => void;
  onBlogScriptModelChange: (value: ScriptModel) => void;
  onCopyText: (key: string, text: string) => void;
  onOpenBlogClip: (blogClip: BlogClip) => void;
  onAnalyze: (videoId: number) => void;
  onTranscript: (videoId: number) => void;
  onHighlights: (videoId: number) => void;
  onRefreshStatus: (videoId: number) => void;
  onApplyNarration: (clip: Clip) => void;
  onBurnSubtitles: (clip: Clip) => void;
  onCreateClip: (highlightId: number) => void;
  onDownloadClip: (clip: Clip) => void;
  onGenerateMetadata: (clip: Clip) => void;
  onStyleChange: (clipId: number, style: SubtitleStyle) => void;
  onTtsModeChange: (clipId: number, mode: TtsMode) => void;
}) {
  const [nav, setNav] = useState<StudioNav>("create");
  const [source, setSource] = useState<CreateSource>("blog");
  const activePlan = plans.find((plan) => plan.id === usage?.plan);

  return (
    <div className="studio">
      <header className="studio-topbar">
        <div className="studio-topbar-left">
          <div className="studio-brand">
            <span className="brand-mark" aria-hidden="true" />
            <strong className="brand-name">New Cut</strong>
          </div>
          <nav className="studio-nav" aria-label="스튜디오 메뉴">
            <button
              type="button"
              className={`studio-nav-link ${nav === "create" ? "is-active" : ""}`}
              onClick={() => setNav("create")}
            >
              만들기
            </button>
            <button
              type="button"
              className={`studio-nav-link ${nav === "projects" ? "is-active" : ""}`}
              onClick={() => setNav("projects")}
            >
              프로젝트
              {blogClips.length + videos.length > 0 ? (
                <span className="studio-nav-count">{blogClips.length + videos.length}</span>
              ) : null}
            </button>
          </nav>
        </div>
        <div className="studio-topbar-meta">
          <div className="usage-chip" title={activePlan?.name}>
            <span>{usage?.plan_name ?? "요금제"}</span>
            <strong>{usage ? `${usage.monthly_usage}/${usage.usage_limit}` : "—"}</strong>
          </div>
          <span className="account-chip">{user.email}</span>
          <button className="btn-ghost" type="button" onClick={onLogout}>
            로그아웃
          </button>
        </div>
      </header>

      <main className="studio-main">
        {nav === "create" ? (
          <>
            <CreateStudio
              source={source}
              onSourceChange={setSource}
              blogUrl={blogUrl}
              blogSubtitleStyle={blogSubtitleStyle}
              blogTargetLength={blogTargetLength}
              blogNarrationLanguage={blogNarrationLanguage}
              blogScriptModel={blogScriptModel}
              isCreatingBlogShort={isCreatingBlogShort}
              youtubeUrl={youtubeUrl}
              isImportingYoutube={isImportingYoutube}
              selectedFile={selectedFile}
              isUploading={isUploading}
              onBlogUrlChange={onBlogUrlChange}
              onBlogSubtitleStyleChange={onBlogSubtitleStyleChange}
              onBlogTargetLengthChange={onBlogTargetLengthChange}
              onBlogNarrationLanguageChange={onBlogNarrationLanguageChange}
              onBlogScriptModelChange={onBlogScriptModelChange}
              onCreateBlogShort={onCreateBlogShort}
              onYoutubeUrlChange={onYoutubeUrlChange}
              onImportYoutube={onImportYoutube}
              onSelectedFileChange={onSelectedFileChange}
              onUpload={onUpload}
            />
            {uploadMessage ? (
              <p className="studio-toast" role="status">
                {uploadMessage}
              </p>
            ) : null}
          </>
        ) : (
          <>
            {uploadMessage ? (
              <p className="studio-toast" role="status">
                {uploadMessage}
              </p>
            ) : null}
            <ProjectsPage
              blogClips={blogClips}
              videos={videos}
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
              onOpenBlogClip={onOpenBlogClip}
              onCreateNew={() => setNav("create")}
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
          </>
        )}
      </main>
    </div>
  );
}
