; Instalador de ForensiX Hash (Inno Setup 6). Lo compila desktop\build_windows.bat:
;   ISCC /DAppVersion=1.0.0 desktop\installer.iss  ->  dist\ForensiX-Hash_1.0.0_x64-setup.exe
;
; Se instala para el usuario actual, sin pedir administrador, en %LOCALAPPDATA%\Programs:
; así la app puede sustituir su propio .exe al actualizarse sola. Quien quiera puede
; instalarla para todos los usuarios desde el primer diálogo.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "ForensiX Hash"
#define AppExe "ForensiX-Hash.exe"
#define AppUrl "https://github.com/ZaperMaster/ForensiX-Hash"

[Setup]
; El AppId identifica la app para actualizar y desinstalar: no cambiarlo nunca.
AppId={{E0640758-6867-4AA4-9CB8-EF8A1A7C52C3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Alejandro Zapata (ForensiX)
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
AppCopyright=Copyright (c) 2026 Alejandro Zapata
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Instalador de {#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=assets\wizard-100.bmp,assets\wizard-150.bmp,assets\wizard-200.bmp
WizardSmallImageFile=assets\wizard-small-100.bmp,assets\wizard-small-150.bmp,assets\wizard-small-200.bmp
ShowLanguageDialog=auto
CloseApplications=yes
RestartApplications=no
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=ForensiX-Hash_{#AppVersion}_x64-setup

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
spanish.LaunchApp=Abrir {#AppName}
english.LaunchApp=Open {#AppName}
spanish.KeepData=Tus registros, la cadena de custodia y los informes PDF no se borran al desinstalar.
english.KeepData=Your records, chain of custody and PDF reports are not deleted when uninstalling.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "ForensiX.Hash.Desktop"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon; AppUserModelID: "ForensiX.Hash.Desktop"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Restos de una actualización automática (el .exe anterior y el descargado)
Type: files; Name: "{app}\{#AppExe}.old"
Type: files; Name: "{app}\{#AppExe}.new"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Solo en una desinstalación normal: en modo silencioso no se espera a nadie.
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    SuppressibleMsgBox(CustomMessage('KeepData'), mbInformation, MB_OK, IDOK);
end;
