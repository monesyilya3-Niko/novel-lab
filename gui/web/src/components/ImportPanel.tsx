// 导入面板：拖拽 / 选文件（txt）。
import { useCallback, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import { useApp } from '../state/AppContext'

interface Props {
  compact?: boolean
}

export default function ImportPanel({ compact }: Props) {
  const { importBook, book } = useApp()
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const doImport = useCallback(
    async (path: string) => {
      setLoading(true)
      setError(null)
      try {
        await importBook(path)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    },
    [importBook],
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (!file) return
      // 浏览器无法直接拿到本地绝对路径，这里用文件名提示用户走「选择文件」，
      // 或通过后端上传（首版用 path 方式，需配合后端 file 上传，此处走选择框）。
      if ((file as unknown as { path?: string }).path) {
        doImport((file as unknown as { path: string }).path)
      } else {
        setError('请点击「选择文件」按钮导入（浏览器安全限制无法直接读取拖拽路径）')
      }
    },
    [doImport],
  )

  const onPick = useCallback(() => {
    fileInput.current?.click()
  }, [])

  const onFileChosen = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      const path = (file as unknown as { path?: string }).path
      if (path) {
        doImport(path)
      } else {
        setError('无法获取本地文件绝对路径，请使用支持 path 的环境')
      }
      e.target.value = ''
    },
    [doImport],
  )

  return (
    <Box sx={{ p: compact ? 1.5 : 3 }}>
      <input
        ref={fileInput}
        type="file"
        accept=".txt"
        style={{ display: 'none' }}
        onChange={onFileChosen}
      />
      <Box
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        sx={{
          border: '2px dashed',
          borderColor: dragging ? 'primary.main' : '#ccc',
          borderRadius: 2,
          p: compact ? 2 : 4,
          textAlign: 'center',
          bgcolor: dragging ? 'rgba(25,118,210,0.06)' : 'transparent',
          cursor: 'pointer',
        }}
        onClick={onPick}
      >
        {loading ? (
          <CircularProgress size={24} />
        ) : (
          <>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              导入 .txt 书籍
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              拖拽到此处，或点击选择文件
            </Typography>
          </>
        )}
      </Box>
      {!compact && (
        <Box sx={{ mt: 2 }}>
          <Button variant="contained" onClick={onPick} disabled={loading} fullWidth>
            选择文件
          </Button>
        </Box>
      )}
      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {book && (
        <Alert severity="success" sx={{ mt: 1.5 }}>
          已导入《{book.title}》 · {book.totalChapters} 章
        </Alert>
      )}
    </Box>
  )
}
