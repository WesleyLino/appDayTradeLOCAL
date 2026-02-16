@echo off
title QuantumTrade B3 - Local Startup
echo Initializing QuantumTrade B3 Station...

:: Start Backend
start cmd /k "python -m uvicorn backend.main:app --reload --port 8000"

:: Start Frontend
start cmd /k "cd frontend && npm run dev"

echo.
echo QuantumTrade is launching!
echo [Backend]: http://localhost:8000
echo [Frontend]: http://localhost:3000
echo.
pause
