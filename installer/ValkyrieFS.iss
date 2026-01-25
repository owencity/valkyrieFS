; ValkyrieFS Inno Setup 스크립트(템플릿)
; - UI(onedir) 설치
; - C# Windows Service 설치/등록/시작
; - 제거 시 서비스 중지/삭제
;
; NOTE: 경로/파일명은 빌드 산출물에 맞게 조정해야 합니다.

[Setup]
AppName=ValkyrieFS
AppVersion=1.0.0
; Inno Setup 6+: {pf} 상수는 이름이 변경되어 경고가 납니다.
; 권장: {autopf} (환경/권한에 따라 적절한 Program Files 경로 자동 선택)
DefaultDirName={autopf}\ValkyrieFS
DefaultGroupName=ValkyrieFS
OutputBaseFilename=ValkyrieFS-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
; 설치기(Setup.exe) 아이콘: 반드시 .ico 권장
; - 파일이 없으면 컴파일이 실패합니다(의도된 동작: 아이콘 누락 방지)
SetupIconFile=..\src\ui\assets\valkyriefs.ico
; 프로그램/기능(앱 제거) 목록의 언인스톨 항목 아이콘
UninstallDisplayIcon={app}\ValkyrieFS.exe

[Files]
; PyInstaller onedir 산출물(예: dist\ValkyrieFS\*)
; Source 경로는 빌드 결과에 맞게 수정하세요.
Source: "..\dist\ValkyrieFS\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; 앱 런타임/바로가기 아이콘(권장): dist에 포함되지 않더라도 설치본에 항상 포함
Source: "..\src\ui\assets\valkyriefs.ico"; DestDir: "{app}\ui\assets"; Flags: ignoreversion

; 서비스 산출물(권장: dotnet publish 결과물을 통째로 포함)
; 예: service\ValkyrieFS.Service\bin\Release\net10.0-windows\win-x64\publish\*
Source: "..\service\ValkyrieFS.Service\bin\Release\net10.0-windows\win-x64\publish\*"; DestDir: "{app}\service"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\ValkyrieFS"; Filename: "{app}\ValkyrieFS.exe"; IconFilename: "{app}\ui\assets\valkyriefs.ico"
Name: "{commondesktop}\ValkyrieFS"; Filename: "{app}\ValkyrieFS.exe"; IconFilename: "{app}\ui\assets\valkyriefs.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면 아이콘 생성"; Flags: unchecked

[Run]
; 설치 후 UI 실행(선택)
Filename: "{app}\ValkyrieFS.exe"; Description: "ValkyrieFS 실행"; Flags: nowait postinstall skipifsilent

[Code]
function ExecAndLog(const FileName, Params: string): Integer;
var
  ResultCode: Integer;
begin
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := -1
  else
    Result := ResultCode;
end;

procedure InstallService();
var
  ScPath, SvcExe: string;
begin
  ScPath := ExpandConstant('{sys}\sc.exe');
  SvcExe := ExpandConstant('"{app}\service\ValkyrieFS.Service.exe"');

  // 기존 서비스가 있으면 삭제 시도(실패해도 진행)
  ExecAndLog(ScPath, 'stop "ValkyrieFS Service"');
  ExecAndLog(ScPath, 'delete "ValkyrieFS Service"');

  // 서비스 생성(로컬시스템, 자동 시작)
  ExecAndLog(ScPath,
    'create "ValkyrieFS Service" binPath= ' + SvcExe +
    ' start= auto obj= LocalSystem');

  // 서비스 시작
  ExecAndLog(ScPath, 'start "ValkyrieFS Service"');
end;

procedure UninstallService();
var
  ScPath: string;
begin
  ScPath := ExpandConstant('{sys}\sc.exe');
  ExecAndLog(ScPath, 'stop "ValkyrieFS Service"');
  ExecAndLog(ScPath, 'delete "ValkyrieFS Service"');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    InstallService();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then begin
    UninstallService();
  end;
end;


