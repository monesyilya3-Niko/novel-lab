import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import InspirationWorkbench from './InspirationWorkbench'

vi.mock('../api/client', () => ({
  toolsApi: {
    generateNames: vi.fn().mockResolvedValue({
      kind: 'character',
      style: 'xianxia',
      gender: 'all',
      count: 3,
      names: ['林清绝', '陆云深', '苏长生'],
    }),
    getHooks: vi.fn().mockResolvedValue({
      totalCount: 1,
      hooks: [
        {
          id: 'HK-001',
          name: '宗门废柴退婚打脸',
          genre: '仙侠修真',
          first300Words: '寒风呼啸，退婚书扔在脸上。',
          chapter1Beat: '被辱受挫，神秘青铜残片觉醒',
          chapter2Beat: '修复经脉，一夜突破三个境界',
          chapter3Beat: '宗门大比前夕，当众镇压挑衅者',
        },
      ],
    }),
    getGoldfingers: vi.fn().mockResolvedValue({
      totalCount: 1,
      goldfingers: [
        {
          id: 'GF-001',
          name: '神级选择系统',
          category: '系统外挂',
          triggerMechanism: '面临危机或命运抉择时',
          progressionCurve: '初期提供极品功法',
          costAndLimits: ['不可撤回'],
          antiCollapseRule: '奖励梯度严格与当前剧情相称',
        },
      ],
    }),
    getShuangdians: vi.fn().mockResolvedValue({
      totalCount: 1,
      shuangdians: [
        {
          id: 'SD-001',
          name: '越级碾压·生死台上断天骄',
          category: '实力碾压',
          suppression: '天骄反派当众逼签生死契约',
          buildUp: '暗中借金手指参悟至尊功法',
          mockery: '第一拍·嘲讽：反派大声哄笑',
          silence: '第二拍·沉默：全场以为主角吓傻',
          crush: '第三拍·碾压：一击必杀吐血跪地',
          spectators: '第四拍·围观：全场数万修士死寂三息',
          upgradePath: '同辈恶霸 → 宗门核心真传',
          antiFatigueTip: '打脸不可原地复读',
        },
      ],
    }),
    getWorlds: vi.fn().mockResolvedValue({
      totalCount: 1,
      worlds: [
        {
          id: 'WD-001',
          name: '东方仙侠·古典修真飞升体系',
          genre: '仙侠修真',
          tierLadder: [
            {
              tier: '炼气期 (1-9层)',
              powerDesc: '引气入体，五感敏锐',
              breakthroughCost: '需百日筑基',
            },
          ],
          ironRules: ['法则铁律一：境界鸿沟不可逾越'],
          currencyAndResources: '下品灵石 → 中品灵石',
          powerCollapseWarning: '严禁金丹多如狗',
        },
      ],
    }),
    getDialogues: vi.fn().mockResolvedValue({
      totalCount: 1,
      dialogues: [
        {
          id: 'DLG-001',
          name: '宗门死斗·生死看淡一剑封喉',
          category: '极致打脸',
          scene: '生死擂台上反派嘲弄主角残废',
          aiSlopBad: '你居然敢挑战我，真是不自量力！',
          humanGood: '话太多。拔剑。',
          subtext: '视若草芥，多说半个字都是浪费灵力',
          actionBeats: '眼神淡漠如看死物，长剑斜指地面',
          speechProfileTip: '惜字如金，重音在动词',
        },
      ],
    }),
    getCharacters: vi.fn().mockResolvedValue({
      totalCount: 1,
      characters: [
        {
          id: 'CHR-001',
          name: '苟道长生·守阁假杂役真剑祖',
          roleType: '主角型',
          genre: '仙侠修真',
          surfaceMask: '宗门藏经阁九品洒扫杂役',
          hiddenContrast: '三千年前纯阳剑祖转世',
          coreMotivation: '苟到飞升尽头得大逍遥',
          fatalFlaw: '严重迫害妄想症',
          antiCollapseRule: '非生死关头绝不暴露底牌',
          catchphrase: '道友切莫动怒，贫道这就告退……',
          arcProgression: '冷眼旁观 → 布局三界 → 一剑荡平诡异',
        },
      ],
    }),
    getEmotions: vi.fn().mockResolvedValue({
      totalCount: 1,
      emotions: [
        {
          id: 'EMT-001',
          emotionScene: '窒息杀意与无形压迫',
          category: '杀机与气场',
          aiClicheExample: '反派非常愤怒，身上释放出强大的杀气',
          sensoryBreakdown: {
            vision: '瞳孔骤然凝缩如针尖',
            physiology: '颈后寒毛根根炸立',
            touchAndTemp: '四周空气仿佛瞬间凝结成铅水',
            soundAndSilence: '整座大殿只剩下粗重紊乱的喘息声',
          },
          environmentalResonance: '狂风无风自止，厅堂火苗压成幽蓝色',
          masterProseSample: '那人甚至没有抬手。他只是静静站在阶前，垂着眼帘。',
          writingRhythmTip: '先抑后扬，严禁用抽象形容词',
        },
      ],
    }),
  },
  friendlyError: (e: unknown) => String(e),
}))

describe('InspirationWorkbench', () => {
  it('渲染起名工坊并显示名称 Chips', async () => {
    render(<InspirationWorkbench />)
    expect(screen.getByText('起名工坊 (离线智能)')).toBeDefined()
    await waitFor(() => {
      expect(screen.getByText('林清绝')).toBeDefined()
      expect(screen.getByText('陆云深')).toBeDefined()
      expect(screen.getByText('苏长生')).toBeDefined()
    })
  })

  it('切换到开篇钩子库', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('开篇钩子库 (黄金三章)'))
    await waitFor(() => {
      expect(screen.getByText('宗门废柴退婚打脸')).toBeDefined()
      expect(screen.getByText('寒风呼啸，退婚书扔在脸上。')).toBeDefined()
    })
  })

  it('切换到金手指机制库', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('金手指机制库 (12大外挂)'))
    await waitFor(() => {
      expect(screen.getByText('神级选择系统')).toBeDefined()
      expect(screen.getByText('系统外挂')).toBeDefined()
    })
  })

  it('切换到爽点打脸设计', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('爽点打脸设计 (三段闭环)'))
    await waitFor(() => {
      expect(screen.getByText('越级碾压·生死台上断天骄')).toBeDefined()
      expect(screen.getByText('实力碾压')).toBeDefined()
    })
  })

  it('切换到世界观体系', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('世界观体系 (力量阶梯)'))
    await waitFor(() => {
      expect(screen.getByText('东方仙侠·古典修真飞升体系')).toBeDefined()
      expect(screen.getByText('炼气期 (1-9层)')).toBeDefined()
    })
  })

  it('切换到名场面台词库 (反AI对话)', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('名场面台词库 (反AI对话)'))
    await waitFor(() => {
      expect(screen.getByText('宗门死斗·生死看淡一剑封喉')).toBeDefined()
      expect(screen.getByText('话太多。拔剑。')).toBeDefined()
      expect(screen.getByText(/你居然敢挑战我/)).toBeDefined()
    })
  })

  it('切换到爆款人设矩阵 (反差弧光)', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('爆款人设矩阵 (反差弧光)'))
    await waitFor(() => {
      expect(screen.getByText('苟道长生·守阁假杂役真剑祖')).toBeDefined()
      expect(screen.getByText(/宗门藏经阁九品洒扫杂役/)).toBeDefined()
      expect(screen.getByText(/三千年前纯阳剑祖转世/)).toBeDefined()
    })
  })

  it('切换到情绪高潮演出 (五感通感)', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('情绪高潮演出 (五感通感)'))
    await waitFor(() => {
      expect(screen.getByText('窒息杀意与无形压迫')).toBeDefined()
      expect(screen.getByText(/那人甚至没有抬手/)).toBeDefined()
      expect(screen.getByText(/瞳孔骤然凝缩如针尖/)).toBeDefined()
    })
  })
})
