import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('element-plus/es/components/')) {
              const component = id.split('element-plus/es/components/')[1]?.split('/')[0]
              return component ? `element-plus-${component}` : 'element-plus-components'
            }
            if (id.includes('element-plus/es/')) return 'element-plus-core'
            if (id.includes('@element-plus/icons-vue')) return 'element-plus-icons'
            if (id.includes('@popperjs')) return 'popper'
            if (id.includes('@lucide')) return 'icons'
            if (id.includes('vue') || id.includes('@vue')) return 'vue-vendor'
            return 'vendor'
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
