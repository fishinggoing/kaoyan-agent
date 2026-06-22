@echo off
echo ========================================
echo   GradSchool Advisor - 考研智能决策系统
echo ========================================
echo.

echo [1/3] Starting backend server...
start "Backend" cmd /c "cd /d %~dp0backend && %~dp0.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/3] Waiting for backend...
timeout /t 3 /nobreak >nul

echo [3/3] Starting frontend dev server...
cd /d %~dp0frontend
start "Frontend" cmd /c "npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Close the terminal windows to stop the servers.
pause
