import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/',
  build: {
    rolldownOptions: {
      input: {
        index: fileURLToPath(new URL('./index.html', import.meta.url)),
        // Local read-only data viewer (#43), served by FastAPI at /dev.
        dev: fileURLToPath(new URL('./dev.html', import.meta.url)),
      },
    },
  },
  server: {
    proxy: {
      // The dev API accepts only a local Host header, so the proxy must not
      // rewrite it (changeOrigin stays false: Host remains localhost:<vite port>).
      '/dev/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
})
