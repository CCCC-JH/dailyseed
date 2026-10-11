/**
 * 毕业卡：把刚宣布毕业的那一盆画成一张图。
 *
 * 「高级感」在这里的落法是**克制**——一张深色卡片、一句原文、一行数据，
 * 没有二维码、没有"快来用"的口号。分享图是留给用户自己的形状，不是广告位。
 */
import { useEffect, useRef, useState } from 'react'
import { Sheet } from './Sheet'
import { canvasToFile, drawGraduationCard } from '../lib/shareCard'
import { copyText, formatDateTimeStamp } from '../lib/format'
import type { Plant } from '../api/types'

interface Props {
  open: boolean
  plant: Plant | null
  onClose: () => void
  onToast: (text: string, tone?: 'normal' | 'warn') => void
}

export function ShareSheet({ open, plant, onClose, onToast }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !plant) return
    let cancelled = false
    const run = async () => {
      // 等字体就绪，否则中文可能以系统字体回退，版式会挪位
      try {
        await document.fonts?.ready
      } catch {
        /* 没有 Font Loading API 就直接画 */
      }
      if (cancelled || !canvasRef.current) return
      drawGraduationCard(canvasRef.current, {
        text: plant.text,
        keptCount: plant.keptCount,
        category: plant.category,
        graduatedDate: (plant.graduatedAt ?? new Date().toISOString()).slice(0, 10),
      })
      setReady(true)
    }
    void run()
    return () => {
      cancelled = true
      setReady(false)
    }
  }, [open, plant])

  if (!plant) return null

  const shareText = `「${plant.text}」——留住 ${plant.keptCount} 次后，我宣布它成了我的习惯。（每日一粒）`

  const download = async () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setBusy(true)
    const file = await canvasToFile(canvas)
    setBusy(false)
    if (!file) {
      onToast('图没生成出来，再试一次', 'warn')
      return
    }
    const url = URL.createObjectURL(file)
    const a = document.createElement('a')
    a.href = url
    a.download = file.name
    a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 4000)
    onToast('已保存到下载')
  }

  const share = async () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setBusy(true)
    const file = await canvasToFile(canvas)
    setBusy(false)
    if (!file) {
      onToast('图没生成出来', 'warn')
      return
    }
    const nav = navigator as Navigator & { canShare?: (data: ShareData) => boolean }
    if (typeof nav.share === 'function' && nav.canShare?.({ files: [file] })) {
      try {
        await nav.share({ files: [file], text: shareText, title: '我毕业的这一粒' })
        return
      } catch {
        /* 用户取消分享不算错误 */
        return
      }
    }
    // 不支持分享文件的浏览器：退回复制文字
    const ok = await copyText(shareText)
    onToast(ok ? '这台设备不能直接分享图，文字已复制' : '这台设备不能分享，长按上图保存')
  }

  return (
    <Sheet open={open} onClose={onClose} labelledBy="share-title">
      <div className="sheet__head">
        <div>
          <h2 className="sheet__title" id="share-title">
            这一粒的故事
          </h2>
          <p className="sheet__sub">
            留住 {plant.keptCount} 次 · {formatDateTimeStamp(plant.graduatedAt)}宣布毕业
          </p>
        </div>
        <button type="button" className="sheet__close" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      <canvas
        ref={canvasRef}
        className="share__preview"
        style={{ aspectRatio: '3 / 4', opacity: ready ? 1 : 0.25, transition: 'opacity 300ms' }}
        aria-label="毕业卡预览"
      />
      <p className="share__hint">长按上图也能保存</p>

      <div className="sheet__actions sheet__actions--row">
        <button type="button" className="btn btn--primary" onClick={share} disabled={busy || !ready}>
          分享
        </button>
        <button type="button" className="btn btn--ghost" onClick={download} disabled={busy || !ready}>
          存成图片
        </button>
      </div>
    </Sheet>
  )
}
