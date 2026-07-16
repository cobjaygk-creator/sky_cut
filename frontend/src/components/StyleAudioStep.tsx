import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import type { AudioAsset, BlogClip, SubtitleTemplate } from "../types";

const TEMPLATE_HINTS: Record<string, string> = {
  기본: "읽기 쉬운 표준 자막. 정보형·리뷰에 무난합니다.",
  볼드: "굵고 강한 자막. 훅·강조 문장에 잘 맞습니다.",
  쇼츠: "숏폼용 큰 자막. 모바일 세로 영상에 권장합니다.",
};

export function StyleAudioStep({
  blogClip,
  busy,
  onApplyTemplate,
  onAudioSettings,
  onBack,
  onRender,
  onMessage,
}: {
  blogClip: BlogClip;
  busy: boolean;
  onApplyTemplate: (templateId: number) => Promise<void>;
  onAudioSettings: (body: {
    auto_bgm?: boolean;
    auto_sfx?: boolean;
    bgm_asset_id?: number | null;
  }) => Promise<void>;
  onBack: () => void;
  onRender: () => void;
  onMessage: (message: string) => void;
}) {
  const [templates, setTemplates] = useState<SubtitleTemplate[]>([]);
  const [bgmAssets, setBgmAssets] = useState<AudioAsset[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      authorizedRequest<SubtitleTemplate[]>("/subtitle-templates"),
      authorizedRequest<AudioAsset[]>("/audio-assets?kind=bgm"),
    ])
      .then(([tpl, bgm]) => {
        if (cancelled) return;
        setTemplates(tpl);
        setBgmAssets(bgm);
      })
      .catch((error) => {
        if (!cancelled) onMessage(error instanceof Error ? error.message : "스타일/오디오를 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [blogClip.id]);

  return (
    <section className="flow-card">
      <p className="create-kicker">스타일 · 오디오</p>
      <h1>자막 스타일과 BGM을 정하세요</h1>
      <p className="flow-lead">
        아래에서 자막·BGM·효과음을 고른 뒤 <strong>프로젝트 만들기</strong>를 누르면 최종 영상 렌더가 시작됩니다.
      </p>

      {loading ? <p className="create-note">불러오는 중…</p> : null}

      <div>
        <h2 className="image-section-title">자막 템플릿</h2>
        <p className="option-help">
          영상에 올라가는 자막의 글꼴·크기·위치를 정합니다. Remotion 최종 렌더와 FFmpeg 폴백 모두 이 선택을 참고합니다.
        </p>
        <div className="template-scroller">
          {templates.map((template) => (
            <button
              key={template.id}
              type="button"
              className={`template-chip ${blogClip.subtitle_template_id === template.id ? "is-selected" : ""}`}
              disabled={busy}
              onClick={() => void onApplyTemplate(template.id)}
              title={TEMPLATE_HINTS[template.name] ?? template.name}
            >
              <strong>{template.name}</strong>
              <span className="muted">{template.is_system ? "시스템" : "내 템플릿"}</span>
            </button>
          ))}
        </div>
        <ul className="option-help-list">
          <li>
            <strong>기본</strong> — {TEMPLATE_HINTS["기본"]}
          </li>
          <li>
            <strong>볼드</strong> — {TEMPLATE_HINTS["볼드"]}
          </li>
          <li>
            <strong>쇼츠</strong> — {TEMPLATE_HINTS["쇼츠"]}
          </li>
        </ul>
      </div>

      <div className="auto-audio-toggles">
        <h2 className="image-section-title">자동 오디오</h2>
        <p className="option-help">
          렌더 직전에 시스템이 트랙을 골라 넣습니다. 직접 BGM을 고르면 자동 BGM보다 직접 선택이 우선합니다.
        </p>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={blogClip.auto_bgm}
            disabled={busy}
            onChange={(event) => void onAudioSettings({ auto_bgm: event.target.checked })}
          />
          <span>
            <strong>자동 BGM</strong>
            <span className="muted"> 길이·톤에 맞는 시스템 배경음악을 자동 배정</span>
          </span>
        </label>
        <p className="option-help option-help-indent">
          대본 톤(요약/훅/상세)과 길이에 맞춰 시스템 BGM을 고릅니다. 아래에서 BGM을 직접 고르면 이 옵션은 꺼집니다.
        </p>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={blogClip.auto_sfx}
            disabled={busy}
            onChange={(event) => void onAudioSettings({ auto_sfx: event.target.checked })}
          />
          <span>
            <strong>자동 SFX</strong>
            <span className="muted"> 보드 전환 시점에 짧은 효과음</span>
          </span>
        </label>
        <p className="option-help option-help-indent">
          첫 보드를 제외한 전환 구간에 시스템 효과음을 붙입니다. 나레이션보다 작게 섞입니다.
        </p>
      </div>

      <div>
        <h2 className="image-section-title">BGM 직접 선택</h2>
        <p className="option-help">
          원하는 배경음악을 고정합니다. <strong>없음</strong>은 BGM 없이 나레이션(+SFX)만 사용합니다. 트랙을 고르면 자동
          BGM은 해제됩니다.
        </p>
        <div className="template-scroller">
          <button
            type="button"
            className={`template-chip ${!blogClip.bgm_asset_id && !blogClip.auto_bgm ? "is-selected" : ""}`}
            disabled={busy}
            onClick={() => void onAudioSettings({ bgm_asset_id: null, auto_bgm: false })}
          >
            <strong>없음</strong>
            <span className="muted">나레이션만</span>
          </button>
          {bgmAssets.map((asset) => (
            <button
              key={asset.id}
              type="button"
              className={`template-chip ${blogClip.bgm_asset_id === asset.id ? "is-selected" : ""}`}
              disabled={busy}
              onClick={() => void onAudioSettings({ bgm_asset_id: asset.id })}
            >
              <strong>{asset.name}</strong>
              <span className="muted">{asset.user_id == null ? "시스템" : "내 파일"}</span>
            </button>
          ))}
        </div>
        <ul className="option-help-list">
          <li>
            <strong>소프트 패드</strong> — 잔잔한 패드 톤. 정보·리뷰에 무난합니다.
          </li>
          <li>
            <strong>라이트 웜</strong> — 조금 더 밝은 분위기. 제품·시공 소개에 잘 맞습니다.
          </li>
        </ul>
      </div>

      <div className="flow-step-actions">
        <button className="ghost-button" type="button" onClick={onBack} disabled={busy}>
          ← 보이스로
        </button>
        <button className="cta-button flow-primary-cta" type="button" disabled={busy} onClick={onRender}>
          {busy ? "시작 중…" : "프로젝트 만들기"}
        </button>
      </div>
    </section>
  );
}
