############################################################################################
#      NSIS Installation Script created by NSIS Quick Setup Script Generator v1.09.18
#               Entirely Edited with NullSoft Scriptable Installation System
#              by Vlasis K. Barkas aka Red Wine red_wine@freemail.gr Sep 2006
############################################################################################

!define APP_NAME "Conductor"
!define COMP_NAME "Conductor Technologies"
!define WEB_SITE "http://www.conductortech.com/"
#!define VERSION "00.00.00.01"
!define COPYRIGHT "${COMP_NAME}"
!define DESCRIPTION "Conductor Client"
#!define LICENSE_TXT "eula.txt"
#!define INSTALLER_NAME "ConductorClient.exe"
!define INSTALL_TYPE "SetShellVarContext current"
!define REG_ROOT "HKCU"
!define UNINSTALL_PATH "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

######################################################################

VIProductVersion  "${VERSION}"
VIAddVersionKey "ProductName"  "${APP_NAME}"
VIAddVersionKey "CompanyName"  "${COMP_NAME}"
VIAddVersionKey "LegalCopyright"  "${COPYRIGHT}"
VIAddVersionKey "FileDescription"  "${DESCRIPTION}"
VIAddVersionKey "FileVersion"  "${VERSION}"

######################################################################

SetCompressor ZLIB
Name "${APP_NAME}"
Caption "${APP_NAME}"
OutFile "${INSTALLER_NAME}"
BrandingText "${APP_NAME}"
XPStyle on
InstallDirRegKey "${REG_ROOT}" "${UNINSTALL_PATH}" "UninstallString"
InstallDir "$PROGRAMFILES\${COMP_NAME}"

######################################################################

!include "MUI2.nsh"
!define MUI_ICON conductor_128.ico

!define MUI_ABORTWARNING
!define MUI_UNABORTWARNING

!insertmacro MUI_PAGE_WELCOME

!ifdef LICENSE_TXT
!insertmacro MUI_PAGE_LICENSE "${LICENSE_TXT}"
!endif

!insertmacro MUI_PAGE_DIRECTORY

!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM

!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

!include "EnvVarUpdate.nsh"


######################################################################

Section -MainProgram
${INSTALL_TYPE}
SetOverwrite ifnewer
SetOutPath "$INSTDIR"
File /r /x ".git" "Conductor"

${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR\Conductor"
${EnvVarUpdate} $0 "PYTHONPATH" "A" "HKLM" "$INSTDIR\Conductor"
${EnvVarUpdate} $0 "PYTHONPATH" "A" "HKLM" "$INSTDIR\Conductor\python\Lib\site-packages"
${EnvVarUpdate} $0 "MAYA_SHELF_PATH" "A" "HKLM" "$INSTDIR\Conductor\maya_shelf"
${EnvVarUpdate} $0 "XBMLANGPATH" "A" "HKLM" "$INSTDIR\Conductor\conductor\resources"
${EnvVarUpdate} $0 "NUKE_PATH" "A" "HKLM" "$INSTDIR\Conductor\nuke_menu"

SectionEnd

######################################################################

Section -Icons_Reg
SetOutPath "$INSTDIR"
WriteUninstaller "$INSTDIR\uninstall.exe"

WriteRegStr ${REG_ROOT} "${UNINSTALL_PATH}"  "DisplayName" "${APP_NAME}"
WriteRegStr ${REG_ROOT} "${UNINSTALL_PATH}"  "UninstallString" "$INSTDIR\uninstall.exe"
WriteRegStr ${REG_ROOT} "${UNINSTALL_PATH}"  "DisplayVersion" "${VERSION}"
WriteRegStr ${REG_ROOT} "${UNINSTALL_PATH}"  "Publisher" "${COMP_NAME}"

!ifdef WEB_SITE
WriteRegStr ${REG_ROOT} "${UNINSTALL_PATH}"  "URLInfoAbout" "${WEB_SITE}"
!endif
SectionEnd

######################################################################

Section Uninstall
${INSTALL_TYPE}

Delete "$INSTDIR\uninstall.exe"
!ifdef WEB_SITE
Delete "$INSTDIR\${APP_NAME} website.url"
!endif

DeleteRegKey ${REG_ROOT} "${UNINSTALL_PATH}"

${EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR\Conductor"
${EnvVarUpdate} $0 "PYTHONPATH" "R" "HKLM" "$INSTDIR\Conductor"
${EnvVarUpdate} $0 "PYTHONPATH" "R" "HKLM" "$INSTDIR\Conductor\python\Lib\site-packages"
${EnvVarUpdate} $0 "MAYA_SHELF_PATH" "R" "HKLM" "$INSTDIR\Conductor\maya_shelf"
${EnvVarUpdate} $0 "XBMLANGPATH" "R" "HKLM" "$INSTDIR\Conductor\conductor\resources"
${EnvVarUpdate} $0 "NUKE_PATH" "R" "HKLM" "$INSTDIR\Conductor\nuke_menu"

RMDir /r /REBOOTOK "$INSTDIR"

SectionEnd

######################################################################
