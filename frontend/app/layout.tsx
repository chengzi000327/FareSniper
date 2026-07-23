import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '你的机票发现与出行陪伴 Agent',
  description: '发现机票、记住偏好，并在出发前持续陪伴。',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
