import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import HelpWorkbench from './HelpWorkbench'
import { I18nProvider } from '../state/I18nContext'

describe('HelpWorkbench 帮助中心与功能指南全量双语支持', () => {
  it('zh-CN 默认环境下正确渲染帮助中心顶层标题、标签页与新手上路', () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <HelpWorkbench />
      </I18nProvider>
    )

    // 标题与副标题
    expect(screen.getByRole('heading', { name: '帮助中心' })).toBeInTheDocument()
    expect(screen.getByText('术语解释、操作指南、工作流、常见问题——都在这里。')).toBeInTheDocument()

    // 四大顶层 Tab
    expect(screen.getByRole('tab', { name: '新手上路' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '术语表' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '功能指南' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '常见问题' })).toBeInTheDocument()

    // 默认展示新手上路生态全景与工作流
    expect(screen.getByText('生态全景：数据是怎么流动的')).toBeInTheDocument()
    expect(screen.getByText(/先拆书，再蒸馏，最后用资产辅助写作/)).toBeInTheDocument()
    expect(screen.getByText('四个典型工作流')).toBeInTheDocument()
    expect(screen.getByText('工作流 A：拆一本书')).toBeInTheDocument()
  })

  it('支持无缝切换到术语表、功能指南与常见问题', () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <HelpWorkbench />
      </I18nProvider>
    )

    // 切换到术语表
    fireEvent.click(screen.getByRole('tab', { name: '术语表' }))
    expect(screen.getByPlaceholderText('搜索术语…')).toBeInTheDocument()
    expect(screen.getByText('全部')).toBeInTheDocument()
    expect(screen.getAllByText('概念').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('资产').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('功能').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('声线卡')).toBeInTheDocument()

    // 搜索术语过滤
    const searchInput = screen.getByPlaceholderText('搜索术语…')
    fireEvent.change(searchInput, { target: { value: '桥段' } })
    expect(screen.getByText('桥段')).toBeInTheDocument()

    // 切换到功能指南
    fireEvent.click(screen.getByRole('tab', { name: '功能指南' }))
    expect(screen.getByText('分析拆书')).toBeInTheDocument()
    expect(screen.getByText('蒸馏（高级功能）')).toBeInTheDocument()
    expect(screen.getByText('质量检验')).toBeInTheDocument()

    // 切换到常见问题
    fireEvent.click(screen.getByRole('tab', { name: '常见问题' }))
    expect(screen.getByText('导入 .txt 后没反应？')).toBeInTheDocument()
    expect(screen.getByText('蒸馏和拆书是什么关系？')).toBeInTheDocument()
  })

  it('支持 initialTab 与 initialAnchor 深度锚点联动', () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <HelpWorkbench initialTab="guides" initialAnchor="distill" />
      </I18nProvider>
    )

    // 应直接处于功能指南 Tab 并展开蒸馏指南
    expect(screen.getByText('蒸馏（高级功能）')).toBeInTheDocument()
    expect(screen.getByText('确认可蒸馏')).toBeInTheDocument()
  })

  it('en-US 环境下全量渲染英文标题、标签页、术语表、工作流与功能指南', () => {
    render(
      <I18nProvider initialLocale="en-US">
        <HelpWorkbench />
      </I18nProvider>
    )

    // 英文标题与副标题
    expect(screen.getByRole('heading', { name: 'Help Center' })).toBeInTheDocument()
    expect(screen.getByText('Terminology, user guides, workflows, and FAQs — all in one place.')).toBeInTheDocument()

    // 英文四大 Tab
    expect(screen.getByRole('tab', { name: 'Quick Start' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Glossary' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Feature Guides' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'FAQ' })).toBeInTheDocument()

    // 英文生态全景与工作流
    expect(screen.getByText('Ecosystem Overview: How Data Flows')).toBeInTheDocument()
    expect(screen.getByText(/Analyze first, Distill next, and then power Assisted Writing with assets/)).toBeInTheDocument()
    expect(screen.getByText('Four Canonical Workflows')).toBeInTheDocument()
    expect(screen.getByText('Workflow A: Analyze a Book')).toBeInTheDocument()

    // 切换到英文术语表
    fireEvent.click(screen.getByRole('tab', { name: 'Glossary' }))
    expect(screen.getByPlaceholderText('Search terms…')).toBeInTheDocument()
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getAllByText('Concepts').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Assets').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Features').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Voice Card')).toBeInTheDocument()
    expect(screen.getByText('Structure Observation')).toBeInTheDocument()

    // 切换到英文功能指南
    fireEvent.click(screen.getByRole('tab', { name: 'Feature Guides' }))
    expect(screen.getByText('Book Analysis')).toBeInTheDocument()
    expect(screen.getByText('Distillation (Advanced)')).toBeInTheDocument()
    expect(screen.getByText('Quality Inspection')).toBeInTheDocument()

    // 切换到英文 FAQ
    fireEvent.click(screen.getByRole('tab', { name: 'FAQ' }))
    expect(screen.getByText('Nothing happens after selecting .txt file?')).toBeInTheDocument()
    expect(screen.getByText('What is the relationship between Analysis and Distillation?')).toBeInTheDocument()
  })
})
