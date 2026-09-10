@echo off
rem ============================================================================
rem  novel-lab GUI 启动脚本（启动文件夹备用方案，W09 P1）
rem
rem  职责：定位项目根目录 → 启动 python -m gui.server（阻塞常驻）。
rem  用法：双击运行，或放入 Windows 启动文件夹
rem        （shell:startup → %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup）
rem ============================================================================

setlocal

rem 项目根目录 = 本脚本所在目录的上两级（gui/autostart -> gui -> novel-lab）。
set "PROJECT_ROOT=%~dp0..\.."

rem 切换到项目根，确保相对路径（assets/reports/corpus/gui_state）解析正确。
pushd "%PROJECT_ROOT%"

rem 优先用 python，其次 py 启动器（Windows 常见）。
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] 未找到 python / py 启动器，请先安装 Python 3.9+。
        pause
        popd
        exit /b 1
    )
)

echo [GUI] 启动 novel-lab 服务（项目目录：%PROJECT_ROOT%）...
echo [GUI] 按 Ctrl+C 或关闭本窗口停止服务。

%PY_CMD% -m gui.server

popd
endlocal
