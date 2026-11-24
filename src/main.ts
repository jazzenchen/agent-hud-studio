import { GeekLoftApp } from './core/App';
import { detectInitialLocale, TRANSLATIONS } from './ui/i18n';

const canvas = document.getElementById('webgl-canvas') as HTMLCanvasElement | null;
if (!canvas) {
  throw new Error('Missing #webgl-canvas element');
}

const app = new GeekLoftApp(canvas);
app.init().catch((err) => {
  console.error('[AStudio] Failed to initialize 3D loft:', err);
  const status = document.getElementById('loading-status');
  if (status) {
    const t = TRANSLATIONS[detectInitialLocale()];
    status.textContent = t.loading.failed(err instanceof Error ? err.message : String(err));
  }
});
