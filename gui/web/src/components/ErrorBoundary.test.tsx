// ErrorBoundary 回归：渲染失败展示错误+重试按钮；重试后成功恢复内容。
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import ErrorBoundary from './ErrorBoundary'

let shouldThrow = true
function Boom() {
  if (shouldThrow) throw new Error('模拟渲染失败')
  return <div>恢复成功</div>
}

describe('ErrorBoundary 失败→重试', () => {
  beforeEach(() => {
    shouldThrow = true
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('失败展示错误与重试按钮，重试后恢复', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByText('组件加载失败')).toBeInTheDocument()
    expect(screen.getByText('模拟渲染失败')).toBeInTheDocument()

    shouldThrow = false
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(screen.getByText('恢复成功')).toBeInTheDocument()
    expect(screen.queryByText('组件加载失败')).not.toBeInTheDocument()
  })

  it('重试后再次失败仍可展示错误', () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    // 重试时依然抛错 → 仍停留在错误态
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(screen.getByText('组件加载失败')).toBeInTheDocument()
  })
})
