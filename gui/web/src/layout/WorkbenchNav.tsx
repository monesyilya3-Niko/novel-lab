// 左侧导航栏：工作台切换（含状态徽标）。
import React from 'react'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Badge from '@mui/material/Badge'
import Tooltip from '@mui/material/Tooltip'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import HomeIcon from '@mui/icons-material/Home'
import InsightsIcon from '@mui/icons-material/Insights'
import EditNoteIcon from '@mui/icons-material/EditNote'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import SettingsIcon from '@mui/icons-material/Settings'
import TuneIcon from '@mui/icons-material/Tune'

export type WorkbenchKey =
  | 'home'
  | 'analysis'
  | 'writing'
  | 'quality'
  | 'assets'
  | 'system'
  | 'settings'

export interface WorkbenchNavItem {
  key: WorkbenchKey
  label: string
  icon: React.ReactNode
  /** 建设中占位（阶段一：写作/质检/系统/设置）。 */
  placeholder?: boolean
  /** 状态徽标数（可选）。 */
  badge?: number
}

const NAV_ITEMS: WorkbenchNavItem[] = [
  { key: 'home', label: '首页', icon: <HomeIcon /> },
  { key: 'analysis', label: '分析', icon: <InsightsIcon /> },
  { key: 'writing', label: '写作', icon: <EditNoteIcon />, placeholder: true },
  { key: 'quality', label: '质检', icon: <FactCheckIcon />, placeholder: true },
  { key: 'assets', label: '资产库', icon: <FolderOpenIcon /> },
  { key: 'system', label: '系统', icon: <TuneIcon />, placeholder: true },
  { key: 'settings', label: '设置', icon: <SettingsIcon />, placeholder: true },
]

export interface WorkbenchNavProps {
  active: WorkbenchKey
  onChange: (key: WorkbenchKey) => void
  /** 各工作台徽标（key → number）。 */
  badges?: Partial<Record<WorkbenchKey, number>>
}

export default function WorkbenchNav({ active, onChange, badges }: WorkbenchNavProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Typography
        variant="caption"
        sx={{ px: 2, pt: 1.5, pb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: 0.5 }}
      >
        工作台
      </Typography>
      <List component="nav" disablePadding sx={{ px: 1 }}>
        {NAV_ITEMS.map((item) => {
          const selected = active === item.key
          const badge = badges?.[item.key]
          const content = (
            <ListItemButton
              selected={selected}
              onClick={() => onChange(item.key)}
              sx={{
                borderRadius: 1.5,
                mb: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '& .MuiListItemIcon-root': { color: 'primary.contrastText' },
                  '&:hover': { bgcolor: 'primary.dark' },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: selected ? 'inherit' : 'text.secondary' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontSize: 14, fontWeight: selected ? 600 : 400 }}
              />
              {badge !== undefined && badge > 0 && (
                <Badge badgeContent={badge} color="secondary" sx={{ mr: 1 }} />
              )}
            </ListItemButton>
          )
          return item.placeholder ? (
            <Tooltip key={item.key} title="建设中" placement="right">
              <Box>{content}</Box>
            </Tooltip>
          ) : (
            <React.Fragment key={item.key}>{content}</React.Fragment>
          )
        })}
      </List>
    </Box>
  )
}
