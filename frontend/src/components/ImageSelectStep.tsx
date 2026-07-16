import { useEffect, useState } from "react";
import { authorizedRequest } from "../api/client";
import { BLOG_IMAGE_MAX_COUNT, BLOG_IMAGE_MIN_COUNT } from "../constants";
import type { BlogClip, BlogClipImageCandidate } from "../types";
import { useCandidateImageUrl } from "./useCandidateImageUrl";

function CandidateThumb({
  blogClipId,
  candidate,
  selected,
  onToggle,
}: {
  blogClipId: number;
  candidate: BlogClipImageCandidate;
  selected: boolean;
  onToggle: () => void;
}) {
  const { url, error } = useCandidateImageUrl(blogClipId, candidate.id);

  return (
    <button
      type="button"
      className={`image-candidate ${selected ? "is-selected" : ""}`}
      onClick={onToggle}
      aria-pressed={selected}
    >
      {url ? <img src={url} alt="" /> : <span className="image-candidate-fallback">{error ? "!" : "…"}</span>}
      <span className="image-candidate-check" aria-hidden="true">
        {selected ? "✓" : ""}
      </span>
    </button>
  );
}

export function ImageSelectStep({
  blogClip,
  confirming,
  onConfirm,
  onMessage,
}: {
  blogClip: BlogClip;
  confirming: boolean;
  onConfirm: (imageIds: number[]) => void;
  onMessage: (message: string) => void;
}) {
  const [candidates, setCandidates] = useState<BlogClipImageCandidate[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    authorizedRequest<BlogClipImageCandidate[]>(`/blog-clips/${blogClip.id}/images`)
      .then((loaded) => {
        if (cancelled) return;
        setCandidates(loaded);
        const initial = loaded.filter((item) => item.selected).map((item) => item.id);
        setSelectedIds(initial.length > 0 ? initial : loaded.map((item) => item.id));
      })
      .catch((error) => {
        if (!cancelled) {
          onMessage(error instanceof Error ? error.message : "이미지를 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [blogClip.id]);

  function toggle(imageId: number) {
    setSelectedIds((current) => {
      if (current.includes(imageId)) {
        return current.filter((id) => id !== imageId);
      }
      if (current.length >= BLOG_IMAGE_MAX_COUNT) {
        onMessage(`이미지는 최대 ${BLOG_IMAGE_MAX_COUNT}장까지 선택할 수 있습니다.`);
        return current;
      }
      return [...current, imageId];
    });
  }

  const selected = candidates
    .filter((item) => selectedIds.includes(item.id))
    .sort((a, b) => selectedIds.indexOf(a.id) - selectedIds.indexOf(b.id));
  const canContinue =
    selectedIds.length >= BLOG_IMAGE_MIN_COUNT && selectedIds.length <= BLOG_IMAGE_MAX_COUNT && !confirming;

  return (
    <section className="flow-card flow-images-card">
      <p className="create-kicker">이미지 선택</p>
      <h1>{blogClip.blog_title ?? "사용할 이미지를 고르세요"}</h1>
      <p className="flow-lead">
        {BLOG_IMAGE_MIN_COUNT}–{BLOG_IMAGE_MAX_COUNT}장을 고른 뒤 다음으로 가면 대본 톤을 선택합니다. 선택{" "}
        {selectedIds.length}장.
      </p>

      {loading ? <p className="create-note">이미지 불러오는 중…</p> : null}

      {!loading && selected.length > 0 ? (
        <div className="image-selected-block">
          <h2 className="image-section-title">선택됨</h2>
          <div className="image-candidate-grid">
            {selected.map((candidate) => (
              <CandidateThumb
                key={`sel-${candidate.id}`}
                blogClipId={blogClip.id}
                candidate={candidate}
                selected
                onToggle={() => toggle(candidate.id)}
              />
            ))}
          </div>
        </div>
      ) : null}

      {!loading ? (
        <div className="image-filmstrip-block">
          <h2 className="image-section-title">후보</h2>
          <div className="image-candidate-strip">
            {candidates.map((candidate) => (
              <CandidateThumb
                key={candidate.id}
                blogClipId={blogClip.id}
                candidate={candidate}
                selected={selectedIds.includes(candidate.id)}
                onToggle={() => toggle(candidate.id)}
              />
            ))}
            <div className="image-candidate-add" aria-hidden="true">
              <span>+</span>
              <span>추가 (곧)</span>
            </div>
          </div>
        </div>
      ) : null}

      <button
        className="cta-button flow-primary-cta"
        type="button"
        disabled={!canContinue}
        onClick={() => onConfirm(selectedIds)}
      >
        {confirming ? "확인 중…" : "다음 · 대본 선택"}
      </button>
    </section>
  );
}
