// ChapterEditor 回归用例（对应交接文档待办 ③）。
//
// 覆盖 2026-09-29 bug 狩猎修的两个行为：
//   1) 外部非空 value 变化必须回同步到编辑器（受控契约）；
//   2) 空段落 / 换行在“纯文本 → HTML → 纯文本”往返中保真。
// 外加：HTML 转义（value 里的 <>& 不得被当成标签解析）、字数统计显示。
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ChapterEditor from './ChapterEditor'

vi.mock('../api/client', () => ({
  toolsApi: {
    checkPoison: vi.fn().mockResolvedValue({
      score: 0,
      verdict: '安全：未发现明显弃坑毒点，行文节奏舒畅',
      totalIssues: 0,
      findings: [],
    }),
  },
  writingApi: {
    deslop: vi.fn().mockResolvedValue({
      aiScore: 0,
      verdict: 'NATURAL',
      verdictCn: '行文自然',
      stats: {
        wordCount: 100,
        sentenceCount: 5,
        issuesCount: 0,
        rangDensity: 0,
      },
      issues: [],
      suggestions: [],
    }),
  },
  friendlyError: (e: unknown) => String(e),
}))

const noop = vi.fn()

/** 取编辑器内各 <p> 的纯文本，按 \n 连接（模拟 getText 的块分隔语义）。 */
function editorParagraphs(container: HTMLElement): string {
  const ps = container.querySelectorAll('.tiptap > p')
  return Array.from(ps)
    .map((p) => p.textContent ?? '')
    .join('\n')
}

describe('ChapterEditor', () => {
  it('初始渲染显示传入的纯文本', async () => {
    const { container } = render(<ChapterEditor value="温霜禾抱着礼物盒" onChange={noop} />)
    await screen.findByText('温霜禾抱着礼物盒')
    expect(container.querySelector('.tiptap')?.textContent).toContain('温霜禾抱着礼物盒')
  })

  it('外部非空 value 变化会同步回编辑器（受控契约）', async () => {
    const { container, rerender } = render(<ChapterEditor value="第一版正文" onChange={noop} />)
    await screen.findByText('第一版正文')
    rerender(<ChapterEditor value="第二版正文" onChange={noop} />)
    await screen.findByText('第二版正文')
    expect(container.querySelector('.tiptap')?.textContent).not.toContain('第一版正文')
  })

  it('外部 value 清空会清空编辑器', async () => {
    const { container, rerender } = render(<ChapterEditor value="待清空的正文" onChange={noop} />)
    await screen.findByText('待清空的正文')
    rerender(<ChapterEditor value="" onChange={noop} />)
    // clearContent 后编辑器只剩一个空段落
    const ps = container.querySelectorAll('.tiptap > p')
    expect(ps.length).toBe(1)
    expect(ps[0].textContent).toBe('')
  })

  it('空段落保真：中间的空行往返不丢失', async () => {
    const { container } = render(<ChapterEditor value={'甲段落\n\n丙段落'} onChange={noop} />)
    await screen.findByText('甲段落')
    // 三个 <p>：甲 / 空 / 丙，join 后还原原文
    expect(editorParagraphs(container)).toBe('甲段落\n\n丙段落')
  })

  it('多段换行保真', async () => {
    const { container } = render(<ChapterEditor value={'第一段\n第二段\n第三段'} onChange={noop} />)
    await screen.findByText('第一段')
    expect(editorParagraphs(container)).toBe('第一段\n第二段\n第三段')
  })

  it('value 中的 HTML 特殊字符被转义，不解析为标签', async () => {
    const { container } = render(<ChapterEditor value={'a<b>&"引号"'} onChange={noop} />)
    await screen.findByText('a<b>&"引号"')
    // 纯文本模式：编辑器内不得出现真正的 <b> 元素
    expect(container.querySelector('.tiptap b')).toBeNull()
  })

  it('显示实时字数', async () => {
    render(<ChapterEditor value="你好世界" onChange={noop} />)
    await screen.findByText('4 字')
  })

  it('达到目标字数显示达标提示', async () => {
    render(<ChapterEditor value="你好世界" onChange={noop} targetChars={4} />)
    await screen.findByText('已达目标 4 字')
  })

  it('点击毒点避雷排查按钮弹出诊断弹窗', async () => {
    render(<ChapterEditor value="主角一剑横扫八荒，斩灭妖邪。" onChange={noop} />)
    const btn = await screen.findByText('🛡️ 毒点避雷排查')
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByText('🛡️ 章节毒点排查诊断')).toBeDefined()
      expect(screen.getByText(/未命中任何已知的过度憋屈/)).toBeDefined()
    })

    const closeBtn = screen.getByText('关闭并返回写作')
    fireEvent.click(closeBtn)
  })

  it('点击去AI味体检按钮弹出诊断弹窗', async () => {
    render(<ChapterEditor value="主角一剑横扫八荒，斩灭妖邪。" onChange={noop} />)
    const btn = await screen.findByText('✨ 去AI味体检')
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByText('✨ 章节去 AI 味诊断')).toBeDefined()
      expect(screen.getByText(/未检测到任何程式化套路/)).toBeDefined()
    })

    const closeBtn = screen.getByText('关闭并返回写作')
    fireEvent.click(closeBtn)
  })
})
