; novel-lab 桌面版 NSIS 自定义卸载脚本（electron-builder 自动包含 build/installer.nsh）
;
; 为什么要清这个目录：electron-updater 把下载下来的整包安装文件缓存在
; %LOCALAPPDATA%\<applicationName>-updater\（本项目 applicationName = novel-lab-desktop），
; NSIS 的卸载逻辑从不触碰它。2026-10-08 在 Windows 10 真机实测：卸载注册表项、
; 桌面/开始菜单快捷方式、安装目录内容都能正常清除，唯独这里留着
; installer.exe 一个文件 89.1 MB —— 等于用户卸载后磁盘上白占 90MB。
;
; 只删 updater 缓存，不碰 %LOCALAPPDATA%\暮冬念春（那是用户的书、资产、报告与数据库，
; 与 deleteAppDataOnUninstall: false 的既有裁决一致：卸载永不删用户数据）。
!macro customUnInstall
  RMDir /r "$LOCALAPPDATA\novel-lab-desktop-updater"
!macroend
