/**
 * 这张卡的一行元信息：类型 · 分类 · 难度。
 *
 * 刻意**不显示**：连续天数、打卡次数、任何进度百分比（红线 1）。
 * 难度写成"很轻 / 中等 / 偏重"而不是数字——数字会被读成分数。
 */
import { difficultyLabel, typeLabel } from '../lib/format'
import type { CardType } from '../api/types'

export function CardMeta({ type, category, difficulty }: { type: CardType; category: string; difficulty: number }) {
  return (
    <div className="today__meta">
      <span className={type === 'INDULGE' ? 'chip chip--harvest' : 'chip'}>{typeLabel(type)}</span>
      <span className="chip">{category}</span>
      <span className="chip">{difficultyLabel(difficulty)}</span>
    </div>
  )
}
