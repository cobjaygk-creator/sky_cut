import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  BlogShorts,
  BLOG_SHORTS_HEIGHT,
  BLOG_SHORTS_WIDTH,
  boardStartFrames,
  totalBlogShortsFrames,
} from "@new-cut/remotion/BlogShorts";
import { authorizedBlob, authorizedRequest } from "../../api/client";
import { buildBlogShortsProps } from "../../lib/blogShortsProps";
import type { BlogClip, Board } from "../../types";
import { BoardTimeline } from "./BoardTimeline";

const FPS = 30;

type PreviewAudioResponse = {
  blog_clip_id: number;
  duration_seconds: number;
  board_durations: number[];
  preview_audio_url: string;
};

export function RemotionPreviewPane({
  blogClip,
  boards,
  selectedBoardId,
  draftText,
  onDraftChange,
  onTextBlur,
  onSelectBoard,
  onDurationCommit,
  onBoardsSynced,
  bgmAssetId,
  bgmVolume,
}: {
  blogClip: BlogClip;
  boards: Board[];
  selectedBoardId: number | null;
  draftText: string;
  onDraftChange: (value: string) => void;
  onTextBlur: () => void;
  onSelectBoard: (boardId: number) => void;
  onDurationCommit: (boardId: number, durationSec: number) => void;
  /** Called after preview-audio rebuild writes TTS lengths onto boards. */
  onBoardsSynced?: () => void;
  /** Local editor overrides (BgmPanel) so cache invalidates after apply. */
  bgmAssetId?: number | null;
  bgmVolume?: number;
}) {
  const playerRef = useRef<PlayerRef>(null);
  const inputPropsRef = useRef(buildBlogShortsProps({
    blogClip,
    boards,
    imageUrls: {},
    selectedBoardId,
    draftText,
  }));
  const suppressSeekRef = useRef(false);
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});
  const [imagesLoading, setImagesLoading] = useState(false);
  const [imagesError, setImagesError] = useState("");
  const [currentFrame, setCurrentFrame] = useState(0);
  const [narrationUrl, setNarrationUrl] = useState<string | null>(null);
  const [audioStatus, setAudioStatus] = useState<"missing" | "ready" | "loading" | "error">("missing");
  const [audioError, setAudioError] = useState("");
  const [audioBusy, setAudioBusy] = useState(false);

  const imageCacheKey = useMemo(
    () => boards.map((board) => `${board.id}:${board.image_path}`).join("|"),
    [boards],
  );

  const resolvedBgmAssetId = bgmAssetId !== undefined ? bgmAssetId : blogClip.bgm_asset_id;
  const resolvedBgmVolume = bgmVolume !== undefined ? bgmVolume : blogClip.bgm_volume;

  const audioCacheKey = useMemo(
    () =>
      [
        blogClip.id,
        blogClip.tts_speed,
        resolvedBgmAssetId,
        resolvedBgmVolume,
        boards.map((b) => `${b.id}:${b.text}:${b.speaker}:${b.sfx_asset_id}:${b.duration_seconds}`).join("|"),
      ].join("::"),
    [blogClip.id, blogClip.tts_speed, resolvedBgmAssetId, resolvedBgmVolume, boards],
  );

  useEffect(() => {
    if (boards.length === 0) {
      setImageUrls({});
      setImagesError("");
      return;
    }

    let cancelled = false;
    const created: string[] = [];
    setImagesLoading(true);
    setImagesError("");

    void (async () => {
      try {
        const entries = await Promise.all(
          boards.map(async (board) => {
            const blob = await authorizedBlob(`/blog-clips/${blogClip.id}/boards/${board.id}/image`);
            const url = URL.createObjectURL(blob);
            created.push(url);
            return [board.id, url] as const;
          }),
        );
        if (!cancelled) {
          setImageUrls(Object.fromEntries(entries));
        }
      } catch (err) {
        if (!cancelled) {
          setImagesError(err instanceof Error ? err.message : "보드 이미지를 불러오지 못했습니다.");
          setImageUrls({});
        }
      } finally {
        if (!cancelled) setImagesLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      for (const url of created) URL.revokeObjectURL(url);
    };
  }, [blogClip.id, imageCacheKey, boards]);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setAudioStatus("loading");
    setAudioError("");

    void (async () => {
      try {
        const blob = await authorizedBlob(`/blog-clips/${blogClip.id}/preview-audio`);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setNarrationUrl(objectUrl);
        setAudioStatus("ready");
      } catch {
        if (cancelled) return;
        setNarrationUrl(null);
        setAudioStatus("missing");
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [blogClip.id, audioCacheKey]);

  async function generatePreviewAudio() {
    setAudioBusy(true);
    setAudioError("");
    try {
      await authorizedRequest<PreviewAudioResponse>(`/blog-clips/${blogClip.id}/preview-audio`, {
        method: "POST",
      });
      const blob = await authorizedBlob(`/blog-clips/${blogClip.id}/preview-audio`);
      setNarrationUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(blob);
      });
      setAudioStatus("ready");
      onBoardsSynced?.();
    } catch (err) {
      setAudioStatus("error");
      setAudioError(err instanceof Error ? err.message : "미리듣기 오디오 생성에 실패했습니다.");
    } finally {
      setAudioBusy(false);
    }
  }

  const inputProps = useMemo(
    () =>
      buildBlogShortsProps({
        blogClip,
        boards,
        imageUrls,
        selectedBoardId,
        draftText,
        narrationUrl,
      }),
    [blogClip, boards, imageUrls, selectedBoardId, draftText, narrationUrl],
  );
  inputPropsRef.current = inputProps;

  const durationInFrames = useMemo(() => totalBlogShortsFrames(inputProps), [inputProps]);
  const boardDurationsSec = useMemo(
    () => inputProps.boards.map((board) => board.durationSec),
    [inputProps.boards],
  );
  const boardStartFramesList = useMemo(() => boardStartFrames(inputProps), [inputProps]);

  // User-driven board select → seek to board start (skip when selection came from playhead)
  useEffect(() => {
    if (selectedBoardId == null || boards.length === 0) return;
    if (suppressSeekRef.current) {
      suppressSeekRef.current = false;
      return;
    }
    const index = boards.findIndex((board) => board.id === selectedBoardId);
    if (index < 0) return;
    const starts = boardStartFrames(inputPropsRef.current);
    const frame = starts[index] ?? 0;
    playerRef.current?.seekTo(frame);
    setCurrentFrame(frame);
  }, [selectedBoardId, boards]);

  // Player frame → playhead + highlight board under playhead (no seek loop)
  useEffect(() => {
    const player = playerRef.current;
    if (!player || imagesLoading || imagesError) return;

    const onFrame = () => {
      const frame = player.getCurrentFrame();
      setCurrentFrame(frame);
      const props = inputPropsRef.current;
      const starts = boardStartFrames(props);
      let index = 0;
      for (let i = 0; i < starts.length; i += 1) {
        if (frame >= (starts[i] ?? 0)) index = i;
      }
      const board = boards[index];
      if (board && board.id !== selectedBoardId) {
        suppressSeekRef.current = true;
        onSelectBoard(board.id);
      }
    };

    player.addEventListener("frameupdate", onFrame);
    return () => {
      player.removeEventListener("frameupdate", onFrame);
    };
  }, [imagesLoading, imagesError, boards, selectedBoardId, onSelectBoard, durationInFrames]);

  function seekFrame(frame: number) {
    const clamped = Math.max(0, Math.min(durationInFrames - 1, frame));
    playerRef.current?.seekTo(clamped);
    setCurrentFrame(clamped);
    const props = inputPropsRef.current;
    const starts = boardStartFrames(props);
    let index = 0;
    for (let i = 0; i < starts.length; i += 1) {
      if (clamped >= (starts[i] ?? 0)) index = i;
    }
    const board = boards[index];
    if (board && board.id !== selectedBoardId) {
      suppressSeekRef.current = true;
      onSelectBoard(board.id);
    }
  }

  if (boards.length === 0) {
    return (
      <section className="preview-pane" aria-label="Remotion 미리보기">
        <div className="preview-empty">
          <p>보드가 없습니다. 보드를 추가하세요.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="preview-pane preview-pane-remotion" aria-label="Remotion 미리보기">
      <div className="preview-player-wrap">
        {imagesLoading ? <p className="muted preview-player-status">이미지 불러오는 중…</p> : null}
        {imagesError ? (
          <p className="form-message preview-player-status" role="alert">
            {imagesError}
          </p>
        ) : null}
        {!imagesLoading && !imagesError ? (
          <Player
            ref={playerRef}
            component={BlogShorts}
            inputProps={inputProps}
            durationInFrames={durationInFrames}
            compositionWidth={BLOG_SHORTS_WIDTH}
            compositionHeight={BLOG_SHORTS_HEIGHT}
            fps={FPS}
            style={{ width: "100%", aspectRatio: "9 / 16" }}
            controls
            loop
            clickToPlay
            acknowledgeRemotionLicense
          />
        ) : (
          <div className="preview-frame preview-frame-waiting" />
        )}
      </div>

      <div className="preview-audio-bar">
        {audioStatus === "ready" ? (
          <p className="muted">TTS/BGM 미리듣기 연결됨 (최종 렌더와 동일 믹스·덕킹)</p>
        ) : audioStatus === "loading" ? (
          <p className="muted">미리듣기 오디오 확인 중…</p>
        ) : (
          <p className="muted">나레이션/BGM은 미리듣기를 생성해야 Player에서 들립니다.</p>
        )}
        <button
          type="button"
          className="small-button"
          disabled={audioBusy}
          onClick={() => void generatePreviewAudio()}
        >
          {audioBusy ? "생성 중…" : audioStatus === "ready" ? "TTS/BGM 다시 생성" : "TTS/BGM 미리듣기 생성"}
        </button>
        {audioError ? (
          <p className="form-message" role="alert">
            {audioError}
          </p>
        ) : null}
      </div>

      {!imagesLoading && !imagesError ? (
        <BoardTimeline
          boards={boards}
          selectedBoardId={selectedBoardId}
          boardDurationsSec={boardDurationsSec}
          boardStartFramesList={boardStartFramesList}
          currentFrame={currentFrame}
          durationInFrames={durationInFrames}
          fps={FPS}
          onSelectBoard={onSelectBoard}
          onSeekFrame={seekFrame}
          onDurationCommit={onDurationCommit}
        />
      ) : null}

      <p className="muted preview-remotion-note">
        타임라인 길이는 TTS 보드 길이와 같고, 오디오는 최종 Remotion 렌더와 같은 믹스(사이드체인 덕킹)를 씁니다.
      </p>
      <label className="preview-text-editor">
        나레이션 텍스트
        <textarea value={draftText} onChange={(event) => onDraftChange(event.target.value)} onBlur={onTextBlur} rows={4} />
      </label>
    </section>
  );
}
