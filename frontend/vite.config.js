import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 归一化部署 base：未设置时使用相对路径；'/' 保持根路径；'/dc' / 'dc/' 均归一为 '/dc/'；
// 绝对 URL base（CDN 部署）原样透传
function normalizeBase(raw) {
  if (!raw) return './'
  let b = String(raw).trim()
  if (!b) return './'
  if (b === '/') return '/'
  if (b.includes('://')) return b
  if (!b.startsWith('/')) b = '/' + b
  if (!b.endsWith('/')) b += '/'
  return b.replace(/\/{2,}/g, '/')
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const base = normalizeBase(env.VITE_BASE_PATH)
  const basePrefix = base.startsWith('/') && base !== '/' ? base.slice(0, -1) : ''

  return {
    base,
    plugins: [vue()],
    build: {
      chunkSizeWarningLimit: 1100,
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-vue': ['vue'],
            'vendor-ep': ['element-plus'],
            'vendor-misc': ['sortablejs', 'vuedraggable'],
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        // 跟随 base：根路径代理 /api，子路径代理 /dc/api 并剥掉前缀
        [`${basePrefix}/api`]: {
          target: 'http://127.0.0.1:8888',
          changeOrigin: true,
          ...(basePrefix ? { rewrite: (p) => p.slice(basePrefix.length) } : {}),
        },
      },
    },
  }
})
