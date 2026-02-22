@echo off
title RL Shadow Monitor — Observacao de Posicoes
echo ============================================================
echo  RL AGENT — SHADOW MODE (apenas observacao)
echo  PPO Agent analisa posicoes abertas e loga recomendacoes
echo  Logs: logs/rl_shadow.log
echo  Pressione Ctrl+C para encerrar
echo ============================================================
echo.
cd /d %~dp0
python backend/rl_shadow_monitor.py
echo.
echo Monitor encerrado.
pause
