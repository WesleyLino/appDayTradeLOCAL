@echo off
title QuantumTrade B3 - Local Startup
echo Initializing QuantumTrade B3 Station...

:: Start Backend (UTF-8 Encoding enforced)
start cmd /k "set PYTHONIOENCODING=utf-8 && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Start Frontend
start cmd /k "cd frontend && npm run dev"

echo.
echo QuantumTrade is launching!
echo [Backend]: http://localhost:8000
echo [Frontend]: http://localhost:3000
echo.
pause
