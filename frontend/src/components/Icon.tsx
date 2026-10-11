import type { CSSProperties, ReactNode } from 'react'

export type IconName = 'sun' | 'plant' | 'path' | 'settings' | 'arrow' | 'leaf'
const paths: Record<IconName, ReactNode> = {
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>,
  plant: <path d="M8 15h8l-1 7H9l-1-7Zm4 0V8M12 11C6 12 4 8 4 4c5 0 8 2 8 7Zm0-2c0-5 3-7 8-7 0 5-3 8-8 7Z" />,
  path: <><path d="M6 21c-6-6 13-6 12-12" /><circle cx="7" cy="5" r="3" /><path d="M7 8v3m11-5V2m-2 2h4" /></>,
  settings: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" fill="var(--bg)" /><circle cx="15" cy="17" r="3" fill="var(--bg)" /></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  leaf: <path d="M5 19C-1 8 10 2 21 3c0 11-5 19-16 16ZM5 19 16 8" />,
}
export function Icon({ name, size = 22, style }: { name: IconName; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name]}</svg>
}

/** 本地矢量插画，缩放不模糊，也不需要额外请求。 */
export function SeedIllustration({ small = false }: { small?: boolean }) {
  return (
    <svg className={small ? 'seed-art seed-art--small' : 'seed-art'} viewBox="0 0 260 210" fill="none" aria-hidden="true">
      <circle cx="130" cy="101" r="84" fill="#eee9d9" /><circle cx="183" cy="49" r="19" fill="#dfac74" />
      <path d="M38 169h184M62 177h137" stroke="#c9c6b2" strokeLinecap="round" /><ellipse cx="130" cy="171" rx="50" ry="6" fill="#dbd4c1" />
      <path d="M130 123c0-27-2-42 3-67" stroke="#47664b" strokeWidth="3" strokeLinecap="round" />
      <path d="M131 97C98 97 87 78 86 59c29 1 46 17 45 38Z" fill="#7c9364" /><path d="M131 76c-1-28 15-43 39-45 2 26-13 43-39 45Z" fill="#3f6249" /><path d="M130 110c5-28 23-39 46-35-5 25-24 37-46 35Z" fill="#a5af7c" />
      <path d="m99 72 30 24m8-26 21-25m-21 59 26-19" stroke="#f6f1df" strokeOpacity=".45" strokeLinecap="round" />
      <path d="m104 126 7 38c1 4 37 4 38 0l7-38" fill="#bc775a" /><path d="m111 132 5 28m6-26 2 27" stroke="#d99a7b" strokeWidth="3" strokeLinecap="round" /><rect x="100" y="119" width="60" height="12" rx="4" fill="#ce8c6b" />
      <path d="m55 114 3-7 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z" fill="#bba679" /><path d="M197 129v9m-4-4h8" stroke="#8c9a79" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
