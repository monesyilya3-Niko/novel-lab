import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AsyncBoundary from './AsyncBoundary'

describe('AsyncBoundary 四态', () => {
  it('loading 态渲染骨架屏', () => {
    render(
      <AsyncBoundary loading error={null}>
        <div>data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByTestId('async-skeleton')).toBeInTheDocument()
    expect(screen.queryByText('data')).not.toBeInTheDocument()
  })

  it('error 态显示中文文案 + 重试按钮', async () => {
    const onRetry = vi.fn()
    render(
      <AsyncBoundary loading={false} error={new TypeError('Failed to fetch')} onRetry={onRetry}>
        <div>data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByTestId('async-error')).toBeInTheDocument()
    expect(screen.getByText(/无法连接服务/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('error 优先于 empty；empty 优先于 data', () => {
    const { rerender } = render(
      <AsyncBoundary loading={false} error={new Error('x')} empty>
        <div>data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByTestId('async-error')).toBeInTheDocument()

    rerender(
      <AsyncBoundary loading={false} error={null} empty>
        <div>data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByTestId('async-empty')).toBeInTheDocument()
    expect(screen.queryByText('data')).not.toBeInTheDocument()
  })

  it('empty 态展示标题/提示/CTA', async () => {
    const onClick = vi.fn()
    render(
      <AsyncBoundary
        loading={false}
        error={null}
        empty
        emptyTitle="还没有资产"
        emptyHint="先拆一本书"
        emptyCta={{ label: '去拆书', onClick }}
      >
        <div>data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByText('还没有资产')).toBeInTheDocument()
    expect(screen.getByText('先拆一本书')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '去拆书' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('就绪态直接渲染 children', () => {
    render(
      <AsyncBoundary loading={false} error={null}>
        <div>ready-data</div>
      </AsyncBoundary>,
    )
    expect(screen.getByText('ready-data')).toBeInTheDocument()
  })
})
