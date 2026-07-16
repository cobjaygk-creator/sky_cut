import { useEffect, useMemo, useState } from "react";
import { authorizedRequest } from "../../api/client";
import { SCRIPT_TONE_LABELS } from "../../constants";
import type { BlogClip, Board } from "../../types";
import { BoardList } from "./BoardList";
import { MediaPanel } from "./MediaPanel";
import { RemotionPreviewPane } from "./RemotionPreviewPane";

export function BoardEditor({
  blogClip,
  onClose,
  onRendered,
  onClipUpdated,
  onMessage,
}: {
  blogClip: BlogClip;
  onClose: () => void;
  onRendered: (updated: BlogClip) => void;
  onClipUpdated?: (updated: BlogClip) => void;
  onMessage: (message: string) => void;
}) {
  const [clip, setClip] = useState(blogClip);
  const [boards, setBoards] = useState<Board[]>([]);
  const [imagePathPool, setImagePathPool] = useState<string[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<number | null>(null);
  const [draftText, setDraftText] = useState("");
  const [durationInput, setDurationInput] = useState("");
  const [autoDuration, setAutoDuration] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [applyingStock, setApplyingStock] = useState(false);
  const [assigningSpeaker, setAssigningSpeaker] = useState(false);
  const [ttsSpeed, setTtsSpeed] = useState(blogClip.tts_speed ?? 1);
  const [visualStyle, setVisualStyle] = useState(blogClip.visual_style || "fullscreen");
  const [applyingVisualStyle, setApplyingVisualStyle] = useState(false);
  const [savingStyleCopy, setSavingStyleCopy] = useState(false);
  const [bgmAssetId, setBgmAssetId] = useState<number | null>(blogClip.bgm_asset_id ?? null);
  const [bgmVolume, setBgmVolume] = useState(blogClip.bgm_volume ?? 0.3);
  const [audioSaving, setAudioSaving] = useState(false);

  const selectedBoard = useMemo(() => boards.find((board) => board.id === selectedBoardId) ?? null, [boards, selectedBoardId]);

  function rememberImagePaths(items: Board[]) {
    setImagePathPool((current) => {
      const next = [...current];
      for (const board of items) {
        if (!next.includes(board.image_path)) next.push(board.image_path);
      }
      return next;
    });
  }

  async function loadBoards() {
    setLoading(true);
    setError("");
    try {
      const loaded = await authorizedRequest<Board[]>(`/blog-clips/${blogClip.id}/boards`);
      setBoards(loaded);
      rememberImagePaths(loaded);
      const nextSelected = loaded.find((board) => board.id === selectedBoardId)?.id ?? loaded[0]?.id ?? null;
      setSelectedBoardId(nextSelected);
      const selected = loaded.find((board) => board.id === nextSelected) ?? null;
      setDraftText(selected?.text ?? "");
      setAutoDuration(selected?.duration_seconds == null);
      setDurationInput(selected?.duration_seconds != null ? String(selected.duration_seconds) : "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "보드를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setClip(blogClip);
    setVisualStyle(blogClip.visual_style || "fullscreen");
  }, [blogClip]);

  useEffect(() => {
    if (blogClip.status !== "awaiting_boards") {
      onClose();
      return;
    }
    setTtsSpeed(blogClip.tts_speed ?? 1);
    setVisualStyle(blogClip.visual_style || "fullscreen");
    setBgmAssetId(blogClip.bgm_asset_id ?? null);
    setBgmVolume(blogClip.bgm_volume ?? 0.3);
    void loadBoards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blogClip.id]);

  useEffect(() => {
    const board = boards.find((item) => item.id === selectedBoardId) ?? null;
    if (!board) {
      setDraftText("");
      setAutoDuration(true);
      setDurationInput("");
      return;
    }
    setDraftText(board.text);
    setAutoDuration(board.duration_seconds == null);
    setDurationInput(board.duration_seconds != null ? String(board.duration_seconds) : "");
    // Only re-sync draft when the selected board changes, not on every boards refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBoardId]);

  function selectBoard(boardId: number) {
    setSelectedBoardId(boardId);
  }

  async function saveText() {
    if (!selectedBoard || saving) return;
    if (draftText === selectedBoard.text) return;
    setSaving(true);
    setError("");
    try {
      const updated = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards/${selectedBoard.id}`, {
        method: "PATCH",
        body: JSON.stringify({ text: draftText }),
      });
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "텍스트 저장에 실패했습니다.");
      await loadBoards();
    } finally {
      setSaving(false);
    }
  }

  async function persistOrder(nextBoards: Board[]) {
    setBoards(nextBoards);
    setError("");
    try {
      const reordered = await authorizedRequest<Board[]>(`/blog-clips/${blogClip.id}/boards/reorder`, {
        method: "PUT",
        body: JSON.stringify({ board_ids: nextBoards.map((board) => board.id) }),
      });
      setBoards(reordered);
    } catch (err) {
      setError(err instanceof Error ? err.message : "순서 변경에 실패했습니다.");
      await loadBoards();
    }
  }

  async function handleMove(boardId: number, direction: -1 | 1) {
    const index = boards.findIndex((board) => board.id === boardId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= boards.length) return;
    const next = [...boards];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    await persistOrder(next.map((board, orderIndex) => ({ ...board, order_index: orderIndex })));
  }

  async function handleReorder(fromId: number, toId: number) {
    const fromIndex = boards.findIndex((board) => board.id === fromId);
    const toIndex = boards.findIndex((board) => board.id === toId);
    if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return;
    const next = [...boards];
    const [item] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, item);
    await persistOrder(next.map((board, orderIndex) => ({ ...board, order_index: orderIndex })));
  }

  async function handleAdd() {
    const imagePath = selectedBoard?.image_path ?? boards[0]?.image_path ?? imagePathPool[0];
    if (!imagePath) {
      setError("추가할 이미지를 찾을 수 없습니다.");
      return;
    }
    setAdding(true);
    setError("");
    try {
      const created = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards`, {
        method: "POST",
        body: JSON.stringify({ image_path: imagePath, text: "" }),
      });
      const loaded = await authorizedRequest<Board[]>(`/blog-clips/${blogClip.id}/boards`);
      setBoards(loaded);
      rememberImagePaths(loaded);
      setSelectedBoardId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "보드 추가에 실패했습니다.");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(boardId: number) {
    setError("");
    try {
      await authorizedRequest(`/blog-clips/${blogClip.id}/boards/${boardId}`, { method: "DELETE" });
      const loaded = await authorizedRequest<Board[]>(`/blog-clips/${blogClip.id}/boards`);
      setBoards(loaded);
      if (selectedBoardId === boardId) {
        setSelectedBoardId(loaded[0]?.id ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "보드 삭제에 실패했습니다.");
      await loadBoards();
    }
  }

  async function handleSwapImage(imagePath: string) {
    if (!selectedBoard || selectedBoard.image_path === imagePath) return;
    setError("");
    try {
      const updated = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards/${selectedBoard.id}`, {
        method: "PATCH",
        body: JSON.stringify({ image_path: imagePath }),
      });
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "이미지 교체에 실패했습니다.");
      await loadBoards();
    }
  }

  async function handleApplyStock(downloadUrl: string) {
    if (!selectedBoard || applyingStock) return;
    setApplyingStock(true);
    setError("");
    try {
      const updated = await authorizedRequest<Board>(
        `/blog-clips/${blogClip.id}/boards/${selectedBoard.id}/stock-image`,
        {
          method: "POST",
          body: JSON.stringify({ download_url: downloadUrl }),
        },
      );
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
      rememberImagePaths([updated]);
      onMessage("스톡 이미지를 보드에 적용했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "스톡 이미지 적용에 실패했습니다.");
      throw err;
    } finally {
      setApplyingStock(false);
    }
  }

  async function handleAssignSpeaker(voiceId: string | null) {
    if (!selectedBoard || assigningSpeaker) return;
    setAssigningSpeaker(true);
    setError("");
    try {
      const updated = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards/${selectedBoard.id}`, {
        method: "PATCH",
        body: JSON.stringify({ speaker: voiceId }),
      });
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
      onMessage(voiceId ? `보드에 보이스 ${voiceId}를 적용했습니다.` : "보드 보이스를 기본값으로 되돌렸습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "보이스 지정에 실패했습니다.");
      throw err;
    } finally {
      setAssigningSpeaker(false);
    }
  }

  async function handleTtsSpeedChange(speed: number) {
    setError("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/tts-settings`, {
        method: "PATCH",
        body: JSON.stringify({ tts_speed: speed }),
      });
      setTtsSpeed(updated.tts_speed);
      onMessage(`재생 속도를 ${updated.tts_speed}배로 저장했습니다.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "재생 속도 저장에 실패했습니다.");
      setTtsSpeed(blogClip.tts_speed ?? 1);
    }
  }

  async function handleApplyVisualStyle(nextStyle: string) {
    if (applyingVisualStyle) return;
    setApplyingVisualStyle(true);
    setError("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/visual-style`, {
        method: "PATCH",
        body: JSON.stringify({ visual_style: nextStyle }),
      });
      setVisualStyle(updated.visual_style || nextStyle);
      setClip(updated);
      onClipUpdated?.(updated);
      onMessage("영상 스타일을 적용했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "영상 스타일 적용에 실패했습니다.");
      throw err;
    } finally {
      setApplyingVisualStyle(false);
    }
  }

  async function handleStyleCopyChange(body: { style_title?: string; style_subtitle?: string }) {
    setSavingStyleCopy(true);
    setError("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/style-copy`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setClip(updated);
      onClipUpdated?.(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "타이틀 저장에 실패했습니다.");
      throw err;
    } finally {
      setSavingStyleCopy(false);
    }
  }

  async function handleBgmChange(nextBgmId: number | null, nextVolume?: number) {
    setAudioSaving(true);
    setError("");
    try {
      const body: { bgm_asset_id: number | null; bgm_volume?: number } = { bgm_asset_id: nextBgmId };
      if (nextVolume != null) body.bgm_volume = nextVolume;
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/audio-settings`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setBgmAssetId(updated.bgm_asset_id);
      setBgmVolume(updated.bgm_volume);
      onMessage(nextBgmId == null ? "BGM을 껐습니다." : "BGM 설정을 저장했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "BGM 설정 저장에 실패했습니다.");
      throw err;
    } finally {
      setAudioSaving(false);
    }
  }

  async function handleSfxChange(sfxAssetId: number | null) {
    if (!selectedBoard) return;
    setAudioSaving(true);
    setError("");
    try {
      const updated = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards/${selectedBoard.id}`, {
        method: "PATCH",
        body: JSON.stringify({ sfx_asset_id: sfxAssetId }),
      });
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
      onMessage(sfxAssetId == null ? "보드 효과음을 제거했습니다." : "보드에 효과음을 적용했습니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "효과음 설정에 실패했습니다.");
      throw err;
    } finally {
      setAudioSaving(false);
    }
  }

  async function commitBoardDuration(boardId: number, value: number) {
    if (!Number.isFinite(value) || value < 0.5) {
      setError("길이는 0.5초 이상이어야 합니다.");
      return;
    }
    setError("");
    if (boardId === selectedBoardId) {
      setAutoDuration(false);
      setDurationInput(String(value));
    }
    try {
      const updated = await authorizedRequest<Board>(`/blog-clips/${blogClip.id}/boards/${boardId}`, {
        method: "PATCH",
        body: JSON.stringify({ duration_seconds: value }),
      });
      setBoards((current) => current.map((board) => (board.id === updated.id ? updated : board)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "길이 저장에 실패했습니다.");
      await loadBoards();
    }
  }

  async function handleDurationBlur() {
    if (!selectedBoard || autoDuration) return;
    const value = Number(durationInput);
    await commitBoardDuration(selectedBoard.id, value);
  }

  function handleAutoDurationChange(value: boolean) {
    setAutoDuration(value);
    if (value) {
      // Keep UI as auto; Stage 18 PATCH cannot clear duration to null without sending the field.
      // Leaving existing duration_seconds as-is until a later API change — document via message.
      onMessage("길이 자동: 렌더 시 남은 시간을 균등 분배합니다. 이미 지정된 값이 있으면 서버에 유지됩니다.");
    }
  }

  async function handleRender() {
    if (boards.length === 0) return;
    const hasText = boards.some((board) => (board.id === selectedBoardId ? draftText : board.text).trim());
    if (!hasText) {
      setError("하나 이상의 보드에 나레이션 문구가 필요합니다.");
      return;
    }
    await saveText();
    setRendering(true);
    setError("");
    try {
      const updated = await authorizedRequest<BlogClip>(`/blog-clips/${blogClip.id}/render`, { method: "POST" });
      onRendered(updated);
      onMessage("보드 구성을 확정했습니다. 영상 렌더링을 시작합니다.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "렌더링 시작에 실패했습니다.");
    } finally {
      setRendering(false);
    }
  }

  const canRender = boards.length > 0 && !rendering && !loading;

  return (
    <div className="board-editor" role="dialog" aria-modal="true" aria-label="보드 편집기">
      <header className="board-editor-header">
        <div>
          <p className="eyebrow">보드 편집</p>
          <h2>{blogClip.blog_title ?? "블로그 쇼츠"}</h2>
          {blogClip.script_tone ? <span className="muted">톤: {SCRIPT_TONE_LABELS[blogClip.script_tone]}</span> : null}
        </div>
        <div className="board-editor-actions">
          <button className="ghost-button" type="button" onClick={handleRender} disabled={!canRender}>
            {rendering ? "렌더링 시작 중" : "지금 렌더링"}
          </button>
          <button className="primary-button" type="button" onClick={onClose}>
            편집 완료
          </button>
        </div>
      </header>

      {error ? (
        <div className="board-editor-error" role="alert">
          <p className="form-message dashboard-message">{error}</p>
          {boards.length === 0 && !loading ? (
            <button className="small-button" type="button" onClick={() => void loadBoards()}>
              다시 시도
            </button>
          ) : null}
        </div>
      ) : null}
      {loading ? <p className="muted">보드를 불러오는 중…</p> : null}

      {!loading && (boards.length > 0 || !error) ? (
        <div className="board-editor-layout">
          <BoardList
            blogClipId={blogClip.id}
            boards={boards}
            selectedBoardId={selectedBoardId}
            onSelect={selectBoard}
            onDelete={handleDelete}
            onAdd={handleAdd}
            onMove={handleMove}
            onReorder={handleReorder}
            adding={adding}
          />
          <RemotionPreviewPane
            blogClip={clip}
            boards={boards}
            selectedBoardId={selectedBoardId}
            draftText={draftText}
            onDraftChange={setDraftText}
            onTextBlur={() => void saveText()}
            onSelectBoard={selectBoard}
            onDurationCommit={(boardId, durationSec) => void commitBoardDuration(boardId, durationSec)}
            onBoardsSynced={() => void loadBoards()}
            bgmAssetId={bgmAssetId}
            bgmVolume={bgmVolume}
          />
          <MediaPanel
            blogClipId={blogClip.id}
            boards={boards}
            selectedBoard={selectedBoard}
            onSwapImage={(imagePath) => void handleSwapImage(imagePath)}
            onApplyStock={handleApplyStock}
            applyingStock={applyingStock}
            ttsSpeed={ttsSpeed}
            onTtsSpeedChange={(speed) => void handleTtsSpeedChange(speed)}
            onAssignSpeaker={handleAssignSpeaker}
            assigningSpeaker={assigningSpeaker}
            appliedVisualStyle={visualStyle}
            styleTitle={clip.style_title ?? clip.blog_title}
            styleSubtitle={clip.style_subtitle}
            onApplyVisualStyle={handleApplyVisualStyle}
            onStyleCopyChange={handleStyleCopyChange}
            applyingVisualStyle={applyingVisualStyle}
            savingStyleCopy={savingStyleCopy}
            onMessage={onMessage}
            bgmAssetId={bgmAssetId}
            bgmVolume={bgmVolume}
            onBgmChange={handleBgmChange}
            onSfxChange={handleSfxChange}
            audioSaving={audioSaving}
            durationInput={durationInput}
            onDurationChange={setDurationInput}
            onDurationBlur={() => void handleDurationBlur()}
            autoDuration={autoDuration}
            onAutoDurationChange={handleAutoDurationChange}
          />
        </div>
      ) : null}
    </div>
  );
}
