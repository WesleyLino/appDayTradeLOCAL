@echo off
set PYTHONIOENCODING=utf-8
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --log-level debug > backend_startup_uvicorn_v2.log 2>&1
