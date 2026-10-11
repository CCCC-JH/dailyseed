/**
 * 「给自己设个提醒」—— 产品里唯一一个召回手段，而且刻意不是我们推送（§8.1）。
 *
 * 这一屏的全部意思在于：**提醒是用户自己设的**。我们只是生成一个 `.ics` 文件，
 * 之后每天响的是他自己的日历。所以这里不写"别忘了"、不写"坚持一下"，
 * 也不问他"做了没有"——只问他几点想看一眼。
 *
 * 「下载日历提醒」这个动作本身就是一次承诺，这比任何推送文案都值钱。
 */
import { useState } from 'react'
import { Sheet } from './Sheet'
import { fetchReminderIcs, setReminder } from '../api/client'
import { shareOrDownloadFile, tapFeedback } from '../lib/format'

interface Props {
  open: boolean
  onClose: () => void
  onToast: (text: string, tone?: 'normal' | 'warn') => void
}

/** 预设三个钟点：降低决策成本，但时间输入框兜底，谁都能改 */
const PRESETS = [
  { time: '08:00', label: '早上 8:00' },
  { time: '12:30', label: '中午 12:30' },
  { time: '21:00', label: '晚上 21:00' },
]

export function ReminderSheet({ open, onClose, onToast }: Props) {
  const [time, setTime] = useState('08:00')
  const [busy, setBusy] = useState(false)

  const saveAndDownload = async () => {
    setBusy(true)
    try {
      const saved = await setReminder(time)
      const ics = await fetchReminderIcs()
      // 先试系统分享面板（手机上是"存到文件 / 用日历打开"），不支持才退回下载。
      // iOS Safari 的"下载"经常只是把文件丢给某个 App，用户不知道点哪个。
      const how = await shareOrDownloadFile(
        'dailyseed.ics',
        ics,
        'text/calendar;charset=utf-8',
        `${saved.time} 的提醒`,
      )
      if (how === 'cancelled') return // 用户自己关掉了分享面板，不是失败
      tapFeedback()
      onToast(
        how === 'shared'
          ? `${saved.time}，挑个日历存下来就行`
          : `${saved.time} 的提醒已经在你手里了`,
      )
    } catch (e) {
      onToast(e instanceof Error ? e.message : '没生成出来，再试一次', 'warn')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose} labelledBy="reminder-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="reminder-title">
            给自己设个提醒
          </h2>
          <p className="sheet__sub">每天几点想看一眼？</p>
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      <div className="remind__presets" role="group" aria-label="常用时间">
        {PRESETS.map((preset) => (
          <button
            key={preset.time}
            type="button"
            className={preset.time === time ? 'chip chip--on' : 'chip'}
            aria-pressed={preset.time === time}
            onClick={() => setTime(preset.time)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <label className="remind__time">
        <span className="row__label">或者自己定</span>
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          aria-label="提醒时间"
        />
      </label>

      <p className="muted" style={{ marginTop: 18 }}>
        点下面的按钮会往你的日历里放一个日程，之后每天到点响的是你自己的日历。
        想停的时候在日历里把它删掉就行——这件事从头到尾都由你说了算。
      </p>

      <div className="sheet__actions">
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={() => void saveAndDownload()}
          disabled={busy || !time}
        >
          {busy ? '生成中…' : '放进我的日历'}
        </button>
        <button type="button" className="btn btn--ghost btn--block" onClick={onClose}>
          以后再说
        </button>
      </div>
    </Sheet>
  )
}
