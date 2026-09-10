// Markdown 报告富文本渲染：react-markdown + remark-gfm。
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Link from '@mui/material/Link'
import Divider from '@mui/material/Divider'

export interface MarkdownReportProps {
  /** 报告标题。 */
  title?: string
  /** Markdown 源文本。 */
  markdown: string
}

/** 将 markdown 字符串渲染为富文本（支持 GFM 表格/列表/代码块）。 */
export default function MarkdownReport({ title, markdown }: MarkdownReportProps) {
  return (
    <Paper variant="outlined" sx={{ p: 2, bgcolor: '#fff' }}>
      {title && (
        <>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            {title}
          </Typography>
          <Divider sx={{ mb: 1.5 }} />
        </>
      )}
      <Box
        sx={{
          '& h1': { fontSize: '1.4rem', fontWeight: 700, mt: 2, mb: 1 },
          '& h2': { fontSize: '1.2rem', fontWeight: 700, mt: 2, mb: 1 },
          '& h3': { fontSize: '1.05rem', fontWeight: 600, mt: 1.5, mb: 0.5 },
          '& p': { my: 0.75, lineHeight: 1.7 },
          '& ul, & ol': { pl: 3, my: 0.75 },
          '& li': { lineHeight: 1.7 },
          '& code': {
            fontFamily: 'monospace',
            fontSize: '0.85em',
            bgcolor: '#f5f5f5',
            px: 0.5,
            py: 0.2,
            borderRadius: 0.5,
          },
          '& pre': {
            bgcolor: '#f5f5f5',
            p: 1.5,
            borderRadius: 1,
            overflow: 'auto',
            my: 1,
          },
          '& pre code': { bgcolor: 'transparent', px: 0, py: 0 },
          '& table': {
            borderCollapse: 'collapse',
            width: '100%',
            my: 1,
            fontSize: '0.9rem',
          },
          '& th, & td': {
            border: '1px solid #e0e0e0',
            px: 1,
            py: 0.5,
            textAlign: 'left',
          },
          '& th': { bgcolor: '#fafafa', fontWeight: 600 },
          '& blockquote': {
            borderLeft: '3px solid #1976d2',
            pl: 1.5,
            ml: 0,
            color: 'text.secondary',
            my: 1,
          },
          '& hr': { border: 'none', borderTop: '1px solid #eee', my: 1.5 },
          '& a': { color: 'primary.main' },
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href, children }) => (
              <Link href={href} target="_blank" rel="noreferrer">
                {children}
              </Link>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
      </Box>
    </Paper>
  )
}
