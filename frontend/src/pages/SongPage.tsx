import { lazy, Suspense } from 'react';
import { useParams, Link } from 'react-router-dom';
import songsData from '../data/songs.json';
import type { Song } from '../types/song';

const ScoreViewer = lazy(() => import('../components/ScoreViewer'));

const songs = songsData as Song[];

export default function SongPage() {
  const { id } = useParams<{ id: string }>();
  const song = songs.find((s) => s.id === id);

  if (!song) {
    return (
      <main className="song-page">
        <Link to="/" className="back-link">← Collection</Link>
        <p className="song-page__not-found">This work could not be found.</p>
      </main>
    );
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

      {song.youtube_id && (
        <section className="song-page__video">
          <iframe
            width="100%"
            style={{ aspectRatio: '16/9', border: 'none', display: 'block' }}
            src={`https://www.youtube.com/embed/${song.youtube_id}`}
            title={song.title}
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

      {song.score_url && (
        <section className="song-page__score">
          <h2 className="section-heading">Score</h2>
          <Suspense fallback={<p className="score-status">Loading score…</p>}>
            <ScoreViewer
              url={song.score_url}
              settings={pc?.score_viewer_settings}
            />
          </Suspense>
        </section>
      )}

      <section className="song-page__downloads">
        <h2 className="section-heading">Downloads &amp; Links</h2>
        <ul className="download-list">
          {allowMp3 && song.audio_url && (
            <li>
              <a href={song.audio_url} download className="download-link">
                Audio (MP3)
              </a>
            </li>
          )}
          {allowXml && song.score_url && (
            <li>
              <a href={song.score_url} download className="download-link">
                Score (MusicXML)
              </a>
            </li>
          )}
          {song.youtube_url && (
            <li>
              <a
                href={song.youtube_url}
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
