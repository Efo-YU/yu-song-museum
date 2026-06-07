import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Base path: set VITE_BASE_URL in CI to /<repo-name>/ for GitHub Pages project sites.
// Falls back to '/' for local dev and user/org sites.
//
// VITE_SINGLE_FILE=1: merge all dynamic imports into the main chunk so the
// archive build's post-process step can inline everything into a single
// index.html that opens correctly via file:// (no CORS fetch for external JS).
const singleFile = !!process.env.VITE_SINGLE_FILE

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_URL ?? '/',
  server: {
    // Listen on all interfaces so the Dev Container port-forward reaches the host.
    host: true,
    port: 5173,
  },
  build: {
    // OSMD is a single large bundle (~1.2 MB) with no internal split points.
    // Raise the limit to avoid a spurious warning we cannot address.
    chunkSizeWarningLimit: 1500,
    ...(singleFile && {
      rollupOptions: {
        output: { codeSplitting: false },
      },
    }),
  },
})
