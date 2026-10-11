/**
 * 同步码的**一次性**提示（第一次留着之后弹一次，可永久关闭）。
 *
 * 只说实话，不夸大也不安慰：
 *   · 这个码是唯一能找回数据的凭据
 *   · 清缓存 + 从没抄下来 = 真的找不回来（后端只存哈希，物理上补发不了）
 * 然后把安慰性话术全删掉——不用"别担心""放心"这类词。
 */
import { useState } from 'react'
import { Sheet } from './Sheet'
import { copyText } from '../lib/format'

interface Props {
  open: boolean
  syncCode: string | null
  /** 「我知道了」——本次不再提，之后还有一次机会 */
  onAcknowledge: () => void
  /** 「不再提醒」——永久关闭 */
  onTurnOff: () => void
  onToast: (text: string, tone?: 'normal' | 'warn') => void
}

export function SyncCodeSheet({ open, syncCode, onAcknowledge, onTurnOff, onToast }: Props) {
  const [copying, setCopying] = useState(false)

  const doCopy = async () => {
    if (!syncCode) return
    setCopying(true)
    const ok = await copyText(syncCode)
    setCopying(false)
    onToast(ok ? '已复制。找张纸条、或者给自己发条消息' : '复制没成功，手动记一下这 8 位')
  }

  return (
    <Sheet open={open} onClose={onAcknowledge} labelledBy="sync-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="sync-title">
            把这句话记住
          </h2>
          <p className="sheet__sub">只提这一次</p>
        </div>
      </div>

      <div className={syncCode ? 'synccode' : 'synccode synccode--missing'}>
        <span className="synccode__value">{syncCode ?? '暂时没拿到'}</span>
      </div>

      <p className="lede" style={{ marginTop: 18 }}>
        这串码是你找回这些卡的唯一凭据。它只存在这台设备上，后端不保存原文——
        所以如果你清了浏览器缓存、又从来没把它记下来，这些卡就真的找不回来了。
      </p>

      <div className="sheet__actions">
        {syncCode && (
          <button type="button" className="btn btn--primary btn--block" onClick={doCopy} disabled={copying}>
            {copying ? '复制中…' : '复制这串码'}
          </button>
        )}
        <button type="button" className="btn btn--ghost btn--block" onClick={onAcknowledge}>
          我知道了
        </button>
        <button type="button" className="btn btn--quiet btn--block" onClick={onTurnOff}>
          不再提醒
        </button>
      </div>
    </Sheet>
  )
}
