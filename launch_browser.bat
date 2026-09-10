@echo off
setlocal

echo =======================================================
echo   Launching Browser with Remote Debugging (Port 9222)
echo =======================================================
echo.

set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CHROME_PATH_X86="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set EDGE_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set EDGE_PATH_X64="C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set BROWSER_EXE=""

if exist %CHROME_PATH% (
    set BROWSER_EXE=%CHROME_PATH%
    echo Found Google Chrome (64-bit).
) else if exist %CHROME_PATH_X86% (
    set BROWSER_EXE=%CHROME_PATH_X86%
    echo Found Google Chrome (32-bit).
) else if exist %EDGE_PATH% (
    set BROWSER_EXE=%EDGE_PATH%
    echo Found Microsoft Edge.
) else if exist %EDGE_PATH_X64% (
    set BROWSER_EXE=%EDGE_PATH_X64%
    echo Found Microsoft Edge (64-bit).
) else (
    echo [ERROR] Neither Google Chrome nor Microsoft Edge was found at default paths.
    pause
    exit /b 1
)

set PROFILE_DIR="%LOCALAPPDATA%\LocalBrowserAgent\Profile"
if not exist %PROFILE_DIR% mkdir %PROFILE_DIR%

echo.
echo Starting browser on port 9222...
echo Profile data saved to: %PROFILE_DIR%
echo.

start "" %BROWSER_EXE% --remote-debugging-port=9222 --user-data-dir=%PROFILE_DIR% "https://ewf.companieshouse.gov.uk"

echo Browser launched successfully!
echo You can now log in and navigate to your form.
echo Once the form is open, run:
echo   python fill_aa02.py
echo.
pause
