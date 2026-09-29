// TropePanel：桥段库入口（放在「写作」页签内）。
//
// 浏览桥段库 → 按分类筛选 / 按当前题材过滤适用 → 查看详情 →
// 一键把桥段骨架写入「写作要点」（情节任务），不用手打复制。
import { useEffect, useMemo, useState} from 'react'
import Box from '@mui/material/Box'
import Alert from '@mui/material/Alert'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import FormControlLabel from '@mui/material/FormControlLabel'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import { tropeApi, friendlyError} from '../api/client'
import type { Trope} from '../types'
import { ink} from '../ink'

interface TropePanelProps {
/** 把文本追加到「写作要点」（GeneratePanel 的 task state）。 */
onInsert: (text: string) => void
/** 当前题材（voice 的 genre），用于「只看当前题材适用」过滤。 */
currentGenre?: string
/** 写作要点当前文本：用于防止同一桥段重复写入（命中身份标记即视为已写入）。 */
taskText?: string
}

/** 桥段 → 可直接拼进写作要点的紧凑文本。
 *
 * 首行固定为桥段名标记 ``【name】``：一是让用户在写作要点里一眼看出这段
 * 骨架来自哪个桥段；二是作为防重复写入的身份锚（见 TropePanel 的去重逻辑）。
 */
export function tropeToTaskText(t: Trope): string {
const lines = [`【${t.name}】`]
const s = t.skeleton
if (s) {
if (s.setup) lines.push(`铺垫：${s.setup}`)
if (s.escalation?.length) {
lines.push(`激化：${s.escalation.map((e, i) => `${i + 1}）${e}`).join('')}`)
}
if (s.payoff) lines.push(`引爆：${s.payoff}`)
if (s.aftermath) lines.push(`余波：${s.aftermath}`)
}
if (t.parameters?.length) {
const ps = t.parameters
.map((p) => `${p.name}（${(p.options?? []).join('/')}）`)
.join('；')
lines.push(`可调参数：${ps}`)
}
return lines.join('\n')
}

/** 桥段在写作要点中的身份标记（与 tropeToTaskText 首行一致）。 */
export function tropeTaskMarker(t: Trope): string {
return `【${t.name}】`
}

export default function TropePanel({ onInsert, currentGenre, taskText}: TropePanelProps) {
const [tropes, setTropes] = useState<Trope[]>([])
const [totalCount, setTotalCount] = useState(0)
const [loading, setLoading] = useState(true)
const [error, setError] = useState('')
const [category, setCategory] = useState('全部')
const [keyword, setKeyword] = useState('')
const [onlyApplicable, setOnlyApplicable] = useState(false)
const [selectedId, setSelectedId] = useState('')

useEffect(() => {
tropeApi
.list()
.then((r) => {
setTropes(r.tropes?? [])
setTotalCount(r.total_count?? 0)
setLoading(false)
})
.catch((e) => {
setError(friendlyError(e))
setLoading(false)
})
}, [])

const categories = useMemo(() => {
const s = new Set(tropes.map((t) => t.category).filter(Boolean))
return ['全部',...Array.from(s)]
}, [tropes])

/** 关键词命中的文本面：桥段名 / 分类 / 骨架四段 / 可调参数名。 */
function tropeSearchHaystack(t: Trope): string {
const parts: string[] = [t.name?? '', t.category?? '']
const s = t.skeleton
if (s) {
parts.push(s.setup?? '', s.payoff?? '', s.aftermath?? '')
parts.push(...(s.escalation?? []))
}
parts.push(...(t.parameters?? []).map((p) => p.name?? ''))
parts.push(...(t.commonFailures?? []))
return parts.join('\n').toLowerCase()
}

const filtered = useMemo(() => {
const kw = keyword.trim().toLowerCase()
return tropes.filter((t) => {
if (category!== '全部' && t.category!== category) return false
if (onlyApplicable && currentGenre) {
const ag = t.applicableGenres?? []
if (!ag.includes(currentGenre)) return false
}
if (kw && !tropeSearchHaystack(t).includes(kw)) return false
return true
})
}, [tropes, category, onlyApplicable, currentGenre, keyword])

const selected = tropes.find((t) => t.id === selectedId)?? null

/** 该桥段是否已在写作要点中（按身份标记判定，防重复写入）。 */
const alreadyInserted = !!selected && !!taskText && taskText.includes(tropeTaskMarker(selected))

const doInsert = () => {
if (!selected || alreadyInserted) return
onInsert(tropeToTaskText(selected))
}

return (
<Paper sx={{ p: 2, mb: 2, backgroundColor: ink.surface}}>
<Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1}}>
<Typography variant="subtitle1">桥段库 · 找灵感</Typography>
<Chip size="small" label={`${totalCount} 条`} />
<Typography variant="caption" color="text.secondary" sx={{ ml: 1}}>
灵感枯竭时翻一翻：选一条桥段，一键写入下面的「写作要点」。
</Typography>
</Box>

{loading && <CircularProgress size={20} />}
{error && <Alert severity="error" sx={{ mb: 1}}>{error}</Alert>}

{!loading &&!error && (
<>
<Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 1}}>
<TextField
select
size="small"
label="分类"
value={category}
onChange={(e) => setCategory(e.target.value)}
sx={{ minWidth: 140}}
>
{categories.map((c) => (
<MenuItem key={c} value={c}>{c}</MenuItem>
))}
</TextField>
<TextField
size="small"
label="搜索桥段"
placeholder="关键词：名称 / 骨架 / 参数"
value={keyword}
onChange={(e) => setKeyword(e.target.value)}
sx={{ minWidth: 200}}
/>
<FormControlLabel
control={
<Checkbox
size="small"
checked={onlyApplicable}
onChange={(e) => setOnlyApplicable(e.target.checked)}
disabled={!currentGenre}
/>
}
label={`只看当前题材适用${currentGenre? `（${currentGenre}）`: '（未识别到题材）'}`}
/>
<Typography variant="caption" color="text.secondary">
{filtered.length} / {tropes.length} 条
</Typography>
</Box>

<Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap'}}>
<List
dense
sx={{
width: 280,
maxWidth: '100%',
maxHeight: 320,
overflowY: 'auto',
border: `1px solid ${ink.hairline}`,
borderRadius: 1,
}}
>
{filtered.map((t) => (
<ListItemButton
key={t.id}
selected={t.id === selectedId}
onClick={() => setSelectedId(t.id)}
>
<ListItemText
primary={t.name}
secondary={t.category}
primaryTypographyProps={{ variant: 'body2'}}
/>
</ListItemButton>
))}
{filtered.length === 0 && (
<Typography variant="body2" color="text.secondary" sx={{ p: 2}}>
没有符合筛选的桥段，换个分类或关键词试试。
</Typography>
)}
</List>

<Box sx={{ flex: 1, minWidth: 260}}>
{!selected? (
<Typography variant="body2" color="text.secondary" sx={{ pt: 1}}>
点左侧任意桥段查看骨架（含铺垫→激化→引爆→余波四段式与可调参数）。
</Typography>
): (
<>
<Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap'}}>
<Typography variant="subtitle2">{selected.name}</Typography>
<Chip size="small" label={selected.category} />
{selected.genreScope && selected.genreScope!== 'universal' && (
<Chip size="small" label={selected.genreScope} color="info" />
)}
</Box>
{selected.skeleton?.setup && (
<Typography variant="body2" sx={{ mb: 1}}>
<b>铺垫：</b>{selected.skeleton.setup}
</Typography>
)}
{selected.skeleton?.escalation?.length > 0 && (
<Box sx={{ mb: 1}}>
<Typography variant="body2"><b>激化：</b></Typography>
{selected.skeleton.escalation.map((e, i) => (
<Typography key={i} variant="body2" sx={{ pl: 2}}>
{i + 1}）{e}
</Typography>
))}
</Box>
)}
{selected.skeleton?.payoff && (
<Typography variant="body2" sx={{ mb: 1}}>
<b>引爆：</b>{selected.skeleton.payoff}
</Typography>
)}
{selected.skeleton?.aftermath && (
<Typography variant="body2" sx={{ mb: 1}}>
<b>余波：</b>{selected.skeleton.aftermath}
</Typography>
)}
{selected.parameters?.length > 0 && (
<Typography variant="body2" sx={{ mb: 1}} color="text.secondary">
可调参数：{selected.parameters.map((p) => `${p.name}（${(p.options?? []).join('/')}）`).join('；')}
</Typography>
)}
{selected.commonFailures?.length > 0 && (
<Typography variant="body2" sx={{ mb: 1}} color="warning.main">
常见翻车：{selected.commonFailures.join('；')}
</Typography>
)}
<Button
variant="contained"
size="small"
onClick={doInsert}
disabled={alreadyInserted}
sx={{ mt: 1}}
>
{alreadyInserted? '已在写作要点中': '写入写作要点'}
</Button>
{alreadyInserted && (
<Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block'}}>
该桥段已写入写作要点，无需重复添加。
</Typography>
)}
</>
)}
</Box>
</Box>
</>
)}
</Paper>
)
}
