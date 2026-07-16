import type { BlogShortsProps } from "@new-cut/remotion/types";
import type { BlogClip, Board } from "../types";

const DEFAULT_BOARD_DURATION_SEC = 2.5;
const DEFAULT_TRANSITION_SEC = 0.35;

export function buildBlogShortsProps(options: {
  blogClip: BlogClip;
  boards: Board[];
  imageUrls: Record<number, string>;
  selectedBoardId: number | null;
  draftText: string;
  narrationUrl?: string | null;
}): BlogShortsProps {
  const { blogClip, boards, imageUrls, selectedBoardId, draftText, narrationUrl } = options;
  return {
    blogClipId: blogClip.id,
    title: blogClip.blog_title,
    transitionSec: DEFAULT_TRANSITION_SEC,
    source: "blog_clip",
    narrationUrl: narrationUrl ?? null,
    boards: boards.map((board) => ({
      boardId: board.id,
      imageUrl: imageUrls[board.id] ?? null,
      text: board.id === selectedBoardId ? draftText : board.text,
      durationSec:
        board.duration_seconds != null && board.duration_seconds > 0
          ? board.duration_seconds
          : DEFAULT_BOARD_DURATION_SEC,
      backgroundColor: null,
      speaker: board.speaker,
    })),
  };
}
