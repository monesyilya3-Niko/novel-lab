import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import EssenceWorkbench from './EssenceWorkbench'

const mockAnalyzeMacro = vi.fn()
const mockListAssets = vi.fn()
const mockCreateAsset = vi.fn()
const mockDeleteAsset = vi.fn()
const mockAdoptAsset = vi.fn()
const mockListBooks = vi.fn()
const mockDeleteBook = vi.fn()
const mockListChains = vi.fn()
const mockCreateChain = vi.fn()
const mockDeleteChain = vi.fn()
const mockProjects = vi.fn()

vi.mock('../api/client', () => ({
  essenceApi: {
    analyzeMacro: (...args: any[]) => mockAnalyzeMacro(...args),
    listAssets: (...args: any[]) => mockListAssets(...args),
    createAsset: (...args: any[]) => mockCreateAsset(...args),
    deleteAsset: (...args: any[]) => mockDeleteAsset(...args),
    adoptAsset: (...args: any[]) => mockAdoptAsset(...args),
    listBooks: (...args: any[]) => mockListBooks(...args),
    deleteBook: (...args: any[]) => mockDeleteBook(...args),
    listChains: (...args: any[]) => mockListChains(...args),
    createChain: (...args: any[]) => mockCreateChain(...args),
    deleteChain: (...args: any[]) => mockDeleteChain(...args),
  },
  writingApi: {
    projects: () => mockProjects(),
  },
  friendlyError: (e: any) => (e?.message ? e.message : '错误'),
}))

describe('EssenceWorkbench', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockProjects.mockResolvedValue([{ name: '测试创作项目', dir: 'p1' }])
    mockListAssets.mockResolvedValue({
      assets: [
        {
          id: 1,
          bookId: 'book_01',
          category: 'outline',
          title: '仙逆第一卷卷纲',
          content: '凡人少年入宗门受辱，偶得神秘圆珠天逆珠逆天改命。',
          summary: '宗门逆袭骨架',
          tags: '凡人流,杀伐果断',
          genre: 'xianxia',
          platform: 'qidian',
          rating: 5,
          userNote: '开篇节奏极其紧凑',
        },
      ],
    })
    mockListBooks.mockResolvedValue({
      books: [
        {
          bookId: 'book_01',
          title: '仙逆',
          genre: 'xianxia',
          platform: 'qidian',
          totalChapters: 120,
          totalChars: 360000,
          avgChapterLen: 3000,
          dialogueRatio: 0.32,
          rhythmClimaxInterval: 3,
          aiSlopScore: 1.2,
          summary: '经典凡人流',
        },
      ],
    })
  })

  it('渲染四大顶层标签页', () => {
    render(<EssenceWorkbench />)
    expect(screen.getByText('离线精读与解构提炼')).toBeInTheDocument()
    expect(screen.getByText('五维精华资产库')).toBeInTheDocument()
    expect(screen.getByText('伏笔暗线图谱')).toBeInTheDocument()
    expect(screen.getByText('已精读书籍档案')).toBeInTheDocument()
  })

  it('切换到伏笔暗线图谱并加载展示暗线', async () => {
    mockListChains.mockResolvedValue({
      chains: [
        {
          id: 101,
          bookId: 'book_01',
          title: '九品功法残卷',
          category: '力量伏笔',
          plantChapter: 3,
          revealChapter: 25,
          climaxChapter: 60,
          description: '第三章主角偶然在藏经阁角落拾取，实为无上心法残卷。',
          status: 'planted',
        },
      ],
    })
    render(<EssenceWorkbench />)
    fireEvent.click(screen.getByText('伏笔暗线图谱'))
    await waitFor(() => {
      expect(screen.getByText('九品功法残卷')).toBeInTheDocument()
      expect(screen.getByText('力量伏笔')).toBeInTheDocument()
      expect(screen.getByText('🌱 已埋下')).toBeInTheDocument()
      expect(screen.getByText(/跨越 57 章释放/)).toBeInTheDocument()
    })
  })

  it('精读提炼表单校验与成功提炼解构', async () => {
    mockAnalyzeMacro.mockResolvedValue({
      bookId: 'essence_test_1',
      title: '仙道求索',
      genre: 'xianxia',
      platform: 'qidian',
      totalChapters: 3,
      totalChars: 9000,
      avgChapterLen: 3000,
      dialogueRatio: 0.35,
      rhythmClimaxInterval: 3,
      aiSlopScore: 1.5,
      openingThreeChapters: [
        {
          chapterIndex: 1,
          title: '第1章 惊变',
          charCount: 3000,
          hookType: '生存危机悬念',
          hasPayoffOrAnticipation: true,
          dialogueRatio: 0.32,
          excerpt: '寒风呼啸，少年拔剑。',
        },
      ],
      highFrequencySpeechPatterns: [{ phrase: '冷笑', count: 4 }],
      suggestedAssets: [
        {
          category: 'outline',
          title: '仙道开局三章主线',
          summary: '危机切入与机缘初现',
          content: '详细内容...',
        },
      ],
    })

    render(<EssenceWorkbench />)

    // 未填书名直接点提炼
    fireEvent.click(screen.getByRole('button', { name: '开始深度精读与宏观解构' }))
    expect(screen.getByText('请输入书籍名称')).toBeInTheDocument()

    // 填写书名与正文
    const titleInput = screen.getByLabelText('精图书籍/样本名称')
    fireEvent.change(titleInput, { target: { value: '仙道求索' } })

    const textInput = screen.getByLabelText('输入精读正文（支持多章连粘，自动识别章节序号）')
    fireEvent.change(textInput, { target: { value: '第1章 惊变\n寒风呼啸，少年拔剑。' } })

    fireEvent.click(screen.getByRole('button', { name: '开始深度精读与宏观解构' }))

    await waitFor(() => {
      expect(mockAnalyzeMacro).toHaveBeenCalledWith({
        title: '仙道求索',
        text: '第1章 惊变\n寒风呼啸，少年拔剑。',
        platform: 'fanqie',
        genre: 'xianxia',
      })
    })

    expect(await screen.findByText('精读提炼报告')).toBeInTheDocument()
    expect(screen.getByText('3 章')).toBeInTheDocument()
    expect(screen.getByText('9,000 字')).toBeInTheDocument()
    expect(screen.getByText('35.0%')).toBeInTheDocument()
    expect(screen.getByText('仙道开局三章主线')).toBeInTheDocument()
  })

  it('五维资产库展示与一键反哺弹窗', async () => {
    mockAdoptAsset.mockResolvedValue({
      adopted: true,
      targetKind: 'outline',
      recordId: 101,
    })

    render(<EssenceWorkbench />)

    // 切换到资产库标签
    fireEvent.click(screen.getByText('五维精华资产库'))

    await waitFor(() => {
      expect(mockListAssets).toHaveBeenCalled()
    })

    expect(await screen.findByText('仙逆第一卷卷纲')).toBeInTheDocument()
    expect(screen.getByText('创作者感悟: 开篇节奏极其紧凑')).toBeInTheDocument()

    // 点击一键反哺创作
    fireEvent.click(screen.getByRole('button', { name: '一键反哺创作' }))
    expect(await screen.findByText('一键反哺至写作工坊')).toBeInTheDocument()

    // 点击确认反哺
    fireEvent.click(screen.getByRole('button', { name: '确认反哺' }))

    await waitFor(() => {
      expect(mockAdoptAsset).toHaveBeenCalledWith({
        asset_id: 1,
        project: '测试创作项目',
        target_kind: 'outline',
      })
    })
  })

  it('已精读书籍档案列表与删除', async () => {
    mockDeleteBook.mockResolvedValue({ deleted: true, bookId: 'book_01' })

    render(<EssenceWorkbench />)

    // 切换到已精读书籍档案
    fireEvent.click(screen.getByText('已精读书籍档案'))

    await waitFor(() => {
      expect(mockListBooks).toHaveBeenCalled()
    })

    expect(await screen.findByText('仙逆')).toBeInTheDocument()
    expect(screen.getByText('120 章 | 360,000 字')).toBeInTheDocument()
  })
})
