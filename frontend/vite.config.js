import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, strictPort: true },
  build: { rollupOptions: { output: { manualChunks: { vendor: ['vue', 'vue-router', 'pinia', 'axios'] } } } },
  test: { environment: 'node', exclude: ['e2e/**', 'node_modules/**'] },
})
