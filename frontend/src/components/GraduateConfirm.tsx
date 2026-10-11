/**
 * 毕业确认。
 *
 * §6.1 的关键：**不设阈值、不催促**。所以这里是"如果你觉得它已经是你的习惯了"，
 * 而不是"你已经留住 7 次，可以毕业了"。系统只在你按下去之后放手。
 */
import { Sheet } from './Sheet'
import type { Plant } from '../api/types'

interface Props {
  plant: Plant | null
  onClose: () => void
  onConfirm: () => void
  busy: boolean
}

export function GraduateConfirm({ plant, onClose, onConfirm, busy }: Props) {
  return (
    <Sheet open={Boolean(plant)} onClose={onClose} labelledBy="graduate-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="graduate-title">
            这一粒，毕业吗
          </h2>
          <p className="sheet__sub">毕业由你自己宣布</p>
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      {plant && (
        <>
          <div className="panel">
            <p className="evidence__text" style={{ fontSize: 17 }}>
              {plant.text}
            </p>
            <p className="muted" style={{ marginTop: 10 }}>
              留住 {plant.keptCount} 次 · {plant.category}
            </p>
          </div>

          <p className="lede" style={{ marginTop: 18 }}>
            毕业不是完成打卡，是你自己说：这件事已经不用我想着去做了。
            宣布之后它会离开窗台，不会被再发给你，但一直留在花园里。
          </p>

          <div className="sheet__actions">
            <button type="button" className="btn btn--primary btn--block" onClick={onConfirm} disabled={busy}>
              {busy ? '记下来…' : '我宣布它毕业了'}
            </button>
            <button type="button" className="btn btn--quiet btn--block" onClick={onClose}>
              再留一阵
            </button>
          </div>
        </>
      )}
    </Sheet>
  )
}
