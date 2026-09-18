; novel-lab Windows 安装器（Inno Setup 6）
; 设计：
; - per-user 安装（无需管理员），默认 {localappdata}\novel-lab
; - 捆绑 CPython 运行时 + git 追踪源码（与绿色版同一份 stage 内容）
; - 快捷方式指向 pythonw.exe（无控制台窗口）；日志在 gui_state/logs/
; - 卸载只删除安装时文件；运行时产生的用户数据（gui_state/ 等）默认保留

#define AppName "novel-lab"
#define AppVersion "1.1.1"
#define AppPublisher "monesyilya3-Niko"
#define AppURL "https://github.com/monesyilya3-Niko/novel-lab"
#define StageDir "dist\novel-lab-portable-v" + AppVersion

[Setup]
AppId={{8E4B6C1A-52D7-4B3E-9A2F-NOVELLAB1000}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=novel-lab-setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
Source: "{#StageDir}\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion
Source: "{#StageDir}\python-runtime\*"; DestDir: "{app}\python-runtime"; Flags: recursesubdirs ignoreversion
Source: "{#StageDir}\Start.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\python-runtime\pythonw.exe"; Parameters: "-m gui.server"; WorkingDir: "{app}\app"; Comment: "novel-lab 工作台（浏览器访问 http://127.0.0.1:8000/）"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python-runtime\pythonw.exe"; Parameters: "-m gui.server"; WorkingDir: "{app}\app"; Tasks: desktopicon

[Run]
Filename: "{app}\python-runtime\python.exe"; Parameters: "-m gui.server"; WorkingDir: "{app}\app"; Flags: nowait postinstall skipifsilent; Description: "立即启动 novel-lab"; 

[UninstallDelete]
; 构建中间产物（如有）随卸载清理；用户数据 gui_state/ 不在安装清单内，默认保留
Type: filesandordirs; Name: "{app}\app\gui\web\node_modules"
