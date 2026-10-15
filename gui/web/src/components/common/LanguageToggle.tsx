import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import TranslateIcon from '@mui/icons-material/Translate'
import Box from '@mui/material/Box'
import { useI18n } from '../../state/I18nContext'

export default function LanguageToggle() {
  const { locale, toggleLocale, t } = useI18n()
  const title = t('toggle_language')
  return (
    <Tooltip title={title}>
      <IconButton
        color="inherit"
        size="small"
        onClick={toggleLocale}
        aria-label={title}
        sx={{
          borderRadius: 2,
          px: 0.8,
          gap: 0.5,
          fontSize: '0.8rem',
          fontWeight: 700,
        }}
      >
        <TranslateIcon fontSize="small" />
        <Box component="span" sx={{ fontSize: '0.75rem', fontWeight: 600 }}>
          {locale === 'zh-CN' ? '中' : 'EN'}
        </Box>
      </IconButton>
    </Tooltip>
  )
}
