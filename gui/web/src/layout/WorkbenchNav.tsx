// 左侧导航栏：工作台切换（含状态徽标）。「墨」设计系统 v2。
import React from 'react'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Divider from '@mui/material/Divider'
import HomeIcon from '@mui/icons-material/Home'
import InsightsIcon from '@mui/icons-material/Insights'
import EditNoteIcon from '@mui/icons-material/EditNote'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import SettingsIcon from '@mui/icons-material/Settings'
import TuneIcon from '@mui/icons-material/Tune'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import { ink } from '../ink'

export type WorkbenchKey =
  | 'home'
  | 'analysis'
  | 'writing'
  | 'quality'
  | 'assets'
  | 'advanced'
  | 'system'
  | 'settings'
  | 'admin'

export interface WorkbenchNavItem {
  key: WorkbenchKey
  label: string
  icon: React.ReactNode
  /** 建设中占位（阶段一：写作/质检/系统/设置）。 */
  /** 状态徽标数（可选）。 */
}

const NAV_GROUPS: { title: string; items: WorkbenchNavItem[] }[] = [
  {
    title: '创作',
    items: [
      { key: 'home', label: '首页', icon: <HomeIcon /> },
      { key: 'analysis', label: '分析拆书', icon: <InsightsIcon /> },
      { key: 'writing', label: '辅助写作', icon: <EditNoteIcon /> },
      { key: 'quality', label: '质量检验', icon: <FactCheckIcon /> },
      { key: 'assets', label: '资产库', icon: <FolderOpenIcon /> },
      { key: 'advanced', label: '高级功能', icon: <AutoAwesomeIcon /> },
    ],
  },
  {
    title: '管理',
    items: [
      { key: 'system', label: '系统', icon: <TuneIcon /> },
      { key: 'settings', label: '设置', icon: <SettingsIcon /> },
      { key: 'admin', label: '管理后台', icon: <AdminPanelSettingsIcon /> },
    ],
  },
]

export interface WorkbenchNavProps {
  active: WorkbenchKey
  onChange: (key: WorkbenchKey) => void
  /** 各工作台徽标（key → number）。 */
}

export default function WorkbenchNav({ active, onChange }: WorkbenchNavProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', py: 1.5 }}>
      {NAV_GROUPS.map((group, gi) => (
        <React.Fragment key={group.title}>
          {gi > 0 && <Divider sx={{ mx: 2, my: 1 }} />}
          <Typography
            variant="caption"
            sx={{ px: 2.5, pb: 0.5, color: 'text.secondary', fontWeight: 600, letterSpacing: '0.25em', fontSize: 11 }}
          >
            {group.title}
          </Typography>
          <List component="nav" disablePadding sx={{ px: 1.5 }}>
            {group.items.map((item) => {
              const selected = active === item.key
              return (
                <ListItemButton
                  key={item.key}
                  selected={selected}
                  onClick={() => onChange(item.key)}
                  sx={{
                    borderRadius: 2,
                    mb: 0.5,
                    py: 1.1,
                    position: 'relative',
                    '&.Mui-selected': {
                      bgcolor: (theme) => theme.palette.mode === 'dark' ? `${ink.cinnabar}26` : ink.cinnabarSoft,
                      color: (theme) => theme.palette.mode === 'dark' ? '#F0A09A' : ink.cinnabarDeep,
                      '& .MuiListItemIcon-root': { color: 'inherit' },
                      '&:hover': {
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? `${ink.cinnabar}33` : '#F6D5D3',
                      },
                      '&::before': {
                        content: '""',
                        position: 'absolute',
                        left: 0,
                        top: '20%',
                        bottom: '20%',
                        width: 3,
                        borderRadius: 2,
                        bgcolor: ink.cinnabar,
                      },
                    },
                    '&:hover': {
                      bgcolor: 'action.hover',
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 38, color: selected ? 'inherit' : 'text.secondary' }}>
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{ fontSize: 14, fontWeight: selected ? 700 : 400 }}
                  />
                </ListItemButton>
              )
            })}
          </List>
        </React.Fragment>
      ))}
      <Box sx={{ flex: 1 }} />
      <Box sx={{ px: 2.5, pb: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: '0.1em' }}>
          v2.0.1 · 墨韵
        </Typography>
      </Box>
    </Box>
  )
}
