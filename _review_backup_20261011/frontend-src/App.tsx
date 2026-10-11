/**
 * 应用外壳：三页切换 + 设备注册 + 统一的数据拉取。
 *
 * 几个刻意的选择：
 *   · **不引路由库**：三页用状态切换，省一个依赖和一份配置（只有三页，不值得）。
 *   · **不缓存卡片数据**：SSR 式的"每次进页面重新拉"最简单，也不会出现前后端不一致。
 *   · **不用 StrictMode**（见 main.tsx）：注册设备的 effect 只能跑一次。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  bootstrapDevice,
  drawToday,
  fetchExplored,
  fetchGarden,
  fetchHistory,
  fetchToday,
  graduate as graduateApi,
  indulgeToday,
  keepPast as keepPastApi,
  keepToday,
} from './api/client'
import {
  getDeviceId,
  getSyncCode,
  markSyncHintShown,
  shouldShowSyncHint,
  takeJustRecovered,
  turnOffSyncHint,
} from './api/session'
import { noteKeep } from './lib/keepHint'
import { tapFeedback } from './lib/format'
import { useToast } from './lib/useToast'
import { TabBar, type View } from './components/TabBar'
import { Toast } from './components/Toast'
import { SyncCodeSheet } from './components/SyncCodeSheet'
import { ShareSheet } from './components/ShareSheet'
import { RestoreSheet } from './components/RestoreSheet'
import { ReminderSheet } from './components/ReminderSheet'
import { Today } from './pages/Today'
import { Garden } from './pages/Garden'
import { Explored } from './pages/Explored'
import { Settings } from './pages/Settings'
import type {
  ExploredRecord,
  Garden as GardenData,
  HistoryItem,
  Plant,
  Today as TodayCard,
} from './api/types'

type Phase = 'loading' | 'ready' | 'error'

export function App() {
  const { toast, show } = useToast()

  const [view, setView] = useState<View>('today')
  const [phase, setPhase] = useState<Phase>('loading')
  const [error, setError] = useState<string | null>(null)

  const [today, setToday] = useState<TodayCard | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [garden, setGarden] = useState<GardenData | null>(null)
  const [explored, setExplored] = useState<ExploredRecord | null>(null)

  const [keeping, setKeeping] = useState(false)
  const [drawing, setDrawing] = useState(false)
  const [keepingPastId, setKeepingPastId] = useState<number | null>(null)
  const [graduating, setGraduating] = useState(false)
  const [justKeptCardId, setJustKeptCardId] = useState<number | null>(null)

  const [syncCode, setSyncCode] = useState<string | null>(getSyncCode())
  const [syncHintOpen, setSyncHintOpen] = useState(false)
  const [restoreOpen, setRestoreOpen] = useState(false)
  const [remindOpen, setRemindOpen] = useState(false)
  const [sharePlant, setSharePlant] = useState<Plant | null>(null)
  const [deviceId, setDeviceId] = useState<string | null>(getDeviceId())
  const [registerKey, setRegisterKey] = useState(0)

  /** 401 自愈只给一次机会：修不好就走错误态，绝不在注册/取数之间无限打转 */
  const healTried = useRef(false)

  const fail = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : String(e))
    setPhase('error')
  }, [])

  const load = useCallback(async () => {
    setPhase('loading')
    setError(null)
    try {
      const [t, h] = await Promise.all([fetchToday(), fetchHistory(3)])
      setToday(t)
      setHistory(h)
      setPhase('ready')
    } catch (e) {
      // 401 不在这里自愈：那个判断只属于下面那个 effect（一处负责，才不会两处打架）
      fail(e)
    }
  }, [fail])

  /**
   * 设备注册 + 首屏数据：**刻意串成一条链**。
   *
   * 以前这是两个并行的 effect，于是 `/api/today` 可能抢在 `POST /api/session` 之前发出去
   * （设备还没注册 → 401），而那个 effect 里又有个永不重置的 `registering` ref 挡着重试，
   * 结果就是永远停在引导屏。现在只从这个 effect 发起首屏，且注册一定先完成。
   */
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const id = await bootstrapDevice()
        if (cancelled) return
        setDeviceId(id)
        setSyncCode(getSyncCode())
        await load()
        if (cancelled) return
        healTried.current = false
        // 浏览器把我们认回来了（本地身份被清过、但 Cookie 还在）：说一句，
        // 免得用户以为"花园怎么自己回来了"。只说一次（sessionStorage 里那个标记读完即清）
        if (takeJustRecovered()) show('认出你了——你的花园还在')
      } catch (e) {
        if (cancelled) return
        // 401 且还没试过自愈：重建身份，effect 会再跑一次（此时注册会真正重试）
        if (e instanceof ApiError && e.status === 401 && !healTried.current) {
          healTried.current = true
          setRegisterKey((k) => k + 1)
          return
        }
        fail(e) // ★ 不再静默：显示可重试的错误，而不是转到天荒地老
      }
    })()
    return () => {
      cancelled = true
    }
  }, [registerKey, load, fail])

  /** 花园单独拉：它只在进花园页时才需要，但每次操作后都要重新对账 */
  const loadGarden = useCallback(async () => {
    try {
      setGarden(await fetchGarden())
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) fail(e)
    }
  }, [fail])

  useEffect(() => {
    if (view === 'garden') void loadGarden()
  }, [view, loadGarden])

  /** 走过的：和花园一样，只在进这一页时才拉，之后每次留住/补留都对账 */
  const loadExplored = useCallback(async () => {
    try {
      setExplored(await fetchExplored())
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) fail(e)
    }
  }, [fail])

  useEffect(() => {
    if (view === 'explored') void loadExplored()
  }, [view, loadExplored])

  const reloadHistory = useCallback(async () => {
    try {
      setHistory(await fetchHistory(3))
    } catch {
      /* 补留列表刷新失败不值得打断用户 */
    }
  }, [])

  // ==================== 动作 ====================

  /**
   * 抽：第一次 = 揭晓当天那张，之后 = 换掉当天那张（重抽）。
   *
   * 配额在服务端，前端只照 `canRedraw` 画入口；这里失败就把服务端的话原样说出来
   * （比如"这张已经留住了，就不再换了"），不自己编话术。
   */
  const doDraw = useCallback(async () => {
    if (drawing) return
    setDrawing(true)
    try {
      const updated = await drawToday()
      setToday(updated)
      setJustKeptCardId(null)
      tapFeedback()
    } catch (e) {
      show(e instanceof Error ? e.message : '没抽出来，再试一次', 'warn')
    } finally {
      setDrawing(false)
    }
  }, [drawing, show])

  const doKeep = useCallback(async () => {    if (keeping) return
    setKeeping(true)
    try {
      const updated = await keepToday()
      setToday(updated)
      tapFeedback()
      const hint = noteKeep(updated.cardId)
      setJustKeptCardId(updated.cardId)
      await Promise.all([reloadHistory(), loadGarden(), loadExplored()])
      // 同步码提示：只在第一次留着之后提一次，可永久关闭（§0.2）
      if (hint.firstKeep && shouldShowSyncHint()) setSyncHintOpen(true)
    } catch (e) {
      show(e instanceof Error ? e.message : '没留住，再试一次', 'warn')
    } finally {
      setKeeping(false)
    }
  }, [keeping, reloadHistory, loadGarden, loadExplored, show])

  const doKeepPast = useCallback(
    async (assignmentId: number) => {
      setKeepingPastId(assignmentId)
      try {
        const updated = await keepPastApi(assignmentId)
        setHistory((prev) =>
          prev.map((item) => (item.assignmentId === assignmentId ? updated : item)),
        )
        tapFeedback()
        setJustKeptCardId(updated.cardId)
        await Promise.all([loadGarden(), loadExplored()])
        show('补上了')
      } catch (e) {
        show(e instanceof Error ? e.message : '这张补不了', 'warn')
      } finally {
        setKeepingPastId(null)
      }
    },
    [loadGarden, loadExplored, show],
  )

  const doIndulge = useCallback(async () => {
    try {
      const updated = await indulgeToday()
      setToday(updated)
      show('今天换成这张了')
    } catch (e) {
      show(e instanceof Error ? e.message : '今天换不了', 'warn')
    }
  }, [show])

  const doGraduate = useCallback(
    async (cardId: number) => {
      setGraduating(true)
      try {
        await graduateApi(cardId) // 幂等：重复调用也 200，graduatedAt 不覆盖
        await loadGarden()
        setJustKeptCardId(null)
      } catch (e) {
        show(e instanceof Error ? e.message : '没能毕业，再试一次', 'warn')
      } finally {
        setGraduating(false)
      }
    },
    [loadGarden, show],
  )

  // ==================== 引导屏 ====================
  if (phase === 'loading' && !today) {
    return (
      <div className="app">
        <div className="view view--center">
          <div className="boot">
            <div className="boot__seed" aria-hidden="true" />
            <p className="kicker">每日一粒</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      {view === 'today' && (
        <Today
          phase={phase}
          error={error}
          today={today}
          history={history}
          keeping={keeping}
          drawing={drawing}
          keepingPastId={keepingPastId}
          justKeptCardId={justKeptCardId}
          onRetry={() => void load()}
          onDraw={() => void doDraw()}
          onKeep={() => void doKeep()}
          onIndulge={() => void doIndulge()}
          onKeepPast={(id) => void doKeepPast(id)}
          onSeeGarden={() => setView('garden')}
        />
      )}

      {view === 'garden' && (
        <Garden
          phase={garden ? 'ready' : phase}
          error={error}
          garden={garden}
          justKeptCardId={justKeptCardId}
          graduating={graduating}
          onRetry={() => void loadGarden()}
          onGoToday={() => setView('today')}
          onGraduate={doGraduate}
          onShare={(plant) => setSharePlant(plant)}
        />
      )}

      {view === 'explored' && (
        <Explored
          phase={explored ? 'ready' : phase}
          error={error}
          explored={explored}
          onRetry={() => void loadExplored()}
          onGoToday={() => setView('today')}
        />
      )}

      {view === 'settings' && (
        <Settings
          syncCode={syncCode}
          deviceId={deviceId}
          onToast={(text, tone) => show(text, tone)}
          onRestore={() => setRestoreOpen(true)}
          onRemind={() => setRemindOpen(true)}
        />
      )}

      <TabBar view={view} onChange={setView} />

      <Toast toast={toast} />

      <SyncCodeSheet
        open={syncHintOpen}
        syncCode={syncCode}
        onToast={(text, tone) => show(text, tone)}
        onAcknowledge={() => {
          markSyncHintShown()
          setSyncHintOpen(false)
        }}
        onTurnOff={() => {
          turnOffSyncHint()
          markSyncHintShown()
          setSyncHintOpen(false)
          show('不再提了。想找它的时候在「设置」里')
        }}
      />

      <ShareSheet
        open={Boolean(sharePlant)}
        plant={sharePlant}
        onClose={() => setSharePlant(null)}
        onToast={(text, tone) => show(text, tone)}
      />

      <RestoreSheet
        open={restoreOpen}
        onClose={() => setRestoreOpen(false)}
        onToast={(text, tone) => show(text, tone)}
      />

      <ReminderSheet
        open={remindOpen}
        onClose={() => setRemindOpen(false)}
        onToast={(text, tone) => show(text, tone)}
      />
    </div>
  )
}
