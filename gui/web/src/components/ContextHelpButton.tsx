// 上下文帮助按钮：点击跳转到帮助中心对应功能指南。
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { useAppOptional } from '../state/AppContext'

interface ContextHelpButtonProps {
  /** 对应功能指南的 key（见 HelpWorkbench GUIDES），如 'analysis' */
  guideKey: string
  /** 提示文字 */
  title?: string
}

export default function ContextHelpButton({ guideKey, title }: ContextHelpButtonProps) {
  // 单元测试中面板可能脱离 AppProvider 独立渲染，此时按钮静默不跳转。
  const app = useAppOptional()

  const handleClick = () => {
    // 跳转到帮助中心「功能指南」页签，并直接展开对应指南。
    app?.openHelp('guides', guideKey)
  }

  return (
    <Tooltip title={title || '查看此功能的使用指南'}>
      <IconButton
        size="small"
        onClick={handleClick}
        aria-label="查看帮助"
        sx={{ color: 'text.secondary' }}
      >
        <HelpOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  )
}
