import { useMemo, useRef, type PointerEvent as ReactPointerEvent } from "react";
import type { Board } from "../../types";

const MIN_DURATION_SEC = 0.5;
const MAX_DURATION_SEC = 30;
const PX_PER_SEC = 48;

export function BoardTimeline({
  boards,
  selectedBoardId,
  boardDurationsSec,
  boardStartFramesList,
  currentFrame,
  durationInFrames,
  fps,
  onSelectBoard,
  onSeekFrame,
  onDurationCommit,
}: {
  boards: Board[];
  selectedBoardId: number | null;
  boardDurationsSec: number[];
  boardStartFramesList: number[];
  currentFrame: number;
  durationInFrames: number;
  fps: number;
  onSelectBoard: (boardId: number) => void;
  onSeekFrame: (frame: number) => void;
  onDurationCommit: (boardId: number, durationSec: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef<{
    boardId: number;
    startX: number;
    startDuration: number;
  } | null>(null);

  const totalSec = durationInFrames / fps;
  const playheadPct = durationInFrames > 1 ? (currentFrame / (durationInFrames - 1)) * 100 : 0;

  const segments = useMemo(() => {
    return boards.map((board, index) => {
      const durationSec = boardDurationsSec[index] ?? MIN_DURATION_SEC;
      const startFrame = boardStartFramesList[index] ?? 0;
      const durationFrames = Math.max(1, Math.round(durationSec * fps));
      return { board, index, durationSec, startFrame, durationFrames };
    });
  }, [boards, boardDurationsSec, boardStartFramesList, fps]);

  function frameFromClientX(clientX: number): number {
    const el = trackRef.current;
    if (!el || durationInFrames <= 0) return 0;
    const rect = el.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(ratio * (durationInFrames - 1));
  }

  function handleTrackPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("[data-resize-handle]")) return;
    onSeekFrame(frameFromClientX(event.clientX));
  }

  function handleResizePointerDown(event: ReactPointerEvent, boardId: number, durationSec: number) {
    event.stopPropagation();
    event.preventDefault();
    resizingRef.current = { boardId, startX: event.clientX, startDuration: durationSec };
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);

    const onMove = (moveEvent: PointerEvent) => {
      const active = resizingRef.current;
      if (!active) return;
      const deltaSec = (moveEvent.clientX - active.startX) / PX_PER_SEC;
      const next = Math.min(MAX_DURATION_SEC, Math.max(MIN_DURATION_SEC, active.startDuration + deltaSec));
      const label = target.parentElement?.querySelector("[data-duration-label]");
      if (label) label.textContent = `${next.toFixed(1)}s`;
      const bar = target.parentElement as HTMLElement | null;
      if (bar && durationInFrames > 0) {
        bar.style.width = `${(Math.round(next * fps) / durationInFrames) * 100}%`;
      }
    };

    const onUp = (upEvent: PointerEvent) => {
      const active = resizingRef.current;
      resizingRef.current = null;
      target.releasePointerCapture(upEvent.pointerId);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      if (!active) return;
      const deltaSec = (upEvent.clientX - active.startX) / PX_PER_SEC;
      const next = Math.min(MAX_DURATION_SEC, Math.max(MIN_DURATION_SEC, active.startDuration + deltaSec));
      onDurationCommit(active.boardId, Math.round(next * 10) / 10);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  if (boards.length === 0 || durationInFrames <= 0) return null;

  return (
    <div className="board-timeline" aria-label="보드 타임라인">
      <div className="board-timeline-meta">
        <strong>타임라인</strong>
        <span className="muted">
          {formatTime(currentFrame / fps)} / {formatTime(totalSec)}
        </span>
      </div>
      <div
        ref={trackRef}
        className="board-timeline-track"
        onPointerDown={handleTrackPointerDown}
        role="slider"
        aria-valuemin={0}
        aria-valuemax={Math.max(0, durationInFrames - 1)}
        aria-valuenow={currentFrame}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") onSeekFrame(Math.min(durationInFrames - 1, currentFrame + Math.round(fps / 2)));
          if (event.key === "ArrowLeft") onSeekFrame(Math.max(0, currentFrame - Math.round(fps / 2)));
        }}
      >
        <div className="board-timeline-segments board-timeline-segments-absolute">
          {segments.map(({ board, durationSec, index, startFrame, durationFrames }) => {
            const selected = board.id === selectedBoardId;
            const leftPct = (startFrame / durationInFrames) * 100;
            const widthPct = (durationFrames / durationInFrames) * 100;
            return (
              <div
                key={board.id}
                className={`board-timeline-clip${selected ? " selected" : ""}`}
                style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                title={`보드 ${index + 1} · ${durationSec.toFixed(1)}s`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectBoard(board.id);
                }}
              >
                <span className="board-timeline-clip-label">
                  {index + 1}
                  <span data-duration-label>{durationSec.toFixed(1)}s</span>
                </span>
                <button
                  type="button"
                  className="board-timeline-resize"
                  data-resize-handle
                  aria-label={`보드 ${index + 1} 길이 조절`}
                  onPointerDown={(event) => handleResizePointerDown(event, board.id, durationSec)}
                />
              </div>
            );
          })}
        </div>
        <div className="board-timeline-playhead" style={{ left: `${playheadPct}%` }} aria-hidden />
      </div>
      <p className="muted board-timeline-hint">클립 클릭·재생헤드 이동 / 오른쪽 핸들로 길이 조절</p>
    </div>
  );
}

function formatTime(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const rem = s - m * 60;
  return `${m}:${rem.toFixed(1).padStart(4, "0")}`;
}
