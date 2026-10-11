/**
 * 四个页签：今天 / 花园 / 走过的 / 设置。
 *
 * 刻意不引入路由库——四页用状态切换就够，还省掉一个依赖和一份配置。
 * 注意这里**没有红点、没有角标**（红线 1：不做监工）。
 */
import { Icon, type IconName } from './Icon'
export type View = 'today' | 'garden' | 'explored' | 'settings'

const TABS: { id: View; label: string; icon: IconName }[] = [
  { id: 'today', label: '今天', icon: 'sun' },
  { id: 'garden', label: '花园', icon: 'plant' },
  { id: 'explored', label: '走过的', icon: 'path' },
  { id: 'settings', label: '设置', icon: 'settings' },
]

export function TabBar({ view, onChange }: { view: View; onChange: (next: View) => void }) {
  return (
    <aside className="navigation">
      <div className="brand"><span className="brand__symbol"><Icon name="plant" size={26} /></span><div>每日一粒<span className="brand__english">DAILYSEED</span></div></div>
    <nav className="tabbar" aria-label="主导航">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className="tab"
          aria-current={view === tab.id ? 'page' : undefined}
          onClick={() => onChange(tab.id)}
        >
          <Icon name={tab.icon} /><span>{tab.label}</span>
          <span className="tab__mark" aria-hidden="true" />
        </button>
      ))}
    </nav>
      <div className="navigation__note"><Icon name="leaf" size={28} /><p>慢慢来，<br />生活会长出自己的样子。</p><span>一粒种子，一点日常。</span></div>
    </aside>
  )
}
