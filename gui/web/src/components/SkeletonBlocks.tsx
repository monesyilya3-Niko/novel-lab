// 骨架屏体系：「墨」设计系统 v3 —— 与内容布局对齐的加载占位。
import Box from '@mui/material/Box'
import Skeleton from '@mui/material/Skeleton'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Grid from '@mui/material/Grid'
import { ink } from '../ink'

/** 统一的骨架屏底色（纸墨质感） */
function InkSkeleton(props: React.ComponentProps<typeof Skeleton>) {
  return (
    <Skeleton
      animation="wave"
      {...props}
      sx={{
        bgcolor: 'action.hover',
        ...props.sx,
      }}
    />
  )
}

/** 仪表盘骨架：统计卡片 + 图表区 */
export function DashboardSkeleton() {
  return (
    <Box sx={{ animation: 'fadeIn 0.3s ease both', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[0, 1, 2, 3].map((i) => (
          <Grid item xs={12} sm={6} md={3} key={i}>
            <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
              <CardContent>
                <InkSkeleton variant="text" width="60%" height={20} />
                <InkSkeleton variant="text" width="40%" height={36} sx={{ mt: 1 }} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Grid container spacing={2}>
        <Grid item xs={12} md={8}>
          <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              <InkSkeleton variant="text" width="30%" height={24} sx={{ mb: 2 }} />
              <InkSkeleton variant="rounded" height={220} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              <InkSkeleton variant="text" width="40%" height={24} sx={{ mb: 2 }} />
              {[0, 1, 2, 3].map((i) => (
                <InkSkeleton key={i} variant="text" height={28} sx={{ mb: 1 }} />
              ))}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}

/** 列表骨架：多行条目 */
export function ListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <Box sx={{ animation: 'fadeIn 0.3s ease both', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <InkSkeleton variant="circular" width={36} height={36} />
          <Box sx={{ flex: 1 }}>
            <InkSkeleton variant="text" width={`${70 - (i % 3) * 15}%`} height={20} />
            <InkSkeleton variant="text" width="40%" height={16} />
          </Box>
          <InkSkeleton variant="rounded" width={64} height={28} />
        </Box>
      ))}
    </Box>
  )
}

/** 图表骨架：标题 + 图表区 */
export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', animation: 'fadeIn 0.3s ease both', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      <CardContent>
        <InkSkeleton variant="text" width="35%" height={24} sx={{ mb: 1 }} />
        <InkSkeleton variant="text" width="55%" height={16} sx={{ mb: 2 }} />
        <InkSkeleton variant="rounded" height={height} />
      </CardContent>
    </Card>
  )
}

/** 表单骨架 */
export function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <Box sx={{ animation: 'fadeIn 0.3s ease both', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
      {Array.from({ length: fields }).map((_, i) => (
        <Box key={i} sx={{ mb: 2.5 }}>
          <InkSkeleton variant="text" width="25%" height={18} sx={{ mb: 1 }} />
          <InkSkeleton variant="rounded" height={40} />
        </Box>
      ))}
      <InkSkeleton variant="rounded" width={120} height={36} sx={{ mt: 1 }} />
    </Box>
  )
}

/** 空状态：水墨风品牌占位 */
export function InkEmptyState({
  title,
  hint,
  icon,
}: {
  title: string
  hint?: string
  icon?: React.ReactNode
}) {
  return (
    <Box
      sx={{
        py: 8,
        px: 3,
        textAlign: 'center',
        animation: 'fadeIn 0.4s ease both',
        '@keyframes fadeIn': { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
      }}
    >
      <Box
        sx={{
          width: 72,
          height: 72,
          mx: 'auto',
          mb: 2.5,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'action.hover',
          color: 'text.secondary',
          // 水墨晕染效果
          background: (theme) =>
            theme.palette.mode === 'dark'
              ? `radial-gradient(circle, ${ink.nightCard} 0%, transparent 70%)`
              : `radial-gradient(circle, ${ink.paperDeep} 0%, transparent 70%)`,
        }}
      >
        {icon}
      </Box>
      <Box
        component="div"
        sx={{
          fontFamily: '"Noto Serif SC", serif',
          fontSize: 17,
          fontWeight: 600,
          mb: 1,
          color: 'text.primary',
        }}
      >
        {title}
      </Box>
      {hint && (
        <Box component="div" sx={{ fontSize: 13.5, color: 'text.secondary', maxWidth: 320, mx: 'auto', lineHeight: 1.7 }}>
          {hint}
        </Box>
      )}
    </Box>
  )
}
