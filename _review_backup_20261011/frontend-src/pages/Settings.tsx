/**
 * 「设置」这一页：同步码常驻可查 + 找回入口 + 提醒 + 产品说明。
 *
 * 同步码为什么放在这里、而且是常驻的：清缓存时 deviceId 和码**一起**消失，
 * 后端认不出你是谁——补发物理上无法送达。所以唯一能做的就是"趁他还不在乎时先塞给他一次"，
 * 并且让他随时能找到。
 *
 * 正文里的「找回」和「提醒」都只是把弹层叫起来，真正的动作在各自的 Sheet 里
 * （那两个都涉及"会发生什么"，需要自己的空间说清楚）。
 */
import { useState } from 'react'
import { copyText } from '../lib/format'

interface Props {
  syncCode: string | null
  deviceId: string | null
  onToast: (text: string, tone?: 'normal' | 'warn') => void
  onRestore: () => void
  onRemind: () => void
}

export function Settings({ syncCode, deviceId, onToast, onRestore, onRemind }: Props) {
  const [busy, setBusy] = useState(false)

  const copyCode = async () => {
    if (!syncCode) return
    setBusy(true)
    const ok = await copyText(syncCode)
    setBusy(false)
    onToast(ok ? '已复制' : '复制没成功，手动记一下')
  }

  return (
    <section className="view" aria-label="设置">
      <header className="today__greeting">
        <span className="kicker">设置</span>
      </header>

      <section aria-label="同步码">
        <div className="section-head">
          <h2>同步码</h2>
          <span>找回数据的凭据</span>
        </div>

        <div className={syncCode ? 'synccode' : 'synccode synccode--missing'}>
          <span className="synccode__value">{syncCode ?? '还没拿到'}</span>
        </div>

        {syncCode && (
          <button
            type="button"
            className="btn btn--ghost btn--block"
            style={{ marginTop: 12 }}
            onClick={copyCode}
            disabled={busy}
          >
            {busy ? '复制中…' : '复制同步码'}
          </button>
        )}

        <p className="muted" style={{ marginTop: 14 }}>
          这串码只存在这台设备上，服务端只保存它的哈希、不保存原文。
          清了浏览器缓存、又从来没记过它，数据就找不回来了——这是"零注册"必须付出的代价。
        </p>
      </section>

      <section aria-label="数据">
        <div className="section-head">
          <h2>这台设备</h2>
        </div>
        <div className="rows">
          <div className="row">
            <span className="row__label">设备标识</span>
            <span className="row__value" style={{ maxWidth: '52%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {deviceId ?? '—'}
            </span>
          </div>
          <button type="button" className="row row--tap" onClick={onRestore}>
            <span className="row__label">用同步码找回数据</span>
            <span className="row__value">换手机时用</span>
          </button>
          <button type="button" className="row row--tap" onClick={onRemind}>
            <span className="row__label">每天提醒我一下</span>
            <span className="row__value">放进你的日历</span>
          </button>
        </div>
        <p className="muted" style={{ marginTop: 14 }}>
          提醒是<strong>你自己设的</strong>，不是我们推送——到点响的是你的日历，想停就把它删掉。
        </p>
      </section>

      <section aria-label="关于">
        <div className="section-head">
          <h2>关于</h2>
        </div>
        <div className="panel">
          <p className="lede" style={{ margin: 0 }}>
            每天给你一个很小的约定。想做就做，觉得好就留下它——留久了，它会自己长成你的习惯。
          </p>
          <p className="muted" style={{ marginTop: 14 }}>
            它不打卡、不算连续天数、不发通知、也不问你做了没有。它只问一句：这张还要吗。
          </p>
          <p className="muted" style={{ marginTop: 14 }}>
            「21 天养成一个习惯」来自 1960 年一位整形外科医生的临床观察，被当成结论传了六十年。
            真实研究里，达到自动化的中位数是 66 天，范围 18 到 254 天——所以这里没有任何天数承诺，
            毕业由你自己宣布。
          </p>
        </div>
      </section>
    </section>
  )
}
