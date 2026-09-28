// 上下文帮助按钮：点击跳转到帮助中心对应功能指南。
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { useApp } from '../state/AppContext'

interface ContextHelpButtonProps {
  /** 对应功能指南的 key（见 HelpWorkbench GUIDES），如 'analysis' */
  guideKey: string
  /** 提示文字 */
  title?: string
}

export default function ContextHelpButton({ title }: ContextHelpButtonProps) {
  const { setWorkbench } = useApp()

  const handleClick = () => {
    // 跳转到帮助中心。HelpWorkbench 通过 initialAnchor 展开对应指南。
    // 由于 AppContext 暂不支持传参，这里先跳转到帮助中心的功能指南页。
    setWorkbench('help')
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
