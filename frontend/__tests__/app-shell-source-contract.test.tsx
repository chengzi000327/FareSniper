import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import React from 'react'
import { render, screen } from '@testing-library/react'
import { AppShell } from '@/components/app-shell'

describe('AppShell source claims', () => {
  it('shows only supported providers and honest progressive states', () => {
    render(<AppShell />)

    expect(screen.getAllByText('携程旅行').length).toBeGreaterThan(0)
    expect(screen.getAllByText('飞猪旅行').length).toBeGreaterThan(0)
    expect(screen.getAllByText('国际航司/销售平台').length).toBeGreaterThan(0)
    expect(screen.getAllByText('正在获取数据').length).toBeGreaterThan(0)
    expect(screen.getAllByText('等待下次刷新').length).toBeGreaterThan(0)
    expect(screen.getAllByText('待确认').length).toBeGreaterThan(0)
    expect(screen.getAllByText('待查询 · 正在获取数据')).toHaveLength(2)
    expect(screen.queryByText(/直飞特惠/)).not.toBeInTheDocument()
    expect(screen.queryByText(/实时价格/)).not.toBeInTheDocument()

    for (const unsupported of [
      '去哪儿网',
      '航旅纵横',
      '同程旅行',
      '穿透全网',
      '综合计算行李额与税费',
      '12,847',
    ]) {
      expect(screen.queryByText(new RegExp(unsupported))).not.toBeInTheDocument()
    }
    expect(screen.queryByText(/¥\d/)).not.toBeInTheDocument()
    expect(screen.queryByText('最低')).not.toBeInTheDocument()
  })

  it('does not hard-code prices, lowest flags, or numeric scores', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'components/app-shell.tsx'),
      'utf8',
    )

    expect(source).not.toMatch(/(?:basePrice|tax|baggageFee|originalPrice)=\{\d/)
    expect(source).not.toMatch(/price:\s*\d/)
    expect(source).not.toContain('lowest: true')
    expect(source).not.toMatch(/recommendScore="\d/)
    expect(source.match(/placeholder/g)).toHaveLength(2)
  })
})
