import React from "react";
import { Composition, CalculateMetadataFunction } from "remotion";
import { BlogShorts, BLOG_SHORTS_HEIGHT, BLOG_SHORTS_WIDTH, totalBlogShortsFrames } from "./BlogShorts";
import { DEFAULT_BLOG_SHORTS_PROPS, type BlogShortsProps } from "./types";

const FPS = 30;

const calculateBlogShortsMetadata: CalculateMetadataFunction<BlogShortsProps> = ({
  props,
}) => {
  return {
    durationInFrames: totalBlogShortsFrames(props),
    fps: FPS,
    width: BLOG_SHORTS_WIDTH,
    height: BLOG_SHORTS_HEIGHT,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BlogShorts"
        component={BlogShorts}
        durationInFrames={totalBlogShortsFrames(DEFAULT_BLOG_SHORTS_PROPS)}
        fps={FPS}
        width={BLOG_SHORTS_WIDTH}
        height={BLOG_SHORTS_HEIGHT}
        defaultProps={DEFAULT_BLOG_SHORTS_PROPS}
        calculateMetadata={calculateBlogShortsMetadata}
      />
    </>
  );
};
