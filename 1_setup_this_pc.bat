@echo off
REM Right-click this file -> "Run as administrator". Only needed once
REM (run it again later to update llama.cpp).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
