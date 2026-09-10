@echo off
title AI Hands-Free Voice Assistant
echo ====================================================
echo   Starting AI Hands-Free Voice & Floating Widget
echo ====================================================

start /B python auto_voice_reader.py
start /B python handsfree_voice_engine.py
start /B python voice_app_server.py
python floating_widget.py

pause
