/**
 * 本地小状态：只为了"该不该弹同步码提示"和"哪一盆刚落地"这两件事。
 * 它不是业务状态——业务状态全在服务端，前端**不缓存**卡片数据。
 */
const KEY_KEPT_ONCE = 'dailyseed.keptOnce'

export interface KeepHint {
  /** 这是这台设备上第一次留住 */
  firstKeep: boolean
  /** 刚留住的那张卡（花园里做落盆动画用） */
  cardId: number
}

export function noteKeep(cardId: number): KeepHint {
  let firstKeep = false
  try {
    firstKeep = window.localStorage.getItem(KEY_KEPT_ONCE) !== '1'
    window.localStorage.setItem(KEY_KEPT_ONCE, '1')
  } catch {
    /* 存不下就当不是第一次，宁可不弹，也不要反复弹 */
  }
  return { firstKeep, cardId }
}
