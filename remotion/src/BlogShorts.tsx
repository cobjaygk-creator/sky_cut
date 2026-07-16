import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { BlogBoardProps, BlogShortsProps, BlogShortsStyleProps } from "./types";

const FPS = 30;
export const BLOG_SHORTS_WIDTH = 1080;
export const BLOG_SHORTS_HEIGHT = 1920;

const STYLE_BY_VISUAL: Record<string, BlogShortsStyleProps> = {
  fullscreen: { layout: "fullscreen", caption: "bottom_box", transitionSec: 0.35, kenBurns: true },
  card_news: { layout: "card", caption: "card_title", transitionSec: 0.35, kenBurns: true },
  info_dark: { layout: "fullscreen", caption: "dark_bar", transitionSec: 0.35, kenBurns: true },
  bold_hook: { layout: "fullscreen", caption: "bold_center", transitionSec: 0.25, kenBurns: true },
};

/** Resolve API/http URLs or remotion/public-relative paths for <Img>. */
export function resolveBoardImageSrc(imageUrl?: string | null): string | undefined {
  if (!imageUrl) return undefined;
  const trimmed = imageUrl.trim();
  if (!trimmed) return undefined;
  if (/^(https?:|data:|blob:)/i.test(trimmed)) {
    return trimmed;
  }
  return staticFile(trimmed.replace(/^\//, ""));
}

function boardFrames(durationSec: number): number {
  return Math.max(1, Math.round(durationSec * FPS));
}

function resolveStyle(props: BlogShortsProps): BlogShortsStyleProps {
  if (props.style?.layout && props.style?.caption) {
    return {
      layout: props.style.layout,
      caption: props.style.caption,
      transitionSec: props.style.transitionSec ?? props.transitionSec ?? 0.35,
      kenBurns: props.style.kenBurns ?? true,
    };
  }
  const key = props.visualStyle ?? "fullscreen";
  return STYLE_BY_VISUAL[key] ?? STYLE_BY_VISUAL.fullscreen;
}

export function totalBlogShortsFrames(props: BlogShortsProps): number {
  const starts = boardStartFrames(props);
  const boards = props.boards ?? [];
  if (boards.length === 0) {
    return FPS * 3;
  }
  const last = boards[boards.length - 1];
  const lastStart = starts[starts.length - 1] ?? 0;
  return Math.max(FPS, lastStart + boardFrames(last.durationSec));
}

/**
 * Start frame (inclusive) for each board — used by Player seek-on-select.
 * Sequential (sum of TTS durations) so composition length matches narration audio.
 * Crossfades extend each Sequence into the next board without shortening the total.
 */
export function boardStartFrames(props: BlogShortsProps): number[] {
  const boards = props.boards ?? [];
  const starts: number[] = [];
  let cursor = 0;
  for (const board of boards) {
    starts.push(cursor);
    cursor += boardFrames(board.durationSec);
  }
  return starts;
}

function CaptionBlock({
  text,
  caption,
  captionY,
  captionOpacity,
}: {
  text: string;
  caption: BlogShortsStyleProps["caption"];
  captionY: number;
  captionOpacity: number;
}) {
  if (caption === "card_title") {
    return (
      <div
        style={{
          position: "absolute",
          left: 48,
          right: 48,
          bottom: 180,
          transform: `translateY(${captionY}px)`,
          opacity: captionOpacity,
        }}
      >
        <div
          style={{
            padding: "28px 28px 32px",
            borderRadius: 28,
            backgroundColor: "rgba(255,255,255,0.96)",
            color: "#151515",
            fontSize: 46,
            fontWeight: 800,
            fontFamily: "Pretendard, Noto Sans KR, sans-serif",
            lineHeight: 1.35,
            letterSpacing: "-0.02em",
            boxShadow: "0 18px 40px rgba(0,0,0,0.28)",
          }}
        >
          {text}
        </div>
      </div>
    );
  }

  if (caption === "dark_bar") {
    return (
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          transform: `translateY(${captionY}px)`,
          opacity: captionOpacity,
          padding: "40px 56px 220px",
          background: "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.82) 45%, rgba(0,0,0,0.92) 100%)",
        }}
      >
        <div
          style={{
            color: "#f4f4f4",
            fontSize: 44,
            fontWeight: 650,
            fontFamily: "Pretendard, Noto Sans KR, sans-serif",
            lineHeight: 1.4,
            letterSpacing: "-0.01em",
            textAlign: "left",
          }}
        >
          {text}
        </div>
      </div>
    );
  }

  if (caption === "bold_center") {
    return (
      <div
        style={{
          position: "absolute",
          left: 48,
          right: 48,
          top: "42%",
          transform: `translateY(${captionY}px)`,
          opacity: captionOpacity,
          textAlign: "center",
        }}
      >
        <div
          style={{
            color: "#ffffff",
            fontSize: 64,
            fontWeight: 900,
            fontFamily: "Pretendard, Noto Sans KR, sans-serif",
            lineHeight: 1.25,
            letterSpacing: "-0.03em",
            textShadow: "0 4px 28px rgba(0,0,0,0.65)",
          }}
        >
          {text}
        </div>
      </div>
    );
  }

  // bottom_box (default)
  return (
    <div
      style={{
        position: "absolute",
        left: 56,
        right: 56,
        bottom: 220,
        transform: `translateY(${captionY}px)`,
        opacity: captionOpacity,
      }}
    >
      <div
        style={{
          display: "inline-block",
          maxWidth: "100%",
          padding: "18px 22px",
          borderRadius: 14,
          backgroundColor: "rgba(0, 0, 0, 0.55)",
          color: "#ffffff",
          fontSize: 48,
          fontWeight: 700,
          fontFamily: "Pretendard, Noto Sans KR, sans-serif",
          lineHeight: 1.35,
          letterSpacing: "-0.02em",
          textAlign: "center",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        {text}
      </div>
    </div>
  );
}

function BoardScene({
  board,
  showTitle,
  title,
  showCaption = true,
  style,
}: {
  board: BlogBoardProps;
  showTitle: boolean;
  title?: string;
  showCaption?: boolean;
  style: BlogShortsStyleProps;
}) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const kenBurns = style.kenBurns
    ? interpolate(frame, [0, durationInFrames], [1, 1.05], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  const captionEnter = spring({
    frame,
    fps,
    config: { damping: 16, stiffness: 120 },
  });
  const captionY = interpolate(captionEnter, [0, 1], [48, 0]);
  const captionOpacity = showCaption ? interpolate(captionEnter, [0, 1], [0, 1]) : 0;

  const bg = board.backgroundColor ?? "#222222";
  const imageSrc = resolveBoardImageSrc(board.imageUrl);
  const isCard = style.layout === "card";

  return (
    <AbsoluteFill style={{ backgroundColor: isCard ? "#0f1115" : bg, overflow: "hidden" }}>
      {isCard ? (
        <div
          style={{
            position: "absolute",
            top: 120,
            left: 48,
            right: 48,
            height: 980,
            borderRadius: 32,
            overflow: "hidden",
            transform: `scale(${kenBurns})`,
            boxShadow: "0 24px 60px rgba(0,0,0,0.45)",
          }}
        >
          {imageSrc ? (
            <Img
              src={imageSrc}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          ) : (
            <div
              style={{
                width: "100%",
                height: "100%",
                background: `radial-gradient(circle at 30% 20%, rgba(255,255,255,0.12), transparent 50%), ${bg}`,
              }}
            />
          )}
        </div>
      ) : (
        <>
          {imageSrc ? (
            <AbsoluteFill style={{ transform: `scale(${kenBurns})` }}>
              <Img
                src={imageSrc}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  imageRendering: "auto",
                }}
              />
            </AbsoluteFill>
          ) : (
            <AbsoluteFill
              style={{
                background: `radial-gradient(circle at 30% 20%, rgba(255,255,255,0.12), transparent 50%), ${bg}`,
                transform: `scale(${kenBurns})`,
              }}
            />
          )}
          {style.caption !== "dark_bar" ? (
            <AbsoluteFill
              style={{
                background:
                  "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, transparent 28%, transparent 55%, rgba(0,0,0,0.72) 100%)",
              }}
            />
          ) : null}
        </>
      )}

      {showTitle && title && style.caption !== "bold_center" ? (
        <div
          style={{
            position: "absolute",
            top: 96,
            left: 64,
            right: 64,
            color: "#ffffff",
            fontSize: 42,
            fontWeight: 800,
            fontFamily: "Pretendard, Noto Sans KR, sans-serif",
            lineHeight: 1.25,
            textShadow: "0 2px 12px rgba(0,0,0,0.45)",
          }}
        >
          {title}
        </div>
      ) : null}

      <CaptionBlock
        text={board.text}
        caption={style.caption}
        captionY={captionY}
        captionOpacity={captionOpacity}
      />
    </AbsoluteFill>
  );
}

export const BlogShorts: React.FC<BlogShortsProps> = (props) => {
  const style = resolveStyle(props);
  const transitionSec = props.transitionSec ?? style.transitionSec ?? 0.35;
  const transitionFrames = boardFrames(transitionSec);
  const boards = props.boards ?? [];

  const timeline = useMemo(() => {
    const items: {
      board: BlogBoardProps;
      from: number;
      duration: number;
      spoken: number;
      index: number;
    }[] = [];
    let cursor = 0;
    boards.forEach((board, index) => {
      const spoken = boardFrames(board.durationSec);
      const overlap =
        index < boards.length - 1 ? Math.min(transitionFrames, Math.max(0, spoken - 1)) : 0;
      items.push({ board, from: cursor, duration: spoken + overlap, spoken, index });
      cursor += spoken;
    });
    return items;
  }, [boards, transitionFrames]);

  const narrationSrc = resolveBoardImageSrc(props.narrationUrl);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {narrationSrc ? <Audio src={narrationSrc} /> : null}
      {timeline.map(({ board, from, duration, spoken, index }) => (
        <Sequence key={index} from={from} durationInFrames={duration} name={`board-${index}`}>
          <FadingBoard
            board={board}
            showTitle={index === 0}
            title={props.title ?? undefined}
            transitionFrames={transitionFrames}
            spokenFrames={spoken}
            isFirst={index === 0}
            isLast={index === timeline.length - 1}
            style={style}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

function FadingBoard({
  board,
  showTitle,
  title,
  transitionFrames,
  spokenFrames,
  isFirst,
  isLast,
  style,
}: {
  board: BlogBoardProps;
  showTitle: boolean;
  title?: string;
  transitionFrames: number;
  spokenFrames: number;
  isFirst: boolean;
  isLast: boolean;
  style: BlogShortsStyleProps;
}) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const fadeIn = isFirst
    ? 1
    : interpolate(frame, [0, transitionFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
  const fadeOut = isLast
    ? 1
    : interpolate(
        frame,
        [durationInFrames - transitionFrames, durationInFrames],
        [1, 0],
        {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        },
      );

  const showCaption = frame < spokenFrames;

  return (
    <AbsoluteFill style={{ opacity: Math.min(fadeIn, fadeOut) }}>
      <BoardScene
        board={board}
        showTitle={showTitle}
        title={title}
        showCaption={showCaption}
        style={style}
      />
    </AbsoluteFill>
  );
}
