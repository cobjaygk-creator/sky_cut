import type { Clip, ClipMetadata, Highlight, SubtitleStyle, TtsMode } from "../types";
import { formatTime } from "../utils/format";
import { ClipSummary } from "./ClipSummary";

export function HighlightList({
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
              <span>
                {formatTime(highlight.start_time)}-{formatTime(highlight.end_time)}
              </span>
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
