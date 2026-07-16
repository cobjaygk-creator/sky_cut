import type { Board } from "../../types";
import { useBoardImageUrl } from "./useBoardImageUrl";

export function PreviewPane({
  blogClipId,
  board,
  draftText,
  onDraftChange,
  onTextBlur,
}: {
  blogClipId: number;
  board: Board | null;
  draftText: string;
  onDraftChange: (value: string) => void;
  onTextBlur: () => void;
}) {
  const { url, error } = useBoardImageUrl(blogClipId, board?.id ?? null, board?.image_path);

  if (!board) {
    return (
      <section className="preview-pane" aria-label="미리보기">
        <div className="preview-empty">
          <p>보드가 없습니다. 보드를 추가하세요.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="preview-pane" aria-label="미리보기">
      <div className="preview-frame" key={board.id}>
        {url && !error ? <img className="preview-image" src={url} alt={`보드 ${board.order_index + 1}`} /> : <div className="preview-placeholder">보드 {board.order_index + 1}</div>}
        <div className="preview-caption">{draftText.trim() || "나레이션 문구를 입력하세요"}</div>
      </div>
      <label className="preview-text-editor">
        나레이션 텍스트
        <textarea value={draftText} onChange={(event) => onDraftChange(event.target.value)} onBlur={onTextBlur} rows={4} />
      </label>
    </section>
  );
}
