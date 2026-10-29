import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development, /api calls are forwarded to the FastAPI server on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1000 },
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_BACKEND_URL || 'http://localhost:8000' },
  },
})
