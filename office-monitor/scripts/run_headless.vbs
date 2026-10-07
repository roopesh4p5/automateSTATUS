' Silent Background Runner for Office Network Health Monitor
' Runs monitor.py completely hidden without showing any terminal/console window
Option Explicit

Dim objShell, objFSO, scriptDir, monitorDir, monitorScript, pythonExe, cmd

Set objFSO = CreateObject("Scripting.FileSystemObject")
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
monitorDir = objFSO.GetParentFolderName(scriptDir)
monitorScript = monitorDir & "\monitor.py"

' Use pythonw.exe if available, otherwise python.exe
pythonExe = "pythonw.exe"

Set objShell = CreateObject("WScript.Shell")
cmd = """" & pythonExe & """ """ & monitorScript & """"

' Run with WindowStyle 0 (Hidden) and bWaitOnReturn False (Async)
objShell.Run cmd, 0, False
