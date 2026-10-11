/**
 * 「花园」这一页：窗台 · 一排小盆。
 *
 * 单位叫**盆**，页面叫**花园**（已定 ①）。每张习惯卡 = 一盆，
 * 植株大小由留住次数决定，毕业 = 它长成了、可以搬走（从窗台移到「已内化」）。
 *
 * 这里**没有**：进度条、目标数、连续天数、排行榜（红线 1 / §十二）。
 * 放纵卡也不会出现在这里——后端用 visibleInGarden 守这条线，前端只是照实画。
 */
import { useMemo, useState } from 'react'
import { AsyncArea, type Phase } from '../components/AsyncArea'
import { EvidenceSheet } from '../components/EvidenceSheet'
import { GraduateConfirm } from '../components/GraduateConfirm'
import { Pot } from '../components/Pot'
import { SeedIllustration } from '../components/Icon'
import { PageHeading } from '../components/PageHeading'
import { Sheet } from '../components/Sheet'
import { Tappable } from '../components/Tappable'
import { formatDateTimeStamp, keptCountLabel } from '../lib/format'
import type { Garden as GardenData, Plant } from '../api/types'

interface Props {
  phase: Phase
  error: string | null
  garden: GardenData | null
  justKeptCardId: number | null
  graduating: boolean
  onRetry: () => void
  onGoToday: () => void
  onGraduate: (cardId: number) => Promise<Plant | null>
  onShare: (plant: Plant) => void
}

export function Garden({
  phase,
  error,
  garden,
  justKeptCardId,
  graduating,
  onRetry,
  onGoToday,
  onGraduate,
  onShare,
}: Props) {
  const [opened, setOpened] = useState<Plant | null>(null)
  const [confirming, setConfirming] = useState<Plant | null>(null)
  const [whyOpen, setWhyOpen] = useState(false)

  /** 没有植株的空窗台：不渲染空花圃，只放一句话 + 一个回去的路 */
  const isEmpty = useMemo(() => {
    if (!garden) return false
    return garden.items.length === 0 && garden.graduated.length === 0
  }, [garden])

  const confirmGraduate = async () => {
    if (!confirming) return
    const done = await onGraduate(confirming.cardId)
    if (!done) return
    setConfirming(null)
    setOpened(null)
    onShare(done)
  }

  return (
    <section className="view" aria-label="花园">
      <PageHeading eyebrow="YOUR LITTLE GARDEN" title="日子在这里，慢慢长大。" description="那些被你留下的小事，成了窗台上的风景。" />
      <AsyncArea
        phase={phase}
        error={error}
        onRetry={onRetry}
        skeleton={
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div className="skeleton" style={{ height: 20, width: '34%' }} />
            <div className="skeleton" style={{ height: 240, borderRadius: 16 }} />
          </div>
        }
      >
        {garden && (
          <>
            <header className="today__greeting">
              <span className="kicker">我的花园</span>
              <p className="lede" style={{ marginTop: 2 }}>
                {isEmpty
                  ? '窗台上还是空的。留住的卡会一盆一盆地摆上来。'
                  : `窗台上还有 ${garden.plantedCount} 盆，已经内化 ${garden.graduatedCount} 盆。`}
              </p>
            </header>

            <section aria-label="窗台">
              <div className="sill">
                {garden.items.length === 0 ? (
                  <div className="sill__empty"><SeedIllustration small /><p>
                    空的窗台不着急。
                    <br />
                    今天那一粒如果觉得好，留住它，这里就多一盆。
                  </p></div>
                ) : (
                  <div className="sill__grid">
                    {garden.items.map((plant) => (
                      <Pot
                        key={plant.cardId}
                        plant={plant}
                        justKept={plant.cardId === justKeptCardId}
                        onTap={() => setOpened(plant)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </section>

            {garden.graduated.length > 0 && (
              <section aria-label="已经内化的">
                <div className="section-head">
                  <h2>已经内化的</h2>
                  <span>{garden.graduatedCount} 盆</span>
                </div>
                <div className="graduated">
                  {garden.graduated.map((plant) => (
                    <Tappable
                      key={plant.cardId}
                      className="graduated__row"
                      onTap={() => setOpened(plant)}
                      label={`${plant.text}，已毕业`}
                    >
                      <span className="graduated__seal" aria-hidden="true">
                        ✦
                      </span>
                      <span className="graduated__text">{plant.text}</span>
                      <span className="graduated__date">{formatDateTimeStamp(plant.graduatedAt)}</span>
                    </Tappable>
                  ))}
                </div>
              </section>
            )}

            {isEmpty && (
              <button type="button" className="btn btn--ghost btn--block" onClick={onGoToday}>
                去看今天那一粒
              </button>
            )}
          </>
        )}
      </AsyncArea>

      {opened && opened.state === 'GRADUATED' && (
        <Sheet open onClose={() => setOpened(null)} labelledBy="plant-title">
          <div className="sheet__head">
            <div>
              <h2 className="sheet__title" id="plant-title">
                {opened.text}
              </h2>
              <p className="sheet__sub">
                内化于 {formatDateTimeStamp(opened.graduatedAt)} · 共{keptCountLabel(opened.keptCount)}
              </p>
            </div>
            <button type="button" className="sheet__close" onClick={() => setOpened(null)} aria-label="关闭">
              ✕
            </button>
          </div>

          {opened.evidence && (
            <button
              type="button"
              className="why"
              onClick={() => {
                setWhyOpen(true)
              }}
            >
              <span className="why__glyph" aria-hidden="true">
                ?
              </span>
              这张卡有依据
            </button>
          )}

          <div className="sheet__actions">
            <button type="button" className="btn btn--ghost btn--block" onClick={() => onShare(opened)}>
              把它做成一张图
            </button>
          </div>
        </Sheet>
      )}

      {opened && opened.state === 'ACTIVE' && (
        <Sheet open onClose={() => setOpened(null)} labelledBy="plant-title">
          <div className="sheet__head">
            <div>
              <h2 className="sheet__title" id="plant-title">
                {opened.text}
              </h2>
              <p className="sheet__sub">
                {opened.category} · 留住 {opened.keptCount} 次
                {opened.firstKeptAt ? ` · 第一次是 ${formatDateTimeStamp(opened.firstKeptAt)}` : ''}
              </p>
            </div>
            <button type="button" className="sheet__close" onClick={() => setOpened(null)} aria-label="关闭">
              ✕
            </button>
          </div>

          {opened.evidence && (
            <button type="button" className="why" onClick={() => setWhyOpen(true)}>
              <span className="why__glyph" aria-hidden="true">
                ?
              </span>
              这张卡有依据
            </button>
          )}

          <div className="sheet__actions">
            <button
              type="button"
              className="btn btn--primary btn--block"
              onClick={() => {
                setConfirming(opened)
                setOpened(null)
              }}
            >
              宣布毕业
            </button>
            {!opened.readyToGraduate && (
              <p className="muted" style={{ textAlign: 'center' }}>
                留得越久越有把握，不过什么时候算"成了"，你说了算。
              </p>
            )}
          </div>
        </Sheet>
      )}

      <GraduateConfirm
        plant={confirming}
        busy={graduating}
        onClose={() => setConfirming(null)}
        onConfirm={confirmGraduate}
      />

      <EvidenceSheet
        open={whyOpen}
        onClose={() => setWhyOpen(false)}
        evidence={opened?.evidence}
        science={opened?.science}
      />
    </section>
  )
}
