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
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import { ink } from '../ink'
import { useI18n } from '../state/I18nContext'

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
  | 'help'

export interface WorkbenchNavItem {
  key: WorkbenchKey
  label: string
  icon: React.ReactNode
}

export interface WorkbenchNavProps {
  active: WorkbenchKey
  onChange: (key: WorkbenchKey) => void
}

export default function WorkbenchNav({ active, onChange }: WorkbenchNavProps) {
  const { t } = useI18n()

  const navGroups: { title: string; items: WorkbenchNavItem[] }[] = [
    {
      title: t('nav_group_create', '创作'),
      items: [
        { key: 'home', label: t('nav_home', '首页'), icon: <HomeIcon /> },
        { key: 'analysis', label: t('nav_analysis', '分析拆书'), icon: <InsightsIcon /> },
        { key: 'writing', label: t('nav_writing', '辅助写作'), icon: <EditNoteIcon /> },
        { key: 'quality', label: t('nav_quality', '质量检验'), icon: <FactCheckIcon /> },
        { key: 'assets', label: t('nav_assets', '资产库'), icon: <FolderOpenIcon /> },
        { key: 'advanced', label: t('nav_advanced', '高级功能'), icon: <AutoAwesomeIcon /> },
      ],
    },
    {
      title: t('nav_group_manage', '管理'),
      items: [
        { key: 'system', label: t('nav_system', '系统'), icon: <TuneIcon /> },
        { key: 'settings', label: t('nav_settings', '设置'), icon: <SettingsIcon /> },
        { key: 'admin', label: t('nav_admin', '管理后台'), icon: <AdminPanelSettingsIcon /> },
      ],
    },
    {
      title: t('nav_group_help', '帮助'),
      items: [
        { key: 'help', label: t('nav_help', '帮助中心'), icon: <HelpOutlineIcon /> },
      ],
    },
  ]

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', py: 1.5 }}>
      {navGroups.map((group, gi) => (
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
                      color: (theme) => theme.palette.mode === 'dark' ? '#93B4FD' : ink.cinnabarDeep,
                      '& .MuiListItemIcon-root': { color: 'inherit' },
                      '&:hover': {
                        bgcolor: (theme) => theme.palette.mode === 'dark' ? `${ink.cinnabar}33` : '#E4EBFD',
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
          v2.2.0
        </Typography>
      </Box>
    </Box>
  )
}
