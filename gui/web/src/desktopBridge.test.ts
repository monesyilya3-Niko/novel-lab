// 桌面桥（Electron preload 注入的 window.novelLab）的两种运行环境回归。
//
// 这里测的是"桥在不在、异常怎么吞"，不是原生对话框本身（那是主进程的
// dialog.showOpenDialog，只能在桌面版里手测）。浏览器模式下必须彻底无声：
// 页面不能出现一个点了没反应的按钮。
import { describe, expect, it, vi } from 'vitest'

import { hasDesktopBridge, pickPath } from './desktopBridge'

describe('desktopBridge', () => {
  it('浏览器模式下没有桥，既不报告可用也不报错', async () => {
    delete (window as unknown as { novelLab?: unknown }).novelLab
    expect(hasDesktopBridge()).toBe(false)
    await expect(pickPath('dir')).resolves.toBeNull()
  })

  it('桌面模式下按 kind 转发，并把选中的路径交回来', async () => {
    const spy = vi.fn().mockResolvedValue('D:/写作/我的书')
    ;(window as unknown as { novelLab: { pickPath: typeof spy } }).novelLab = { pickPath: spy }
    expect(hasDesktopBridge()).toBe(true)
    await expect(pickPath('dir')).resolves.toBe('D:/写作/我的书')
    expect(spy).toHaveBeenCalledWith('dir')
  })

  it('主进程对话框失败时返回 null，而不是把异常文案当成路径', async () => {
    ;(window as unknown as { novelLab: { pickPath: () => Promise<string> } }).novelLab = {
      pickPath: () => Promise.reject(new Error('主进程已退出')),
    }
    await expect(pickPath('file')).resolves.toBeNull()
  })

  it('用户取消时主进程回 null，调用方据此什么都不填', async () => {
    ;(window as unknown as { novelLab: { pickPath: () => Promise<null> } }).novelLab = {
      pickPath: async () => null,
    }
    await expect(pickPath('dir')).resolves.toBeNull()
  })
})
