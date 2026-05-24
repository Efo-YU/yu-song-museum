import { Link } from 'react-router-dom';
import type { Song } from '../types/song';

interface Props {
  song: Song;
}

export default function SongCard({ song }: Props) {
  const primaryColor = song.page_config?.theme?.primary_color ?? '#4a90d9';

  return (
    <Link
      to={`/songs/${song.id}`}
      className="song-card"
      style={{ '--accent': primaryColor } as React.CSSProperties}
    >
      <div className="song-card__accent" />
      <div className="song-card__body">
        <h2 className="song-card__title">{song.title}</h2>
        {song.credits && (
          <p className="song-card__credits">
            {[song.credits.composer, song.credits.vocalist]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}
        {song.bpm && (
          <p className="song-card__meta">
            {song.key ?? ''} · {song.bpm} BPM
          </p>
        )}
      </div>
    </Link>
  );
}
