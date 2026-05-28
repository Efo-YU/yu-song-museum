import { Link } from 'react-router-dom';
import type { Song } from '../types/song';

interface Props {
  song: Song;
  index?: number;
}

export default function SongCard({ song, index }: Props) {
  const num = index !== undefined ? String(index).padStart(2, '0') : '';

  return (
    <Link to={`/songs/${song.slug}`} className="song-card">
      {num && <p className="song-card__number">No. {num}</p>}
      <h2 className="song-card__title">{song.title}</h2>
      {song.credits && (
        <p className="song-card__credits">
          {[song.credits.composer, song.credits.vocalist]
            .filter(Boolean)
            .join(' · ')}
        </p>
      )}
      {(song.key || song.bpm) && (
        <p className="song-card__meta">
          {[song.key, song.bpm ? `${song.bpm} bpm` : ''].filter(Boolean).join('  ·  ')}
        </p>
      )}
      {song.versions.length > 1 && (
        <p className="song-card__versions">{song.versions.length} versions</p>
      )}
    </Link>
  );
}
