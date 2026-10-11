/** 底部弹层外壳：遮罩、Esc 关闭、打开时锁住页面滚动 */
import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  labelledBy?: string
  children: ReactNode
}

export function Sheet({ open, onClose, labelledBy, children }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    // 弹层内没有可聚焦元素时，焦点留在弹层上，读屏不会跑回背景
    sheetRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="mask" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
      >
        <div className="sheet__grip" />
        {children}
      </div>
    </div>
  )
}
