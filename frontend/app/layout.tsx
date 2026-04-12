import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FareSniper | 特价机票发现平台',
  description: '懂你的航线，才叫真特价。',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
