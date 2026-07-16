import { useEffect, useRef, useState } from "react";
import { authorizedBlob, authorizedRequest } from "../api/client";
import type { BlogClip, Voice } from "../types";

export function VoiceStep({
  blogClip,
  saving,
  onSave,
  onBack,
  onNext,
  onMessage,
}: {
  blogClip: BlogClip;
  saving: boolean;
  onSave: (voiceId: string, ttsSpeed: number) => Promise<void>;
  onBack: () => void;
  onNext: () => void;
  onMessage: (message: string) => void;
}) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVoice, setSelectedVoice] = useState(blogClip.default_voice ?? "");
  const [speedDraft, setSpeedDraft] = useState(String(blogClip.tts_speed || 1));
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sampleUrlRef = useRef<string | null>(null);

  useEffect(() => {
    setSelectedVoice(blogClip.default_voice ?? "");
    setSpeedDraft(String(blogClip.tts_speed || 1));
  }, [blogClip.default_voice, blogClip.tts_speed]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    authorizedRequest<Voice[]>("/voices")
      .then((loaded) => {
        if (cancelled) return;
        setVoices(loaded);
        setSelectedVoice((current) => {
          if (current && loaded.some((voice) => voice.id === current)) return current;
          if (blogClip.default_voice && loaded.some((voice) => voice.id === blogClip.default_voice)) {
            return blogClip.default_voice;
          }
          return loaded[0]?.id ?? "";
        });
      })
      .catch((error) => {
        if (!cancelled) onMessage(error instanceof Error ? error.message : "보이스 목록을 불러오지 못했습니다.");
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

  async function handleContinue() {
    if (!selectedVoice) {
      onMessage("보이스를 선택해 주세요.");
      return;
    }
    const speed = Number(speedDraft);
    if (!Number.isFinite(speed) || speed < 0.25 || speed > 4) {
      onMessage("재생 속도는 0.25~4.0 사이여야 합니다.");
      return;
    }
    try {
      await onSave(selectedVoice, speed);
      onNext();
    } catch {
      /* onSave surfaces the error message */
    }
  }

  return (
    <section className="flow-card">
      <p className="create-kicker">보이스</p>
      <h1>AI 나레이션 보이스를 고르세요</h1>
      <p className="flow-lead">선택한 보이스와 속도가 모든 보드에 적용됩니다. 보드 편집기에서 보드별로도 바꿀 수 있어요.</p>

      <label className="create-field inline-field">
        <span>재생 속도</span>
        <input type="number" min={0.25} max={4} step={0.05} value={speedDraft} onChange={(e) => setSpeedDraft(e.target.value)} />
      </label>

      {loading ? <p className="create-note">보이스 불러오는 중…</p> : null}

      <div className="voice-gallery">
        {voices.map((voice) => (
          <div key={voice.id} className={`voice-card ${selectedVoice === voice.id ? "is-selected" : ""}`}>
            <button type="button" className="voice-card-main" onClick={() => setSelectedVoice(voice.id)}>
              <strong>{voice.name}</strong>
              <span className="muted">{voice.description}</span>
            </button>
            <button type="button" className="ghost-button" onClick={() => void handlePlaySample(voice.id)}>
              {playingVoiceId === voice.id ? "재생 중…" : "미리듣기"}
            </button>
          </div>
        ))}
      </div>

      <div className="flow-step-actions">
        <button className="ghost-button" type="button" onClick={onBack}>
          ← 보드로
        </button>
        <button className="cta-button" type="button" disabled={saving || loading} onClick={() => void handleContinue()}>
          {saving ? "저장 중…" : "다음 · 스타일/오디오"}
        </button>
      </div>
    </section>
  );
}
