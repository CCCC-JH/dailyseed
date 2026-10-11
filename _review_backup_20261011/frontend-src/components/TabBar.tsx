/**
 * 四个页签：今天 / 花园 / 走过的 / 设置。
 *
 * 刻意不引入路由库——四页用状态切换就够，还省掉一个依赖和一份配置。
 * 注意这里**没有红点、没有角标**（红线 1：不做监工）。
 */
export type View = 'today' | 'garden' | 'explored' | 'settings'

const TABS: { id: View; label: string }[] = [
  { id: 'today', label: '今天' },
  { id: 'garden', label: '花园' },
  { id: 'explored', label: '走过的' },
  { id: 'settings', label: '设置' },
]

export function TabBar({ view, onChange }: { view: View; onChange: (next: View) => void }) {
  return (
    <nav className="tabbar" aria-label="主导航">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className="tab"
          aria-current={view === tab.id ? 'page' : undefined}
          onClick={() => onChange(tab.id)}
        >
          <span className="tab__mark" aria-hidden="true" />
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
