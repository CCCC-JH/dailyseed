/**
 * 身份回归：直接在 Node 里跑**真实的** `src/api/client.ts` / `session.ts` / `lib/keepHint.ts`。
 *
 * 为什么值得这么做（而不是写一份"移植版"实现来测）：
 *   这个页面最容易坏的地方（首屏注册、401 自愈、清缓存被 Cookie 认回、同步码规范化）
 *   全在浏览器里，而**无头浏览器在这台机器上起不来**（Chrome/Edge 的 crashpad 与 Mojo
 *   命名管道都被拒）。那就把边界挪一下：这几个模块只依赖 `window.localStorage /
 *   sessionStorage / crypto / fetch`，把四样东西用假的塞进 `vm` 就能跑真源码。
 *   ——移植版的问题在于它会**验一个过时的模型**：源码改了、移植版没改，测试照样绿。
 *
 * 依赖：`typescript`（vite 模板自带的 devDependency，用来把 TS 转成 CJS）。
 * 用法：`node qa-verify-bootstrap.mjs`（无需浏览器、无需后端、无需 npm install 额外包）
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { webcrypto } from 'node:crypto'
import ts from 'typescript'

// 把 `../lib/keepHint` 这种相对路径规整成 `lib/keepHint`（相对于 src/）
function resolveName(name, from) {
  const parts = from ? from.split('/').slice(0, -1) : []
  for (const part of name.split('/')) {
    if (part === '' || part === '.') continue
    if (part === '..') parts.pop()
    else parts.push(part)
  }
  return parts.join('/')
}

function harness(fetcher, initial = {}) {
  const values = new Map(Object.entries(initial))
  const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) }
  const modules = new Map()
  function load(rawName, from = '') {
    const name = resolveName(rawName, from)
    if (modules.has(name)) return modules.get(name)
    const output = ts.transpileModule(readFileSync(new URL(`./src/${name}.ts`, import.meta.url), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText
    const exports = {}
    modules.set(name, exports)
    vm.runInNewContext(output, {
      exports,
      require: path => load(path, name),
      window: { localStorage: storage, sessionStorage: storage },
      crypto: webcrypto,
      fetch: fetcher,
      console,
    })
    return exports
  }
  return { client: load('api/client'), session: load('api/session'), hint: load('lib/keepHint'), values }
}
const response = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })
const key = 'dailyseed.deviceId'
let passed = 0
let guards = 0
async function check(name, test) { await test(); console.log(`PASS ${name}`); passed++ }

// ==================== 一、身份场景（跑真源码） ====================

await check('全新设备的并发注册只创建一次', async () => {
  let created = 0
  const h = harness(async (path, init) => {
    assert.equal(path, '/api/session')
    const { deviceId } = JSON.parse(init.body)
    if (!deviceId) return response(400)
    created++
    return response(200, { created: true, syncCode: 'TEST-CODE' })
  })
  const ids = await Promise.all([h.client.bootstrapDevice(), h.client.bootstrapDevice()])
  assert.equal(ids[0], ids[1]); assert.equal(created, 1)
  assert.equal(h.values.get(key), ids[0]); assert.equal(h.session.getSyncCode(), 'TEST-CODE')
})

for (const outage of ['network', 'server']) {
  await check(`${outage} 故障不更换已有身份，恢复后可重试`, async () => {
    let failing = true; let calls = 0
    const h = harness(async (_path, init) => {
      calls++; assert.equal(JSON.parse(init.body).deviceId, 'dev-original')
      if (failing) { if (outage === 'network') throw new TypeError('offline'); return response(503) }
      return response(200, { created: false })
    }, { [key]: 'dev-original' })
    await assert.rejects(h.client.bootstrapDevice()); assert.equal(calls, 1)
    assert.equal(h.values.get(key), 'dev-original')
    failing = false
    assert.equal(await h.client.bootstrapDevice(), 'dev-original'); assert.equal(calls, 2)
  })
}
await check('清掉本地身份后由 Cookie 恢复，保存服务端设备 ID', async () => {
  const h = harness(async (_path, init) => {
    assert.equal(JSON.parse(init.body).deviceId, null)
    assert.equal(init.headers['X-Device-Id'], undefined)
    return response(200, { deviceId: 'srv-recovered', recovered: true, created: false })
  })
  assert.equal(await h.client.bootstrapDevice(), 'srv-recovered')
  assert.equal(h.values.get(key), 'srv-recovered'); assert.equal(h.session.takeJustRecovered(), true)
  // 「刚被 Cookie 认回来」这个事实只说一次：读过就没了（否则每次刷新都弹一遍）
  assert.equal(h.session.takeJustRecovered(), false)
})
await check('401 先修身份再重试，重试用的是修好的 ID（串行）', async () => {
  let created = 0
  const seen = []
  const h = harness(async (path, init) => {
    if (path === '/api/session') { created++; return response(200, { created: true, deviceId: 'dev-fresh' }) }
    seen.push(init.headers['X-Device-Id'])
    return init.headers['X-Device-Id'] === 'dev-stale' ? response(401) : response(200, { cardId: 25 })
  }, { [key]: 'dev-stale' })
  const today = await h.client.fetchToday()
  assert.equal(today.cardId, 25)
  assert.equal(created, 1)                       // 只注册一次
  assert.deepEqual(seen, ['dev-stale', 'dev-fresh'])  // 第二次带的是修好的 ID
  assert.equal(h.values.get(key), 'dev-fresh')
})
await check('并发 401 只修复一次，两个请求都使用修复后的 ID', async () => {
  let created = 0
  const h = harness(async (path, init) => {
    if (path === '/api/session') {
      if (!JSON.parse(init.body).deviceId) return response(400)
      created++; return response(200, { created: true })
    }
    return init.headers['X-Device-Id'] === 'dev-stale' ? response(401) : response(200, { cardId: 25 })
  }, { [key]: 'dev-stale' })
  const values = await Promise.all([h.client.fetchToday(), h.client.fetchToday()])
  assert.equal(created, 1); assert.ok(values.every(value => value.cardId === 25))
})
await check('身份修复失败不会永久缓存失败结果', async () => {
  let down = true
  const h = harness(async (_path, init) => {
    if (down) throw new TypeError('offline')
    return JSON.parse(init.body).deviceId ? response(200, { created: true }) : response(400)
  })
  await assert.rejects(h.client.repairDevice('bad'))
  down = false
  assert.ok((await h.client.repairDevice('bad')).startsWith('dev-'))
})
await check('同步码容错与空响应保留使用实际 session.ts', async () => {
  const h = harness(async () => response(200))
  for (const input of ['k7m2p9qx', 'K7M2 P9QX', 'K7M2-P9QX', 'K7M2　P9QX']) assert.equal(h.session.canonicalSyncCode(input), 'K7M2-P9QX')
  assert.equal(h.session.canonicalSyncCode('123'), '')
  h.session.saveSession({ syncCode: 'TEST-CODE' }); h.session.saveSession({ syncCode: null })
  assert.equal(h.session.getSyncCode(), 'TEST-CODE')
})
await check('同步码提示：第一次留住才提，提过就不再提，「不再提醒」是永久关闭', async () => {
  const h = harness(async () => response(200))
  // ⚠️ 只能逐字段比：`noteKeep` 返回的对象是在 vm 的**另一个 realm** 里造的，
  //    原型不是这个文件的 Object.prototype，`deepStrictEqual` 会以
  //    "same structure but not reference-equal" 拒掉它（实测踩到）。
  const first = h.hint.noteKeep(5)
  assert.equal(first.firstKeep, true); assert.equal(first.cardId, 5)
  const second = h.hint.noteKeep(6)
  assert.equal(second.firstKeep, false); assert.equal(second.cardId, 6)
  assert.equal(h.session.shouldShowSyncHint(), true)
  h.session.markSyncHintShown()
  assert.equal(h.session.shouldShowSyncHint(), false)
  const other = harness(async () => response(200))
  other.session.turnOffSyncHint()
  assert.equal(other.session.shouldShowSyncHint(), false)
})

// ==================== 二、源码守卫：有些"形状"只能靠读源码来守 ====================
//
// 这几条守的不是行为而是**结构**：它们靠假 fetch 测不出来（改了照样能跑通），
// 但只要有人"顺手改回旧形状"，症状会是丢身份、多建号这类用户级事故。
// 所以判据直接写在真实源码文本上。

const src = name => readFileSync(new URL(`./src/${name}`, import.meta.url), 'utf8')
/** 取某个顶层函数的函数体（到下一个顶层 export 前） */
function bodyOf(source, fnName) {
  const start = source.indexOf(`function ${fnName}`)
  if (start < 0) return ''
  const next = source.indexOf('\nexport ', start + 1)
  return source.slice(start, next < 0 ? source.length : next)
}
const clientSrc = src('api/client.ts')
const sessionSrc = src('api/session.ts')
const FILES = { client: clientSrc, session: sessionSrc, main: src('main.tsx') }

const shapeChecks = [
  {
    name: '源码守卫 1：`session.ts` 仍然导出 readDeviceId / canonicalSyncCode / saveSession',
    why: '这三个是"清缓存还能被认回"和"码不丢"的接口，缺一个整套退路就散了',
    test: f => /export function readDeviceId\b/.test(f.session)
      && /export function canonicalSyncCode\b/.test(f.session)
      && /export function saveSession\b/.test(f.session),
    // 人造旧形状：只有 ensureDeviceId（会生成 ID），没有 readDeviceId
    counter: 'export function ensureDeviceId() {}\nexport function saveSession() {}\n',
  },
  {
    name: '源码守卫 2：`restoreSession` 不许退回会自作主张重注册的 `request()`',
    why: '恢复的前提是"这台设备还没被认识"，走 request() 会在 401 时先把它注册掉 → 恢复恒 409',
    test: f => bodyOf(f.client, 'restoreSession').includes("fetch('/api/session/restore'")
      && !bodyOf(f.client, 'restoreSession').includes('request('),
    counter: "export async function restoreSession(a) { return request('/api/session/restore') }\n",
  },
  {
    name: '源码守卫 3：`bootstrapDevice` 用 readDeviceId（不生成），不用 ensureDeviceId',
    why: '本地没有 ID 时**必须什么都不发**，一发新 ID 后端就当成新用户，Cookie 退路永远走不到',
    test: f => bodyOf(f.client, 'bootstrapDevice').includes('readDeviceId(')
      && !bodyOf(f.client, 'bootstrapDevice').includes('ensureDeviceId('),
    counter: 'export function bootstrapDevice() { const id = ensureDeviceId(); return id }\n',
  },
  {
    name: '源码守卫 4：`main.tsx` 不套 StrictMode',
    why: '注册设备的 effect 只能跑一次，StrictMode 会跑两遍、多建一个用户',
    // ⚠️ 判据要盯**JSX 用法**，不能是裸的 `StrictMode`：`main.tsx` 里有一句注释
    //    "刻意不用 StrictMode"，宽匹配会把它判成违规（实测这个假阳性把我自己抓了一次）。
    test: f => !/<(?:React\.)?StrictMode\b/.test(f.main),
    counter: '<StrictMode><App /></StrictMode>\n',
  },
]

for (const c of shapeChecks) {
  assert.ok(c.test(FILES), `${c.name} —— ${c.why}`)
  console.log(`PASS ${c.name}`)
  guards++
}

// ★ 守卫本身要先验：拿上面那段**人造的旧形状**喂进同一套判据，必须被判为不合格。
//   只会通过的守卫等于没有守卫 —— 这一条是照 `tools/verify_redlines.py --selftest` 的规矩来的。
for (const c of shapeChecks) {
  const fake = { client: c.counter, session: c.counter, main: c.counter }
  assert.ok(!c.test(fake), `${c.name} 在人造旧形状上居然也通过 —— 这是一道永远为真的空守卫`)
}
console.log(`PASS 反例自检：${guards} 道守卫在"人造旧形状"上都确实会报（它们不是永远为真）`)

console.log(`${passed} 个场景 + ${guards} 道源码守卫 + 1 条反例自检全过（跑的是 src/ 里的真源码）`)
