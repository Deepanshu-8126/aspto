Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python -m actions.telegram_control_hub", 0, False
