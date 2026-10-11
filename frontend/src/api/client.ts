/**
 * 唯一的网络层：全部走相对路径 `/api/...`，由 vite 代理（开发）或同域反代（生产）转发。
 *
 * 身份只靠一个请求头 `X-Device-Id` —— 后端不信任前端传的 userId（见 TodayController 注释）。
 * 401 意味着后端不认识这个设备（比如换了库）：这里会**清掉本地 deviceId、重建身份、自己重试一次**，
 * 而不是把一个未注册的 ID 反复丢给后端（那会永远卡在加载屏）。自愈只做一次，失败就抛出去让上层显示错误。
 */
import {
  ensureDeviceId,
  markJustRecovered,
  newDeviceId,
  readDeviceId,
  saveDeviceId,
  saveSession,
  saveSyncCode,
} from './session'
import type { ExploredRecord, Garden, HistoryItem, Plant, ReminderInfo, SessionInfo, Today } from './types'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const KEY_DEVICE = 'dailyseed.deviceId'

/**
 * 设备注册是**全局单飞**的：同一时刻只可能有一个 POST /api/session 在飞。
 *
 * 为什么必须这样：`/api/today` 和 `/api/history` 是并行发的，如果各自拿自己的
 * deviceId 去建身份，会同时建出**两个**用户、后写进 localStorage 的那个覆盖先写的，
 * 于是另一个 ID 从没注册过、下一次请求就 401。
 */
let booting: Promise<string> | null = null

/**
 * 建好（或复用）这个设备的匿名身份，返回**已经注册过**的 deviceId。
 *
 * 自愈路径全靠它：客户端一旦发现设备不被认识，就把那个坏 ID 记下来交给 heal()，
 * 由这里重建身份，而不是继续拿一个未注册的 ID 反复重试。
 *
 * **还有一条退路**：localStorage 被清掉之后，`ensureDeviceId()` 拿不出任何 ID，
 * 这时后端会用一个 HttpOnly Cookie 认出人，并在响应里补发一个 deviceId——
 * 我们必须把它存下来，否则下一次刷新又回到"没有身份"的状态。见 `types.ts` 的 `SessionInfo.deviceId`。
 */
export function bootstrapDevice(): Promise<string> {
  if (!booting) {
    // readDeviceId（不生成）——没有本地身份时就把这条路让给 Cookie 退路
    const id = readDeviceId() ?? ''
    booting = createSession(id)
      .then((info) => {
        saveSession(info) // ★ 拿到就立刻存，不等毕业、不等用户想起来
        // 服务端补发了 ID（= 它靠 Cookie 认出了我们）：存下来，下次就走正路
        if (info.deviceId) {
          saveDeviceId(info.deviceId)
          if (info.recovered) markJustRecovered()
          return info.deviceId
        }
        return id
      })
      .catch(async (error: unknown) => {
        // 网络或服务器故障不能被解释为身份失效，否则短暂离线会丢掉原账号。
        if (!(error instanceof ApiError) || !((error.status === 400 && !id) || error.status === 401)) throw error
        // 这个 ID 没能建上（空值、被后端拒、或库被重置）：换一个干净的再试一次
        const fresh = newDeviceId()
        const info = await createSession(fresh)
        saveSession(info)
        saveDeviceId(info.deviceId ?? fresh)
        return info.deviceId ?? fresh
      })
      .catch((error: unknown) => {
        booting = null // 不缓存被拒绝的 Promise，让「再试一次」可以恢复
        throw error
      })
  }
  return booting
}

/**
 * 设备不被认识时调这个：把**坏掉的那个 ID** 记下来并修好它，返回修好后的 deviceId。
 *
 * 关键点：`repairing` 是**同步**写进去的（在第一个 await 之前），而且按坏 ID 去重。
 * 首屏的 `/api/today` 与 `/api/history` 是并行发的、在同一 tick 里都会撞上同一个 401；
 * 如果等到 await 之后才登记，两个请求就都会各自注册一次 —— 建出两个用户。
 * 同步登记之后，第二个请求拿到的是同一张"正在修"的票，只 await、不重复注册。
 */
const repairing = new Map<string, Promise<string>>()

export function repairDevice(badId: string): Promise<string> {
  const existing = repairing.get(badId)
  if (existing) return existing

  const p = (async () => {
    try {
      window.localStorage.removeItem(KEY_DEVICE)
    } catch {
      /* ignore */
    }
    booting = null
    return await bootstrapDevice() // 拿到一个全新的、已经注册过的 ID
  })()

  repairing.set(badId, p)
  void p.catch(() => repairing.delete(badId))
  return p
}

async function request<T>(path: string, init?: RequestInit, as: 'json' | 'text' = 'json'): Promise<T> {
  // 每次发送都记下**这次真正发出去的** deviceId。
  // 这一点很关键：401 之后再去读 localStorage 可能已经被并行的另一个请求修好了，
  // 那样会把一个刚建好的新 ID 当成坏的、再修一次（= 多建一个用户）。
  let sentId = ''

  const send = () => {
    sentId = ensureDeviceId()
    return fetch(path, {
      ...init,
      headers: {
        'X-Device-Id': sentId,
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init?.headers ?? {}),
      },
    })
  }

  let res = await send()

  if (res.status === 401) {
    // 设备不被认识：修好身份后**自己重试一次**。
    // 只在这一次重试上做自愈——失败就交给上层显示错误，绝不无限重试（那会永远卡在加载屏）。
    await repairDevice(sentId)
    res = await send()
    if (res.status === 401) throw new ApiError(401, '这个设备还没注册上，请重试')
  }

  if (!res.ok) {
    // 后端用 ResponseStatusException，错误体是 Spring 默认结构
    let detail = ''
    try {
      const body = (await res.json()) as { message?: string; error?: string }
      detail = body.message || body.error || ''
    } catch {
      /* 非 JSON 就用状态码兜底 */
    }
    throw new ApiError(res.status, detail || `请求失败（${res.status}）`)
  }

  if (res.status === 204) return undefined as T

  // 日历文件不是 JSON：解析成对象会把正文丢掉，所以让它原样出来
  if (as === 'text') return (await res.text()) as T
  return (await res.json()) as T
}

/** 注册设备，拿到同步码。**只应由 bootstrapDevice 调用**（它负责单飞与落盘） */
export function createSession(deviceId: string): Promise<SessionInfo> {
  // deviceId 为空 = "这台设备没有任何本地身份"（localStorage 被清了）。
  // 这时**必须连请求头都不发**：发一个空的或新的 ID，后端只会当成新用户建号，
  // 那条"靠 HttpOnly Cookie 认人"的退路就永远走不到了。
  //
  // 注意这条路不能走 request()——它会在发之前调 ensureDeviceId() 现场生成一个 ID，
  // 正好是我们最不想要的行为。
  return fetch('/api/session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(deviceId ? { 'X-Device-Id': deviceId } : {}),
    },
    body: JSON.stringify({ deviceId: deviceId || null }),
  }).then(async (res) => {
    if (!res.ok) {
      let detail = ''
      try {
        const body = (await res.json()) as { message?: string; error?: string }
        detail = body.message || body.error || ''
      } catch {
        /* 非 JSON 就用状态码兜底 */
      }
      throw new ApiError(res.status, detail || `注册失败（${res.status}）`)
    }
    return (await res.json()) as SessionInfo
  })
}

/** 今天的一粒种子（懒生成 + 幂等：同一天反复调返回同一张）。**未揭晓时前端应显示卡背** */
export function fetchToday(): Promise<Today> {
  return request<Today>('/api/today')
}

/**
 * 抽：第一次 = 揭晓当天那张；之后每次 = 换掉当天那张（重抽）。
 *
 * 配额由服务端判定，用完/已留住都会 409——前端据 `canRedraw` 决定要不要画入口。
 */
export function drawToday(): Promise<Today> {
  return request<Today>('/api/today/draw', { method: 'POST' })
}

/** 唯一的核心交互。幂等：重复点也只是原样返回，keptCount 不会涨 */
export function keepToday(note?: string): Promise<Today> {
  return request<Today>('/api/today/keep', {
    method: 'POST',
    body: JSON.stringify({ note: note ?? null }),
  })
}

/** 今天想放纵（门槛在服务端判定，不满足时入口根本不出现） */
export function indulgeToday(): Promise<Today> {
  return request<Today>('/api/today/indulge', { method: 'POST' })
}

/** 最近 3 天可补留的卡 */
export function fetchHistory(days = 3): Promise<HistoryItem[]> {
  return request<HistoryItem[]>(`/api/history?days=${days}`)
}

/** 补留：只有 3 天内、没留过、且不是放纵卡的才会成功（否则 409） */
export function keepPast(assignmentId: number): Promise<HistoryItem> {
  return request<HistoryItem>(`/api/history/${assignmentId}/keep`, { method: 'POST' })
}

/** 我的花园：窗台上还有几盆 + 已内化清单 */
export function fetchGarden(): Promise<Garden> {
  return request<Garden>('/api/garden')
}

/** 宣布毕业。幂等：重复调用也 200，graduatedAt 不会被覆盖 */
export function graduate(cardId: number): Promise<Plant> {
  return request<Plant>(`/api/garden/${cardId}/graduate`, { method: 'POST' })
}

// ==================== 模块 C：走过的 / 恢复 / 提醒 ====================

/** 走过的全部探索卡（新的在前）。只读：这一页没有"做了什么"要提交 */
export function fetchExplored(): Promise<ExploredRecord> {
  return request<ExploredRecord>('/api/explored')
}

/**
 * 用同步码找回数据（换手机 / 清了缓存）。
 *
 * **这一步不能走 `request()`**：它会在 401 时自作主张地把设备重新注册一遍，
 * 而恢复的前提恰恰是"这台设备还没被认识"。所以这里直接 fetch，
 * 并且成功后要把**换发的新码**立刻存下来（旧码已经作废了）。
 */
export async function restoreSession(syncCode: string, deviceId: string): Promise<string> {
  const res = await fetch('/api/session/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ syncCode, deviceId }),
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { message?: string; error?: string }
      detail = body.message || body.error || ''
    } catch {
      /* 非 JSON 就用兜底文案 */
    }
    throw new ApiError(res.status, detail || `恢复失败（${res.status}）`)
  }
  const info = (await res.json()) as { syncCode: string }
  saveSyncCode(info.syncCode)
  return info.syncCode
}

/** 存下用户自设的提醒时间（只收 HH:mm，格式不对后端会 400） */
export function setReminder(time: string): Promise<ReminderInfo> {
  return request<ReminderInfo>('/api/session/reminder', {
    method: 'POST',
    body: JSON.stringify({ time }),
  })
}

/**
 * 取日历提醒文件。
 *
 * ⚠️ **必须走这里，不能在页面上写 `<a href="/api/reminder.ics">`**：
 * 身份只靠 `X-Device-Id` 请求头，点链接时浏览器带不上它，后端会以
 * 400「缺少请求头」拒掉——这个坑踩过一次。
 */
export function fetchReminderIcs(): Promise<string> {
  return request<string>('/api/reminder.ics', undefined, 'text')
}
