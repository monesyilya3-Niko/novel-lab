import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import WritingWorkbench from './WritingWorkbench'

const mockProjects = vi.fn()
const mockGetProjectMeta = vi.fn()
const mockUpdateProjectMeta = vi.fn()
const mockOutlines = vi.fn()
const mockCharacters = vi.fn()
const mockNotes = vi.fn()
const mockStats = vi.fn()
const mockImportChapter = vi.fn()
const mockDeslop = vi.fn()
const mockCheckPoisons = vi.fn()
const mockDiagnose = vi.fn()
const mockListAssets = vi.fn()
const mockListChains = vi.fn()
const mockExport = vi.fn()
const mockCreateOutline = vi.fn()

vi.mock('../api/client', () => ({
  writingApi: {
    projects: () => mockProjects(),
    getProjectMeta: (proj: string) => mockGetProjectMeta(proj),
    updateProjectMeta: (proj: string, body: any) => mockUpdateProjectMeta(proj, body),
    outlines: (proj: string) => mockOutlines(proj),
    characters: (proj: string) => mockCharacters(proj),
    notes: (proj: string) => mockNotes(proj),
    stats: (proj: string, days?: number) => mockStats(proj, days),
    importChapter: (body: any) => mockImportChapter(body),
    deslop: (text: string) => mockDeslop(text),
    export: (proj: string, fmt?: string) => mockExport(proj, fmt),
    createOutline: (body: any) => mockCreateOutline(body),
    createCharacter: vi.fn().mockResolvedValue({ id: 10 }),
    createNote: vi.fn().mockResolvedValue({ id: 10 }),
    inject: vi.fn().mockResolvedValue({ prompt: 'test prompt', char_count: 10 }),
    generate: vi.fn().mockResolvedValue({ status: 'done', taskId: 't1' }),
    taskState: vi.fn().mockResolvedValue({ status: 'done' }),
    score: vi.fn().mockResolvedValue({ score: 95 }),
    assembleCandidates: vi.fn().mockResolvedValue([]),
    assemble: vi.fn().mockResolvedValue({}),
  },
  toolsApi: {
    checkPoison: (text: string) => mockCheckPoisons(text),
  },
  platformApi: {
    diagnose: (body: any) => mockDiagnose(body),
  },
  essenceApi: {
    listAssets: (params?: any) => mockListAssets(params),
    listChains: (bookId?: string) => mockListChains(bookId),
    createChain: vi.fn().mockResolvedValue({ id: 99, title: 'new chain' }),
  },
  assetApi: {
    list: vi.fn().mockResolvedValue({ items: [] }),
  },
  subscribeTaskEvents: vi.fn(() => () => {}),
  friendlyError: (e: any) => (e?.message ? e.message : String(e)),
}))

vi.mock('../state/AppContext', () => ({
  useApp: () => ({
    consistencyTarget: 90,
  }),
  useAppOptional: () => null,
}))

vi.mock('./useWritingAssets', () => ({
  useWritingAssets: () => ({
    assets: [],
    distilledAssets: [],
    byKind: () => [],
    voice: '',
    setVoice: vi.fn(),
    genrePack: '',
    setGenrePack: vi.fn(),
    craft: '',
    setCraft: vi.fn(),
    distilled: '',
    setDistilled: vi.fn(),
    proseCard: '',
    setProseCard: vi.fn(),
    mismatches: [],
    voiceGenre: '',
  }),
}))

describe('WritingWorkbench - 沉浸式创作室与多空间闭环', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockProjects.mockResolvedValue([
      { id: 'p1', name: '万界仙途', readOnly: false, platform: 'fanqie', genre: 'xianxia', targetWords: 1000000 },
    ])
    mockGetProjectMeta.mockResolvedValue({
      project: '万界仙途',
      platform: 'fanqie',
      genre: 'xianxia',
      targetWords: 1000000,
      summary: '少年持逆天珠入宗门',
      meta: {},
      createdAt: 1000,
      updatedAt: 2000,
    })
    mockOutlines.mockResolvedValue([
      { id: 1, project: '万界仙途', kind: 'chapter', title: '第1章 惊变', summary: '宗门考核受挫', status: 'planned', sortOrder: 1 },
    ])
    mockCharacters.mockResolvedValue([
      { id: 1, project: '万界仙途', name: '林凡', role: '主角', description: '表面病弱内藏杀伐果断', extra: '' },
    ])
    mockNotes.mockResolvedValue([
      { id: 1, project: '万界仙途', title: '金手指伏笔', content: '珠子在月圆之夜发光' },
    ])
    mockStats.mockResolvedValue({
      project: '万界仙途',
      todayWords: 3200,
      todayChapters: 1,
      totalWords: 50000,
      totalChapters: 16,
      streakDays: 5,
      history: [],
    })
    mockListAssets.mockResolvedValue({
      assets: [
        {
          id: 1,
          bookId: 'book_01',
          category: 'hook',
          title: '30秒退婚逆袭钩子',
          content: '今日你退我婚约，他日莫悔！',
          summary: '番茄开篇高爆钩子',
          tags: '逆袭,退婚',
          genre: 'xianxia',
          platform: 'fanqie',
          rating: 5,
          userNote: '',
          createdAt: 1000,
          updatedAt: 2000,
        },
      ],
    })
    mockListChains.mockResolvedValue({
      chains: [
        {
          id: 1,
          bookId: '万界仙途',
          title: '神秘石珠身世',
          category: 'identity',
          plantChapter: 1,
          revealChapter: 5,
          climaxChapter: 10,
          description: '主角身上的上古至宝',
          status: 'planted',
          createdAt: 1000,
          updatedAt: 1000,
        },
      ],
    })
    mockExport.mockResolvedValue({
      filename: '万界仙途-全书导出.docx',
      contentBase64: 'UEsDBBQAAAAI',
      format: 'docx',
      chapters: 16,
      words: 50000,
    })
  })

  it('默认渲染沉浸创作室 StudioView，包含作品企划与三栏主体', async () => {
    render(<WritingWorkbench />)
    expect(screen.getByText('沉浸创作室 (Studio)')).toBeInTheDocument()
    expect(screen.getByText('工坊流水线 (Pipeline)')).toBeInTheDocument()

    await waitFor(() => {
      // 顶栏作品与平台定位
      expect(screen.getByText('番茄小说')).toBeInTheDocument()
      expect(screen.getByText('保存并入库')).toBeInTheDocument()
      expect(screen.getByText('下一章')).toBeInTheDocument()
      expect(screen.getByText('全书导出')).toBeInTheDocument()
      expect(screen.getByText('⚡ 排毒与去AI')).toBeInTheDocument()
      expect(screen.getByText('📊 签约预测')).toBeInTheDocument()
      // 左栏大纲
      expect(screen.getByText(/大纲 \(1\)/)).toBeInTheDocument()
    })
  })

  it('支持无缝切换到工坊流水线 Pipeline 模式', async () => {
    render(<WritingWorkbench />)
    const pipelineTab = screen.getByRole('tab', { name: /工坊流水线/ })
    fireEvent.click(pipelineTab)
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: '资产注入' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: 'AI 章节生成' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '单章质检打分' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '去 AI 味实验室' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: '小说精华数据库' })).toBeInTheDocument()
    })
  })

  it('一键全维排毒与去 AI 检测并渲染诊断反馈', async () => {
    mockCheckPoisons.mockResolvedValue({
      score: 85,
      verdict: '轻度风险',
      totalIssues: 1,
      findings: [
        {
          line: 1,
          type: 'abused_protagonist',
          typeName: '开局过度憋屈虐主',
          severity: 'high',
          snippet: '林凡被抽打得皮开肉绽无力还手',
          matched: '无力还手',
          reason: '缺乏底牌反制机制',
          suggestion: '在被羞辱同时展现神珠微光或心理算计',
        },
      ],
    })
    mockDeslop.mockResolvedValue({
      aiScore: 4.2,
      verdict: 'MILD',
      verdictCn: '轻度 AI 指纹',
      stats: { wordCount: 1500, sentenceCount: 80, issuesCount: 2, rangDensity: 0.1 },
      issues: [],
      suggestions: ['减少“不可否认”此类虚浮转折'],
    })

    render(<WritingWorkbench />)
    await waitFor(() => expect(screen.getByText('⚡ 排毒与去AI')).toBeInTheDocument())

    fireEvent.click(screen.getByText('⚡ 排毒与去AI'))
    await waitFor(() => {
      expect(mockCheckPoisons).toHaveBeenCalled()
      expect(mockDeslop).toHaveBeenCalled()
      expect(screen.getByText(/毒点排查: 轻度风险/)).toBeInTheDocument()
      expect(screen.getByText(/开局过度憋屈虐主/)).toBeInTheDocument()
      expect(screen.getByText(/AI 指纹: 轻度 AI 指纹/)).toBeInTheDocument()
    })
  })

  it('五维精华反哺：资产一键插入正文', async () => {
    render(<WritingWorkbench />)
    await waitFor(() => expect(screen.getByText('精华资产反哺')).toBeInTheDocument())

    fireEvent.click(screen.getByText('精华资产反哺'))
    await waitFor(() => {
      expect(screen.getByText('30秒退婚逆袭钩子')).toBeInTheDocument()
      expect(screen.getByText('插入正文')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('插入正文'))
    await waitFor(() => {
      expect(screen.getByText(/已成功将【30秒退婚逆袭钩子】插入当前正文/)).toBeInTheDocument()
    })
  })

  it('企划定位对话框：支持修改并持久化平台与题材属性', async () => {
    mockUpdateProjectMeta.mockResolvedValue({
      project: '万界仙途',
      platform: 'qidian',
      genre: 'xianxia',
      targetWords: 2000000,
      summary: '升级流宗门大作',
    })

    render(<WritingWorkbench />)
    await waitFor(() => expect(screen.getByText('企划定位')).toBeInTheDocument())

    fireEvent.click(screen.getByText('企划定位'))
    await waitFor(() => {
      expect(screen.getByText('作品企划与多平台定位')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('保存企划'))
    await waitFor(() => {
      expect(mockUpdateProjectMeta).toHaveBeenCalledWith('万界仙途', expect.objectContaining({
        platform: expect.any(String),
        genre: expect.any(String),
      }))
      expect(screen.getByText('作品企划定位已保存并持久化')).toBeInTheDocument()
    })
  })

  it('全书导出对话框：支持选择格式并调用导出端点', async () => {
    // 模拟 URL.createObjectURL 与 revokeObjectURL
    window.URL.createObjectURL = vi.fn().mockReturnValue('blob:test')
    window.URL.revokeObjectURL = vi.fn()

    render(<WritingWorkbench />)
    await waitFor(() => expect(screen.getByText('全书导出')).toBeInTheDocument())

    fireEvent.click(screen.getByText('全书导出'))
    await waitFor(() => {
      expect(screen.getByText('全书一键导出与排版生成')).toBeInTheDocument()
      expect(screen.getByText('立即下载')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('立即下载'))
    await waitFor(() => {
      expect(mockExport).toHaveBeenCalledWith('万界仙途', 'docx')
      expect(screen.getByText(/全书已成功导出为 万界仙途-全书导出.docx/)).toBeInTheDocument()
    })
  })

  it('下一章轮转：自动递增章号并重置章节状态', async () => {
    render(<WritingWorkbench />)
    await waitFor(() => expect(screen.getByText('下一章')).toBeInTheDocument())

    fireEvent.click(screen.getByText('下一章'))
    await waitFor(() => {
      expect(screen.getByText(/已准备好开启第 2 章创作/)).toBeInTheDocument()
      const titleInput = screen.getByDisplayValue('第2章')
      expect(titleInput).toBeInTheDocument()
    })
  })

  it('伏笔暗线协同提醒与右栏图谱联动', async () => {
    render(<WritingWorkbench />)
    await waitFor(() => {
      // 本章处于第1章埋设阶段，触发协同提醒条
      expect(screen.getByText(/本章（第 1 章）伏笔暗线协同推进提醒/)).toBeInTheDocument()
      expect(screen.getByText(/神秘石珠身世/)).toBeInTheDocument()
    })

    // 切换右栏至精华与暗线
    fireEvent.click(screen.getByText('精华资产反哺'))
    await waitFor(() => expect(screen.getByText(/伏笔暗线 \(1\)/)).toBeInTheDocument())

    // 切换至暗线子页签
    fireEvent.click(screen.getByText(/伏笔暗线 \(1\)/))
    await waitFor(() => {
      expect(screen.getByText('草蛇灰线推进图谱')).toBeInTheDocument()
      expect(screen.getByText('引用暗线到正文')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('引用暗线到正文'))
    await waitFor(() => {
      expect(screen.getByText(/已成功将【神秘石珠身世】插入当前正文/)).toBeInTheDocument()
    })
  })
})
