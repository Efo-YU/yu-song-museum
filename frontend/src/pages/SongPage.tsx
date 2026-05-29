import { lazy, Suspense } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { marked } from 'marked';
import songsData from '../data/songs.json';
import type { Song, SongVariant } from '../types/song';

const ScoreViewer = lazy(() => import('../components/ScoreViewer'));

const songs = songsData as Song[];

export default function SongPage() {
  const { slug, variant: variantParam } = useParams<{ slug: string; variant: string }>();
  const navigate = useNavigate();

  const song = songs.find((s) => s.slug === slug);

  if (!song) {
    return (
      <main className="song-page">
        <Link to="/" className="back-link">← Collection</Link>
        <p className="song-page__not-found">This work could not be found.</p>
      </main>
    );
  }

  const defaultSlug = song.default_variant ?? song.variants[0]?.slug;
  const activeSlug = variantParam ?? defaultSlug;
  const activeVariant: SongVariant | undefined = song.variants.find((v) => v.slug === activeSlug)
    ?? song.variants[0];

  const multipleVariants = song.variants.length > 1;

  function handleVariantSelect(v: SongVariant) {
    if (v.slug === defaultSlug) {
      navigate(`/songs/${song!.slug}`);
    } else {
      navigate(`/songs/${song!.slug}/${v.slug}`);
    }
  }

  const pc = song.page_config;
  const allowXml = pc?.downloads?.allow_xml ?? true;
  const allowMp3 = pc?.downloads?.allow_mp3 ?? true;

  return (
    <main className="song-page">
      <Link to="/" className="back-link">← Collection</Link>

      <header className="song-page__header">
        <h1 className="song-page__title">{song.title}</h1>
        <div className="song-page__divider" />

        {song.credits && (
          <dl className="song-page__credits">
            {Object.entries(song.credits).map(([role, name]) =>
              name ? (
                <div key={role} className="song-page__credit-row">
                  <dt>{creditLabel(role)}</dt>
                  <dd>{name}</dd>
                </div>
              ) : null,
            )}
          </dl>
        )}

        {(song.bpm || song.key) && (
          <p className="song-page__meta">
            {[song.key, song.bpm ? `${song.bpm} bpm` : '']
              .filter(Boolean)
              .join('  ·  ')}
          </p>
        )}
      </header>

      {multipleVariants && (
        <nav className="variant-tabs" aria-label="Variants">
          {song.variants.map((v) => (
            <button
              key={v.slug}
              type="button"
              className={`variant-tab${v.slug === activeVariant?.slug ? ' variant-tab--active' : ''}`}
              onClick={() => handleVariantSelect(v)}
            >
              {v.label}
              {v.description && (
                <span className="variant-tab__desc">{v.description}</span>
              )}
            </button>
          ))}
        </nav>
      )}

      {activeVariant?.youtube_id && (
        <section className="song-page__video">
          <iframe
            width="100%"
            style={{ aspectRatio: '16/9', border: 'none', display: 'block' }}
            src={`https://www.youtube.com/embed/${activeVariant.youtube_id}`}
            title={`${song.title} — ${activeVariant.label}`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </section>
      )}

      {pc?.description_markdown && (
        <section className="song-page__description">
          <h2 className="section-heading">この作品について</h2>
          <div
            className="prose"
            dangerouslySetInnerHTML={{ __html: marked.parse(pc.description_markdown) as string }}
          />
          {pc.source && (
            <p className="song-page__source">出典：{pc.source}</p>
          )}
        </section>
      )}

      {pc?.lyrics && pc.lyrics.length > 0 && (
        <section className="song-page__lyrics">
          <h2 className="section-heading">歌詞</h2>
          <ol className="lyrics-list">
            {pc.lyrics.map((verse) => (
              <li key={verse.number} className="lyrics-verse">
                {verse.lines.map((line, i) => (
                  <span key={i} className="lyrics-line">{line}</span>
                ))}
              </li>
            ))}
          </ol>
        </section>
      )}

      {activeVariant?.score_url && (
        <section className="song-page__score">
          <h2 className="section-heading">Score</h2>
          <Suspense fallback={<p className="score-status">Loading score…</p>}>
            <ScoreViewer
              url={activeVariant.score_url}
              settings={activeVariant.score_viewer_settings}
            />
          </Suspense>
        </section>
      )}

      {allowMp3 && activeVariant?.audio_url && (
        <section className="song-page__audio">
          <h2 className="section-heading">Listen — {activeVariant.label}</h2>
          <audio
            key={activeVariant.audio_url}
            controls
            src={activeVariant.audio_url}
            className="audio-player"
          />
        </section>
      )}

      <section className="song-page__downloads">
        <h2 className="section-heading">Downloads &amp; Links</h2>
        <ul className="download-list">
          {allowMp3 && activeVariant?.audio_url && (
            <li>
              <a href={activeVariant.audio_url} download className="download-link">
                Audio — {activeVariant.label} (MP3)
              </a>
            </li>
          )}
          {allowXml && activeVariant?.score_url && (
            <li>
              <a href={activeVariant.score_url} download className="download-link">
                Score (MusicXML)
              </a>
            </li>
          )}
          {activeVariant?.youtube_url && (
            <li>
              <a
                href={activeVariant.youtube_url}
                target="_blank"
                rel="noopener noreferrer"
                className="download-link"
              >
                Watch on YouTube ↗
              </a>
            </li>
          )}
        </ul>
      </section>
    </main>
  );
}

const CREDIT_LABELS: Record<string, string> = {
  lyricist: 'Lyricist',
  composer: 'Composer',
  vocalist: 'Covered by',
};

function creditLabel(role: string): string {
  return CREDIT_LABELS[role] ?? role.charAt(0).toUpperCase() + role.slice(1);
}
