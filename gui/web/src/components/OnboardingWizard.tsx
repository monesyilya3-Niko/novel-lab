// 首启引导向导（参考 Jan onboarding：最少必填、随时可跳过）。
// 触发条件：无书籍数据 && 无资产 && 未在本地标记过 onboarded。
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import MobileStepper from '@mui/material/MobileStepper'
import Typography from '@mui/material/Typography'
import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { WorkbenchKey } from '../layout/WorkbenchNav'

const STORAGE_KEY = 'novellab.onboarded'

export function isOnboarded(): boolean {
  return window.localStorage.getItem(STORAGE_KEY) === '1'
}

interface Step {
  title: string
  body: ReactNode
  cta: { label: string; go?: WorkbenchKey }
}

export default function OnboardingWizard({
  onDone,
  onNavigate,
}: {
  onDone: () => void
  onNavigate: (k: WorkbenchKey) => void
}) {
  const [step, setStep] = useState(0)

  const finish = (go?: WorkbenchKey | unknown) => {
    const target = typeof go === 'string' ? (go as WorkbenchKey) : undefined
    window.localStorage.setItem(STORAGE_KEY, '1')
    onDone()
    if (target) onNavigate(target)
  }

  const steps = useMemo<Step[]>(
    () => [
      {
        title: '欢迎使用 novel-lab',
        body: (
          <Typography variant="body2" color="text.secondary">
            把优秀小说拆成可复用的写作资产，再用这些资产驱动创作。
            全流程在本机完成，不会上传任何数据。三步上手，随时可跳过。
          </Typography>
        ),
        cta: { label: '下一步' },
      },
      {
        title: '第一步：导入并拆书',
        body: (
          <Typography variant="body2" color="text.secondary">
            到「分析」页导入一本 TXT 全本，选择题材后启动拆书。
            拆解完成后自动生成文风卡、笔法卡、结构/商业观测等资产与万字分析报告。
          </Typography>
        ),
        cta: { label: '去导入', go: 'analysis' },
      },
      {
        title: '第二步：查看资产与质检',
        body: (
          <Typography variant="body2" color="text.secondary">
            「资产库」浏览全部结构化资产；「质检」页可对任意章节跑 12 维质量检查
            与全书质检；「写作」页用资产注入辅助生成新章节。
          </Typography>
        ),
        cta: { label: '开始使用' },
      },
    ],
    [],
  )

  const current = steps[step]

  return (
    <Dialog open onClose={finish} maxWidth="sm" fullWidth data-testid="onboarding">
      <DialogTitle sx={{ fontWeight: 600 }}>{current.title}</DialogTitle>
      <DialogContent>
        <Box sx={{ minHeight: 88, display: 'flex', alignItems: 'center' }}>{current.body}</Box>
        <MobileStepper
          variant="dots"
          steps={steps.length}
          position="static"
          activeStep={step}
          sx={{ bgcolor: 'transparent', pl: 0 }}
          nextButton={null}
          backButton={null}
        />
      </DialogContent>
      <DialogActions>
        <Button size="small" color="inherit" onClick={() => finish()}>
          跳过
        </Button>
        {step > 0 && (
          <Button size="small" onClick={() => setStep((s) => s - 1)}>
            上一步
          </Button>
        )}
        <Button
          variant="contained"
          size="small"
          onClick={() => (step < steps.length - 1 ? setStep((s) => s + 1) : finish(current.cta.go))}
        >
          {current.cta.label}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
