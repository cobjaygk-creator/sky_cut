export type View = "login" | "register" | "dashboard";
export type VideoStatus = "uploaded" | "extracting_audio" | "audio_extracted" | "transcribing" | "transcribed" | "failed";
export type ClipStatus = "pending" | "processing" | "completed" | "failed";
export type BlogClipStatus = ClipStatus | "awaiting_images" | "awaiting_script" | "awaiting_boards";
export type ScriptTone = "summary" | "hook" | "detailed";
export type SubtitleStyle = "basic" | "bold" | "shorts";
export type TargetLength = "short" | "long";
export type NarrationLanguage = "original" | "ko" | "en" | "ja";
export type ScriptModel = "gpt-4o-mini" | "gpt-4o";
export type TtsMode = "original_audio" | "ai_narration";
export type WizardBoardsStep = "video_style" | "edit_mode" | "quick" | "ready";
export type VisualStyleSlug = "fullscreen" | "card_news" | "info_dark" | "bold_hook";

export type VisualStyle = {
  slug: VisualStyleSlug | string;
  label: string;
  description: string;
  badge?: string | null;
  previewImage?: string | null;
  layout: string;
  caption: string;
  transitionSec: number;
  kenBurns: boolean;
};

/** Normalize persisted wizard_step; legacy boards/voice/style → edit_mode. */
export function parseWizardBoardsStep(value: string | null | undefined): WizardBoardsStep {
  if (value === "video_style" || value === "quick" || value === "ready" || value === "edit_mode") {
    return value;
  }
  // Legacy linear steps collapse into the new fork screen.
  if (value === "boards" || value === "voice" || value === "style") return "edit_mode";
  return "edit_mode";
}

export type User = {
  id: number;
  email: string;
  plan: string;
  monthly_usage: number;
  usage_limit: number;
  usage_month: string;
  created_at: string;
};

export type Video = {
  id: number;
  original_filename: string;
  stored_filename: string;
  content_type: string;
  file_size: number;
  status: VideoStatus;
  audio_path: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type VideoStatusResponse = Pick<Video, "id" | "status" | "audio_path" | "error_message" | "updated_at">;

export type Usage = {
  plan: string;
  plan_name: string;
  monthly_usage: number;
  usage_limit: number;
  remaining: number;
  usage_month: string;
  max_video_minutes: number;
};

export type Plan = {
  id: string;
  name: string;
  monthly_video_limit: number;
  max_video_minutes: number;
  description: string;
};

export type TranscriptSegment = { index: number; start: number; end: number; text: string };

export type Transcript = {
  id: number;
  video_id: number;
  status: "transcribing" | "transcribed" | "failed";
  text: string | null;
  segments: TranscriptSegment[];
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Highlight = {
  id: number;
  video_id: number;
  start_time: number;
  end_time: number;
  title: string;
  reason: string;
  content_type: string;
  score: number;
  created_at: string;
};

export type Clip = {
  id: number;
  video_id: number;
  highlight_id: number;
  output_path: string | null;
  subtitle_style: string | null;
  subtitle_path: string | null;
  subtitled_output_path: string | null;
  tts_mode: string;
  narration_script: string | null;
  narration_audio_path: string | null;
  narrated_output_path: string | null;
  status: ClipStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ClipMetadata = {
  id: number;
  clip_id: number;
  title_candidates: string[];
  description: string;
  hashtags: string[];
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

/** Temporary debug payload from the last successful blog render. */
export type RenderSpec = {
  engine?: string;
  requested_engine?: string;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  captions?: string;
  resolution?: string;
  fps?: number;
  board_count?: number;
  duration_seconds?: number;
  tts_speed?: number;
  bgm?: boolean;
  bgm_volume?: number | null;
  sfx_boards?: number;
  output_bytes?: number | null;
  output_file?: string | null;
};

export type BlogClip = {
  id: number;
  source_url: string;
  blog_title: string | null;
  narration_script: string | null;
  script_tone: ScriptTone | null;
  script_candidates: Partial<Record<ScriptTone, string>>;
  subtitle_style: string;
  subtitle_template_id: number | null;
  video_path: string | null;
  subtitled_video_path: string | null;
  status: BlogClipStatus;
  progress_stage: string;
  progress_percent: number;
  error_message: string | null;
  title_candidates: string[];
  description: string | null;
  hashtags: string[];
  metadata_error: string | null;
  tts_speed: number;
  bgm_asset_id: number | null;
  bgm_volume: number;
  active_version_id: number | null;
  target_length: TargetLength;
  narration_language: NarrationLanguage;
  script_model?: ScriptModel;
  default_voice: string | null;
  auto_bgm: boolean;
  auto_sfx: boolean;
  wizard_step: WizardBoardsStep | null;
  visual_style?: VisualStyleSlug | string;
  render_spec?: RenderSpec | null;
  created_at: string;
  updated_at: string;
};

export type BlogClipImageCandidate = {
  id: number;
  blog_clip_id: number;
  order_index: number;
  source_url: string | null;
  selected: boolean;
  created_at: string;
  updated_at: string;
};

export type BlogClipVersion = {
  id: number;
  blog_clip_id: number;
  label: string;
  source: string;
  script_tone: ScriptTone | null;
  narration_script: string | null;
  video_path: string | null;
  subtitled_video_path: string | null;
  status: BlogClipStatus;
  progress_stage: string;
  progress_percent: number;
  error_message: string | null;
  title_candidates: string[];
  description: string | null;
  hashtags: string[];
  metadata_error: string | null;
  is_active: boolean;
  render_spec?: RenderSpec | null;
  created_at: string;
  updated_at: string;
};

export type Voice = {
  id: string;
  name: string;
  description: string;
};

export type SubtitleTemplate = {
  id: number;
  user_id: number | null;
  name: string;
  slug: string | null;
  is_system: boolean;
  font_name: string;
  font_size: number;
  primary_color: string;
  outline_color: string;
  back_color: string;
  primary_alpha: number;
  outline_alpha: number;
  back_alpha: number;
  bold: boolean;
  outline: number;
  shadow: number;
  alignment: number;
  margin_l: number;
  margin_r: number;
  margin_v: number;
  border_style: number;
  created_at: string;
  updated_at: string;
};

export type Board = {
  id: number;
  blog_clip_id: number;
  order_index: number;
  image_path: string;
  text: string;
  speaker: string | null;
  duration_seconds: number | null;
  sfx_asset_id: number | null;
  created_at: string;
  updated_at: string;
};

export type AudioAsset = {
  id: number;
  user_id: number | null;
  kind: "bgm" | "sfx" | string;
  name: string;
  slug: string | null;
  is_system: boolean;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
};

export type StockPhoto = {
  id: number | null;
  photographer: string;
  alt: string;
  preview_url: string;
  download_url: string;
  width: number | null;
  height: number | null;
};

export type StockSearchResponse = {
  query: string;
  page: number;
  per_page: number;
  total_results: number;
  photos: StockPhoto[];
};
