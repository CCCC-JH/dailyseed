/**
 * 一盆 = 一张卡。植株大小由「留住次数」决定，分四档。
 *
 * 视觉是离散的（4 档）而不是连续的：连续生长在数据上几乎看不出差别，
 * 而且会让用户开始数"还差几次变大"——那就变成绩效了（红线 1）。
 */
import { keptCountLabel } from '../lib/format'
import type { Plant } from '../api/types'

/** 留住次数 → 植株档位 1..4 */
function sizeClass(keptCount: number): 1 | 2 | 3 | 4 {
  if (keptCount >= 15) return 4
  if (keptCount >= 7) return 3
  if (keptCount >= 3) return 2
  return 1
}

interface Props {
  plant: Plant
  onTap: () => void
  /** 刚留住时的落盆动画 */
  justKept?: boolean
}

export function Pot({ plant, onTap, justKept = false }: Props) {
  const size = sizeClass(plant.keptCount)
  return (
    <button
      type="button"
      className={`pot pot--${size}${justKept ? ' pot--tapped' : ''}`}
      onClick={onTap}
      aria-label={`${plant.text}，${keptCountLabel(plant.keptCount)}`}
    >
      <span className="pot__stage" aria-hidden="true">
        <span className="pot__saucer" />
        <span className="pot__bowl">
          <span className="pot__leaf" />
          <span className="pot__leaf pot__leaf--2" />
          <span className="pot__leaf pot__leaf--3" />
        </span>
      </span>
      <span className="pot__meta">
        <span className="pot__count">{plant.keptCount}</span>
        {plant.readyToGraduate && (
          <span className="pot__ready" title="留得够久了，这个选项现在有意义了">
            ✦
          </span>
        )}
      </span>
    </button>
  )
}
