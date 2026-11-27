import { createReadStream, existsSync, statSync } from 'node:fs';
import { basename, resolve } from 'node:path';
import { defineConfig, type Plugin } from 'vite';

// Personal material (photos, voice, avatar splats) lives in assets/personal/, which git ignores.
// It is never under public/, because public/ is copied into dist/ and deployed. The dev server
// alone answers /assets/avatars/<file> from assets/personal/splats/, so a splat placed there
// loads locally and can never reach a build.
function personalSplats(): Plugin {
  const dir = resolve(__dirname, 'assets/personal/splats');
  return {
    name: 'personal-splats',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/assets/avatars/', (req, res, next) => {
        const file = resolve(dir, basename(decodeURIComponent((req.url ?? '').split('?')[0])));
        if (!existsSync(file) || !statSync(file).isFile()) return next();
        res.setHeader('Content-Type', 'application/octet-stream');
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [personalSplats()],
  optimizeDeps: {
    exclude: ['@sparkjsdev/spark'],
  },
  server: {
    port: 5173,
    open: false,
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
