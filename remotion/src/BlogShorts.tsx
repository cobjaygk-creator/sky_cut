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
import type { BlogBoardProps, BlogShortsProps } from "./types";

const FPS = 30;
export const BLOG_SHORTS_WIDTH = 1080;
export const BLOG_SHORTS_HEIGHT = 1920;

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

function BoardScene({
  board,
  showTitle,
  title,
  showCaption = true,
}: {
  board: BlogBoardProps;
  showTitle: boolean;
  title?: string;
  /** Hide caption during crossfade tail so the next board's line takes over. */
  showCaption?: boolean;
}) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Keep zoom modest — blog source images are often ~966px wide; heavy zoom looks soft.
  const kenBurns = interpolate(frame, [0, durationInFrames], [1, 1.05], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const captionEnter = spring({
    frame,
    fps,
    config: { damping: 16, stiffness: 120 },
  });
  const captionY = interpolate(captionEnter, [0, 1], [48, 0]);
  const captionOpacity = showCaption ? interpolate(captionEnter, [0, 1], [0, 1]) : 0;

  const bg = board.backgroundColor ?? "#222222";
  const imageSrc = resolveBoardImageSrc(board.imageUrl);

  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: "hidden" }}>
      {imageSrc ? (
        <AbsoluteFill
          style={{
            transform: `scale(${kenBurns})`,
          }}
        >
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

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, transparent 28%, transparent 55%, rgba(0,0,0,0.72) 100%)",
        }}
      />

      {showTitle && title ? (
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
          {board.text}
        </div>
      </div>
    </AbsoluteFill>
  );
}

export const BlogShorts: React.FC<BlogShortsProps> = (props) => {
  const transitionSec = props.transitionSec ?? 0.35;
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
      // Extend into the next board for visual crossfade; total composition stays sum(spoken).
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
}: {
  board: BlogBoardProps;
  showTitle: boolean;
  title?: string;
  transitionFrames: number;
  spokenFrames: number;
  isFirst: boolean;
  isLast: boolean;
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

  // Caption follows spoken length only — not the visual crossfade tail.
  const showCaption = frame < spokenFrames;

  return (
    <AbsoluteFill style={{ opacity: Math.min(fadeIn, fadeOut) }}>
      <BoardScene board={board} showTitle={showTitle} title={title} showCaption={showCaption} />
    </AbsoluteFill>
  );
}
