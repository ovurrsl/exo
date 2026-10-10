; EXO data and models live outside $INSTDIR and are preserved by the installer.
; The desktop's explicit uninstall dialog controls model deletion.
!macro NSIS_HOOK_PREUNINSTALL
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "EXO Windows"
!macroend
