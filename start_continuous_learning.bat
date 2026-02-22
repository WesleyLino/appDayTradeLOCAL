@echo off
title Continuous Learning Worker — Anti Concept Drift
echo ============================================================
echo  SISTEMA IMUNOLOGICO AUTONOMO — Aprendizado Continuo
echo  Rodara ciclo de otimizacao diariamente as 18:05
echo  Pressione Ctrl+C para encerrar
echo ============================================================
echo.
cd /d %~dp0
pythonw backend/continuous_learning_worker.py
echo.
echo Worker encerrado.
pause
