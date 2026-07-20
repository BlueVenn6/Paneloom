Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

!ifndef STAGE_DIR
  !error "STAGE_DIR must point to the PyInstaller one-folder output."
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE must be the absolute installer output path."
!endif
!ifndef SOURCE_ROOT
  !error "SOURCE_ROOT must point to the repository root."
!endif
!ifndef WEBVIEW_BOOTSTRAPPER
  !error "WEBVIEW_BOOTSTRAPPER must point to the signed Microsoft bootstrapper."
!endif
!ifndef APP_VERSION
  !define APP_VERSION "0.1.0-beta.1"
!endif

!define APP_REGISTRY_KEY "Software\Paneloom"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Paneloom"
!define WEBVIEW_CLIENT_KEY "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "Paneloom ${APP_VERSION}"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\Paneloom"
InstallDirRegKey HKCU "${APP_REGISTRY_KEY}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64
BrandingText "Paneloom"
Icon "${SOURCE_ROOT}\desktop\resources\paneloom.ico"
UninstallIcon "${SOURCE_ROOT}\desktop\resources\paneloom.ico"

VIProductVersion "0.1.0.1"
VIAddVersionKey /LANG=1033 "ProductName" "Paneloom"
VIAddVersionKey /LANG=1033 "CompanyName" "Paneloom contributors"
VIAddVersionKey /LANG=1033 "FileDescription" "Paneloom Windows installer"
VIAddVersionKey /LANG=1033 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright (c) 2026 Paneloom contributors"

!define MUI_ABORTWARNING
!define MUI_ICON "${SOURCE_ROOT}\desktop\resources\paneloom.ico"
!define MUI_UNICON "${SOURCE_ROOT}\desktop\resources\paneloom.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\Paneloom.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Start Paneloom"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${SOURCE_ROOT}\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Section "-Microsoft Edge WebView2 Runtime" SEC_WEBVIEW
  SetRegView 32
  ReadRegStr $0 HKLM "${WEBVIEW_CLIENT_KEY}" "pv"
  ${If} $0 == ""
    ReadRegStr $0 HKCU "${WEBVIEW_CLIENT_KEY}" "pv"
  ${EndIf}
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    SetOutPath "$TEMP"
    File /oname=MicrosoftEdgeWebview2Setup.exe "${WEBVIEW_BOOTSTRAPPER}"
    DetailPrint "Installing Microsoft Edge WebView2 Runtime..."
    ExecWait '"$TEMP\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
    Delete "$TEMP\MicrosoftEdgeWebview2Setup.exe"
    ${If} $1 != 0
      MessageBox MB_ICONSTOP|MB_OK "Microsoft Edge WebView2 Runtime installation failed with exit code $1. Paneloom was not installed."
      Abort
    ${EndIf}
  ${EndIf}
  SetRegView lastused
SectionEnd

Section "Paneloom application" SEC_APP
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\*"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${APP_REGISTRY_KEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Paneloom"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Paneloom contributors"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\Paneloom.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1

  CreateDirectory "$SMPROGRAMS\Paneloom"
  CreateShortcut "$SMPROGRAMS\Paneloom\Paneloom.lnk" "$INSTDIR\Paneloom.exe" "" "$INSTDIR\Paneloom.exe" 0
  CreateShortcut "$SMPROGRAMS\Paneloom\Uninstall Paneloom.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section /o "Desktop shortcut" SEC_DESKTOP
  SetShellVarContext current
  CreateShortcut "$DESKTOP\Paneloom.lnk" "$INSTDIR\Paneloom.exe" "" "$INSTDIR\Paneloom.exe" 0
SectionEnd

LangString DESC_SEC_APP ${LANG_SIMPCHINESE} "安装 Paneloom 本地桌面应用。"
LangString DESC_SEC_APP ${LANG_ENGLISH} "Install the Paneloom local desktop application."
LangString DESC_SEC_DESKTOP ${LANG_SIMPCHINESE} "在桌面创建 Paneloom 快捷方式。"
LangString DESC_SEC_DESKTOP ${LANG_ENGLISH} "Create a Paneloom shortcut on the desktop."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_APP} $(DESC_SEC_APP)
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP} $(DESC_SEC_DESKTOP)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\Paneloom.lnk"
  Delete "$SMPROGRAMS\Paneloom\Paneloom.lnk"
  Delete "$SMPROGRAMS\Paneloom\Uninstall Paneloom.lnk"
  RMDir "$SMPROGRAMS\Paneloom"

  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "${APP_REGISTRY_KEY}"
  RMDir /r "$INSTDIR"

  ; User settings, logs and encrypted API keys in %LOCALAPPDATA%\Paneloom,
  ; and projects in Documents\Paneloom Projects, are intentionally preserved.
SectionEnd
