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
listMock.mockResolvedValue({ totalCount: 2, tropes: [T1, T2]})
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

it('tropeToTaskText 纯函数：骨架四段式与参数齐全', () => {
const text = tropeToTaskText(T1 as never)
expect(text).toContain('')
expect(text).toContain('激化：1）公开打脸激化一2）公开打脸激化二')
expect(text).toContain('可调参数：对手身份（情敌/上司）')
})

it('加载失败显示错误', async () => {
listMock.mockRejectedValueOnce(new Error('nope'))
render(<TropePanel onInsert={() => {}} />)
expect(await screen.findByText(/nope/)).toBeTruthy()
})
})
