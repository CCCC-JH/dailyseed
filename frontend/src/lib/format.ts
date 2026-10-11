/** 展示用的纯格式化。全部不做时区换算——服务端已经按用户时区给了本地日期。 */

/** 2026-10-09 → 10月9日 */
export function formatMonthDay(iso: string): string {
  const [, m, d] = iso.split('-')
  if (!m || !d) return iso
  return `${Number(m)}月${Number(d)}日`
}

/** 把 yyyy-MM-dd 解析成本地当天中午，避免时区把日期挪走一天 */
function parseLocalDate(iso: string): Date | null {
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d, 12, 0, 0)
}

/** 「今天」/「昨天」/「10月7日」——补留列表用 */
export function formatRelativeDay(iso: string, todayIso: string): string {
  const a = parseLocalDate(iso)
  const b = parseLocalDate(todayIso)
  if (!a || !b) return formatMonthDay(iso)
  const diff = Math.round((b.getTime() - a.getTime()) / 86_400_000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff === 2) return '前天'
  return formatMonthDay(iso)
}

/** ISO 本地时间串 → 10月9日 */
export function formatDateTimeStamp(iso?: string): string {
  if (!iso) return ''
  const date = iso.slice(0, 10)
  return date ? formatMonthDay(date) : ''
}

/** 今天的 yyyy-MM-dd（按设备本地时区，只用于文案对照） */
export function todayIso(): string {
  const now = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`
}

/** 难度不是分数，是"这条有多消耗"——只做极简表述，不显示数字 */
export function difficultyLabel(difficulty: number): string {
  if (difficulty <= 0) return '零消耗'
  if (difficulty === 1) return '很轻'
  if (difficulty === 2) return '中等'
  return '偏重'
}

export function typeLabel(type: string): string {
  if (type === 'HABIT') return '习惯'
  if (type === 'EXPLORE') return '探索'
  if (type === 'INDULGE') return '放纵'
  return type
}

/** 「已经留住 7 次」这类仅在花园内部出现的计数表述 */
export function keptCountLabel(n: number): string {
  return `留住 ${n} 次`
}

/** 复制到剪贴板：优先现代 API，失败退回 execCommand（http/旧内核下 Clipboard API 可能被拒） */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* 继续往下退 */
  }
  try {
    const el = document.createElement('textarea')
    el.value = text
    el.setAttribute('readonly', '')
    el.style.position = 'fixed'
    el.style.top = '-1000px'
    document.body.appendChild(el)
    el.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(el)
    return ok
  } catch {
    return false
  }
}

/** 极轻的触感反馈（支持的设备才有）。不是庆祝，只是"收到了" */
export function tapFeedback(): void {
  try {
    if ('vibrate' in navigator) navigator.vibrate(8)
  } catch {
    /* ignore */
  }
}

/**
 * 这台设备能不能分享**文件**（不只是文字）。
 *
 * iOS Safari 与部分桌面浏览器对 `navigator.share({files})` 支持不一，所以每次都要问一遍。
 * 问不能用 try/catch 代替——`canShare` 是同步的、不会弹任何界面，用它先判定最干净。
 */
/**
 * 存一个文件到用户的下载里（日历提醒 .ics 的退路用）。
 *
 * 为什么不能写成一个 `<a href="/api/reminder.ics">`：身份只靠 `X-Device-Id` 请求头，
 * 浏览器点链接时带不上它，后端会以 400「缺少请求头」拒掉。
 * 所以必须先把正文 fetch 回来，再变成本地 Blob 存下去。
 */
export function downloadBlob(filename: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
}

/**
 * 这台设备能不能分享**文件**（不只是文字）。
 *
 * iOS Safari 与部分桌面浏览器对 `navigator.share({files})` 支持不一，所以每次都要问一遍。
 * 不能拿 try/catch 代替——`canShare` 是同步的、不弹任何界面，用它先判定最干净。
 */
export function canShareFiles(file: File): boolean {
  const nav = navigator as Navigator & { canShare?: (data: ShareData) => boolean }
  try {
    return typeof nav.share === 'function' && nav.canShare?.({ files: [file] }) === true
  } catch {
    return false
  }
}

/**
 * 把一段文本当文件**分享出去**（能分享时）或**存下来**（不能分享时），返回走了哪条路。
 *
 * 为什么两件事要写在一起：`.ics` 在 iOS Safari 上"下载"经常只是把文件丢给某个 App，
 * 用户不知道该点哪个；而系统分享面板里"存储到文件 / 用日历打开"是现成的两条路。
 * 所以**先试分享、不行再退下载**——顺序不能反（下载会立刻触发，用户就没机会看到分享面板）。
 */
export async function shareOrDownloadFile(
  filename: string,
  text: string,
  type: string,
  title: string,
): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const file = new File([new Blob([text], { type })], filename, { type })
  if (canShareFiles(file)) {
    try {
      await (navigator as Navigator).share({ files: [file], title })
      return 'shared'
    } catch {
      // 用户在分享面板里按了取消——不是失败，也不该再顺手给他下载一遍
      return 'cancelled'
    }
  }
  downloadBlob(filename, text, type)
  return 'downloaded'
}
