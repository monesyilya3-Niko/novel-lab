@echo off
rem ============================================================================
rem  novel-lab GUI 开机自启安装脚本（Windows 任务计划，W09 P1）
rem
rem  原理：用 schtasks 注册一个「登录时运行」的任务，指向 start_gui.bat。
rem  用法：右键「以管理员身份运行」，或普通用户运行（任务计划按当前用户登录触发）。
rem ============================================================================

setlocal

set "PROJECT_ROOT=%~dp0..\.."
set "TASK_NAME=novel-lab-gui-autostart"

echo [install] 注册开机自启任务：%TASK_NAME%
echo [install] 脚本路径：%PROJECT_ROOT%\gui\autostart\start_gui.bat

rem 先删除同名旧任务（幂等）。
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>nul

rem /SC ONLOGON  = 当前用户登录时触发
rem /RU          = 以当前用户身份运行
rem /IT          = 仅在用户交互登录时运行（GUI 程序必需，否则无界面/无法弹浏览器）
schtasks /Create /TN "%TASK_NAME%" ^
    /TR "\"%PROJECT_ROOT%\gui\autostart\start_gui.bat\"" ^
    /SC ONLOGON ^
    /RL LIMITED ^
    /IT ^
    /F

if %errorlevel%==0 (
    echo [install] 开机自启安装成功。
    echo [install] 可在「任务计划程序」中查看：%TASK_NAME%
) else (
    echo [install] 安装失败（可能需要管理员权限）。
)

pause
endlocal
