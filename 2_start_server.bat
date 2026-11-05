@echo off
REM ============================================================
REM  Starts the model server on this PC (port 8080).
REM  Use this SAME file on BOTH PCs so they serve the same model.
REM ============================================================

REM ---- edit these (keep them identical on both PCs) ----
set MODEL=unsloth/gemma-3-12b-it-GGUF:Q4_K_M
set API_KEY=change-me-server-key
set CONTEXT=16384
set SLOTS=2
REM ------------------------------------------------------
REM MODEL:   Gemma 3 12B (~8 GB) fits fully on both GPUs.
REM          For Gemma 3 27B use unsloth/gemma-3-27b-it-GGUF:Q4_K_M
REM          (part of it spills into RAM, so it runs slower).
REM SLOTS:   how many requests this PC handles at once.
REM          CONTEXT is shared between slots (16384 / 2 = 8192 each).
REM --fit:   fills the GPU first, then uses RAM/CPU for anything left.

"C:\llama\llama-server.exe" ^
  -hf %MODEL% ^
  --fit on ^
  -c %CONTEXT% ^
  --parallel %SLOTS% ^
  --alias gemma ^
  --host 0.0.0.0 --port 8080 ^
  --api-key %API_KEY%

pause
