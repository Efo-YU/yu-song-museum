import { useEffect, useRef, useState } from 'react';
import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay';
import type { ScoreViewerSettings } from '../types/song';

interface Props {
  url: string;
  settings?: ScoreViewerSettings;
}

type Status = 'idle' | 'loading' | 'ready' | 'error';

export default function ScoreViewer({ url, settings }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<OpenSheetMusicDisplay | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !url) return;

    let cancelled = false;

    async function load() {
      setStatus('loading');
      try {
        if (!osmdRef.current) {
          osmdRef.current = new OpenSheetMusicDisplay(el!, {
            autoResize: true,
            drawingParameters: 'default',
          });
        }

        osmdRef.current.zoom = settings?.default_zoom ?? 1.0;
        await osmdRef.current.load(url);

        if (cancelled) return;

        osmdRef.current.render();
        setStatus('ready');
      } catch (err) {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : String(err));
          setStatus('error');
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [url, settings?.default_zoom]);

  return (
    <div className="score-viewer">
      {status === 'loading' && (
        <p className="score-status">Loading score…</p>
      )}
      {status === 'error' && (
        <p className="score-status score-status--error">
          Failed to load score: {errorMsg}
        </p>
      )}
      <div ref={containerRef} style={{ width: '100%' }} />
    </div>
  );
}
