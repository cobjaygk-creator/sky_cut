import { useEffect, useState } from "react";
import {
  BLOG_CLIP_STATUS_LABELS,
  BLOG_PROGRESS_STAGE_LABELS,
  SCRIPT_TONE_HINTS,
  SCRIPT_TONE_LABELS,
  SCRIPT_TONES,
  SUBTITLE_STYLE_LABELS,
} from "../constants";
import type { BlogClip, ScriptTone, SubtitleStyle, WizardBoardsStep } from "../types";
import { parseWizardBoardsStep } from "../types";
import { BlogClipCard } from "./BlogClipCard";
import { ImageSelectStep } from "./ImageSelectStep";
import { QuickSettingsStep } from "./QuickSettingsStep";

const FLOW_STEPS = [
  { id: "progress", label: "준비" },
  { id: "images", label: "이미지" },
  { id: "script", label: "대본" },
  { id: "edit", label: "편집" },
  { id: "done", label: "완료" },
] as const;

const PHASE2_STAGES = new Set([
  "synthesizing_audio",
  "rendering_video",
  "burning_subtitles",
]);

function isPhase2Render(blogClip: BlogClip): boolean {
  if (blogClip.status !== "pending" && blogClip.status !== "processing") return false;
  if (blogClip.progress_percent >= 55) return true;
  return PHASE2_STAGES.has(blogClip.progress_stage);
}

function bgmSummary(blogClip: BlogClip): string {
  if (blogClip.bgm_asset_id != null) return `BGM #${blogClip.bgm_asset_id}`;
  if (blogClip.auto_bgm) return "자동 BGM";
  return "BGM 없음";
}

export function BlogClipFlow({
  blogClip,
  boardCount,
  copiedKey,
  downloadingBlogClipId,
  generatingBlogMetadataId,
  selectingBlogScriptId,
  confirmingImageSelection,
  savingVoice,
  savingStyle,
  renderingFromFlow,
  onBackToStudio,
  onCopyText,
  onDownloadBlogClip,
  onGenerateMetadata,
  onSelectScript,
  onConfirmImages,
  onSaveDefaultVoice,
  onApplyTemplate,
  onAudioSettings,
  onWizardStepChange,
  onRender,
  onOpenBoardEditor,
  onBlogClipUpdated,
  onMessage,
}: {
  blogClip: BlogClip;
  boardCount?: number;
  copiedKey: string | null;
  downloadingBlogClipId: number | null;
  generatingBlogMetadataId: number | null;
  selectingBlogScriptId: number | null;
  confirmingImageSelection: boolean;
  savingVoice: boolean;
  savingStyle: boolean;
  renderingFromFlow: boolean;
  onBackToStudio: () => void;
  onCopyText: (key: string, text: string) => void;
  onDownloadBlogClip: (blogClip: BlogClip) => void;
  onGenerateMetadata: (blogClip: BlogClip) => void;
  onSelectScript: (blogClip: BlogClip, tone: ScriptTone) => void;
  onConfirmImages: (blogClip: BlogClip, imageIds: number[]) => void;
  onSaveDefaultVoice: (blogClip: BlogClip, voiceId: string, ttsSpeed: number) => Promise<void>;
  onApplyTemplate: (blogClip: BlogClip, templateId: number) => Promise<void>;
  onAudioSettings: (
    blogClip: BlogClip,
    body: { auto_bgm?: boolean; auto_sfx?: boolean; bgm_asset_id?: number | null },
  ) => Promise<void>;
  onWizardStepChange: (blogClip: BlogClip, step: WizardBoardsStep) => void;
  onRender: (blogClip: BlogClip) => void;
  onOpenBoardEditor: (blogClip: BlogClip) => void;
  onBlogClipUpdated: (blogClip: BlogClip) => void;
  onMessage: (message: string) => void;
}) {
  const [boardsStep, setBoardsStep] = useState<WizardBoardsStep>(() => parseWizardBoardsStep(blogClip.wizard_step));

  useEffect(() => {
    if (blogClip.status === "awaiting_boards") {
      setBoardsStep(parseWizardBoardsStep(blogClip.wizard_step));
    }
  }, [blogClip.id, blogClip.status, blogClip.wizard_step]);

  const isProgress = blogClip.status === "pending" || blogClip.status === "processing";
  const isFinalRender = isPhase2Render(blogClip);
  const isAwaitingImages = blogClip.status === "awaiting_images";
  const isAwaitingScript = blogClip.status === "awaiting_script";
  const isAwaitingBoards = blogClip.status === "awaiting_boards";
  const isCompleted = blogClip.status === "completed";
  const isFailed = blogClip.status === "failed";
  const stageLabel = BLOG_PROGRESS_STAGE_LABELS[blogClip.progress_stage] ?? blogClip.progress_stage;
  const availableTones = SCRIPT_TONES.filter((tone) => Boolean(blogClip.script_candidates[tone]));

  const stepIndex = isFinalRender
    ? 4
    : isProgress
      ? 0
      : isAwaitingImages
        ? 1
        : isAwaitingScript
          ? 2
          : isAwaitingBoards
            ? 3
            : isCompleted || isFailed
              ? 4
              : 0;

  const stepperSteps = FLOW_STEPS.map((step, index) => {
    if (index === 4 && isFinalRender) return { ...step, label: "렌더 중" };
    return step;
  });

  function goToBoardsStep(step: WizardBoardsStep) {
    if (!isAwaitingBoards || boardsStep === step) return;
    setBoardsStep(step);
    onWizardStepChange(blogClip, step);
  }

  function handleStepperClick(index: number) {
    if (!isAwaitingBoards) return;
    if (index === 3) goToBoardsStep("edit_mode");
  }

  return (
    <div className="flow-shell">
      <header className="flow-topbar">
        <button className="ghost-button" type="button" onClick={onBackToStudio}>
          ← 작업실로
        </button>
        <div className="flow-brand">
          <strong>New Cut</strong>
          <span>쇼츠 제작</span>
        </div>
        <span className={`status-badge status-${blogClip.status}`}>
          {BLOG_CLIP_STATUS_LABELS[blogClip.status]}
        </span>
      </header>

      <div className="flow-body">
        <aside className="flow-stepper" aria-label="제작 단계">
          <p className="flow-stepper-title">진행 단계</p>
          <ol className="flow-stepper-list">
            {stepperSteps.map((step, index) => {
              const isCurrent = index === stepIndex;
              const isDone = index < stepIndex;
              const canJump = isAwaitingBoards && index === 3;
              const className = `flow-stepper-item ${isCurrent ? "is-current" : ""} ${isDone ? "is-done" : ""} ${canJump ? "is-clickable" : ""}`;
              if (canJump) {
                return (
                  <li key={step.id}>
                    <button
                      type="button"
                      className={className}
                      aria-current={isCurrent ? "step" : undefined}
                      onClick={() => handleStepperClick(index)}
                    >
                      <span className="flow-step-dot">{index + 1}</span>
                      <span>{step.label}</span>
                    </button>
                  </li>
                );
              }
              return (
                <li key={step.id}>
                  <div className={className} aria-current={isCurrent ? "step" : undefined}>
                    <span className="flow-step-dot">{index + 1}</span>
                    <span>{step.label}</span>
                  </div>
                </li>
              );
            })}
          </ol>
        </aside>

        <main className="flow-main">
          {isProgress ? (
            <section className="flow-card flow-progress-card" aria-live="polite">
              <p className="create-kicker">{isFinalRender ? "렌더 중" : "준비 중"}</p>
              <h1>{isFinalRender ? "영상을 만들고 있어요" : "쇼츠를 준비하고 있어요"}</h1>
              <p className="flow-lead">
                {isFinalRender
                  ? "음성·BGM을 섞은 뒤 세로 영상을 합성하는 중입니다."
                  : "글을 읽고 이미지 후보와 대본을 준비하는 중입니다."}
              </p>
              <div className="flow-progress">
                <div className="blog-progress-track">
                  <div className="blog-progress-fill" style={{ width: `${blogClip.progress_percent}%` }} />
                </div>
                <span className="blog-progress-label">
                  {stageLabel} · {blogClip.progress_percent}%
                </span>
              </div>
              <p className="create-note flow-url">{blogClip.source_url}</p>
            </section>
          ) : null}

          {isAwaitingImages ? (
            <ImageSelectStep
              blogClip={blogClip}
              confirming={confirmingImageSelection}
              onConfirm={(imageIds) => onConfirmImages(blogClip, imageIds)}
              onMessage={onMessage}
            />
          ) : null}

          {isAwaitingScript ? (
            <section className="flow-card">
              <p className="create-kicker">대본 선택</p>
              <h1>{blogClip.blog_title ?? "나레이션 톤을 고르세요"}</h1>
              <p className="flow-lead">세 가지 톤 중 하나로 보드를 만듭니다. 나중에 다른 톤 버전도 만들 수 있어요.</p>
              <div className="script-tone-list">
                {availableTones.map((tone) => (
                  <div className="script-tone-option" key={tone}>
                    <div className="script-tone-header">
                      <strong>{SCRIPT_TONE_LABELS[tone]}</strong>
                      <span className="muted">{SCRIPT_TONE_HINTS[tone]}</span>
                    </div>
                    <p className="narration-script">{blogClip.script_candidates[tone]}</p>
                    <button
                      className="cta-button"
                      type="button"
                      onClick={() => onSelectScript(blogClip, tone)}
                      disabled={selectingBlogScriptId === blogClip.id}
                    >
                      {selectingBlogScriptId === blogClip.id ? "선택 중…" : "이 대본으로 계속"}
                    </button>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {isAwaitingBoards && boardsStep === "edit_mode" ? (
            <section className="flow-card flow-boards-card">
              <p className="create-kicker">편집 모드</p>
              <h1>어떻게 만들까요?</h1>
              <p className="flow-lead">보드를 직접 다듬거나, 기본값으로 빠르게 만들 수 있어요.</p>
              <div className="highlight-meta">
                <span>{boardCount ? `보드 ${boardCount}개` : "보드 준비됨"}</span>
                <span>자막: {SUBTITLE_STYLE_LABELS[blogClip.subtitle_style as SubtitleStyle] ?? blogClip.subtitle_style}</span>
                {blogClip.script_tone ? <span>톤: {SCRIPT_TONE_LABELS[blogClip.script_tone]}</span> : null}
              </div>
              <div className="flow-step-actions">
                <button className="ghost-button" type="button" onClick={() => goToBoardsStep("quick")}>
                  퀵 모드
                </button>
                <button className="cta-button flow-primary-cta" type="button" onClick={() => onOpenBoardEditor(blogClip)}>
                  세부 편집
                </button>
              </div>
            </section>
          ) : null}

          {isAwaitingBoards && boardsStep === "quick" ? (
            <QuickSettingsStep
              blogClip={blogClip}
              savingVoice={savingVoice}
              busy={savingStyle || renderingFromFlow}
              onSaveDefaultVoice={(voiceId, ttsSpeed) => onSaveDefaultVoice(blogClip, voiceId, ttsSpeed)}
              onApplyTemplate={(templateId) => onApplyTemplate(blogClip, templateId)}
              onAudioSettings={(body) => onAudioSettings(blogClip, body)}
              onBack={() => goToBoardsStep("edit_mode")}
              onRender={() => onRender(blogClip)}
              onMessage={onMessage}
            />
          ) : null}

          {isAwaitingBoards && boardsStep === "ready" ? (
            <section className="flow-card flow-boards-card">
              <p className="create-kicker">렌더 확인</p>
              <h1>이 설정으로 만들까요?</h1>
              <p className="flow-lead">세부 편집이 반영되었습니다. 확인 후 렌더링을 시작하세요.</p>
              <div className="highlight-meta">
                <span>{boardCount ? `보드 ${boardCount}개` : "보드"}</span>
                <span>보이스: {blogClip.default_voice ?? "기본"}</span>
                <span>{bgmSummary(blogClip)}</span>
                {blogClip.auto_sfx ? <span>자동 SFX</span> : null}
              </div>
              <div className="flow-step-actions">
                <button className="ghost-button" type="button" onClick={() => onOpenBoardEditor(blogClip)}>
                  세부 편집으로 돌아가기
                </button>
                <button
                  className="cta-button flow-primary-cta"
                  type="button"
                  disabled={renderingFromFlow}
                  onClick={() => onRender(blogClip)}
                >
                  {renderingFromFlow ? "시작 중…" : "렌더링"}
                </button>
              </div>
            </section>
          ) : null}

          {isFailed ? (
            <section className="flow-card">
              <p className="create-kicker">실패</p>
              <h1>생성에 실패했습니다</h1>
              <p className="error-text">{blogClip.error_message ?? "알 수 없는 오류가 발생했습니다."}</p>
              <button className="cta-button" type="button" onClick={onBackToStudio}>
                작업실로 돌아가기
              </button>
            </section>
          ) : null}

          {isCompleted ? (
            <section className="flow-result">
              <div className="flow-card flow-result-hero">
                <p className="create-kicker">완료</p>
                <h1>{blogClip.blog_title ?? "쇼츠가 완성되었습니다"}</h1>
                <p className="flow-lead">다운로드·메타데이터·다른 톤 버전은 아래에서 이어서 할 수 있어요.</p>
              </div>
              <BlogClipCard
                blogClip={blogClip}
                copiedKey={copiedKey}
                downloadingBlogClipId={downloadingBlogClipId}
                generatingBlogMetadataId={generatingBlogMetadataId}
                selectingBlogScriptId={selectingBlogScriptId}
                blogBoardCounts={boardCount != null ? { [blogClip.id]: boardCount } : {}}
                onCopyText={onCopyText}
                onDownloadBlogClip={onDownloadBlogClip}
                onGenerateMetadata={onGenerateMetadata}
                onSelectScript={onSelectScript}
                onOpenBoardEditor={onOpenBoardEditor}
                onBlogClipUpdated={onBlogClipUpdated}
                onMessage={onMessage}
              />
              <button className="ghost-button flow-back-bottom" type="button" onClick={onBackToStudio}>
                작업실로 돌아가기
              </button>
            </section>
          ) : null}
        </main>
      </div>
    </div>
  );
}
