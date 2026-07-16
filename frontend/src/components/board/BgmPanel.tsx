import { useEffect, useRef, useState } from "react";
import { authorizedBlob, authorizedRequest, uploadRequest } from "../../api/client";
import type { AudioAsset, Board } from "../../types";

export function BgmPanel({
  selectedBoard,
  bgmAssetId,
  bgmVolume,
  onBgmChange,
  onSfxChange,
  saving,
}: {
  selectedBoard: Board | null;
  bgmAssetId: number | null;
  bgmVolume: number;
  onBgmChange: (bgmAssetId: number | null, bgmVolume?: number) => Promise<void>;
  onSfxChange: (sfxAssetId: number | null) => Promise<void>;
  saving: boolean;
}) {
  const [bgmAssets, setBgmAssets] = useState<AudioAsset[]>([]);
  const [sfxAssets, setSfxAssets] = useState<AudioAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [volumeDraft, setVolumeDraft] = useState(String(bgmVolume));
  const [uploading, setUploading] = useState(false);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadKind, setUploadKind] = useState<"bgm" | "sfx">("bgm");

  async function loadAssets() {
    setLoading(true);
    setError("");
    try {
      const [bgm, sfx] = await Promise.all([
        authorizedRequest<AudioAsset[]>("/audio-assets?kind=bgm"),
        authorizedRequest<AudioAsset[]>("/audio-assets?kind=sfx"),
      ]);
      setBgmAssets(bgm);
      setSfxAssets(sfx);
    } catch (err) {
      setError(err instanceof Error ? err.message : "오디오 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAssets();
    return () => {
      if (audioRef.current) audioRef.current.pause();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  useEffect(() => {
    setVolumeDraft(String(bgmVolume));
  }, [bgmVolume]);

  async function handlePreview(assetId: number) {
    setError("");
    try {
      if (audioRef.current) audioRef.current.pause();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      setPlayingId(assetId);
      const blob = await authorizedBlob(`/audio-assets/${assetId}/file`);
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setPlayingId(null);
      await audio.play();
    } catch (err) {
      setPlayingId(null);
      setError(err instanceof Error ? err.message : "미리듣기에 실패했습니다.");
    }
  }

  async function handleVolumeBlur() {
    const value = Number(volumeDraft);
    if (!Number.isFinite(value) || value < 0 || value > 0.55) {
      setError("BGM 볼륨은 0~0.55 사이여야 합니다 (TTS를 덮지 않도록 제한).");
      setVolumeDraft(String(bgmVolume));
      return;
    }
    if (Math.abs(value - bgmVolume) < 0.001) return;
    try {
      await onBgmChange(bgmAssetId, value);
    } catch (err) {
      setError(err instanceof Error ? err.message : "볼륨 저장에 실패했습니다.");
    }
  }

  async function handleUpload(file: File) {
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("kind", uploadKind);
      body.append("name", file.name.replace(/\.[^.]+$/, ""));
      body.append("file", file);
      await uploadRequest<AudioAsset>("/audio-assets", body);
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드에 실패했습니다.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="media-tab-body">
      <p className="muted">BGM은 TTS보다 작게 깔립니다. 보드별로 효과음을 넣을 수 있습니다.</p>
      {error ? <p className="form-message">{error}</p> : null}
      {loading ? <p className="muted">오디오 목록 불러오는 중…</p> : null}

      <section className="stock-search" aria-label="BGM">
        <h3 className="stock-search-title">BGM</h3>
        <label className="voice-speed">
          BGM 볼륨 (0–0.55)
          <input
            type="number"
            min={0}
            max={0.55}
            step={0.01}
            value={volumeDraft}
            onChange={(event) => setVolumeDraft(event.target.value)}
            onBlur={() => void handleVolumeBlur()}
            disabled={saving}
          />
        </label>
        <ul className="template-list">
          {bgmAssets.map((asset) => {
            const active = bgmAssetId === asset.id;
            return (
              <li key={asset.id} className={`template-card ${active ? "active" : ""}`}>
                <div className="template-card-copy">
                  <strong>{asset.name}</strong>
                  <span className="muted">{asset.is_system ? "시스템" : "내 업로드"}</span>
                </div>
                <div className="template-card-actions">
                  <button className="ghost-small" type="button" onClick={() => void handlePreview(asset.id)}>
                    {playingId === asset.id ? "재생 중" : "미리듣기"}
                  </button>
                  <button className="small-button" type="button" disabled={saving || active} onClick={() => void onBgmChange(asset.id)}>
                    {active ? "적용됨" : "적용"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
        {bgmAssetId != null ? (
          <button className="ghost-button" type="button" disabled={saving} onClick={() => void onBgmChange(null)}>
            BGM 끄기
          </button>
        ) : null}
      </section>

      <section className="stock-search" aria-label="효과음">
        <h3 className="stock-search-title">효과음 (선택 보드)</h3>
        {!selectedBoard ? <p className="muted">보드를 선택한 뒤 효과음을 지정하세요.</p> : null}
        {selectedBoard ? (
          <p className="muted">
            현재: {selectedBoard.sfx_asset_id ? `SFX #${selectedBoard.sfx_asset_id}` : "없음"} — 보드 시작 시 재생
          </p>
        ) : null}
        <ul className="template-list">
          {sfxAssets.map((asset) => {
            const active = selectedBoard?.sfx_asset_id === asset.id;
            return (
              <li key={asset.id} className={`template-card ${active ? "active" : ""}`}>
                <div className="template-card-copy">
                  <strong>{asset.name}</strong>
                  <span className="muted">{asset.is_system ? "시스템" : "내 업로드"}</span>
                </div>
                <div className="template-card-actions">
                  <button className="ghost-small" type="button" onClick={() => void handlePreview(asset.id)}>
                    {playingId === asset.id ? "재생 중" : "미리듣기"}
                  </button>
                  <button
                    className="small-button"
                    type="button"
                    disabled={!selectedBoard || saving || active}
                    onClick={() => void onSfxChange(asset.id)}
                  >
                    {active ? "적용됨" : "이 보드에"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
        {selectedBoard?.sfx_asset_id != null ? (
          <button className="ghost-button" type="button" disabled={saving} onClick={() => void onSfxChange(null)}>
            효과음 제거
          </button>
        ) : null}
      </section>

      <section className="stock-search" aria-label="업로드">
        <h3 className="stock-search-title">오디오 업로드</h3>
        <div className="template-card-actions">
          <label className="duration-auto">
            <input type="radio" checked={uploadKind === "bgm"} onChange={() => setUploadKind("bgm")} />
            BGM
          </label>
          <label className="duration-auto">
            <input type="radio" checked={uploadKind === "sfx"} onChange={() => setUploadKind("sfx")} />
            효과음
          </label>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.aac,.ogg,audio/*"
          disabled={uploading}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void handleUpload(file);
          }}
        />
        {uploading ? <p className="muted">업로드 중…</p> : null}
      </section>
    </div>
  );
}
