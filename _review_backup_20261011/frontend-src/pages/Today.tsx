/**
 * 「今天」这一页：拿到今天那一粒 → 留住 / 不勉强。
 *
 * 三条红线在这个文件里的具体落法：
 *   ① 不做监工：没有任何"你还没做""连续几天"的文案；没留住就没有任何提示。
 *   ② 不劝服：卡片下方只有「这张卡有依据」这个**陈述**，不写"建议你看看"。
 *   ③ C 级不显示入口：evidence 为空 → 「?」入口根本不渲染。
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { CardMeta } from '../components/CardMeta'
import { AsyncArea, type Phase } from '../components/AsyncArea'
import { EvidenceSheet } from '../components/EvidenceSheet'
import type { HistoryItem, Today as TodayCard } from '../api/types'
import { formatRelativeDay, todayIso } from '../lib/format'

interface Props {
  phase: Phase
  error: string | null
  today: TodayCard | null
  history: HistoryItem[]
  keeping: boolean
  /** 正在抽（翻面动画期间要挡住重复点击） */
  drawing: boolean
  keepingPastId: number | null
  /** 刚留住的卡（花园里落盆动画 + 「看看它在哪」） */
  justKeptCardId: number | null
  onRetry: () => void
  onDraw: () => void
  onKeep: () => void
  onIndulge: () => void
  onKeepPast: (assignmentId: number) => void
  onSeeGarden: () => void
}

export function Today({
  phase,
  error,
  today,
  history,
  keeping,
  drawing,
  keepingPastId,
  justKeptCardId,
  onRetry,
  onDraw,
  onKeep,
  onIndulge,
  onKeepPast,
  onSeeGarden,
}: Props) {
  /**
   * 是否按"卡面"画。
   *
   * 除了服务端的 revealed，这里**额外**要求 kept 也按卡面画：留住的卡不可能没被翻开过。
   * 这道护栏防的是"库里出现 KEPT + 未揭晓"时画出一个没有按钮的空白卡背（死状态）——
   * 后端也有一道同样的护栏，两边都守住，版本不同步时也不会把用户卡死。
   */
  const faceUp = today?.revealed === true || today?.kept === true

  /** 「?」弹层为哪张卡打开：今天那张，或补留列表里的某一条 */
  const [whyOpen, setWhyOpen] = useState(false)
  const [whyFrom, setWhyFrom] = useState<'today' | number>('today')

  /**
   * 抽卡次数变多 = 这是一次重抽（不是第一次揭晓）。
   * 重抽播"换卡"入场动画；第一次揭晓由卡背翻面来演，不该两套动画叠在一起。
   */
  const [swapped, setSwapped] = useState(false)
  const lastDrawCount = useRef<number | null>(null)
  useEffect(() => {
    const count = today?.drawCount ?? null
    if (count !== null && lastDrawCount.current !== null && count > lastDrawCount.current) {
      setSwapped(true)
    }
    lastDrawCount.current = count
  }, [today?.drawCount])

  const todayDate = todayIso()
  const past = useMemo(
    () => history.filter((item) => item.date !== todayDate).sort((a, b) => (a.date < b.date ? 1 : -1)),
    [history, todayDate],
  )

  const why = useMemo(() => {
    if (whyFrom === 'today') return today
    return past.find((item) => item.assignmentId === whyFrom) ?? null
  }, [whyFrom, today, past])

  return (
    <section className="view" aria-label="今天">
      <AsyncArea
        phase={phase}
        error={error}
        onRetry={onRetry}
        skeleton={
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div className="skeleton" style={{ height: 20, width: '38%' }} />
            <div className="skeleton" style={{ height: 214, borderRadius: 24 }} />
            <div className="skeleton" style={{ height: 52, borderRadius: 999 }} />
          </div>
        }
      >
        {today && (
          <div className="today__stage">
            <header className="today__greeting">
              <span className="kicker">今天这一粒</span>
              <span className="today__date">{today.date}</span>
            </header>

            <div className="flip">
              <div className={`flip__inner${faceUp ? ' is-revealed' : ''}`}>
                <div className="flip__face flip__back">
                  <div className="cardback">
                    <span className="cardback__seed" aria-hidden="true" />
                    <span className="cardback__kicker">今天这一粒</span>
                    <span className="cardback__hint">点一下，看是什么</span>
                  </div>
                </div>

                <div className="flip__face flip__front">
                  <article
                    key={`${today.cardId}-${today.drawCount}`}
                    className={`today__card${swapped ? ' today__card--swap' : ''}`}
                    onAnimationEnd={() => setSwapped(false)}
                  >
                    <CardMeta type={today.type} category={today.category} difficulty={today.difficulty} />

                    <h1 className="today__text">{today.text}</h1>

                    {today.evidence && (
                      <button
                        type="button"
                        className="why"
                        style={{ marginTop: 20 }}
                        onClick={() => {
                          setWhyFrom('today')
                          setWhyOpen(true)
                        }}
                      >
                        <span className="why__glyph" aria-hidden="true">
                          ?
                        </span>
                        这张卡有依据
                      </button>
                    )}
                  </article>
                </div>
              </div>

              {!faceUp && (
                <button
                  type="button"
                  className="flip__tap"
                  onClick={onDraw}
                  disabled={drawing}
                  aria-label="抽今天这一粒"
                >
                  <span className="flip__tap-glyph" aria-hidden="true">
                    ↻
                  </span>
                  抽
                </button>
              )}
            </div>

            {/* 抽完才出现动作。卡背状态下只有一个动作：抽 */}
            {faceUp && (
              <div className="today__actions">
                {today.type === 'INDULGE' ? (
                  <p className="lede" style={{ margin: 0 }}>
                    这张不用留住。放纵是允许，不是收集——它不会进花园。
                  </p>
                ) : today.kept ? (
                  <div className="today__kept">
                    <span className="today__kept-icon" aria-hidden="true">
                      ✓
                    </span>
                    <span>已经留住了。它在窗台上。</span>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="btn btn--primary btn--block"
                    onClick={onKeep}
                    disabled={keeping}
                  >
                    {keeping ? '记下来…' : '留住它'}
                  </button>
                )}

                {today.kept && today.type !== 'INDULGE' && (
                  <button type="button" className="btn btn--ghost btn--block" onClick={onSeeGarden}>
                    去看看它在哪
                  </button>
                )}

                {/* 重抽：后端 canRedraw 判定（没留住 + 配额没用完）。无限配额时刻意不写任何次数 */}
                {today.canRedraw && (
                  <button
                    type="button"
                    className="btn btn--ghost btn--block today__redraw"
                    onClick={onDraw}
                    disabled={drawing}
                  >
                    {drawing ? '正在换…' : '再抽一张'}
                  </button>
                )}
              </div>
            )}

            {justKeptCardId !== null && (
              <p className="muted" style={{ textAlign: 'center' }}>
                留着不是打卡。你只是把它留下了，明天还会遇见它。
              </p>
            )}
          </div>
        )}

        {past.length > 0 && (
          <section aria-label="还能补留的">
            <div className="section-head">
              <h2>还能补留的</h2>
              <span>最近 3 天</span>
            </div>
            <div className="rows">
              {past.map((item) => (
                <div className="row" key={item.assignmentId}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0, flex: 1 }}>
                    <span className="today__date">{formatRelativeDay(item.date, todayDate)}</span>
                    <span
                      style={{
                        fontSize: 14,
                        color: item.kept ? 'var(--ink-3)' : 'var(--ink)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.text}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 'none' }}>
                    {item.evidence && (
                      <button
                        type="button"
                        className="why"
                        style={{ padding: '5px 9px' }}
                        aria-label="看这张卡的依据"
                        onClick={() => {
                          setWhyFrom(item.assignmentId)
                          setWhyOpen(true)
                        }}
                      >
                        <span className="why__glyph" aria-hidden="true">
                          ?
                        </span>
                      </button>
                    )}
                    {item.kept ? (
                      <span className="row__value">已留住</span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn--ghost btn--quiet"
                        onClick={() => onKeepPast(item.assignmentId)}
                        disabled={keepingPastId === item.assignmentId}
                      >
                        {keepingPastId === item.assignmentId ? '…' : '留着'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {today?.canIndulge && (
          <button type="button" className="today__indulge" onClick={onIndulge}>
            今天想放纵
          </button>
        )}
      </AsyncArea>

      <EvidenceSheet
        open={whyOpen}
        onClose={() => setWhyOpen(false)}
        evidence={why?.evidence}
        science={why?.science}
      />
    </section>
  )
}
