import type { BlogShortsProps, BlogShortsStyleProps } from "@new-cut/remotion/types";
import type { BlogClip, Board } from "../types";

const DEFAULT_BOARD_DURATION_SEC = 2.5;
const DEFAULT_TRANSITION_SEC = 0.35;

const STYLE_BY_VISUAL: Record<string, BlogShortsStyleProps> = {
  fullscreen: {
    layout: "fullscreen",
    caption: "bottom_box",
    header: "overlay",
    accent: "#FFE566",
    transitionSec: 0.35,
    kenBurns: true,
  },
  card_news: {
    layout: "card",
    caption: "card_bottom",
    header: "card_white",
    accent: "#1f6b4a",
    transitionSec: 0.35,
    kenBurns: true,
  },
  info_dark: {
    layout: "fullscreen",
    caption: "dark_bar",
    header: "info_navy",
    accent: "#7CFFB2",
    transitionSec: 0.35,
    kenBurns: true,
  },
  bold_hook: {
    layout: "fullscreen",
    caption: "bold_center",
    header: "viral_black",
    accent: "#5EF2D0",
    transitionSec: 0.25,
    kenBurns: true,
  },
};

export function buildBlogShortsProps(options: {
  blogClip: BlogClip;
  boards: Board[];
  imageUrls: Record<number, string>;
  selectedBoardId: number | null;
  draftText: string;
  narrationUrl?: string | null;
  styleTitle?: string | null;
  styleSubtitle?: string | null;
}): BlogShortsProps {
  const {
    blogClip,
    boards,
    imageUrls,
    selectedBoardId,
    draftText,
    narrationUrl,
    styleTitle,
    styleSubtitle,
  } = options;
  const visualStyle = blogClip.visual_style || "fullscreen";
  const style = STYLE_BY_VISUAL[visualStyle] ?? STYLE_BY_VISUAL.fullscreen;
  const resolvedTitle =
    (styleTitle !== undefined ? styleTitle : blogClip.style_title) || blogClip.blog_title || null;
  const resolvedSubtitle =
    styleSubtitle !== undefined ? styleSubtitle : blogClip.style_subtitle ?? null;
  return {
    blogClipId: blogClip.id,
    title: blogClip.blog_title,
    styleTitle: resolvedTitle,
    styleSubtitle: resolvedSubtitle,
    transitionSec: style.transitionSec ?? DEFAULT_TRANSITION_SEC,
    source: "blog_clip",
    narrationUrl: narrationUrl ?? null,
    visualStyle,
    style,
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
