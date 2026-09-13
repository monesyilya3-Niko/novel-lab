// 资产库（M4）：只读浏览 —— 分类树 + 详情 + 计数 + 分页。
import { useCallback, useEffect, useMemo, useState } from 'react'
import Box from '@mui/material/Box'
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
import * as api from '../api/client'
import type { AssetItem, AssetKind } from '../types'
import { friendlyError } from '../api/client'

const KIND_LABELS: Record<AssetKind, string> = {
  voice: '声线卡',
  structure: '结构观测',
  commercial: '商业观测',
  craft: '笔法卡',
  genre_pack: '题材包',
  prose_card: '文风卡',
  trope: '桥段',
  report: '报告',
  book: '语料',
}

const ALL_KINDS: AssetKind[] = [
  'voice',
  'structure',
  'commercial',
  'craft',
  'genre_pack',
  'prose_card',
  'trope',
  'report',
  'book',
]

const PAGE_SIZE = 20

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

  const load = useCallback(async (k: AssetKind | null, p: number) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.listAssets(k ?? undefined, (p - 1) * PAGE_SIZE, PAGE_SIZE)
      setItems(res.items)
      setTotal(res.total)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(kind, 1)
    setPage(1)
  }, [kind, load])

  const onSelect = useCallback(async (item: AssetItem) => {
    setSelected(item)
    setDetailLoading(true)
    setDetail(null)
    try {
      const d = await api.getAssetDetail(item.kind, item.id)
      setDetail(d)
    } catch (e) {
      setDetail({ error: friendlyError(e) })
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const pageCount = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total])

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
        资产库
      </Typography>

      <Grid container spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {/* 分类树 + 列表 */}
        <Grid item xs={12} md={5} sx={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <Card variant="outlined" sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Box sx={{ p: 1.5, borderBottom: '1px solid #eee', display: 'flex', flexWrap: 'wrap', gap: 1 }}>
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
            <Box sx={{ p: 1.5, borderTop: '1px solid #eee', display: 'flex', justifyContent: 'center' }}>
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
