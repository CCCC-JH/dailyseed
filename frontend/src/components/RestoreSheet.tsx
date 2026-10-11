/**
 * 「用同步码找回数据」—— 换手机、或者清了缓存之后的那条路（设计文档 §7.2）。
 *
 * 为什么这一屏要**说清楚会发生什么**：恢复的本质是"把同步码绑到这台设备上"，
 * 成功之后**旧码立刻作废、换发一个新码**。用户有权在按下按钮之前就知道这件事，
 * 所以下面那段话不是免责声明，而是这个动作的一部分。
 *
 * 成功后直接 `location.reload()`：身份换了，整个首屏都得重新拉一遍，
 * 这比在前端手动把 today / history / garden 一个个换掉更不容易出错。
 */
import { useState } from 'react'
import { Sheet } from './Sheet'
import { restoreSession } from '../api/client'
import { canonicalSyncCode, ensureDeviceId } from '../api/session'
import { tapFeedback } from '../lib/format'

interface Props {
  open: boolean
  onClose: () => void
  onToast: (text: string, tone?: 'normal' | 'warn') => void
}

export function RestoreSheet({ open, onClose, onToast }: Props) {
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    // 先按规范形态整理一遍：大小写、空格、漏掉的连字符都不该让用户重抄
    const canonical = canonicalSyncCode(code)
    if (!canonical) {
      onToast('同步码是 8 位，像 K7M2-P9QX 这样', 'warn')
      return
    }
    setBusy(true)
    try {
      // ⚠️ 这台设备必须**还没被注册过**：已经被认识的设备会拿到 409「不用恢复」。
      // 所以这里绝不能先调 bootstrapDevice —— 那等于把路堵上。
      await restoreSession(canonical, ensureDeviceId())
      tapFeedback()
      onToast('找回来了')
      // 身份已经换了，重新走一遍干净的首屏
      window.setTimeout(() => window.location.reload(), 600)
    } catch (e) {
      setBusy(false)
      onToast(e instanceof Error ? e.message : '没找回来，再对一遍码', 'warn')
    }
  }

  return (
    <Sheet open={open} onClose={onClose} labelledBy="restore-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="restore-title">
            用同步码找回数据
          </h2>
          <p className="sheet__sub">换手机、或者清了浏览器缓存之后</p>
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      <label className="remind__time">
        <span className="row__label">同步码</span>
        <input
          type="text"
          inputMode="text"
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          placeholder="K7M2-P9QX"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="同步码"
        />
      </label>

      <p className="muted" style={{ marginTop: 18 }}>
        大小写、空格、漏掉中间那道横杠都没关系，我们会替你补上。
      </p>
      <p className="muted" style={{ marginTop: 12 }}>
        <strong>找回之后会换发一个新码</strong>，你现在那串就作废了——
        所以成功之后记得把新码也记下来。
      </p>

      <div className="sheet__actions">
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={() => void submit()}
          disabled={busy || !code.trim()}
        >
          {busy ? '正在找…' : '找回我的花园'}
        </button>
        <button type="button" className="btn btn--ghost btn--block" onClick={onClose} disabled={busy}>
          先不找
        </button>
      </div>
    </Sheet>
  )
}
