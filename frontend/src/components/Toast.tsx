import type { ToastState } from '../lib/useToast'

export function Toast({ toast }: { toast: ToastState | null }) {
  if (!toast) return null
  return (
    <div className={toast.tone === 'warn' ? 'toast toast--warn' : 'toast'} role="status" aria-live="polite">
      {toast.text}
    </div>
  )
}
