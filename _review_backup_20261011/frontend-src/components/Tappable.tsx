import type { KeyboardEvent, ReactNode } from 'react'

interface Props {
  onTap: () => void
  className?: string
  style?: React.CSSProperties
  /** 有内层可点元素时用 div + role，避免按钮套按钮（HTML 不允许） */
  as?: 'button' | 'div'
  label?: string
  children: ReactNode
}

export function Tappable({ onTap, className, style, as = 'button', label, children }: Props) {
  if (as === 'button') {
    return (
      <button type="button" className={className} style={style} onClick={onTap} aria-label={label}>
        {children}
      </button>
    )
  }

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onTap()
    }
  }

  return (
    <div
      className={className}
      style={style}
      role="button"
      tabIndex={0}
      aria-label={label}
      onClick={onTap}
      onKeyDown={onKey}
    >
      {children}
    </div>
  )
}
