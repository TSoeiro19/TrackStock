// Vite: "npm run build" gera frontend/dist (servido pelo backend Python);
// "npm run dev" serve o frontend em http://localhost:5173 com recarga automática e envia /api ao backend.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = 'http://localhost:8765';

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 1000 },   // app local: um só ficheiro JS é ok
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND,
        changeOrigin: true,
        // o backend só aceita pedidos com origem na própria app
        configure: (proxy) => proxy.on('proxyReq', (req) => req.setHeader('origin', BACKEND)),
      },
    },
  },
});
