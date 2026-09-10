@echo off
title Orb AI Voice Assistant
echo Starting Orb AI Voice Assistant...
start msedge --app=http://localhost:8766 || start chrome --app=http://localhost:8766 || start http://localhost:8766
exit
