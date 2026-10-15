@echo off
REM Vampires VS Werewolves - Windows 1-Click Connector
python connect.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Notice] Make sure python is in your PATH.
)
pause
