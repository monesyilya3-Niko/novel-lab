// TropePanel 回归用例（交接文档待办 ④：桥段库写作页入口）。
//
// 覆盖：列表渲染与计数、分类筛选、题材适用过滤、选中看详情、
// 「写入写作要点」把桥段骨架文本交给 onInsert。
import { render, screen, fireEvent, within} from '@testing-library/react'
import { describe, expect, it, vi, beforeEach} from 'vitest'
import TropePanel, { tropeToTaskText} from './TropePanel'
import { tropeApi} from '../api/client'

vi.mock('../api/client', () => ({
tropeApi: { list: vi.fn()},
friendlyError: (e: unknown) => String(e),
}))

const listMock = vi.mocked(tropeApi.list)

function trope(id: string, name: string, category: string, genres: string[]) {
return {
id,
name,
category,
genreScope: 'universal',
applicableGenres: genres,
skeleton: {
setup: `${name}的铺垫`,
escalation: [`${name}激化一`, `${name}激化二`],
payoff: `${name}的引爆`,
aftermath: `${name}的余波`,
},
abstractionLevel: 'structural',
parameters: [{ name: '对手身份', options: ['情敌', '上司']}],
effectiveness: '',
variations: [],
commonFailures: ['为打而打'],
}
}

const T1 = trope('T-1', '公开打脸', '打脸', ['realistic-romance', '都市'])
const T2 = trope('T-2', '英雄救美', '情感', ['xianxia'])

beforeEach(() => {
vi.clearAllMocks()
listMock.mockResolvedValue({ total_count: 2, tropes: [T1, T2]})
})

describe('TropePanel', () => {
it('渲染桥段列表与总数', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
expect(screen.getByText('英雄救美')).toBeTruthy()
expect(screen.getByText('2 条')).toBeTruthy()
})

it('按分类筛选', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
fireEvent.mouseDown(screen.getByLabelText('分类'))
const opts = await screen.findAllByRole('option')
fireEvent.click(within(document.body).getByRole('option', { name: '打脸'}))
expect(screen.queryByText('英雄救美')).toBeNull()
expect(screen.getByText('公开打脸')).toBeTruthy()
expect(opts.length).toBeGreaterThan(0)
})

it('只看当前题材适用：过滤掉不适用的桥段', async () => {
render(<TropePanel onInsert={() => {}} currentGenre="realistic-romance" />)
await screen.findByText('公开打脸')
fireEvent.click(screen.getByLabelText(/只看当前题材适用/))
expect(screen.getByText('公开打脸')).toBeTruthy()
expect(screen.queryByText('英雄救美')).toBeNull()
})

it('选中桥段展示骨架详情', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
fireEvent.click(screen.getByText('公开打脸'))
expect(await screen.findByText(/公开打脸的铺垫/)).toBeTruthy()
expect(screen.getByText(/公开打脸的引爆/)).toBeTruthy()
expect(screen.getByText(/对手身份/)).toBeTruthy()
})

it('写入写作要点：onInsert 收到包含桥段名的文本', async () => {
const onInsert = vi.fn()
render(<TropePanel onInsert={onInsert} />)
await screen.findByText('公开打脸')
fireEvent.click(screen.getByText('公开打脸'))
fireEvent.click(await screen.findByRole('button', { name: '写入写作要点'}))
expect(onInsert).toHaveBeenCalledTimes(1)
const text = onInsert.mock.calls[0][0] as string
expect(text).toContain('')
expect(text).toContain('铺垫：公开打脸的铺垫')
expect(text).toContain('引爆：公开打脸的引爆')
})

it('tropeToTaskText 纯函数：首行桥段名标记 + 骨架四段式与参数齐全', () => {
const text = tropeToTaskText(T1 as never)
const lines = text.split('\n')
expect(lines[0]).toBe('【公开打脸】')
expect(text).toContain('激化：1）公开打脸激化一2）公开打脸激化二')
expect(text).toContain('可调参数：对手身份（情敌/上司）')
})

it('tropeTaskMarker 与 tropeToTaskText 首行一致', async () => {
const { tropeTaskMarker} = await import('./TropePanel')
expect(tropeTaskMarker(T1 as never)).toBe('【公开打脸】')
expect(tropeToTaskText(T1 as never).startsWith(tropeTaskMarker(T1 as never))).toBe(true)
})

it('关键词搜索：按桥段名过滤', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
fireEvent.change(screen.getByLabelText('搜索桥段'), { target: { value: '英雄救美'}})
expect(screen.queryByText('公开打脸')).toBeNull()
expect(screen.getByText('英雄救美')).toBeTruthy()
})

it('关键词搜索：命中骨架文本', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
fireEvent.change(screen.getByLabelText('搜索桥段'), { target: { value: '英雄救美的引爆'}})
expect(screen.queryByText('公开打脸')).toBeNull()
expect(screen.getByText('英雄救美')).toBeTruthy()
})

it('关键词搜索：无命中时给提示', async () => {
render(<TropePanel onInsert={() => {}} />)
await screen.findByText('公开打脸')
fireEvent.change(screen.getByLabelText('搜索桥段'), { target: { value: '不存在的桥段zzz'}})
expect(await screen.findByText(/换个分类或关键词试试/)).toBeTruthy()
})

it('防重复写入：已在写作要点中的桥段按钮置灰且不回调', async () => {
const onInsert = vi.fn()
render(<TropePanel onInsert={onInsert} taskText={'已有内容\n【公开打脸】\n铺垫：xxx'} />)
await screen.findByText('公开打脸')
fireEvent.click(screen.getByText('公开打脸'))
const btn = await screen.findByRole('button', { name: '已在写作要点中'})
expect(btn).toBeDisabled()
expect(screen.getByText(/无需重复添加/)).toBeTruthy()
fireEvent.click(btn)
expect(onInsert).not.toHaveBeenCalled()
})

it('防重复写入：未写入过的桥段按钮可用', async () => {
const onInsert = vi.fn()
render(<TropePanel onInsert={onInsert} taskText={'别的内容'} />)
await screen.findByText('公开打脸')
fireEvent.click(screen.getByText('公开打脸'))
const btn = await screen.findByRole('button', { name: '写入写作要点'})
expect(btn).not.toBeDisabled()
fireEvent.click(btn)
expect(onInsert).toHaveBeenCalledTimes(1)
expect(onInsert.mock.calls[0][0] as string).toContain('【公开打脸】')
})

it('加载失败显示错误', async () => {
listMock.mockRejectedValueOnce(new Error('nope'))
render(<TropePanel onInsert={() => {}} />)
expect(await screen.findByText(/nope/)).toBeTruthy()
})
})
