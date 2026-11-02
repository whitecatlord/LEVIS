@echo off
setlocal
cd /d "%~dp0"
set "LEVIS_QUALIFICATION_OUTPUT=%TEMP%\LEVIS_B0_qualification_%RANDOM%_%RANDOM%"
where py >nul 2>nul
if errorlevel 1 (
  python qualify.py --output "%LEVIS_QUALIFICATION_OUTPUT%"
) else (
  py -3 qualify.py --output "%LEVIS_QUALIFICATION_OUTPUT%"
)
set "LEVIS_QUALIFICATION_RESULT=%ERRORLEVEL%"
echo Qualification logs: %LEVIS_QUALIFICATION_OUTPUT%
echo Exit code: %LEVIS_QUALIFICATION_RESULT%
echo A passing run does not grant acceptance or promote the runtime.
pause
exit /b %LEVIS_QUALIFICATION_RESULT%
