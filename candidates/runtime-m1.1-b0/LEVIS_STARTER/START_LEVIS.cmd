@echo off
setlocal
cd /d "%~dp0"
python levis_desktop.py
if errorlevel 1 (
  echo LEVIS could not start. Python 3 with Tkinter is required.
  pause
)
