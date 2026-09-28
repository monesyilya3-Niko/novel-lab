// 工作台切换过渡：淡入 + 轻微上移动效。「墨」设计系统 v3。
// 用法：<WorkbenchTransition key={workbenchKey}>...</WorkbenchTransition>
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'

export default function WorkbenchTransition({
  children,
}: {
  children: React.ReactNode
}) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const t = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(t)
  }, [])

  return (
    <Box
      sx={{
        height: '100%',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(10px)',
        transition: 'opacity 0.25s ease, transform 0.28s cubic-bezier(0.2, 0.9, 0.25, 1)',
      }}
    >
      {children}
    </Box>
  )
}
