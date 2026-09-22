@echo off
title Orb Voice Studio
start msedge --app=http://localhost:8766 --window-size=460,720 || start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8766 --window-size=460,720 || start http://localhost:8766
exit
