/**
 * 「走过的」这一页：探索卡的去处（设计文档 §3.2）。
 *
 * 三类卡各进各的家，这条线是产品结构本身：
 *   习惯卡 → 花园（会留、会长、会毕业）· 探索卡 → **这里**（一次性，走过就算）· 放纵卡 → 什么都不进
 *
 * 所以这一页刻意**不是成就册**：
 *   · 没有进度条、没有"你已探索 23/100"、没有徽章、没有连续天数（红线 1）
 *   · 唯一的计数是一句叙述——"这些是你走过的 23 条路"，那是回看，不是分数
 *   · 不留住也不会被记一笔"你没做"：探索卡本来就是一次性的，走了就是走过了
 *
 * 版式也照这个意思来：**一条安静的路**，不是一排格子。
 */
import { useState } from 'react'
import { AsyncArea, type Phase } from '../components/AsyncArea'
import { EvidenceSheet } from '../components/EvidenceSheet'
import { Tappable } from '../components/Tappable'
import { Icon } from '../components/Icon'
import { PageHeading } from '../components/PageHeading'
import { formatMonthDay, formatRelativeDay, todayIso } from '../lib/format'
import type { ExploredCard, ExploredRecord } from '../api/types'

interface Props {
  phase: Phase
  error: string | null
  explored: ExploredRecord | null
  onRetry: () => void
  onGoToday: () => void
}

/** 一条路：卡原文 + 遇见它的那天 + （有依据才有的）「?」入口 */
function Trail({
  card,
  today,
  onOpenWhy,
}: {
  card: ExploredCard
  today: string
  onOpenWhy: () => void
}) {
  return (
    <div className="trail">
      <span className="trail__dot" aria-hidden="true" />
      <div className="trail__body">
        <p className="trail__text">{card.text}</p>
        <p className="trail__meta">
          <span>{formatRelativeDay(card.date, today)}</span>
          <span className="trail__sep" aria-hidden="true">
            ·
          </span>
          <span>{card.category}</span>
          {card.kept && (
            <>
              <span className="trail__sep" aria-hidden="true">
                ·
              </span>
              <span className="trail__kept">留住了</span>
            </>
          )}
        </p>
      </div>
      {card.evidence && (
        <Tappable className="why why--compact" onTap={onOpenWhy} label={`${card.text}，看它的依据`}>
          <span className="why__glyph" aria-hidden="true">
            ?
          </span>
        </Tappable>
      )}
    </div>
  )
}

export function Explored({ phase, error, explored, onRetry, onGoToday }: Props) {
  const [opened, setOpened] = useState<ExploredCard | null>(null)

  /** 今天按**设备本地时区**算，只用于「今天 / 昨天 / 前天」这类文案对照。
   *  用 UTC（toISOString）会在东八区晚上 8 点之后把日期推早一天，和服务端给的日期对不上。 */
  const today = todayIso()

  return (
    <section className="view" aria-label="走过的">
      <PageHeading eyebrow="LITTLE DISCOVERIES" title="走过的，都是风景。" description="换一条路，看一点新鲜，收藏日常里的偶然。" />
      <AsyncArea
        phase={phase}
        error={error}
        onRetry={onRetry}
        skeleton={
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div className="skeleton" style={{ height: 20, width: '38%' }} />
            <div className="skeleton" style={{ height: 160, borderRadius: 16 }} />
          </div>
        }
      >
        {explored && (
          <>
            <header className="today__greeting">
              <span className="kicker">走过的</span>
              <p className="lede" style={{ marginTop: 2 }}>
                {explored.totalCount === 0
                  ? '探索卡是一次就完了的那种——走过就算，不用留住，也不会再来。'
                  : `这些是你走过的 ${explored.totalCount} 条路。`}
              </p>
              {explored.from && explored.to && explored.from !== explored.to && (
                <p className="muted" style={{ marginTop: 6 }}>
                  {formatMonthDay(explored.from)} — {formatMonthDay(explored.to)}
                </p>
              )}
            </header>

            {explored.items.length === 0 ? (
              <div className="panel empty-trail"><Icon name="path" size={48} />
                <p className="muted" style={{ margin: 0 }}>
                  这里会安安静静地攒着。抽到探索卡的那天，它就出现在这儿。
                </p>
              </div>
            ) : (
              <section aria-label="走过的路">
                <div className="trail-list">
                  {explored.items.map((card) => (
                    <Trail
                      key={card.cardId}
                      card={card}
                      today={today}
                      onOpenWhy={() => setOpened(card)}
                    />
                  ))}
                </div>
              </section>
            )}

            {explored.items.length === 0 && (
              <button type="button" className="btn btn--ghost btn--block" onClick={onGoToday}>
                去看今天那一粒
              </button>
            )}
          </>
        )}
      </AsyncArea>

      <EvidenceSheet
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        evidence={opened?.evidence}
        science={opened?.science}
      />
    </section>
  )
}
