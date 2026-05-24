import { HashRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SongPage from './pages/SongPage';

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/songs/:id" element={<SongPage />} />
      </Routes>
    </HashRouter>
  );
}
