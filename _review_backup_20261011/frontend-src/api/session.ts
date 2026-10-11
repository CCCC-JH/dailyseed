/**
 * 身份：deviceId 是**唯一**能认出用户的东西（同步码只是它的备份）。
 *
 * 为什么同步码要「创建时立刻存 + 设置页常驻」：清缓存时 deviceId 和码**一起**消失，
 * 后端认不出你是谁 —— 补发物理上无法送达。所以能做的只有"趁他还不在乎时先塞给他一次"。
 */
import type { SessionInfo } from '../api/types'

const KEY_DEVICE = 'dailyseed.deviceId'
const KEY_SYNC = 'dailyseed.syncCode'
const KEY_HINT_DONE = 'dailyseed.syncHintDone'
const KEY_HINT_OFF = 'dailyseed.syncHintOff'
const KEY_RECOVERED = 'dailyseed.justRecovered'

/** localStorage 在隐私模式 / 沙箱里可能直接抛异常，全部包一层，绝不让它把应用打崩 */
function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* 存不下就算了，不要弹错给用户 */
  }
}

export function getDeviceId(): string | null {
  return read(KEY_DEVICE)
}

/**
 * 读**已存在**的 deviceId，**绝不生成**。
 *
 * 和 `ensureDeviceId()` 的区别正是"清缓存还能不能找回"的关键：
 * 被清掉之后如果没有别的凭据，我们就该**什么都不发**——
 * 一发一个新 ID，后端只能当成新用户，那条 Cookie 退路就永远走不到。
 */
export function readDeviceId(): string | null {
  return read(KEY_DEVICE)
}

/** 存下一个 deviceId（服务端补发的那种，见 SessionInfo.deviceId） */
export function saveDeviceId(id: string): void {
  write(KEY_DEVICE, id)
}

/**
 * 这一次打开是不是"靠浏览器的 Cookie 被认出来的"（= 本地身份丢过一次）。
 *
 * 跨**页面重载**传递一个一次性事实，所以只能落盘：`App.tsx` 读一次、读完就清，
 * 免得每次刷新都弹一遍。用 sessionStorage 而不是 localStorage 正是为了这个——
 * 换个标签页、或者关掉浏览器再打开，就不该再提这件事了。
 */
export function markJustRecovered(): void {
  try {
    window.sessionStorage.setItem(KEY_RECOVERED, '1')
  } catch {
    /* 存不下就算了，少一句提示而已 */
  }
}

/** 读并**立刻清掉**这个标记：它只说一次 */
export function takeJustRecovered(): boolean {
  try {
    const yes = window.sessionStorage.getItem(KEY_RECOVERED) === '1'
    if (yes) window.sessionStorage.removeItem(KEY_RECOVERED)
    return yes
  } catch {
    return false
  }
}

/** 生成一个本地匿名设备 ID（不要求密码学强度，只要够唯一）。
 *  导出是为了让 client.ts 在「这个 ID 没建上」时能换一个干净的重试。 */
export function newDeviceId(): string {
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36)
  return 'dev-' + rand
}

/** 拿到（必要时生成）设备 ID。首次进入时这个 ID 会被 POST /api/session 注册 */
export function ensureDeviceId(): string {
  const existing = read(KEY_DEVICE)
  if (existing) return existing
  const fresh = newDeviceId()
  write(KEY_DEVICE, fresh)
  return fresh
}

export function getSyncCode(): string | null {
  return read(KEY_SYNC)
}

/**
 * 存下这次会话拿到的同步码。
 *
 * ⚠️ **`syncCode` 为 null 时绝不能写**：那表示"这个设备已经用过"，后端不再返回码。
 * 恢复流程就是踩在这条上的——`POST /api/session/restore` 换发新码并落盘，
 * 紧接着恢复成功触发的 `location.reload()` 会再调一次 `POST /api/session`，
 * 那次返回的 `syncCode` 是 null；如果照写不误，**刚换到手的码会在同一次刷新里被抹掉**，
 * 设置页从此显示"还没拿到"。
 */
export function saveSession(info: SessionInfo): void {
  if (info.syncCode) write(KEY_SYNC, info.syncCode)
}

/** 换发新码之后覆盖本地那一份。**恢复成功后立刻调**——旧码在那时已经作废了 */
export function saveSyncCode(code: string): void {
  write(KEY_SYNC, code)
}

/**
 * 把用户抄下来的同步码整理成**落库时的规范形态** `K7M2-P9QX`。
 *
 * 两种写法都要认（小写、少打或漏掉连字符），因为他是从截图或纸上抄回来的。
 * 但只做"整理"不做"猜"：有效字符不是正好 8 个就返回空串，交给服务端去报"位数不对"。
 *
 * ⚠️ 连字符要**补回去**：服务端哈希的是带连字符的那一串原码。
 * 这一条同时在后端 `RestoreService.canonicalSyncCode` 里守着——两边都不能少。
 */
export function canonicalSyncCode(raw: string): string {
  const bare = bareSyncCode(raw)
  if (bare.length !== 8) return ''
  return `${bare.slice(0, 4)}-${bare.slice(4)}`
}

/** 去掉分隔符与空白、转大写，只剩字母数字本体（全角空格也要算空白） */
export function bareSyncCode(raw: string): string {
  let out = ''
  for (const ch of raw ?? '') {
    if (ch >= '0' && ch <= '9') out += ch
    else if (ch >= 'A' && ch <= 'Z') out += ch
    else if (ch >= 'a' && ch <= 'z') out += ch.toUpperCase()
  }
  return out
}

/**
 * 同步码提示策略：只在**第一次留着之后**提示一次（可永久关闭），毕业时不再提示
 */
export function shouldShowSyncHint(): boolean {
  return read(KEY_HINT_DONE) !== '1' && read(KEY_HINT_OFF) !== '1'
}

export function markSyncHintShown(): void {
  write(KEY_HINT_DONE, '1')
}

/** 「不再提醒」——永久关闭 */
export function turnOffSyncHint(): void {
  write(KEY_HINT_OFF, '1')
}
