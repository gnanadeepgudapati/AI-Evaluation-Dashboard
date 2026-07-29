import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/',
  build: {
    outDir: '../frontend',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/compare': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
      '/suites': 'http://localhost:8000',
      '/stream': 'http://localhost:8000',
      '/evaluate': 'http://localhost:8000',
      '/evaluations': 'http://localhost:8000',
    },
  },
})
