// 一键分析控制条：题材下拉（必填，来自 /api/genres）+ 「一键分析」按钮 + 任务状态。
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import CircularProgress from '@mui/material/CircularProgress'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import { useApp } from '../state/AppContext'
import { getGenres } from '../api/client'
import { useI18n } from '../state/I18nContext'
import type { TaskStatus } from '../types'

const STATUS_KEYS: Record<TaskStatus, string> = {
  idle: 'analysis_status_idle',
  running: 'analysis_status_running',
  paused: 'analysis_status_paused',
  done: 'analysis_status_done',
  error: 'analysis_status_error',
}

const STATUS_COLOR: Record<TaskStatus, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  idle: 'default',
  running: 'primary',
  paused: 'warning',
  done: 'success',
  error: 'error',
}

export interface AnalysisControlBarProps {
  /** 一键分析完成后回调（切到结果页）。 */
  onGoResult: () => void
}

export default function AnalysisControlBar({ onGoResult }: AnalysisControlBarProps) {
  const { t } = useI18n()
  const { book, status, runFullAnalysis } = useApp()
  const [genres, setGenres] = useState<string[]>([])
  const [genre, setGenre] = useState('')
  const [busy, setBusy] = useState(false)
  const [errorKey, setErrorKey] = useState<string | null>(null)
  const [rawError, setRawError] = useState<string | null>(null)

  // P0-4：题材列表来自后端注册表（与后端校验同源），必填，无"未知"默认值。
  useEffect(() => {
    let cancelled = false
    getGenres()
      .then((list) => {
        if (cancelled) return
        setGenres(list)
        // P0-4：不自动选中，用户必须显式选择题材（必填）
      })
      .catch(() => {
        if (!cancelled) setErrorKey('analysis_err_load_genres')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const taskStatus: TaskStatus = status?.status ?? 'idle'
  const isRunning = taskStatus === 'running'

  const doRun = async () => {
    if (!genre) {
      setErrorKey('analysis_err_select_genre')
      return
    }
    setBusy(true)
    setErrorKey(null)
    setRawError(null)
    try {
      await runFullAnalysis(genre)
      onGoResult()
    } catch (e) {
      setRawError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const errorMessage = errorKey ? t(errorKey) : rawError

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', py: 0.5 }}>
      {status && (
        <Chip size="small" label={t(STATUS_KEYS[taskStatus] ?? 'analysis_status_idle')} color={STATUS_COLOR[taskStatus]} />
      )}
      {status && (status.done > 0 || status.total > 0) && (
        <Typography variant="caption" color="text.secondary">
          {status.done}/{status.total} {t('analysis_batches_unit')}
        </Typography>
      )}

      {!book ? (
        <Typography variant="caption" color="text.secondary">
          {t('analysis_need_book')}
        </Typography>
      ) : (
        <>
          <FormControl size="small" sx={{ minWidth: 150 }} required>
            <InputLabel id="genre-select-label">{t('analysis_genre_label')}</InputLabel>
            <Select
              labelId="genre-select-label"
              value={genre}
              label={t('analysis_genre_label')}
              onChange={(e) => setGenre(e.target.value)}
              sx={{ fontSize: 13 }}
            >
              {genres.map((g) => (
                <MenuItem key={g} value={g} sx={{ fontSize: 13 }}>
                  {g}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="contained"
            size="small"
            disabled={busy || isRunning || !genre}
            onClick={doRun}
            startIcon={busy ? <CircularProgress size={14} color="inherit" /> : undefined}
          >
            {isRunning ? t('analysis_btn_running') : t('analysis_btn_start')}
          </Button>
        </>
      )}

      {errorMessage && (
        <Typography variant="caption" color="error.main">
          {errorMessage}
        </Typography>
      )}
    </Box>
  )
}
