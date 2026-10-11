/** 底部弹层外壳：遮罩、Esc 关闭、打开时锁住页面滚动 */
import { useEffect, useRef, type ReactNode } from 'react'

const openSheets: HTMLDivElement[] = []
let previousOverflow = ''

interface Props {
  open: boolean
  onClose: () => void
  labelledBy?: string
  children: ReactNode
}

export function Sheet({ open, onClose, labelledBy, children }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const sheet = sheetRef.current
    if (!open || !sheet) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    if (openSheets.length === 0) {
      previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
    }
    openSheets.push(sheet)
    const onKey = (e: KeyboardEvent) => {
      if (openSheets[openSheets.length - 1] !== sheet) return
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current()
      }
      if (e.key === 'Tab') {
        const focusable = [...sheet.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')]
          .filter(element => element.getClientRects().length > 0)
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (!first) { e.preventDefault(); sheet.focus() }
        else if (e.shiftKey && (document.activeElement === first || document.activeElement === sheet)) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && (document.activeElement === last || document.activeElement === sheet)) { e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    // 弹层内没有可聚焦元素时，焦点留在弹层上，读屏不会跑回背景
    sheet.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      const wasTop = openSheets[openSheets.length - 1] === sheet
      openSheets.splice(openSheets.indexOf(sheet), 1)
      if (openSheets.length === 0) document.body.style.overflow = previousOverflow
      if (wasTop && previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

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
