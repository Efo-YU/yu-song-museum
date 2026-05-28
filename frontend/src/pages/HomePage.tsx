import songsData from "../data/songs.json";
import SongCard from "../components/SongCard";
import type { Song } from "../types/song";

const songs = songsData as Song[];

export default function HomePage() {
  return (
    <main className="home">
      <header className="site-header">
        <h1 className="site-header__wordmark">YU Song Museum</h1>
        <div className="site-header__rule">
          <span>&#9670;</span>
        </div>
        <p className="site-header__subtitle">
          A collection of AI-synthesized vocal works
        </p>
      </header>

      {songs.length === 0 ? (
        <p className="home__empty">The collection has not yet opened.</p>
      ) : (
        <>
          <p className="home__gallery-label">
            Collection — {songs.length} work{songs.length !== 1 ? "s" : ""}
          </p>
          <div className="song-grid">
            {songs.map((song, i) => (
              <SongCard key={song.slug} song={song} index={i + 1} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
