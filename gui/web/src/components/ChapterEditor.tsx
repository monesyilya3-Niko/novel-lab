// ChapterEditor：章节正文编辑器（基于 Tiptap，设计灵感来自 steven-tey/novel，Apache-2.0）。
// 定位：比 textarea 更干净的中文长文编辑面，带实时字数统计与占位提示。
// 数据契约：value/onChange 均为纯文本（后端只收纯文本），编辑器内部富文本状态不外泄。
import { useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import CharacterCount from '@tiptap/extension-character-count'
import Placeholder from '@tiptap/extension-placeholder'
import { ink } from '../ink'

interface ChapterEditorProps {
  value: string
  onChange: (text: string) => void
  placeholder?: string
  minHeight?: number
  /** 字数目标（如 1500），达到后显示达标提示 */
  targetChars?: number
}

/** 纯文本 → 编辑器初始 HTML（转义 + 换行分段）。 */
function textToHtml(text: string): string {
  return `<p>${text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '</p><p>')}</p>`
}

export default function ChapterEditor({
  value,
  onChange,
  placeholder = '在此粘贴或编写章节正文……',
  minHeight = 160,
  targetChars,
}: ChapterEditorProps) {
  const editor = useEditor({
    extensions: [
      // 纯文本模式：只保留段落与换行，关闭加粗/标题等 mark，避免"排了版却存不下来"的误会。
      StarterKit.configure({
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        heading: false,
        blockquote: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        horizontalRule: false,
        dropcursor: false,
        gapcursor: false,
      }),
      CharacterCount,
      Placeholder.configure({ placeholder }),
    ],
    content: value ? textToHtml(value) : '',
    editorProps: {
      attributes: {
        style: `min-height: ${minHeight}px; outline: none; font-size: 14px; line-height: 1.9; color: ${ink.text};`,
      },
    },
    onUpdate: ({ editor }) => {
      onChange(editor.getText())
    },
  })

  // 外部 value 变化时同步回编辑器（清空或载入新文本都同步；getText 对比防循环）。
  useEffect(() => {
    if (editor && editor.getText() !== value) {
      if (value === '') {
        editor.commands.clearContent()
      } else {
        editor.commands.setContent(textToHtml(value))
      }
    }
  }, [value, editor])

  const chars = editor?.storage.characterCount.characters() ?? value.length
  const targetMet = targetChars != null && chars >= targetChars

  return (
    <Box
      sx={{
        border: `1px solid ${ink.hairline}`,
        borderRadius: 2,
        backgroundColor: ink.surface,
        '& .tiptap p': { margin: '0 0 0.9em 0' },
        '& .tiptap p.is-editor-empty:first-child::before': {
          content: 'attr(data-placeholder)',
          color: ink.textTertiary,
          float: 'left',
          height: 0,
          pointerEvents: 'none',
        },
        '&:focus-within': { borderColor: ink.accent },
      }}
    >
      <Box sx={{ px: 1.5, py: 1 }}>
        <EditorContent editor={editor} />
      </Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderTop: `1px solid ${ink.hairline}`,
        }}
      >
        {targetChars != null && (
          <Typography variant="caption" sx={{ color: targetMet ? ink.success : ink.textTertiary }}>
            {targetMet ? `已达目标 ${targetChars} 字` : `目标 ${targetChars} 字`}
          </Typography>
        )}
        <Typography variant="caption" sx={{ color: ink.textTertiary }}>
          {chars} 字
        </Typography>
      </Box>
    </Box>
  )
}
