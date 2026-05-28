import { lazy, Suspense } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import songsData from '../data/songs.json';
import type { Song, SongVersion } from '../types/song';

const ScoreViewer = lazy(() => import('../components/ScoreViewer'));

const songs = songsData as Song[];

export default function SongPage() {
  const { slug, version: versionParam } = useParams<{ slug: string; version: string }>();
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

  const defaultSlug = song.default_version ?? song.versions[0]?.slug;
  const activeSlug = versionParam ?? defaultSlug;
  const activeVersion: SongVersion | undefined = song.versions.find((v) => v.slug === activeSlug)
    ?? song.versions[0];

  const multipleVersions = song.versions.length > 1;

  function handleVersionSelect(v: SongVersion) {
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
                  <dt>{capitalize(role)}</dt>
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

      {multipleVersions && (
        <nav className="version-tabs" aria-label="Versions">
          {song.versions.map((v) => (
            <button
              key={v.slug}
              type="button"
              className={`version-tab${v.slug === activeVersion?.slug ? ' version-tab--active' : ''}`}
              onClick={() => handleVersionSelect(v)}
            >
              {v.label}
              {v.description && (
                <span className="version-tab__desc">{v.description}</span>
              )}
            </button>
          ))}
        </nav>
      )}

      {activeVersion?.youtube_id && (
        <section className="song-page__video">
          <iframe
            width="100%"
            style={{ aspectRatio: '16/9', border: 'none', display: 'block' }}
            src={`https://www.youtube.com/embed/${activeVersion.youtube_id}`}
            title={`${song.title} — ${activeVersion.label}`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </section>
      )}

      {pc?.description_markdown && (
        <section className="song-page__description">
          <h2 className="section-heading">About this work</h2>
          <p>{pc.description_markdown}</p>
        </section>
      )}

      {activeVersion?.score_url && (
        <section className="song-page__score">
          <h2 className="section-heading">Score</h2>
          <Suspense fallback={<p className="score-status">Loading score…</p>}>
            <ScoreViewer
              url={activeVersion.score_url}
              settings={activeVersion.score_viewer_settings}
            />
          </Suspense>
        </section>
      )}

      {allowMp3 && activeVersion?.audio_url && (
        <section className="song-page__audio">
          <h2 className="section-heading">Listen — {activeVersion.label}</h2>
          <audio
            key={activeVersion.audio_url}
            controls
            src={activeVersion.audio_url}
            className="audio-player"
          />
        </section>
      )}

      <section className="song-page__downloads">
        <h2 className="section-heading">Downloads &amp; Links</h2>
        <ul className="download-list">
          {allowMp3 && activeVersion?.audio_url && (
            <li>
              <a href={activeVersion.audio_url} download className="download-link">
                Audio — {activeVersion.label} (MP3)
              </a>
            </li>
          )}
          {allowXml && activeVersion?.score_url && (
            <li>
              <a href={activeVersion.score_url} download className="download-link">
                Score (MusicXML)
              </a>
            </li>
          )}
          {activeVersion?.youtube_url && (
            <li>
              <a
                href={activeVersion.youtube_url}
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

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
