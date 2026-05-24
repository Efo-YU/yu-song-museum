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

export interface PageConfig {
  theme?: { primary_color?: string };
  description_markdown?: string;
  score_viewer_settings?: ScoreViewerSettings;
  downloads?: { allow_xml?: boolean; allow_mp3?: boolean };
}

export interface Song {
  id: string;
  title: string;
  bpm?: number;
  key?: string;
  credits?: Credits;
  youtube_id?: string;
  youtube_url?: string;
  audio_url?: string;
  score_url?: string;
  page_config?: PageConfig;
}
