import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import type { BlogClip, VisualStyle, VisualStyleSlug } from "../types";

export function VideoStyleStep({
  blogClip,
  saving,
  onSelect,
  onMessage,
}: {
  blogClip: BlogClip;
  saving: boolean;
  onSelect: (style: VisualStyleSlug | string) => Promise<void>;
  onMessage: (message: string) => void;
}) {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(blogClip.visual_style || "fullscreen");

  useEffect(() => {
    setSelected(blogClip.visual_style || "fullscreen");
  }, [blogClip.visual_style]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    authorizedRequest<VisualStyle[]>("/visual-styles")
      .then((loaded) => {
        if (cancelled) return;
        setStyles(loaded);
        setSelected((current) => {
          if (current && loaded.some((item) => item.slug === current)) return current;
          return loaded[0]?.slug ?? "fullscreen";
        });
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
  }, [blogClip.id]);

  async function handleContinue() {
    try {
      await onSelect(selected);
    } catch {
      /* parent surfaces error */
    }
  }

  return (
    <section className="flow-card">
      <p className="create-kicker">영상 스타일</p>
      <h1>영상 스타일을 선택해 주세요</h1>
      <p className="flow-lead">대본에 맞는 레이아웃·자막 룩을 고른 뒤 편집으로 이어갑니다.</p>

      {loading ? <p className="create-note">스타일 불러오는 중…</p> : null}

      <div className="style-gallery">
        {styles.map((style) => (
          <button
            key={style.slug}
            type="button"
            className={`style-card ${selected === style.slug ? "is-selected" : ""}`}
            disabled={saving}
            onClick={() => setSelected(style.slug)}
          >
            {style.badge ? <span className="style-card-badge">{style.badge}</span> : null}
            {selected === style.slug ? <span className="style-card-check" aria-hidden="true">✓</span> : null}
            <div className="style-card-preview">
              {style.previewImage ? (
                <img src={style.previewImage} alt="" />
              ) : (
                <div className={`style-card-fallback style-fallback-${style.slug}`} />
              )}
            </div>
            <strong>{style.label}</strong>
            <span className="muted">{style.description}</span>
          </button>
        ))}
      </div>

      <div className="flow-step-actions">
        <button className="cta-button flow-primary-cta" type="button" disabled={saving || loading} onClick={() => void handleContinue()}>
          {saving ? "저장 중…" : "이 스타일로 계속"}
        </button>
      </div>
    </section>
  );
}
