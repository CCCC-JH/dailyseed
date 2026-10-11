/**
 * 后端响应的类型定义。
 *
 * ⚠️ 两条铁律（都是实测出来的，不是猜的）：
 *   1. 后端开了 `spring.jackson.default-property-inclusion: non_null` —— **null 字段根本不会出现在 JSON 里**。
 *      所以 `evidence` / `science` / `source` / `graduatedAt` 全部是**可选**（`?`），
 *      判断一律用 `if (x)`，**绝对不要写 `x === null`**（那个键可能压根不存在）。
 *   2. 卡片依据分三级：A 有 `source`、B 没有、C 连 `evidence` 键都没有（红线 3：没依据就不给入口）。
 */

export type CardType = 'HABIT' | 'EXPLORE' | 'INDULGE'
export type EvidenceLevel = 'A' | 'B'
export type GardenState = 'ACTIVE' | 'GRADUATED'

/** 「?」展开的前三段：① 好处 ② 依据 ③ 出处（只有 A 级有出处） */
export interface Evidence {
  level?: EvidenceLevel
  benefit?: string
  basis?: string
  /** 只有 A 级卡才有这个键 */
  source?: string
}

/** 第 ④ 段「多知道一点」（科普），只挂在卡上 */
export interface ScienceNote {
  key?: string
  title?: string
  body?: string
  source?: string
}

/** POST /api/session */
export interface SessionInfo {
  userId: number
  /** 8 位同步码，形如 K9XG-F734。**必须立刻存下来**。设备已被认识时为 null（`non_null` 下整键消失） */
  syncCode?: string
  created: boolean
  /**
   * **只有"服务端补发了一个 deviceId"时才有值**。
   *
   * 后端为了救"localStorage 被清掉"的情况会种一个 HttpOnly Cookie（脚本读不到里面的 userId），
   * 所以前端唯一能察觉"我换了个人"的途径就是这个字段——收到它就存进 localStorage，之后走正路。
   */
  deviceId?: string
  /** 这次是靠 Cookie 认出来的。前端只用来决定要不要提示一句 */
  recovered?: boolean
}

/** GET /api/today（`POST /api/today/draw` 返回同一个形状） */
export interface Today {
  date: string
  assignmentId: number
  cardId: number
  text: string
  type: CardType
  category: string
  difficulty: number
  /** 放纵卡才有：STOP 停止型 / GIVE 给予型 */
  indulgenceKind?: 'STOP' | 'GIVE'
  kept: boolean
  /** 放纵日入口是否出现（门槛在服务端，且**永不公示**） */
  canIndulge: boolean
  /** 已揭晓：false = 还是卡背，要点一下才翻开（服务端存，刷新后保持） */
  revealed: boolean
  /** 今天已经抽了几次 */
  drawCount: number
  /** 每天最多抽几次；**0 = 无限**（开发期默认） */
  maxDraws: number
  /** 还能不能再抽一次（没留住 + 配额没用完）。后端算好，前端照实画 */
  canRedraw: boolean
  evidence?: Evidence
  science?: ScienceNote
}

/** GET /api/history 里的一条（裸数组，没有 canIndulge / indulgenceKind） */
export interface HistoryItem {
  date: string
  assignmentId: number
  cardId: number
  text: string
  type: CardType
  category: string
  difficulty: number
  kept: boolean
  evidence?: Evidence
  science?: ScienceNote
}

/** 花园里的一盆 */
export interface Plant {
  cardId: number
  type: CardType
  category: string
  text: string
  difficulty: number
  keptCount: number
  firstKeptAt?: string
  lastKeptAt?: string
  state: GardenState
  graduatedAt?: string
  /** 留到 7 次 → 「这个选项现在有意义了」。**不是**「你该毕业了」（§6.1） */
  readyToGraduate: boolean
  evidence?: Evidence
  science?: ScienceNote
}

/** GET /api/garden */
export interface Garden {
  plantedCount: number
  graduatedCount: number
  items: Plant[]
  graduated: Plant[]
}

/**
 * GET /api/explored 里的一条：一张探索卡 + 你唯一一次遇见它的那天。
 *
 * 注意这里**没有** `type` —— 这一页只装探索卡，后端已经保证了；
 * 前端不需要（也不该）再判一次类型。
 */
export interface ExploredCard {
  cardId: number
  category: string
  text: string
  difficulty: number
  /** 遇见它的那天 */
  date: string
  /** 那天有没有把它留下。探索卡不强制留住，这里只是标一下 */
  kept: boolean
  evidence?: Evidence
  science?: ScienceNote
}

/** GET /api/explored。`from`/`to` 为空表示一次都没走过 */
export interface ExploredRecord {
  totalCount: number
  from?: string
  to?: string
  items: ExploredCard[]
}

/** POST /api/session/reminder */
export interface ReminderInfo {
  time: string
}
