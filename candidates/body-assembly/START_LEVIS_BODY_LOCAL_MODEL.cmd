@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "assemble.py" --adapter ollama %*
) else (
  echo Install the pinned dependencies using README.md first.
  pause
)
