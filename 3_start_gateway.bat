@echo off
REM Starts the single link on port 8000. Run on THIS PC after 2_start_server.bat.
cd /d "%~dp0"
python -m pip install --quiet --disable-pip-version-check fastapi uvicorn httpx psutil
python gateway.py
pause
