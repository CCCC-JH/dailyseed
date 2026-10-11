/* eslint-env serviceworker */
/**
 * 一个手写的最小 Service Worker —— 不到 60 行，比引 workbox 更好懂，也少一堆依赖。
 *
 * 策略刻意简单：
 *   · 导航请求（打开页面）：network-first —— 先拿最新的，断网才回缓存。
 *     这样"每天打开看到今天那一粒"不会因为缓存而看到旧的骨架。
 *   · 静态资源（js/css/图标/字体）：cache-first —— 它们带内容哈希，不会过期。
 *   · /api/** ：**完全不碰**。卡片数据必须实时，缓存它等于让用户看到昨天的卡。
 */
const CACHE = 'dailyseed-shell-v2'
const PRECACHE = ['/', '/manifest.webmanifest', '/icons/icon-192.png']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('dailyseed-shell-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  // 接口一律走网络，缓存它会让"今天"变成假的
  if (url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((cache) => cache.put('/', copy))
          return res
        })
        .catch(() => caches.match('/').then((hit) => hit ?? Response.error())),
    )
    return
  }

  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) return hit
      return fetch(request).then((res) => {
        if (res.ok && (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/'))) {
          const copy = res.clone()
          caches.open(CACHE).then((cache) => cache.put(request, copy))
        }
        return res
      })
    }),
  )
})
