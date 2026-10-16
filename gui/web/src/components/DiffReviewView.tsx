// 双栏对比审校视图（Side-by-Side Review & Diff View）
import { useState } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import Tooltip from '@mui/material/Tooltip'
import { useThemeMode } from '../state/ThemeModeContext'
import { useI18n } from '../state/I18nContext'
import { ink } from '../ink'

export interface DiffReviewViewProps {
  originalText: string
  polishedText: string
  onAccept?: (acceptedText: string) => void
  onReject?: () => void
}

export default function DiffReviewView({
  originalText,
  polishedText,
  onAccept,
  onReject,
}: DiffReviewViewProps) {
  const { isDark } = useThemeMode()
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)

  const origParas = originalText.split('\n').filter((p) => p.trim())
  const polishParas = polishedText.split('\n').filter((p) => p.trim())
  const maxParas = Math.max(origParas.length, polishParas.length)

  const handleCopy = () => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(polishedText).catch(() => {})
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
      {/* 顶栏操作 */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <CompareArrowsIcon sx={{ color: 'primary.main' }} />
          <Typography variant="subtitle1" fontWeight={700}>
            {t('diff_title')}
          </Typography>
          <Chip
            label={`${t('diff_orig_prefix')} ${origParas.length} ${t('diff_paras_unit')} / ${t('diff_polish_prefix')} ${polishParas.length} ${t('diff_paras_unit')}`}
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title={copied ? t('diff_copied') : t('diff_copy_btn')}>
            <Button size="small" variant="outlined" startIcon={<ContentCopyIcon />} onClick={handleCopy}>
              {copied ? t('diff_copied') : t('diff_copy_btn')}
            </Button>
          </Tooltip>
          {onReject && (
            <Button size="small" color="inherit" onClick={onReject}>
              {t('diff_reject_btn')}
            </Button>
          )}
          {onAccept && (
            <Button size="small" variant="contained" startIcon={<CheckCircleOutlineIcon />} onClick={() => onAccept(polishedText)}>
              {t('diff_accept_btn')}
            </Button>
          )}
        </Box>
      </Box>

      {/* 双栏对比区 */}
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0, gap: 2, overflow: 'hidden' }}>
        {/* 左栏：原稿 */}
        <Paper
          elevation={0}
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: `1px solid ${isDark ? ink.nightLine : ink.hairline}`,
            borderRadius: 2,
            bgcolor: isDark ? ink.nightCard : '#FAFBFD',
          }}
        >
          <Box sx={{ py: 1, px: 2, borderBottom: `1px solid ${isDark ? ink.nightLine : ink.hairline}`, bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' }}>
            <Typography variant="subtitle2" color="text.secondary" fontWeight={600}>
              {t('diff_orig_header')}
            </Typography>
          </Box>
          <Box sx={{ flex: 1, overflow: 'auto', p: 2.5, lineHeight: 1.8, fontSize: 14 }}>
            {Array.from({ length: maxParas }).map((_, idx) => {
              const p = origParas[idx] ?? ''
              const isDiff = p !== (polishParas[idx] ?? '')
              return (
                <Box
                  key={idx}
                  sx={{
                    mb: 1.5,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: isDiff ? (isDark ? 'rgba(220, 38, 38, 0.08)' : 'rgba(254, 226, 226, 0.45)') : 'transparent',
                    borderLeft: isDiff ? '3px solid #DC2626' : '3px solid transparent',
                    color: isDark ? ink.moonWhite : ink.text,
                  }}
                >
                  {p || <Typography variant="caption" color="text.secondary">{t('diff_empty_para')}</Typography>}
                </Box>
              )
            })}
          </Box>
        </Paper>

        {/* 右栏：润色后 */}
        <Paper
          elevation={0}
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: `1px solid ${isDark ? ink.nightLine : ink.hairline}`,
            borderRadius: 2,
            bgcolor: isDark ? ink.nightCard : '#FFFFFF',
          }}
        >
          <Box sx={{ py: 1, px: 2, borderBottom: `1px solid ${isDark ? ink.nightLine : ink.hairline}`, bgcolor: isDark ? 'rgba(37,99,235,0.06)' : 'rgba(37,99,235,0.04)' }}>
            <Typography variant="subtitle2" color="primary.main" fontWeight={600}>
              {t('diff_polish_header')}
            </Typography>
          </Box>
          <Box sx={{ flex: 1, overflow: 'auto', p: 2.5, lineHeight: 1.8, fontSize: 14 }}>
            {Array.from({ length: maxParas }).map((_, idx) => {
              const p = polishParas[idx] ?? ''
              const isDiff = p !== (origParas[idx] ?? '')
              return (
                <Box
                  key={idx}
                  sx={{
                    mb: 1.5,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: isDiff ? (isDark ? 'rgba(22, 163, 74, 0.12)' : 'rgba(220, 252, 231, 0.55)') : 'transparent',
                    borderLeft: isDiff ? '3px solid #16A34A' : '3px solid transparent',
                    color: isDark ? ink.moonWhite : ink.text,
                  }}
                >
                  {p || <Typography variant="caption" color="text.secondary">{t('diff_empty_para')}</Typography>}
                </Box>
              )
            })}
          </Box>
        </Paper>
      </Box>
    </Box>
  )
}
