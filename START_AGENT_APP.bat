@echo off
title Companies House Form Assistant
cd /d "%~dp0"

echo Starting Companies House Form Assistant...
start "" pythonw gui_app.py

if %ERRORLEVEL% NEQ 0 (
    echo Launching with standard python...
    start "" python gui_app.py
)
