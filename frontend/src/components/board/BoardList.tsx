import { useRef } from "react";
import type { Board } from "../../types";
import { BoardListItem } from "./BoardListItem";

export function BoardList({
  blogClipId,
  boards,
  selectedBoardId,
  onSelect,
  onDelete,
  onAdd,
  onMove,
  onReorder,
  adding,
}: {
  blogClipId: number;
  boards: Board[];
  selectedBoardId: number | null;
  onSelect: (boardId: number) => void;
  onDelete: (boardId: number) => void;
  onAdd: () => void;
  onMove: (boardId: number, direction: -1 | 1) => void;
  onReorder: (fromId: number, toId: number) => void;
  adding: boolean;
}) {
  const dragIdRef = useRef<number | null>(null);

  return (
    <aside className="board-list" aria-label="보드 목록">
      <div className="board-list-header">
        <h3>보드</h3>
        <span className="muted">{boards.length}개</span>
      </div>
      {boards.length === 0 ? <p className="muted">보드가 없습니다. 보드를 추가하세요.</p> : null}
      <ul className="board-list-ul">
        {boards.map((board, index) => (
          <BoardListItem
            key={board.id}
            board={board}
            blogClipId={blogClipId}
            selected={selectedBoardId === board.id}
            onSelect={() => onSelect(board.id)}
            onDelete={() => onDelete(board.id)}
            onMoveUp={() => onMove(board.id, -1)}
            onMoveDown={() => onMove(board.id, 1)}
            canMoveUp={index > 0}
            canMoveDown={index < boards.length - 1}
            onDragStart={() => {
              dragIdRef.current = board.id;
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              const dragId = dragIdRef.current;
              if (dragId != null && dragId !== board.id) onReorder(dragId, board.id);
              dragIdRef.current = null;
            }}
          />
        ))}
      </ul>
      <button className="small-button" type="button" onClick={onAdd} disabled={adding}>
        {adding ? "추가 중" : "+ 보드 추가"}
      </button>
    </aside>
  );
}
