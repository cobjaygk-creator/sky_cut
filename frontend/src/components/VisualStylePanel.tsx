import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import type { VisualStyle, VisualStyleSlug } from "../types";

/** Compact visual-style picker + editable top title/subtitle for BoardEditor. */
export function VisualStylePanel({
  appliedStyle,
  styleTitle,
  styleSubtitle,
  onApply,
  onStyleCopyChange,
  applying,
  savingCopy,
  onMessage,
}: {
  appliedStyle?: string | null;
  styleTitle?: string | null;
  styleSubtitle?: string | null;
  onApply: (style: VisualStyleSlug | string) => Promise<void>;
  onStyleCopyChange: (body: { style_title?: string; style_subtitle?: string }) => Promise<void>;
  applying: boolean;
  savingCopy: boolean;
  onMessage: (message: string) => void;
}) {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [titleDraft, setTitleDraft] = useState(styleTitle ?? "");
  const [subtitleDraft, setSubtitleDraft] = useState(styleSubtitle ?? "");

  useEffect(() => {
    setTitleDraft(styleTitle ?? "");
    setSubtitleDraft(styleSubtitle ?? "");
  }, [styleTitle, styleSubtitle]);

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

  async function saveCopy() {
    try {
      await onStyleCopyChange({
        style_title: titleDraft,
        style_subtitle: subtitleDraft,
      });
    } catch {
      /* parent surfaces */
    }
  }

  return (
    <div className="media-tab-body">
      <p className="muted">상단 타이틀·보조설명은 템플릿 헤더에 표시됩니다. 미리보기에 바로 반영됩니다.</p>

      <label className="style-copy-field">
        상단 타이틀
        <textarea
          rows={2}
          value={titleDraft}
          disabled={savingCopy}
          onChange={(event) => setTitleDraft(event.target.value)}
          onBlur={() => void saveCopy()}
          placeholder="예: 밀양 숨겨진 숙소 추천"
        />
      </label>
      <label className="style-copy-field">
        보조 설명
        <input
          type="text"
          value={subtitleDraft}
          disabled={savingCopy}
          onChange={(event) => setSubtitleDraft(event.target.value)}
          onBlur={() => void saveCopy()}
          placeholder="예: 깔끔한 정보 전달"
        />
      </label>

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
