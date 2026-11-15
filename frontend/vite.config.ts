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
      // xfwd adds X-Forwarded-For with the address of the client that reached
      // Vite; uvicorn trusts it from 127.0.0.1 by default, so the loopback check
      // sees that client rather than the proxy itself.
      '/dev/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
        xfwd: true,
      },
    },
  },
})
