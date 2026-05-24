import songsData from '../data/songs.json';
import SongCard from '../components/SongCard';
import type { Song } from '../types/song';

const songs = songsData as Song[];

export default function HomePage() {
  return (
    <main className="home">
      <header className="home__header">
        <h1 className="home__title">Yu Song Museum</h1>
        <p className="home__subtitle">AI-synthesized music, scored and streamed.</p>
      </header>

      {songs.length === 0 ? (
        <p className="home__empty">No songs published yet.</p>
      ) : (
        <div className="song-grid">
          {songs.map((song) => (
            <SongCard key={song.id} song={song} />
          ))}
        </div>
      )}
    </main>
  );
}
