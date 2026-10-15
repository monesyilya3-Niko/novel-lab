import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, beforeEach } from 'vitest'
import { I18nProvider, useI18n } from './I18nContext'
import { writeStorage, removeStorage } from '../safeStorage'

function TestConsumer() {
  const { locale, toggleLocale, t } = useI18n()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="brand">{t('brand_name')}</span>
      <span data-testid="fallback">{t('nonexistent_key', '默认兜底')}</span>
      <button onClick={toggleLocale}>切换语言</button>
    </div>
  )
}

describe('I18nContext', () => {
  beforeEach(() => {
    removeStorage('novellab.locale')
  })

  it('默认采用 zh-CN 语言与对应中文翻译', () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    )
    expect(screen.getByTestId('locale').textContent).toBe('zh-CN')
    expect(screen.getByTestId('brand').textContent).toBe('暮冬念春')
    expect(screen.getByTestId('fallback').textContent).toBe('默认兜底')
  })

  it('读取已存储的 en-US 语言偏好', () => {
    writeStorage('novellab.locale', 'en-US')
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    )
    expect(screen.getByTestId('locale').textContent).toBe('en-US')
    expect(screen.getByTestId('brand').textContent).toBe('Exoscribe')
  })

  it('切换语言在 zh-CN 与 en-US 之间循环流转', () => {
    render(
      <I18nProvider>
        <TestConsumer />
      </I18nProvider>,
    )
    expect(screen.getByTestId('locale').textContent).toBe('zh-CN')
    expect(screen.getByTestId('brand').textContent).toBe('暮冬念春')

    const btn = screen.getByText('切换语言')
    fireEvent.click(btn)

    expect(screen.getByTestId('locale').textContent).toBe('en-US')
    expect(screen.getByTestId('brand').textContent).toBe('Exoscribe')

    fireEvent.click(btn)
    expect(screen.getByTestId('locale').textContent).toBe('zh-CN')
    expect(screen.getByTestId('brand').textContent).toBe('暮冬念春')
  })

  it('脱离 Provider 独立调用 useI18n 优雅降级不崩', () => {
    render(<TestConsumer />)
    expect(screen.getByTestId('locale').textContent).toBe('zh-CN')
    expect(screen.getByTestId('brand').textContent).toBe('暮冬念春')
  })
})
