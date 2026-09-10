// 「建设中」占位页（阶段一：写作/质检/系统/设置）。
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import ConstructionIcon from '@mui/icons-material/Construction'

export interface PlaceholderProps {
  title: string
  description?: string
}

export default function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1.5,
        color: 'text.secondary',
      }}
    >
      <ConstructionIcon sx={{ fontSize: 48, opacity: 0.4 }} />
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {description ?? '该模块将在后续阶段上线，敬请期待'}
      </Typography>
    </Box>
  )
}
