// 导入面板：拖拽 / 选文件（txt），经 multipart 上传到后端。
import { useCallback, useEffect, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import { useApp } from '../state/AppContext'
import { listSamples, type SampleInfo } from '../api/client'
import { useI18n } from '../state/I18nContext'

interface Props {
  compact?: boolean
}

export default function ImportPanel({ compact }: Props) {
  const { t } = useI18n()
  const { uploadBook, book } = useApp()
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const doUpload = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith('.txt')) {
        setError(t('analysis_import_only_txt'))
        return
      }
      setLoading(true)
      setError(null)
      try {
        await uploadBook(file)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    },
    [uploadBook, t],
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (!file) return
      void doUpload(file)
    },
    [doUpload],
  )

  const onPick = useCallback(() => {
    fileInput.current?.click()
  }, [])

  const onFileChosen = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) void doUpload(file)
      e.target.value = ''
    },
    [doUpload],
  )

  return (
    <Box sx={{ p: compact ? 1.5 : 3 }}>
      <input
        ref={fileInput}
        type="file"
        accept=".txt"
        style={{ display: 'none' }}
        onChange={onFileChosen}
      />
      <Box
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        sx={{
          border: '2px dashed',
          borderColor: dragging ? 'primary.main' : 'divider',
          borderRadius: 2,
          p: compact ? 2 : 4,
          textAlign: 'center',
          bgcolor: dragging ? 'rgba(25,118,210,0.06)' : 'transparent',
          cursor: 'pointer',
        }}
        onClick={onPick}
      >
        {loading ? (
          <CircularProgress size={24} />
        ) : (
          <>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {t('analysis_import_title')}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {t('analysis_import_drag_hint')}
            </Typography>
          </>
        )}
      </Box>
      {!compact && (
        <Box sx={{ mt: 2 }}>
          <Button variant="contained" onClick={onPick} disabled={loading} fullWidth>
            {t('analysis_import_btn_pick')}
          </Button>
        </Box>
      )}
      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {book && (
        <Alert severity="success" sx={{ mt: 1.5 }}>
          {t('analysis_import_success_prefix')}{book.title}{t('analysis_import_success_middle')}{book.totalChapters}{t('analysis_import_success_suffix')}
        </Alert>
      )}
      {/* 内置示例语料：一键导入试手 */}
      <SampleList onImported={() => setError(null)} />
    </Box>
  )
}

/** 内置示例语料列表（一键导入）。 */
function SampleList({ onImported }: { onImported: () => void }) {
  const { t, locale } = useI18n()
  const { importSampleBook } = useApp()
  const [samples, setSamples] = useState<SampleInfo[] | null>(null)
  const [importing, setImporting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listSamples()
      .then(list => { if (!cancelled) setSamples(list) })
      .catch(() => { if (!cancelled) setSamples([]) })
    return () => { cancelled = true }
  }, [])

  const doImportSample = async (name: string) => {
    setImporting(name)
    setError(null)
    try {
      // 走 AppContext：导入后切换当前书并触发成功提示（与文件上传同一路径）。
      await importSampleBook(name)
      onImported()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setImporting(null)
    }
  }

  if (!samples || samples.length === 0) return null

  return (
    <Box sx={{ mt: 3 }}>
      <Divider sx={{ mb: 2 }} />
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, flex: 1 }}>
          📦 {t('analysis_sample_title')} <Typography component="span" variant="caption" color="text.secondary">{t('analysis_sample_subtitle')}</Typography>
        </Typography>
        <ContextHelpButton guideKey="analysis" title={t('analysis_sample_help_title')} />
      </Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {samples.map(s => (
          <Chip
            key={s.name}
            label={`${s.genre} · ${s.chapters} ${locale === 'en-US' ? 'ch.' : '章'}`}
            clickable
            disabled={importing !== null}
            onClick={() => void doImportSample(s.name)}
            icon={importing === s.name ? <CircularProgress size={14} /> : undefined}
            variant="outlined"
            sx={{ '&:hover': { borderColor: 'primary.main' } }}
          />
        ))}
      </Box>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
    </Box>
  )
}
