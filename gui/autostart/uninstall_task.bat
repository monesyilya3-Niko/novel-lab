@echo off
rem ============================================================================
rem  novel-lab GUI 开机自启卸载脚本（W09 P1）
rem
rem  删除 install_task.bat 注册的任务计划，并清理启动文件夹中的备用快捷方式。
rem ============================================================================

setlocal

set "TASK_NAME=novel-lab-gui-autostart"

echo [uninstall] 删除开机自启任务：%TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>nul

if %errorlevel%==0 (
    echo [uninstall] 任务计划已删除。
) else (
    echo [uninstall] 任务计划不存在或删除失败。
)

rem 清理启动文件夹中的备用快捷方式（如有）。
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP_DIR%\novel-lab-gui.lnk" (
    del /F /Q "%STARTUP_DIR%\novel-lab-gui.lnk" >nul 2>nul
    echo [uninstall] 已删除启动文件夹快捷方式。
)

pause
endlocal
