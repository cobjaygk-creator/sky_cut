import type { DragEvent } from "react";
import type { Board } from "../../types";
import { useBoardImageUrl } from "./useBoardImageUrl";

export function BoardListItem({
  board,
  blogClipId,
  selected,
  onSelect,
  onDelete,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  onDragStart,
  onDragOver,
  onDrop,
}: {
  board: Board;
  blogClipId: number;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onDragStart: () => void;
  onDragOver: (event: DragEvent) => void;
  onDrop: () => void;
}) {
  const { url, error } = useBoardImageUrl(blogClipId, board.id, board.image_path);
  const previewText = board.text.trim() || "(텍스트 없음)";

  return (
    <li
      className={`board-list-item ${selected ? "selected" : ""}`}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <button className="board-list-item-main" type="button" onClick={onSelect}>
        <span className="board-thumb" aria-hidden>
          {url && !error ? <img src={url} alt="" /> : <span className="board-thumb-fallback">{board.order_index + 1}</span>}
        </span>
        <span className="board-list-item-copy">
          <strong>보드 {board.order_index + 1}</strong>
          {board.speaker ? <span className="board-speaker-badge">{board.speaker}</span> : null}
          <span className="muted">{previewText}</span>
        </span>
      </button>
      <div className="board-list-item-actions">
        <button className="ghost-small" type="button" onClick={onMoveUp} disabled={!canMoveUp} aria-label="위로">
          ▲
        </button>
        <button className="ghost-small" type="button" onClick={onMoveDown} disabled={!canMoveDown} aria-label="아래로">
          ▼
        </button>
        <button className="ghost-small" type="button" onClick={onDelete} aria-label="삭제">
          ×
        </button>
      </div>
    </li>
  );
}
