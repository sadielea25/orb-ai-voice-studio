@echo off
title Hands-Free Voice Assistant - Headphones & Room Mode
cd /d "%~dp0"
echo ========================================================
echo   Starting Hands-Free Voice Assistant (Headphones Mode)
echo ========================================================
echo.
python handsfree_duplex.py
pause
