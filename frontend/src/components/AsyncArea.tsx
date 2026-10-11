/**
 * 统一处理"加载中 / 出错 / 有数据"三种状态，避免每个页面各写一套。
 *
 * 出错文案一律是"服务没连上"这种大实话，不写"出错了请重试"式的官腔。
 */
import type { ReactNode } from 'react'

export type Phase = 'loading' | 'ready' | 'error'

interface Props {
  phase: Phase
  error?: string | null
  onRetry?: () => void
  skeleton?: ReactNode
  children: ReactNode
}

export function AsyncArea({ phase, error, onRetry, skeleton, children }: Props) {
  if (phase === 'loading') {
    return <>{skeleton ?? <div className="skeleton" style={{ height: 180 }} />}</>
  }

  if (phase === 'error') {
    return (
      <div className="error-state" role="alert">
        <p className="title" style={{ fontSize: 19 }}>
          暂时没能连上
        </p>
        <p className="lede" style={{ maxWidth: 340 }}>
          {error ?? '等网络恢复后，再试一次。你的记录还在。'}
        </p>
        {onRetry && (
          <button type="button" className="btn btn--ghost" onClick={onRetry}>
            再试一次
          </button>
        )}
      </div>
    )
  }

  return <>{children}</>
}
