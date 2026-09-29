// InlineGuide：在功能旁边直接展示的就地说明（不跳转帮助中心）。
// 设计：默认一行"这个功能做什么"，点击展开看步骤/示例/注意事项。
import { useState } from 'react'
import Box from '@mui/material/Box'
import Collapse from '@mui/material/Collapse'
import IconButton from '@mui/material/IconButton'
import Typography from '@mui/material/Typography'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { ink } from '../ink'

interface InlineGuideProps {
  /** 一句话：这个功能是做什么的 */
  what: string
  /** 操作步骤 */
  steps?: string[]
  /** 注意事项 */
  tips?: string[]
  /** 输入示例（如"写作要点"怎么写） */
  example?: string
  /** 默认展开 */
  defaultOpen?: boolean
}

export default function InlineGuide({ what, steps, tips, example, defaultOpen = false }: InlineGuideProps) {
  const [open, setOpen] = useState(defaultOpen)
  const hasDetail = (steps?.length ?? 0) > 0 || (tips?.length ?? 0) > 0 || !!example
  return (
    <Box
      sx={{
        mb: 2,
        border: `1px solid ${ink.hairline}`,
        borderRadius: 2,
        backgroundColor: ink.bg,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 1 }}>
        <InfoOutlinedIcon sx={{ fontSize: 18, color: ink.accent, flexShrink: 0 }} />
        <Typography variant="body2" sx={{ flex: 1, color: ink.textSecondary }}>
          {what}
        </Typography>
        {hasDetail && (
          <IconButton
            size="small"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? '收起说明' : '展开说明'}
            sx={{
              transform: open ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.2s',
              color: ink.textTertiary,
            }}
          >
            <ExpandMoreIcon fontSize="small" />
          </IconButton>
        )}
      </Box>
      {hasDetail && (
        <Collapse in={open}>
          <Box sx={{ px: 1.5, pb: 1.5, pt: 0.5, borderTop: `1px dashed ${ink.hairline}` }}>
            {steps && steps.length > 0 && (
              <Box component="ol" sx={{ m: 0, pl: 2.5, mb: tips || example ? 1 : 0 }}>
                {steps.map((s, i) => (
                  <Typography component="li" variant="body2" key={i} sx={{ color: ink.textSecondary, mb: 0.5 }}>
                    {s}
                  </Typography>
                ))}
              </Box>
            )}
            {example && (
              <Box sx={{ mt: 1, p: 1.2, borderRadius: 1.5, backgroundColor: ink.surface, border: `1px solid ${ink.hairline}` }}>
                <Typography variant="caption" sx={{ color: ink.textTertiary, display: 'block', mb: 0.5 }}>
                  示例
                </Typography>
                <Typography variant="body2" sx={{ color: ink.text, whiteSpace: 'pre-wrap' }}>
                  {example}
                </Typography>
              </Box>
            )}
            {tips && tips.length > 0 && (
              <Box sx={{ mt: 1 }}>
                {tips.map((t, i) => (
                  <Typography variant="caption" key={i} sx={{ display: 'block', color: ink.textTertiary, mb: 0.4 }}>
                    ※ {t}
                  </Typography>
                ))}
              </Box>
            )}
          </Box>
        </Collapse>
      )}
    </Box>
  )
}
