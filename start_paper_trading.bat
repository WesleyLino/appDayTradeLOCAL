@echo off
echo ==========================================
echo      TRADING SYSTEM - PAPER TRADING
echo ==========================================
echo.
echo 1. Iniciando Backend (Python/FastAPI)...
start "Backend Trading" cmd /k "cd backend && python main.py"
echo Backend iniciado em nova janela.
echo.
echo 2. Iniciando Frontend (Next.js)...
start "Frontend Trading" cmd /k "cd frontend && npm run dev"
echo Frontend iniciado em nova janela.
echo.
echo ==========================================
echo Sistema em execucao.
echo Acesse: http://localhost:3000
echo.
echo Para encerrar, feche as janelas abertas.
pause
