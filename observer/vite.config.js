import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['three'],
  },
  server: {
    host: process.env.OBSERVER_HOST || '127.0.0.1',
    port: 3000,
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'credentialless',
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ollama': {
        target: process.env.OLLAMA_PROXY_URL || process.env.VITE_OLLAMA_TARGET || 'http://localhost:11434',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ollama/, ''),
      },
    },
  },
  optimizeDeps: {
    exclude: ['three', '@met4citizen/talkinghead', '@met4citizen/talkinghead/modules/talkinghead.mjs'],
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('@met4citizen/talkinghead')) return 'avatar-talkinghead';
          if (id.includes('@react-three') || id.includes('@pixiv/three-vrm')) return 'avatar-react-three';
          if (id.includes('/three/') || id.includes('\\three\\')) return 'three-core';
          if (id.includes('/react/') || id.includes('\\react\\') || id.includes('/react-dom/') || id.includes('\\react-dom\\')) {
            return 'react-vendor';
          }
          return 'vendor';
        },
      },
    },
  },
});
