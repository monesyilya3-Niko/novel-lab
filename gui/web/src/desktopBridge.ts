// 桌面版（Electron）与浏览器两种运行环境的差别收在这里。
//
// 桥由 `desktop/preload.js` 注入，只提供一个 `pickPath(kind)`。浏览器里
// `window.novelLab` 不存在，调用点必须先问 `hasDesktopBridge()` 再渲染按钮，
// 这样同一份 dist 在 `npm run dev` + 浏览器下也不会出现点不动的按钮。
export type PickKind = 'dir' | 'file'

interface NovelLabBridge {
  pickPath?: (kind: PickKind) => Promise<string | null>
}

function bridge(): NovelLabBridge | undefined {
  return (window as unknown as { novelLab?: NovelLabBridge }).novelLab
}

export function hasDesktopBridge(): boolean {
  return typeof bridge()?.pickPath === 'function'
}

/** 用系统原生对话框选路径；用户取消、或不在桌面版里，返回 null。 */
export async function pickPath(kind: PickKind): Promise<string | null> {
  const fn = bridge()?.pickPath
  if (!fn) return null
  try {
    return await fn(kind)
  } catch {
    // 主进程对话框出错时宁可什么都不填：把异常文案塞进路径输入框，
    // 用户会拿它当路径提交，然后收到一句看不懂的"目录不存在"。
    return null
  }
}
