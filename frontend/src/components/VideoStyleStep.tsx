import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import type { BlogClip, VisualStyle, VisualStyleSlug } from "../types";

export function VideoStyleStep({
  blogClip,
  saving,
  onSelect,
  onBack,
  onMessage,
}: {
  blogClip: BlogClip;
  saving: boolean;
  onSelect: (
    style: VisualStyleSlug | string,
    copy: { style_title: string; style_subtitle: string },
  ) => Promise<void>;
  onBack?: () => void;
  onMessage: (message: string) => void;
}) {
  const [styles, setStyles] = useState<VisualStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(blogClip.visual_style || "fullscreen");
  const [titleDraft, setTitleDraft] = useState(blogClip.style_title || blogClip.blog_title || "");
  const [subtitleDraft, setSubtitleDraft] = useState(blogClip.style_subtitle || "");

  useEffect(() => {
    setSelected(blogClip.visual_style || "fullscreen");
    setTitleDraft(blogClip.style_title || blogClip.blog_title || "");
    setSubtitleDraft(blogClip.style_subtitle || "");
  }, [blogClip.visual_style, blogClip.style_title, blogClip.style_subtitle, blogClip.blog_title]);

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
      await onSelect(selected, {
        style_title: titleDraft,
        style_subtitle: subtitleDraft,
      });
    } catch {
      /* parent surfaces error */
    }
  }

  return (
    <section className="flow-card">
      <p className="create-kicker">퀵 모드 · 영상 스타일</p>
      <h1>영상 스타일을 선택해 주세요</h1>
      <p className="flow-lead">상단 타이틀·보조설명을 정한 뒤 스타일을 고르면 보이스 설정으로 이어갑니다.</p>

      <label className="style-copy-field">
        상단 타이틀
        <textarea
          rows={2}
          value={titleDraft}
          disabled={saving}
          onChange={(event) => setTitleDraft(event.target.value)}
          placeholder="예: 밀양 숨겨진 숙소 추천"
        />
      </label>
      <label className="style-copy-field">
        보조 설명
        <input
          type="text"
          value={subtitleDraft}
          disabled={saving}
          onChange={(event) => setSubtitleDraft(event.target.value)}
          placeholder="예: 깔끔한 정보 전달"
        />
      </label>

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
        {onBack ? (
          <button className="ghost-button" type="button" disabled={saving} onClick={onBack}>
            ← 편집 모드
          </button>
        ) : null}
        <button className="cta-button flow-primary-cta" type="button" disabled={saving || loading} onClick={() => void handleContinue()}>
          {saving ? "저장 중…" : "다음 · 보이스/오디오"}
        </button>
      </div>
    </section>
  );
}
