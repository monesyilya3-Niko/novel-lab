import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Skeleton from '@mui/material/Skeleton'
import Typography from '@mui/material/Typography'
import type { ReactNode } from 'react'
import { friendlyError } from '../../api/client'

export interface AsyncBoundaryProps {
  loading: boolean
  error: unknown
  /** 有数据但为空时展示引导态（不传则空态由调用方自行处理） */
  empty?: boolean
  emptyTitle?: string
  emptyHint?: string
  emptyCta?: { label: string; onClick: () => void }
  onRetry?: () => void
  /** 骨架屏最小高度，减少布局抖动 */
  minHeight?: number
  children: ReactNode
}

/**
 * 数据加载四态统一出口（模式参考 react-admin）：
 * skeleton → error（中文文案 + 重试）→ empty（引导 CTA）→ data。
 *
 * 优先级：loading > error > empty > data。
 * 错误文案经 friendlyError 归一——调用方不再手写 CircularProgress/Alert 组合。
 */
export default function AsyncBoundary({
  loading,
  error,
  empty = false,
  emptyTitle = '暂无数据',
  emptyHint,
  emptyCta,
  onRetry,
  minHeight = 240,
  children,
}: AsyncBoundaryProps) {
  if (loading) {
    return (
      <Box sx={{ p: 2, minHeight }} data-testid="async-skeleton">
        <Skeleton variant="text" width="30%" height={32} />
        <Skeleton variant="text" width="90%" />
        <Skeleton variant="text" width="80%" />
        <Skeleton variant="rectangular" width="100%" height={minHeight / 3} sx={{ mt: 2 }} />
        <Skeleton variant="rectangular" width="65%" height={minHeight / 3} sx={{ mt: 1 }} />
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ p: 2, minHeight }} data-testid="async-error">
        <Alert
          severity="error"
          action={
            onRetry && (
              <Button color="inherit" size="small" onClick={onRetry}>
                重试
              </Button>
            )
          }
        >
          {friendlyError(error)}
        </Alert>
      </Box>
    )
  }

  if (empty) {
    return (
      <Box
        sx={{
          p: 4,
          minHeight,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 1,
        }}
        data-testid="async-empty"
      >
        <Typography variant="subtitle1">{emptyTitle}</Typography>
        {emptyHint && (
          <Typography variant="body2" color="text.secondary">
            {emptyHint}
          </Typography>
        )}
        {emptyCta && (
          <Button variant="contained" size="small" onClick={emptyCta.onClick} sx={{ mt: 1 }}>
            {emptyCta.label}
          </Button>
        )}
      </Box>
    )
  }

  return <>{children}</>
}
