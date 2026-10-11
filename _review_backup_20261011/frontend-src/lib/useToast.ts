/** 一个够用的提示条：一次只显示一条，自己会走 */
import { useCallback, useRef, useState } from 'react'

export interface ToastState {
  text: string
  tone: 'normal' | 'warn'
}

export function useToast() {
  const [toast, setToast] = useState<ToastState | null>(null)
  const timer = useRef<number | null>(null)

  const show = useCallback((text: string, tone: 'normal' | 'warn' = 'normal') => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    setToast({ text, tone })
    timer.current = window.setTimeout(() => setToast(null), 2800)
  }, [])

  const clear = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    setToast(null)
  }, [])

  return { toast, show, clear }
}
