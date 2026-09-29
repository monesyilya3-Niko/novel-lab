// 资产库（M4）：只读浏览 —— 分类树 + 详情 + 计数 + 分页。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Chip from '@mui/material/Chip'
import Pagination from '@mui/material/Pagination'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import * as api from '../api/client'
import type { AssetItem, AssetKind } from '../types'
import { KIND_LABELS } from '../assetKindLabels'
import { friendlyError } from '../api/client'

const ALL_KINDS: AssetKind[] = [
  'voice',
  'structure',
  'commercial',
  'craft',
  'genre_pack',
  'prose_card',
  'distilled',
  'prose_card_index',
  'trope',
  'report',
  'book',
]

const PAGE_SIZE = 20

/** 资产中文摘要渲染：后端 describe_asset() 生成的 markdown（# 标题 / ## 分节 / - 列表）。 */
function SummaryView({ text }: { text: string }) {
  const blocks = useMemo(() => {
    type Block =
      | { type: 'section'; text: string }
      | { type: 'para'; text: string }
      | { type: 'bullets'; items: string[] }
    const out: Block[] = []
    let bullets: string[] = []
    const flush = () => {
      if (bullets.length > 0) {
        out.push({ type: 'bullets', items: bullets })
        bullets = []
      }
    }
    for (const raw of text.split('\n')) {
      const line = raw.trim()
      if (!line) {
        flush()
        continue
      }
      if (line.startsWith('## ')) {
        flush()
        out.push({ type: 'section', text: line.slice(3) })
      } else if (line.startsWith('# ')) {
        flush() // 标题已在详情头显示，此处跳过
      } else if (line.startsWith('- ')) {
        bullets.push(line.slice(2))
      } else {
        flush()
        out.push({ type: 'para', text: line })
      }
    }
    flush()
    return out
  }, [text])

  return (
    <Box>
      {blocks.map((b, i) => {
        if (b.type === 'section') {
          return (
            <Typography key={i} variant="subtitle2" sx={{ fontWeight: 700, mt: 2, mb: 0.5 }}>
              {b.text}
            </Typography>
          )
        }
        if (b.type === 'bullets') {
          return (
            <Box key={i} sx={{ mb: 0.5 }}>
              {b.items.map((it, j) => {
                const sep = it.indexOf('：')
                return (
                  <Typography key={j} variant="body2" sx={{ mb: 0.3, lineHeight: 1.7 }}>
                    <Box component="span" sx={{ color: 'text.secondary' }}>· </Box>
                    {sep > 0 ? (
                      <>
                        <Box component="span" sx={{ fontWeight: 600 }}>{it.slice(0, sep)}</Box>
                        {it.slice(sep)}
                      </>
                    ) : (
                      it
                    )}
                  </Typography>
                )
              })}
            </Box>
          )
        }
        return (
          <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 1, lineHeight: 1.7 }}>
            {b.text}
          </Typography>
        )
      })}
    </Box>
  )
}

export default function AssetLibrary() {
  const [kind, setKind] = useState<AssetKind | null>(null)
  const [items, setItems] = useState<AssetItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<AssetItem | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  // B10/B11：序列守卫，防止旧响应覆盖新状态。
  const loadSeq = useRef(0)
  const detailSeq = useRef(0)

  const load = useCallback(async (k: AssetKind | null, p: number) => {
    const seq = ++loadSeq.current
    setLoading(true)
    setError('')
    try {
      const res = await api.listAssets(k ?? undefined, (p - 1) * PAGE_SIZE, PAGE_SIZE)
      if (seq !== loadSeq.current) return // 旧响应丢弃
      setItems(res.items)
      setTotal(res.total)
    } catch (e) {
      if (seq !== loadSeq.current) return
      setError(friendlyError(e))
    } finally {
      if (seq === loadSeq.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(kind, 1)
    setPage(1)
  }, [kind, load])

  const onSelect = useCallback(async (item: AssetItem) => {
    const seq = ++detailSeq.current
    setSelected(item)
    setDetailLoading(true)
    setDetail(null)
    try {
      const d = await api.getAssetDetail(item.kind, item.id)
      if (seq !== detailSeq.current) return // 旧响应丢弃
      setDetail(d)
    } catch (e) {
      if (seq !== detailSeq.current) return
      setDetail({ error: friendlyError(e) })
    } finally {
      if (seq === detailSeq.current) setDetailLoading(false)
    }
  }, [])

  const pageCount = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total])

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, flex: 1 }}>
          资产库
        </Typography>
        <ContextHelpButton guideKey="assets" />
      </Box>

      <Grid container spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {/* 分类树 + 列表 */}
        <Grid item xs={12} md={5} sx={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Card variant="outlined" sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip
                label="全部"
                variant={kind === null ? 'filled' : 'outlined'}
                color={kind === null ? 'primary' : 'default'}
                onClick={() => setKind(null)}
              />
              {ALL_KINDS.map((k) => (
                <Chip
                  key={k}
                  label={KIND_LABELS[k]}
                  variant={kind === k ? 'filled' : 'outlined'}
                  color={kind === k ? 'primary' : 'default'}
                  onClick={() => setKind(k)}
                />
              ))}
            </Box>
            <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              {error ? (
                <Typography variant="body2" color="error" sx={{ p: 3, textAlign: 'center' }}>
                  加载失败：{error}
                </Typography>
              ) : loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : items.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ p: 3, textAlign: 'center' }}>
                  暂无资产
                </Typography>
              ) : (
                <List dense disablePadding>
                  {items.map((it) => (
                    <ListItemButton
                      key={it.id}
                      selected={selected?.id === it.id}
                      onClick={() => onSelect(it)}
                    >
                      <ListItemText
                        primary={it.name}
                        secondary={`${KIND_LABELS[it.kind]} · ${(it.size / 1024).toFixed(1)} KB`}
                        primaryTypographyProps={{ fontSize: 14 }}
                      />
                    </ListItemButton>
                  ))}
                </List>
              )}
            </Box>
            <Box sx={{ p: 1.5, borderTop: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'center' }}>
              <Pagination
                count={pageCount}
                page={page}
                onChange={(_e, v) => {
                  setPage(v)
                  load(kind, v)
                }}
                size="small"
              />
            </Box>
          </Card>
        </Grid>

        {/* 详情 */}
        <Grid item xs={12} md={7} sx={{ minHeight: 0 }}>
          <Card variant="outlined" sx={{ height: '100%', overflow: 'auto' }}>
            <CardContent>
              {!selected ? (
                <Typography variant="body2" color="text.secondary" sx={{ p: 4, textAlign: 'center' }}>
                  从左侧选择一个资产查看详情
                </Typography>
              ) : detailLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : (
                <>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {selected.name}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, mt: 0.5, mb: 1 }}>
                    <Chip label={KIND_LABELS[selected.kind]} size="small" color="primary" />
                    <Chip label={selected.path} size="small" variant="outlined" />
                  </Box>
                  <Divider sx={{ mb: 1.5 }} />
                  {detail && detail.markdown ? (
                    <Typography
                      component="pre"
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0 }}
                    >
                      {String(detail.markdown)}
                    </Typography>
                  ) : detail && detail.preview ? (
                    <Typography
                      component="pre"
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', m: 0 }}
                    >
                      {String(detail.preview)}
                    </Typography>
                  ) : detail && detail.summary ? (
                    <>
                      <SummaryView text={String(detail.summary)} />
                      {/* key 按资产隔离：切换资产时折叠状态重置，不会把上一个资产的展开态带过来 */}
                      <Accordion key={selected.id} sx={{ mt: 2 }} disableGutters>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Typography variant="body2" color="text.secondary">
                            高级 · 查看原始数据
                          </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                          <Typography
                            component="pre"
                            variant="body2"
                            sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, m: 0 }}
                          >
                            {JSON.stringify(detail.content ?? {}, null, 2)}
                          </Typography>
                        </AccordionDetails>
                      </Accordion>
                    </>
                  ) : (
                    <Typography
                      component="pre"
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, m: 0 }}
                    >
                      {JSON.stringify(detail ?? {}, null, 2)}
                    </Typography>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
