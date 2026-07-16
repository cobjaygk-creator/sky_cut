import { CLIP_STATUS_LABELS, SUBTITLE_STYLE_LABELS, SUBTITLE_STYLES, TTS_MODE_LABELS, TTS_MODES } from "../constants";
import type { Clip, ClipMetadata, SubtitleStyle, TtsMode } from "../types";
import { MetadataBox } from "./MetadataBox";

export function ClipSummary({
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
      {clip.narrated_output_path ? (
        <span>{clip.narrated_output_path}</span>
      ) : clip.subtitled_output_path ? (
        <span>{clip.subtitled_output_path}</span>
      ) : clip.output_path ? (
        <span>{clip.output_path}</span>
      ) : null}
      {clip.error_message ? <span className="error-text">{clip.error_message}</span> : null}
      {canUseClip ? (
        <>
          <div className="subtitle-controls">
            <label>
              자막 스타일
              <select value={selectedStyle} onChange={(event) => onStyleChange(clip.id, event.target.value as SubtitleStyle)}>
                {SUBTITLE_STYLES.map((style) => (
                  <option value={style} key={style}>
                    {SUBTITLE_STYLE_LABELS[style]}
                  </option>
                ))}
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
                {TTS_MODES.map((mode) => (
                  <option value={mode} key={mode}>
                    {TTS_MODE_LABELS[mode]}
                  </option>
                ))}
              </select>
            </label>
            <button className="small-button" type="button" onClick={() => onApplyNarration(clip)} disabled={narratingClipId === clip.id}>
              {narratingClipId === clip.id ? "적용 중" : "음성 적용"}
            </button>
          </div>
          {clip.narration_script ? <p className="narration-script">{clip.narration_script}</p> : null}
          <button
            className="small-button metadata-button"
            type="button"
            onClick={() => onGenerateMetadata(clip)}
            disabled={generatingMetadataId === clip.id || Boolean(metadata)}
          >
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
