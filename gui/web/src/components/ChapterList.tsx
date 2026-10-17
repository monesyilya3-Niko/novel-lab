// 章节列表面板：卷→章→批，状态徽标。
import { useCallback } from 'react'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import { useApp } from '../state/AppContext'
import { useI18n } from '../state/I18nContext'

export default function ChapterList() {
  const { t } = useI18n()
  const { book, selectedChapter, selectChapter, batchStates } = useApp()

  const chapterStatus = useCallback(
    (chapterIndex: number, batchCount: number): { label: string; color: string } => {
      let success = 0
      let failed = 0
      let running = 0
      for (let bi = 0; bi < batchCount; bi++) {
        const st = batchStates[`c${chapterIndex}-b${bi}`]?.status ?? 'pending'
        if (st === 'success') success++
        else if (st === 'failed') failed++
        else if (st === 'running') running++
      }
      if (failed > 0 && success + failed === batchCount && running === 0) {
        return { label: t('analysis_chap_status_failed'), color: 'red' }
      }
      if (success === batchCount && batchCount > 0) return { label: t('analysis_chap_status_done'), color: 'green' }
      if (success > 0 || running > 0) return { label: t('analysis_chap_status_partial'), color: 'orange' }
      return { label: t('analysis_chap_status_pending'), color: 'gray' }
    },
    [batchStates, t],
  )

  if (!book) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          {t('analysis_chap_not_imported')}
        </Typography>
      </Box>
    )
  }

  return (
    <List dense sx={{ width: '100%' }}>
      {book.chapters.map((ch) => {
        const st = chapterStatus(ch.index, ch.batchCount)
        return (
          <ListItemButton
            key={ch.index}
            selected={selectedChapter === ch.index}
            onClick={() => selectChapter(ch.index)}
            sx={{ alignItems: 'flex-start' }}
          >
            <ListItemText
              primary={
                <Typography variant="body2" noWrap>
                  {t('analysis_chap_prefix')}{ch.index}{t('analysis_chap_suffix')} {ch.title.replace(/^第[一二三四五六七八九十百千零0-9]+[章回节卷]\s*/, '')}
                </Typography>
              }
              secondary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                  <Chip
                    size="small"
                    label={`${st.label}`}
                    sx={{
                      bgcolor: st.color,
                      color: 'common.white',
                      height: 18,
                      fontSize: 11,
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {ch.batchCount} {t('analysis_batches_unit')}
                  </Typography>
                </Box>
              }
            />
          </ListItemButton>
        )
      })}
    </List>
  )
}
