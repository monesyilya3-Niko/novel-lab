// 桌面版渲染层与主进程之间唯一的桥。
//
// 只暴露一个函数、只回一个路径字符串：不把 ipcRenderer 递给页面，
// 页面也就拿不到"向主进程发任意消息"的能力。选择器返回的路径仍然要
// 经后端正文准入（gui/text_access）过滤，这里不是安全边界，只是省得
// 用户手打一长串 Windows 路径。
'use strict'

const { contextBridge, ipcRenderer } = require('electron')

// kind: 'dir' 选目录（章节目录），'file' 选单章文件（.txt/.md）
contextBridge.exposeInMainWorld('novelLab', {
  pickPath: (kind) => ipcRenderer.invoke('novel-lab:pick-path', kind),
})
