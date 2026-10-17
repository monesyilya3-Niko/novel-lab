// 分析进度面板：总进度条 + 章×批状态矩阵。
import { useMemo } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import Tooltip from '@mui/material/Tooltip'
import { useApp } from '../state/AppContext'
import { useI18n } from '../state/I18nContext'
import { palette } from '../theme'

const STATUS_I18N_KEYS: Record<string, string> = {
  idle: 'analysis_status_idle',
  pending: 'analysis_status_pending',
  running: 'analysis_status_running',
  success: 'analysis_status_success',
  failed: 'analysis_status_failed',
  skipped: 'analysis_status_skipped',
}

// 批次状态语义色：取自 theme.ts 统一色板；pending 用中性灰（无主题角色，保留）。
const CELL_COLOR: Record<string, string> = {
  pending: '#e0e0e0',
  running: palette.primary,
  success: palette.success,
  failed: palette.error,
  skipped: palette.warning,
}

export default function ProgressPanel() {
  const { t, locale } = useI18n()
  const { book, batchStates, status } = useApp()

  const { done, total } = useMemo(() => {
    if (!book) return { done: 0, total: 0 }
    let d = 0
    let tCount = 0
    for (const ch of book.chapters) {
      tCount += ch.batchCount
      for (let bi = 0; bi < ch.batchCount; bi++) {
        const st = batchStates[`c${ch.index}-b${bi}`]?.status
        if (st === 'success') d++
      }
    }
    return { done: d, total: tCount }
  }, [book, batchStates])

  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  if (!book) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">{t('analysis_need_book')}</Typography>
      </Box>
    )
  }

  const currentStatusLabel = t(STATUS_I18N_KEYS[status?.status ?? 'idle'] ?? 'analysis_status_idle')

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        {t('analysis_prog_title')}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <Box sx={{ flex: 1 }}>
          <LinearProgress variant="determinate" value={pct} sx={{ height: 10, borderRadius: 5 }} />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
          {done} / {total} {t('analysis_batches_unit')} · {pct}%
        </Typography>
      </Box>
      <Typography variant="caption" color="text.secondary">
        {t('analysis_prog_status_current')}：{currentStatusLabel} · {t('analysis_prog_checkpoint')} {status?.cursor || '-'}
      </Typography>

      {/* 章×批矩阵 */}
      <Box sx={{ mt: 3 }}>
        {book.chapters.map((ch) => {
          const cols = Math.max(ch.batchCount, 1)
          return (
            <Box key={ch.index} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" noWrap sx={{ width: 140, flexShrink: 0 }}>
                {t('analysis_chap_prefix')}{ch.index}{t('analysis_chap_suffix')}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                {Array.from({ length: cols }).map((_, bi) => {
                  const key = `c${ch.index}-b${bi}`
                  const st = batchStates[key]?.status ?? 'pending'
                  const statusLabel = t(STATUS_I18N_KEYS[st] ?? 'analysis_status_pending')
                  const tooltipText = locale === 'en-US'
                    ? `Ch.${ch.index} Batch ${bi} · ${statusLabel}`
                    : `第${ch.index}章 第${bi}批 · ${statusLabel}`
                  return (
                    <Tooltip key={bi} title={tooltipText}>
                      <Box
                        sx={{
                          width: 14,
                          height: 14,
                          borderRadius: '3px',
                          bgcolor: CELL_COLOR[st] ?? CELL_COLOR.pending,
                        }}
                      />
                    </Tooltip>
                  )
                })}
              </Box>
            </Box>
          )
        })}
      </Box>

      {/* 图例 */}
      <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
        {(['pending', 'running', 'success', 'failed', 'skipped'] as const).map((s) => (
          <Box key={s} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 12, height: 12, borderRadius: '3px', bgcolor: CELL_COLOR[s] }} />
            <Typography variant="caption" color="text.secondary">
              {t(STATUS_I18N_KEYS[s] ?? s)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  )
}
