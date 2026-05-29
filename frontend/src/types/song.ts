export interface Credits {
  vocalist?: string;
  composer?: string;
  lyricist?: string;
  [key: string]: string | undefined;
}

export interface ScoreViewerSettings {
  default_zoom?: number;
  default_visible_parts?: string[];
}

export interface LyricVerse {
  number: number;
  lines: string[];
}

export interface PageConfig {
  theme?: { primary_color?: string };
  description_markdown?: string;
  established?: string;
  source?: string;
  lyrics?: LyricVerse[];
  downloads?: { allow_xml?: boolean; allow_mp3?: boolean };
}

export interface SongVariant {
  slug: string;
  label: string;
  description?: string;
  youtube_id?: string;
  youtube_url?: string;
  audio_url?: string;
  score_url?: string;
  score_viewer_settings?: ScoreViewerSettings;
}

export interface Song {
  slug: string;
  title: string;
  bpm?: number;
  key?: string;
  credits?: Credits;
  page_config?: PageConfig;
  variants: SongVariant[];
  default_variant?: string;
}
