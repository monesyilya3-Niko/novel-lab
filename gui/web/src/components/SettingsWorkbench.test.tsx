// P2-F12 SettingsWorkbench 即时校验回归：与后端 update_settings 规则对齐。
import { describe, expect, it, vi } from 'vitest'
import { validateSettingsField } from './SettingsWorkbench'

vi.mock('../state/AppContext', () => ({
  useApp: () => ({ refreshThresholds: vi.fn() }),
}))
vi.mock('../api/client', () => ({
  systemApi: { settings: () => Promise.resolve({}) },
  friendlyError: (e: unknown) => String(e),
}))

const base = {
  consistencyTarget: '90',
  qualityPassLine: '75',
  qualityWarnLine: '60',
  defaultWords: '2400',
  maxAttempts: '3',
}

describe('validateSettingsField', () => {
  it('合法值无错误', () => {
    expect(validateSettingsField('consistencyTarget', '90', base)).toBe('')
    expect(validateSettingsField('qualityPassLine', '75', base)).toBe('')
    expect(validateSettingsField('qualityWarnLine', '60', base)).toBe('')
    expect(validateSettingsField('defaultWords', '2400', base)).toBe('')
    expect(validateSettingsField('maxAttempts', '3', base)).toBe('')
  })

  it('空值与非数字被拒绝', () => {
    expect(validateSettingsField('defaultWords', '', base)).toBe('不能为空')
    expect(validateSettingsField('defaultWords', 'abc', base)).toBe('请输入数字')
  })

  it('范围越界被拒绝（与后端一致）', () => {
    expect(validateSettingsField('qualityPassLine', '101', base)).toBe('必须在 0-100 之间')
    expect(validateSettingsField('qualityPassLine', '-1', base)).toBe('必须在 0-100 之间')
    expect(validateSettingsField('defaultWords', '99', base)).toBe('必须在 100-20000 之间')
    expect(validateSettingsField('defaultWords', '20001', base)).toBe('必须在 100-20000 之间')
    expect(validateSettingsField('maxAttempts', '0', base)).toBe('必须在 1-10 之间')
    expect(validateSettingsField('maxAttempts', '11', base)).toBe('必须在 1-10 之间')
  })

  it('整数约束', () => {
    expect(validateSettingsField('defaultWords', '2400.5', base)).toBe('必须为整数')
    expect(validateSettingsField('maxAttempts', '2.5', base)).toBe('必须为整数')
  })

  it('及格线必须 ≥ 警告线（交叉校验）', () => {
    expect(validateSettingsField('qualityPassLine', '50', base)).toBe('及格线必须 ≥ 警告线')
    expect(validateSettingsField('qualityWarnLine', '80', base)).toBe('警告线必须 ≤ 及格线')
    // 相等合法
    expect(validateSettingsField('qualityPassLine', '60', base)).toBe('')
  })
})
