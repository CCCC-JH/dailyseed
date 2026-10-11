import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 后端没有 CORS 配置，所以开发期绝不直连 8080：
// 前端一律请求相对路径 /api/...，由这个代理转发。
// 这样生产环境（反向代理 / 同域部署）代码一行都不用改。
//
// ⚠️ 这个文件刻意是 .mjs 而不是 .ts：Vite 加载 .ts 配置时要起一个 esbuild 子进程去编译它，
//    在受限沙箱里那会以 spawn EPERM 失败。用 .mjs 就把这一步省掉了。
//    它仍然会被 typecheck（见 tsconfig.node.json 的 allowJs + checkJs）。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  // ⚠️ preview **不会**继承 server.proxy：少了这一段，`npm run preview` 上
  //    dist 里的 /api 请求会直接 404（前端会以为是后端挂了）。这里必须再写一遍。
  preview: {
    // 显式绑 host：preview 默认只监听 ::1（IPv6），于是 `http://127.0.0.1:4173`
    // 会连不上（只有 localhost 恰好解析到 ::1 才行），很容易被误判成"服务挂了"。
    host: true,
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
  },
})
