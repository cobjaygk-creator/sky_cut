import type { RenderSpec } from "../types";

function formatBytes(bytes: number | null | undefined): string | null {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function engineLabel(engine: string | undefined): string {
  if (engine === "remotion") return "Remotion";
  if (engine === "ffmpeg") return "FFmpeg";
  return engine || "unknown";
}

export function RenderSpecFooter({
  spec,
  title = "렌더 스펙 (임시)",
}: {
  spec: RenderSpec | null | undefined;
  title?: string;
}) {
  if (!spec) return null;

  const size = formatBytes(spec.output_bytes);
  const rows: Array<[string, string]> = [
    ["엔진", engineLabel(spec.engine)],
    ["요청 엔진", engineLabel(spec.requested_engine)],
    ["폴백", spec.fallback_used ? "예 (Remotion → FFmpeg)" : "아니오"],
    ["자막", spec.captions === "remotion" ? "Remotion 합성" : spec.captions === "ass" ? "ASS burn-in" : spec.captions || "—"],
    ["해상도", spec.resolution || "—"],
    ["FPS", spec.fps != null ? String(spec.fps) : "—"],
    ["보드", spec.board_count != null ? `${spec.board_count}개` : "—"],
    ["길이", spec.duration_seconds != null ? `${spec.duration_seconds}s` : "—"],
    ["TTS 속도", spec.tts_speed != null ? String(spec.tts_speed) : "—"],
    [
      "BGM",
      spec.bgm
        ? `있음${spec.bgm_volume != null ? ` (vol ${spec.bgm_volume})` : ""}`
        : "없음",
    ],
    ["SFX 보드", spec.sfx_boards != null ? `${spec.sfx_boards}개` : "—"],
  ];
  if (size) rows.push(["파일 크기", size]);
  if (spec.output_file) rows.push(["파일명", spec.output_file]);
  if (spec.fallback_reason) rows.push(["폴백 사유", spec.fallback_reason]);

  return (
    <details className="render-spec-footer">
      <summary>
        {title}: <strong>{engineLabel(spec.engine)}</strong>
        {spec.fallback_used ? " · fallback" : ""}
        {spec.duration_seconds != null ? ` · ${spec.duration_seconds}s` : ""}
        {spec.resolution ? ` · ${spec.resolution}` : ""}
      </summary>
      <dl className="render-spec-grid">
        {rows.map(([label, value]) => (
          <div className="render-spec-row" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
