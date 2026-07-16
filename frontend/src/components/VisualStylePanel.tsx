import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import type { VisualStyle, VisualStyleSlug } from "../types";

/** Compact visual-style picker for BoardEditor media panel. */
export function VisualStylePanel({
  appliedStyle,
  onApply,
  applying,
  onMessage,
}: {
  appliedStyle?: string | null;
  onApply: (style: VisualStyleSlug | string) => Promise<void>;
  applying: boolean;
  onMessage: (message: string) => void;
}) {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    authorizedRequest<VisualStyle[]>("/visual-styles")
      .then((loaded) => {
        if (!cancelled) setStyles(loaded);
      })
      .catch((error) => {
        if (!cancelled) onMessage(error instanceof Error ? error.message : "스타일 목록을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="media-tab-body">
      <p className="muted">영상 레이아웃·자막 룩을 고르면 미리보기에 바로 반영됩니다.</p>
      {loading ? <p className="muted">스타일 불러오는 중…</p> : null}
      <div className="visual-style-list">
        {styles.map((style) => {
          const active = (appliedStyle || "fullscreen") === style.slug;
          return (
            <button
              key={style.slug}
              type="button"
              className={`visual-style-row ${active ? "is-selected" : ""}`}
              disabled={applying || active}
              onClick={() => void onApply(style.slug)}
            >
              <div className="visual-style-row-preview">
                {style.previewImage ? <img src={style.previewImage} alt="" /> : null}
              </div>
              <div className="visual-style-row-copy">
                <strong>
                  {style.label}
                  {style.badge ? <span className="visual-style-row-badge">{style.badge}</span> : null}
                </strong>
                <span className="muted">{style.description}</span>
              </div>
              <span className="muted">{active ? "적용됨" : applying ? "저장 중…" : "적용"}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
