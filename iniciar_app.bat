@echo off
title PickleScout AI - Servidor y Web App
echo ========================================================
echo        PickleScout AI - Analizador de Videos
echo ========================================================
echo.
echo Iniciando servidor backend y aplicacion web...
echo Accede en tu navegador a: http://127.0.0.1:8000
echo.

cd /d "%~dp0"
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend

pause
