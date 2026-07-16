import { useEffect, useRef, useState } from "react";
import { authorizedBlob, authorizedRequest } from "../api/client";
import type { AudioAsset, BlogClip, Voice } from "../types";

export function QuickSettingsStep({
  blogClip,
  savingVoice,
  busy,
  onSaveDefaultVoice,
  onAudioSettings,
  onBack,
  onRender,
  onMessage,
}: {
  blogClip: BlogClip;
  savingVoice: boolean;
  busy: boolean;
  onSaveDefaultVoice: (voiceId: string, ttsSpeed: number) => Promise<void>;
  onAudioSettings: (body: {
    auto_bgm?: boolean;
    auto_sfx?: boolean;
    bgm_asset_id?: number | null;
  }) => Promise<void>;
  onBack: () => void;
  onRender: () => void;
  onMessage: (message: string) => void;
}) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [bgmAssets, setBgmAssets] = useState<AudioAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVoice, setSelectedVoice] = useState(blogClip.default_voice ?? "");
  const [speedDraft, setSpeedDraft] = useState(String(blogClip.tts_speed || 1));
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sampleUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setSelectedVoice(blogClip.default_voice ?? "");
    setSpeedDraft(String(blogClip.tts_speed || 1));
  }, [blogClip.default_voice, blogClip.tts_speed]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      authorizedRequest<Voice[]>("/voices"),
      authorizedRequest<AudioAsset[]>("/audio-assets?kind=bgm"),
    ])
      .then(([loadedVoices, bgm]) => {
        if (cancelled) return;
        setVoices(loadedVoices);
        setBgmAssets(bgm);
        setSelectedVoice((current) => {
          if (current && loadedVoices.some((voice) => voice.id === current)) return current;
          if (blogClip.default_voice && loadedVoices.some((voice) => voice.id === blogClip.default_voice)) {
            return blogClip.default_voice;
          }
          return loadedVoices[0]?.id ?? "";
        });
      })
      .catch((error) => {
        if (!cancelled) onMessage(error instanceof Error ? error.message : "퀵 설정을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [blogClip.id, blogClip.default_voice]);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (sampleUrlRef.current) URL.revokeObjectURL(sampleUrlRef.current);
    };
  }, []);

  async function handlePlaySample(voiceId: string) {
    try {
      audioRef.current?.pause();
      if (sampleUrlRef.current) {
        URL.revokeObjectURL(sampleUrlRef.current);
        sampleUrlRef.current = null;
      }
      setPlayingVoiceId(voiceId);
      const blob = await authorizedBlob(`/voices/${encodeURIComponent(voiceId)}/sample`);
      const url = URL.createObjectURL(blob);
      sampleUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlayingVoiceId(null);
      await audio.play();
    } catch (error) {
      setPlayingVoiceId(null);
      onMessage(error instanceof Error ? error.message : "샘플 재생에 실패했습니다.");
    }
  }

  async function handleRender() {
    if (!selectedVoice) {
      onMessage("보이스를 선택해 주세요.");
      return;
    }
    const speed = Number(speedDraft);
    if (!Number.isFinite(speed) || speed < 0.25 || speed > 4) {
      onMessage("재생 속도는 0.25~4.0 사이여야 합니다.");
      return;
    }
    setSubmitting(true);
    try {
      await onSaveDefaultVoice(selectedVoice, speed);
      onRender();
    } catch {
      /* onSave surfaces the error message */
    } finally {
      setSubmitting(false);
    }
  }

  const blocked = busy || savingVoice || submitting || loading;

  return (
    <section className="flow-card">
      <p className="create-kicker">퀵 모드</p>
      <h1>보이스와 오디오를 정하세요</h1>
      <p className="flow-lead">
        영상 스타일은 이전 단계에서 적용됩니다. 보이스·BGM을 고른 뒤 <strong>프로젝트 만들기</strong>를 누르세요.
      </p>

      {loading ? <p className="create-note">불러오는 중…</p> : null}

      <label className="create-field inline-field">
        <span>재생 속도</span>
        <input
          type="number"
          min={0.25}
          max={4}
          step={0.05}
          value={speedDraft}
          disabled={blocked}
          onChange={(e) => setSpeedDraft(e.target.value)}
        />
      </label>

      <div>
        <h2 className="image-section-title">보이스</h2>
        <div className="voice-gallery">
          {voices.map((voice) => (
            <div key={voice.id} className={`voice-card ${selectedVoice === voice.id ? "is-selected" : ""}`}>
              <button
                type="button"
                className="voice-card-main"
                disabled={blocked}
                onClick={() => setSelectedVoice(voice.id)}
              >
                <strong>{voice.name}</strong>
                <span className="muted">{voice.description}</span>
              </button>
              <button type="button" className="ghost-button" disabled={blocked} onClick={() => void handlePlaySample(voice.id)}>
                {playingVoiceId === voice.id ? "재생 중…" : "미리듣기"}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="auto-audio-toggles">
        <h2 className="image-section-title">자동 오디오</h2>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={blogClip.auto_bgm}
            disabled={blocked}
            onChange={(event) => void onAudioSettings({ auto_bgm: event.target.checked })}
          />
          <span>
            <strong>자동 BGM</strong>
            <span className="muted"> 길이·톤에 맞는 시스템 배경음악</span>
          </span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={blogClip.auto_sfx}
            disabled={blocked}
            onChange={(event) => void onAudioSettings({ auto_sfx: event.target.checked })}
          />
          <span>
            <strong>자동 SFX</strong>
            <span className="muted"> 보드 전환 시 짧은 효과음</span>
          </span>
        </label>
      </div>

      <div>
        <h2 className="image-section-title">BGM 직접 선택</h2>
        <div className="template-scroller">
          <button
            type="button"
            className={`template-chip ${!blogClip.bgm_asset_id && !blogClip.auto_bgm ? "is-selected" : ""}`}
            disabled={blocked}
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
              disabled={blocked}
              onClick={() => void onAudioSettings({ bgm_asset_id: asset.id })}
            >
              <strong>{asset.name}</strong>
              <span className="muted">{asset.user_id == null ? "시스템" : "내 파일"}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flow-step-actions">
        <button className="ghost-button" type="button" onClick={onBack} disabled={blocked}>
          ← 편집 모드
        </button>
        <button className="cta-button flow-primary-cta" type="button" disabled={blocked} onClick={() => void handleRender()}>
          {submitting || busy ? "시작 중…" : "프로젝트 만들기"}
        </button>
      </div>
    </section>
  );
}
