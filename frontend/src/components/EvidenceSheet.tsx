/**
 * 「?」展开：① 好处 ② 依据 ③ 出处（只有 A 级有）④ 多知道一点。
 *
 * 措辞红线（§3.6 / 红线 2）：只陈述"谁发现了什么"，**不写"你应该…"**。
 * B 级固定加一句"这是机制，不是研究结论"——诚实用在这里，而不是靠话术补。
 * C 级卡连入口都不给（红线 3），所以这个组件根本不会为 C 级渲染。
 */
import { Sheet } from './Sheet'
import type { Evidence, ScienceNote } from '../api/types'

interface Props {
  open: boolean
  onClose: () => void
  evidence?: Evidence
  science?: ScienceNote
}

export function EvidenceSheet({ open, onClose, evidence, science }: Props) {
  const hasAny = Boolean(evidence) || Boolean(science)
  const isGradeA = evidence?.level === 'A'

  return (
    <Sheet open={open} onClose={onClose} labelledBy="evidence-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="evidence-title">
            这张卡的依据
          </h2>
          {evidence?.level && (
            <p className="sheet__sub">
              {isGradeA ? '有具体研究支持' : '只是机制讲得通，没有人专门研究过这件事'}
            </p>
          )}
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      {!hasAny ? (
        <p className="muted">这张卡没有留下依据。</p>
      ) : (
        <div className="evidence">
          {evidence?.benefit && (
            <section className="evidence__block">
              <span className="evidence__label">① 好处</span>
              <p className="evidence__text">{evidence.benefit}</p>
            </section>
          )}

          {evidence?.basis && (
            <section className="evidence__block">
              <span className="evidence__label">② 依据</span>
              <p className="evidence__text">{evidence.basis}</p>
              {evidence.level === 'B' && (
                <p className="evidence__note">这是机制，不是研究结论。</p>
              )}
            </section>
          )}

          {evidence?.source && (
            <section className="evidence__block">
              <span className="evidence__label">③ 出处</span>
              <p className="evidence__text evidence__text--cite">{evidence.source}</p>
            </section>
          )}

          {science && (
            <section className="evidence__science">
              <span className="evidence__label">④ 多知道一点</span>
              {science.title && <h3>{science.title}</h3>}
              {science.body && <p className="evidence__text">{science.body}</p>}
              {science.source && (
                <p className="evidence__text evidence__text--cite" style={{ marginTop: 10 }}>
                  {science.source}
                </p>
              )}
            </section>
          )}
        </div>
      )}
    </Sheet>
  )
}
