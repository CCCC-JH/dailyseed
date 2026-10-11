import { createRoot } from 'react-dom/client'
import { App } from './App'
import './styles/base.css'
import './styles/components.css'

const container = document.getElementById('root')
if (!container) throw new Error('#root 不存在')

// 刻意不用 StrictMode：它会在开发模式下把 effect 跑两遍，
// 而这里的 effect 会去 POST /api/session（注册设备）——多注册一次就多一个用户。
createRoot(container).render(<App />)

// PWA：只在生产构建里注册 Service Worker。
// 开发模式不注册是故意的——SW 会缓存 / 让热更新失效，调试时会以为代码没生效。
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js')
  })
}
