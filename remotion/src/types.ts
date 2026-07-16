/**
 * BlogShorts props — keep in sync with:
 * - remotion/schemas/blog-shorts-props.schema.json
 * - backend BlogShortsPropsResponse / remotion_props_service.py
 */
export type BlogBoardProps = {
  boardId?: number | null;
  /** http(s) URL, or path under remotion/public for staticFile() */
  imageUrl?: string | null;
  text: string;
  /** Seconds this board is on screen */
  durationSec: number;
  backgroundColor?: string | null;
  speaker?: string | null;
};

export type VisualStyleSlug = "fullscreen" | "card_news" | "info_dark" | "bold_hook";

export type BlogShortsStyleProps = {
  layout: "fullscreen" | "card";
  caption: "bottom_box" | "card_title" | "card_bottom" | "dark_bar" | "bold_center";
  header: "none" | "overlay" | "card_white" | "info_navy" | "viral_black";
  accent: string;
  transitionSec: number;
  kenBurns: boolean;
};

export type BlogShortsProps = {
  blogClipId?: number | null;
  title?: string | null;
  /** Top template title (editable) */
  styleTitle?: string | null;
  /** Top template subtitle / accent line (editable) */
  styleSubtitle?: string | null;
  /** Fade overlap between boards in seconds */
  transitionSec?: number;
  source?: "dummy" | "blog_clip";
  /** staticFile-relative or absolute URL for full narration (TTS/BGM mix) */
  narrationUrl?: string | null;
  visualStyle?: VisualStyleSlug | string | null;
  style?: BlogShortsStyleProps | null;
  boards: BlogBoardProps[];
};

export const DEFAULT_BLOG_SHORTS_PROPS: BlogShortsProps = {
  blogClipId: null,
  title: "블로그 → 쇼츠 스파이크",
  styleTitle: "블로그 → 쇼츠 스파이크",
  styleSubtitle: "핵심만 짧게",
  transitionSec: 0.35,
  source: "dummy",
  visualStyle: "fullscreen",
  style: {
    layout: "fullscreen",
    caption: "bottom_box",
    header: "overlay",
    accent: "#FFE566",
    transitionSec: 0.35,
    kenBurns: true,
  },
  boards: [
    {
      text: "첫 3초, 훅으로 시선을 잡습니다",
      durationSec: 2.8,
      backgroundColor: "#1a3a4a",
    },
    {
      text: "본문 핵심을 짧게 보드로 나눕니다",
      durationSec: 3.2,
      backgroundColor: "#2d4a3e",
    },
    {
      text: "자막·전환은 Remotion으로 맞춥니다",
      durationSec: 3.0,
      backgroundColor: "#3d2a4a",
    },
  ],
};
